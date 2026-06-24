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
log.setLevel(logging.INFO)

_gain_cache      = {}
_gain_cache_lock = threading.Lock()
# Max concurrent Yahoo calls per batch — shared semaphore prevents runaway threads
# across concurrent requests without a persistent module-level thread pool.
_yahoo_sem = threading.Semaphore(10)


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
        with _yahoo_sem:
            gain, price = fetch_gain_range(t, date_from, date_to)
        return t, gain, price

    with ThreadPoolExecutor(max_workers=10) as ex:
        futures = {ex.submit(_fetch_one, t): t for t in to_fetch}
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


def _fetch_close(ticker: str, target_date: str = None):
    """Fetch close for ticker. If target_date (DD-MM-YYYY) given, returns close
    on-or-before that date. Otherwise returns latest close."""
    symbol = f"{ticker}.JK"
    try:
        params = {"interval": "1d", "includeAdjustedClose": "false"}
        target_str = None
        if target_date:
            d = parse_date(target_date)
            params["period1"] = int((datetime(d.year, d.month, d.day, tzinfo=WIB) - timedelta(days=10)).timestamp())
            params["period2"] = int((datetime(d.year, d.month, d.day, tzinfo=WIB) + timedelta(days=2)).timestamp())
            target_str = d.strftime("%Y-%m-%d")
        else:
            params["range"] = "5d"

        resp = requests.get(
            f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}",
            headers=YF_HEADERS, params=params, timeout=8,
        )
        r = resp.json().get("chart", {}).get("result", [None])[0]
        if not r:
            return ticker, None
        timestamps = r.get("timestamp", []) or []
        closes     = r.get("indicators", {}).get("quote", [{}])[0].get("close", []) or []

        if target_str is None:
            valid = [c for c in closes if c and float(c) > 0]
            return ticker, int(round(float(valid[-1]))) if valid else None

        best = None
        for i, ts in enumerate(timestamps):
            c = closes[i] if i < len(closes) else None
            if not c or float(c) <= 0:
                continue
            ds = datetime.fromtimestamp(ts, tz=WIB).strftime("%Y-%m-%d")
            if ds <= target_str:
                best = float(c)
        return ticker, int(round(best)) if best else None
    except Exception:
        return ticker, None


def _fetch_ohlcv_history(ticker: str, date_from: datetime = None, date_to: datetime = None):
    """Fetch daily OHLCV history for a ticker from Yahoo Finance."""
    symbol = f"{ticker}.JK"
    try:
        params = {"interval": "1d", "includeAdjustedClose": "false"}
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
        q       = r.get("indicators", {}).get("quote", [{}])[0]
        opens   = q.get("open",   [])
        highs   = q.get("high",   [])
        lows    = q.get("low",    [])
        closes  = q.get("close",  [])
        volumes = q.get("volume", [])
        rows = []
        for i, ts in enumerate(timestamps):
            c = closes[i] if i < len(closes) else None
            if not c:
                continue
            rows.append({
                "date":   datetime.fromtimestamp(ts, tz=WIB).strftime("%Y-%m-%d"),
                "open":   round(float(opens[i]),   0) if i < len(opens)   and opens[i]   else None,
                "high":   round(float(highs[i]),   0) if i < len(highs)   and highs[i]   else None,
                "low":    round(float(lows[i]),    0) if i < len(lows)    and lows[i]    else None,
                "close":  round(float(c),          0),
                "volume": int(volumes[i])              if i < len(volumes) and volumes[i] else None,
            })
        return ticker, rows
    except Exception:
        return ticker, []


# Keep old name as alias so existing callers don't break
_fetch_close_history = _fetch_ohlcv_history


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


# DataSectors interval mapping: tf → (ds_interval, days_back)
_DS_TF_MAP = {
    "5m":  ("5m",     10),
    "15m": ("15m",    30),
    "30m": ("30m",    60),
    "1h":  ("1h",    180),
    "1d":  ("daily", 730),
}


