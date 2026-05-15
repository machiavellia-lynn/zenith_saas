"""
scraper_saver.py — Zenith 2.0 DB Insert Layer
RULE: Receive parsed dict from scraper_parser.py — no raw message parsing here.
      Caller controls transaction (commit/rollback). No conn.commit() here.
"""
import logging

log = logging.getLogger("zenith.saver")


def _register_tickers(conn, rows: list[dict]) -> None:
    """Upsert ticker into universe so BSJP scanner tracks it."""
    cur = conn.cursor()
    for row in rows:
        try:
            cur.execute("""
                INSERT INTO ticker_universe (ticker) VALUES (%s)
                ON CONFLICT (ticker) DO NOTHING
            """, (row["ticker"],))
        except Exception:
            pass


def save_sm_bm_rows(conn, message_id: int, rows: list[dict]) -> int:
    """Insert SM/BM rows. Returns count of new rows inserted."""
    _register_tickers(conn, rows)
    saved = 0
    cur = conn.cursor()
    for row in rows:
        try:
            cur.execute("""
                INSERT INTO raw_messages (
                    message_id, channel, date, time,
                    tx_count, ticker, price, gain_pct, freq,
                    value_raw, value_numeric,
                    avg_mf_raw, avg_mf_numeric,
                    mf_delta_raw, mf_delta_numeric,
                    vol_x, signal
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (message_id, ticker) DO NOTHING
            """, (
                message_id,
                row["channel"], row["date"], row["time"],
                row["tx_count"], row["ticker"], row["price"],
                row["gain_pct"], row["freq"],
                row["value_raw"], row["value_numeric"],
                row["avg_mf_raw"], row["avg_mf_numeric"],
                row["mf_delta_raw"], row["mf_delta_numeric"],
                row["vol_x"], row["signal"],
            ))
            saved += cur.rowcount
        except Exception as e:
            log.warning("SM/BM insert fail ticker=%s msg=%s: %s", row["ticker"], message_id, e)
    return saved


def save_mf_rows(conn, message_id: int, rows: list[dict]) -> int:
    """Insert MF+/MF- rows. Returns count of new rows inserted."""
    _register_tickers(conn, rows)
    saved = 0
    cur = conn.cursor()
    for row in rows:
        try:
            cur.execute("""
                INSERT INTO raw_mf_messages (
                    message_id, channel, date, time,
                    tx_count, ticker, price, gain_pct,
                    val_raw, val_numeric,
                    mf_raw, mf_numeric,
                    mft_raw, mft_numeric,
                    cm_delta_raw, cm_delta_numeric,
                    signal
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (message_id, ticker) DO NOTHING
            """, (
                message_id,
                row["channel"], row["date"], row["time"],
                row["tx_count"], row["ticker"], row["price"], row["gain_pct"],
                row["val_raw"], row["val_numeric"],
                row["mf_raw"], row["mf_numeric"],
                row["mft_raw"], row["mft_numeric"],
                row["cm_delta_raw"], row["cm_delta_numeric"],
                row["signal"],
            ))
            saved += cur.rowcount
        except Exception as e:
            log.warning("MF insert fail ticker=%s msg=%s: %s", row["ticker"], message_id, e)
    return saved
