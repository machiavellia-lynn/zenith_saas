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
from datetime import datetime, timezone

from config import (
    WIB, TG_API_ID, TG_API_HASH, TG_SESSION_PATH,
    TG_GROUP_ID as GROUP_ID,
    TG_TOPIC_SMART as TOPIC_SMART,
    TG_TOPIC_BAD as TOPIC_BAD,
    TG_TOPIC_MF_PLUS as TOPIC_MF_PLUS,
    TG_TOPIC_MF_MINUS as TOPIC_MF_MINUS,
    BACKFILL_HOUR, BACKFILL_MINUTE, RECOMPUTE_HOUR, RECOMPUTE_MINUTE,
)
from core.db import get_scraper_db, transaction
from scraper.scraper_parser import parse_joker_message, parse_mf_message
from scraper.scraper_saver import save_sm_bm_rows, save_mf_rows
from algo.summary_rebuild import rebuild_summary_for_date, rebuild_all_summaries
from algo.analytics_daily import compute_analytics_for_date
from data.price_fetch import enrich_daily_prices, sync_price_history_from_eod
from algo.algo_backtest import run_backtest

log = logging.getLogger("zenith.scraper")
log.setLevel(logging.INFO)
log.propagate = False
if not log.handlers:
    h = logging.StreamHandler()
    h.setFormatter(logging.Formatter("[%(asctime)s] SCRAPER %(levelname)s — %(message)s", "%H:%M:%S"))
    log.addHandler(h)

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


def process_message(conn, message) -> int:
    """Parse + save one Telegram message. Returns rows saved."""
    if not message.text:
        return 0

    topic_id = get_message_topic_id(message)
    if topic_id not in ALL_TOPICS:
        return 0

    msg_id  = message.id
    channel = TOPIC_CHANNELS[topic_id]

    if topic_id in SM_BM_TOPICS:
        rows = parse_joker_message(message.text, channel)
        if rows:
            with transaction(conn):
                saved = save_sm_bm_rows(conn, msg_id, rows)
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
    else:
        rows = parse_mf_message(message.text, channel)
        if rows:
            with transaction(conn):
                saved = save_mf_rows(conn, msg_id, rows)
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

    return 0


# ── Backfill + request queue ───────────────────────────────────────────────────
_backfill_request  = {"days": None, "status": "idle", "result": None}
_rebuild_request   = {"status": "idle", "result": None}
_recompute_request = {"status": "idle", "result": None}
_backtest_request  = {"days": None, "status": "idle", "result": None}
_backfill_lock    = threading.Lock()
_scraper_thread   = None


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
            enrich_daily_prices(conn, today_wib)
        with transaction(conn):
            sync_price_history_from_eod(conn, today_wib)
        with transaction(conn):
            compute_analytics_for_date(conn, today_wib)
    except Exception as e:
        log.warning("Post-backfill analytics failed: %s", e)

    log.info(f"✅ BACKFILL done — {total_saved} new rows")


def request_backfill(days: int) -> dict:
    with _backfill_lock:
        if _backfill_request["status"] == "running":
            return {"ok": False, "error": "Backfill already running"}
        _backfill_request.update({"days": days, "status": "pending", "result": None})
        return {"ok": True, "message": f"Backfill {days} days queued"}


def request_rebuild() -> dict:
    with _backfill_lock:
        if _rebuild_request["status"] == "running":
            return {"ok": False, "error": "Rebuild already running"}
        _rebuild_request.update({"status": "pending", "result": None})
        return {"ok": True, "message": "Summary rebuild queued"}


def request_recompute_analytics() -> dict:
    with _backfill_lock:
        if _recompute_request["status"] == "running":
            return {"ok": False, "error": "Recompute already running"}
        _recompute_request.update({"status": "pending", "result": None})
        return {"ok": True, "message": "Analytics recompute queued"}


