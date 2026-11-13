"""
broksum_fetch.py — Zenith 2.0 Broker Summary Data Layer (ARJUM API)
RULE: Single source of truth for all stock.arjum.com API calls.
      Caller controls all commits — no conn.commit() inside these functions.

ARJUM endpoints used:
  GET /api/broker-summary/{code}?start_date=D&end_date=D
      Full per-broker buy/sell breakdown (bval/bvol/sval/svol/nval/nvol).
      IMPORTANT: start_date/end_date is a RANGE the API aggregates over, not a
      per-day series — passing a wide range returns one summed total, not one
      row per day. To get daily granularity this must be called once per
      trading day (start_date == end_date). The `date` query param alone is
      silently ignored (confirmed empirically 2026-07-29) — start_date/end_date
      is the only working param pair.
  GET /api/broker-accumulation/{code}
      Historical per-broker DAILY net-flow series (nval/nvol/cum_nval/bavg/savg
      only — no gross buy/sell) covering several months by default, in a
      single request. This is the cheap one for retroactive backfill.
"""
import time
import logging

import requests

from core.db import execute

log = logging.getLogger("zenith.broksum")
log.setLevel(logging.INFO)


def _headers():
    from config import ARJUM_API_KEY
    return {"X-API-Key": ARJUM_API_KEY}


def fetch_broker_summary_day(conn, ticker: str, date: str) -> dict:
    """Fetch full broker buy/sell breakdown for one ticker on one trading day
    (date in YYYY-MM-DD). Upserts into broker_summary. Returns dict with
    request/row counts and rate-limit info. Caller is responsible for commit."""
    from config import ARJUM_API_KEY, ARJUM_BASE_URL

    if not ARJUM_API_KEY:
        log.error("fetch_broker_summary_day: ARJUM_API_KEY not set")
        return {"ok": False, "error": "ARJUM_API_KEY not set", "requests_used": 0}

    try:
        r = requests.get(
            f"{ARJUM_BASE_URL}/api/broker-summary/{ticker}",
            headers=_headers(),
            params={"start_date": date, "end_date": date},
            timeout=20,
        )
        if r.status_code == 500:
            time.sleep(3)
            r = requests.get(
                f"{ARJUM_BASE_URL}/api/broker-summary/{ticker}",
                headers=_headers(),
                params={"start_date": date, "end_date": date},
                timeout=20,
            )
        remaining = r.headers.get("x-ratelimit-remaining")
        if r.status_code != 200:
            log.warning("ARJUM broker-summary %s %s: HTTP %s", ticker, date, r.status_code)
            return {"ok": False, "error": f"HTTP {r.status_code}", "requests_used": 1,
                     "rate_limit_remaining": remaining}

        brokers = r.json().get("brokers", [])
        inserted = 0
        for b in brokers:
            try:
                execute(conn, """
                    INSERT INTO broker_summary
                        (date, ticker, broker_code, broker_name, bval, bvol, sval, svol, nval, nvol)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (date, ticker, broker_code) DO UPDATE SET
                        broker_name = EXCLUDED.broker_name,
                        bval = EXCLUDED.bval, bvol = EXCLUDED.bvol,
                        sval = EXCLUDED.sval, svol = EXCLUDED.svol,
                        nval = EXCLUDED.nval, nvol = EXCLUDED.nvol
                """, [date, ticker, b.get("broker_code"), b.get("broker_name"),
                      b.get("bval"), b.get("bvol"), b.get("sval"), b.get("svol"),
                      b.get("nval"), b.get("nvol")])
                inserted += 1
            except Exception as e:
                log.warning("broker_summary insert fail ticker=%s date=%s broker=%s: %s",
                            ticker, date, b.get("broker_code"), e)
                try:
                    conn.rollback()
                except Exception:
                    pass

        return {"ok": True, "requests_used": 1, "rows_inserted": inserted,
                "brokers_seen": len(brokers), "rate_limit_remaining": remaining}

    except Exception as e:
        log.warning("ARJUM broker-summary fetch fail ticker=%s date=%s: %s", ticker, date, e)
        return {"ok": False, "error": str(e), "requests_used": 1}