def fetch_ohlcv_datasectors(ticker: str, tf: str) -> dict:
    """Fetch OHLCV candles from DataSectors. Returns same format as fetch_ohlcv.
    Intraday datetimes are UTC from DS — converted to WIB before returning.
    Daily uses 'date' field (YYYY-MM-DD) and 'unixdate' (WIB midnight unix)."""
    from config import DS_API_KEY, DS_BASE_URL
    from datetime import timezone as _tz

    if tf not in _DS_TF_MAP:
        return {"error": f"Timeframe tidak valid: {tf}"}

    interval_str, days_back = _DS_TF_MAP[tf]
    now_wib   = datetime.now(WIB)
    date_to   = now_wib.strftime("%Y-%m-%d")
    date_from = (now_wib - timedelta(days=days_back)).strftime("%Y-%m-%d")

    try:
        r = requests.get(
            f"{DS_BASE_URL}/api/chart-saham/{ticker}/{interval_str}",
            headers={"Authorization": f"Bearer {DS_API_KEY}"},
            params={"from": date_from, "to": date_to},
            timeout=20,
        )
        if r.status_code != 200:
            return {"error": f"DataSectors HTTP {r.status_code} for {ticker}"}

        # DS returns nested data.data.data.chartbit (intraday) or data.data.data.chartbit (daily)
        chartbit = (r.json()
                    .get("data", {})
                    .get("data", {})
                    .get("data", {})
                    .get("chartbit", []))

        if not chartbit:
            return {"error": f"No data for {ticker} {tf}"}

        candles = []
        is_daily = (tf == "1d")

        # DS returns newest-first — reverse to oldest-first
        for c in reversed(chartbit):
            try:
                o = c.get("open")
                h = c.get("high")
                l = c.get("low")
                cl = c.get("close")
                if not (o and cl):
                    continue

                if is_daily:
                    dt_wib = datetime.strptime(c["date"], "%Y-%m-%d").replace(tzinfo=WIB)
                    time_val    = int(dt_wib.timestamp())
                    datetime_wib = c["date"]
                else:
                    dt_utc   = datetime.strptime(c["datetime"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=_tz.utc)
                    dt_wib   = dt_utc.astimezone(WIB)
                    time_val    = int(dt_wib.timestamp())
                    datetime_wib = dt_wib.strftime("%Y-%m-%d %H:%M")

                candles.append({
                    "time":         time_val,
                    "open":         int(o),
                    "high":         int(h),
                    "low":          int(l),
                    "close":        int(cl),
                    "volume":       int(c.get("volume") or 0),
                    "datetime_wib": datetime_wib,
                })
            except Exception:
                continue

        if not candles:
            return {"error": f"No valid candles for {ticker} {tf}"}

        return {
            "ticker":     ticker,
            "tf":         tf,
            "candles":    candles,
            "count":      len(candles),
            "name":       ticker,
            "price":      candles[-1]["close"],
            "data_range": f"{candles[0]['datetime_wib']} → {candles[-1]['datetime_wib']} WIB",
        }
    except Exception as e:
        log.warning("fetch_ohlcv_datasectors %s %s: %s", ticker, tf, e)
        return {"error": str(e)}


def enrich_daily_prices(conn, date_str: str) -> int:
    """Fetch close prices for all tickers in eod_summary for a given date.
    Caller is responsible for commit."""
    tickers = [r["ticker"] for r in fetchall(conn, "SELECT DISTINCT ticker FROM eod_summary WHERE date = %s", [date_str])]
    if not tickers:
        return 0

    updated = 0
    with ThreadPoolExecutor(max_workers=15) as ex:
        futures = {ex.submit(_fetch_close, t, date_str): t for t in tickers}
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


def sync_price_history_from_eod(conn, date_str: str) -> int:
    """Copy eod_summary.price_close → price_history for date_str.
    Reuses prices already fetched by enrich_daily_prices — no extra Yahoo call.
    Caller is responsible for commit."""
    date_yyyy = f"{date_str[6:10]}-{date_str[3:5]}-{date_str[:2]}"
    rows = fetchall(conn,
        "SELECT ticker, price_close FROM eod_summary WHERE date = %s AND price_close IS NOT NULL",
        [date_str])
    inserted = 0
    for r in rows:
        try:
            execute(conn, """
                INSERT INTO price_history (date, ticker, close)
                VALUES (%s, %s, %s)
                ON CONFLICT (date, ticker) DO UPDATE SET close = EXCLUDED.close
            """, [date_yyyy, r["ticker"], r["price_close"]])
            inserted += 1
        except Exception as e:
            log.warning("sync_price_history failed ticker=%s: %s", r["ticker"], e)
    log.info("sync_price_history_from_eod %s: %d rows", date_str, inserted)
    return inserted


def backfill_prices(conn, days: int = 30, date_from: str = None, date_to: str = None, delay_ms: int = 0):
    """Backfill price_close in eod_summary for a date range.
    Strategy: 1 Yahoo request per ticker (covers entire date range), parallel via ThreadPoolExecutor.
    Mirrors Zenith 1.0 implementation. delay_ms kept for API compatibility (unused).
    Caller is responsible for commit."""
    try:
        def _to_ddmmyyyy(d):
            if d and len(d) == 10 and d[4] == "-":
                return f"{d[8:]}-{d[5:7]}-{d[:4]}"
            return d

        fmt = "%d-%m-%Y"
        now = datetime.now(WIB)

        if date_from and date_to:
            date_from = _to_ddmmyyyy(date_from)
            date_to   = _to_ddmmyyyy(date_to)
            dt_f = datetime.strptime(date_from, fmt).replace(tzinfo=WIB)
            dt_t = datetime.strptime(date_to,   fmt).replace(tzinfo=WIB)
            log.info(f"💰 PRICE BACKFILL: {date_from} → {date_to}")
            rows = fetchall(conn, "SELECT DISTINCT date FROM eod_summary")
            valid_dates = set()
            for r in rows:
                try:
                    d = datetime.strptime(r["date"], fmt).replace(tzinfo=WIB)
                    if dt_f <= d <= dt_t:
                        valid_dates.add(r["date"])
                except Exception:
                    pass
        else:
            log.info(f"💰 PRICE BACKFILL: last {days} dates")
            all_dates = fetchall(conn, """
                SELECT date FROM (
                    SELECT DISTINCT date FROM eod_summary
                ) t
                ORDER BY TO_DATE(date, 'DD-MM-YYYY') DESC LIMIT %s
            """, [days])
            valid_dates = set(r["date"] for r in all_dates)
            if valid_dates:
                dates_sorted = sorted(valid_dates, key=lambda x: datetime.strptime(x, fmt))
                dt_f = datetime.strptime(dates_sorted[0],  fmt).replace(tzinfo=WIB)
                dt_t = datetime.strptime(dates_sorted[-1], fmt).replace(tzinfo=WIB)
            else:
                dt_f, dt_t = now - timedelta(days=60), now

        if not valid_dates:
            log.warning("  No dates to backfill")
            return 0

        ticker_rows = fetchall(conn,
            "SELECT DISTINCT ticker FROM eod_summary WHERE date = ANY(%s)",
            [list(valid_dates)])
        ticker_list = [r["ticker"] for r in ticker_rows]
        log.info(f"  Tickers: {len(ticker_list)}, Dates: {len(valid_dates)}")

        # 1 Yahoo request per ticker — parallel fetch (matches Zenith 1.0)
        with ThreadPoolExecutor(max_workers=8) as ex:
            results = list(ex.map(lambda t: _fetch_close_history(t, dt_f, dt_t), ticker_list))

        # Convert valid_dates DD-MM-YYYY → YYYY-MM-DD lookup set
        valid_yyyy_mm_dd = {f"{d[6:10]}-{d[3:5]}-{d[:2]}": d for d in valid_dates}

        updated = 0
        for tk, rows in results:
            if not rows:
                continue
            for r in rows:
                yyyy_mm_dd = r["date"]
                close = r["close"]
                if yyyy_mm_dd in valid_yyyy_mm_dd and close:
                    dd_mm_yyyy = valid_yyyy_mm_dd[yyyy_mm_dd]
                    execute(conn, "UPDATE eod_summary SET price_close = %s WHERE date = %s AND ticker = %s",
                            [int(close), dd_mm_yyyy, tk])
                    updated += 1
        conn.commit()

        log.info(f"✅ PRICE BACKFILL done: {updated} cells updated for {len(ticker_list)} tickers")
        return updated
    except Exception as e:
        log.error(f"❌ Backfill prices failed: {e}")
        return 0


def backfill_price_history_ohlcv(conn, date_from: str = None, date_to: str = None):
    """Backfill price_history with full OHLCV for all active tickers in ticker_universe.
    date_from / date_to in DD-MM-YYYY or None for last 210 days.
    Caller is responsible for commit."""
    tickers = [r["ticker"] for r in fetchall(conn,
        "SELECT ticker FROM ticker_universe WHERE is_active = TRUE")]
    if not tickers:
        tickers = [r["ticker"] for r in fetchall(conn, "SELECT DISTINCT ticker FROM eod_summary")]
    now     = datetime.now(WIB)

    if date_from and date_to:
        fmt    = "%d-%m-%Y"
        dt_f   = datetime.strptime(date_from, fmt).replace(tzinfo=WIB) - timedelta(days=3)
        dt_t   = datetime.strptime(date_to,   fmt).replace(tzinfo=WIB) + timedelta(days=1)
        log.info("Backfilling price_history OHLCV %s → %s for %d tickers", date_from, date_to, len(tickers))
    else:
        dt_f   = now - timedelta(days=210)
        dt_t   = now
        log.info("Backfilling price_history OHLCV 210d for %d tickers", len(tickers))

    with ThreadPoolExecutor(max_workers=8) as ex:
        results = list(ex.map(lambda t: _fetch_ohlcv_history(t, dt_f, dt_t), tickers))

    inserted = 0
    for ticker, rows in results:
        for r in rows:
            try:
                execute(conn, """
                    INSERT INTO price_history (date, ticker, open, high, low, close, volume)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (date, ticker) DO UPDATE SET
                        open = EXCLUDED.open, high = EXCLUDED.high,
                        low  = EXCLUDED.low,  close = EXCLUDED.close,
                        volume = EXCLUDED.volume
                """, [r["date"], ticker, r["open"], r["high"], r["low"], r["close"], r["volume"]])
                inserted += 1
            except Exception as e:
                log.warning("price_history insert fail ticker=%s date=%s: %s", ticker, r["date"], e)
    log.info("price_history OHLCV backfill done: %d rows for %d tickers", inserted, len(tickers))
    return inserted


def backfill_price_history_200d(conn):
    """Alias kept for backward compatibility."""
    return backfill_price_history_ohlcv(conn)


def enrich_daily_ohlcv(conn, date_str: str) -> int:
    """Fetch today's OHLCV from Yahoo for all active tickers in ticker_universe.
    Stores full OHLCV in price_history AND updates eod_summary.price_close when row exists.
    Single Yahoo call per ticker.
    Caller is responsible for commit."""
    tickers = [r["ticker"] for r in fetchall(conn,
        "SELECT ticker FROM ticker_universe WHERE is_active = TRUE")]
    if not tickers:
        # Fallback for first run before ticker_universe is seeded
        tickers = [r["ticker"] for r in fetchall(conn,
            "SELECT DISTINCT ticker FROM eod_summary WHERE date = %s", [date_str])]
    if not tickers:
        return 0

    date_yyyy = f"{date_str[6:10]}-{date_str[3:5]}-{date_str[:2]}"
    target_dt = datetime.strptime(date_yyyy, "%Y-%m-%d").replace(tzinfo=WIB)
    dt_f = target_dt - timedelta(days=5)
    dt_t = target_dt + timedelta(days=2)

    with ThreadPoolExecutor(max_workers=15) as ex:
        results = list(ex.map(lambda t: _fetch_ohlcv_history(t, dt_f, dt_t), tickers))

    updated = 0
    for ticker, rows in results:
        best = None
        for r in rows:
            if r["date"] <= date_yyyy:
                best = r
        if not best:
            continue
        try:
            execute(conn, """
                INSERT INTO price_history (date, ticker, open, high, low, close, volume)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (date, ticker) DO UPDATE SET
                    open = EXCLUDED.open, high = EXCLUDED.high,
                    low  = EXCLUDED.low,  close = EXCLUDED.close,
                    volume = EXCLUDED.volume
            """, [best["date"], ticker, best["open"], best["high"], best["low"], best["close"], best["volume"]])
            # Only update eod_summary if a Telegram row exists for this date
            execute(conn,
                "UPDATE eod_summary SET price_close = %s WHERE date = %s AND ticker = %s",
                [best["close"], date_str, ticker])
            updated += 1
        except Exception as e:
            log.warning("enrich_daily_ohlcv failed ticker=%s: %s", ticker, e)

    log.info("enrich_daily_ohlcv %s: %d tickers updated", date_str, updated)
    return updated


def sync_eod_prices_from_history(conn, date_from: str = None, date_to: str = None) -> int:
    """Copy price_history.close → eod_summary.price_close for a date range (no Yahoo call).
    date_from / date_to in DD-MM-YYYY. None = all dates.
    Caller is responsible for commit."""
    if date_from and date_to:
        rows = execute(conn, """
            UPDATE eod_summary e
            SET price_close = ph.close
            FROM price_history ph
            WHERE ph.ticker = e.ticker
              AND ph.date = TO_CHAR(TO_DATE(e.date, 'DD-MM-YYYY'), 'YYYY-MM-DD')
              AND ph.close IS NOT NULL
              AND TO_DATE(e.date, 'DD-MM-YYYY') BETWEEN TO_DATE(%s, 'DD-MM-YYYY') AND TO_DATE(%s, 'DD-MM-YYYY')
        """, [date_from, date_to])
    else:
        rows = execute(conn, """
            UPDATE eod_summary e
            SET price_close = ph.close
            FROM price_history ph
            WHERE ph.ticker = e.ticker
              AND ph.date = TO_CHAR(TO_DATE(e.date, 'DD-MM-YYYY'), 'YYYY-MM-DD')
              AND ph.close IS NOT NULL
        """)
    updated = rows if isinstance(rows, int) else 0
    log.info("sync_eod_prices_from_history: %s rows updated", updated)
    return updated


def _fetch_ohlcv_intraday_15m(ticker: str, dt_f: datetime, dt_t: datetime):
    """Fetch 15m OHLCV for ticker. Yahoo allows max ~60 days back for 15m interval.
    Returns (ticker, rows) where rows are dicts with datetime (WIB), OHLCV."""
    symbol = f"{ticker}.JK"
    try:
        resp = requests.get(
            f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}",
            headers=YF_HEADERS,
            params={
                "interval": "15m",
                "period1": int(dt_f.timestamp()),
                "period2": int(dt_t.timestamp()),
                "includePrePost": "false",
                "includeAdjustedClose": "false",
            },
            timeout=15,
        )
        r = resp.json().get("chart", {}).get("result", [None])[0]
        if not r:
            return ticker, []
        timestamps = r.get("timestamp", [])
        q       = r.get("indicators", {}).get("quote", [{}])[0]
        opens   = q.get("open",   [])
        highs   = q.get("high",   [])
        lows    = q.get("low",    [])
        closes  = q.get("close",  [])
        volumes = q.get("volume", [])
        rows = []
        for i, ts in enumerate(timestamps):
            c = closes[i] if i < len(closes) else None
            if not c:
                continue
            dt_wib = datetime.fromtimestamp(ts, tz=WIB)
            rows.append({
                "datetime": dt_wib.strftime("%Y-%m-%d %H:%M"),
                "open":   round(float(opens[i]),  0) if i < len(opens)  and opens[i]  else None,
                "high":   round(float(highs[i]),  0) if i < len(highs)  and highs[i]  else None,
                "low":    round(float(lows[i]),   0) if i < len(lows)   and lows[i]   else None,
                "close":  round(float(c),         0),
                "volume": int(volumes[i])             if i < len(volumes) and volumes[i] else None,
            })
        return ticker, rows
    except Exception:
        return ticker, []


