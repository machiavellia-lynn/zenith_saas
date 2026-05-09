"""
algo_backtest.py — Zenith 2.0 Backtest Engine
Pair-based backtest: multi-entry BUY → SELL/SL close, mirroring Zenith 1.0 logic.
RULE: Fetch prices from eod_summary (not Yahoo directly).
"""
import logging
import threading
from collections import defaultdict
from datetime import datetime
from config import WIB
from core.db import fetchall
from algo.algo_wyckoff import get_action, get_watch_flag

log = logging.getLogger("zenith.backtest")

_backtest_lock    = threading.Lock()
_backtest_result  = None
_backtest_running = False
_backtest_error   = None


def _to_cmp(date_str: str) -> str:
    """Convert DD-MM-YYYY to YYYYMMDD for correct string comparison."""
    if not date_str or len(date_str) != 10:
        return date_str
    return f"{date_str[6:10]}{date_str[3:5]}{date_str[:2]}"


def _days_between(d1: str, d2: str) -> int:
    """Days between two DD-MM-YYYY strings."""
    try:
        a = datetime.strptime(d1, "%d-%m-%Y")
        b = datetime.strptime(d2, "%d-%m-%Y")
        return abs((b - a).days)
    except Exception:
        return 0


def run_backtest(conn, days: int = 30, date_from: str = None, date_to: str = None) -> dict:
    """
    Multi-entry pair-based backtest over eod_summary date range.
    - Each BUY opens a new position (multi-entry, like Zenith 1.0).
    - SELL closes ALL open positions for that ticker.
    - ATR-based stop loss checked daily.
    Returns leaderboard dict matching backtest.html expectations.
    """
    global _backtest_result

    # ── Fetch ALL rows in range (need every day's price for daily SL check) ────
    # Fetch all fields needed to re-compute action live from current algo settings.
    # Do NOT use stored action column — it reflects the algo version at scrape time.
    if date_from and date_to:
        date_from_cmp = _to_cmp(date_from)
        date_to_cmp   = _to_cmp(date_to)
        all_rows = fetchall(conn, """
            SELECT ticker, date, price_close, phase, atr_pct,
                   sri, rsm, bm_val, bm_sma10, price_change_pct, watch
            FROM eod_summary ORDER BY ticker, date
        """)
        rows = [r for r in all_rows
                if date_from_cmp <= _to_cmp(r["date"]) <= date_to_cmp
                and r.get("price_close")]
    else:
        distinct = fetchall(conn, """
            SELECT date FROM (SELECT DISTINCT date FROM eod_summary) t
            ORDER BY TO_DATE(date, 'DD-MM-YYYY') ASC
        """)
        all_distinct = [r["date"] for r in distinct]
        cutoff_date = all_distinct[-days] if len(all_distinct) >= days else (all_distinct[0] if all_distinct else "01-01-2000")
        cutoff_cmp  = _to_cmp(cutoff_date)
        all_rows = fetchall(conn, """
            SELECT ticker, date, price_close, phase, atr_pct,
                   sri, rsm, bm_val, bm_sma10, price_change_pct, watch
            FROM eod_summary ORDER BY ticker, date
        """)
        rows = [r for r in all_rows
                if _to_cmp(r["date"]) >= cutoff_cmp and r.get("price_close")]

    # Re-compute action using current algo settings (not stored DB value)
    def _recompute_action(r) -> str:
        try:
            sri      = float(r["sri"])      if r.get("sri")      else 0.0
            rsm      = float(r["rsm"])      if r.get("rsm")      else 0.0
            bm_val   = float(r["bm_val"])   if r.get("bm_val")   else 0.0
            bm_sma10 = float(r["bm_sma10"]) if r.get("bm_sma10") else 0.0
            atr_pct  = float(r["atr_pct"])  if r.get("atr_pct")  else 2.5
            pchg     = float(r["price_change_pct"]) if r.get("price_change_pct") else None
            watch    = r.get("watch")
            phase    = r.get("phase") or "NEUTRAL"
            return get_action(phase, pchg, atr_pct, bm_val, bm_sma10, watch, sri=sri, rsm=rsm)
        except Exception:
            return "HOLD"

    for r in rows:
        r["action"] = _recompute_action(r)

    # ── Index: {date: {ticker: row}} ────────────────────────────────────────────
    days_index = defaultdict(dict)
    for row in rows:
        days_index[row["date"]][row["ticker"]] = row

    sorted_dates = sorted(days_index.keys(), key=_to_cmp)

    # ── Multi-entry position tracking ───────────────────────────────────────────
    trades = []
    open_positions = defaultdict(list)  # {ticker: [{entry_date, entry_price, entry_phase, sl_threshold}, ...]}

    for date_str in sorted_dates:
        day_tickers = days_index[date_str]

        # 1. Check ATR stop loss daily for every open position
        for ticker, positions in list(open_positions.items()):
            if not positions:
                continue
            day_row = day_tickers.get(ticker)
            price   = day_row["price_close"] if day_row else None
            if not price:
                continue

            surviving = []
            for pos in positions:
                loss_pct = (price - pos["entry_price"]) / pos["entry_price"] * 100
                if loss_pct <= pos["sl_threshold"]:
                    trades.append({
                        "ticker":      ticker,
                        "entry_date":  pos["entry_date"],
                        "exit_date":   date_str,
                        "entry_price": pos["entry_price"],
                        "exit_price":  price,
                        "profit":      round(loss_pct, 2),
                        "duration":    _days_between(pos["entry_date"], date_str),
                        "phase":       pos["entry_phase"],
                        "exit_phase":  "SL",
                    })
                else:
                    surviving.append(pos)
            open_positions[ticker] = surviving

        # 2. Process BUY / SELL signals for this day
        for ticker, row in day_tickers.items():
            action = row.get("action")
            price  = row.get("price_close")
            if not action or not price:
                continue

            if action == "BUY":
                atr_pct      = row.get("atr_pct") or 2.5
                sl_threshold = -min(max(atr_pct * 2.0, 5.0), 12.0)
                open_positions[ticker].append({
                    "entry_date":  date_str,
                    "entry_price": price,
                    "entry_phase": row.get("phase"),
                    "sl_threshold": sl_threshold,
                })

            elif action == "SELL" and open_positions[ticker]:
                for pos in open_positions[ticker]:
                    profit = round((price - pos["entry_price"]) / pos["entry_price"] * 100, 2)
                    trades.append({
                        "ticker":      ticker,
                        "entry_date":  pos["entry_date"],
                        "exit_date":   date_str,
                        "entry_price": pos["entry_price"],
                        "exit_price":  price,
                        "profit":      profit,
                        "duration":    _days_between(pos["entry_date"], date_str),
                        "phase":       pos["entry_phase"],
                        "exit_phase":  row.get("phase"),
                    })
                open_positions[ticker] = []

    # ── Build leaderboard grouped by entry phase ────────────────────────────────
    phase_map = defaultdict(list)
    for t in trades:
        if t.get("profit", 0) < -50:  # exclude extreme losses (rights issue, delisting)
            continue
        phase_map[t["phase"] or "UNKNOWN"].append(t)

    leaderboard = []
    for phase, pt in phase_map.items():
        wins        = [t for t in pt if t["profit"] > 0]
        losses      = [t for t in pt if t["profit"] <= 0]
        gross_profit = sum(t["profit"] for t in wins)
        gross_loss   = abs(sum(t["profit"] for t in losses))
        pf = round(gross_profit / gross_loss, 2) if gross_loss > 0 else None
        leaderboard.append({
            "entry":        phase,
            "trades":       len(pt),
            "wins":         len(wins),
            "losses":       len(losses),
            "win_rate":     round(len(wins) / len(pt) * 100, 1),
            "avg_profit":   round(sum(t["profit"] for t in pt) / len(pt), 2),
            "avg_win":      round(gross_profit / len(wins), 2) if wins else None,
            "avg_loss":     round(-gross_loss / len(losses), 2) if losses else None,
            "avg_duration": round(sum(t["duration"] for t in pt) / len(pt), 1),
            "profit_factor": pf,
            "details": [{
                "ticker":      t["ticker"],
                "entry_date":  t["entry_date"],
                "exit_date":   t["exit_date"],
                "entry_price": t["entry_price"],
                "exit_price":  t["exit_price"],
                "profit":      t["profit"],
                "duration":    t["duration"],
                "exit_phase":  t["exit_phase"],
            } for t in pt],
        })

    valid_trades = [t for t in trades if t.get("profit", 0) >= -50]
    total_wins   = sum(1 for t in valid_trades if t["profit"] > 0)
    total_losses = len(valid_trades) - total_wins
    gross_p      = sum(t["profit"] for t in valid_trades if t["profit"] > 0)
    gross_l      = abs(sum(t["profit"] for t in valid_trades if t["profit"] <= 0))
    overall_pf   = round(gross_p / gross_l, 2) if gross_l > 0 else None
    overall_wr   = round(total_wins / len(valid_trades) * 100, 1) if valid_trades else None

    all_entry_dates = [t["entry_date"] for t in valid_trades]
    all_exit_dates  = [t["exit_date"]  for t in valid_trades]
    all_d = sorted(all_entry_dates + all_exit_dates, key=_to_cmp)
    date_range = f"{all_d[0]} - {all_d[-1]}" if all_d else "-"

    result = {
        "leaderboard":           leaderboard,
        "total_trades":          len(valid_trades),
        "total_wins":            total_wins,
        "total_losses":          total_losses,
        "overall_win_rate":      overall_wr,
        "overall_profit_factor": overall_pf,
        "tickers_tested":        len({t["ticker"] for t in valid_trades}),
        "date_range":            date_range,
        "computed_at":           datetime.now(WIB).strftime("%d-%m-%Y %H:%M"),
    }

    with _backtest_lock:
        _backtest_result = result

    return result