def get_backfill_status() -> dict:
    with _backfill_lock:
        return {
            "backfill":     dict(_backfill_request),
            "rebuild":      dict(_rebuild_request),
            "recompute":    dict(_recompute_request),
            "backtest":     dict(_backtest_request),
            "thread_alive": _scraper_thread is not None and _scraper_thread.is_alive(),
        }


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

    conn = get_scraper_db()
    log.info("📦 DB: PostgreSQL connected")

    client = TelegramClient(session_file, TG_API_ID, TG_API_HASH)
    try:
        await client.connect()
        if not await client.is_user_authorized():
            log.error("❌ Session not authorized")
            return

        log.info("🔗 Telegram connected")
        await client.get_dialogs()

        @client.on(events.NewMessage(chats=GROUP_ID))
        async def on_new_message(event):
            try:
                n = process_message(conn, event.message)
                if n > 0:
                    label = TOPIC_LABELS.get(get_message_topic_id(event.message), "?")
                    log.info(f"📩 {label} msg={event.message.id} → {n} row(s)")
            except Exception as e:
                log.error(f"❌ Listener error: {e}")

        log.info(f"👂 Listening | backfill {BACKFILL_HOUR:02d}:{BACKFILL_MINUTE:02d} / recompute {RECOMPUTE_HOUR:02d}:{RECOMPUTE_MINUTE:02d} WIB")

        first_pass_done = second_pass_done = backtest_done_today = False
        last_check_date = None

        while True:
            now_wib    = datetime.now(WIB)
            today_str  = now_wib.strftime("%Y-%m-%d")

            log.debug(f"⏰ Loop iteration at {now_wib.strftime('%H:%M:%S')}")

            if today_str != last_check_date:
                first_pass_done = second_pass_done = backtest_done_today = False
                last_check_date = today_str

            if not first_pass_done and now_wib.hour >= BACKFILL_HOUR and now_wib.minute >= BACKFILL_MINUTE:
                try:
                    log.info("🔔 First pass (15:30)")
                    await run_backfill(client, conn)
                except Exception as e:
                    log.error(f"❌ First pass: {e}")
                finally:
                    first_pass_done = True

            if first_pass_done and not second_pass_done and now_wib.hour >= RECOMPUTE_HOUR and now_wib.minute >= RECOMPUTE_MINUTE:
                try:
                    log.info("🔄 Second pass (16:30)")
                    await run_backfill(client, conn)
                except Exception as e:
                    log.error(f"❌ Second pass: {e}")
                finally:
                    second_pass_done = True

            if second_pass_done and not backtest_done_today:
                try:
                    today_wib_str = datetime.now(WIB).strftime("%d-%m-%Y")
                    run_backtest(conn, days=0, date_from="29-09-2025", date_to=today_wib_str)
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

            with _backfill_lock:
                do_recompute = _recompute_request["status"] == "pending"
                if do_recompute:
                    _recompute_request["status"] = "running"

            if do_recompute:
                try:
                    dates = [r["date"] for r in fetchall(conn,
                        "SELECT DISTINCT date FROM eod_summary ORDER BY TO_DATE(date,'DD-MM-YYYY')")]
                    log.info(f"🔄 Recompute analytics: {len(dates)} dates")
                    total = 0
                    for d in dates:
                        try:
                            n = compute_analytics_for_date(conn, d)
                            total += n
                            conn.commit()
                        except Exception as e:
                            conn.rollback()
                            log.error("analytics failed for %s: %s", d, e)
                    with _backfill_lock:
                        _recompute_request.update({"status": "done", "result": {"total": total, "dates": len(dates)}})
                    log.info(f"✅ Recompute analytics done: {total} rows, {len(dates)} dates")
                except Exception as e:
                    log.error(f"❌ Recompute analytics: {e}")
                    with _backfill_lock:
                        _recompute_request.update({"status": "error", "result": str(e)})

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

            await asyncio.sleep(5)

    except Exception as e:
        log.error(f"❌ Fatal: {e}")
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
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(scraper_main())
        except Exception as e:
            log.error(f"❌ Thread crashed: {e}")
        finally:
            loop.close()

    _scraper_thread = threading.Thread(target=_run, name="zenith-scraper", daemon=True)
    _scraper_thread.start()
    log.info("🚀 Scraper thread started")
    return _scraper_thread
