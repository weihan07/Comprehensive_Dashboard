"""Raw daily-export cleaner for the Sales Dashboard.

Workflow: you download today's CSV from the source system and drop it into
``…/Raw Data…/Data/Master Data``, ``…/Master Data (RM)`` or ``…/Agent Data``.
This module then:

  1. detects the stream (Agent B2B / Master B2C / Master RM),
  2. normalises column names to the unified schema the dashboard expects
     (matching ``db_utils.COLUMN_RENAME`` keys) — Master-RM's different names are
     mapped onto the standard Master schema, so Master + Master-RM merge cleanly,
  3. parses dates with **reversed day/month detection** (some sources are DD/MM),
  4. coerces numeric columns,
  5. auto-fills missing values per a documented policy (and **counts every fill**),
  6. quarantines unrecoverable rows (negative amounts / unparseable order dates),
  7. returns a cleaned DataFrame + a transparent change report.

It is a thin pre-step in front of ``db_utils.append_master`` / ``append_agent``
(which already de-dupe, hash-guard, and rebuild the cache).
"""
from __future__ import annotations

from pathlib import Path
import pandas as pd
import numpy as np

# ── Column-name normalisation per stream → unified names matching COLUMN_RENAME ──

# Master (B2C): UPPERCASE variants → lowercase the dashboard expects.
_MASTER_RENAME = {
    "IP地址": "ip地址", "IP国家": "ip国家", "SKU名称": "sku名称", "用户ID": "用户id",
}

# Master RM (local-currency): differing names mapped onto the standard Master schema.
_MASTER_RM_RENAME = {
    "用户注册时间": "注册时间", "下单时间": "订单时间", "用户名称": "用户名",
    "用户ID": "用户id", "IP地址": "ip地址", "IP国家": "ip国家", "SKU名称": "sku名称",
    "售价(当地币)": "售价", "实际支付(当地币)": "实际支付", "服务费(当地币)": "服务费",
    "优惠金额(当地币)": "优惠券金额", "是否新人价": "是否新人优惠", "是否折扣价": "是否折扣金额",
    "支付订单号": "useepay订单号", "供应商订单号": "接口商订单号", "订单来源": "来源",
    "供应商名称": "供应商名称", "供应商ID": "供应商id",
}

_DATE_COLS = ["订单时间", "注册时间"]
_NUM_COLS  = ["售价", "结算价", "实际支付", "面额", "优惠券金额", "税费", "服务费"]

# Missing-value policy (auto-fill + report):
_FILL_ZERO    = ["优惠券金额", "税费", "服务费"]                                  # amounts → 0
_FILL_BLANK   = ["优惠券名称", "取消原因", "用户名", "sku名称", "商品名称",
                 "unionid", "接口商订单号", "useepay订单号", "充值号码", "pin码", "PIN码"]  # text → ''
_FILL_UNKNOWN = ["国家", "订单状态"]                                             # key dims → 'Unknown'


def detect_stream(cols) -> str:
    cset = {str(c).strip() for c in cols}
    if {"下单时间", "用户注册时间"} & cset or "售价(当地币)" in cset or "实际支付(当地币)" in cset:
        return "master_rm"
    if "代理商名称" in cset or "批次号" in cset or ("商品信息" in cset and "用户ID" not in cset):
        return "agent"
    return "master"


def segment_of(stream: str) -> str:
    """Which dashboard segment this stream feeds (Master + Master-RM = B2C)."""
    return "agent" if stream == "agent" else "master"


