"""
price_fetch.py — Zenith 2.0 Price Data Layer
RULE: Single source of truth for all external price API calls (Yahoo Finance).
      No other file may hit price APIs directly.
      Caller controls all commits — no conn.commit() inside these functions.
"""
import time
import threading
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta

import requests

from config import WIB, YF_HEADERS, GAIN_CACHE_TTL
from core.utils import parse_date
from core.db import fetchall, execute, get_db

log = logging.getLogger("zenith.price")

GAIN_EXECUTOR = ThreadPoolExecutor(max_workers=10)

_gain_cache      = {}
_gain_cache_lock = threading.Lock()


def fetch_gain_range(ticker: str, date_from: str, date_to: str):
    """
    Calculate % price change from date_from to date_to.
    Single day  → close vs previous close.
    Multi day   → close date_to vs close date_from.
    Returns (gain_pct, price_int) or (None, None) on failure.
    """
    symbol = f"{ticker}.JK"
    try:
        d0 = parse_date(date_from)
        d1 = parse_date(date_to)
        p1 = int((datetime(d0.year, d0.month, d0.day, tzinfo=WIB) - timedelta(days=10)).timestamp())
        p2 = int((datetime(d1.year, d1.month, d1.day, tzinfo=WIB) + timedelta(days=3)).timestamp())

        resp = requests.get(
            f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}",
            headers=YF_HEADERS,
            params={"interval": "1d", "period1": p1, "period2": p2, "includeAdjustedClose": "false"},
            timeout=10,
        )
        data   = resp.json()
        result = data.get("chart", {}).get("result")
        if not result:
            return None, None

        r          = result[0]
        timestamps = r.get("timestamp", [])
        quote      = r.get("indicators", {}).get("quote", [{}])[0]
        closes     = quote.get("close", [])

        candles = []
        for i, ts in enumerate(timestamps):
            c = closes[i] if i < len(closes) else None
            if not c or float(c) <= 0:
                continue
            dt_wib = datetime.fromtimestamp(ts, tz=WIB)
            candles.append((dt_wib.strftime("%Y-%m-%d"), float(c)))

        if not candles:
            return None, None

        d0_str = d0.strftime("%Y-%m-%d")
        d1_str = d1.strftime("%Y-%m-%d")

        def find_close_on_or_before(target_str):
            best = None
            for date_str, close in candles:
                if date_str <= target_str:
                    best = (date_str, close)
            return best

        result_d1 = find_close_on_or_before(d1_str)
        if not result_d1:
            return None, None

        close_d1 = result_d1[1]
        price    = int(round(close_d1))

        if d0 == d1:
            idx = next((i for i, (ds, _) in enumerate(candles) if ds == result_d1[0]), None)
            if idx is not None and idx > 0:
                close_prev = candles[idx - 1][1]
                gain = round((close_d1 - close_prev) / close_prev * 100, 2)
                return gain, price
            return None, price
        else:
            result_d0 = find_close_on_or_before(d0_str)
            if not result_d0 or result_d0[1] <= 0:
                return None, price
            gain = round((close_d1 - result_d0[1]) / result_d0[1] * 100, 2)
            return gain, price

    except Exception as e:
        log.debug("fetch_gain_range %s: %s", ticker, e)
        return None, None


def get_gains_batch(tickers: list, date_from: str, date_to: str) -> dict:
    """Parallel batch gain fetch with in-memory cache."""
    now      = time.time()
    result   = {}
    to_fetch = []

    with _gain_cache_lock:
        for t in tickers:
            key    = f"{t}|{date_from}|{date_to}"
            cached = _gain_cache.get(key)
            if cached and (now - cached["ts"]) < GAIN_CACHE_TTL:
                result[t] = {"gain": cached["gain"], "price": cached["price"]}
            else:
                to_fetch.append(t)

    if not to_fetch:
        return result

    def _fetch_one(t):
        gain, price = fetch_gain_range(t, date_from, date_to)
        return t, gain, price

    futures = {GAIN_EXECUTOR.submit(_fetch_one, t): t for t in to_fetch}
    for future in as_completed(futures, timeout=30):
        try:
            t, gain, price = future.result()
            key = f"{t}|{date_from}|{date_to}"
            with _gain_cache_lock:
                _gain_cache[key] = {"gain": gain, "price": price, "ts": time.time()}
            result[t] = {"gain": gain, "price": price}
        except Exception:
            t = futures[future]
            result[t] = {"gain": None, "price": None}

    return result


