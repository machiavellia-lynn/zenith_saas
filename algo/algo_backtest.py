"""
algo_backtest.py — Zenith 2.0 Backtest Engine
Pair-based backtest: BUY open → SELL close signals.
RULE: Fetch prices from price_history table (not Yahoo directly).
"""
import json
import logging
import threading
from datetime import datetime
from config import WIB
from core.db import fetchall, execute
from algo.algo_wyckoff import classify_zenith_v3_1, get_action

log = logging.getLogger("zenith.backtest")

_backtest_lock   = threading.Lock()
_backtest_result = None
_backtest_running = False


def run_backtest(conn, days: int = 30, date_from: str = None, date_to: str = None) -> dict:
    """
    Pair-based backtest over eod_summary date range.
    Returns summary dict with win_rate, avg_gain, trade_count.
    """
    global _backtest_result, _backtest_running

    if date_from and date_to:
        rows = fetchall(conn, """
            SELECT * FROM eod_summary
            WHERE date >= %s AND date <= %s AND action IS NOT NULL
            ORDER BY ticker, date
        """, [date_from, date_to])
    else:
        cutoff = fetchall(conn, """
            SELECT date FROM eod_summary ORDER BY date DESC
            LIMIT 1 OFFSET %s
        """, [days])
        cutoff_date = cutoff[0]["date"] if cutoff else "01-01-2000"
        rows = fetchall(conn, """
            SELECT * FROM eod_summary
            WHERE date >= %s AND action IS NOT NULL
            ORDER BY ticker, date
        """, [cutoff_date])

    trades = []
    open_positions = {}

    for row in rows:
        ticker = row["ticker"]
        action = row.get("action")
        price  = row.get("price_close")
        if not price:
            continue

        if action == "BUY" and ticker not in open_positions:
            open_positions[ticker] = {
                "entry_date": row["date"],
                "entry_price": price,
                "entry_phase": row.get("phase"),
            }
        elif action == "SELL" and ticker in open_positions:
            entry = open_positions.pop(ticker)
            gain  = round((price - entry["entry_price"]) / entry["entry_price"] * 100, 2)
            trades.append({
                "ticker": ticker,
                "entry_date": entry["entry_date"],
                "exit_date": row["date"],
                "entry_price": entry["entry_price"],
                "exit_price": price,
                "gain_pct": gain,
                "phase": entry["entry_phase"],
            })

    win_count  = sum(1 for t in trades if t["gain_pct"] > 0)
    avg_gain   = round(sum(t["gain_pct"] for t in trades) / len(trades), 2) if trades else 0
    win_rate   = round(win_count / len(trades) * 100, 1) if trades else 0

    result = {
        "trade_count": len(trades),
        "win_rate": win_rate,
        "avg_gain": avg_gain,
        "trades": trades[-100:],  # last 100 for response size
        "computed_at": datetime.now(WIB).isoformat(),
    }

    with _backtest_lock:
        _backtest_result = result

    return result


def request_backtest(days: int):
    """Non-blocking backtest trigger from HTTP thread."""
    global _backtest_running

    def _run():
        global _backtest_running
        try:
            from core.db import get_db
            conn = get_db()
            run_backtest(conn, days=days)
        except Exception as e:
            log.error(f"Backtest error: {e}")
        finally:
            _backtest_running = False

    with _backtest_lock:
        if _backtest_running:
            return
        _backtest_running = True

    threading.Thread(target=_run, daemon=True, name="backtest").start()


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
        "ticker": ticker,
        "trade_count": len(trades),
        "win_rate": win_rate,
        "avg_gain": avg_gain,
    }
