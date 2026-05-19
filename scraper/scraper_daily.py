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
BSJP_HOUR      = 15
BSJP_MINUTE    = 48
BSJP_FINAL_HOUR   = 16
BSJP_FINAL_MINUTE = 30
TOP_N_BSJP     = 15
BSJP_BLACKLIST = {"HATM", "JAST", "CYBR", "AYLS", "VAST", "VTNY"}

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
_backfill_request  = {"days": None, "status": "idle", "result": None}
_rebuild_request   = {"status": "idle", "result": None}
_recompute_request = {"status": "idle", "result": None}
_backtest_request  = {"days": None, "status": "idle", "result": None}
_fix_all_request   = {"status": "idle", "step": None, "date_from": None, "date_to": None, "result": None}
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


# ── BSJP scoring + scan functions ─────────────────────────────────────────────

def _compute_bsjp_score(row: dict, sig: dict) -> float:
    SETUP_WR = {
        "SMA5_BREAKOUT_V13": 0.784,
        "SMA5_PULLBACK_V12": 0.638,
        "BB_PULLBACK":       0.596,
        "SMA5_BREAKOUT_V11": 0.550,
        "POWER_BREAK_V21":   0.520,
        "POWER_BREAK_V22":   0.520,
    }

    def _f(v, d=0.0):
        try: return float(v) if v is not None else d
        except: return d

    sm  = _f(row.get("sm_val"))
    bm  = abs(_f(row.get("bm_val")))
    rsm = sm / (sm + bm) * 100 if (sm + bm) > 0 else 0
    rsm_n = max(0.0, min(1.0, (rsm - 60) / 40))

    sri   = _f(row.get("sri"), 1.2)
    sri_n = max(0.0, min(1.0, (sri - 1.2) / 3.8))

    setup_wr  = SETUP_WR.get(sig["setup"], 0.5)
    close_pos = max(0.0, min(1.0, _f(row.get("close_pos"), 0.5)))

    mf   = _f(row.get("mf_ratio"), 50)
    mf_n = max(0.0, min(1.0, (mf - 50) / 50))

    return round(rsm_n*0.30 + sri_n*0.25 + setup_wr*0.25 + close_pos*0.10 + mf_n*0.10, 4)


