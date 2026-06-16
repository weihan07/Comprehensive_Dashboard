"""Database layer for the Sales Dashboard.

Storage layout (under ./database/):
  - Agent_Database.parquet  - rolling B2B/Agent store (primary, fast appends)
  - Master_Database.parquet - rolling B2C/Master store (primary, fast appends)
  - Agent_Database.xlsx     - human-readable backup, written on demand
  - Master_Database.xlsx    - human-readable backup, written on demand
  - sales_cache.parquet     - fast combined cache used by the dashboard

Daily uploads append to the parquet rolling stores (seconds). The xlsx
backups are only rewritten via export_excel_backup() or a full
rebuild_from_source() — writing 1M+ rows to Excel takes minutes, so it is
no longer done on every upload.

Key functions:
  - read_database()         - load combined DataFrame from cache (or rebuild)
  - append_agent(df)        - append a daily Agent batch, dedup by 订单号
  - append_master(df)       - append a daily Master batch, dedup by 订单号
  - export_excel_backup()   - write the xlsx backups from the rolling stores
  - rebuild_cache()         - regenerate sales_cache.parquet from rolling stores
  - import_status()         - quick description of DB state (row counts, dates)
"""

from __future__ import annotations

import os
import time
from pathlib import Path
import pandas as pd

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

DASHBOARD_DIR = Path(__file__).resolve().parent
DB_DIR = DASHBOARD_DIR / "database"
AGENT_DB = DB_DIR / "Agent_Database.xlsx"
MASTER_DB = DB_DIR / "Master_Database.xlsx"
# Parquet rolling stores — primary store for daily appends (writing the
# 1M-row xlsx on every upload takes minutes; parquet takes ~2 seconds).
# The xlsx files remain as on-demand human-readable backups
# (see export_excel_backup()).
AGENT_DB_PARQUET = DB_DIR / "Agent_Database.parquet"
MASTER_DB_PARQUET = DB_DIR / "Master_Database.parquet"
CACHE_PARQUET = DB_DIR / "sales_cache.parquet"

# Long-term archive folders for every daily Excel the user uploads.
# Each upload is copied here unchanged so a per-day audit trail exists,
# even though the rolling Agent_Database.xlsx / Master_Database.xlsx
# (and the parquet cache) are what the dashboard actually reads.
AGENT_ARCHIVE_DIR = Path(
    r"C:\Disk\LiuLian Tech Sdn. Bhd\Report\Recon & Reverse Recon"
    r"\Raw Data (30 Nov - 23 Mac)\Data\Agent Data"
)
MASTER_ARCHIVE_DIR = Path(
    r"C:\Disk\LiuLian Tech Sdn. Bhd\Report\Recon & Reverse Recon"
    r"\Raw Data (30 Nov - 23 Mac)\Data\Master Data"
)

# Source-of-truth xlsx files (the user edits these directly when fixing data
# issues). 'Reload from source' rebuilds the rolling database + parquet cache
# from these.
SOURCE_AGENT = Path(
    r"C:\Disk\LiuLian Tech Sdn. Bhd\Report\Recon & Reverse Recon"
    r"\Raw Data (30 Nov - 23 Mac)\Agent Data.xlsx"
)
SOURCE_MASTER = Path(
    r"C:\Disk\LiuLian Tech Sdn. Bhd\Report\Recon & Reverse Recon"
    r"\Raw Data (30 Nov - 23 Mac)\Master Data.xlsx"
)

# Order-id columns - used as the primary key for dedup. Master files use
# '订单号' (order id); Agent files use the same.
ORDER_ID_COL = "订单号"

