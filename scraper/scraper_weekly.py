"""
scraper_weekly.py — Zenith 2.0 Weekly Backfill
Scrape messages from past N days. Deduplication via ON CONFLICT DO NOTHING.

Usage:
    python scraper_weekly.py          (CLI, standalone)
    GET /admin/scraper-weekly         (triggered from admin panel)
"""
import asyncio
import re
import os
import logging
from datetime import datetime, timedelta

from config import (
    WIB, TG_API_ID as API_ID, TG_API_HASH as API_HASH,
    TG_SESSION_PATH as SESSION_PATH,
    TG_GROUP_ID as GROUP_ID,
)
from core.db import get_scraper_db, fetchall, transaction
from scraper.scraper_parser import parse_joker_message, parse_mf_message
from scraper.scraper_saver import save_sm_bm_rows, save_mf_rows
from scraper.scraper_daily import (
    get_message_topic_id, ALL_TOPICS, SM_BM_TOPICS,
    TOPIC_LABELS, TOPIC_CHANNELS, _ensure_conn,
)
from algo.summary_rebuild import rebuild_summary_for_date
from algo.analytics_daily import compute_analytics_for_date
from data.price_fetch import backfill_prices

log = logging.getLogger("zenith.weekly")  # inherits zenith parent handler

DAYS_BACK = 7


async def run_weekly_backfill(client=None, conn=None, days=DAYS_BACK, dates=None):
    """Scrape messages from past N days (or explicit dates list). Returns {scanned, saved}."""
    own_client = client is None
    own_conn   = conn is None

    if own_conn:
        conn = get_scraper_db()

    if own_client:
        from telethon import TelegramClient
        client = TelegramClient(SESSION_PATH, API_ID, API_HASH)
        await client.connect()
        if not await client.is_user_authorized():
            log.error("❌ Session not authorized")
            return {"scanned": 0, "saved": 0}
        await client.get_dialogs()

    now_wib = datetime.now(WIB)
    if dates is not None:
        valid_dates = set(dates)
        date_range  = f"{min(dates)} → {max(dates)}"
    else:
        valid_dates = {(now_wib - timedelta(days=i)).strftime("%d-%m-%Y") for i in range(days)}
        date_range  = f"{(now_wib - timedelta(days=days-1)).strftime('%d-%m-%Y')} → {now_wib.strftime('%d-%m-%Y')}"
    log.info(f"🔄 WEEKLY BACKFILL: {len(valid_dates)} dates ({date_range})")

    # Stop iterating once message date is older than the earliest target date.
    # iter_messages goes newest→oldest, so any future date (today's messages)
    # must be skipped — only break when we've gone past the window.
    min_valid_dt = min(datetime.strptime(d, "%d-%m-%Y") for d in valid_dates)

    total_scanned = total_saved = 0

    for topic_id in ALL_TOPICS:
        label   = TOPIC_LABELS[topic_id]
        channel = TOPIC_CHANNELS[topic_id]
        scanned = saved = 0

        conn = _ensure_conn(conn)  # reconnect before each topic's DB work

        async for message in client.iter_messages(GROUP_ID, reply_to=topic_id, limit=None):
            if not message.text:
                continue
            text_clean = message.text.replace("```", "").replace("`", "")
            date_match = re.search(r"(\d{2}-\d{2}-\d{4})", text_clean)
            if not date_match:
                continue

            msg_date = date_match.group(1)
            scanned += 1

            if msg_date in valid_dates:
                msg_id = message.id
                try:
                    if topic_id in SM_BM_TOPICS:
                        rows = parse_joker_message(message.text, channel)
                        if rows:
                            with transaction(conn):
                                n = save_sm_bm_rows(conn, msg_id, rows)
                            saved += n
                    else:
                        rows = parse_mf_message(message.text, channel)
                        if rows:
                            with transaction(conn):
                                n = save_mf_rows(conn, msg_id, rows)
                            saved += n
                except Exception as e:
                    log.warning(f"  ⚠️ {label} msg={msg_id} save failed: {e}")
            else:
                try:
                    if datetime.strptime(msg_date, "%d-%m-%Y") < min_valid_dt:
                        break  # gone past our target window, no more useful messages
                except ValueError:
                    pass

            if scanned % 200 == 0:
                log.info(f"  {label}: scanned={scanned}, new={saved}...")

        log.info(f"  {label}: scanned={scanned}, new_rows={saved}")
        total_scanned += scanned
        total_saved   += saved

    log.info(f"💾 Raw data: {total_scanned} scanned, {total_saved} saved")

    if total_saved > 0:
        dates_sorted = sorted(valid_dates, key=lambda x: datetime.strptime(x, "%d-%m-%Y"))
        log.info(f"📊 Rebuilding summaries for {len(dates_sorted)} dates...")

        for d in dates_sorted:
            try:
                rebuild_summary_for_date(conn, d)
                conn.commit()
            except Exception as e:
                log.error(f"  ❌ Rebuild {d}: {e}")
                conn.rollback()

        # Convert DD-MM-YYYY → YYYY-MM-DD for backfill_prices
        def _to_iso(d):
            dd, mm, yyyy = d.split("-")
            return f"{yyyy}-{mm}-{dd}"

        try:
            prices_count = backfill_prices(conn, date_from=_to_iso(dates_sorted[0]), date_to=_to_iso(dates_sorted[-1]))
            log.info(f"💰 Price backfill result: {prices_count} prices updated")
        except Exception as e:
            log.warning(f"⚠️ Price backfill failed: {e}")

        # Compute analytics for ALL dates in eod_summary that have prices, not just dates_sorted
        # This ensures that dates updated by backfill_prices (including stale data from previous runs)
        # also get their analytics recalculated
        log.info("📊 Computing analytics for all updated dates...")
        # Note: eod_summary.date is DD-MM-YYYY format, so use dates_sorted directly (not converted)
        # Fetch all dates in range, then sort in Python (avoid PostgreSQL DISTINCT + ORDER BY issue)
        all_eod_rows = fetchall(conn, """
            SELECT DISTINCT date FROM eod_summary
            WHERE date IS NOT NULL
        """, [])
        all_eod_dates = sorted([
            r["date"] for r in all_eod_rows
            if datetime.strptime(r["date"], "%d-%m-%Y") >= datetime.strptime(dates_sorted[0], "%d-%m-%Y")
            and datetime.strptime(r["date"], "%d-%m-%Y") <= datetime.strptime(dates_sorted[-1], "%d-%m-%Y")
        ], key=lambda d: datetime.strptime(d, "%d-%m-%Y"))

        analytics_count = 0
        for d in all_eod_dates:
            try:
                n = compute_analytics_for_date(conn, d)
                analytics_count += n
                conn.commit()
            except Exception as e:
                log.error(f"  ❌ Analytics {d}: {e}")
                conn.rollback()

        log.info(f"💰 Analytics recomputed for {len(all_eod_dates)} dates, {analytics_count} tickers updated")

        log.info("✅ Summaries + prices + analytics rebuilt")

    log.info(f"✅ WEEKLY BACKFILL complete: scanned={total_scanned}, new_rows={total_saved}")

    if own_client:
        await client.disconnect()
    if own_conn:
        conn.close()

    return {"scanned": total_scanned, "saved": total_saved}


