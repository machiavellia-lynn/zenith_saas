"""
analytics_bsjp.py — BSJP (Beli Sore Jual Pagi) Indicator Computation
Reads from:  price_history (OHLCV, all tickers in ticker_universe)
Writes to:   price_history (BSJP indicator columns)
RULE: No Telegram data. Pure price-derived indicators only.
      Per-ticker exception handling — one failure does not stop the batch.
"""
import logging
import threading

from core.db import fetchall, execute
from algo.indicators import (
    compute_ma, compute_ma50, compute_bollinger_bands, detect_sideways,
    compute_close_position, compute_ma5_price_streak, compute_days_since_near_level,
)

log = logging.getLogger("zenith.bsjp")

_STREAK_WIN = 30
_ATR_PERIOD  = 14


def compute_bsjp_for_date(conn, date_str: str) -> int:
    """Compute BSJP indicators for ALL tickers in price_history on date_str.
    Batch-loads 210-day OHLCV history, computes per-ticker, writes back.
    Accepts DD-MM-YYYY or YYYY-MM-DD — normalizes to YYYY-MM-DD internally.
    Returns number of tickers updated."""
    # price_history.date is stored as YYYY-MM-DD; normalize from DD-MM-YYYY if needed
    if len(date_str) == 10 and date_str[2] == '-' and date_str[5] == '-':
        date_yyyy = f"{date_str[6:10]}-{date_str[3:5]}-{date_str[:2]}"
    else:
        date_yyyy = date_str

    tickers_rows = fetchall(conn, """
        SELECT DISTINCT ph.ticker FROM price_history ph
        JOIN ticker_universe u ON u.ticker = ph.ticker
        WHERE ph.date = %s AND u.is_active = TRUE
    """, [date_yyyy])

    if not tickers_rows:
        log.warning("bsjp: no price_history rows for %s", date_str)
        return 0

    tickers = [r["ticker"] for r in tickers_rows]

    # Batch: 210-day OHLCV per ticker (newest-first query, then reversed)
    all_ph = fetchall(conn, """
        SELECT ticker, date, open, high, low, close, volume
        FROM price_history
        WHERE ticker = ANY(%s) AND date <= %s
        ORDER BY ticker, date DESC
    """, [tickers, date_yyyy])

    ph_map: dict = {}
    for r in all_ph:
        t = r["ticker"]
        bucket = ph_map.setdefault(t, [])
        if len(bucket) < 210:
            bucket.append(r)
    ph_map = {t: list(reversed(v)) for t, v in ph_map.items()}

    updated = 0
    for ticker in tickers:
        ph = ph_map.get(ticker, [])
        try:
            ind = _compute_one(ph)
            execute(conn, """
                UPDATE price_history SET
                    ma5   = %s, ma13  = %s, ma34  = %s,
                    ma50  = %s, ma200 = %s, atr_pct = %s,
                    bb_upper = %s, bb_mid = %s, bb_lower = %s, bb_width = %s,
                    close_pos        = %s,
                    prev_high_break  = %s,
                    ma5_price_streak = %s,
                    is_sideways      = %s,
                    daily_value      = %s,
                    prev_close_below_ma5      = %s,
                    prev_close_below_bb_lower = %s,
                    days_since_near_ma50      = %s,
                    days_since_near_bb_mid    = %s
                WHERE date = %s AND ticker = %s
            """, [
                ind["ma5"], ind["ma13"], ind["ma34"],
                ind["ma50"], ind["ma200"], ind["atr_pct"],
                ind["bb_upper"], ind["bb_mid"], ind["bb_lower"], ind["bb_width"],
                ind["close_pos"], ind["prev_high_break"],
                ind["ma5_price_streak"], ind["is_sideways"],
                ind["daily_value"],
                ind["prev_close_below_ma5"], ind["prev_close_below_bb_lower"],
                ind["days_since_near_ma50"], ind["days_since_near_bb_mid"],
                date_yyyy, ticker,
            ])
            updated += 1
        except Exception as e:
            log.warning("bsjp failed ticker=%s date=%s: %s", ticker, date_str, e)

    log.info("compute_bsjp_for_date %s: %d/%d tickers updated", date_str, updated, len(tickers))
    return updated


def compute_bsjp_range(conn, date_from: str, date_to: str) -> int:
    """Run compute_bsjp_for_date for every date in range (DD-MM-YYYY format)."""
    dates = [r["date"] for r in fetchall(conn, """
        SELECT DISTINCT date FROM price_history
        WHERE date BETWEEN %s AND %s
        ORDER BY date
    """, [date_from, date_to])]
    total = 0
    for d in dates:
        total += compute_bsjp_for_date(conn, d)
    return total


