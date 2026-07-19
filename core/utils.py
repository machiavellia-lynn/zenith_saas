"""
utils.py — Zenith 2.0 Pure Utility Functions
RULE: Pure functions only. No DB, no HTTP, no Flask imports.
"""
import gc
import os
import re
from datetime import datetime


def parse_date(s: str):
    """DD-MM-YYYY → datetime.date"""
    return datetime.strptime(s, "%d-%m-%Y").date()


def date_to_sortkey(s: str) -> int:
    """DD-MM-YYYY → YYYYMMDD integer for sorting."""
    try:
        d = datetime.strptime(s, "%d-%m-%Y")
        return int(d.strftime("%Y%m%d"))
    except Exception:
        return 0


def format_idr(val) -> str:
    """Format float rupiah value to IDR string (e.g. 1.23 Jt, 45.6 M)."""
    if val is None:
        return "-"
    try:
        val = float(val)
    except (ValueError, TypeError):
        return "-"
    abs_val = abs(val)
    sign = "-" if val < 0 else ""
    if abs_val >= 1_000_000:
        return f"{sign}{abs_val / 1_000_000:.2f} T"
    if abs_val >= 1_000:
        return f"{sign}{abs_val / 1_000:.2f} M"
    if abs_val >= 1:
        return f"{sign}{abs_val:.2f} Jt"
    return f"{sign}{abs_val * 1_000:.2f} rb"


def date_range(date_from: str, date_to: str) -> list[str]:
    """DD-MM-YYYY range inclusive → list of DD-MM-YYYY strings."""
    from datetime import timedelta
    d0 = parse_date(date_from)
    d1 = parse_date(date_to)
    if d0 > d1:
        d0, d1 = d1, d0
    dates, cur = [], d0
    while cur <= d1:
        dates.append(cur.strftime("%d-%m-%Y"))
        cur += timedelta(days=1)
    return dates


def trim_memory():
    """Force GC and return freed heap pages to OS. Safe no-op on non-Linux platforms."""
    gc.collect()
    try:
        import ctypes
        ctypes.CDLL("libc.so.6").malloc_trim(0)
    except Exception:
        pass


_syariah_cache: frozenset | None = None


def load_syariah_reference(syariah_file: str) -> frozenset:
    """Load sharia-compliant tickers (OJK Daftar Efek Syariah) from .md file.

    Same numbered-list format as kompas100.md. Cached after first read — the
    list is static between OJK's twice-yearly revisions (May & November), so
    re-reading it on every request would be wasted I/O.
    """
    global _syariah_cache
    if _syariah_cache is not None:
        return _syariah_cache
    tickers = set()
    try:
        with open(syariah_file, "r", encoding="utf-8") as f:
            for raw in f:
                match = re.match(r"^\d+\.\s*([A-Z]{4})\s*$", raw.strip())
                if match:
                    tickers.add(match.group(1))
    except FileNotFoundError:
        pass
    _syariah_cache = frozenset(tickers)
    return _syariah_cache


def syariah_tickers() -> frozenset:
    """Sharia universe, path resolved from the repo root.

    Convenience wrapper so callers outside the request/template layer don't each
    rebuild the path to syariah.md. Backed by the same cache.
    """
    import os
    path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "syariah.md")
    return load_syariah_reference(path)


def load_kompas100_reference(kompas100_file: str):
    """Load Kompas100 tickers list from .md file."""
    tickers = []
    esg = set()
    try:
        with open(kompas100_file, "r", encoding="utf-8") as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                match = re.match(r"^\d+\.\s*(.+)$", line)
                if not match:
                    continue
                entry = match.group(1).strip()
                parts = [p.strip() for p in re.split(r"\s*-\s*", entry, maxsplit=1)]
                ticker = parts[0].upper()
                if not ticker:
                    continue
                tickers.append(ticker)
                if len(parts) > 1 and "ESG" in parts[1].upper():
                    esg.add(ticker)
    except FileNotFoundError:
        pass
    return frozenset(tickers), frozenset(esg)