def backfill_intraday_15m(conn, date_from: str, date_to: str) -> dict:
    """Fetch and store 15m OHLCV candles for all active tickers in ticker_universe.
    date_from / date_to in DD-MM-YYYY. Yahoo allows max ~60 days back.
    Caller is responsible for commit."""
    tickers = [r["ticker"] for r in fetchall(conn,
        "SELECT ticker FROM ticker_universe WHERE is_active = TRUE")]
    if not tickers:
        tickers = [r["ticker"] for r in fetchall(conn, "SELECT DISTINCT ticker FROM eod_summary")]
    if not tickers:
        return {"ok": False, "error": "No tickers found"}

    fmt  = "%d-%m-%Y"
    dt_f = datetime.strptime(date_from, fmt).replace(tzinfo=WIB)
    dt_t = datetime.strptime(date_to,   fmt).replace(tzinfo=WIB) + timedelta(days=1)

    log.info("backfill_intraday_15m %s → %s for %d tickers", date_from, date_to, len(tickers))

    with ThreadPoolExecutor(max_workers=4) as ex:
        results = list(ex.map(lambda t: _fetch_ohlcv_intraday_15m(t, dt_f, dt_t), tickers))

    inserted = 0
    skipped  = 0
    skipped_tickers = []
    for ticker, rows in results:
        if not rows:
            skipped += 1
            skipped_tickers.append(ticker)
            continue
        for r in rows:
            try:
                execute(conn, """
                    INSERT INTO price_history_15m (datetime, ticker, open, high, low, close, volume)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (datetime, ticker) DO UPDATE SET
                        open = EXCLUDED.open, high = EXCLUDED.high,
                        low  = EXCLUDED.low,  close = EXCLUDED.close,
                        volume = EXCLUDED.volume
                """, [r["datetime"], ticker, r["open"], r["high"], r["low"], r["close"], r["volume"]])
                inserted += 1
            except Exception as e:
                log.warning("15m insert fail ticker=%s dt=%s: %s", ticker, r["datetime"], e)

    log.info("backfill_intraday_15m done: %d rows, %d tickers skipped: %s",
             inserted, skipped, ", ".join(skipped_tickers[:20]) if skipped_tickers else "none")
    return {
        "ok": True,
        "tickers": len(tickers),
        "tickers_skipped": skipped,
        "skipped_list": skipped_tickers,
        "rows_inserted": inserted,
        "date_from": date_from,
        "date_to": date_to,
    }


