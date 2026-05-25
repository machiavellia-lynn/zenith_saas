"""
scraper_daily.py — Zenith 2.0 Telegram Scraper Daemon
Realtime listener + scheduled daily backfill.
Imports pure logic from scraper_parser / scraper_saver / summary_rebuild / analytics_daily.
"""
import asyncio
import re
import os
import logging
import threading
import time
from datetime import datetime, timezone, timedelta

from config import (
    WIB, TG_API_ID, TG_API_HASH, TG_SESSION_PATH,
    TG_GROUP_ID as GROUP_ID,
    TG_TOPIC_SMART as TOPIC_SMART,
    TG_TOPIC_BAD as TOPIC_BAD,
    TG_TOPIC_MF_PLUS as TOPIC_MF_PLUS,
    TG_TOPIC_MF_MINUS as TOPIC_MF_MINUS,
    MIDDAY_HOUR, MIDDAY_MINUTE, BACKFILL_HOUR, BACKFILL_MINUTE,
    RECOMPUTE_HOUR, RECOMPUTE_MINUTE,
)
from core.db import get_scraper_db, transaction, fetchall
from core.utils import trim_memory
import psycopg2
from scraper.scraper_parser import parse_joker_message, parse_mf_message
from scraper.scraper_saver import save_sm_bm_rows, save_mf_rows
from algo.summary_rebuild import rebuild_summary_for_date, rebuild_all_summaries, seed_eod_from_price_history
from algo.analytics_daily import compute_analytics_for_date
from data.price_fetch import enrich_daily_ohlcv, backfill_price_history_ohlcv, sync_eod_prices_from_history
from algo.analytics_bsjp import compute_bsjp_for_date
from algo.algo_backtest import run_backtest

# ── Shared handler on parent "zenith" so all zenith.* loggers emit to console ──
_zenith_root = logging.getLogger("zenith")
_zenith_root.setLevel(logging.INFO)
if not _zenith_root.handlers:
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter("[%(asctime)s] %(name)s %(levelname)s — %(message)s", "%H:%M:%S"))
    _zenith_root.addHandler(_h)

log = logging.getLogger("zenith.scraper")

# ── DB reconnect helper ───────────────────────────────────────────────────────

def _ensure_conn(conn):
    """Return healthy DB connection, silently reconnecting if the link dropped.

    The scraper holds a single long-lived connection. Railway can restart
    PostgreSQL or close idle connections — this guard prevents silent data loss
    by reconnecting before each loop iteration.
    """
    try:
        conn.cursor().execute("SELECT 1")
        return conn
    except (psycopg2.OperationalError, psycopg2.InterfaceError, Exception):
        log.warning("🔌 DB connection lost — reconnecting")
        try:
            conn.close()
        except Exception:
            pass
        new_conn = get_scraper_db()
        log.info("✅ DB reconnected")
        return new_conn


# ── Topic routing ──────────────────────────────────────────────────────────────
SM_BM_TOPICS = {TOPIC_SMART, TOPIC_BAD}
MF_TOPICS    = {TOPIC_MF_PLUS, TOPIC_MF_MINUS}
ALL_TOPICS   = SM_BM_TOPICS | MF_TOPICS

TOPIC_LABELS = {
    TOPIC_SMART:    "SM",
    TOPIC_BAD:      "BM",
    TOPIC_MF_PLUS:  "MF+",
    TOPIC_MF_MINUS: "MF-",
}
TOPIC_CHANNELS = {
    TOPIC_SMART:    "smart",
    TOPIC_BAD:      "bad",
    TOPIC_MF_PLUS:  "mf_plus",
    TOPIC_MF_MINUS: "mf_minus",
}

# ── BSJP constants ────────────────────────────────────────────────────────────
BSJP_PREFETCH_HOUR   = 12
BSJP_PREFETCH_MINUTE = 30
BSJP_15M_HOUR        = 15
BSJP_15M_MINUTE      = 46
BSJP_HOUR            = 15
BSJP_MINUTE          = 48
TOP_N_BSJP = 15

# ── Analytics throttle — recompute at most once per 60s per date ───────────────
_analytics_throttle: dict = {}
_analytics_throttle_lock  = threading.Lock()
ANALYTICS_THROTTLE_SECS   = 60