def _fetch_close(ticker: str):
    """Fetch latest close price for a single ticker."""
    symbol = f"{ticker}.JK"
    try:
        resp = requests.get(
            f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}",
            headers=YF_HEADERS,
            params={"interval": "1d", "range": "5d"},
            timeout=8,
        )
        r = resp.json().get("chart", {}).get("result", [None])[0]
        if not r:
            return ticker, None
        closes = r.get("indicators", {}).get("quote", [{}])[0].get("close", [])
        closes = [c for c in closes if c]
        return ticker, round(closes[-1], 0) if closes else None
    except Exception:
        return ticker, None


def _fetch_close_history(ticker: str, date_from: datetime = None, date_to: datetime = None):
    """Fetch daily close history for a ticker."""
    symbol = f"{ticker}.JK"
    try:
        params = {"interval": "1d"}
        if date_from and date_to:
            params["period1"] = int(date_from.timestamp())
            params["period2"] = int(date_to.timestamp())
        else:
            params["range"] = "1y"
        resp = requests.get(
            f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}",
            headers=YF_HEADERS,
            params=params,
            timeout=10,
        )
        r = resp.json().get("chart", {}).get("result", [None])[0]
        if not r:
            return ticker, []
        timestamps = r.get("timestamp", [])
        q          = r.get("indicators", {}).get("quote", [{}])[0]
        closes     = q.get("close", [])
        rows = []
        for i, ts in enumerate(timestamps):
            c = closes[i] if i < len(closes) else None
            if c:
                dt = datetime.fromtimestamp(ts, tz=WIB).strftime("%Y-%m-%d")
                rows.append({"date": dt, "close": round(float(c), 0)})
        return ticker, rows
    except Exception:
        return ticker, []


def fetch_ohlcv(ticker: str, tf: str, interval_map: dict) -> dict:
    """Fetch OHLCV candles from Yahoo Finance. Returns dict with candles list."""
    from config import WIB
    from datetime import datetime, timezone, timedelta
    if tf not in interval_map:
        return {"error": f"Timeframe tidak valid: {tf}"}

    p      = interval_map[tf]
    symbol = f"{ticker}.JK"
    now    = datetime.now(timezone.utc)
    period2 = int(now.timestamp())
    period1 = 0 if p["days"] >= 9999 else int((now - timedelta(days=p["days"])).timestamp())

    try:
        resp = requests.get(
            f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}",
            headers=YF_HEADERS,
            params={"interval": p["interval"], "period1": period1, "period2": period2,
                    "includePrePost": "false", "includeAdjustedClose": "false"},
            timeout=20,
        )
        data   = resp.json()
        result = data.get("chart", {}).get("result")
        if not result:
            err = data.get("chart", {}).get("error", {})
            return {"error": err.get("description", f"No data for {symbol}")}

        r          = result[0]
        timestamps = r.get("timestamp", [])
        quote      = r.get("indicators", {}).get("quote", [{}])[0]
        opens   = quote.get("open",   [])
        highs   = quote.get("high",   [])
        lows    = quote.get("low",    [])
        closes  = quote.get("close",  [])
        volumes = quote.get("volume", [])

        candles_map = {}
        for i, ts in enumerate(timestamps):
            try:
                o = opens[i]  if i < len(opens)   else None
                h = highs[i]  if i < len(highs)   else None
                l = lows[i]   if i < len(lows)    else None
                c = closes[i] if i < len(closes)  else None
                v = volumes[i] if i < len(volumes) else 0
                if None in (o, h, l, c) or any(x <= 0 for x in (o, h, l, c)):
                    continue
                dt_wib = datetime.fromtimestamp(ts, tz=WIB)
                wib_ts = ts + (7 * 3600)
                candle = {
                    "time":         wib_ts,
                    "open":         int(round(float(o))),
                    "high":         int(round(float(h))),
                    "low":          int(round(float(l))),
                    "close":        int(round(float(c))),
                    "volume":       int(v) if v else 0,
                    "datetime_wib": dt_wib.strftime("%Y-%m-%d %H:%M"),
                }
                key = dt_wib.strftime("%Y-%m-%d") if p["interval"] == "1d" else wib_ts
                candles_map[key] = candle
            except Exception:
                continue

        candles   = sorted(candles_map.values(), key=lambda x: x["time"])
        meta      = r.get("meta", {})
        price_raw = meta.get("regularMarketPrice")
        return {
            "ticker":     ticker,
            "symbol":     symbol,
            "tf":         tf,
            "candles":    candles,
            "count":      len(candles),
            "name":       meta.get("longName") or meta.get("shortName") or ticker,
            "price":      int(round(float(price_raw))) if price_raw else None,
            "data_range": f"{candles[0]['datetime_wib']} → {candles[-1]['datetime_wib']} WIB" if candles else "",
        }
    except Exception as e:
        log.warning("fetch_ohlcv %s %s: %s", ticker, tf, e)
        return {"error": str(e)}