def fetch_intraday_15m_datasectors(conn, tickers: list, date_from: str, date_to: str = None, progress_cb=None) -> dict:
    """Fetch 15m OHLCV from DataSectors for given tickers.
    date_from / date_to in DD-MM-YYYY. date_to defaults to date_from (single day).
    Supports multi-day ranges — one request per ticker covers the full range.
    Rate-limited to 1 req/sec. Converts UTC→WIB before storing.
    progress_cb(done, total, current_ticker, inserted, failed) — called per ticker.
    Caller is responsible for commit."""
    from config import DS_API_KEY, DS_BASE_URL
    from datetime import timezone as _tz

    if not DS_API_KEY:
        log.error("fetch_intraday_15m_datasectors: DATASECTORS_API_KEY not set")
        return {"ok": False, "error": "DS_API_KEY not set"}

    if not tickers:
        return {"ok": True, "tickers": 0, "rows_inserted": 0, "failed_count": 0}

    def _to_ymd(dmy: str) -> str:
        d, m, y = dmy.split("-")
        return f"{y}-{m}-{d}"

    date_ymd_from = _to_ymd(date_from)
    date_ymd_to   = _to_ymd(date_to) if date_to else date_ymd_from
    headers       = {"Authorization": f"Bearer {DS_API_KEY}"}
    inserted      = 0
    failed        = []

    for i, ticker in enumerate(tickers):
        if i > 0:
            time.sleep(1)
        try:
            r = requests.get(
                f"{DS_BASE_URL}/api/chart-saham/{ticker}/15m",
                headers=headers,
                params={"from": date_ymd_from, "to": date_ymd_to},
                timeout=20,
            )
            if r.status_code == 500:
                time.sleep(3)
                r = requests.get(
                    f"{DS_BASE_URL}/api/chart-saham/{ticker}/15m",
                    headers=headers,
                    params={"from": date_ymd_from, "to": date_ymd_to},
                    timeout=20,
                )
            if r.status_code != 200:
                log.warning("DS 15m %s: HTTP %s", ticker, r.status_code)
                failed.append(ticker)
                continue

            candles = (r.json()
                       .get("data", {})
                       .get("data", {})
                       .get("data", {})
                       .get("chartbit", []))

            for c in candles:
                # Skip candles with missing price data to avoid aborted transaction state
                if not (c.get("open") and c.get("close")):
                    continue
                try:
                    raw_dt = c.get("datetime", "")
                    try:
                        dt_utc = datetime.strptime(raw_dt, "%Y-%m-%d %H:%M:%S").replace(tzinfo=_tz.utc)
                    except ValueError:
                        dt_utc = datetime.strptime(raw_dt[:16], "%Y-%m-%d %H:%M").replace(tzinfo=_tz.utc)
                    # Store without seconds — all queries use RIGHT(datetime,5)='15:45' pattern
                    dt_wib = dt_utc.astimezone(WIB).strftime("%Y-%m-%d %H:%M")
                    vol    = int(c.get("volume") or 0)
                    execute(conn, """
                        INSERT INTO price_history_15m (datetime, ticker, open, high, low, close, volume)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (datetime, ticker) DO UPDATE SET
                            open = EXCLUDED.open, high = EXCLUDED.high,
                            low  = EXCLUDED.low,  close = EXCLUDED.close,
                            volume = EXCLUDED.volume
                    """, [dt_wib, ticker, c["open"], c["high"], c["low"], c["close"], vol])
                    inserted += 1
                except Exception as e:
                    log.warning("DS 15m insert fail ticker=%s dt=%s: %s", ticker, c.get("datetime"), e)
                    try:
                        conn.rollback()
                    except Exception:
                        pass

        except Exception as e:
            log.warning("DS 15m fetch fail ticker=%s: %s", ticker, e)
            failed.append(ticker)

        if progress_cb:
            try:
                progress_cb(i + 1, len(tickers), ticker, inserted, len(failed))
            except Exception:
                pass

    log.info("fetch_intraday_15m_datasectors %s→%s: %d rows, %d tickers, %d failed",
             date_from, date_to or date_from, inserted, len(tickers), len(failed))
    return {
        "ok":            True,
        "tickers":       len(tickers),
        "rows_inserted": inserted,
        "failed_count":  len(failed),
        "failed":        failed[:20],
    }


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