def _should_recompute_analytics(date_str: str) -> bool:
    now = time.time()
    with _analytics_throttle_lock:
        last = _analytics_throttle.get(date_str, 0)
        if now - last > ANALYTICS_THROTTLE_SECS:
            _analytics_throttle[date_str] = now
            return True
    return False


def get_message_topic_id(message) -> int | None:
    if message.reply_to:
        return (getattr(message.reply_to, "reply_to_top_id", None) or
                getattr(message.reply_to, "reply_to_msg_id", None))
    return None


_TOPIC_HANDLERS = None  # initialized lazily to avoid circular import at module load


def _get_topic_handlers():
    global _TOPIC_HANDLERS
    if _TOPIC_HANDLERS is None:
        _TOPIC_HANDLERS = {
            **{t: (parse_joker_message, save_sm_bm_rows) for t in SM_BM_TOPICS},
            **{t: (parse_mf_message,    save_mf_rows)    for t in MF_TOPICS},
        }
    return _TOPIC_HANDLERS


def process_message(conn, message) -> int:
    """Parse + save one Telegram message. Returns rows saved."""
    if not message.text:
        return 0

    topic_id = get_message_topic_id(message)
    handler  = _get_topic_handlers().get(topic_id)
    if not handler:
        return 0

    parse_fn, save_fn = handler
    channel = TOPIC_CHANNELS[topic_id]
    rows    = parse_fn(message.text, channel)
    if not rows:
        return 0

    with transaction(conn):
        saved = save_fn(conn, message.id, rows)

    if saved > 0 and rows[0].get("date"):
        date_str = rows[0]["date"]
        try:
            with transaction(conn):
                rebuild_summary_for_date(conn, date_str)
            if _should_recompute_analytics(date_str):
                with transaction(conn):
                    compute_analytics_for_date(conn, date_str)
        except Exception as e:
            log.warning("Post-save analytics failed date=%s: %s", date_str, e)

    return saved


# ── Backfill + request queue ───────────────────────────────────────────────────
_backfill_request      = {"days": None, "status": "idle", "result": None}
_rebuild_request       = {"status": "idle", "result": None}
_recompute_request     = {"status": "idle", "result": None}
_backtest_request      = {"days": None, "status": "idle", "result": None}
_fix_all_request       = {"status": "idle", "step": None, "date_from": None, "date_to": None, "result": None}
_tele_dates_request    = {"dates": None, "status": "idle", "scanned": 0, "saved": 0, "error": None}
_backfill_lock    = threading.Lock()
_scraper_thread   = None
# Signals the async loop to wake up immediately when a request is queued
# instead of waiting up to 5 s for the next sleep cycle.
_request_event: asyncio.Event | None = None


async def run_backfill(client, conn):
    """Scan today's messages in all 4 topics and fill any gaps."""
    today_wib = datetime.now(WIB).strftime("%d-%m-%Y")
    log.info(f"🔄 BACKFILL {today_wib}")

    total_saved = 0
    for topic_id in ALL_TOPICS:
        label = TOPIC_LABELS[topic_id]
        scanned = saved = 0
        async for message in client.iter_messages(GROUP_ID, reply_to=topic_id, limit=None):
            if not message.text:
                continue
            text_clean = message.text.replace("```", "").replace("`", "")
            date_match = re.search(r"(\d{2}-\d{2}-\d{4})", text_clean)
            if not date_match:
                continue
            if date_match.group(1) != today_wib:
                scanned += 1
                if scanned > 50 and saved == 0:
                    break
                continue
            scanned += 1
            saved += process_message(conn, message)
        log.info(f"  {label}: scanned={scanned}, new={saved}")
        total_saved += saved

    try:
        with transaction(conn):
            rebuild_summary_for_date(conn, today_wib)
        with transaction(conn):
            enrich_daily_ohlcv(conn, today_wib)
        with transaction(conn):
            seed_eod_from_price_history(conn, today_wib, today_wib)
        with transaction(conn):
            compute_analytics_for_date(conn, today_wib)
        with transaction(conn):
            compute_bsjp_for_date(conn, today_wib)
    except Exception as e:
        log.warning("Post-backfill analytics failed: %s", e)

    log.info(f"✅ BACKFILL done — {total_saved} new rows")