def _parse_dates(series: pd.Series, report: dict, col: str) -> pd.Series:
    """Robust date parse with reversed day/month handling.

    Tries the standard parse first; if many rows fail, retries dayfirst=True and
    keeps whichever recovers more. Reports the parsed date range so a reversed
    column (which yields an absurd range) is easy to spot, and flags ambiguity.
    """
    s = series.astype("string").str.strip()
    nonblank = s.notna() & (s != "") & (s.str.lower() != "nan")
    dt = pd.to_datetime(s, errors="coerce")
    failed = nonblank & dt.isna()
    if nonblank.sum() and failed.mean() > 0.2:
        dt2 = pd.to_datetime(s, errors="coerce", dayfirst=True)
        if dt2.notna().sum() > dt.notna().sum():
            dt = dt2
            report.setdefault("date_dayfirst", []).append(col)
    valid = dt.dropna()
    if len(valid):
        report.setdefault("date_range", {})[col] = f"{valid.min():%Y-%m-%d} → {valid.max():%Y-%m-%d}"
        # ambiguity hint: every day ≤ 12 means DD/MM vs MM/DD is indistinguishable
        amb = ((valid.dt.day <= 12).mean() == 1.0)
        if amb:
            report.setdefault("date_ambiguous", []).append(col)
    return dt


