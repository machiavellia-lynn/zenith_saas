"""
db.py — Zenith 2.0 PostgreSQL Connection Management
RULE: Zero business logic here. Connection management only.
"""
import threading
import logging
from contextlib import contextmanager
import psycopg2
import psycopg2.extras
from config import DATABASE_URL

log = logging.getLogger("zenith.db")

_local = threading.local()


def get_db():
    """Thread-local PostgreSQL connection reuse with lazy reconnect.

    Does NOT run a health-check query on every call — that costs 1 extra
    roundtrip per request. Instead, callers (execute/fetchall/fetchone) catch
    connection errors and call _reconnect() to get a fresh connection.
    """
    conn = getattr(_local, "conn", None)
    if conn is None or conn.closed:
        conn = _new_conn()
    return conn


def _new_conn():
    conn = psycopg2.connect(
        DATABASE_URL,
        cursor_factory=psycopg2.extras.RealDictCursor,
    )
    conn.autocommit = False
    _local.conn = conn
    log.debug("New DB connection opened")
    return conn


def _reconnect():
    """Close stale thread-local connection and open a fresh one."""
    conn = getattr(_local, "conn", None)
    if conn is not None:
        try:
            conn.close()
        except Exception:
            pass
    return _new_conn()


def get_scraper_db():
    """Dedicated connection for scraper thread (separate from Flask thread-local)."""
    conn = psycopg2.connect(
        DATABASE_URL,
        cursor_factory=psycopg2.extras.RealDictCursor,
        connect_timeout=60,
    )
    conn.autocommit = False
    return conn


@contextmanager
def transaction(conn):
    """Context manager for safe commit/rollback."""
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def close_db():
    """Close thread-local connection (call on app teardown or thread exit)."""
    conn = getattr(_local, "conn", None)
    if conn is not None:
        try:
            conn.close()
        except Exception:
            pass
        _local.conn = None


def execute(conn, sql: str, params=None):
    """Execute a non-SELECT query. Returns cursor."""
    try:
        cur = conn.cursor()
        cur.execute(sql, params or [])
        return cur
    except (psycopg2.OperationalError, psycopg2.InterfaceError):
        conn = _reconnect()
        _local.conn = conn
        cur = conn.cursor()
        cur.execute(sql, params or [])
        return cur


def fetchone(conn, sql: str, params=None) -> dict | None:
    """Fetch single row as dict."""
    try:
        cur = conn.cursor()
        cur.execute(sql, params or [])
        row = cur.fetchone()
        return dict(row) if row else None
    except (psycopg2.OperationalError, psycopg2.InterfaceError):
        conn = _reconnect()
        _local.conn = conn
        cur = conn.cursor()
        cur.execute(sql, params or [])
        row = cur.fetchone()
        return dict(row) if row else None


def fetchall(conn, sql: str, params=None) -> list[dict]:
    """Fetch all rows as list of dicts."""
    try:
        cur = conn.cursor()
        cur.execute(sql, params or [])
        return [dict(r) for r in cur.fetchall()]
    except (psycopg2.OperationalError, psycopg2.InterfaceError):
        conn = _reconnect()
        _local.conn = conn
        cur = conn.cursor()
        cur.execute(sql, params or [])
        return [dict(r) for r in cur.fetchall()]


def load_idx_universe(conn) -> list[str]:
    """All distinct tickers from eod_summary."""
    rows = fetchall(conn, "SELECT DISTINCT ticker FROM eod_summary ORDER BY ticker")
    return [r["ticker"] for r in rows]
