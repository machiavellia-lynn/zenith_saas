"""
summary_rebuild.py — Zenith 2.0 Flow Aggregation
Aggregate raw SM/BM/MF data from raw tables → eod_summary (flow fields only).
RULE: Only write flow columns (sm_val, bm_val, tx_count, mf_plus, mf_minus, vwap_sm, vwap_bm).
      Analytics fields (price_close, sri, phase, action, etc.) are written by analytics_daily.py.
"""
import logging
from core.db import get_db, fetchall, execute

log = logging.getLogger("zenith.summary_rebuild")
log.setLevel(logging.INFO)


def rebuild_summary_for_date(conn, date_str: str, full_reset: bool = False):
    """
    Aggregate raw data for date_str into eod_summary (flow fields only).

    full_reset=False (default): upsert — preserve analytics fields.
    full_reset=True: delete and rebuild from scratch.
    """
    if full_reset:
        execute(conn, "DELETE FROM eod_summary WHERE date = %s", [date_str])

    # ── SM/BM aggregation ────────────────────────────────────────────────
    sm_rows = fetchall(conn, """
        SELECT ticker,
               SUM(CASE WHEN channel = 'smart' THEN value_numeric ELSE 0 END) AS sm_val,
               SUM(CASE WHEN channel = 'bad'   THEN value_numeric ELSE 0 END) AS bm_val,
               COUNT(*) AS tx_count,
               COUNT(CASE WHEN channel = 'smart' THEN 1 END) AS tx_sm,
               COUNT(CASE WHEN channel = 'bad'   THEN 1 END) AS tx_bm,
               SUM(CASE WHEN channel = 'smart' AND value_numeric != 0
                        THEN price * ABS(value_numeric) ELSE 0 END) /
               NULLIF(SUM(CASE WHEN channel = 'smart' AND value_numeric != 0
                               THEN ABS(value_numeric) ELSE 0 END), 0) AS vwap_sm,
               SUM(CASE WHEN channel = 'bad' AND value_numeric != 0
                        THEN price * ABS(value_numeric) ELSE 0 END) /
               NULLIF(SUM(CASE WHEN channel = 'bad' AND value_numeric != 0
                               THEN ABS(value_numeric) ELSE 0 END), 0) AS vwap_bm
        FROM raw_messages
        WHERE date = %s AND channel IN ('smart', 'bad')
        GROUP BY ticker
    """, [date_str])

    # ── MF aggregation ───────────────────────────────────────────────────
    mf_rows = fetchall(conn, """
        SELECT ticker,
               SUM(CASE WHEN channel = 'mf_plus'  THEN mf_numeric ELSE 0 END) AS mf_plus,
               SUM(CASE WHEN channel = 'mf_minus' THEN mf_numeric ELSE 0 END) AS mf_minus
        FROM raw_mf_messages
        WHERE date = %s
        GROUP BY ticker
    """, [date_str])

    mf_map = {r["ticker"]: r for r in mf_rows}

    if not sm_rows:
        log.warning("⚠️ No SM/BM data found in raw_messages for date=%s", date_str)

    for row in sm_rows:
        ticker = row["ticker"]
        mf     = mf_map.get(ticker, {})
        execute(conn, """
            INSERT INTO eod_summary (date, ticker, sm_val, bm_val, tx_count, tx_sm, tx_bm,
                                     mf_plus, mf_minus, vwap_sm, vwap_bm)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (date, ticker) DO UPDATE SET
                sm_val   = EXCLUDED.sm_val,
                bm_val   = EXCLUDED.bm_val,
                tx_count = EXCLUDED.tx_count,
                tx_sm    = EXCLUDED.tx_sm,
                tx_bm    = EXCLUDED.tx_bm,
                mf_plus  = EXCLUDED.mf_plus,
                mf_minus = EXCLUDED.mf_minus,
                vwap_sm  = EXCLUDED.vwap_sm,
                vwap_bm  = EXCLUDED.vwap_bm
        """, [
            date_str, ticker,
            row.get("sm_val") or 0, row.get("bm_val") or 0,
            row.get("tx_count") or 0, row.get("tx_sm") or 0, row.get("tx_bm") or 0,
            mf.get("mf_plus"), mf.get("mf_minus"),
            row.get("vwap_sm"), row.get("vwap_bm"),
        ])

    log.info("rebuild_summary_for_date %s: %d tickers", date_str, len(sm_rows))


def rebuild_all_summaries(conn):
    """Rebuild eod_summary for all dates present in raw_messages.
    Commits per-date to avoid holding a large transaction during full rebuild."""
    dates = [r["date"] for r in fetchall(conn, "SELECT DISTINCT date FROM raw_messages ORDER BY date")]
    log.info("Rebuilding summary for %d dates", len(dates))
    for date_str in dates:
        rebuild_summary_for_date(conn, date_str, full_reset=False)
        conn.commit()
