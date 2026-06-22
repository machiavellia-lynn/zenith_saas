"""
routes_flow.py — Blueprint: /api/flow, /api/transactions, /api/overlay, /api/ohlcv
RULE: Routing + input validation only. No business logic, no direct API calls.
"""
import logging
from datetime import datetime, timezone
from flask import Blueprint, jsonify, request

from core.auth import is_authed
from config import WIB, YF_HEADERS, INTERVAL_MAP, SECTORS
from core.utils import parse_date, date_range
from core.db import get_db, fetchall
from core.cache import TTLCache
from data.price_fetch import fetch_ohlcv, fetch_ohlcv_datasectors
from algo.algo_wyckoff import (
    classify_zenith_v3_1, get_action, get_watch_flag,
    get_ma_structure, get_phase_narrative, detect_trade_detail_gate,
)

bp_flow = Blueprint("flow", __name__)
log = logging.getLogger("zenith.routes.flow")

# analytics_map cache: TTL 5 min for today, 30 min for historical
_analytics_cache = TTLCache()
_ANALYTICS_TTL_TODAY = 300
_ANALYTICS_TTL_HIST  = 1800


# ── /api/flow ─────────────────────────────────────────────────────────────────
@bp_flow.route("/api/flow")
def flow():
    if not is_authed():
        return jsonify({"error": "unauthorized"}), 401

    today_wib = datetime.now(WIB).strftime("%d-%m-%Y")
    date_from = request.args.get("date_from", today_wib)
    date_to   = request.args.get("date_to",   today_wib)

    try:
        parse_date(date_from)
        parse_date(date_to)
    except ValueError:
        return jsonify({"error": "Format tanggal salah, gunakan DD-MM-YYYY"}), 400

    dates = date_range(date_from, date_to)
    conn  = get_db()

    try:
        rows = fetchall(conn, """
            SELECT ticker,
                   SUM(sm_val)   AS sm_val,
                   SUM(bm_val)   AS bm_val,
                   SUM(tx_count) AS tx,
                   SUM(tx_sm)    AS tx_sm,
                   SUM(tx_bm)    AS tx_bm,
                   SUM(mf_plus)  AS mf_plus,
                   SUM(mf_minus) AS mf_minus,
                   SUM(CASE WHEN vwap_sm IS NOT NULL AND sm_val > 0 THEN vwap_sm * sm_val ELSE 0 END)
                       / NULLIF(SUM(CASE WHEN vwap_sm IS NOT NULL AND sm_val > 0 THEN sm_val ELSE 0 END), 0) AS vwap_sm,
                   SUM(CASE WHEN vwap_bm IS NOT NULL AND bm_val > 0 THEN vwap_bm * bm_val ELSE 0 END)
                       / NULLIF(SUM(CASE WHEN vwap_bm IS NOT NULL AND bm_val > 0 THEN bm_val ELSE 0 END), 0) AS vwap_bm
            FROM eod_summary
            WHERE date = ANY(%s)
            GROUP BY ticker
        """, [dates])

        analytics_map = {}

        # Load existing dates in range once (DISTINCT, index-friendly), sort in Python
        existing_in_range = [r["date"] for r in fetchall(conn,
            "SELECT DISTINCT date FROM eod_summary WHERE date = ANY(%s)", [dates])]
        existing_sorted = sorted(existing_in_range, key=parse_date)
        latest_date   = existing_sorted[-1] if existing_sorted else None
        earliest_date = existing_sorted[0]  if existing_sorted else None

        if latest_date:
            analytics_map = _analytics_cache.get(latest_date)
            if analytics_map is None:
                a_rows = fetchall(conn, """
                    SELECT ticker, price_close, sri, volx_gap, vwap_sm, vwap_bm,
                           atr_pct, sm_sma10, bm_sma10, watch, price_change_pct,
                           sm_val, bm_val,
                           ma5, ma13, ma34, ma200, rsi14, cm_streak
                    FROM eod_summary WHERE date = %s
                """, [latest_date])
                analytics_map = {r["ticker"]: r for r in a_rows}
                today_str = datetime.now(WIB).strftime("%d-%m-%Y")
                ttl = _ANALYTICS_TTL_TODAY if latest_date == today_str else _ANALYTICS_TTL_HIST
                _analytics_cache.set(latest_date, analytics_map, ttl)

        gains_map = {}
        is_single = (date_from == date_to)
        if rows:
            tickers_for_gain = list({r["ticker"] for r in rows})
            if is_single and latest_date:
                # Single day: read stored price_change_pct written by analytics_daily
                for t in tickers_for_gain:
                    a = analytics_map.get(t, {})
                    gains_map[t] = {
                        "gain":  a.get("price_change_pct"),
                        "price": a.get("price_close"),
                    }
            else:
                # Multi-day: compute from price_history (daily closes stored from Yahoo)
                date_to_yyyy   = f"{date_to[6:10]}-{date_to[3:5]}-{date_to[:2]}"
                date_from_yyyy = f"{date_from[6:10]}-{date_from[3:5]}-{date_from[:2]}"
                close_end = {r["ticker"]: r["close"] for r in fetchall(conn, """
                    SELECT DISTINCT ON (ticker) ticker, close
                    FROM price_history
                    WHERE ticker = ANY(%s) AND date <= %s
                    ORDER BY ticker, date DESC
                """, [tickers_for_gain, date_to_yyyy])}
                close_ref = {r["ticker"]: r["close"] for r in fetchall(conn, """
                    SELECT DISTINCT ON (ticker) ticker, close
                    FROM price_history
                    WHERE ticker = ANY(%s) AND date < %s
                    ORDER BY ticker, date DESC
                """, [tickers_for_gain, date_from_yyyy])}
                for t in tickers_for_gain:
                    p_end = close_end.get(t)
                    p_ref = close_ref.get(t)
                    gain  = round((p_end - p_ref) / p_ref * 100, 2) if p_end and p_ref and p_ref > 0 else None
                    gains_map[t] = {
                        "gain":  gain,
                        "price": int(round(p_end)) if p_end else None,
                    }

            if is_single:
                from data.price_cache import get_cached_stocks, _is_market_open
                if _is_market_open():
                    live = get_cached_stocks()
                    for t in list(gains_map):
                        if t in live:
                            gains_map[t] = {"gain": live[t]["gain_pct"], "price": live[t]["price"]}

    except Exception as e:
        log.exception("flow /api/flow DB error")
        return jsonify({"error": "Server error"}), 500

    data = {}
    for row in rows:
        t = row["ticker"]
        data[t] = {
            "sm_val":   row["sm_val"]   or 0,
            "bm_val":   row["bm_val"]   or 0,
            "tx":       row["tx"]       or 0,
            "tx_sm":    row["tx_sm"]    or 0,
            "tx_bm":    row["tx_bm"]    or 0,
            "mf_plus":  row["mf_plus"],
            "mf_minus": row["mf_minus"],
            "net_mf": (
                round((row["mf_plus"] or 0) - abs(row["mf_minus"] or 0), 2)
                if row["mf_plus"] is not None or row["mf_minus"] is not None else None
            ),
            "vwap_sm":  row["vwap_sm"],
            "vwap_bm":  row["vwap_bm"],
        }

    kompas100_mode = request.args.get("kompas100", "").strip().lower() in ("1", "true", "yes", "on")
    if kompas100_mode:
        import os
        from core.utils import load_kompas100_reference
        kompas_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), "kompas100.md")
        k100, _ = load_kompas100_reference(kompas_file)
        data = {t: v for t, v in data.items() if t in k100}
        for t in k100:
            if t not in data:
                data[t] = {"sm_val": 0, "bm_val": 0, "tx": 0, "tx_sm": 0, "tx_bm": 0,
                           "mf_plus": None, "mf_minus": None, "net_mf": None, "_nodata": True}

    sector_name    = request.args.get("sector", "").strip()
    sector_members = set(SECTORS[sector_name]) if sector_name and sector_name in SECTORS else None
    if sector_members:
        for t in sector_members:
            if t not in data:
                data[t] = {"sm_val": 0, "bm_val": 0, "mf_plus": None, "mf_minus": None,
                           "net_mf": None, "tx": 0, "_nodata": True}

    if not data:
        return jsonify({"tickers": [], "totals": {}})

    tickers = []
    for t, d in data.items():
        if sector_members and t not in sector_members:
            continue
        nodata  = d.get("_nodata", False)
        sm      = round(d["sm_val"], 2) if not nodata else None
        bm      = round(d["bm_val"], 2) if not nodata else None
        cm      = round(d["sm_val"] - d["bm_val"], 2) if not nodata else None
        total_f = d["sm_val"] + d["bm_val"]
        rsm     = round(d["sm_val"] / total_f * 100, 1) if not nodata and total_f > 0 else None

        g        = gains_map.get(t, {})
        a        = analytics_map.get(t, {})
        gain     = g.get("gain")
        price_now = g.get("price") or a.get("price_close")
        sri       = a.get("sri") or 0
        atr_pct   = a.get("atr_pct")
        bm_sma10  = a.get("bm_sma10") or 0

        rpr_val = round(d.get("tx_bm", 0) / (d.get("tx_sm", 0) + d.get("tx_bm", 0)), 2) \
                  if (d.get("tx_sm", 0) + d.get("tx_bm", 0)) > 0 else 0

        phase = watch = "NEUTRAL"
        action = "HOLD"
        ma_structure = trade_gate = narrative = None

        # For phase/gate classification always use single-day bm_val from latest_date
        # so it stays on the same scale as bm_sma10 (per-day average).
        bm_classify = a.get("bm_val") or (d.get("bm_val") or 0)

        if rsm is not None:
            bm_raw       = d.get("bm_val") or 0
            phase        = classify_zenith_v3_1(sri, rsm, rpr_val, gain, bm_classify, bm_sma10, atr_pct)
            watch        = get_watch_flag(phase, gain, atr_pct)
            action       = get_action(phase, gain, atr_pct, bm_val=bm_classify, bm_sma10=bm_sma10, watch_flag=watch, sri=sri, rsm=rsm)
            if watch is None and a.get("watch"):
                watch = a.get("watch")
            ma_structure = get_ma_structure(price_now, a.get("ma5"), a.get("ma13"), a.get("ma34"), a.get("ma200"))
            trade_gate   = detect_trade_detail_gate(phase, gain, bm_classify, bm_sma10, atr_pct, action)
            narrative    = get_phase_narrative(phase, ma_structure, trade_gate)
        else:
            bm_raw       = d.get("bm_val") or 0
            ma_structure = get_ma_structure(price_now, a.get("ma5"), a.get("ma13"), a.get("ma34"), a.get("ma200"))

        tickers.append({
            "ticker":       t,
            "clean_money":  cm,
            "sm_val":       sm,
            "bm_val":       bm,
            "rsm":          rsm,
            "mf_plus":      round(d["mf_plus"],  2) if d.get("mf_plus")  is not None else None,
            "mf_minus":     round(d["mf_minus"], 2) if d.get("mf_minus") is not None else None,
            "net_mf":       round(d["net_mf"],   2) if d.get("net_mf")   is not None else None,
            "gain_pct":     gain,
            "price":        price_now,
            "tx":           int(d.get("tx") or 0),
            "phase":        phase,
            "action":       action,
            "watch":        watch,
            "sri":          sri if sri else None,
            "mes":          round(abs(gain) / sri, 2) if gain is not None and sri > 0 else None,
            "volx_gap":     a.get("volx_gap"),
            "rpr":          rpr_val if rpr_val else None,
            "price_change": gain,
            "atr_pct":      atr_pct,
            "sm_sma10":     round(a["sm_sma10"], 2) if a.get("sm_sma10") else None,
            "vwap_sm":      round(d["vwap_sm"],  2) if d.get("vwap_sm")  else None,
            "vwap_bm":      round(d["vwap_bm"],  2) if d.get("vwap_bm")  else None,
            "ma5":          round(a["ma5"],   2) if a.get("ma5")   is not None else None,
            "ma13":         round(a["ma13"],  2) if a.get("ma13")  is not None else None,
            "ma34":         round(a["ma34"],  2) if a.get("ma34")  is not None else None,
            "ma200":        round(a["ma200"], 2) if a.get("ma200") is not None else None,
            "rsi14":        round(a["rsi14"], 1) if a.get("rsi14") is not None else None,
            "cm_streak":    int(a["cm_streak"]) if a.get("cm_streak") is not None else None,
            "ma_structure": ma_structure,
            "narrative":    narrative,
            "bm_sma10":     round(bm_sma10, 2) if bm_sma10 else None,
        })

    tickers.sort(key=lambda x: x["clean_money"] if x["clean_money"] is not None else -999999, reverse=True)

    def _safe_sum(key):
        vals  = [x[key] for x in tickers if x[key] is not None]
        total = round(sum(vals), 2) if vals else None
        return total if total != 0 else None

    totals = {
        "sm":       round(sum(x["sm_val"] or 0      for x in tickers), 2),
        "bm":       round(sum(x["bm_val"] or 0      for x in tickers), 2),
        "mf_plus":  _safe_sum("mf_plus"),
        "mf_minus": _safe_sum("mf_minus"),
        "net_cm":   round(sum(x["clean_money"] or 0 for x in tickers), 2),
        "net_mf":   _safe_sum("net_mf"),
        "count":    len(tickers),
    }

    return jsonify({"tickers": tickers, "totals": totals, "date_from": date_from, "date_to": date_to})