def enrich_daily_prices(conn, date_str: str) -> int:
    """Fetch close prices for all tickers in eod_summary for a given date.
    Caller is responsible for commit."""
    tickers = [r["ticker"] for r in fetchall(conn, "SELECT DISTINCT ticker FROM eod_summary WHERE date = %s", [date_str])]
    if not tickers:
        return 0

    updated = 0
    with ThreadPoolExecutor(max_workers=15) as ex:
        futures = {ex.submit(_fetch_close, t): t for t in tickers}
        for fut in as_completed(futures, timeout=120):
            try:
                ticker, close = fut.result()
                if close:
                    execute(conn, "UPDATE eod_summary SET price_close = %s WHERE date = %s AND ticker = %s",
                            [close, date_str, ticker])
                    updated += 1
            except Exception as e:
                log.warning("enrich_daily_prices failed ticker=%s date=%s: %s", futures[fut], date_str, e)
    return updated


def backfill_prices(conn, days: int = 30, date_from: str = None, date_to: str = None, delay_ms: int = 500):
    """Backfill price_close in eod_summary for a date range.
    Accepts both DD-MM-YYYY and YYYY-MM-DD formats for date_from/date_to.
    delay_ms: sleep between dates to avoid Yahoo rate limit.
    Caller is responsible for commit."""
    try:
        # Convert YYYY-MM-DD to DD-MM-YYYY if needed (eod_summary stores DD-MM-YYYY)
        def _to_ddmmyyyy(d):
            if d and len(d) == 10 and d[4] == "-":  # YYYY-MM-DD format
                return f"{d[8:]}-{d[5:7]}-{d[:4]}"
            return d

        if date_from and date_to:
            date_from = _to_ddmmyyyy(date_from)
            date_to = _to_ddmmyyyy(date_to)
            log.info(f"💰 Backfill prices: {date_from} → {date_to}")
            rows = fetchall(conn, "SELECT DISTINCT date FROM eod_summary WHERE date >= %s AND date <= %s ORDER BY date", [date_from, date_to])
        else:
            log.info(f"💰 Backfill prices: last {days} days")
            rows = fetchall(conn, "SELECT DISTINCT date FROM eod_summary ORDER BY date DESC LIMIT %s", [days])

        if not rows:
            log.warning("⚠️ No dates found in eod_summary for backfill")
            return

        log.info(f"  Processing {len(rows)} dates...")
        for i, r in enumerate(rows, 1):
            try:
                enrich_daily_prices(conn, r["date"])
                conn.commit()
                log.debug(f"  [{i}/{len(rows)}] {r['date']} ✓")
            except Exception as e:
                log.error(f"  ❌ {r['date']}: {e}")
            if delay_ms > 0:
                time.sleep(delay_ms / 1000)
        log.info(f"✅ Backfill prices complete: {len(rows)} dates")
    except Exception as e:
        log.error(f"❌ Backfill prices failed: {e}")


def backfill_price_history_200d(conn):
    """Backfill price_history table with 200 days of closes per ticker.
    Caller is responsible for commit."""
    tickers = [r["ticker"] for r in fetchall(conn, "SELECT DISTINCT ticker FROM eod_summary")]
    cutoff  = datetime.now(WIB) - timedelta(days=210)
    log.info("Backfilling price_history for %d tickers since %s", len(tickers), cutoff.date())

    for ticker in tickers:
        _, rows = _fetch_close_history(ticker, date_from=cutoff, date_to=datetime.now(WIB))
        for r in rows:
            try:
                execute(conn, """
                    INSERT INTO price_history (date, ticker, close)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (date, ticker) DO NOTHING
                """, [r["date"], ticker, r["close"]])
            except Exception as e:
                log.warning("price_history insert fail ticker=%s date=%s: %s", ticker, r["date"], e)


def fetch_all_gains_to_db(conn, date_str: str, delay_ms: int = 333):
    """Fetch gains for all tickers in eod_summary for date_str and write to DB.
    Caller is responsible for commit."""
    tickers = [r["ticker"] for r in fetchall(conn, "SELECT DISTINCT ticker FROM eod_summary WHERE date = %s", [date_str])]
    for t in tickers:
        gain, price = fetch_gain_range(t, date_str, date_str)
        if price:
            execute(conn, """
                UPDATE eod_summary
                SET price_close = %s, price_change_pct = %s
                WHERE date = %s AND ticker = %s
            """, [price, gain, date_str, t])
        time.sleep(delay_ms / 1000)
