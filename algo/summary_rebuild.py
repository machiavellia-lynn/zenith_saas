"""
summary_rebuild.py — Zenith 2.0 Flow Aggregation
Aggregate raw SM/BM/MF data from raw tables → eod_summary (flow fields only).
RULE: Only write flow columns (sm_val, bm_val, tx_count, mf_plus, mf_minus, vwap_sm, vwap_bm).
      Analytics fields (price_close, sri, phase, action, etc.) are written by analytics_daily.py.
"""
import logging
from core.db import get_db, fetchall, execute
from core.trading_calendar import TRADING_DAY_HAVING

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

    # ── SM/BM aggregation + volx_gap ────────────────────────────────────
    # mf_delta_numeric is the net money flow per alert (signed: + for SM, - for BM).
    # This matches what the transaction detail view displays, keeping sm_val/bm_val consistent.
    # value_numeric (gross batch value) is intentionally NOT used here to avoid overcounting.
    sm_rows = fetchall(conn, """
        SELECT ticker,
               SUM(CASE WHEN channel = 'smart' THEN ABS(mf_delta_numeric) ELSE 0 END) AS sm_val,
               SUM(CASE WHEN channel = 'bad'   THEN ABS(mf_delta_numeric) ELSE 0 END) AS bm_val,
               COUNT(*) AS tx_count,
               COUNT(CASE WHEN channel = 'smart' THEN 1 END) AS tx_sm,
               COUNT(CASE WHEN channel = 'bad'   THEN 1 END) AS tx_bm,
               SUM(CASE WHEN channel = 'smart' AND mf_delta_numeric IS NOT NULL AND mf_delta_numeric != 0
                        THEN price * ABS(mf_delta_numeric) ELSE 0 END) /
               NULLIF(SUM(CASE WHEN channel = 'smart' AND mf_delta_numeric IS NOT NULL AND mf_delta_numeric != 0
                               THEN ABS(mf_delta_numeric) ELSE 0 END), 0) AS vwap_sm,
               SUM(CASE WHEN channel = 'bad' AND mf_delta_numeric IS NOT NULL AND mf_delta_numeric != 0
                        THEN price * ABS(mf_delta_numeric) ELSE 0 END) /
               NULLIF(SUM(CASE WHEN channel = 'bad' AND mf_delta_numeric IS NOT NULL AND mf_delta_numeric != 0
                               THEN ABS(mf_delta_numeric) ELSE 0 END), 0) AS vwap_bm,
               AVG(CASE WHEN channel = 'smart' AND vol_x > 0 THEN vol_x ELSE NULL END) AS volx_gap
        FROM raw_messages
        WHERE date = %s AND channel IN ('smart', 'bad')
        GROUP BY ticker
    """, [date_str])

    # ── MF aggregation ───────────────────────────────────────────────────
    mf_rows = fetchall(conn, """
        SELECT ticker,
               SUM(CASE WHEN channel = 'mf_plus'  THEN mf_numeric       ELSE 0 END) AS mf_plus,
               SUM(CASE WHEN channel = 'mf_minus' THEN ABS(mf_numeric) ELSE 0 END) AS mf_minus
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
                                     mf_plus, mf_minus, vwap_sm, vwap_bm, volx_gap)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (date, ticker) DO UPDATE SET
                sm_val   = EXCLUDED.sm_val,
                bm_val   = EXCLUDED.bm_val,
                tx_count = EXCLUDED.tx_count,
                tx_sm    = EXCLUDED.tx_sm,
                tx_bm    = EXCLUDED.tx_bm,
                mf_plus  = EXCLUDED.mf_plus,
                mf_minus = EXCLUDED.mf_minus,
                vwap_sm  = EXCLUDED.vwap_sm,
                vwap_bm  = EXCLUDED.vwap_bm,
                volx_gap = EXCLUDED.volx_gap
        """, [
            date_str, ticker,
            row.get("sm_val") or 0, row.get("bm_val") or 0,
            row.get("tx_count") or 0, row.get("tx_sm") or 0, row.get("tx_bm") or 0,
            mf.get("mf_plus"), mf.get("mf_minus"),
            row.get("vwap_sm"), row.get("vwap_bm"),
            round(row.get("volx_gap"), 2) if row.get("volx_gap") else None,
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


def seed_eod_from_price_history(conn, date_from: str = None, date_to: str = None) -> int:
    """Seed eod_summary rows for ALL active tickers for each trading date in price_history.
    Only inserts missing rows — existing rows are preserved (ON CONFLICT DO NOTHING).
    date_from / date_to: DD-MM-YYYY. None = all dates in price_history.
    Caller is responsible for commit."""

    def _to_yyyy(d):
        if d and len(d) == 10 and d[2] == '-':
            return f"{d[6:10]}-{d[3:5]}-{d[:2]}"
        return d

    if date_from and date_to:
        cur = execute(conn, f"""
            INSERT INTO eod_summary (date, ticker, sm_val, bm_val, tx_count)
            SELECT
                TO_CHAR(ph.date::date, 'DD-MM-YYYY'),
                tu.ticker,
                0, 0, 0
            FROM (SELECT date FROM price_history
                  WHERE date >= %s AND date <= %s
                  GROUP BY date HAVING {TRADING_DAY_HAVING}) ph
            CROSS JOIN (SELECT ticker FROM ticker_universe WHERE is_active = TRUE) tu
            ON CONFLICT (date, ticker) DO NOTHING
        """, [_to_yyyy(date_from), _to_yyyy(date_to)])
    else:
        cur = execute(conn, f"""
            INSERT INTO eod_summary (date, ticker, sm_val, bm_val, tx_count)
            SELECT
                TO_CHAR(ph.date::date, 'DD-MM-YYYY'),
                tu.ticker,
                0, 0, 0
            FROM (SELECT date FROM price_history
                  GROUP BY date HAVING {TRADING_DAY_HAVING}) ph
            CROSS JOIN (SELECT ticker FROM ticker_universe WHERE is_active = TRUE) tu
            ON CONFLICT (date, ticker) DO NOTHING
        """)

    inserted = cur.rowcount if cur else 0
    log.info("seed_eod_from_price_history %s → %s: %d rows inserted", date_from or "all", date_to or "all", inserted)
    return inserted
