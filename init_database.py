"""One-time database initialisation.

Reads the existing master Excel files at the canonical Recon raw-data path
and seeds:
    database/Agent_Database.xlsx
    database/Master_Database.xlsx
    database/sales_cache.parquet

Run this once after pulling the new code, or any time you need to rebuild
the database from scratch from the source Recon files.

Usage:
    python init_database.py
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import pandas as pd

import db_utils

SOURCE_AGENT = Path(
    r"C:\Disk\LiuLian Tech Sdn. Bhd\Report\Recon & Reverse Recon"
    r"\Raw Data (30 Nov - 23 Mac)\Agent Data.xlsx"
)
SOURCE_MASTER = Path(
    r"C:\Disk\LiuLian Tech Sdn. Bhd\Report\Recon & Reverse Recon"
    r"\Raw Data (30 Nov - 23 Mac)\Master Data.xlsx"
)


def main() -> int:
    db_utils.ensure_db_dir()

    if not SOURCE_AGENT.exists():
        print(f"ERROR: source not found: {SOURCE_AGENT}", file=sys.stderr)
        return 1
    if not SOURCE_MASTER.exists():
        print(f"ERROR: source not found: {SOURCE_MASTER}", file=sys.stderr)
        return 1

    print("=" * 60)
    print(" Initialising sales database from source Excel files")
    print("=" * 60)

    t0 = time.time()
    print(f"\n[1/4] Reading Agent: {SOURCE_AGENT.name}")
    agent = db_utils._read_excel_any_sheet(SOURCE_AGENT)
    print(f"      Loaded {len(agent):,} rows in {time.time()-t0:.1f}s")

    t1 = time.time()
    print(f"\n[2/4] Reading Master: {SOURCE_MASTER.name}")
    master = db_utils._read_excel_any_sheet(SOURCE_MASTER)
    print(f"      Loaded {len(master):,} rows in {time.time()-t1:.1f}s")

    t2 = time.time()
    print(f"\n[3/4] Writing database/Agent_Database.xlsx ...")
    db_utils._write_xlsx(agent, db_utils.AGENT_DB)
    print(f"      Done in {time.time()-t2:.1f}s")

    t3 = time.time()
    print(f"\n[4/4] Writing database/Master_Database.xlsx ...")
    db_utils._write_xlsx(master, db_utils.MASTER_DB)
    print(f"      Done in {time.time()-t3:.1f}s")

    print(f"\nRebuilding combined cache ...")
    db_utils.rebuild_cache()

    print("\n" + "=" * 60)
    print(" Database initialised successfully")
    print("=" * 60)
    print(f" Total time: {time.time()-t0:.1f}s")
    print(f" Files created in: {db_utils.DB_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
