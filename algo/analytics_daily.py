"""
analytics_daily.py — Zenith 2.0 Analytics Orchestration
RULE: No HTTP calls. No raw DB queries for flow data — that's summary_rebuild's job.
      Read eod_summary (flow fields) → compute analytics → write analytics fields back.
"""
import logging
from datetime import datetime, timedelta

from core.db import fetchall, execute
from algo.algo_wyckoff import (
    classify_zenith_v3_1, get_action, get_watch_flag,
    detect_trade_detail_gate, compute_ma, compute_rsi14,
    compute_cm_streak, get_ma_structure, get_phase_narrative,
)
from config import WIB

log = logging.getLogger("zenith.analytics")
log.setLevel(logging.INFO)

_28_DAYS = 28


def compute_analytics_for_date(conn, date_str: str):
    """
    For every ticker in eod_summary on date_str:
    1. Fetch 10-day history for SMA calculations
    2. Compute SRI, MES, RPR, VolxGap, ATR%, MAs, RSI14
    3. Classify phase + action + watch via algo_wyckoff
    4. Compute suggested_sl, ma_structure, narrative
    5. Write analytics fields back to eod_summary
    """
    rows = fetchall(conn, """
        SELECT * FROM eod_summary WHERE date = %s
    """, [date_str])

    if not rows:
        log.warning("No eod_summary rows for %s", date_str)
        return 0

    updated = 0
    for row in rows:
        ticker = row["ticker"]
        try:
            analytics = _compute_one(conn, ticker, date_str, row)
            execute(conn, """
                UPDATE eod_summary SET
                    sri = %s, mes = %s, volx_gap = %s, rpr = %s, atr_pct = %s,
                    price_close = %s, price_change_pct = %s,
                    sm_sma10 = %s, bm_sma10 = %s,
                    ma5 = %s, ma13 = %s, ma34 = %s, ma200 = %s,
                    rsi14 = %s, cm_streak = %s, ma_structure = %s,
                    phase = %s, action = %s, watch = %s,
                    trade_gate = %s, narrative = %s
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
                date_str, ticker,
            ])
            updated += 1
        except Exception as e:
            log.warning("analytics failed ticker=%s date=%s: %s", ticker, date_str, e)

    log.info("compute_analytics_for_date %s: %d tickers updated", date_str, updated)
    return updated


def _compute_one(conn, ticker: str, date_str: str, row: dict) -> dict:
    """Compute analytics for a single ticker row."""
    # ── 10-day history for SMA ────────────────────────────────────────────
    history = fetchall(conn, """
        SELECT sm_val, bm_val, tx_count, tx_sm, tx_bm,
               price_close, volx_gap
        FROM eod_summary
        WHERE ticker = %s AND TO_DATE(date, 'DD-MM-YYYY') <= TO_DATE(%s, 'DD-MM-YYYY')
        ORDER BY TO_DATE(date, 'DD-MM-YYYY') DESC
        LIMIT 10
    """, [ticker, date_str])

    history_reversed = list(reversed(history))  # oldest first

    sm_val  = row.get("sm_val") or 0
    bm_val  = row.get("bm_val") or 0
    tx_sm   = row.get("tx_sm") or 0
    tx_bm   = row.get("tx_bm") or 0
    tx_total = (row.get("tx_count") or 0) or (tx_sm + tx_bm)
    price_close    = row.get("price_close")
    price_prev     = _get_prev_close(conn, ticker, date_str)
    price_change   = round((price_close - price_prev) / price_prev * 100, 2) if price_close and price_prev and price_prev > 0 else None

    # ── SRI (SM Relative Intensity) ───────────────────────────────────────
    total_flow = sm_val + abs(bm_val)
    rsm = round(sm_val / total_flow * 100, 2) if total_flow > 0 else 50.0

    sm_vals_10 = [h["sm_val"] for h in history_reversed if h["sm_val"]]
    sm_mean    = sum(sm_vals_10) / len(sm_vals_10) if sm_vals_10 else 0
    sri        = round(sm_val / sm_mean, 2) if sm_mean > 0 else 0

    # ── MES (Market Exhaustion Score) ─────────────────────────────────────
    mes = round(abs(bm_val) / total_flow * 100, 2) if total_flow > 0 else 0

    # ── RPR (Relative Pressure Ratio) ────────────────────────────────────
    rpr = round(tx_bm / tx_total, 3) if tx_total > 0 else 0

    # ── VolxGap: gap between close price and smart money VWAP (%) ────────
    vwap_sm_val = row.get("vwap_sm")
    volx_gap = round((price_close - vwap_sm_val) / vwap_sm_val * 100, 2) if price_close and vwap_sm_val and vwap_sm_val > 0 else None

    # ── ATR% ──────────────────────────────────────────────────────────────
    closes_10 = [h["price_close"] for h in history_reversed if h.get("price_close")]
    atr_pct   = _compute_atr_pct(closes_10) if len(closes_10) >= 3 else 2.5

    # ── SMA10 for SM and BM ───────────────────────────────────────────────
    sm_sma10 = round(sum(h["sm_val"] for h in history_reversed[-10:]) / min(len(history_reversed), 10), 2) if history_reversed else 0
    bm_sma10 = round(sum(abs(h["bm_val"]) for h in history_reversed[-10:]) / min(len(history_reversed), 10), 2) if history_reversed else 0

    # ── MA & RSI from price_history ───────────────────────────────────────
    # date_str is DD-MM-YYYY; price_history.date is YYYY-MM-DD — convert for string comparison
    date_yyyy_mm_dd = f"{date_str[6:10]}-{date_str[3:5]}-{date_str[:2]}"
    ph = fetchall(conn, """
        SELECT close FROM price_history
        WHERE ticker = %s AND date <= %s
        ORDER BY date DESC LIMIT 210
    """, [ticker, date_yyyy_mm_dd])
    closes_hist = list(reversed([r["close"] for r in ph if r["close"]]))

    ma5   = compute_ma(closes_hist, 5)
    ma13  = compute_ma(closes_hist, 13)
    ma34  = compute_ma(closes_hist, 34)
    ma200 = compute_ma(closes_hist, 200)
    rsi14 = compute_rsi14(closes_hist)
    cm    = compute_cm_streak(closes_hist, ma5)
    ma_structure = get_ma_structure(price_close, ma5, ma13, ma34, ma200)

    # ── Phase classification ──────────────────────────────────────────────
    phase = classify_zenith_v3_1(sri, rsm, rpr, price_change, bm_val, bm_sma10, atr_pct)
    watch = get_watch_flag(phase, price_change, atr_pct)
    action = get_action(phase, price_change, atr_pct, bm_val, bm_sma10, watch, sri=sri, rsm=rsm)
    gate  = detect_trade_detail_gate(phase, price_change, bm_val, bm_sma10, atr_pct, action)
    narrative = get_phase_narrative(phase, ma_structure, gate)

    return {
        "sri": sri, "mes": mes, "volx_gap": volx_gap, "rpr": rpr, "atr_pct": atr_pct,
        "price_close": price_close, "price_change_pct": price_change,
        "sm_sma10": sm_sma10, "bm_sma10": bm_sma10,
        "ma5": ma5, "ma13": ma13, "ma34": ma34, "ma200": ma200,
        "rsi14": rsi14, "cm_streak": cm, "ma_structure": ma_structure,
        "phase": phase, "action": action, "watch": watch,
        "trade_gate": gate, "narrative": narrative,
    }


def _get_prev_close(conn, ticker: str, date_str: str):
    # Use price_history (consecutive trading days) instead of eod_summary
    # which only has entries on days with SM/BM activity — causing stale prev prices.
    date_yyyy = f"{date_str[6:10]}-{date_str[3:5]}-{date_str[:2]}"
    rows = fetchall(conn, """
        SELECT close FROM price_history
        WHERE ticker = %s AND date < %s
        ORDER BY date DESC LIMIT 1
    """, [ticker, date_yyyy])
    return rows[0]["close"] if rows else None


def _compute_atr_pct(closes: list) -> float:
    if len(closes) < 2:
        return 2.5
    ranges = [abs(closes[i] - closes[i-1]) / closes[i-1] * 100 for i in range(1, len(closes)) if closes[i-1] > 0]
    return round(sum(ranges) / len(ranges), 2) if ranges else 2.5


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
