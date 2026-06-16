"""Lightweight persistence for per-tab analyst remarks stored in database/remarks.json."""
import json
import os
from datetime import datetime
from pathlib import Path

_REMARKS_FILE = Path(__file__).parent / "database" / "remarks.json"


def _current_month() -> str:
    return datetime.now().strftime("%Y-%m")


def _make_key(tab: str) -> str:
    return f"{tab.lower().replace(' ', '_')}_{_current_month()}"


def load_remarks() -> dict:
    if not _REMARKS_FILE.exists():
        return {}
    try:
        with open(_REMARKS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_remark(tab: str, text: str) -> None:
    remarks = load_remarks()
    remarks[_make_key(tab)] = text.strip()
    _REMARKS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(_REMARKS_FILE, "w", encoding="utf-8") as f:
        json.dump(remarks, f, ensure_ascii=False, indent=2)


def get_remark(tab: str) -> str:
    return load_remarks().get(_make_key(tab), "")
