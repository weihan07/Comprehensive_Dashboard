"""Offline IP → city / subdivision geolocation (DB-IP City Lite, MMDB format).

Reads ``database/dbip-city-lite.mmdb`` via ``maxminddb`` (pure-python,
memory-mapped). **Fully offline** — no network calls, no external API; raw IPs
never leave the machine, only aggregated regions are ever shown. Used to drill
the country-level maps down to **state / province (subdivision)** for the B2C
IP failure map.

Degrades gracefully: ``available()`` returns False (and ``lookup`` returns None)
when the library or the .mmdb file is missing, so the dashboard still runs.

To (re)fresh the database: download the free, no-account DB-IP City Lite build
and drop it in ``database/`` (kept out of git):
    https://download.db-ip.com/free/dbip-city-lite-YYYY-MM.mmdb.gz
    gunzip → database/dbip-city-lite.mmdb
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

_DB_PATH = Path(__file__).parent / "database" / "dbip-city-lite.mmdb"
_reader = None
_tried = False


def _get_reader():
    global _reader, _tried
    if _reader is None and not _tried:
        _tried = True
        try:
            import maxminddb
            if _DB_PATH.exists():
                _reader = maxminddb.open_database(str(_DB_PATH))
        except Exception:
            _reader = None
    return _reader


def available() -> bool:
    """True when the mmdb + reader are ready to resolve IPs."""
    return _get_reader() is not None


def db_path() -> str:
    return str(_DB_PATH)


def _name(node) -> str | None:
    names = (node or {}).get("names") or {}
    return names.get("en") or (next(iter(names.values()), None) if names else None)


@lru_cache(maxsize=500_000)
def lookup(ip: str):
    """Resolve one IP → dict(iso2, country, subdivision, city, lat, lon), or
    None if the db is unavailable / the IP doesn't resolve. Cached per IP."""
    reader = _get_reader()
    if reader is None or not ip:
        return None
    try:
        rec = reader.get(ip)
    except (ValueError, Exception):
        return None
    if not rec:
        return None
    country = rec.get("country") or {}
    subs = rec.get("subdivisions") or []
    loc = rec.get("location") or {}
    return {
        "iso2": country.get("iso_code"),
        "country": _name(country),
        "subdivision": _name(subs[0]) if subs else None,
        "city": _name(rec.get("city")),
        "lat": loc.get("latitude"),
        "lon": loc.get("longitude"),
    }
