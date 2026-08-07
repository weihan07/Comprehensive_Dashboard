"""Refresh `database/fx_rates.csv` with real, effective-dated FX rates.

Why this exists
---------------
`fx_rates.py` ships a single mid-2025 indicative snapshot. Settlement costs
(`settlement_rmb = settlement_price / rate`) drive Net Contribution, the Profit
Pool, per-operator margin and the supplier scorecard — and **80% of GMV settles
in non-USD/RMB currencies**. Measured against real ECB rates the snapshot is off
by up to +13% (MYR) and −15% (IDR), in *opposite* directions, which distorts
cross-market profit comparisons. This script replaces the guesswork with
per-month rates.

Sources (only currency codes are sent — no business data ever leaves the box):
  * ECB via api.frankfurter.dev — **monthly averages** of daily rates, for the
    30 currencies the ECB publishes (covers ~90% of GMV: MYR, USD, IDR, MXN…).
  * USD-pegged currencies (SAR, AED, QAR…) — derived exactly from the month's
    USD rate times the published peg.
  * Everything else — open.er-api.com (free, no key) latest rate, written for
    the current month only. Earlier months fall back to the snapshot, which
    `fx_rates.rate_for_iso` handles.

Usage
-----
    python scripts/update_fx.py                 # 2025-07 → current month
    python scripts/update_fx.py --start 2026-01
    python scripts/update_fx.py --dry-run

Re-run it monthly (it is idempotent). On any failure the existing CSV is left
untouched. Output columns: iso, month, rate, source
(rate = local currency per 1 RMB, matching fx_rates.COUNTRY_CURRENCY).
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import urllib.request
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import fx_rates  # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "database" / "fx_rates.csv"
FRANKFURTER = "https://api.frankfurter.dev/v1"
ER_API = "https://open.er-api.com/v6/latest/CNY"
DEFAULT_START = "2025-07"          # first month of the dashboard's data

# Currencies hard-pegged to USD → derive from the month's USD rate (exact,
# no external source needed). local_per_RMB = USD_per_RMB * local_per_USD.
USD_PEGS = {
    "SAR": 3.75, "AED": 3.6725, "QAR": 3.64, "OMR": 0.3845,
    "JOD": 0.709, "BHD": 0.376, "PAB": 1.0, "BSD": 1.0, "BMD": 1.0,
    "XCD": 2.70, "BBD": 2.0, "BZD": 2.0, "CUP": 24.0, "DJF": 177.72,
    "ERN": 15.0, "LBP": 89500.0,
}


def _get(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (fx-updater)"})
    with urllib.request.urlopen(req, timeout=45) as r:
        return json.load(r)


def _months(start: str, end: str) -> list[str]:
    y, m = (int(x) for x in start.split("-"))
    ey, em = (int(x) for x in end.split("-"))
    out = []
    while (y, m) <= (ey, em):
        out.append(f"{y:04d}-{m:02d}")
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def _month_bounds(month: str) -> tuple[str, str]:
    """('YYYY-MM-01', 'YYYY-MM-<last day>') for a 'YYYY-MM' string."""
    y, m = (int(x) for x in month.split("-"))
    first = date(y, m, 1)
    next_first = date(y + 1, 1, 1) if m == 12 else date(y, m + 1, 1)
    last = date.fromordinal(next_first.toordinal() - 1)
    return first.isoformat(), last.isoformat()


def fetch_ecb_monthly(symbols: list[str], months: list[str]) -> dict:
    """{(iso, month): average rate} — mean of the month's daily ECB rates."""
    out: dict[tuple[str, str], float] = {}
    syms = ",".join(sorted(symbols))
    for mon in months:
        start, end = _month_bounds(mon)
        try:
            data = _get(f"{FRANKFURTER}/{start}..{end}?base=CNY&symbols={syms}")
        except Exception as exc:
            print(f"  ! {mon}: ECB fetch failed ({exc})")
            continue
        acc: dict[str, list[float]] = {}
        for _day, rates in (data.get("rates") or {}).items():
            for iso, val in rates.items():
                acc.setdefault(iso, []).append(float(val))
        for iso, vals in acc.items():
            if vals:
                out[(iso, mon)] = sum(vals) / len(vals)
        print(f"  · {mon}: {len(acc)} currencies (avg of {len(data.get('rates') or {})} days)")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--start", default=DEFAULT_START, help="first month, YYYY-MM")
    ap.add_argument("--end", default=None, help="last month, YYYY-MM (default: current)")
    ap.add_argument("--dry-run", action="store_true", help="print a summary, write nothing")
    args = ap.parse_args()

    today = date.today()
    end = args.end or f"{today.year:04d}-{today.month:02d}"
    months = _months(args.start, end)
    needed = sorted({iso for (_s, iso, _r) in fx_rates.COUNTRY_CURRENCY.values()})
    print(f"Months : {months[0]} → {months[-1]}  ({len(months)})")
    print(f"Needed : {len(needed)} currencies")

    ecb_all = set(_get(f"{FRANKFURTER}/currencies").keys())
    ecb_syms = [i for i in needed if i in ecb_all and i != "CNY"]
    print(f"\n[1/3] ECB monthly averages for {len(ecb_syms)} currencies …")
    rows: dict[tuple[str, str], tuple[float, str]] = {}
    for (iso, mon), rate in fetch_ecb_monthly(ecb_syms, months).items():
        rows[(iso, mon)] = (rate, "ecb")

    print(f"\n[2/3] Deriving {len(USD_PEGS)} USD-pegged currencies …")
    n_peg = 0
    for mon in months:
        usd = rows.get(("USD", mon))
        if not usd:
            continue
        for iso, peg in USD_PEGS.items():
            if iso in needed:
                rows[(iso, mon)] = (usd[0] * peg, "usd-peg")
                n_peg += 1
    print(f"  · {n_peg} rows derived from the monthly USD rate")

    rest = [i for i in needed if i not in ecb_all and i not in USD_PEGS and i != "CNY"]
    print(f"\n[3/3] Latest rate for {len(rest)} remaining currencies (current month only) …")
    n_live = 0
    try:
        live = (_get(ER_API).get("rates") or {})
        for iso in rest:
            if iso in live:
                rows[(iso, months[-1])] = (float(live[iso]), "er-api-latest")
                n_live += 1
        print(f"  · {n_live} written for {months[-1]}; earlier months fall back to the snapshot")
    except Exception as exc:
        print(f"  ! live fetch failed ({exc}) — those currencies keep the snapshot rate")

    if not rows:
        print("\nNothing fetched — leaving the existing CSV untouched.")
        return 1

    covered = sorted({iso for (iso, _m) in rows})
    print(f"\nTotal {len(rows)} rows · {len(covered)} currencies")
    for iso in ("MYR", "IDR", "MXN", "USD", "SAR", "AED"):
        got = [(m, r) for (i, m), (r, _s) in rows.items() if i == iso]
        if got:
            got.sort()
            snap = {c: r for (_s2, c, r) in fx_rates.COUNTRY_CURRENCY.values()}.get(iso)
            print(f"  {iso}: {got[0][0]}={got[0][1]:.4f} … {got[-1][0]}={got[-1][1]:.4f}"
                  f"   (snapshot {snap})")

    if args.dry_run:
        print("\n--dry-run: nothing written.")
        return 0

    OUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUT.with_suffix(".tmp.csv")
    with open(tmp, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["iso", "month", "rate", "source"])
        for (iso, mon) in sorted(rows):
            rate, src = rows[(iso, mon)]
            w.writerow([iso, mon, f"{rate:.6f}", src])
    tmp.replace(OUT)
    print(f"\nWritten → {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