# Source column → dashboard column mapping. Keys are matched after
# lower-casing and replacing spaces with underscores.
COLUMN_RENAME = {
    "国家": "country",
    "订单号": "order_id",
    "售价": "_sales_listed",
    "实际支付": "_sales_paid",
    "结算价": "settlement_price",
    "商品名称": "product",
    "商品信息": "product_info",   # Agent rows use this for product description
    "用户id": "user_id",
    "订单时间": "order_time",
    "注册时间": "register_time",
    "ip国家": "ip_country",
    "运营商": "operator",
    "商品分类": "product_category",
    "面额": "denomination",        # face value / denomination of the recharge
    "代理商名称": "agent_name",    # B2B only — agent/reseller display name
    "来源": "user_source",         # B2C only — acquisition channel / referral source
    "ip地址": "ip_address",        # B2C only — raw IP address of order placement
    "订单状态": "order_status",    # both — completed / failed / pending
    "是否使用优惠券": "coupon_used", # Master only
    "批次号": "batch_number",      # Agent only — purchase batch reference
    "sku名称": "sku_name",         # Master only — SKU label ('50GB，28天', 'RM 50')
    "品牌商": "brand",             # Master only — clean operator/brand name
    "优惠券名称": "coupon_name",   # Master only — campaign name
    "优惠券金额": "coupon_amount", # Master only — coupon discount value
    "是否新人优惠": "new_user_promo",  # Master only — new-user promo flag
    "是否角标产品": "badge_product",   # Master only — featured/badge product flag
    "区号": "area_code",           # both — destination calling code
    "充值号码": "recharge_number", # both — recharged phone number (beneficiary)
    "接口商订单号": "interface_order_id",  # both — supplier-side order id
}

# Source columns we know about but deliberately do not map/use yet.
# Anything outside COLUMN_RENAME + this set is reported as a NEW column
# during import so schema additions don't go unnoticed.
KNOWN_PASSTHROUGH_COLUMNS = {
    "date", "segment", "pin码", "用户名", "useepay订单号", "取消原因",
}


def _known_source_columns() -> set:
    return {str(k).lower().replace(" ", "_") for k in COLUMN_RENAME} | KNOWN_PASSTHROUGH_COLUMNS


def _log(msg: str) -> None:
    print(f"[db] {msg}", flush=True)


def ensure_db_dir() -> None:
    DB_DIR.mkdir(parents=True, exist_ok=True)


def archive_upload(src_path, archive_dir: Path, original_name: str | None = None) -> Path:
    """Copy an uploaded daily Excel into the long-term archive folder.

    The original filename is preserved. If a file with that name already
    exists in the archive, a ``_YYYYMMDD_HHMMSS`` suffix is appended so
    nothing is overwritten.

    Returns the final destination path.
    """
    import shutil
    from datetime import datetime

    src = Path(src_path)
    archive_dir = Path(archive_dir)
    archive_dir.mkdir(parents=True, exist_ok=True)

    safe_name = (original_name or src.name).strip() or src.name
    target = archive_dir / safe_name
    if target.exists():
        stem, suffix = Path(safe_name).stem, Path(safe_name).suffix or ".xlsx"
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        target = archive_dir / f"{stem}_{ts}{suffix}"

    shutil.copy2(src, target)
    _log(f"Archived upload -> {target}")
    return target


# ---------------------------------------------------------------------------
# Excel helpers
# ---------------------------------------------------------------------------

def _read_excel_any_sheet(path: Path) -> pd.DataFrame:
    """Read the first sheet of an xlsx (preferring 'Whole' if present)."""
    try:
        return pd.read_excel(path, sheet_name="Whole")
    except ValueError:
        xls = pd.ExcelFile(path)
        return pd.read_excel(xls, sheet_name=xls.sheet_names[0])


