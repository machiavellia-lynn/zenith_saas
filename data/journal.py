"""
journal.py — Zenith 2.0 Trade Journal
RULE: All trade position logic lives here only. No journal logic in routes_*.py.
"""
import logging
from datetime import datetime
from config import WIB
from core.db import fetchall, execute

log = logging.getLogger("zenith.journal")


def open_position(conn, ticker: str, entry_phase: str, entry_date: str, buy_price: float):
    """Insert new open position into trade_journal."""
    now = datetime.now(WIB).isoformat()
    execute(conn, """
        INSERT INTO trade_journal
            (ticker, entry_phase, entry_date, buy_price, status, created_at, updated_at)
        VALUES (%s, %s, %s, %s, 'open', %s, %s)
    """, [ticker, entry_phase, entry_date, buy_price, now, now])


def close_position(conn, ticker: str, exit_date: str, sell_price: float, exit_reason: str) -> int:
    """Close ALL open positions for ticker. Returns rows updated."""
    open_rows = fetchall(conn, """
        SELECT id, buy_price, entry_date FROM trade_journal
        WHERE ticker = %s AND status = 'open'
    """, [ticker])

    if not open_rows:
        return 0

    now = datetime.now(WIB).isoformat()
    updated = 0
    for row in open_rows:
        buy  = row["buy_price"]
        gain = round((sell_price - buy) / buy * 100, 2) if buy > 0 else None
        try:
            d_entry = datetime.strptime(row["entry_date"], "%d-%m-%Y").date()
            d_exit  = datetime.strptime(exit_date, "%d-%m-%Y").date()
            hold_days = (d_exit - d_entry).days
        except Exception:
            hold_days = None

        execute(conn, """
            UPDATE trade_journal SET
                status = 'closed', exit_date = %s, sell_price = %s,
                gain_pct = %s, hold_days = %s, exit_reason = %s, updated_at = %s
            WHERE id = %s
        """, [exit_date, sell_price, gain, hold_days, exit_reason, now, row["id"]])
        updated += 1

    return updated


def check_stop_loss(conn, date_str: str, threshold_pct: float = -10.0) -> list[dict]:
    """Check all open positions against threshold. Returns list of triggered positions."""
    open_rows = fetchall(conn, """
        SELECT j.ticker, j.buy_price, e.price_close
        FROM trade_journal j
        LEFT JOIN eod_summary e ON e.ticker = j.ticker AND e.date = %s
        WHERE j.status = 'open'
    """, [date_str])

    triggered = []
    for row in open_rows:
        price = row.get("price_close")
        buy   = row.get("buy_price")
        if price and buy and buy > 0:
            pct = (price - buy) / buy * 100
            if pct <= threshold_pct:
                triggered.append({"ticker": row["ticker"], "pct": round(pct, 2)})

    return triggered


def get_journal_list(conn) -> list[dict]:
    return fetchall(conn, """
        SELECT * FROM trade_journal ORDER BY entry_date DESC
    """)


def get_trade_detail(conn, ticker: str, date_str: str) -> dict | None:
    """Get full trade detail for a ticker+date from eod_summary."""
    rows = fetchall(conn, """
        SELECT * FROM eod_summary WHERE ticker = %s AND date = %s
    """, [ticker, date_str])
    return dict(rows[0]) if rows else None
