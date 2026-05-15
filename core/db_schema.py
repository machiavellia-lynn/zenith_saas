"""
db_schema.py — Zenith 2.0 PostgreSQL DDL
RULE: ALL CREATE TABLE and index definitions live here only.
      No CREATE TABLE in any other file.
"""
import logging
from core.db import get_db

log = logging.getLogger("zenith.schema")


def ensure_schema():
    """Create all tables and indexes. Safe to call on every startup."""
    conn = get_db()
    _create_users(conn)
    _create_raw_messages(conn)
    _create_raw_mf_messages(conn)
    _create_eod_summary(conn)
    _create_price_history(conn)
    _create_trade_journal(conn)
    _create_backtest_cache(conn)
    _create_ohlcv_cache(conn)
    _create_corporate_events(conn)
    _create_inst_flow_cache(conn)
    _create_intraday_ohlcv(conn)
    conn.commit()
    log.info("Schema ensured OK")


def _create_users(conn):
    conn.cursor().execute("""
        CREATE TABLE IF NOT EXISTS users (
            id           SERIAL PRIMARY KEY,
            username     VARCHAR(255) UNIQUE NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            role         VARCHAR(50) DEFAULT 'guest',
            created_at   TIMESTAMP DEFAULT NOW()
        )
    """)
    conn.cursor().execute("CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)")


def _create_raw_messages(conn):
    conn.cursor().execute("""
        CREATE TABLE IF NOT EXISTS raw_messages (
            id           SERIAL PRIMARY KEY,
            message_id   BIGINT,
            channel      TEXT,
            date         TEXT NOT NULL,
            time         TEXT,
            tx_count     INTEGER,
            ticker       TEXT NOT NULL,
            price        REAL,
            gain_pct     REAL,
            freq         INTEGER,
            value_raw    TEXT,
            value_numeric REAL,
            avg_mf_raw   TEXT,
            avg_mf_numeric REAL,
            mf_delta_raw TEXT,
            mf_delta_numeric REAL,
            vol_x        REAL,
            signal       TEXT,
            UNIQUE (message_id, ticker)
        )
    """)
    conn.cursor().execute("CREATE INDEX IF NOT EXISTS idx_raw_date ON raw_messages(date)")
    conn.cursor().execute("CREATE INDEX IF NOT EXISTS idx_raw_ticker_date ON raw_messages(ticker, date)")


def _create_raw_mf_messages(conn):
    conn.cursor().execute("""
        CREATE TABLE IF NOT EXISTS raw_mf_messages (
            id           SERIAL PRIMARY KEY,
            message_id   BIGINT,
            channel      TEXT,
            date         TEXT NOT NULL,
            time         TEXT,
            tx_count     INTEGER,
            ticker       TEXT NOT NULL,
            price        REAL,
            gain_pct     REAL,
            val_raw      TEXT,
            val_numeric  REAL,
            mf_raw       TEXT,
            mf_numeric   REAL,
            mft_raw      TEXT,
            mft_numeric  REAL,
            cm_delta_raw TEXT,
            cm_delta_numeric REAL,
            signal       TEXT,
            UNIQUE (message_id, ticker)
        )
    """)
    conn.cursor().execute("CREATE INDEX IF NOT EXISTS idx_mf_date ON raw_mf_messages(date)")
    conn.cursor().execute("CREATE INDEX IF NOT EXISTS idx_mf_ticker_date ON raw_mf_messages(ticker, date)")


def _create_eod_summary(conn):
    conn.cursor().execute("""
        CREATE TABLE IF NOT EXISTS eod_summary (
            date             TEXT NOT NULL,
            ticker           TEXT NOT NULL,
            sm_val           REAL DEFAULT 0,
            bm_val           REAL DEFAULT 0,
            tx_count         INTEGER DEFAULT 0,
            tx_sm            INTEGER DEFAULT 0,
            tx_bm            INTEGER DEFAULT 0,
            mf_plus          REAL,
            mf_minus         REAL,
            vwap_sm          REAL,
            vwap_bm          REAL,
            price_close      REAL,
            price_change_pct REAL,
            sri              REAL,
            mes              REAL,
            volx_gap         REAL,
            rpr              REAL,
            atr_pct          REAL,
            phase            TEXT,
            action           TEXT,
            sm_sma10         REAL,
            bm_sma10         REAL,
            watch            TEXT,
            ma5              REAL,
            ma13             REAL,
            ma34             REAL,
            ma200            REAL,
            rsi14            REAL,
            cm_streak        INTEGER,
            ma_structure     TEXT,
            trade_gate       TEXT,
            narrative        TEXT,
            PRIMARY KEY (date, ticker)
        )
    """)
    conn.cursor().execute("CREATE INDEX IF NOT EXISTS idx_eod_date ON eod_summary(date)")
    conn.cursor().execute("CREATE INDEX IF NOT EXISTS idx_eod_ticker ON eod_summary(ticker, date)")
    # BSJP indicator columns — added incrementally via ALTER TABLE
    for col, typedef in [
        ("ma50",            "REAL"),
        ("bb_upper",        "REAL"),
        ("bb_mid",          "REAL"),
        ("bb_lower",        "REAL"),
        ("bb_width",        "REAL"),
        ("is_sideways",     "BOOLEAN"),
        ("close_pos",       "REAL"),
        ("prev_high_break", "BOOLEAN"),
        ("mf_ratio",        "REAL"),
    ]:
        conn.cursor().execute(
            f"ALTER TABLE eod_summary ADD COLUMN IF NOT EXISTS {col} {typedef}"
        )