def _read_data_file(path) -> pd.DataFrame:
    """Read a daily data file. Auto-detects the format from the extension.

    Supported:
      .xlsx / .xls / .xlsm   Excel
      .csv                   CSV (auto-detect separator + encoding)
      .tsv                   tab-separated values
    """
    path = Path(path)
    ext = path.suffix.lower()
    if ext in {".xlsx", ".xls", ".xlsm"}:
        return _read_excel_any_sheet(path)
    if ext in {".csv", ".tsv", ".txt"}:
        sep = "\t" if ext == ".tsv" else None  # None -> pandas sniffs
        for enc in ("utf-8", "utf-8-sig", "gbk", "cp1252", "latin-1"):
            try:
                if sep is None:
                    # python engine sniffs the separator but doesn't support low_memory
                    return pd.read_csv(path, encoding=enc, sep=None, engine="python")
                return pd.read_csv(path, encoding=enc, low_memory=False, sep=sep)
            except (UnicodeDecodeError, UnicodeError):
                continue
        # Last resort: silently replace bad bytes so we still get a frame
        return pd.read_csv(path, encoding="utf-8", sep=None, engine="python",
                           encoding_errors="replace")
    raise ValueError(
        f"Unsupported file type: '{path.suffix}'. "
        "Please upload .xlsx, .xls, .xlsm, .csv, or .tsv."
    )


def _write_xlsx(df: pd.DataFrame, path: Path) -> None:
    """Save a DataFrame to xlsx using xlsxwriter (much faster than openpyxl)."""
    ensure_db_dir()
    tmp = path.with_suffix(".tmp.xlsx")
    try:
        df.to_excel(tmp, index=False, engine="xlsxwriter")
    except Exception:
        # Fallback if xlsxwriter is unavailable
        df.to_excel(tmp, index=False, engine="openpyxl")
    os.replace(tmp, path)


# ---------------------------------------------------------------------------
# Parquet rolling stores (primary store for daily appends)
# ---------------------------------------------------------------------------

def _read_rolling(parquet_path: Path, xlsx_path: Path) -> "pd.DataFrame | None":
    """Read a rolling store. Prefers the parquet store; falls back to the
    legacy xlsx (one-time migration path). Returns None when neither exists."""
    if parquet_path.exists():
        t0 = time.time()
        df = pd.read_parquet(parquet_path)
        _log(f"Read {parquet_path.name}: {len(df):,} rows ({time.time()-t0:.1f}s)")
        return df
    if xlsx_path.exists():
        t0 = time.time()
        df = _read_excel_any_sheet(xlsx_path)
        _log(f"Read legacy {xlsx_path.name}: {len(df):,} rows ({time.time()-t0:.1f}s)")
        return df
    return None


def _write_rolling(df: pd.DataFrame, parquet_path: Path) -> None:
    """Write a rolling store as parquet (seconds instead of the minutes a
    1M-row xlsx write takes). Object columns are normalised to the nullable
    'string' dtype so pyarrow doesn't choke on mixed int/str Excel cells."""
    ensure_db_dir()
    out = df.copy()
    for col in out.select_dtypes(include="object").columns:
        out[col] = out[col].astype("string")
    tmp = parquet_path.with_suffix(".tmp.parquet")
    out.to_parquet(tmp, index=False)
    os.replace(tmp, parquet_path)


def _validate_incoming(incoming: pd.DataFrame) -> dict:
    """Import validation report: date range of the batch, columns we have
    never seen before (future schema additions), and missing key columns."""
    info = {"date_min": None, "date_max": None,
            "unknown_columns": [], "missing_expected": []}
    if incoming is None or incoming.empty:
        return info
    for col in ("订单时间", "order_time"):
        if col in incoming.columns:
            dt = pd.to_datetime(incoming[col], errors="coerce")
            if dt.notna().any():
                info["date_min"] = str(dt.min())[:16]
                info["date_max"] = str(dt.max())[:16]
            break
    known = _known_source_columns()
    info["unknown_columns"] = sorted(
        str(c) for c in incoming.columns
        if str(c).strip().lower().replace(" ", "_") not in known
    )
    for required in (ORDER_ID_COL, "订单时间"):
        if required not in incoming.columns:
            info["missing_expected"].append(required)
    return info


# ---------------------------------------------------------------------------
# Append + dedup
# ---------------------------------------------------------------------------