# ── /api/transactions ─────────────────────────────────────────────────────────
@bp_flow.route("/api/transactions")
def transactions():
    if not is_authed():
        return jsonify({"error": "unauthorized"}), 401

    ticker    = request.args.get("ticker", "").upper().strip()
    today_wib = datetime.now(WIB).strftime("%d-%m-%Y")
    date_from = request.args.get("date_from", today_wib)
    date_to   = request.args.get("date_to",   today_wib)

    if not ticker:
        return jsonify({"error": "ticker required"}), 400
    try:
        parse_date(date_from)
        parse_date(date_to)
    except ValueError:
        return jsonify({"error": "Format tanggal salah"}), 400

    dates = date_range(date_from, date_to)
    try:
        rows = fetchall(get_db(), """
            SELECT channel, date, time, price, gain_pct,
                   mf_delta_raw, mf_delta_numeric, vol_x, signal
            FROM raw_messages
            WHERE ticker = %s AND date = ANY(%s)
            ORDER BY TO_DATE(date, 'DD-MM-YYYY'), time
        """, [ticker, dates])
    except Exception as e:
        log.exception("flow /api/transactions DB error")
        return jsonify({"error": "Server error"}), 500

    sm_rows, bm_rows = [], []
    for r in rows:
        row = {
            "date":     r["date"],
            "time":     r["time"],
            "price":    int(round(r["price"])) if r["price"] else None,
            "gain_pct": r["gain_pct"],
            "mf":       r["mf_delta_raw"],
            "mf_num":   r["mf_delta_numeric"],
            "vol_x":    r["vol_x"],
            "signal":   r["signal"],
        }
        (sm_rows if r["channel"] == "smart" else bm_rows).append(row)

    return jsonify({"ticker": ticker, "sm": sm_rows, "bm": bm_rows,
                    "sm_count": len(sm_rows), "bm_count": len(bm_rows)})


