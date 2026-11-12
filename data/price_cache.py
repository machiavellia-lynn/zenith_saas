"""
price_cache.py — Server-side live price cache.
One background thread refreshes every 30s during market hours.
- IHSG index from Yahoo single quote
- All IDX stocks from Yahoo batch quote (/v7/finance/quote, 100 per request)
All routes read from shared dicts — Yahoo cost stays flat regardless of user count.
"""
import threading
import time
import logging
import requests
from datetime import datetime

from config import WIB, YF_HEADERS, YF_PROXIES, SECTORS
from core.cache import TTLCache

log = logging.getLogger("zenith.price_cache")

# ── IHSG cache ─────────────────────────────────────────────────────────────────
_ihsg_cache: dict = {"price": None, "gain_pct": None, "updated_at": None}
_ihsg_lock = threading.Lock()

# ── Stock cache ────────────────────────────────────────────────────────────────
_ALL_TICKERS = sorted({t for tl in SECTORS.values() for t in tl})
_stock_cache: dict = {}   # {ticker: {price, gain_pct}}
_stock_lock = threading.Lock()


# ── Helpers ────────────────────────────────────────────────────────────────────

def _is_market_open() -> bool:
    """Mon–Fri 09:00–16:15 WIB."""
    now = datetime.now(WIB)
    if now.weekday() >= 5:
        return False
    mins = now.hour * 60 + now.minute
    return 540 <= mins <= 975  # 09:00 = 540, 16:15 = 975


# ── IHSG ───────────────────────────────────────────────────────────────────────

def _fetch_ihsg() -> dict:
    try:
        resp = requests.get(
            "https://query1.finance.yahoo.com/v8/finance/chart/%5EJKSE",
            headers=YF_HEADERS, proxies=YF_PROXIES,
            params={"interval": "1d", "range": "5d"},
            timeout=5,
        )
        result = resp.json().get("chart", {}).get("result", [None])[0]
        if not result:
            return {"price": None, "gain_pct": None}

        meta   = result.get("meta", {})
        price  = meta.get("regularMarketPrice")
        closes = result.get("indicators", {}).get("quote", [{}])[0].get("close", []) or []
        valid_closes = [c for c in closes if c and float(c) > 0]
        prev = float(valid_closes[-2]) if len(valid_closes) >= 2 else meta.get("previousClose")

        gain_pct = None
        if price and prev and prev > 0:
            gain_pct = round((float(price) - prev) / prev * 100, 2)

        return {
            "price":    round(float(price), 2) if price else None,
            "gain_pct": gain_pct,
        }
    except Exception as e:
        log.warning("IHSG fetch failed: %s", e)
        return {"price": None, "gain_pct": None}


def _refresh_ihsg():
    data = _fetch_ihsg()
    with _ihsg_lock:
        _ihsg_cache["price"]      = data["price"]
        _ihsg_cache["gain_pct"]   = data["gain_pct"]
        _ihsg_cache["updated_at"] = datetime.now(WIB).isoformat()


def get_cached_ihsg() -> dict:
    with _ihsg_lock:
        return dict(_ihsg_cache)


_ihsg_hist = TTLCache()


def get_ihsg_history(range_: str = "2y") -> dict:
    """Daily IHSG closes as {DD-MM-YYYY: close}, for the /portfolio benchmark line.

    Cached for 1 h: this is EOD data that changes once a day, while /portfolio
    re-requests it on every date-range change. Returns {} on failure — the
    benchmark line is decorative, so it must never break the portfolio response.
    """
    cached = _ihsg_hist.get(range_)
    if cached is not None:
        return cached

    out = {}
    try:
        resp = requests.get(
            "https://query1.finance.yahoo.com/v8/finance/chart/%5EJKSE",
            headers=YF_HEADERS, proxies=YF_PROXIES,
            params={"interval": "1d", "range": range_},
            timeout=8,
        )
        result = resp.json().get("chart", {}).get("result", [None])[0] or {}
        stamps = result.get("timestamp") or []
        closes = result.get("indicators", {}).get("quote", [{}])[0].get("close") or []
        for ts, c in zip(stamps, closes):
            if not c:
                continue
            # Yahoo stamps each daily bar at the exchange session open; render it
            # in WIB so the calendar date matches eod_summary's DD-MM-YYYY keys.
            out[datetime.fromtimestamp(ts, WIB).strftime("%d-%m-%Y")] = round(float(c), 2)
    except Exception as e:
        log.warning("IHSG history fetch failed: %s", e)

    # Cache even an empty result, briefly, so a Yahoo outage can't turn every
    # portfolio request into an 8 s timeout.
    _ihsg_hist.set(range_, out, 3600 if out else 120)
    return out