async def run_weekly_maintenance(client=None, conn=None, intraday_executor=None, intraday_conn_box=None):
    """Full weekly sweep — triggered Monday 03:00 WIB by the scraper loop.
    Covers the 7 calendar days ending yesterday (last week's trading days).
    Steps: Telegram → rebuild → OHLCV → analytics → 15m intraday → BSJP → backtest.
    All steps run unconditionally (not gated on new Telegram rows).

    intraday_executor / intraday_conn_box: the SAME dedicated single-worker executor and
    connection scraper_daily.py's 12:30/15:46 BSJP passes use to offload
    fetch_intraday_15m_yahoo — see that module's _fetch_intraday_15m
    docstring for why calling it inline freezes the caller's event loop.
    Step 3 below does the identical fetch, one request per ticker (up to
    ~800) covering the whole trading-day range; called from the scheduler
    while-loop (as this function normally is), it would starve that loop
    for however long the fetch takes, the same bug just on Mondays instead
    of every trading day.
    Optional and defaulting to None so this function stays callable on its
    own (CLI / an admin route with no scheduler-owned executor to hand in) —
    in that case Step 3 falls back to the old inline blocking call, which is
    fine there since nothing else needs that event loop responsive.
    """
    from data.price_fetch import backfill_price_history_ohlcv, fetch_intraday_15m_yahoo
    from algo.analytics_bsjp import compute_bsjp_for_date
    from algo.algo_backtest import run_backtest

    own_conn = conn is None
    if own_conn:
        conn = get_scraper_db()

    now_wib  = datetime.now(WIB)
    all_7    = [(now_wib - timedelta(days=i)).strftime("%d-%m-%Y") for i in range(1, 8)]
    trading  = sorted(
        [d for d in all_7 if datetime.strptime(d, "%d-%m-%Y").weekday() < 5],
        key=lambda x: datetime.strptime(x, "%d-%m-%Y"),
    )

    def _iso(d):
        dd, mm, yyyy = d.split("-")
        return f"{yyyy}-{mm}-{dd}"

    log.info("📅 Weekly maintenance START — %d trading days: %s → %s",
             len(trading), trading[0], trading[-1])

    # ── Step 1: Telegram backfill ──────────────────────────────────────────
    log.info("  [1/5] Telegram backfill")
    try:
        res = await run_weekly_backfill(client=client, conn=conn, days=7)
        log.info("  Telegram: scanned=%d saved=%d", res["scanned"], res["saved"])
    except Exception as e:
        log.error("  Telegram backfill failed: %s", e)

    # ── Step 2: Rebuild summaries + OHLCV prices + analytics (forced) ─────
    log.info("  [2/5] Rebuild summaries + prices + analytics")
    for d in trading:
        try:
            rebuild_summary_for_date(conn, d)
            conn.commit()
        except Exception as e:
            log.error("  rebuild %s: %s", d, e)
            conn.rollback()

    try:
        backfill_price_history_ohlcv(conn, _iso(trading[0]), _iso(trading[-1]))
        conn.commit()
    except Exception as e:
        log.warning("  price backfill: %s", e)

    for d in trading:
        try:
            compute_analytics_for_date(conn, d)
            conn.commit()
        except Exception as e:
            log.error("  analytics %s: %s", d, e)
            conn.rollback()

    # ── Step 3: 15m intraday backfill ─────────────────────────────────────
    # One request per ticker covers the whole trading-day range (see
    # fetch_intraday_15m_yahoo's docstring) — do NOT loop per day here,
    # that would multiply Yahoo calls (and this step's wall-clock,
    # which matters since it runs inline on intraday_executor's single worker
    # thread) by len(trading) for no benefit.
    log.info("  [3/5] 15m intraday backfill")
    tickers = [r["ticker"] for r in fetchall(conn,
        "SELECT ticker FROM ticker_universe WHERE is_active = TRUE")]
    try:
        if intraday_executor is not None and intraday_conn_box is not None:
            from scraper.scraper_daily import _fetch_intraday_15m
            loop = asyncio.get_running_loop()
            res = await loop.run_in_executor(
                intraday_executor, _fetch_intraday_15m, intraday_conn_box, tickers, trading[0], trading[-1])
        else:
            res = fetch_intraday_15m_yahoo(conn, tickers, trading[0], trading[-1])
            conn.commit()
        log.info("  15m %s → %s: %d rows", trading[0], trading[-1], res.get("rows_inserted", 0))
    except Exception as e:
        log.error("  15m %s → %s: %s", trading[0], trading[-1], e)

    # ── Step 4: BSJP indicators + signals ─────────────────────────────────
    log.info("  [4/5] BSJP indicators + signals")
    for d in trading:
        try:
            compute_bsjp_for_date(conn, _iso(d))
            conn.commit()
        except Exception as e:
            log.error("  bsjp_ind %s: %s", d, e)
            conn.rollback()

    from scraper.scraper_daily import run_bsjp_scan
    for d in trading:
        try:
            n = run_bsjp_scan(conn, date_dmy=d)
            log.info("  bsjp_signals %s: %d signals", d, n)
        except Exception as e:
            log.error("  bsjp_scan %s: %s", d, e)

    # ── Step 5: Full backtest ──────────────────────────────────────────────
    log.info("  [5/5] Full backtest")
    try:
        run_backtest(conn, days=0)
    except Exception as e:
        log.error("  backtest: %s", e)

    if own_conn:
        conn.close()
    log.info("✅ Weekly maintenance DONE")


async def main():
    from telethon import TelegramClient
    conn   = get_scraper_db()
    client = TelegramClient(SESSION_PATH, API_ID, API_HASH)
    async with client:
        log.info("🔗 Connected to Telegram")
        await client.get_dialogs()
        await run_weekly_backfill(client, conn)
    conn.close()


if __name__ == "__main__":
    asyncio.run(main())