def fetch_broker_summary_range(conn, ticker: str, dates: list, progress_cb=None) -> dict:
    """Fetch full daily broker breakdown for `ticker` across `dates` (list of
    YYYY-MM-DD strings, one ARJUM request per date — this endpoint has no
    bulk per-day history mode). Rate-limited to 1 req/sec between calls.
    progress_cb(done, total, current_date, inserted, requests_used) per date.
    Caller is responsible for commit."""
    total_requests = 0
    total_inserted = 0
    failed_dates = []
    last_remaining = None

    for i, date in enumerate(dates):
        if i > 0:
            time.sleep(1)
        result = fetch_broker_summary_day(conn, ticker, date)
        total_requests += result.get("requests_used", 0)
        if result.get("ok"):
            total_inserted += result.get("rows_inserted", 0)
        else:
            failed_dates.append(date)
        if result.get("rate_limit_remaining") is not None:
            last_remaining = result["rate_limit_remaining"]
        if progress_cb:
            try:
                progress_cb(i + 1, len(dates), date, total_inserted, total_requests)
            except Exception:
                pass

    return {"ok": True, "ticker": ticker, "days_requested": len(dates),
            "requests_used": total_requests, "rows_inserted": total_inserted,
            "failed_dates": failed_dates, "rate_limit_remaining": last_remaining}


def fetch_broker_accumulation(conn, ticker: str) -> dict:
    """Fetch the historical daily net-flow series for `ticker` (single request,
    ARJUM's default window — typically several months). Upserts into
    broker_accumulation. Caller is responsible for commit."""
    from config import ARJUM_API_KEY, ARJUM_BASE_URL

    if not ARJUM_API_KEY:
        log.error("fetch_broker_accumulation: ARJUM_API_KEY not set")
        return {"ok": False, "error": "ARJUM_API_KEY not set", "requests_used": 0}

    try:
        r = requests.get(
            f"{ARJUM_BASE_URL}/api/broker-accumulation/{ticker}",
            headers=_headers(),
            timeout=20,
        )
        if r.status_code == 500:
            time.sleep(3)
            r = requests.get(
                f"{ARJUM_BASE_URL}/api/broker-accumulation/{ticker}",
                headers=_headers(),
                timeout=20,
            )
        remaining = r.headers.get("x-ratelimit-remaining")
        if r.status_code != 200:
            log.warning("ARJUM broker-accumulation %s: HTTP %s", ticker, r.status_code)
            return {"ok": False, "error": f"HTTP {r.status_code}", "requests_used": 1,
                     "rate_limit_remaining": remaining}

        data = r.json()
        inserted = 0
        for series in data.get("series", []):
            broker_code = series.get("broker_code")
            broker_name = series.get("broker_name")
            for p in series.get("points", []):
                try:
                    execute(conn, """
                        INSERT INTO broker_accumulation
                            (date, ticker, broker_code, broker_name, nval, nvol, cum_nval, bavg, savg)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (date, ticker, broker_code) DO UPDATE SET
                            broker_name = EXCLUDED.broker_name,
                            nval = EXCLUDED.nval, nvol = EXCLUDED.nvol,
                            cum_nval = EXCLUDED.cum_nval,
                            bavg = EXCLUDED.bavg, savg = EXCLUDED.savg
                    """, [p.get("date"), ticker, broker_code, broker_name,
                          p.get("nval"), p.get("nvol"), p.get("cum_nval"),
                          p.get("bavg"), p.get("savg")])
                    inserted += 1
                except Exception as e:
                    log.warning("broker_accumulation insert fail ticker=%s broker=%s date=%s: %s",
                                ticker, broker_code, p.get("date"), e)
                    try:
                        conn.rollback()
                    except Exception:
                        pass

        return {"ok": True, "requests_used": 1, "rows_inserted": inserted,
                "start_date": data.get("start_date"), "end_date": data.get("end_date"),
                "brokers": len(data.get("series", [])), "rate_limit_remaining": remaining}

    except Exception as e:
        log.warning("ARJUM broker-accumulation fetch fail ticker=%s: %s", ticker, e)
        return {"ok": False, "error": str(e), "requests_used": 1}
