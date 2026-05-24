"""
analytics_bsjp.py — BSJP (Beli Sore Jual Pagi) Indicator Computation
Reads from:  price_history (OHLCV, all tickers in ticker_universe)
Writes to:   price_history (BSJP indicator columns)
RULE: No Telegram data. Pure price-derived indicators only.
      Per-ticker exception handling — one failure does not stop the batch.
"""
import logging

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
    Returns number of tickers updated."""
    tickers_rows = fetchall(conn, """
        SELECT DISTINCT ph.ticker FROM price_history ph
        JOIN ticker_universe u ON u.ticker = ph.ticker
        WHERE ph.date = %s AND u.is_active = TRUE
    """, [date_str])

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
    """, [tickers, date_str])

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
                date_str, ticker,
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


_BSJP_BLACKLIST = {"HATM", "JAST", "CYBR", "AYLS", "VAST", "VTNY"}
_TOP_N_BSJP     = 15


def generate_bsjp_signals(conn, date_dmy: str) -> int:
    """
    Generate sinyal BSJP PRE untuk date_dmy (DD-MM-YYYY).
    Signal detection pakai harga 15:45; entry tetap EOD close (IEP).
    Tulis top 15 ke bsjp_signals.
    """
    from algo.algo_bsjp import BSJPAlgo, _compute_score, _is_ara

    d, m, y  = date_dmy.split("-")
    date_ymd = f"{y}-{m}-{d}"

    algo = BSJPAlgo()

    # Join eod_summary (SM gate) + price_history (BSJP indicators)
    eod_rows = fetchall(conn, """
        SELECT
            e.ticker,
            e.price_close, e.price_change_pct,
            e.phase, e.sri, e.rpr, e.mf_ratio, e.sm_val, e.bm_val,
            p.ma5, p.bb_mid, p.bb_upper, p.bb_lower,
            p.is_sideways, p.close_pos, p.prev_high_break,
            p.ma5_price_streak, p.prev_close_below_ma5,
            p.daily_value, p.days_since_near_bb_mid
        FROM eod_summary e
        LEFT JOIN price_history p ON p.ticker = e.ticker AND p.date = %s
        WHERE e.date = %s
    """, [date_ymd, date_dmy])

    if not eod_rows:
        log.warning("generate_bsjp_signals: no EOD data for %s", date_dmy)
        return 0

    # PRE prices dari 15m candles
    pre_rows  = fetchall(conn,
        "SELECT ticker, close FROM price_history_15m WHERE datetime = %s",
        [date_ymd + " 15:45"])
    open_rows = fetchall(conn,
        "SELECT ticker, open FROM price_history_15m WHERE datetime = %s",
        [date_ymd + " 09:00"])

    prices_1545 = {r["ticker"]: float(r["close"]) for r in pre_rows  if r.get("close")}
    prices_open = {r["ticker"]: float(r["open"])  for r in open_rows if r.get("open")}

    if not prices_1545:
        log.warning("generate_bsjp_signals: no 15m PRE data for %s, aborted", date_dmy)
        return 0

    pool = []
    for eod in eod_rows:
        t = eod["ticker"]
        if t in _BSJP_BLACKLIST:
            continue

        row       = dict(eod)
        eod_close = float(row.get("price_close") or 0)
        if eod_close <= 0:
            continue

        # Override price_close/price_change_pct dengan harga PRE 15:45
        c1545    = prices_1545.get(t)
        open_day = prices_open.get(t)
        if c1545 and open_day and open_day > 0:
            row["price_close"]      = c1545
            row["price_change_pct"] = (c1545 - open_day) / open_day * 100

        if _is_ara(row):
            continue

        sig = algo.signal_detail(t, row)
        if not sig:
            continue

        # Entry tetap EOD close (IEP), bukan harga 15:45
        sig["entry"] = round(eod_close)
        sig["tp1"]   = round(eod_close * 1.01)
        sig["tp2"]   = round(eod_close * 1.02)

        score = _compute_score(row, sig["setup"])
        pool.append((score, t, sig))

    pool.sort(key=lambda x: -x[0])
    top15 = pool[:_TOP_N_BSJP]

    if not top15:
        log.info("generate_bsjp_signals %s: 0 signals", date_dmy)
        return 0

    execute(conn, "DELETE FROM bsjp_signals WHERE date = %s", [date_dmy])
    for rank, (score, t, sig) in enumerate(top15, 1):
        execute(conn, """
            INSERT INTO bsjp_signals
                (date, ticker, setup, entry, tp1, tp2, sl, sl_type, score, day_rank)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (date, ticker) DO UPDATE SET
                setup    = EXCLUDED.setup,    entry  = EXCLUDED.entry,
                tp1      = EXCLUDED.tp1,      tp2    = EXCLUDED.tp2,
                sl       = EXCLUDED.sl,       sl_type = EXCLUDED.sl_type,
                score    = EXCLUDED.score,    day_rank = EXCLUDED.day_rank,
                computed_at = NOW()
        """, [date_dmy, t, sig["setup"], sig["entry"], sig["tp1"], sig["tp2"],
              sig["sl"], sig.get("sl_type"), round(score, 4), rank])

    conn.commit()
    log.info("generate_bsjp_signals %s: %d signals inserted", date_dmy, len(top15))
    return len(top15)


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