def _create_price_history(conn):
    conn.cursor().execute("""
        CREATE TABLE IF NOT EXISTS price_history (
            date   TEXT NOT NULL,
            ticker TEXT NOT NULL,
            open   REAL,
            high   REAL,
            low    REAL,
            close  REAL NOT NULL,
            volume BIGINT,
            PRIMARY KEY (date, ticker)
        )
    """)
    conn.cursor().execute("CREATE INDEX IF NOT EXISTS idx_ph_ticker ON price_history(ticker, date)")
    # Migration: add OHLCV columns to existing table
    for col, typedef in [("open", "REAL"), ("high", "REAL"), ("low", "REAL"), ("volume", "BIGINT")]:
        conn.cursor().execute(f"ALTER TABLE price_history ADD COLUMN IF NOT EXISTS {col} {typedef}")


def _create_trade_journal(conn):
    conn.cursor().execute("""
        CREATE TABLE IF NOT EXISTS trade_journal (
            id           SERIAL PRIMARY KEY,
            ticker       TEXT NOT NULL,
            entry_phase  TEXT,
            entry_date   TEXT NOT NULL,
            buy_price    REAL NOT NULL,
            status       TEXT NOT NULL DEFAULT 'open',
            exit_date    TEXT,
            sell_price   REAL,
            gain_pct     REAL,
            hold_days    INTEGER,
            exit_reason  TEXT,
            created_at   TEXT,
            updated_at   TEXT
        )
    """)
    conn.cursor().execute("CREATE INDEX IF NOT EXISTS idx_journal_ticker_status ON trade_journal(ticker, status)")
    conn.cursor().execute("CREATE INDEX IF NOT EXISTS idx_journal_entry_date ON trade_journal(entry_date)")


def _create_backtest_cache(conn):
    conn.cursor().execute("""
        CREATE TABLE IF NOT EXISTS backtest_cache (
            id         SERIAL PRIMARY KEY,
            run_id     TEXT UNIQUE,
            days       INTEGER,
            date_from  TEXT,
            date_to    TEXT,
            result     TEXT,
            computed_at TEXT
        )
    """)


# ── DataSectors cache tables (Tier 1-4 — not yet active) ─────────────────────

def _create_ohlcv_cache(conn):
    conn.cursor().execute("""
        CREATE TABLE IF NOT EXISTS ohlcv_cache (
            ticker     TEXT NOT NULL,
            date       TEXT NOT NULL,
            open       REAL,
            high       REAL,
            low        REAL,
            close      REAL,
            volume     BIGINT,
            fetched_at BIGINT,
            PRIMARY KEY (ticker, date)
        )
    """)


def _create_corporate_events(conn):
    conn.cursor().execute("""
        CREATE TABLE IF NOT EXISTS corporate_events (
            ticker      TEXT NOT NULL,
            event_type  TEXT NOT NULL,
            event_date  TEXT NOT NULL,
            detail      TEXT,
            fetched_at  BIGINT,
            PRIMARY KEY (ticker, event_type, event_date)
        )
    """)


def _create_inst_flow_cache(conn):
    conn.cursor().execute("""
        CREATE TABLE IF NOT EXISTS inst_flow_cache (
            ticker     TEXT PRIMARY KEY,
            signal     TEXT,
            fetched_at BIGINT
        )
    """)


def _create_intraday_ohlcv(conn):
    conn.cursor().execute("""
        CREATE TABLE IF NOT EXISTS intraday_ohlcv (
            id        SERIAL PRIMARY KEY,
            ticker    TEXT NOT NULL,
            datetime  TEXT NOT NULL,
            date      TEXT NOT NULL,
            time      TEXT NOT NULL,
            timeframe TEXT NOT NULL,
            open      REAL,
            high      REAL,
            low       REAL,
            close     REAL,
            volume    BIGINT,
            UNIQUE (ticker, datetime, timeframe)
        )
    """)
    conn.cursor().execute("CREATE INDEX IF NOT EXISTS idx_intraday_ticker    ON intraday_ohlcv(ticker)")
    conn.cursor().execute("CREATE INDEX IF NOT EXISTS idx_intraday_date      ON intraday_ohlcv(date)")
    conn.cursor().execute("CREATE INDEX IF NOT EXISTS idx_intraday_tf        ON intraday_ohlcv(timeframe)")
    conn.cursor().execute("CREATE INDEX IF NOT EXISTS idx_intraday_tick_date ON intraday_ohlcv(ticker, date)")