def request_backtest(days: int = 30, date_from: str = None, date_to: str = None):
    """Non-blocking backtest trigger from HTTP thread."""
    global _backtest_running, _backtest_error

    def _run():
        global _backtest_running, _backtest_error
        try:
            from core.db import get_db
            conn = get_db()
            run_backtest(conn, days=days, date_from=date_from, date_to=date_to)
            _backtest_error = None
        except Exception as e:
            log.error("Backtest error: %s", e)
            _backtest_error = str(e)
        finally:
            _backtest_running = False

    with _backtest_lock:
        if _backtest_running:
            return False
        _backtest_running = True
        _backtest_error   = None

    threading.Thread(target=_run, daemon=True, name="backtest").start()
    return True


def get_backtest_status() -> dict:
    with _backtest_lock:
        if _backtest_running:
            return {"status": "running"}
        if _backtest_error:
            return {"status": "error", "result": _backtest_error}
        return {"status": "done"}


def get_backtest_result() -> dict | None:
    with _backtest_lock:
        return _backtest_result


def get_ticker_fitness(conn, ticker: str, days: int = 90) -> dict:
    """
    Per-ticker backtest stats extracted from cached _backtest_result.
    Returns the full format expected by flow.html loadTickerFitness().
    """
    with _backtest_lock:
        cached = _backtest_result

    if not cached:
        return {"ticker": ticker, "total_trades": 0, "error": "No backtest data"}

    period   = cached.get("date_range", "")
    computed = cached.get("computed_at", "")

    # Extract all trades for this ticker from the leaderboard details
    ticker_trades = []
    entry_phase_map = defaultdict(list)

    for entry_row in cached.get("leaderboard", []):
        entry_phase = entry_row.get("entry", "")
        for d in entry_row.get("details", []):
            if d["ticker"] == ticker and d.get("profit", 0) >= -50:
                trade = {**d, "entry_phase": entry_phase}
                ticker_trades.append(trade)
                entry_phase_map[entry_phase].append(trade)

    if not ticker_trades:
        return {"ticker": ticker, "total_trades": 0, "period": period}

    wins   = [t for t in ticker_trades if t["profit"] > 0]
    losses = [t for t in ticker_trades if t["profit"] <= 0]
    gp     = sum(t["profit"] for t in wins)
    gl     = abs(sum(t["profit"] for t in losses))
    pf     = round(gp / gl, 2) if gl > 0 else (99.0 if gp > 0 else 0)

    # Per-phase breakdown
    phase_stats = []
    best_phase  = None
    best_gp     = -999

    for ph, ph_trades in entry_phase_map.items():
        ph_wins = [t for t in ph_trades if t["profit"] > 0]
        ph_gl   = abs(sum(t["profit"] for t in ph_trades if t["profit"] <= 0))
        ph_gp   = sum(t["profit"] for t in ph_trades if t["profit"] > 0)
        ph_pf   = round(ph_gp / ph_gl, 2) if ph_gl > 0 else (99.0 if ph_gp > 0 else 0)
        ph_wr   = round(len(ph_wins) / len(ph_trades) * 100, 1) if ph_trades else 0
        ph_avg  = round(sum(t["profit"] for t in ph_trades) / len(ph_trades), 2)
        phase_stats.append({
            "phase": ph, "trades": len(ph_trades),
            "win_rate": ph_wr, "profit_factor": ph_pf, "avg_profit": ph_avg,
        })
        if ph_gp > best_gp:
            best_gp    = ph_gp
            best_phase = {
                "phase": ph, "win_rate": ph_wr, "profit_factor": ph_pf,
                "avg_profit": ph_avg, "trades": len(ph_trades),
            }

    trades_sorted = sorted(
        ticker_trades,
        key=lambda t: _to_cmp(t.get("entry_date", "")),
        reverse=True,
    )

    return {
        "ticker":        ticker,
        "total_trades":  len(ticker_trades),
        "win_rate":      round(len(wins) / len(ticker_trades) * 100, 1),
        "profit_factor": pf,
        "avg_profit":    round(sum(t["profit"] for t in ticker_trades) / len(ticker_trades), 2),
        "best_phase":    best_phase,
        "phase_stats":   sorted(phase_stats, key=lambda x: x["avg_profit"], reverse=True),
        "wins":          len(wins),
        "losses":        len(losses),
        "period":        period,
        "computed_at":   computed,
        "trades":        trades_sorted,
    }