def _compute_one(ph: list) -> dict:
    """Compute all BSJP indicators for one ticker. ph = oldest-first OHLCV rows."""
    closes = [r["close"] for r in ph if r["close"]]

    ma5  = compute_ma(closes, 5)
    ma13 = compute_ma(closes, 13)
    ma34 = compute_ma(closes, 34)
    ma50 = compute_ma50(closes)
    ma200 = compute_ma(closes, 200)

    atr_pct = _compute_atr_pct(ph)

    bb = compute_bollinger_bands(closes)
    bb_upper = bb["upper"] if bb else None
    bb_mid   = bb["mid"]   if bb else None
    bb_lower = bb["lower"] if bb else None
    bb_width = bb["width"] if bb else None

    is_sideways = detect_sideways(closes, ma5, ma34, bb_width)

    today = ph[-1] if ph else None
    close_pos = compute_close_position(
        today["close"] if today else None,
        today["high"]  if today else None,
        today["low"]   if today else None,
    )

    prev_high_break = (
        bool(ph[-1]["close"] > ph[-2]["high"])
        if len(ph) >= 2 and ph[-2].get("high") and ph[-1].get("close")
        else False
    )

    # MA5 price streak
    n = len(closes)
    if n >= 5:
        _limit = min(n, _STREAK_WIN)
        _s_cls = closes[-_limit:]
        _s_ma5 = [compute_ma(closes[:n - _limit + i + 1], 5) for i in range(_limit)]
        ma5_price_streak = compute_ma5_price_streak(_s_cls, _s_ma5)
    else:
        ma5_price_streak = 0

    daily_value = (
        float(today["close"]) * float(today["volume"])
        if today and today.get("volume") is not None
        else None
    )

    # Previous-day flags
    if len(ph) >= 2 and closes:
        prev_close = ph[-2]["close"]
        prev_ma5   = compute_ma(closes[:-1], 5)
        prev_close_below_ma5 = (
            bool(prev_close < prev_ma5)
            if prev_close is not None and prev_ma5 is not None else False
        )
        prev_bb = compute_bollinger_bands(closes[:-1])
        prev_close_below_bb_lower = (
            bool(prev_close < prev_bb["lower"])
            if prev_bb and prev_close is not None else False
        )
    else:
        prev_close_below_ma5 = False
        prev_close_below_bb_lower = False

    days_since_near_ma50 = (
        compute_days_since_near_level(closes, ma50) if ma50 else None
    )
    days_since_near_bb_mid = (
        compute_days_since_near_level(closes, bb_mid) if bb_mid else None
    )

    return {
        "ma5": ma5, "ma13": ma13, "ma34": ma34, "ma50": ma50, "ma200": ma200,
        "atr_pct": atr_pct,
        "bb_upper": bb_upper, "bb_mid": bb_mid, "bb_lower": bb_lower, "bb_width": bb_width,
        "close_pos": close_pos, "prev_high_break": prev_high_break,
        "ma5_price_streak": ma5_price_streak, "is_sideways": is_sideways,
        "daily_value": daily_value,
        "prev_close_below_ma5": prev_close_below_ma5,
        "prev_close_below_bb_lower": prev_close_below_bb_lower,
        "days_since_near_ma50": days_since_near_ma50,
        "days_since_near_bb_mid": days_since_near_bb_mid,
    }


def generate_bsjp_signals(conn, date_dmy: str) -> int:
    """Delegate ke run_bsjp_scan di scraper — satu source of truth."""
    from scraper.scraper_daily import run_bsjp_scan
    return run_bsjp_scan(conn, date_dmy)


_backfill_lock    = threading.Lock()
_backfill_running = False
_backfill_progress = {"done": 0, "total": 0, "error": None}


def request_bsjp_backfill(date_from_dmy: str, date_to_dmy: str) -> bool:
    """Trigger background backfill of bsjp_signals for a date range (DD-MM-YYYY)."""
    global _backfill_running
    with _backfill_lock:
        if _backfill_running:
            return False
        _backfill_running = True
        _backfill_progress["done"]  = 0
        _backfill_progress["total"] = 0
        _backfill_progress["error"] = None

    def _run():
        global _backfill_running
        try:
            from core.db import get_db
            from scraper.scraper_daily import run_bsjp_scan
            conn = get_db()

            from_cmp = date_from_dmy[6:10] + date_from_dmy[3:5] + date_from_dmy[:2]
            to_cmp   = date_to_dmy[6:10]   + date_to_dmy[3:5]   + date_to_dmy[:2]

            raw_dates = fetchall(conn, """
                SELECT DISTINCT date FROM eod_summary
                WHERE SUBSTRING(date,7,4)||SUBSTRING(date,4,2)||SUBSTRING(date,1,2)
                      BETWEEN %s AND %s
            """, [from_cmp, to_cmp])

            dates = sorted(raw_dates, key=lambda r: r["date"][6:10] + r["date"][3:5] + r["date"][:2])

            _backfill_progress["total"] = len(dates)
            for i, row in enumerate(dates):
                run_bsjp_scan(conn, row["date"])
                _backfill_progress["done"] = i + 1

            log.info("bsjp backfill done: %d dates processed", len(dates))
        except Exception as e:
            log.error("bsjp backfill error: %s", e)
            _backfill_progress["error"] = str(e)
        finally:
            _backfill_running = False

    threading.Thread(target=_run, daemon=True, name="bsjp-backfill").start()
    return True


def get_backfill_status() -> dict:
    with _backfill_lock:
        if _backfill_running:
            return {"status": "running", **_backfill_progress}
        if _backfill_progress.get("error"):
            return {"status": "error", "error": _backfill_progress["error"]}
        return {"status": "done", **_backfill_progress}


def _compute_atr_pct(ph_asc: list) -> float:
    """ATR% dari H/L/C. ph_asc = oldest-first."""
    trs  = []
    rows = [r for r in ph_asc if r.get("close")]
    for i in range(1, len(rows)):
        h      = rows[i].get("high")  or rows[i]["close"]
        l      = rows[i].get("low")   or rows[i]["close"]
        prev_c = rows[i - 1]["close"]
        if not prev_c or prev_c <= 0:
            continue
        tr = max(h - l, abs(h - prev_c), abs(l - prev_c))
        trs.append(tr / prev_c * 100)
    if not trs:
        return 2.5
    recent = trs[-_ATR_PERIOD:] if len(trs) >= _ATR_PERIOD else trs
    return round(sum(recent) / len(recent), 2)