async def run_bsjp_scan_pass(conn):
    """Pass 15:48 — generate BSJP signal estimasi, top-15 by score."""
    from algo.algo_bsjp import BSJPAlgo
    import yfinance as yf

    WIB_TZ = timezone(timedelta(hours=7))
    today  = datetime.now(WIB_TZ).strftime("%d-%m-%Y")
    algo   = BSJPAlgo()

    with conn.cursor() as cur:
        cur.execute("""
            SELECT e.*, p.ma5, p.bb_mid, p.bb_lower, p.ma5_price_streak,
                   p.prev_high_break, p.is_sideways, p.daily_value,
                   p.prev_close_below_ma5, p.prev_close_below_bb_lower,
                   p.days_since_near_bb_mid, p.close_pos, p.close AS ph_close
            FROM eod_summary e
            LEFT JOIN price_history p
                ON p.ticker = e.ticker
                AND p.date = TO_CHAR(TO_DATE(e.date,'DD-MM-YYYY') - INTERVAL '1 day','YYYY-MM-DD')
            WHERE e.date = %s AND e.sri IS NOT NULL AND e.sm_val > 0
        """, (today,))
        eod_rows = [dict(r) for r in cur.fetchall()]

    candidates = []
    for row in eod_rows:
        t = row.get("ticker", "")
        if t in BSJP_BLACKLIST:
            continue
        row["price_close"] = row.get("ph_close") or row.get("price_close")
        if not row["price_close"]:
            continue
        sig = algo.signal_detail(t, row)
        if sig:
            candidates.append((t, sig, row))

    if not candidates:
        log.info("[BSJP 15:48] No candidates found.")
        return

    # Fetch live price untuk kandidat saja
    tickers_yf  = [f"{t}.JK" for t, _, _ in candidates]
    live_prices = {}
    try:
        batch = yf.download(tickers_yf, period="1d", interval="1m",
                            auto_adjust=True, progress=False)
        if hasattr(batch.columns, "levels"):
            for t_jk in tickers_yf:
                t = t_jk.replace(".JK", "")
                try:
                    live_prices[t] = float(batch["Close"][t_jk].dropna().iloc[-1])
                except Exception:
                    pass
    except Exception as e:
        log.warning(f"[BSJP 15:48] yfinance error: {e}")

    # Score dan rank semua kandidat
    scored = []
    for ticker, sig_est, row in candidates:
        live_price = live_prices.get(ticker, sig_est["entry"])
        row_live   = dict(row)
        row_live["price_close"] = live_price
        prev = row.get("ph_close") or live_price
        row_live["price_change_pct"] = (live_price - prev) / prev * 100 if prev else 0
        sig_live = algo.signal_detail(ticker, row_live)
        if not sig_live:
            continue
        score = _compute_bsjp_score(row_live, sig_live)
        lot   = int(10_000_000 / live_price)
        scored.append((score, ticker, sig_live, row_live, lot))

    # Sort by score DESC, ambil top-15
    scored.sort(key=lambda x: -x[0])
    top15 = scored[:TOP_N_BSJP]

    now_str = datetime.now(WIB_TZ).isoformat()
    for rank, (score, ticker, sig, row, lot) in enumerate(top15, 1):
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO bsjp_signals
                    (date, ticker, setup, entry_est, tp1, tp2, sl, sl_type,
                     score, day_rank, lot_size, status, computed_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'ESTIMASI',%s)
                ON CONFLICT (date, ticker) DO UPDATE SET
                    setup=EXCLUDED.setup, entry_est=EXCLUDED.entry_est,
                    tp1=EXCLUDED.tp1, tp2=EXCLUDED.tp2, sl=EXCLUDED.sl,
                    sl_type=EXCLUDED.sl_type, score=EXCLUDED.score,
                    day_rank=EXCLUDED.day_rank, lot_size=EXCLUDED.lot_size,
                    status='ESTIMASI', computed_at=EXCLUDED.computed_at
            """, (today, ticker, sig["setup"], round(float(row["price_close"])),
                  sig["tp1"], sig["tp2"], sig["sl"], sig["sl_type"],
                  score, rank, lot, now_str))
        conn.commit()

    log.info(f"[BSJP 15:48] {len(top15)} signals (dari {len(scored)} kandidat) disimpan.")


def run_bsjp_finalize_pass(conn):
    """Pass 16:30 — finalize BSJP signals dengan close actual."""
    from algo.algo_bsjp import BSJPAlgo

    WIB_TZ  = timezone(timedelta(hours=7))
    today   = datetime.now(WIB_TZ).strftime("%d-%m-%Y")
    algo    = BSJPAlgo()
    now_str = datetime.now(WIB_TZ).isoformat()

    with conn.cursor() as cur:
        cur.execute("SELECT ticker FROM bsjp_signals WHERE date=%s AND status='ESTIMASI'", (today,))
        pending = [r['ticker'] for r in cur.fetchall()]

    if not pending:
        return

    with conn.cursor() as cur:
        cur.execute("""
            SELECT e.*, p.ma5, p.bb_mid, p.bb_lower, p.ma5_price_streak,
                   p.prev_high_break, p.is_sideways, p.daily_value,
                   p.prev_close_below_ma5, p.prev_close_below_bb_lower,
                   p.days_since_near_bb_mid, p.close_pos
            FROM eod_summary e
            LEFT JOIN price_history p
                ON p.ticker = e.ticker
                AND p.date = TO_CHAR(TO_DATE(e.date,'DD-MM-YYYY'),'YYYY-MM-DD')
            WHERE e.date = %s AND e.ticker = ANY(%s)
        """, (today, pending))
        eod_map = {r['ticker']: dict(r) for r in cur.fetchall()}

    for ticker in pending:
        row = eod_map.get(ticker)
        if not row:
            _mark_invalid(conn, today, ticker, "data tidak ditemukan setelah recompute", now_str)
            continue

        sig = algo.signal_detail(ticker, row)
        if sig:
            score = _compute_bsjp_score(row, sig)
            lot   = int(10_000_000 / float(row["price_close"]))
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE bsjp_signals SET
                        entry_final=%s, tp1=%s, tp2=%s, sl=%s, sl_type=%s,
                        score=%s, lot_size=%s, status='CONFIRMED', computed_at=%s
                    WHERE date=%s AND ticker=%s
                """, (round(float(row["price_close"])), sig["tp1"], sig["tp2"],
                      sig["sl"], sig["sl_type"], score, lot, now_str, today, ticker))
            conn.commit()
        else:
            reason = _detect_invalid_reason(row, algo)
            _mark_invalid(conn, today, ticker, reason, now_str)

    log.info(f"[BSJP 16:30] Finalize selesai — {len(pending)} signals diproses.")