# ── Stocks ─────────────────────────────────────────────────────────────────────

_crumb_lock = threading.Lock()
_yf_auth: dict = {"session": None, "crumb": None, "at": 0.0}
_CRUMB_TTL = 3600


def _yf_session_crumb(force: bool = False):
    """Cookie + crumb pair that /v7/finance/quote now requires (401 without it)."""
    with _crumb_lock:
        fresh = time.time() - _yf_auth["at"] < _CRUMB_TTL
        if not force and _yf_auth["crumb"] and fresh:
            return _yf_auth["session"], _yf_auth["crumb"]
        s = requests.Session()
        s.headers.update(YF_HEADERS)
        if YF_PROXIES:
            s.proxies.update(YF_PROXIES)
        s.get("https://fc.yahoo.com", timeout=10)  # sets the cookie; body/404 is irrelevant
        # getcrumb answers 406 to "Accept: application/json" (set in YF_HEADERS).
        r = s.get("https://query2.finance.yahoo.com/v1/test/getcrumb",
                  headers={"Accept": "*/*"}, timeout=10)
        crumb = r.text.strip()
        if r.status_code != 200 or not crumb or "<" in crumb or " " in crumb:
            raise RuntimeError(f"getcrumb failed: HTTP {r.status_code}")
        _yf_auth.update(session=s, crumb=crumb, at=time.time())
        return s, crumb


def _fetch_batch_quotes(batch: list) -> dict:
    """Yahoo /v7/finance/quote for up to 100 IDX tickers. Returns {ticker: {price, gain_pct}}."""
    symbols = ",".join(f"{t}.JK" for t in batch)
    try:
        for attempt in (0, 1):
            session, crumb = _yf_session_crumb(force=attempt == 1)
            resp = session.get(
                "https://query1.finance.yahoo.com/v7/finance/quote",
                params={"symbols": symbols, "crumb": crumb},
                timeout=10,
            )
            if resp.status_code not in (401, 403):
                break
        body = resp.json()
        if "quoteResponse" not in body:
            log.warning("Batch quote rejected (batch of %d): HTTP %s %s",
                        len(batch), resp.status_code, str(body.get("finance", {}).get("error"))[:120])
            return {}
        quotes = body["quoteResponse"].get("result", [])
        result = {}
        for q in quotes:
            ticker   = q.get("symbol", "").replace(".JK", "")
            price    = q.get("regularMarketPrice")
            gain_pct = q.get("regularMarketChangePercent")
            if ticker and price is not None:
                result[ticker] = {
                    "price":    int(round(float(price))),
                    "gain_pct": round(float(gain_pct), 2) if gain_pct is not None else None,
                }
        return result
    except Exception as e:
        log.warning("Batch quote fetch failed (batch of %d): %s", len(batch), e)
        return {}


def _refresh_stocks():
    """Fetch live prices for all ~800 IDX tickers in batches of 100."""
    new_cache = {}
    for i in range(0, len(_ALL_TICKERS), 100):
        batch = _ALL_TICKERS[i:i + 100]
        new_cache.update(_fetch_batch_quotes(batch))
    with _stock_lock:
        _stock_cache.clear()
        _stock_cache.update(new_cache)
    log.debug("Stock cache refreshed: %d tickers", len(new_cache))


def get_cached_stocks() -> dict:
    with _stock_lock:
        return dict(_stock_cache)


# ── Main loop ──────────────────────────────────────────────────────────────────

def _run_loop():
    _refresh_ihsg()
    _refresh_stocks()
    while True:
        time.sleep(30 if _is_market_open() else 60)
        _refresh_ihsg()
        _refresh_stocks()


def start_price_cache_thread():
    t = threading.Thread(target=_run_loop, daemon=True, name="price-cache")
    t.start()
    log.info("Price cache thread started (30s refresh during market hours, ~%d tickers)", len(_ALL_TICKERS))
