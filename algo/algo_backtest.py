"""
algo_backtest.py — Zenith 2.0 Backtest Engine
Pair-based backtest: BUY open -> SELL close signals.
RULE: Fetch prices from price_history table (not Yahoo directly).
"""
import logging
import threading
from collections import defaultdict
from datetime import datetime
from config import WIB
from core.db import fetchall

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
    Pair-based backtest over eod_summary date range.
    Returns leaderboard dict matching backtest.html expectations.
    Dates stored as DD-MM-YYYY; convert to YYYYMMDD for correct string comparison.
    """
    global _backtest_result

    if date_from and date_to:
        date_from_cmp = _to_cmp(date_from)
        date_to_cmp   = _to_cmp(date_to)
        all_rows = fetchall(conn, """
            SELECT * FROM eod_summary WHERE action IS NOT NULL ORDER BY ticker, date
        """)
        rows = [r for r in all_rows
                if date_from_cmp <= _to_cmp(r["date"]) <= date_to_cmp]
    else:
        cutoff = fetchall(conn, """
            SELECT date FROM eod_summary
            ORDER BY SUBSTR(date,7,4)||SUBSTR(date,4,2)||SUBSTR(date,1,2) DESC
            LIMIT 1 OFFSET %s
        """, [days])
        cutoff_date = cutoff[0]["date"] if cutoff else "01-01-2000"
        cutoff_cmp  = _to_cmp(cutoff_date)
        all_rows = fetchall(conn, """
            SELECT * FROM eod_summary WHERE action IS NOT NULL ORDER BY ticker, date
        """)
        rows = [r for r in all_rows if _to_cmp(r["date"]) >= cutoff_cmp]

    # ── Pair trades ────────────────────────────────────────────────────────────
    trades = []
    open_positions = {}

    for row in sorted(rows, key=lambda r: (_to_cmp(r["date"]), r["ticker"])):
        ticker = row["ticker"]
        action = row.get("action")
        price  = row.get("price_close")
        if not price:
            continue

        if action == "BUY" and ticker not in open_positions:
            open_positions[ticker] = {
                "entry_date":  row["date"],
                "entry_price": price,
                "entry_phase": row.get("phase"),
            }
        elif action == "SELL" and ticker in open_positions:
            entry = open_positions.pop(ticker)
            profit = round((price - entry["entry_price"]) / entry["entry_price"] * 100, 2)
            trades.append({
                "ticker":       ticker,
                "entry_date":   entry["entry_date"],
                "exit_date":    row["date"],
                "entry_price":  entry["entry_price"],
                "exit_price":   price,
                "profit":       profit,
                "duration":     _days_between(entry["entry_date"], row["date"]),
                "phase":        entry["entry_phase"],
                "exit_phase":   row.get("phase"),
            })

    # ── Build leaderboard grouped by entry phase ────────────────────────────
    phase_map = defaultdict(list)
    for t in trades:
        phase_map[t["phase"] or "UNKNOWN"].append(t)

    leaderboard = []
    for phase, pt in phase_map.items():
        wins   = [t for t in pt if t["profit"] > 0]
        losses = [t for t in pt if t["profit"] <= 0]
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
                "ticker":       t["ticker"],
                "entry_date":   t["entry_date"],
                "exit_date":    t["exit_date"],
                "entry_price":  t["entry_price"],
                "exit_price":   t["exit_price"],
                "profit":       t["profit"],
                "duration":     t["duration"],
                "exit_phase":   t["exit_phase"],
            } for t in pt],
        })

    total_wins   = sum(1 for t in trades if t["profit"] > 0)
    total_losses = len(trades) - total_wins
    gross_p = sum(t["profit"] for t in trades if t["profit"] > 0)
    gross_l = abs(sum(t["profit"] for t in trades if t["profit"] <= 0))
    overall_pf   = round(gross_p / gross_l, 2) if gross_l > 0 else None
    overall_wr   = round(total_wins / len(trades) * 100, 1) if trades else None

    sorted_dates = sorted([t["entry_date"] for t in trades] + [t["exit_date"] for t in trades],
                          key=_to_cmp)
    date_range = f"{sorted_dates[0]} - {sorted_dates[-1]}" if sorted_dates else "-"

    result = {
        "leaderboard":           leaderboard,
        "total_trades":          len(trades),
        "total_wins":            total_wins,
        "total_losses":          total_losses,
        "overall_win_rate":      overall_wr,
        "overall_profit_factor": overall_pf,
        "tickers_tested":        len({t["ticker"] for t in trades}),
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
    """For polling: returns running/done/error status."""
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
    """Compute per-ticker backtest metrics."""
    rows = fetchall(conn, """
        SELECT date, action, phase, price_close
        FROM eod_summary
        WHERE ticker = %s AND action IS NOT NULL
        ORDER BY date DESC LIMIT %s
    """, [ticker, days])

    trades = []
    open_pos = None
    for row in reversed(rows):
        action = row.get("action")
        price  = row.get("price_close")
        if not price:
            continue
        if action == "BUY" and not open_pos:
            open_pos = {"entry_price": price, "entry_date": row["date"]}
        elif action == "SELL" and open_pos:
            gain = round((price - open_pos["entry_price"]) / open_pos["entry_price"] * 100, 2)
            trades.append(gain)
            open_pos = None

    win_rate = round(sum(1 for g in trades if g > 0) / len(trades) * 100, 1) if trades else 0
    avg_gain = round(sum(trades) / len(trades), 2) if trades else 0

    return {
        "ticker":      ticker,
        "trade_count": len(trades),
        "win_rate":    win_rate,
        "avg_gain":    avg_gain,
    }