def clean(df: pd.DataFrame, stream: str | None = None) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Clean one raw export. Returns (cleaned_df, quarantined_df, report)."""
    report: dict = {"stream": None, "segment": None, "rows_in": int(len(df)),
                    "renamed": {}, "coerced": [], "filled": {}, "quarantined": 0,
                    "notes": []}
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    stream = stream or detect_stream(df.columns)
    report["stream"] = stream
    report["segment"] = segment_of(stream)

    # 1 · normalise column names
    rmap = {"master": _MASTER_RENAME, "master_rm": _MASTER_RM_RENAME, "agent": {}}[stream]
    actual = {k: v for k, v in rmap.items() if k in df.columns}
    # generic safety net for any remaining UPPERCASE variants
    for c in list(df.columns):
        if c in ("IP地址", "IP国家", "SKU名称", "用户ID") and c not in actual:
            actual[c] = {"IP地址": "ip地址", "IP国家": "ip国家",
                         "SKU名称": "sku名称", "用户ID": "用户id"}[c]
    df = df.rename(columns=actual)
    report["renamed"] = actual

    # 2 · dates  (reversed day/month aware)
    for c in _DATE_COLS:
        if c in df.columns:
            df[c] = _parse_dates(df[c], report, c)
            report["coerced"].append(c)

    # 3 · numerics
    for c in _NUM_COLS:
        if c in df.columns:
            df[c] = pd.to_numeric(
                df[c].astype("string").str.replace(",", "", regex=False).str.strip(),
                errors="coerce")
            report["coerced"].append(c)

    # 4 · quarantine unrecoverable rows
    bad = pd.Series(False, index=df.index)
    for c in ("实际支付", "售价"):
        if c in df.columns:
            bad = bad | (df[c] < 0)
    if "订单时间" in df.columns:
        bad = bad | df["订单时间"].isna()
    report["quarantined"] = int(bad.sum())
    quarantined = df[bad].copy()
    df = df[~bad].copy()

    # 5 · auto-fill missing values (per policy) + count
    def _fill(cols, value, tag):
        for c in cols:
            if c in df.columns:
                n = int(df[c].isna().sum())
                if n:
                    df[c] = df[c].fillna(value)
                    report["filled"][c] = f"{n} → {tag}"
    _fill(_FILL_ZERO, 0, "0")
    _fill(_FILL_BLANK, "", "''")
    _fill(_FILL_UNKNOWN, "Unknown", "Unknown")

    # 6 · trim whitespace
    for c in df.columns:
        if df[c].dtype == object or str(df[c].dtype) == "string":
            df[c] = df[c].astype("string").str.strip()

    report["rows_out"] = int(len(df))
    return df, quarantined, report


# ── Daily orchestration ──────────────────────────────────────────────────────

_DEFAULT_DATA_ROOT = Path(
    r"C:\Disk\LiuLian Tech Sdn. Bhd\Report\Recon & Reverse Recon\Raw Data (30 Nov - 23 Mac)\Data")
_STREAM_FOLDERS = {"master": ["Master Data", "Master Data (RM)"], "agent": ["Agent Data"]}


def _read_csv(path: Path) -> pd.DataFrame:
    for enc in ("utf-8-sig", "gb18030", "utf-8"):
        try:
            return pd.read_csv(path, dtype=str, encoding=enc)
        except Exception:
            continue
    return pd.read_csv(path, dtype=str, encoding="latin-1")


def scan(data_root=None) -> list[Path]:
    """All dashboard-relevant raw CSVs (Master, Master-RM, Agent)."""
    root = Path(data_root) if data_root else _DEFAULT_DATA_ROOT
    files = []
    for subs in _STREAM_FOLDERS.values():
        for sub in subs:
            files += sorted((root / sub).glob("*.csv"))
    return files


def _file_hash(path: Path) -> str:
    import hashlib
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def _processed_path() -> Path:
    import db_utils
    return db_utils.AGENT_DB_PARQUET.parent / "cleaned_imports.json"


def _load_processed() -> set:
    import json
    p = _processed_path()
    if p.exists():
        try:
            return set(json.load(open(p, encoding="utf-8")))
        except Exception:
            return set()
    return set()


def _save_processed(hashes: set):
    import json
    try:
        p = _processed_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        json.dump(sorted(hashes), open(p, "w", encoding="utf-8"))
    except Exception:
        pass


def import_new_daily(data_root=None, dry_run: bool = True) -> dict:
    """Clean every dashboard raw CSV not yet processed, then (unless dry_run) append
    per segment in ONE batch each (single cache rebuild). Skips files already done
    by raw-content hash (database/cleaned_imports.json). Returns a summary dict."""
    import db_utils
    root = Path(data_root) if data_root else _DEFAULT_DATA_ROOT
    processed = _load_processed()
    file_reports, batches, new_hashes = [], {"master": [], "agent": []}, set()
    for seg, subs in _STREAM_FOLDERS.items():
        for sub in subs:
            for f in sorted((root / sub).glob("*.csv")):
                fh = _file_hash(f)
                if fh in processed:
                    file_reports.append({"file": f.name, "skipped": "already imported"})
                    continue
                try:
                    cleaned, quar, rep = clean(_read_csv(f))
                except Exception as exc:
                    file_reports.append({"file": f.name, "error": str(exc)})
                    continue
                rep["file"] = f.name
                batches[rep["segment"]].append(cleaned)
                new_hashes.add(fh)
                file_reports.append(rep)
    summary = {"files": file_reports, "import": {}}
    if not dry_run:
        for seg, frames in batches.items():
            if frames:
                combined = pd.concat(frames, ignore_index=True)
                fn = db_utils.append_master if seg == "master" else db_utils.append_agent
                summary["import"][seg] = fn(combined)
        _save_processed(processed | new_hashes)
    return summary


# ── Full rebuild from Data/ (history xlsx + daily CSVs) ──────────────────────
# Makes Data/ the SOLE raw source: the multi-sheet history workbooks supply the
# back-history and the daily-CSV subfolders supply recent days. One-time, slow
# (reads the big xlsx once); afterwards import_new_daily() handles new CSVs fast.

# Authoritative history workbooks in Data/ (each split by period across sheets).
_HISTORY_FILES = {
    "master": ["Master Data (1 Jul - 10 May).xlsx"],
    "agent":  ["Agent Data (1 Jul - 31 Mac).xlsx"],
}


def _read_history_xlsx(path: Path) -> pd.DataFrame:
    """Read EVERY sheet of a history workbook (period-split) and concat them.
    Identifier columns are forced to text via ``db_utils._STR_DTYPE`` so 18–19
    digit order numbers keep full precision (no float corruption)."""
    import db_utils
    sheets = pd.read_excel(path, sheet_name=None, dtype=db_utils._STR_DTYPE)
    frames = [s for s in sheets.values() if len(s)]
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def _read_source(path: Path) -> pd.DataFrame:
    if path.suffix.lower() in (".xlsx", ".xls", ".xlsm"):
        return _read_history_xlsx(path)
    return _read_csv(path)


def _segment_sources(root: Path, seg: str) -> list[Path]:
    """History workbook(s) first, then the daily-CSV subfolders (so a later
    daily export of the same order wins in keep='last' de-dup)."""
    paths = [root / n for n in _HISTORY_FILES.get(seg, []) if (root / n).exists()]
    for sub in _STREAM_FOLDERS[seg]:
        paths += sorted((root / sub).glob("*.csv"))
    return paths


def build_segment_frame(root: Path, seg: str) -> tuple["pd.DataFrame | None", list]:
    """Clean every source for a segment, concat, and de-dup by 订单号 (keep the
    most-recent export). Returns (frame, per-file reports)."""
    reports, frames = [], []
    for p in _segment_sources(root, seg):
        try:
            cleaned, _quar, rep = clean(_read_source(p))
        except Exception as exc:
            reports.append({"file": p.name, "error": str(exc)})
            continue
        rep["file"] = p.name
        reports.append(rep)
        frames.append(cleaned)
    if not frames:
        return None, reports
    combined = pd.concat(frames, ignore_index=True)
    before = len(combined)
    if "订单号" in combined.columns:
        combined = combined.drop_duplicates(subset=["订单号"], keep="last")
    reports.append({"rows_concat": before, "after_dedup": len(combined),
                    "overlap_removed": before - len(combined)})
    return combined.reset_index(drop=True), reports


def full_rebuild_from_data(data_root=None, dry_run: bool = True) -> dict:
    """Rebuild the WHOLE database from Data/ raw (history xlsx + daily CSVs),
    replacing the rolling stores + cache with correct text order_ids.

    dry_run=True (default): build + summarise only, write nothing.
    dry_run=False: write Master/Agent rolling parquet stores, rebuild the cache,
    and mark every daily CSV processed so import_new_daily() won't re-add them."""
    import db_utils
    root = Path(data_root) if data_root else _DEFAULT_DATA_ROOT
    master_df, mrep = build_segment_frame(root, "master")
    agent_df,  arep = build_segment_frame(root, "agent")

    def _summ(df):
        if df is None or not len(df):
            return {"rows": 0}
        dt = pd.to_datetime(df.get("订单时间"), errors="coerce")
        return {"rows": int(len(df)),
                "date_min": str(dt.min())[:10], "date_max": str(dt.max())[:10]}

    summary = {"master": _summ(master_df), "agent": _summ(agent_df),
               "master_files": mrep, "agent_files": arep, "applied": False}
    if not dry_run:
        if master_df is not None:
            db_utils._write_rolling(master_df, db_utils.MASTER_DB_PARQUET)
        if agent_df is not None:
            db_utils._write_rolling(agent_df, db_utils.AGENT_DB_PARQUET)
        db_utils.rebuild_cache(agent_df=agent_df, master_df=master_df)
        hashes = {_file_hash(p) for subs in _STREAM_FOLDERS.values()
                  for sub in subs for p in (root / sub).glob("*.csv")}
        _save_processed(hashes)
        summary["applied"] = True
    return summary


if __name__ == "__main__":
    import json
    import sys
    if "--full-rebuild" in sys.argv:
        res = full_rebuild_from_data(dry_run="--apply" not in sys.argv)
        print(json.dumps({k: res[k] for k in ("master", "agent", "applied")},
                         ensure_ascii=False, default=str))
    else:
        dry = "--import" not in sys.argv   # default dry-run; pass --import to actually load
        res = import_new_daily(dry_run=dry)
        for r in res["files"]:
            print(json.dumps({k: r[k] for k in r if k != "import"}, ensure_ascii=False, default=str))
        if not dry:
            print("IMPORT:", json.dumps(res["import"], ensure_ascii=False, default=str))