def _mark_invalid(conn, date, ticker, reason, now_str):
    with conn.cursor() as cur:
        cur.execute("""
            UPDATE bsjp_signals SET status='INVALID', invalid_reason=%s, computed_at=%s
            WHERE date=%s AND ticker=%s
        """, (reason, now_str, date, ticker))
    conn.commit()


def _detect_invalid_reason(row: dict, algo) -> str:
    def _f(v, d=0.0):
        try: return float(v) if v is not None else d
        except: return d

    phase = row.get("phase", "")
    if phase in {"UPTHRUST", "DISTRI"}:
        return f"phase berubah jadi {phase}"
    if _f(row.get("sri")) < algo.MIN_SRI:
        return f"sri {_f(row.get('sri')):.2f} < {algo.MIN_SRI}"
    if _f(row.get("rpr"), 1) > algo.MAX_RPR:
        return f"rpr {_f(row.get('rpr'),1):.2f} > {algo.MAX_RPR}"
    if _f(row.get("mf_ratio")) < algo.MIN_MF_RATIO:
        return f"mf_ratio {_f(row.get('mf_ratio')):.1f} < {algo.MIN_MF_RATIO}"
    sm  = _f(row.get("sm_val"))
    bm  = abs(_f(row.get("bm_val")))
    rsm = sm / (sm + bm) * 100 if (sm + bm) > 0 else 0
    if rsm < algo.MIN_RSM:
        return f"rsm {rsm:.1f}% < {algo.MIN_RSM}%"
    price  = _f(row.get("price_close"))
    ma5    = _f(row.get("ma5"))
    if ma5 and price < ma5:
        return f"close {price} < ma5 {ma5:.0f}"
    bb_mid = _f(row.get("bb_mid"))
    if bb_mid and price < bb_mid:
        return f"close {price} < bb_mid {bb_mid:.0f}"
    return "kondisi setup tidak terpenuhi setelah close final"


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
        await client.get_dialogs()

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
        bsjp_scan_done = bsjp_final_done = False
        last_check_date = None

        while True:
            conn = _ensure_conn(conn)
            now_wib    = datetime.now(WIB)
            today_str  = now_wib.strftime("%Y-%m-%d")

            log.debug(f"⏰ Loop iteration at {now_wib.strftime('%H:%M:%S')}")

            if today_str != last_check_date:
                midday_pass_done = first_pass_done = second_pass_done = backtest_done_today = False
                bsjp_scan_done = bsjp_final_done = False
                last_check_date = today_str

            if not midday_pass_done and (now_wib.hour > MIDDAY_HOUR or (now_wib.hour == MIDDAY_HOUR and now_wib.minute >= MIDDAY_MINUTE)):
                try:
                    log.info("🌤️ Midday pass (12:10)")
                    await run_backfill(client, conn)
                except Exception as e:
                    log.error(f"❌ Midday pass: {e}")
                finally:
                    midday_pass_done = True

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

            # Pass 15:48 — BSJP Scan (ESTIMASI)
            if not bsjp_scan_done and now_wib.hour == BSJP_HOUR and now_wib.minute >= BSJP_MINUTE:
                try:
                    log.info("📊 BSJP scan pass (15:48)")
                    await run_bsjp_scan_pass(conn)
                except Exception as e:
                    log.error(f"❌ BSJP scan pass: {e}")
                finally:
                    bsjp_scan_done = True

            # Pass 16:30 — BSJP Finalize (CONFIRMED/INVALID)
            if second_pass_done and not bsjp_final_done and (
                now_wib.hour > BSJP_FINAL_HOUR or
                (now_wib.hour == BSJP_FINAL_HOUR and now_wib.minute >= BSJP_FINAL_MINUTE)
            ):
                try:
                    log.info("✅ BSJP finalize pass (16:30)")
                    run_bsjp_finalize_pass(conn)
                except Exception as e:
                    log.error(f"❌ BSJP finalize pass: {e}")
                finally:
                    bsjp_final_done = True

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
