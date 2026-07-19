"""
trading_calendar.py — the IDX bursa calendar, derived from price_history.

price_history is NOT a clean bursa calendar. It holds rows for days the exchange
was closed, left there by two writers that fed each other:

  * sync_price_history_from_eod()  (data/price_fetch.py) copies
    eod_summary.price_close -> price_history with `close` only and no volume.
    Currently unreferenced — the rows it left behind are historical residue,
    not an ongoing leak — but it is still importable.
  * seed_eod_from_price_history()  (algo/summary_rebuild.py) cross-joins the
    price_history date list with the active universe back into eod_summary,
    which is how a closed day acquires a full set of eod rows too.

So one stale carried-forward close on a holiday propagates into both tables and
a closed day starts looking like a trading day in every query that treats
"a date exists in price_history" as "the bursa was open".

Shape of those rows, measured on live data: close copied verbatim from the
previous trading day (811/813 tickers identical) and volume NULL for every
ticker on that date. Note volume is NULL, never 0 — the eod sync never writes
the column at all — so the predicate has to be `volume > 0` (NULL > 0 is NULL,
which WHERE drops) and not `volume != 0`.

A real trading day always has at least one ticker that traded. That is the
whole definition here, and it is deliberately date-level, not row-level:
individual tickers legitimately have NULL volume on a real trading day when
suspended or untraded (~22/day), and those rows must stay in their own
indicator windows.

Validated against the official IDX "Kalender Libur Bursa 2026": applying this
filter to live data reproduces the published Hari Bursa counts for Jan-Jun 2026
exactly (112 of 112) and removes exactly the seven gazetted holidays that had
fabricated rows. See tests/test_trading_calendar.py.
"""
import logging

from core.db import fetchall

log = logging.getLogger("zenith.calendar")

# SQL predicate for "the bursa was open on this date". Kept as a fragment so
# callers that need it inside a larger statement stay in sync with this module.
TRADING_DAY_HAVING = "MAX(volume) > 0"


def trading_dates(conn, date_from: str = None, date_to: str = None) -> list:
    """Distinct IDX trading dates as 'YYYY-MM-DD' strings, oldest first.

    date_from / date_to are inclusive 'YYYY-MM-DD' bounds (price_history.date is
    TEXT in that format, so lexicographic comparison is chronological).
    """
    where, params = [], []
    if date_from:
        where.append("date >= %s")
        params.append(date_from)
    if date_to:
        where.append("date <= %s")
        params.append(date_to)
    clause = ("WHERE " + " AND ".join(where)) if where else ""

    rows = fetchall(conn, f"""
        SELECT date FROM price_history
        {clause}
        GROUP BY date
        HAVING {TRADING_DAY_HAVING}
        ORDER BY date
    """, params)
    return [str(r["date"]) for r in rows]


def next_trading_day_map(conn) -> dict:
    """{'DD-MM-YYYY' -> next trading 'DD-MM-YYYY'} over the full calendar.

    BSJP exits T+1 off 15m candles, so the exit date must be the next day the
    bursa was actually open — not merely the next date present in price_history.
    """
    dmy = [f"{d[8:10]}-{d[5:7]}-{d[:4]}" for d in trading_dates(conn)]
    return {d: dmy[i + 1] for i, d in enumerate(dmy[:-1])}
