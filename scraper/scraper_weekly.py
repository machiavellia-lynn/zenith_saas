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
from core.db import get_scraper_db, fetchall
from scraper.scraper_parser import parse_joker_message, parse_mf_message
from scraper.scraper_saver import save_sm_bm_rows, save_mf_rows
from scraper.scraper_daily import (
    get_message_topic_id, ALL_TOPICS, SM_BM_TOPICS,
    TOPIC_LABELS, TOPIC_CHANNELS,
)
from algo.summary_rebuild import rebuild_summary_for_date
from algo.analytics_daily import compute_analytics_for_date
from data.price_fetch import backfill_prices

log = logging.getLogger("zenith.weekly")
log.setLevel(logging.INFO)
log.propagate = False
if not log.handlers:
    h = logging.StreamHandler()
    h.setFormatter(logging.Formatter("[%(asctime)s] WEEKLY %(levelname)s — %(message)s", "%H:%M:%S"))
    log.addHandler(h)

DAYS_BACK = 7


async def run_weekly_backfill(client=None, conn=None, days=DAYS_BACK):
    """Scrape messages from past N days. Returns {scanned, saved}."""
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

    now_wib     = datetime.now(WIB)
    valid_dates = {(now_wib - timedelta(days=i)).strftime("%d-%m-%Y") for i in range(days)}
    date_range  = f"{(now_wib - timedelta(days=days-1)).strftime('%d-%m-%Y')} → {now_wib.strftime('%d-%m-%Y')}"
    log.info(f"🔄 WEEKLY BACKFILL: {days} days ({date_range})")

    total_scanned = total_saved = 0

    for topic_id in ALL_TOPICS:
        label   = TOPIC_LABELS[topic_id]
        channel = TOPIC_CHANNELS[topic_id]
        scanned = saved = consecutive_old = 0

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
                consecutive_old = 0
                msg_id = message.id
                if topic_id in SM_BM_TOPICS:
                    rows = parse_joker_message(message.text, channel)
                    if rows:
                        n = save_sm_bm_rows(conn, msg_id, rows)
                        saved += n
                else:
                    rows = parse_mf_message(message.text, channel)
                    if rows:
                        n = save_mf_rows(conn, msg_id, rows)
                        saved += n
            else:
                consecutive_old += 1
                if consecutive_old > 100:
                    break

            if scanned % 200 == 0:
                log.info(f"  {label}: scanned={scanned}, new={saved}...")

        log.info(f"  {label}: scanned={scanned}, new_rows={saved}")
        total_scanned += scanned
        total_saved   += saved

    # Commit raw messages regardless of whether any were saved
    conn.commit()
    log.info(f"💾 Raw data committed: {total_scanned} scanned, {total_saved} saved")

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
