"""
intraday_collector.py — Zenith 2.0 Intraday OHLCV Collector
RULE: Single source of truth untuk semua intraday data fetch (Yahoo Finance 5m/15m).
      Caller controls all commits — no conn.commit() inside these functions.
"""
import time
import logging
from datetime import datetime, timezone, timedelta

import yfinance as yf

from config import WIB
from core.db import fetchall, execute

log = logging.getLogger("zenith.intraday")

_TIMEFRAME_PERIOD = {"5m": "60d", "15m": "60d"}
_MARKET_OPEN_H  = 9
_MARKET_CLOSE_H = 16

# Throttle config — conservative to avoid Yahoo rate limits
_DELAY_PER_TICKER  = 0.5   # seconds between each ticker
_PAUSE_EVERY_N     = 20    # pause longer every N tickers
_PAUSE_LONG_S      = 10    # seconds for the longer pause
_RETRY_DELAYS      = [5, 15, 30]  # backoff seconds on rate-limit hit


def _get_all_tickers(conn) -> list:
    rows = fetchall(conn, "SELECT DISTINCT ticker FROM eod_summary ORDER BY ticker")
    return [r["ticker"] for r in rows]


def _fetch_and_save(conn, ticker: str, timeframe: str,
                    date_from: str = None, date_to: str = None) -> int:
    """Fetch satu ticker+timeframe dari Yahoo, simpan ke intraday_ohlcv.
    date_from / date_to: filter opsional format YYYY-MM-DD.
    Return jumlah baris baru tersimpan."""
    symbol = f"{ticker}.JK"
    period = _TIMEFRAME_PERIOD.get(timeframe, "60d")

    df = None
    for attempt, backoff in enumerate([0] + _RETRY_DELAYS):
        if backoff:
            log.info("Rate limit hit for %s %s — retrying in %ds (attempt %d)",
                     ticker, timeframe, backoff, attempt + 1)
            time.sleep(backoff)
        try:
            df = yf.download(
                symbol,
                period=period,
                interval=timeframe,
                auto_adjust=False,
                progress=False,
            )
            break  # success
        except Exception as e:
            err = str(e).lower()
            if "429" in err or "rate limit" in err or "too many" in err:
                if attempt < len(_RETRY_DELAYS):
                    continue
            log.warning("yf.download failed ticker=%s tf=%s: %s", ticker, timeframe, e)
            return 0

    if df is None:
        return 0

    if df is None or df.empty:
        return 0

    saved = 0
    for ts, row in df.iterrows():
        try:
            # Konversi timestamp ke WIB
            if hasattr(ts, "tzinfo") and ts.tzinfo is not None:
                dt_wib = ts.astimezone(WIB)
            else:
                dt_wib = ts.replace(tzinfo=timezone.utc).astimezone(WIB)

            # Filter jam bursa IDX: 09:00–16:00 WIB
            if not (_MARKET_OPEN_H <= dt_wib.hour < _MARKET_CLOSE_H):
                continue

            date_str = dt_wib.strftime("%Y-%m-%d")

            # Filter date range jika diberikan
            if date_from and date_str < date_from:
                continue
            if date_to and date_str > date_to:
                continue

            dt_str   = dt_wib.strftime("%Y-%m-%d %H:%M:%S")
            time_str = dt_wib.strftime("%H:%M")

            o = float(row["Open"])   if row["Open"]   is not None else None
            h = float(row["High"])   if row["High"]   is not None else None
            l = float(row["Low"])    if row["Low"]    is not None else None
            c = float(row["Close"])  if row["Close"]  is not None else None
            v = int(row["Volume"])   if row["Volume"] is not None else None

            execute(conn, """
                INSERT INTO intraday_ohlcv
                    (ticker, datetime, date, time, timeframe, open, high, low, close, volume)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (ticker, datetime, timeframe) DO NOTHING
            """, [ticker, dt_str, date_str, time_str, timeframe, o, h, l, c, v])
            saved += 1
        except Exception as e:
            log.debug("intraday row skip ticker=%s: %s", ticker, e)

    return saved


def _collect_batch(conn, tickers: list, timeframes: list,
                   date_from: str = None, date_to: str = None, label: str = "") -> dict:
    """Internal: fetch + save batch of tickers. Shared by all public functions."""
    saved = skipped = 0
    total = len(tickers)
    for i, ticker in enumerate(tickers, 1):
        for tf in timeframes:
            try:
                n = _fetch_and_save(conn, ticker, tf, date_from, date_to)
                saved += n
                if n == 0:
                    skipped += 1
            except Exception as e:
                log.warning("collect failed ticker=%s tf=%s: %s", ticker, tf, e)
                skipped += 1
            time.sleep(_DELAY_PER_TICKER)

        if i % 10 == 0:
            log.info("%s progress: %d/%d tickers (saved=%d)", label, i, total, saved)

        # Longer pause every N tickers to let Yahoo rate limit window reset
        if i % _PAUSE_EVERY_N == 0 and i < total:
            log.info("%s — pausing %ds at ticker %d/%d to avoid rate limit",
                     label, _PAUSE_LONG_S, i, total)
            time.sleep(_PAUSE_LONG_S)

    return {"saved": saved, "skipped": skipped, "tickers": total}


def collect_intraday_for_date(conn, date_str: str, timeframes: list = None) -> dict:
    """Fetch semua tickers untuk tanggal date_str (YYYY-MM-DD). Caller commit."""
    if timeframes is None:
        timeframes = ["5m", "15m"]
    tickers = _get_all_tickers(conn)
    if not tickers:
        log.warning("collect_intraday_for_date: no tickers found")
        return {"saved": 0, "skipped": 0, "tickers": 0}
    result = _collect_batch(conn, tickers, timeframes,
                            date_from=date_str, date_to=date_str,
                            label=f"intraday {date_str}")
    log.info("collect_intraday_for_date %s: %s", date_str, result)
    return result


def collect_intraday_incremental(conn, timeframes: list = None) -> dict:
    """Fetch data intraday hari ini (WIB). Dipanggil dari scheduler harian."""
    if timeframes is None:
        timeframes = ["5m", "15m"]
    today = datetime.now(WIB).strftime("%Y-%m-%d")
    return collect_intraday_for_date(conn, today, timeframes)


def collect_intraday_range(conn, date_from: str, date_to: str,
                           timeframes: list = None) -> dict:
    """Backfill dengan custom date range (YYYY-MM-DD).
    Yahoo tetap fetch 60d, tapi hanya rows dalam range yang disimpan.
    Dijalankan manual via admin panel."""
    if timeframes is None:
        timeframes = ["5m", "15m"]
    tickers = _get_all_tickers(conn)
    if not tickers:
        log.warning("collect_intraday_range: no tickers found")
        return {"saved": 0, "skipped": 0, "tickers": 0}
    result = _collect_batch(conn, tickers, timeframes,
                            date_from=date_from, date_to=date_to,
                            label=f"intraday range {date_from}~{date_to}")
    log.info("collect_intraday_range %s~%s: %s", date_from, date_to, result)
    return result


def collect_intraday_full_backfill(conn, timeframes: list = None) -> dict:
    """Backfill penuh 60 hari ke belakang (tanpa filter tanggal). One-time manual."""
    if timeframes is None:
        timeframes = ["5m", "15m"]
    tickers = _get_all_tickers(conn)
    if not tickers:
        log.warning("collect_intraday_full_backfill: no tickers found")
        return {"saved": 0, "skipped": 0, "tickers": 0}
    result = _collect_batch(conn, tickers, timeframes, label="intraday full backfill")
    log.info("collect_intraday_full_backfill done: %s", result)
    return result
