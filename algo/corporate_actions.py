"""algo/corporate_actions.py — corporate-action ticker exclusion + auto-detection.

Single source of truth for "which tickers are excluded because of a stock split
or rights issue". A CA re-bases the price series, so historical entries, MAs and
P&L computed across the event date are meaningless — the ticker is dropped from
Portfolio, BSJP signal generation and trade-done history rather than corrected.

Only status='confirmed' rows exclude anything. 'suspected' rows are auto-detected
and awaiting admin review — they are surfaced in the UI but must NOT affect any
calculation. 'rejected' rows are tombstones that stop the detector re-flagging.
"""
import logging
import time

from core.db import fetchall, execute

log = logging.getLogger("zenith.corpaction")


def ca_tickers(conn) -> set:
    """Confirmed corporate-action tickers. CA only — no BLACKLIST."""
    return {r["ticker"] for r in fetchall(conn,
        "SELECT DISTINCT ticker FROM corporate_events WHERE status = 'confirmed'")}


def excluded_tickers(conn) -> set:
    """BLACKLIST (static quality list) ∪ confirmed CA tickers. For BSJP.

    Wyckoff must NOT use this — BLACKLIST is a BSJP-specific quality filter,
    not a data-integrity one, and folding it in would silently change Wyckoff
    results. Wyckoff uses ca_tickers() instead.
    """
    from algo.algo_bsjp import BLACKLIST
    return set(BLACKLIST) | ca_tickers(conn)


def suspected_tickers(conn) -> set:
    """Awaiting admin review. Surfaced in the UI, never excluded."""
    return {r["ticker"] for r in fetchall(conn,
        "SELECT DISTINCT ticker FROM corporate_events WHERE status = 'suspected'")}


# ── Auto-detection ────────────────────────────────────────────────────────────
#
# eod_summary.price_close is written as a copy of price_history.close
# (enrich_daily_ohlcv / sync_eod_prices_from_history), so for any freshly
# processed date the two agree by construction. Historical eod_summary rows are
# a stale snapshot that is never re-synced, while price_history.close DOES get
# retroactively back-adjusted by the data provider when a split / rights issue
# happens. That divergence is the signal we detect.
#
# CAVEAT: the admin "Fix All" / backfill_price_history_ohlcv path re-syncs
# eod_summary from price_history for its date range, which erases this evidence.
# Detections must be reviewed before a Fix All is run over the same range.

_DEV_THRESHOLD  = 0.12   # ratio must deviate >12% from 1.0
_MIN_DAYS       = 2      # on at least this many days, to reject one-off noise
_LOOKBACK_DAYS  = 20     # calendar days of history examined
_REJECT_COOLDOWN_DAYS = 90  # how long a 'rejected' verdict suppresses re-flagging


def detect_back_adjustments(conn) -> list:
    """Flag tickers whose price_history has been back-adjusted vs eod_summary.

    Records hits as status='suspected' — they are NOT excluded until an admin
    approves them. Returns the list of newly-flagged tickers. Caller commits.
    """
    rows = fetchall(conn, """
        SELECT e.ticker,
               e.date        AS date_dmy,
               e.price_close AS eod_close,
               ph.close      AS hist_close
        FROM eod_summary e
        JOIN price_history ph
          ON ph.ticker = e.ticker
         AND ph.date = TO_CHAR(TO_DATE(e.date, 'DD-MM-YYYY'), 'YYYY-MM-DD')
        WHERE e.price_close > 0
          AND ph.close > 0
          AND TO_DATE(e.date, 'DD-MM-YYYY') >= CURRENT_DATE - %s::integer
          -- Suppression is scoped, not ticker-wide: a 'rejected' verdict must
          -- not blind us to a genuine split on that ticker a year later, so it
          -- only silences re-flagging for a cooldown period.
          AND e.ticker NOT IN (
              SELECT ticker FROM corporate_events
              WHERE status IN ('confirmed', 'suspected')
                 OR (status = 'rejected' AND COALESCE(detected_at, 0) >= %s)
          )
    """, [_LOOKBACK_DAYS, int(time.time()) - _REJECT_COOLDOWN_DAYS * 86400])

    hits = {}
    for r in rows:
        ratio = float(r["hist_close"]) / float(r["eod_close"])
        if abs(ratio - 1.0) > _DEV_THRESHOLD:
            hits.setdefault(r["ticker"], []).append((r["date_dmy"], ratio))

    flagged = []
    now = int(time.time())
    for ticker, devs in sorted(hits.items()):
        if len(devs) < _MIN_DAYS:
            continue
        devs.sort(key=lambda d: d[0][6:10] + d[0][3:5] + d[0][:2])
        ratios = [d[1] for d in devs]
        # A back-adjustment rewrites every date BEFORE the ex-date, so the
        # divergence runs [.. , ex_date-1]. The ex-date therefore sits just past
        # the NEWEST divergent date, not the oldest — devs[0] would report the
        # lookback window's edge, which can be weeks off.
        event_date = devs[-1][0]
        detail = (f"auto-detected: {len(devs)} hari rasio price_history/eod_summary "
                  f"{min(ratios):.3f}–{max(ratios):.3f}, divergen {devs[0][0]}..{devs[-1][0]} "
                  f"— ex-date kemungkinan tepat setelah {devs[-1][0]}; cek tanggal & tipe sebelum approve")
        execute(conn, """
            INSERT INTO corporate_events
                (ticker, event_type, event_date, detail, fetched_at, status, detected_at)
            VALUES (%s, 'auto_detected', %s, %s, %s, 'suspected', %s)
            ON CONFLICT (ticker, event_type, event_date) DO NOTHING
        """, [ticker, event_date, detail, now, now])
        flagged.append(ticker)

    log.info("detect_back_adjustments: %d ticker flagged as suspected", len(flagged))
    return flagged
