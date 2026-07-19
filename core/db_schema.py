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
    _create_ticker_universe(conn)
    _create_backtest_cache(conn)
    _create_price_history_15m(conn)
    _create_ohlcv_cache(conn)
    _create_corporate_events(conn)
    _create_inst_flow_cache(conn)
    _create_bsjp_signals(conn)
    _create_bsjp_results(conn)
    _create_api_keys(conn)
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
        # BSJP setup condition columns (may live in price_history; mirrored here for single-table reads)
        ("prev_close_below_ma5",  "BOOLEAN"),
        ("ma5_price_streak",      "INTEGER"),
        ("daily_value",           "REAL"),
        ("days_since_near_bb_mid","INTEGER"),
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
    # Migration: add OHLCV columns + BSJP indicator columns
    for col, typedef in [
        ("open",   "REAL"), ("high", "REAL"), ("low", "REAL"), ("volume", "BIGINT"),
        # MAs
        ("ma5",   "REAL"), ("ma13",  "REAL"), ("ma34", "REAL"),
        ("ma50",  "REAL"), ("ma200", "REAL"),
        ("atr_pct", "REAL"),
        # Bollinger Bands
        ("bb_upper", "REAL"), ("bb_mid", "REAL"), ("bb_lower", "REAL"), ("bb_width", "REAL"),
        # Price behaviour
        ("close_pos",        "REAL"),
        ("prev_high_break",  "BOOLEAN"),
        ("ma5_price_streak", "INTEGER"),
        ("is_sideways",      "BOOLEAN"),
        ("daily_value",      "REAL"),
        # Previous-day flags
        ("prev_close_below_ma5",      "BOOLEAN"),
        ("prev_close_below_bb_lower", "BOOLEAN"),
        # Level-touch tracking
        ("days_since_near_ma50",   "INTEGER"),
        ("days_since_near_bb_mid", "INTEGER"),
    ]:
        conn.cursor().execute(f"ALTER TABLE price_history ADD COLUMN IF NOT EXISTS {col} {typedef}")


def _create_ticker_universe(conn):
    """Master list of all IDX tickers to track for BSJP.
    Auto-populated when new tickers arrive via Telegram scraper."""
    conn.cursor().execute("""
        CREATE TABLE IF NOT EXISTS ticker_universe (
            ticker    TEXT PRIMARY KEY,
            is_active BOOLEAN DEFAULT TRUE,
            added_at  TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    # Seed from existing data on first migration (idempotent via ON CONFLICT DO NOTHING)
    conn.cursor().execute("""
        INSERT INTO ticker_universe (ticker)
        SELECT DISTINCT ticker FROM eod_summary
        ON CONFLICT (ticker) DO NOTHING
    """)
    conn.cursor().execute("""
        INSERT INTO ticker_universe (ticker)
        SELECT DISTINCT ticker FROM price_history
        ON CONFLICT (ticker) DO NOTHING
    """)


def _create_price_history_15m(conn):
    """15-minute OHLCV candles for all tickers — used by BSJP backtest.
    datetime stored in WIB (UTC+7). Yahoo Finance provides max 60 days back."""
    conn.cursor().execute("""
        CREATE TABLE IF NOT EXISTS price_history_15m (
            datetime  TEXT NOT NULL,
            ticker    TEXT NOT NULL,
            open      REAL,
            high      REAL,
            low       REAL,
            close     REAL NOT NULL,
            volume    BIGINT,
            PRIMARY KEY (datetime, ticker)
        )
    """)
    conn.cursor().execute(
        "CREATE INDEX IF NOT EXISTS idx_ph15m_ticker ON price_history_15m(ticker, datetime)"
    )


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
    # Review workflow — added incrementally via ALTER TABLE.
    # 'confirmed' = excluded from Portfolio/BSJP/trade history;
    # 'suspected' = auto-detected, shown in admin for review but NOT excluded;
    # 'rejected'  = reviewed and dismissed — kept as a tombstone so the
    #               auto-detector does not re-flag the ticker every night.
    for col, typedef in [
        ("status",      "TEXT DEFAULT 'confirmed'"),
        ("detected_at", "BIGINT"),
    ]:
        conn.cursor().execute(
            f"ALTER TABLE corporate_events ADD COLUMN IF NOT EXISTS {col} {typedef}"
        )
    conn.cursor().execute(
        "UPDATE corporate_events SET status = 'confirmed' WHERE status IS NULL"
    )


def _create_inst_flow_cache(conn):
    conn.cursor().execute("""
        CREATE TABLE IF NOT EXISTS inst_flow_cache (
            ticker     TEXT PRIMARY KEY,
            signal     TEXT,
            fetched_at BIGINT
        )
    """)


def _create_bsjp_signals(conn):
    cur = conn.cursor()
    # Migrate: drop old schema that had entry_est/entry_final/invalid_reason
    cur.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'bsjp_signals' AND column_name = 'entry_final'
    """)
    if cur.fetchone():
        cur.execute("DROP TABLE IF EXISTS bsjp_signals CASCADE")

    cur.execute("""
        CREATE TABLE IF NOT EXISTS bsjp_signals (
            id          SERIAL PRIMARY KEY,
            date        TEXT NOT NULL,
            ticker      TEXT NOT NULL,
            setup       TEXT NOT NULL,
            entry       INTEGER,
            tp1         INTEGER,
            tp2         INTEGER,
            sl          INTEGER,
            sl_type     TEXT,
            score       REAL,
            day_rank    INTEGER,
            lot_size    INTEGER,
            computed_at TIMESTAMP DEFAULT NOW(),
            UNIQUE(date, ticker)
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_bsjp_date   ON bsjp_signals(date)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_bsjp_ticker ON bsjp_signals(ticker)")


def _create_bsjp_results(conn):
    conn.cursor().execute("""
        CREATE TABLE IF NOT EXISTS bsjp_results (
            id          SERIAL PRIMARY KEY,
            date        TEXT NOT NULL,
            ticker      TEXT NOT NULL,
            exit_price  REAL,
            status      TEXT,
            reason      TEXT,
            exit_time   TEXT,
            pnl         REAL,
            computed_at TIMESTAMP DEFAULT NOW(),
            UNIQUE(date, ticker)
        )
    """)
    conn.cursor().execute("CREATE INDEX IF NOT EXISTS idx_bsjp_res_date ON bsjp_results(date)")


def _create_api_keys(conn):
    """Multi-key auth for /api/v1/* external API. Legacy single ZENITH_API_KEY
    env var still accepted as a fallback — see core/api_auth.py."""
    conn.cursor().execute("""
        CREATE TABLE IF NOT EXISTS api_keys (
            id           SERIAL PRIMARY KEY,
            name         TEXT NOT NULL,
            key_prefix   TEXT NOT NULL,
            key_hash     TEXT NOT NULL UNIQUE,
            environment  TEXT NOT NULL DEFAULT 'live',
            created_at   TIMESTAMPTZ DEFAULT NOW(),
            last_used_at TIMESTAMPTZ,
            revoked      BOOLEAN DEFAULT FALSE
        )
    """)
    conn.cursor().execute("CREATE INDEX IF NOT EXISTS idx_api_keys_hash ON api_keys(key_hash)")