def _wake_loop():
    """Signal the scraper loop to process pending requests immediately."""
    if _request_event is not None:
        _request_event.set()


def request_backfill(days: int) -> dict:
    with _backfill_lock:
        if _backfill_request["status"] == "running":
            return {"ok": False, "error": "Backfill already running"}
        _backfill_request.update({"days": days, "status": "pending", "result": None})
    _wake_loop()
    return {"ok": True, "message": f"Backfill {days} days queued"}


def request_rebuild() -> dict:
    with _backfill_lock:
        if _rebuild_request["status"] == "running":
            return {"ok": False, "error": "Rebuild already running"}
        _rebuild_request.update({"status": "pending", "result": None})
    log.info("📋 Rebuild Summary queued")
    _wake_loop()
    return {"ok": True, "message": "Summary rebuild queued"}


def request_recompute_analytics() -> dict:
    with _backfill_lock:
        if _recompute_request["status"] == "running":
            return {"ok": False, "error": "Recompute already running"}
        _recompute_request.update({"status": "pending", "result": None})
    log.info("📋 Recompute Analytics queued")
    _wake_loop()
    return {"ok": True, "message": "Analytics recompute queued"}


def request_tele_dates_backfill(dates: list) -> dict:
    with _backfill_lock:
        if _tele_dates_request["status"] in ("running", "pending"):
            return {"ok": False, "error": "Telegram backfill sedang berjalan"}
        _tele_dates_request.update({"dates": dates, "status": "pending",
                                    "scanned": 0, "saved": 0, "error": None})
    log.info("📋 Tele dates backfill queued: %s", dates)
    _wake_loop()
    return {"ok": True, "message": f"Telegram backfill queued ({len(dates)} tanggal)"}


def get_tele_dates_status() -> dict:
    with _backfill_lock:
        return dict(_tele_dates_request)


def request_fix_all(date_from: str = None, date_to: str = None) -> dict:
    with _backfill_lock:
        if _fix_all_request["status"] == "running":
            return {"ok": False, "error": "Fix All already running"}
        _fix_all_request.update({"status": "pending", "step": None,
                                  "date_from": date_from, "date_to": date_to, "result": None})
    log.info("📋 Fix All queued (date_from=%s date_to=%s)", date_from or "all", date_to or "all")
    _wake_loop()
    return {"ok": True, "message": "Fix All queued"}


def get_backfill_status() -> dict:
    with _backfill_lock:
        return {
            "backfill":     dict(_backfill_request),
            "rebuild":      dict(_rebuild_request),
            "recompute":    dict(_recompute_request),
            "backtest":     dict(_backtest_request),
            "fix_all":      dict(_fix_all_request),
            "thread_alive": _scraper_thread is not None and _scraper_thread.is_alive(),
        }


# ── BSJP scan ────────────────────────────────────────────────────────────────