def _append_dedup(existing: pd.DataFrame | None, incoming: pd.DataFrame,
                  key_col: str = ORDER_ID_COL) -> tuple[pd.DataFrame, int, int]:
    """Combine existing + incoming, keeping the latest row per key.

    Returns (merged_df, rows_added, rows_skipped_as_duplicate).
    """
    if incoming is None or incoming.empty:
        return (existing if existing is not None else pd.DataFrame()), 0, 0

    if existing is None or existing.empty:
        merged = incoming.copy()
        added = len(merged)
        if key_col in merged.columns:
            before = len(merged)
            merged = merged.drop_duplicates(subset=[key_col], keep="last")
            added = len(merged)
            return merged, added, before - added
        return merged, added, 0

    # Align column unions
    all_cols = list(dict.fromkeys(list(existing.columns) + list(incoming.columns)))
    existing = existing.reindex(columns=all_cols)
    incoming = incoming.reindex(columns=all_cols)

    if key_col not in all_cols:
        merged = pd.concat([existing, incoming], ignore_index=True)
        return merged, len(incoming), 0

    # New rows = those whose key isn't already in existing
    existing_keys = set(existing[key_col].dropna().astype(str))
    incoming_keys = incoming[key_col].dropna().astype(str)
    is_new = ~incoming_keys.isin(existing_keys)
    new_rows_count = int(is_new.sum())
    dup_count = int(len(incoming) - new_rows_count)

    # Concat then dedup keeping the latest occurrence (incoming wins)
    merged = pd.concat([existing, incoming], ignore_index=True)
    merged = merged.drop_duplicates(subset=[key_col], keep="last")
    return merged, new_rows_count, dup_count


def append_agent(incoming: pd.DataFrame) -> dict:
    """Append a daily Agent batch. Returns a status dict."""
    ensure_db_dir()
    t0 = time.time()
    validation = _validate_incoming(incoming)
    existing = _read_rolling(AGENT_DB_PARQUET, AGENT_DB)
    merged, added, dups = _append_dedup(existing, incoming)
    _log(f"Agent: +{added} new, -{dups} duplicates, total {len(merged):,} rows")
    _write_rolling(merged, AGENT_DB_PARQUET)
    _log(f"{AGENT_DB_PARQUET.name} written")
    rebuild_cache(agent_df=merged)
    elapsed = time.time() - t0
    return {
        "segment": "Agent",
        "added": added,
        "duplicates": dups,
        "total_rows": len(merged),
        "elapsed_seconds": round(elapsed, 1),
        **validation,
    }


def append_master(incoming: pd.DataFrame) -> dict:
    """Append a daily Master batch. Returns a status dict."""
    ensure_db_dir()
    t0 = time.time()
    validation = _validate_incoming(incoming)
    existing = _read_rolling(MASTER_DB_PARQUET, MASTER_DB)
    merged, added, dups = _append_dedup(existing, incoming)
    _log(f"Master: +{added} new, -{dups} duplicates, total {len(merged):,} rows")
    _write_rolling(merged, MASTER_DB_PARQUET)
    _log(f"{MASTER_DB_PARQUET.name} written")
    rebuild_cache(master_df=merged)
    elapsed = time.time() - t0
    return {
        "segment": "Master",
        "added": added,
        "duplicates": dups,
        "total_rows": len(merged),
        "elapsed_seconds": round(elapsed, 1),
        **validation,
    }


