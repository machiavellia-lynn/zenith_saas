"""
price_cache.py — Server-side IHSG price cache.
Background thread refreshes from Yahoo Finance every 30s during market hours only.
All clients read from one shared dict — request cost is flat regardless of user count.
"""
import threading
import time
import logging
import requests
from datetime import datetime

from config import WIB, YF_HEADERS

log = logging.getLogger("zenith.price_cache")

_cache: dict = {"price": None, "gain_pct": None, "updated_at": None}
_lock = threading.Lock()


def _is_market_open() -> bool:
    """Mon–Fri 09:00–16:15 WIB."""
    now = datetime.now(WIB)
    if now.weekday() >= 5:
        return False
    mins = now.hour * 60 + now.minute
    return 540 <= mins <= 975  # 09:00 = 540, 16:15 = 975


def _fetch_ihsg() -> dict:
    try:
        resp = requests.get(
            "https://query1.finance.yahoo.com/v8/finance/chart/%5EJKSE",
            headers=YF_HEADERS,
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


def _refresh():
    data = _fetch_ihsg()
    with _lock:
        _cache["price"]      = data["price"]
        _cache["gain_pct"]   = data["gain_pct"]
        _cache["updated_at"] = datetime.now(WIB).isoformat()
    log.debug("IHSG cache refreshed: price=%s gain_pct=%s", data["price"], data["gain_pct"])


def get_cached_ihsg() -> dict:
    with _lock:
        return dict(_cache)


def _run_loop():
    _refresh()  # immediate first fetch on startup
    while True:
        time.sleep(30 if _is_market_open() else 60)
        _refresh()


def start_price_cache_thread():
    t = threading.Thread(target=_run_loop, daemon=True, name="price-cache")
    t.start()
    log.info("Price cache thread started (30s refresh during market hours)")
