"""
analytics_daily.py — Zenith 2.0 Analytics Orchestration
RULE: No HTTP calls. No raw DB queries for flow data — that's summary_rebuild's job.
      Read eod_summary (flow fields) → compute analytics → write analytics fields back.
"""
import logging

from core.db import fetchall, execute
from core.utils import trim_memory
from algo.indicators import (
    compute_ma, compute_rsi14, compute_cm_streak,
    compute_ma50, compute_bollinger_bands, detect_sideways,
    compute_close_position, compute_mf_ratio,
)
from algo.algo_wyckoff import (
    classify_zenith_v3_1, get_action, get_watch_flag,
    detect_trade_detail_gate, get_ma_structure, get_phase_narrative,
)

log = logging.getLogger("zenith.analytics")

_28_DAYS = 28


def compute_analytics_for_date(conn, date_str: str):
    """
    For every ticker in eod_summary on date_str:
    1. Batch-load 10-day SM/BM history + 210-day price_history + prev_close (3 queries)
    2. Compute SRI, MES, RPR, VolxGap, ATR%, MAs, RSI14 per ticker
    3. Classify phase + action + watch via algo_wyckoff
    4. Write analytics fields back to eod_summary
    """
    rows = fetchall(conn, """
        SELECT * FROM eod_summary WHERE date = %s
    """, [date_str])

    if not rows:
        log.warning("No eod_summary rows for %s", date_str)
        return 0

    tickers = [r["ticker"] for r in rows]
    date_yyyy = f"{date_str[6:10]}-{date_str[3:5]}-{date_str[:2]}"

    # Batch: 10-day SM/BM history for all tickers; group oldest-first per ticker
    all_hist = fetchall(conn, """
        SELECT ticker, sm_val, bm_val, tx_count, tx_sm, tx_bm, price_close, volx_gap
        FROM eod_summary
        WHERE ticker = ANY(%s) AND TO_DATE(date, 'DD-MM-YYYY') <= TO_DATE(%s, 'DD-MM-YYYY')
        ORDER BY ticker, TO_DATE(date, 'DD-MM-YYYY') DESC
    """, [tickers, date_str])
    history_map: dict = {}
    for r in all_hist:
        t = r["ticker"]
        bucket = history_map.setdefault(t, [])
        if len(bucket) < 10:
            bucket.append(r)
    history_map = {t: list(reversed(v)) for t, v in history_map.items()}

    # Batch: 210-day OHLC from price_history; group oldest-first per ticker
    all_ph = fetchall(conn, """
        SELECT ticker, high, low, close
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

    # Batch: most-recent close BEFORE date_yyyy for each ticker
    prev_close_rows = fetchall(conn, """
        SELECT DISTINCT ON (ticker) ticker, close
        FROM price_history
        WHERE ticker = ANY(%s) AND date < %s
        ORDER BY ticker, date DESC
    """, [tickers, date_yyyy])
    prev_close_map = {r["ticker"]: r["close"] for r in prev_close_rows}

    updated = 0
    for row in rows:
        ticker = row["ticker"]
        try:
            analytics = _compute_one(
                ticker, date_str, row,
                history_map.get(ticker, []),
                ph_map.get(ticker, []),
                prev_close_map.get(ticker),
            )
        except Exception as e:
            log.warning("analytics _compute_one failed ticker=%s date=%s: %s", ticker, date_str, e)
            continue

        cur = conn.cursor()
        cur.execute("SAVEPOINT sp_analytics")
        try:
            execute(conn, """
                UPDATE eod_summary SET
                    sri = %s, mes = %s, volx_gap = %s, rpr = %s, atr_pct = %s,
                    price_close = %s, price_change_pct = %s,
                    sm_sma10 = %s, bm_sma10 = %s,
                    ma5 = %s, ma13 = %s, ma34 = %s, ma200 = %s,
                    rsi14 = %s, cm_streak = %s, ma_structure = %s,
                    phase = %s, action = %s, watch = %s,
                    trade_gate = %s, narrative = %s,
                    ma50 = %s, bb_upper = %s, bb_mid = %s, bb_lower = %s, bb_width = %s,
                    is_sideways = %s, close_pos = %s, prev_high_break = %s, mf_ratio = %s
                WHERE date = %s AND ticker = %s
            """, [
                analytics["sri"], analytics["mes"], analytics["volx_gap"],
                analytics["rpr"], analytics["atr_pct"],
                analytics["price_close"], analytics["price_change_pct"],
                analytics["sm_sma10"], analytics["bm_sma10"],
                analytics["ma5"], analytics["ma13"], analytics["ma34"], analytics["ma200"],
                analytics["rsi14"], analytics["cm_streak"], analytics["ma_structure"],
                analytics["phase"], analytics["action"], analytics["watch"],
                analytics["trade_gate"], analytics["narrative"],
                analytics["ma50"], analytics["bb_upper"], analytics["bb_mid"],
                analytics["bb_lower"], analytics["bb_width"], analytics["is_sideways"],
                analytics["close_pos"], analytics["prev_high_break"], analytics["mf_ratio"],
                date_str, ticker,
            ])
            cur.execute("RELEASE SAVEPOINT sp_analytics")
            updated += 1
        except Exception as e:
            cur.execute("ROLLBACK TO SAVEPOINT sp_analytics")
            log.warning("analytics failed ticker=%s date=%s: %s", ticker, date_str, e)

    log.info("compute_analytics_for_date %s: %d tickers updated", date_str, updated)
    return updated


def _compute_one(ticker: str, date_str: str, row: dict,
                 history: list, ph: list, prev_close) -> dict:
    """Compute analytics for one ticker. All data pre-loaded by caller (no DB access)."""
    sm_val   = row.get("sm_val") or 0
    bm_val   = row.get("bm_val") or 0
    tx_sm    = row.get("tx_sm") or 0
    tx_bm    = row.get("tx_bm") or 0
    tx_total = (row.get("tx_count") or 0) or (tx_sm + tx_bm)
    price_close  = row.get("price_close") or (ph[-1]["close"] if ph else None)
    price_change = (
        round((price_close - prev_close) / prev_close * 100, 2)
        if price_close and prev_close and prev_close > 0 else None
    )

    # ── SRI (SM Relative Intensity) ───────────────────────────────────────
    total_flow = sm_val + abs(bm_val)
    rsm = round(sm_val / total_flow * 100, 2) if total_flow > 0 else 50.0

    sm_vals_10 = [h["sm_val"] for h in history if h["sm_val"]]
    sm_mean    = sum(sm_vals_10) / len(sm_vals_10) if sm_vals_10 else 0
    sri        = round(sm_val / sm_mean, 2) if sm_mean > 0 else 0

    # ── MES, RPR, VolxGap ────────────────────────────────────────────────
    mes = round(abs(bm_val) / total_flow * 100, 2) if total_flow > 0 else 0
    rpr = round(tx_bm / tx_total, 3) if tx_total > 0 else 0
    vwap_sm_val = row.get("vwap_sm")
    volx_gap = (
        round((price_close - vwap_sm_val) / vwap_sm_val * 100, 2)
        if price_close and vwap_sm_val and vwap_sm_val > 0 else None
    )

    # ── SMA10 for SM and BM ───────────────────────────────────────────────
    sm_sma10 = round(sum(h["sm_val"] for h in history[-10:]) / min(len(history), 10), 2) if history else 0
    bm_sma10 = round(sum(abs(h["bm_val"]) for h in history[-10:]) / min(len(history), 10), 2) if history else 0

    # ── MA, RSI, ATR from price_history (ph is oldest-first) ─────────────
    closes_hist = [r["close"] for r in ph if r["close"]]

    atr_pct = _compute_atr_pct_hlc(ph) if len(ph) >= 3 else 2.5

    ma5   = compute_ma(closes_hist, 5)
    ma13  = compute_ma(closes_hist, 13)
    ma34  = compute_ma(closes_hist, 34)
    ma200 = compute_ma(closes_hist, 200)
    rsi14 = compute_rsi14(closes_hist)
    cm    = compute_cm_streak(closes_hist, ma5)
    ma_structure = get_ma_structure(price_close, ma5, ma13, ma34, ma200)

    # ── Phase classification ──────────────────────────────────────────────
    phase     = classify_zenith_v3_1(sri, rsm, rpr, price_change, bm_val, bm_sma10, atr_pct)
    watch     = get_watch_flag(phase, price_change, atr_pct)
    action    = get_action(phase, price_change, atr_pct, bm_val, bm_sma10, watch, sri=sri, rsm=rsm)
    gate      = detect_trade_detail_gate(phase, price_change, bm_val, bm_sma10, atr_pct, action)
    narrative = get_phase_narrative(phase, ma_structure, gate)

    # ── BSJP indicators ───────────────────────────────────────────────────
    ma50  = compute_ma50(closes_hist)
    bb    = compute_bollinger_bands(closes_hist)
    bb_upper = bb["upper"] if bb else None
    bb_mid   = bb["mid"]   if bb else None
    bb_lower = bb["lower"] if bb else None
    bb_width = bb["width"] if bb else None

    is_sideways = detect_sideways(closes_hist, ma5, ma34, bb_width)

    today_ph   = ph[-1] if ph else None
    close_pos  = compute_close_position(
        price_close,
        today_ph["high"] if today_ph else None,
        today_ph["low"]  if today_ph else None,
    )
    prev_high_break = (
        bool(price_close > ph[-2]["high"])
        if len(ph) >= 2 and ph[-2].get("high") and price_close else False
    )

    mf_plus  = row.get("mf_plus")
    mf_minus = row.get("mf_minus")
    mf_ratio = compute_mf_ratio(mf_plus, mf_minus)

    return {
        "sri": sri, "mes": mes, "volx_gap": volx_gap, "rpr": rpr, "atr_pct": atr_pct,
        "price_close": price_close, "price_change_pct": price_change,
        "sm_sma10": sm_sma10, "bm_sma10": bm_sma10,
        "ma5": ma5, "ma13": ma13, "ma34": ma34, "ma200": ma200,
        "rsi14": rsi14, "cm_streak": cm, "ma_structure": ma_structure,
        "phase": phase, "action": action, "watch": watch,
        "trade_gate": gate, "narrative": narrative,
        "ma50": ma50, "bb_upper": bb_upper, "bb_mid": bb_mid,
        "bb_lower": bb_lower, "bb_width": bb_width, "is_sideways": is_sideways,
        "close_pos": close_pos, "prev_high_break": prev_high_break, "mf_ratio": mf_ratio,
    }


def _compute_atr_pct_hlc(ph_asc: list, period: int = 14) -> float:
    """True Range ATR% using H/L/C from price_history rows (oldest-first).
    TR = max(H-L, |H-prev_C|, |L-prev_C|); ATR% = TR/prev_C*100."""
    trs = []
    rows = [r for r in ph_asc if r.get("close")]
    for i in range(1, len(rows)):
        h      = rows[i].get("high")  or rows[i]["close"]
        l      = rows[i].get("low")   or rows[i]["close"]
        prev_c = rows[i-1]["close"]
        if not prev_c or prev_c <= 0:
            continue
        tr = max(h - l, abs(h - prev_c), abs(l - prev_c))
        trs.append(tr / prev_c * 100)
    if not trs:
        return 2.5
    recent = trs[-period:] if len(trs) >= period else trs
    return round(sum(recent) / len(recent), 2)


def compute_analytics_range(conn, date_from: str, date_to: str):
    """Run compute_analytics_for_date for every date in range."""
    dates = [r["date"] for r in fetchall(conn, """
        SELECT DISTINCT date FROM eod_summary
        WHERE TO_DATE(date, 'DD-MM-YYYY') >= TO_DATE(%s, 'DD-MM-YYYY')
          AND TO_DATE(date, 'DD-MM-YYYY') <= TO_DATE(%s, 'DD-MM-YYYY')
        ORDER BY TO_DATE(date, 'DD-MM-YYYY')
    """, [date_from, date_to])]
    for d in dates:
        compute_analytics_for_date(conn, d)
    trim_memory()