def run_bsjp_scan(conn, date_dmy: str | None = None):
    """
    15:48 pass — generate BSJP signals.
    Indicators from eod_summary directly; days_since_near_bb_mid from price_history.
    15:45 candle used for condition check only; entry = eod_summary.price_close.
    """
    from algo.algo_bsjp import BSJPAlgo, BLACKLIST, _is_ara, _compute_score, _to_tick

    WIB_TZ  = timezone(timedelta(hours=7))
    today   = date_dmy or datetime.now(WIB_TZ).strftime("%d-%m-%Y")
    try:
        d, m, y = today.split("-")
        today_ymd = f"{y}-{m}-{d}"
    except Exception:
        today_ymd = datetime.now(WIB_TZ).strftime("%Y-%m-%d")

    algo = BSJPAlgo()

    # SM/BM/Wyckoff from eod_summary; BSJP indicators from price_history (same day).
    # Use today_ymd (YYYY-MM-DD) as direct parameter so PostgreSQL can use idx_ph_ticker.
    with conn.cursor() as cur:
        cur.execute("""
            SELECT
                e.date, e.ticker,
                e.sm_val, e.bm_val, e.sri, e.rpr, e.mf_ratio,
                e.price_close, e.price_change_pct, e.phase,
                COALESCE(e.ma5, p.ma5)             AS ma5,
                COALESCE(e.bb_mid, p.bb_mid)       AS bb_mid,
                COALESCE(e.bb_upper, p.bb_upper)   AS bb_upper,
                COALESCE(e.bb_lower, p.bb_lower)   AS bb_lower,
                COALESCE(e.is_sideways, p.is_sideways) AS is_sideways,
                COALESCE(e.close_pos, p.close_pos) AS close_pos,
                COALESCE(e.prev_high_break, p.prev_high_break) AS prev_high_break,
                p.ma5_price_streak,
                p.daily_value,
                p.prev_close_below_ma5,
                p.days_since_near_bb_mid
            FROM eod_summary e
            LEFT JOIN price_history p
                ON p.ticker = e.ticker AND p.date = %s
            WHERE e.date = %s
        """, (today_ymd, today))
        eod_rows = [dict(r) for r in cur.fetchall()]

    if not eod_rows:
        log.info(f"[BSJP] {today}: eod_summary kosong, tidak ada kandidat.")
        return 0

    # Fetch 15:45 and 09:00 candles in one query
    with conn.cursor() as cur:
        cur.execute("""
            SELECT ticker, datetime, open, close FROM price_history_15m
            WHERE datetime IN (%s, %s)
        """, (today_ymd + " 15:45", today_ymd + " 09:00"))
        prices_1545, prices_open = {}, {}
        for r in cur.fetchall():
            if str(r["datetime"]).endswith("15:45") and r["close"]:
                prices_1545[r["ticker"]] = float(r["close"])
            elif str(r["datetime"]).endswith("09:00") and r["open"]:
                prices_open[r["ticker"]] = float(r["open"])

    scored = []
    for row in eod_rows:
        ticker = row.get("ticker", "")
        if ticker in BLACKLIST:
            continue

        eod_price_close = float(row.get("price_close") or 0)
        if not eod_price_close:
            continue

        close_1545 = prices_1545.get(ticker)
        open_0900  = prices_open.get(ticker)

        # Override price_close with 15:45 candle for condition checking only
        row_scan = dict(row)
        if close_1545:
            row_scan["price_close"] = close_1545
            if open_0900 and open_0900 > 0:
                row_scan["price_change_pct"] = (close_1545 - open_0900) / open_0900 * 100

        if _is_ara(row_scan):
            continue

        sig = algo.signal_detail(ticker, row_scan)
        if not sig:
            continue

        # Entry = EOD close from eod_summary (tick-rounded), not 15:45 candle
        sig["entry"] = _to_tick(eod_price_close)
        sig["tp1"]   = _to_tick(eod_price_close * 1.01)
        sig["tp2"]   = _to_tick(eod_price_close * 1.02)

        score = _compute_score(row_scan, sig["setup"])
        lot   = int(10_000_000 / eod_price_close)
        scored.append((score, ticker, sig, row_scan, lot))

    scored.sort(key=lambda x: -x[0])
    top = scored[:TOP_N_BSJP]

    with conn.cursor() as cur:
        cur.execute("DELETE FROM bsjp_signals WHERE date = %s", (today,))
        if top:
            cur.executemany("""
                INSERT INTO bsjp_signals
                    (date, ticker, setup, entry, tp1, tp2, sl, sl_type,
                     score, day_rank, lot_size)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, [
                (today, ticker, sig["setup"], sig["entry"],
                 sig["tp1"], sig["tp2"], sig["sl"], sig["sl_type"],
                 score, rank, lot)
                for rank, (score, ticker, sig, row, lot) in enumerate(top, 1)
            ])
    conn.commit()

    log.info(f"[BSJP] {today}: {len(top)} sinyal (dari {len(scored)} kandidat). 15m: {len(prices_1545)} ticker.")
    return len(top)


# ── BSJP pre-filter ───────────────────────────────────────────────────────────

def pre_filter_bsjp_candidates(conn, date_dmy: str) -> list:
    """Return tickers that pass the BSJP SM gate from eod_summary.
    date_dmy in DD-MM-YYYY. Used to minimize DataSectors API calls at 15:46."""
    from algo.algo_bsjp import BLACKLIST
    rows = fetchall(conn, """
        SELECT ticker
        FROM eod_summary
        WHERE date = %s
          AND phase NOT IN ('UPTHRUST', 'DISTRI')
          AND sri >= 1.2
          AND mf_ratio >= 50.0
          AND price_close > 0
          AND sm_val IS NOT NULL
          AND bm_val IS NOT NULL
          AND sm_val > 0
          AND (sm_val + ABS(bm_val)) > 0
          AND sm_val * 100.0 / (sm_val + ABS(bm_val)) >= 60
    """, [date_dmy])
    return [r["ticker"] for r in rows if r["ticker"] not in BLACKLIST]


# ── Main async loop ────────────────────────────────────────────────────────────
async def scraper_main():
    try:
        from telethon import TelegramClient, events
    except ImportError:
        log.error("❌ telethon not installed")
        return

    session_file = TG_SESSION_PATH
    if not os.path.exists(session_file + ".session") and not os.path.exists(session_file):
        log.error(f"❌ Session file not found: {session_file}")
        return

    global _request_event
    _request_event = asyncio.Event()

    conn = get_scraper_db()
    log.info("📦 DB: PostgreSQL connected")

    client = TelegramClient(session_file, TG_API_ID, TG_API_HASH)
    try:
        await client.connect()
        if not await client.is_user_authorized():
            log.error("❌ Session not authorized")
            return

        log.info("🔗 Telegram connected")
        await client.get_dialogs(limit=50)  # limit entity cache; 50 cukup untuk resolve GROUP_ID

        @client.on(events.NewMessage(chats=GROUP_ID))
        async def on_new_message(event):
            nonlocal conn
            try:
                conn = _ensure_conn(conn)
                n = process_message(conn, event.message)
                if n > 0:
                    label = TOPIC_LABELS.get(get_message_topic_id(event.message), "?")
                    log.info(f"📩 {label} msg={event.message.id} → {n} row(s)")
            except Exception as e:
                log.error(f"❌ Listener error: {e}")

        log.info(f"👂 Listening | midday {MIDDAY_HOUR:02d}:{MIDDAY_MINUTE:02d} / backfill {BACKFILL_HOUR:02d}:{BACKFILL_MINUTE:02d} / recompute {RECOMPUTE_HOUR:02d}:{RECOMPUTE_MINUTE:02d} WIB")

        midday_pass_done = first_pass_done = second_pass_done = backtest_done_today = False
        bsjp_prefetch_done = bsjp_15m_done = bsjp_scan_done = False
        last_check_date = None

        while True:
            conn = _ensure_conn(conn)
            now_wib    = datetime.now(WIB)
            today_str  = now_wib.strftime("%Y-%m-%d")

            log.debug(f"⏰ Loop iteration at {now_wib.strftime('%H:%M:%S')}")

            if today_str != last_check_date:
                midday_pass_done = first_pass_done = second_pass_done = backtest_done_today = False
                bsjp_prefetch_done = bsjp_15m_done = bsjp_scan_done = False
                last_check_date = today_str

            if not midday_pass_done and (now_wib.hour > MIDDAY_HOUR or (now_wib.hour == MIDDAY_HOUR and now_wib.minute >= MIDDAY_MINUTE)):
                try:
                    log.info("🌤️ Midday pass (12:10)")
                    await run_backfill(client, conn)
                except Exception as e:
                    log.error(f"❌ Midday pass: {e}")
                finally:
                    midday_pass_done = True
                    trim_memory()

            if not first_pass_done and now_wib.hour >= BACKFILL_HOUR and now_wib.minute >= BACKFILL_MINUTE:
                try:
                    log.info("🔔 First pass (15:30)")
                    await run_backfill(client, conn)
                except Exception as e:
                    log.error(f"❌ First pass: {e}")
                finally:
                    first_pass_done = True
                    trim_memory()

            if first_pass_done and not second_pass_done and now_wib.hour >= RECOMPUTE_HOUR and now_wib.minute >= RECOMPUTE_MINUTE:
                try:
                    log.info("🔄 Second pass (16:30)")
                    await run_backfill(client, conn)
                except Exception as e:
                    log.error(f"❌ Second pass: {e}")
                finally:
                    second_pass_done = True
                    trim_memory()

            # 12:30 — Pre-fetch 15m candles for all tickers (09:00–12:xx stored in DB)
            if not bsjp_prefetch_done and now_wib.hour == BSJP_PREFETCH_HOUR and now_wib.minute >= BSJP_PREFETCH_MINUTE:
                try:
                    log.info("📡 BSJP 15m prefetch (12:30) — all active tickers")
                    from data.price_fetch import fetch_intraday_15m_datasectors
                    today_dmy   = now_wib.strftime("%d-%m-%Y")
                    all_tickers = [r["ticker"] for r in fetchall(conn,
                        "SELECT ticker FROM ticker_universe WHERE is_active = TRUE")]
                    res = fetch_intraday_15m_datasectors(conn, all_tickers, today_dmy)
                    conn.commit()
                    log.info(f"📡 15m prefetch done: {res.get('rows_inserted', 0)} rows for {res.get('tickers', 0)} tickers")
                except Exception as e:
                    log.error(f"❌ BSJP 15m prefetch: {e}")
                finally:
                    bsjp_prefetch_done = True

            # 15:46 — Fetch 15m candles for BSJP candidates only (15:45 candle must be ready)
            if not bsjp_15m_done and now_wib.hour == BSJP_15M_HOUR and now_wib.minute >= BSJP_15M_MINUTE:
                try:
                    log.info("📡 BSJP 15m enrich (15:46)")
                    from data.price_fetch import fetch_intraday_15m_datasectors
                    today_dmy  = now_wib.strftime("%d-%m-%Y")
                    candidates = pre_filter_bsjp_candidates(conn, today_dmy)
                    log.info(f"📡 BSJP candidates: {len(candidates)} tickers")
                    res = fetch_intraday_15m_datasectors(conn, candidates, today_dmy)
                    conn.commit()
                    log.info(f"📡 15m enrich done: {res.get('rows_inserted', 0)} rows for {len(candidates)} tickers")
                except Exception as e:
                    log.error(f"❌ BSJP 15m enrich: {e}")
                finally:
                    bsjp_15m_done = True

            # 15:48 — BSJP Signal
            if not bsjp_scan_done and now_wib.hour == BSJP_HOUR and now_wib.minute >= BSJP_MINUTE:
                try:
                    log.info("📊 BSJP scan (15:48)")
                    run_bsjp_scan(conn)
                except Exception as e:
                    log.error(f"❌ BSJP scan: {e}")
                finally:
                    bsjp_scan_done = True

            if second_pass_done and not backtest_done_today:
                try:
                    run_backtest(conn, days=0)
                except Exception as e:
                    log.error(f"❌ Nightly backtest: {e}")
                finally:
                    backtest_done_today = True

            with _backfill_lock:
                bf_status = _backfill_request.get("status", "idle")
                pending_days = _backfill_request["days"] if bf_status == "pending" else None
                if pending_days is not None and pending_days > 0:
                    log.info(f"📥 Backfill request detected: days={pending_days}, setting status→running")
                    _backfill_request["status"] = "running"
                elif bf_status != "idle":
                    log.debug(f"Backfill status={bf_status}, days={_backfill_request.get('days')}")

            if pending_days:
                try:
                    from scraper.scraper_weekly import run_weekly_backfill
                    result = await run_weekly_backfill(client, conn, days=pending_days)
                    with _backfill_lock:
                        _backfill_request.update({"status": "done", "result": result})
                except Exception as e:
                    log.error(f"❌ Manual backfill: {e}")
                    with _backfill_lock:
                        _backfill_request.update({"status": "error", "result": str(e)})
                finally:
                    trim_memory()

            with _backfill_lock:
                do_rebuild = _rebuild_request["status"] == "pending"
                if do_rebuild:
                    _rebuild_request["status"] = "running"

            if do_rebuild:
                try:
                    result = rebuild_all_summaries(conn)
                    with _backfill_lock:
                        _rebuild_request.update({"status": "done", "result": result})
                except Exception as e:
                    log.error(f"❌ Rebuild: {e}")
                    with _backfill_lock:
                        _rebuild_request.update({"status": "error", "result": str(e)})
                finally:
                    trim_memory()

            with _backfill_lock:
                do_recompute = _recompute_request["status"] == "pending"
                if do_recompute:
                    _recompute_request["status"] = "running"

            if do_recompute:
                try:
                    dates = [r["date"] for r in fetchall(conn, """
                        SELECT date FROM (
                            SELECT DISTINCT date FROM eod_summary
                        ) t
                        ORDER BY TO_DATE(date,'DD-MM-YYYY')
                    """)]
                    log.info("🔄 Recompute analytics START — %d dates", len(dates))
                    total = 0
                    for i, d in enumerate(dates, 1):
                        try:
                            n = compute_analytics_for_date(conn, d)
                            total += n
                            conn.commit()
                        except Exception as e:
                            conn.rollback()
                            log.error("analytics failed for %s: %s", d, e)
                        if i % 10 == 0 or i == len(dates):
                            log.info("  recompute progress %d/%d (rows=%d)", i, len(dates), total)
                    with _backfill_lock:
                        _recompute_request.update({"status": "done", "result": {"total": total, "dates": len(dates)}})
                    log.info("✅ Recompute analytics DONE — %d rows, %d dates", total, len(dates))
                except Exception as e:
                    log.error("❌ Recompute analytics: %s", e)
                    with _backfill_lock:
                        _recompute_request.update({"status": "error", "result": str(e)})
                finally:
                    trim_memory()

            with _backfill_lock:
                bt_days = _backtest_request["days"] if _backtest_request["status"] == "pending" else None
                if bt_days:
                    _backtest_request["status"] = "running"

            if bt_days:
                try:
                    result = run_backtest(conn, days=bt_days)
                    with _backfill_lock:
                        _backtest_request.update({"status": "done", "result": {"ok": True, "total_trades": result.get("trade_count", 0)}})
                except Exception as e:
                    log.error(f"❌ Backtest: {e}")
                    with _backfill_lock:
                        _backtest_request.update({"status": "error", "result": str(e)})

            with _backfill_lock:
                do_fix_all = _fix_all_request["status"] == "pending"
                if do_fix_all:
                    _fix_all_request["status"] = "running"
                    fa_date_from = _fix_all_request["date_from"]
                    fa_date_to   = _fix_all_request["date_to"]

            if do_fix_all:
                try:
                    def _set_step(s):
                        with _backfill_lock:
                            _fix_all_request["step"] = s

                    # Step 1: rebuild summaries
                    _set_step("rebuild")
                    log.info("Fix All — Step 1: rebuild summaries")
                    if fa_date_from and fa_date_to:
                        dates = [r["date"] for r in fetchall(conn, """
                            SELECT date FROM (SELECT DISTINCT date FROM eod_summary) t
                            WHERE TO_DATE(date,'DD-MM-YYYY') BETWEEN TO_DATE(%s,'DD-MM-YYYY') AND TO_DATE(%s,'DD-MM-YYYY')
                            ORDER BY TO_DATE(date,'DD-MM-YYYY')
                        """, [fa_date_from, fa_date_to])]
                        for d in dates:
                            try:
                                with transaction(conn):
                                    rebuild_summary_for_date(conn, d)
                            except Exception as e:
                                log.error("Fix All rebuild failed date=%s: %s", d, e)
                                conn.rollback()
                    else:
                        rebuild_all_summaries(conn)
                        conn.commit()

                    # Step 2: backfill OHLCV into price_history
                    _set_step("prices")
                    log.info("Fix All — Step 2: backfill OHLCV price history")
                    backfill_price_history_ohlcv(conn, fa_date_from, fa_date_to)
                    conn.commit()

                    # Step 3: sync eod_summary.price_close from price_history
                    _set_step("sync")
                    log.info("Fix All — Step 3: sync eod prices from history")
                    sync_eod_prices_from_history(conn, fa_date_from, fa_date_to)
                    conn.commit()

                    # Step 4: recompute analytics
                    _set_step("analytics")
                    log.info("Fix All — Step 4: recompute analytics")
                    if fa_date_from and fa_date_to:
                        ana_dates = [r["date"] for r in fetchall(conn, """
                            SELECT date FROM (SELECT DISTINCT date FROM eod_summary) t
                            WHERE TO_DATE(date,'DD-MM-YYYY') BETWEEN TO_DATE(%s,'DD-MM-YYYY') AND TO_DATE(%s,'DD-MM-YYYY')
                            ORDER BY TO_DATE(date,'DD-MM-YYYY')
                        """, [fa_date_from, fa_date_to])]
                    else:
                        ana_dates = [r["date"] for r in fetchall(conn, """
                            SELECT date FROM (SELECT DISTINCT date FROM eod_summary) t
                            ORDER BY TO_DATE(date,'DD-MM-YYYY')
                        """)]
                    total_a = 0
                    for i, d in enumerate(ana_dates, 1):
                        try:
                            n = compute_analytics_for_date(conn, d)
                            total_a += n
                            conn.commit()
                        except Exception as e:
                            conn.rollback()
                            log.error("Fix All analytics failed date=%s: %s", d, e)
                        if i % 10 == 0 or i == len(ana_dates):
                            log.info("  fix_all analytics %d/%d (rows=%d)", i, len(ana_dates), total_a)

                    # Step 5: compute BSJP indicators for all tickers
                    _set_step("bsjp")
                    log.info("Fix All — Step 5: compute BSJP indicators")
                    bsjp_dates = [r["date"] for r in fetchall(conn, """
                        SELECT DISTINCT date FROM price_history
                        ORDER BY date
                    """)]
                    total_b = 0
                    for i, d in enumerate(bsjp_dates, 1):
                        try:
                            n = compute_bsjp_for_date(conn, d)
                            total_b += n
                            conn.commit()
                        except Exception as e:
                            conn.rollback()
                            log.error("Fix All BSJP failed date=%s: %s", d, e)
                        if i % 20 == 0 or i == len(bsjp_dates):
                            log.info("  bsjp progress %d/%d (rows=%d)", i, len(bsjp_dates), total_b)

                    with _backfill_lock:
                        _fix_all_request.update({
                            "status": "done", "step": None,
                            "result": {
                                "dates": len(ana_dates), "analytics_rows": total_a,
                                "bsjp_dates": len(bsjp_dates), "bsjp_rows": total_b,
                            },
                        })
                    log.info("Fix All done: %d Wyckoff dates, %d BSJP dates", len(ana_dates), len(bsjp_dates))
                except Exception as e:
                    log.error(f"❌ Fix All: {e}")
                    with _backfill_lock:
                        _fix_all_request.update({"status": "error", "step": None, "result": str(e)})
                finally:
                    trim_memory()

            with _backfill_lock:
                do_tele_dates = _tele_dates_request["status"] == "pending"
                if do_tele_dates:
                    _tele_dates_request["status"] = "running"
                    tele_dates_list = _tele_dates_request["dates"]

            if do_tele_dates:
                try:
                    from scraper.scraper_weekly import run_weekly_backfill
                    result = await run_weekly_backfill(client, conn, dates=tele_dates_list)
                    with _backfill_lock:
                        _tele_dates_request.update({"status": "done",
                            "scanned": result.get("scanned", 0),
                            "saved":   result.get("saved", 0)})
                    log.info("✅ Tele dates backfill done: scanned=%d saved=%d",
                             result.get("scanned", 0), result.get("saved", 0))
                except Exception as e:
                    log.error("❌ Tele dates backfill: %s", e)
                    with _backfill_lock:
                        _tele_dates_request.update({"status": "error", "error": str(e)})
                finally:
                    trim_memory()

            # Wait up to 5 s, but wake immediately if a request is queued
            try:
                await asyncio.wait_for(_request_event.wait(), timeout=5)
                _request_event.clear()
            except asyncio.TimeoutError:
                pass

    except Exception as e:
        log.error(f"❌ Fatal: {e}")
        raise  # signal wrapper: transient failure, restart needed
    finally:
        try:
            await client.disconnect()
        except Exception:
            pass
        try:
            conn.close()
        except Exception:
            pass
        log.info("🔌 Disconnected")


def start_scraper_thread():
    global _scraper_thread

    def _run():
        delay = 0
        while True:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(scraper_main())
                break  # clean exit (no session / not authorized) — permanent, don't restart
            except Exception:
                pass   # already logged by scraper_main
            finally:
                loop.close()
            delay = min(delay * 2 + 10, 300)   # 10 → 30 → 70 → 150 → 300s cap
            log.warning("🔄 Scraper restarting in %ds", delay)
            time.sleep(delay)

    _scraper_thread = threading.Thread(target=_run, name="zenith-scraper", daemon=True)
    _scraper_thread.start()
    log.info("🚀 Scraper thread started")
    return _scraper_thread