def export_excel_backup(progress_callback=None) -> dict:
    """Write the rolling stores back to the human-readable xlsx backups
    on demand (slow for 1M+ rows, so no longer done on every upload)."""
    def _say(msg):
        _log(msg)
        if progress_callback:
            try:
                progress_callback(msg)
            except Exception:
                pass

    out = {"agent_rows": 0, "master_rows": 0}
    t0 = time.time()
    a = _read_rolling(AGENT_DB_PARQUET, AGENT_DB)
    if a is not None:
        _say(f"Writing {AGENT_DB.name} ({len(a):,} rows) ...")
        _write_xlsx(a, AGENT_DB)
        out["agent_rows"] = len(a)
    m = _read_rolling(MASTER_DB_PARQUET, MASTER_DB)
    if m is not None:
        _say(f"Writing {MASTER_DB.name} ({len(m):,} rows) ...")
        _write_xlsx(m, MASTER_DB)
        out["master_rows"] = len(m)
    out["elapsed_sec"] = round(time.time() - t0, 1)
    _say(f"Excel backup complete ({out['elapsed_sec']}s)")
    return out


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------

def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Apply the same lower/replace/rename pipeline used by load_data,
    plus country translation."""
    from country_mapping import translate_country

    df = df.copy()
    df.columns = df.columns.str.lower().str.replace(" ", "_")
    df = df.rename(columns=COLUMN_RENAME)

    has_paid = "_sales_paid" in df.columns
    has_listed = "_sales_listed" in df.columns
    if has_paid and has_listed:
        df["sales"] = df["_sales_paid"].fillna(df["_sales_listed"])
        # Keep the listed price too — listed vs paid = discount depth
        df = df.rename(columns={"_sales_listed": "sales_listed"})
        df = df.drop(columns=["_sales_paid"])
    elif has_paid:
        df = df.rename(columns={"_sales_paid": "sales"})
    elif has_listed:
        df["sales"] = df["_sales_listed"]
        df = df.rename(columns={"_sales_listed": "sales_listed"})

    if df.columns.duplicated().any():
        df = df.loc[:, ~df.columns.duplicated(keep="first")]

    if "order_time" in df.columns:
        df["order_time"] = pd.to_datetime(df["order_time"], errors="coerce")
    if "register_time" in df.columns:
        df["register_time"] = pd.to_datetime(df["register_time"], errors="coerce")
    for col in ["sales", "sales_listed", "settlement_price", "coupon_amount"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    if "country" in df.columns:
        df["country"] = df["country"].map(translate_country)

    # Cast every remaining object column to pandas' nullable 'string' dtype.
    # Excel cells in the same column sometimes parse as int and sometimes as
    # str (e.g. 用户名 / username), which makes pyarrow.Table.from_pandas raise
    # "Expected bytes, got a 'int' object". 'string' dtype normalises this.
    for col in df.select_dtypes(include="object").columns:
        df[col] = df[col].astype("string")

    return df


def rebuild_cache(agent_df: "pd.DataFrame | None" = None,
                  master_df: "pd.DataFrame | None" = None) -> Path:
    """Regenerate sales_cache.parquet from the two rolling xlsx files.

    If ``agent_df`` and/or ``master_df`` are provided (e.g. by
    ``rebuild_from_source``), they are used directly — saving the
    minutes it takes to re-read those files from disk.
    """
    ensure_db_dir()
    frames = []
    if agent_df is not None:
        a = agent_df.copy()
        a["segment"] = "B2B"
        frames.append(a)
        _log(f"Using in-memory Agent frame: {len(a):,} rows")
    else:
        a = _read_rolling(AGENT_DB_PARQUET, AGENT_DB)
        if a is not None:
            a["segment"] = "B2B"
            frames.append(a)
    if master_df is not None:
        m = master_df.copy()
        m["segment"] = "B2C"
        frames.append(m)
        _log(f"Using in-memory Master frame: {len(m):,} rows")
    else:
        m = _read_rolling(MASTER_DB_PARQUET, MASTER_DB)
        if m is not None:
            m["segment"] = "B2C"
            frames.append(m)
    if not frames:
        raise FileNotFoundError(
            "No database files found. Run init_database.py first or import "
            "Agent/Master data via the Import Data tab."
        )
    combined = pd.concat(frames, ignore_index=True)
    combined = _normalize_columns(combined)
    combined = combined.drop_duplicates()
    t0 = time.time()
    combined.to_parquet(CACHE_PARQUET, index=False)
    _log(
        f"sales_cache.parquet written: {len(combined):,} rows, "
        f"{len(combined.columns)} cols ({time.time()-t0:.1f}s)"
    )
    return CACHE_PARQUET


def read_database(columns: list[str] | None = None) -> pd.DataFrame:
    """Load the combined dataset for the dashboard.

    Order of preference:
      1. sales_cache.parquet (fast)
      2. Rebuild cache from xlsx files

    Pass ``columns=[...]`` to read only a subset (much faster + lower memory).
    """
    ensure_db_dir()
    needs_rebuild = True
    if CACHE_PARQUET.exists():
        cmtime = CACHE_PARQUET.stat().st_mtime
        newest_source = max(
            (p.stat().st_mtime for p in
             (AGENT_DB, MASTER_DB, AGENT_DB_PARQUET, MASTER_DB_PARQUET)
             if p.exists()),
            default=0,
        )
        if cmtime >= newest_source:
            needs_rebuild = False
    if needs_rebuild:
        rebuild_cache()
    t0 = time.time()
    if columns is not None:
        # Tolerate older cache files with fewer columns
        import pyarrow.parquet as pq
        available = set(pq.ParquetFile(CACHE_PARQUET).schema_arrow.names)
        wanted = [c for c in columns if c in available]
        df = pd.read_parquet(CACHE_PARQUET, columns=wanted)
    else:
        df = pd.read_parquet(CACHE_PARQUET)
    _log(
        f"Read sales_cache.parquet: {len(df):,} rows, "
        f"{len(df.columns)} cols ({time.time()-t0:.1f}s)"
    )
    return df


# ---------------------------------------------------------------------------
# Reload from source xlsx (Master Data.xlsx + Agent Data.xlsx)
# ---------------------------------------------------------------------------

def rebuild_from_source(progress_callback=None) -> dict:
    """Re-read the source Master Data.xlsx + Agent Data.xlsx (the 'Whole'
    sheets) and OVERWRITE the rolling database files + parquet cache.

    Use this after you have edited the source xlsx files manually in Excel
    and want the dashboard to reflect those changes.

    NOTE: this overwrites database/Agent_Database.xlsx and
    database/Master_Database.xlsx. Any rows previously appended via the
    Import Data flow that are NOT in the source xlsx will be lost — re-do
    those imports after the source rebuild if needed.

    ``progress_callback`` is an optional callable that receives a single
    string argument so the UI can show interim status.
    """
    def _say(msg):
        _log(msg)
        if progress_callback:
            try:
                progress_callback(msg)
            except Exception:
                pass

    if not SOURCE_AGENT.exists():
        raise FileNotFoundError(f"Source Agent file not found: {SOURCE_AGENT}")
    if not SOURCE_MASTER.exists():
        raise FileNotFoundError(f"Source Master file not found: {SOURCE_MASTER}")

    ensure_db_dir()
    t0 = time.time()

    _say(f"Reading source Agent xlsx ({SOURCE_AGENT.name}) ...")
    t = time.time()
    agent = _read_excel_any_sheet(SOURCE_AGENT)
    _say(f"  Agent: {len(agent):,} rows ({time.time()-t:.1f}s)")

    _say(f"Reading source Master xlsx ({SOURCE_MASTER.name}) ...")
    t = time.time()
    master = _read_excel_any_sheet(SOURCE_MASTER)
    _say(f"  Master: {len(master):,} rows ({time.time()-t:.1f}s)")

    _say("Writing rolling parquet stores ...")
    t = time.time()
    _write_rolling(agent, AGENT_DB_PARQUET)
    _write_rolling(master, MASTER_DB_PARQUET)
    _say(f"  Done ({time.time()-t:.1f}s)")

    _say("Writing Agent_Database.xlsx ...")
    t = time.time()
    _write_xlsx(agent, AGENT_DB)
    _say(f"  Done ({time.time()-t:.1f}s)")

    _say("Writing Master_Database.xlsx ...")
    t = time.time()
    _write_xlsx(master, MASTER_DB)
    _say(f"  Done ({time.time()-t:.1f}s)")

    # Build the parquet directly from the in-memory frames we already have —
    # saves the ~7 minutes that re-reading the xlsx would otherwise take.
    _say("Rebuilding parquet cache (in-memory) ...")
    rebuild_cache(agent_df=agent, master_df=master)

    elapsed = time.time() - t0
    _say(f"Reload complete · {elapsed:.0f}s total")
    return {
        "agent_rows": len(agent),
        "master_rows": len(master),
        "elapsed_sec": elapsed,
    }


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------

def source_freshness() -> dict:
    """Compare modification timestamps of source xlsx vs rolling DB files.

    Returns a dict with:
      - source_agent_mtime, db_agent_mtime, agent_stale (bool)
      - source_master_mtime, db_master_mtime, master_stale (bool)
      - any_stale (bool): True iff at least one rolling DB lags its source
    """
    from datetime import datetime

    def _ts(path):
        try:
            return datetime.fromtimestamp(path.stat().st_mtime)
        except FileNotFoundError:
            return None

    out = {
        "source_agent_mtime":  _ts(SOURCE_AGENT),
        "source_master_mtime": _ts(SOURCE_MASTER),
        "db_agent_mtime":      _ts(AGENT_DB),
        "db_master_mtime":     _ts(MASTER_DB),
    }
    out["agent_stale"]  = (out["source_agent_mtime"]  is not None and
                           out["db_agent_mtime"]  is not None and
                           out["source_agent_mtime"]  > out["db_agent_mtime"])
    out["master_stale"] = (out["source_master_mtime"] is not None and
                           out["db_master_mtime"] is not None and
                           out["source_master_mtime"] > out["db_master_mtime"])
    out["any_stale"] = out["agent_stale"] or out["master_stale"]
    return out


def cache_mtime():
    """Modification time of the parquet cache (None when missing)."""
    from datetime import datetime
    try:
        return datetime.fromtimestamp(CACHE_PARQUET.stat().st_mtime)
    except FileNotFoundError:
        return None


def _rolling_summary(parquet_path: Path, xlsx_path: Path) -> tuple:
    """(row_count, max_date_str) for one rolling store — cheap parquet path
    first, legacy full-Excel read only as a fallback."""
    if parquet_path.exists():
        try:
            import pyarrow.parquet as pq
            pf = pq.ParquetFile(parquet_path)
            rows = pf.metadata.num_rows
            max_date = None
            for date_col in ("订单时间", "Date", "date"):
                if date_col in pf.schema_arrow.names:
                    d = pd.read_parquet(parquet_path, columns=[date_col])[date_col]
                    d = pd.to_datetime(d, errors="coerce")
                    if d.notna().any():
                        max_date = str(d.max())
                    break
            return rows, max_date
        except Exception:
            pass
    if xlsx_path.exists():
        try:
            df = _read_excel_any_sheet(xlsx_path)
            max_date = None
            if "Date" in df.columns:
                max_date = str(pd.to_datetime(df["Date"], errors="coerce").max())
            return len(df), max_date
        except Exception:
            pass
    return 0, None


def import_status() -> dict:
    """Return a quick summary of the database state."""
    out = {
        "agent_exists": AGENT_DB_PARQUET.exists() or AGENT_DB.exists(),
        "master_exists": MASTER_DB_PARQUET.exists() or MASTER_DB.exists(),
        "cache_exists": CACHE_PARQUET.exists(),
    }
    out["agent_rows"], out["agent_max_date"] = _rolling_summary(AGENT_DB_PARQUET, AGENT_DB)
    out["master_rows"], out["master_max_date"] = _rolling_summary(MASTER_DB_PARQUET, MASTER_DB)
    return out