# ── /api/overlay ──────────────────────────────────────────────────────────────
@bp_flow.route("/api/overlay")
def overlay():
    if not is_authed():
        return jsonify({"error": "unauthorized"}), 401

    ticker = request.args.get("ticker", "").upper().strip()
    tf     = request.args.get("tf", "1d")
    if not ticker:
        return jsonify({"error": "ticker required"}), 400

    try:
        rows = fetchall(get_db(), """
            SELECT date, time, channel, mf_delta_numeric
            FROM raw_messages WHERE ticker = %s
            ORDER BY TO_DATE(date, 'DD-MM-YYYY'), time
        """, [ticker])
    except Exception as e:
        log.exception("flow /api/overlay DB error")
        return jsonify({"error": "Server error"}), 500

    if not rows:
        return jsonify({"ticker": ticker, "tf": tf, "points": []})

    tf_minutes = {"5m": 5, "15m": 15, "30m": 30, "1h": 60, "1d": None}
    bucket_min = tf_minutes.get(tf)
    buckets    = {}

    for r in rows:
        try:
            d = datetime.strptime(r["date"], "%d-%m-%Y")
        except Exception:
            continue

        if bucket_min is None:
            key = int(d.replace(tzinfo=timezone.utc).timestamp()) + (7 * 3600)
        else:
            parts  = (r["time"] or "").replace(".", ":").split(":")
            h      = int(parts[0]) if len(parts) >= 1 and parts[0].isdigit() else 9
            m      = int(parts[1]) if len(parts) >= 2 and parts[1].isdigit() else 0
            bstart = ((h * 60 + m) // bucket_min) * bucket_min
            key    = int(d.replace(tzinfo=timezone.utc).timestamp()) + (bstart // 60) * 3600 + (bstart % 60) * 60

        if key not in buckets:
            buckets[key] = {"time": key, "sm": 0.0, "bm": 0.0}

        mf = r["mf_delta_numeric"] or 0
        if r["channel"] == "smart":
            buckets[key]["sm"] += mf
        else:
            buckets[key]["bm"] += abs(mf)

    points = []
    cum_sm = cum_bm = cum_cm = 0.0
    for k in sorted(buckets.keys()):
        v      = buckets[k]
        sm     = round(v["sm"], 2)
        bm     = round(v["bm"], 2)
        cm     = round(sm - bm, 2)
        cum_sm = round(cum_sm + sm, 2)
        cum_bm = round(cum_bm + bm, 2)
        cum_cm = round(cum_cm + cm, 2)
        points.append({"time": v["time"], "sm": sm, "bm": bm, "cm": cm,
                       "cum_sm": cum_sm, "cum_bm": cum_bm, "cum_cm": cum_cm})

    return jsonify({"ticker": ticker, "tf": tf, "points": points})


# ── /api/ohlcv ────────────────────────────────────────────────────────────────
@bp_flow.route("/api/ohlcv")
def ohlcv():
    if not is_authed():
        return jsonify({"error": "unauthorized"}), 401

    ticker = request.args.get("ticker", "BBRI").upper().strip()
    tf     = request.args.get("tf", "15m")

    from config import DS_ENABLED
    if DS_ENABLED:
        result = fetch_ohlcv_datasectors(ticker, tf)
        if "error" in result:
            log.warning("DS ohlcv failed %s %s: %s — fallback Yahoo", ticker, tf, result["error"])
            result = fetch_ohlcv(ticker, tf, INTERVAL_MAP)
    else:
        result = fetch_ohlcv(ticker, tf, INTERVAL_MAP)

    if "error" in result:
        return jsonify(result), 404
    return jsonify(result)
