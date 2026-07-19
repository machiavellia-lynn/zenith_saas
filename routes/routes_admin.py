"""
routes_admin.py — Blueprint: /admin/*
RULE: Routing + status reporting only. All ops (rebuild, backfill, scraper) in dedicated modules.
"""
import os
from flask import Blueprint, render_template, jsonify, request, redirect, abort
from core.auth import is_authed, is_admin

bp_admin = Blueprint("admin", __name__)


@bp_admin.before_request
def _require_admin():
    if not is_authed():
        return redirect("/")
    if not is_admin():
        abort(403)

# Module-level state for "Fetch All 15m" background job
_intraday_all = {
    "status":       "idle",   # idle | running | done | error
    "current_date": None,
    "done":         0,
    "total":        0,
    "rows_total":   0,
    "error":        None,
}

# Module-level state for "Fetch All OHLCV Daily" background job
_ohlcv_daily_all = {
    "status":         "idle",   # idle | running | done | error
    "current_ticker": None,
    "done":           0,
    "total":          0,
    "rows_total":     0,
    "error":          None,
    "date_from":      None,
    "date_to":        None,
}


@bp_admin.route("/admin")
def admin_page():
    if not is_authed():
        return redirect("/")
    return render_template("admin.html")


@bp_admin.route("/admin/scraper-status")
def scraper_status():
    if not is_authed():
        return redirect("/")
    from scraper.scraper_daily import get_backfill_status
    from core.db import get_scraper_db, fetchall

    status = get_backfill_status()

    def _sort_to_dmy(s):
        """Convert YYYYMMDD sort key back to DD-MM-YYYY for display."""
        if not s or len(str(s)) != 8:
            return "—"
        s = str(s)
        return f"{s[6:8]}-{s[4:6]}-{s[0:4]}"

    try:
        conn = get_scraper_db()
        # Actual channel values stored by the scraper
        # SM/BM stored in raw_messages; MF+/MF- stored in raw_mf_messages
        sm_bm_map = {"smart": "SM", "bad": "BM"}
        mf_map    = {"mf_plus": "MF+", "mf_minus": "MF-"}
        first_data  = {}
        latest_data = {}
        row_counts  = {}

        for ch, label in sm_bm_map.items():
            rows = fetchall(conn, """
                SELECT
                    MIN(SUBSTR(date,7,4)||SUBSTR(date,4,2)||SUBSTR(date,1,2)) AS first_sort,
                    MAX(SUBSTR(date,7,4)||SUBSTR(date,4,2)||SUBSTR(date,1,2)) AS last_sort,
                    COUNT(*) AS cnt
                FROM raw_messages WHERE channel = %s
            """, [ch])
            if rows and rows[0]["cnt"]:
                r = rows[0]
                first_data[label]  = _sort_to_dmy(r["first_sort"])
                latest_data[label] = _sort_to_dmy(r["last_sort"])
                row_counts[label]  = int(r["cnt"])
            else:
                first_data[label]  = "—"
                latest_data[label] = "—"
                row_counts[label]  = 0

        for ch, label in mf_map.items():
            rows = fetchall(conn, """
                SELECT
                    MIN(SUBSTR(date,7,4)||SUBSTR(date,4,2)||SUBSTR(date,1,2)) AS first_sort,
                    MAX(SUBSTR(date,7,4)||SUBSTR(date,4,2)||SUBSTR(date,1,2)) AS last_sort,
                    COUNT(*) AS cnt
                FROM raw_mf_messages WHERE channel = %s
            """, [ch])
            if rows and rows[0]["cnt"]:
                r = rows[0]
                first_data[label]  = _sort_to_dmy(r["first_sort"])
                latest_data[label] = _sort_to_dmy(r["last_sort"])
                row_counts[label]  = int(r["cnt"])
            else:
                first_data[label]  = "—"
                latest_data[label] = "—"
                row_counts[label]  = 0

        eod = fetchall(conn, """
            SELECT
                MIN(SUBSTR(date,7,4)||SUBSTR(date,4,2)||SUBSTR(date,1,2)) AS first_sort,
                MAX(SUBSTR(date,7,4)||SUBSTR(date,4,2)||SUBSTR(date,1,2)) AS last_sort,
                COUNT(*) AS cnt
            FROM eod_summary
        """)
        if eod and eod[0]["cnt"]:
            first_data["EOD"]     = _sort_to_dmy(eod[0]["first_sort"])
            latest_data["EOD"]    = _sort_to_dmy(eod[0]["last_sort"])
            row_counts["summary"] = int(eod[0]["cnt"])
        else:
            first_data["EOD"]     = "—"
            latest_data["EOD"]    = "—"
            row_counts["summary"] = 0

        status["first_data"]  = first_data
        status["latest_data"] = latest_data
        status["row_counts"]  = row_counts
        conn.close()
    except Exception as e:
        status["db_error"] = str(e)

    return jsonify(status)


@bp_admin.route("/admin/fix-all")
def fix_all():
    if not is_authed():
        return redirect("/")
    date_from = request.args.get("date_from", "").strip() or None
    date_to   = request.args.get("date_to",   "").strip() or None
    from scraper.scraper_daily import request_fix_all
    result = request_fix_all(date_from, date_to)
    return jsonify(result)


@bp_admin.route("/admin/scraper-weekly")
def trigger_weekly():
    if not is_authed():
        return redirect("/")
    days = int(request.args.get("days", 7))
    from scraper.scraper_daily import request_backfill
    result = request_backfill(days)
    return jsonify(result)


# ── Telegram Backfill (fetch raw msgs from Telegram for a date range) ─────────

@bp_admin.route("/admin/tele-backfill")
def admin_tele_backfill():
    if not is_authed():
        return redirect("/")

    date_from = request.args.get("date_from", "").strip()
    date_to   = request.args.get("date_to",   "").strip()
    if not date_from or not date_to:
        return jsonify({"ok": False, "error": "date_from dan date_to wajib (DD-MM-YYYY)"}), 400

    from core.utils import date_range as _date_range
    from scraper.scraper_daily import request_tele_dates_backfill

    dates = _date_range(date_from, date_to)
    result = request_tele_dates_backfill(dates)
    return jsonify(result)


@bp_admin.route("/admin/tele-backfill-status")
def admin_tele_backfill_status():
    if not is_authed():
        return redirect("/")
    from scraper.scraper_daily import get_tele_dates_status
    return jsonify(get_tele_dates_status())


@bp_admin.route("/admin/rebuild-summary")
def rebuild_summary():
    if not is_authed():
        return redirect("/")
    date_str = request.args.get("date", "")
    if not date_str:
        # No date = queue full rebuild via scraper daemon
        from scraper.scraper_daily import request_rebuild
        result = request_rebuild()
        return jsonify(result)
    from algo.summary_rebuild import rebuild_summary_for_date
    from core.db import get_scraper_db, transaction
    conn = get_scraper_db()
    try:
        with transaction(conn):
            rebuild_summary_for_date(conn, date_str)
        return jsonify({"ok": True})
    finally:
        conn.close()


@bp_admin.route("/admin/recompute-analytics")
def recompute_analytics():
    if not is_authed():
        return redirect("/")
    date_str = request.args.get("date", "")
    if not date_str:
        from scraper.scraper_daily import request_recompute_analytics
        result = request_recompute_analytics()
        return jsonify(result)
    from algo.analytics_daily import compute_analytics_for_date
    from core.db import get_scraper_db, transaction
    conn = get_scraper_db()
    try:
        with transaction(conn):
            n = compute_analytics_for_date(conn, date_str)
        return jsonify({"ok": True, "updated": n})
    finally:
        conn.close()


_prices_progress = {
    "status": "idle",
    "step":   None,        # prices | 200d | analytics | None
    "done":   0,
    "total":  0,
    "current": None,
    "prices_updated":       0,
    "analytics_recomputed": 0,
    "date_from": None,
    "date_to":   None,
    "error":     None,
}


@bp_admin.route("/admin/backfill-prices")
def admin_backfill_prices():
    if not is_authed():
        return redirect("/")
    if _prices_progress["status"] == "running":
        return jsonify({"ok": False, "error": "Backfill prices sedang berjalan, tunggu selesai."})
    days      = int(request.args.get("days", 30))
    date_from = request.args.get("date_from", "").strip() or None
    date_to   = request.args.get("date_to", "").strip() or None

    import threading
    from data.price_fetch import backfill_prices
    from algo.analytics_daily import compute_analytics_for_date
    from core.db import get_scraper_db, fetchall
    from datetime import datetime
    import logging as _logging
    _log = _logging.getLogger("zenith.admin")

    _prices_progress.update({
        "status": "running", "step": "prices", "done": 0, "total": 0, "current": None,
        "prices_updated": 0, "analytics_recomputed": 0,
        "date_from": date_from, "date_to": date_to, "error": None,
    })

    def _run():
        conn = get_scraper_db()
        try:
            # Phase 1: prices (fetches price_history via DataSectors, then syncs
            # into eod_summary.price_close — one DataSectors call per ticker, not two)
            _prices_progress["step"] = "prices"
            prices_updated = backfill_prices(conn, days=days, date_from=date_from, date_to=date_to)
            _prices_progress["prices_updated"] = prices_updated

            # Phase 2: analytics
            analytics_recomputed = 0
            if date_from:
                fmt = "%d-%m-%Y"
                dt_f = datetime.strptime(date_from, fmt)
                dt_t = datetime.strptime(date_to, fmt) if date_to else datetime.now()
                all_rows = fetchall(conn, "SELECT DISTINCT date FROM eod_summary ORDER BY date")
                dates_to_recompute = sorted([
                    r["date"] for r in all_rows
                    if dt_f <= datetime.strptime(r["date"], fmt) <= dt_t
                ])
                _prices_progress.update({"step": "analytics", "done": 0, "total": len(dates_to_recompute)})
                for i, d in enumerate(dates_to_recompute):
                    _prices_progress["current"] = d
                    try:
                        n = compute_analytics_for_date(conn, d)
                        analytics_recomputed += n
                        conn.commit()
                    except Exception as e:
                        _log.error(f"Analytics recompute failed for {d}: {e}")
                        conn.rollback()
                    _prices_progress["done"] = i + 1
                _prices_progress["analytics_recomputed"] = analytics_recomputed

            _prices_progress.update({"status": "done", "step": None, "current": None})
            _log.info("backfill prices done: %s prices, %s analytics", prices_updated, analytics_recomputed)
        except Exception as e:
            conn.rollback()
            _prices_progress.update({"status": "error", "error": str(e)})
            _log.error(f"Backfill prices failed: {e}")
        finally:
            conn.close()

    threading.Thread(target=_run, daemon=True).start()
    return jsonify({"ok": True, "message": f"Backfill prices dimulai ({date_from} s/d {date_to})."})


@bp_admin.route("/admin/prices-progress")
def admin_prices_progress():
    if not is_authed():
        return redirect("/")
    return jsonify(_prices_progress)


@bp_admin.route("/admin/backfill-200d")
def admin_backfill_200d():
    if not is_authed():
        return redirect("/")
    import threading
    from data.price_fetch import backfill_price_history_200d
    from core.db import get_scraper_db
    import logging as _logging
    _log = _logging.getLogger("zenith.admin")

    def _run():
        conn = get_scraper_db()
        try:
            backfill_price_history_200d(conn)
            conn.commit()
        except Exception as e:
            conn.rollback()
            _log.error(f"price_history backfill failed: {e}")
        finally:
            conn.close()

    threading.Thread(target=_run, daemon=True).start()
    return jsonify({"ok": True, "message": "200d price history backfill started"})


_intraday_progress = {
    "status":  "idle",   # idle | running | done | error
    "done":    0,
    "total":   0,
    "current": None,
    "rows_inserted": 0,
    "failed_count":  0,
    "date_from": None,
    "date_to":   None,
    "error":     None,
}


@bp_admin.route("/admin/backfill-intraday")
def admin_backfill_intraday():
    if not is_authed():
        return redirect("/")
    if _intraday_progress["status"] == "running":
        return jsonify({"ok": False, "error": "Backfill intraday sedang berjalan, tunggu selesai."})
    date_from = request.args.get("date_from", "").strip()
    date_to   = request.args.get("date_to",   "").strip()
    if not date_from or not date_to:
        return jsonify({"ok": False, "error": "date_from dan date_to wajib (DD-MM-YYYY)"}), 400

    import threading
    from data.price_fetch import fetch_intraday_15m_datasectors
    from core.db import get_scraper_db, fetchall
    import logging as _logging
    _log = _logging.getLogger("zenith.admin")

    _intraday_progress.update({
        "status": "running", "done": 0, "total": 0, "current": None,
        "rows_inserted": 0, "failed_count": 0,
        "date_from": date_from, "date_to": date_to, "error": None,
    })

    def _progress_cb(done, total, current, inserted, failed):
        _intraday_progress["done"]    = done
        _intraday_progress["total"]   = total
        _intraday_progress["current"] = current
        _intraday_progress["rows_inserted"] = inserted
        _intraday_progress["failed_count"]  = failed

    def _run():
        conn = get_scraper_db()
        try:
            tickers = [r["ticker"] for r in fetchall(conn,
                "SELECT ticker FROM ticker_universe WHERE is_active = TRUE")]
            if not tickers:
                tickers = [r["ticker"] for r in fetchall(conn,
                    "SELECT DISTINCT ticker FROM eod_summary")]
            _intraday_progress["total"] = len(tickers)
            _log.info("backfill intraday DS: %d tickers, %s s/d %s", len(tickers), date_from, date_to)
            res = fetch_intraday_15m_datasectors(conn, tickers, date_from, date_to, progress_cb=_progress_cb)
            conn.commit()
            _intraday_progress["status"] = "done"
            _log.info("backfill intraday DS done: %s rows, %s failed",
                      res.get("rows_inserted"), res.get("failed_count"))
        except Exception as e:
            conn.rollback()
            _intraday_progress.update({"status": "error", "error": str(e)})
            _log.error("backfill intraday DS failed: %s", e)
        finally:
            conn.close()

    threading.Thread(target=_run, daemon=True).start()
    return jsonify({"ok": True, "message": f"Intraday 15m backfill via DataSectors dimulai ({date_from} s/d {date_to})."})


@bp_admin.route("/admin/intraday-progress")
def admin_intraday_progress():
    if not is_authed():
        return redirect("/")
    return jsonify(_intraday_progress)


@bp_admin.route("/admin/backfill-intraday-all")
def admin_backfill_intraday_all():
    if not is_authed():
        return redirect("/")
    if _intraday_all["status"] == "running":
        return jsonify({"ok": False, "error": "Sudah berjalan, tunggu selesai dulu."})

    import threading, time as _time
    from datetime import datetime, timedelta
    from data.price_fetch import backfill_intraday_15m
    from core.db import get_scraper_db, fetchall
    from config import WIB
    import logging as _logging
    _log = _logging.getLogger("zenith.admin")

    def _run():
        # Ambil semua tanggal IDX dalam 60 hari kalender dari price_history
        conn = get_scraper_db()
        try:
            cutoff = (datetime.now(WIB) - timedelta(days=60)).strftime("%Y-%m-%d")
            rows   = fetchall(conn, """
                SELECT DISTINCT date FROM price_history
                WHERE date >= %s ORDER BY date
            """, [cutoff])
        except Exception as e:
            _intraday_all.update({"status": "error", "error": str(e)})
            conn.close()
            return
        finally:
            conn.close()

        dates = [r["date"] for r in rows]  # format YYYY-MM-DD
        _intraday_all.update({
            "status": "running", "total": len(dates),
            "done": 0, "rows_total": 0, "error": None, "current_date": None,
        })
        _log.info("intraday_all: %d tanggal akan diproses", len(dates))

        for i, date_yyyy in enumerate(dates):
            d, m, y = date_yyyy[8:10], date_yyyy[5:7], date_yyyy[:4]
            date_dmy = f"{d}-{m}-{y}"
            _intraday_all["current_date"] = date_yyyy

            conn = get_scraper_db()
            try:
                res = backfill_intraday_15m(conn, date_dmy, date_dmy)
                conn.commit()
                _intraday_all["rows_total"] += res.get("rows_inserted", 0)
            except Exception as e:
                conn.rollback()
                _log.error("intraday_all failed %s: %s", date_yyyy, e)
            finally:
                conn.close()

            _intraday_all["done"] = i + 1
            if i < len(dates) - 1:
                _time.sleep(180)

        _intraday_all.update({"status": "done", "current_date": None})
        _log.info("intraday_all done: %d tanggal, %d rows", len(dates), _intraday_all["rows_total"])

    threading.Thread(target=_run, daemon=True).start()
    return jsonify({"ok": True, "message": "Fetch All 15m dimulai di background."})


@bp_admin.route("/admin/intraday-all-status")
def admin_intraday_all_status():
    if not is_authed():
        return redirect("/")
    return jsonify(_intraday_all)


@bp_admin.route("/admin/fix-15m-datetime")
def admin_fix_15m_datetime():
    """One-time migration: rows stored with seconds format (HH:MM:SS) → HH:MM.
    Safe to re-run — uses ON CONFLICT to handle duplicates, then deletes old rows."""
    from core.db import get_scraper_db, execute
    import logging as _logging
    _log = _logging.getLogger("zenith.admin")

    conn = get_scraper_db()
    try:
        with conn.cursor() as cur:
            # Re-insert bad rows with truncated datetime (ON CONFLICT merges duplicates)
            cur.execute("""
                INSERT INTO price_history_15m (datetime, ticker, open, high, low, close, volume)
                SELECT LEFT(datetime, 16), ticker, open, high, low, close, volume
                FROM price_history_15m
                WHERE LENGTH(datetime) > 16
                ON CONFLICT (datetime, ticker) DO UPDATE SET
                    open   = EXCLUDED.open,
                    high   = EXCLUDED.high,
                    low    = EXCLUDED.low,
                    close  = EXCLUDED.close,
                    volume = EXCLUDED.volume
            """)
            migrated = cur.rowcount
            # Delete the bad rows
            cur.execute("DELETE FROM price_history_15m WHERE LENGTH(datetime) > 16")
            deleted = cur.rowcount
        conn.commit()
        _log.info("fix-15m-datetime: migrated=%d deleted=%d", migrated, deleted)
        return jsonify({"ok": True, "migrated": migrated, "deleted": deleted})
    except Exception as e:
        conn.rollback()
        _log.error("fix-15m-datetime failed: %s", e)
        return jsonify({"ok": False, "error": str(e)}), 500
    finally:
        conn.close()


@bp_admin.route("/admin/backfill-ohlcv-daily")
def admin_backfill_ohlcv_daily():
    if not is_authed():
        return redirect("/")
    if _ohlcv_daily_all["status"] == "running":
        return jsonify({"ok": False, "error": "Sudah berjalan, tunggu selesai dulu."})

    date_from = request.args.get("date_from", "").strip()
    date_to   = request.args.get("date_to",   "").strip()
    if not date_from or not date_to:
        return jsonify({"ok": False, "error": "date_from dan date_to wajib (DD-MM-YYYY)"}), 400

    import threading
    from datetime import datetime
    from data.price_fetch import fetch_daily_datasectors
    from core.db import get_scraper_db, fetchall
    import logging as _logging
    _log = _logging.getLogger("zenith.admin")

    fmt = "%d-%m-%Y"
    try:
        datetime.strptime(date_from, fmt)
        datetime.strptime(date_to, fmt)
    except ValueError:
        return jsonify({"ok": False, "error": "Format tanggal salah, gunakan DD-MM-YYYY"}), 400

    _ohlcv_daily_all.update({
        "status": "idle", "current_ticker": None,
        "done": 0, "total": 0, "rows_total": 0,
        "error": None, "date_from": date_from, "date_to": date_to,
    })

    def _progress_cb(done, total, current, inserted, failed):
        _ohlcv_daily_all["done"]           = done
        _ohlcv_daily_all["total"]          = total
        _ohlcv_daily_all["current_ticker"] = current
        _ohlcv_daily_all["rows_total"]     = inserted

    def _run():
        conn = get_scraper_db()
        try:
            rows = fetchall(conn, "SELECT ticker FROM ticker_universe WHERE is_active = TRUE ORDER BY ticker")
            if not rows:
                rows = fetchall(conn, "SELECT DISTINCT ticker FROM eod_summary ORDER BY ticker")
            tickers = [r["ticker"] for r in rows]
        except Exception as e:
            _ohlcv_daily_all.update({"status": "error", "error": str(e)})
            conn.close()
            return

        _ohlcv_daily_all.update({
            "status": "running", "total": len(tickers),
            "done": 0, "rows_total": 0, "error": None,
        })
        _log.info("ohlcv_daily_all: %d tickers, %s → %s", len(tickers), date_from, date_to)

        try:
            fetch_daily_datasectors(conn, tickers, date_from, date_to, progress_cb=_progress_cb)
            conn.commit()
        except Exception as e:
            conn.rollback()
            _log.error("ohlcv_daily_all failed: %s", e)
            _ohlcv_daily_all["error"] = str(e)
        finally:
            conn.close()

        _ohlcv_daily_all.update({"status": "done", "current_ticker": None})
        _log.info("ohlcv_daily_all done: %d tickers, %d rows", len(tickers), _ohlcv_daily_all["rows_total"])

    threading.Thread(target=_run, daemon=True).start()
    return jsonify({"ok": True, "message": f"OHLCV Daily backfill dimulai ({date_from} → {date_to})."})


@bp_admin.route("/admin/ohlcv-daily-status")
def admin_ohlcv_daily_status():
    if not is_authed():
        return redirect("/")
    return jsonify(_ohlcv_daily_all)


@bp_admin.route("/admin/seed-eod")
def admin_seed_eod():
    if not is_authed():
        return redirect("/")
    date_from = request.args.get("date_from", "").strip() or None
    date_to   = request.args.get("date_to",   "").strip() or None

    import threading
    from algo.summary_rebuild import seed_eod_from_price_history
    from core.db import get_scraper_db, transaction
    import logging as _logging
    _log = _logging.getLogger("zenith.admin")

    def _run():
        conn = get_scraper_db()
        try:
            with transaction(conn):
                inserted = seed_eod_from_price_history(conn, date_from, date_to)
            _log.info("seed_eod done: %d rows inserted", inserted)
        except Exception as e:
            conn.rollback()
            _log.error("seed_eod failed: %s", e)
        finally:
            conn.close()

    threading.Thread(target=_run, daemon=True).start()
    label = f"{date_from} → {date_to}" if date_from else "semua tanggal"
    return jsonify({"ok": True, "message": f"Seed EOD Summary dimulai ({label}). Cek server log untuk result."})


# Module-level state for BSJP historical backfill
_bsjp_backfill = {
    "status":       "idle",   # idle | running | done | error
    "current_date": None,
    "done":         0,
    "total":        0,
    "inserted":     0,
    "error":        None,
}


def _run_bsjp_scan_for_date(conn, date_str: str) -> int:
    """Run BSJP scan for a specific date. Delegates to scraper's run_bsjp_scan."""
    from scraper.scraper_daily import run_bsjp_scan
    return run_bsjp_scan(conn, date_str)


@bp_admin.route("/admin/bsjp-scan")
def admin_bsjp_scan():
    """Manual BSJP scan for a specific date (sync, uses historical eod_summary)."""
    if not is_authed():
        return redirect("/")
    date_str = request.args.get("date", "").strip()
    if not date_str:
        return jsonify({"ok": False, "error": "Parameter date wajib (DD-MM-YYYY)"}), 400

    from core.db import get_scraper_db
    conn = get_scraper_db()
    try:
        count = _run_bsjp_scan_for_date(conn, date_str)
        return jsonify({"ok": True, "date": date_str, "signals": count})
    except Exception as e:
        conn.rollback()
        return jsonify({"ok": False, "error": str(e)}), 500
    finally:
        conn.close()



@bp_admin.route("/admin/bsjp-backfill")
def admin_bsjp_backfill():
    """Historical BSJP backfill for a date range (background thread)."""
    if not is_authed():
        return redirect("/")
    if _bsjp_backfill["status"] == "running":
        return jsonify({"ok": False, "error": "Sudah berjalan, tunggu selesai dulu."})

    date_from = request.args.get("date_from", "").strip()
    date_to   = request.args.get("date_to",   "").strip()
    if not date_from or not date_to:
        return jsonify({"ok": False, "error": "date_from dan date_to wajib (DD-MM-YYYY)"}), 400

    import threading
    import logging
    from core.db import get_scraper_db, fetchall
    _log = logging.getLogger("zenith.admin")

    def _run():
        conn = get_scraper_db()
        try:
            rows = fetchall(conn, """
                SELECT DISTINCT date FROM eod_summary
                WHERE SUBSTR(date,7,4)||SUBSTR(date,4,2)||SUBSTR(date,1,2)
                      BETWEEN SUBSTR(%s,7,4)||SUBSTR(%s,4,2)||SUBSTR(%s,1,2)
                          AND SUBSTR(%s,7,4)||SUBSTR(%s,4,2)||SUBSTR(%s,1,2)
                ORDER BY date
            """, [date_from, date_from, date_from, date_to, date_to, date_to])
        except Exception as e:
            _bsjp_backfill.update({"status": "error", "error": str(e)})
            conn.close()
            return
        finally:
            conn.close()

        dates = [r["date"] for r in rows]
        _bsjp_backfill.update({
            "status": "running", "total": len(dates),
            "done": 0, "inserted": 0, "error": None, "current_date": None,
        })
        _log.info("BSJP backfill: %d tanggal, %s → %s", len(dates), date_from, date_to)

        for i, d in enumerate(dates):
            _bsjp_backfill["current_date"] = d
            conn = get_scraper_db()
            try:
                n = _run_bsjp_scan_for_date(conn, d)
                _bsjp_backfill["inserted"] += n
            except Exception as e:
                conn.rollback()
                _log.error("BSJP backfill failed %s: %s", d, e)
            finally:
                conn.close()
            _bsjp_backfill["done"] = i + 1

        _bsjp_backfill.update({"status": "done", "current_date": None})
        _log.info("BSJP backfill done: %d signals dari %d tanggal", _bsjp_backfill["inserted"], len(dates))

    threading.Thread(target=_run, daemon=True).start()
    return jsonify({"ok": True, "message": f"BSJP backfill dimulai ({date_from} → {date_to}). Cek status."})


@bp_admin.route("/admin/bsjp-syariah-backfill")
def admin_bsjp_syariah_backfill():
    """Insert-only: adds universe='syariah' rows for dates that already have
    'full' rows but predate the universe column. Never touches 'full' rows —
    see scraper_daily.backfill_syariah_signals."""
    if not is_authed():
        return redirect("/")
    from scraper.scraper_daily import backfill_syariah_signals
    date_from = request.args.get("date_from", "").strip() or None
    date_to   = request.args.get("date_to",   "").strip() or None
    triggered = backfill_syariah_signals(date_from, date_to)
    if not triggered:
        return jsonify({"ok": False, "error": "Sudah berjalan, tunggu selesai dulu."})
    return jsonify({"ok": True})


@bp_admin.route("/admin/bsjp-syariah-backfill-status")
def admin_bsjp_syariah_backfill_status():
    if not is_authed():
        return jsonify({"error": "unauthorized"}), 401
    from scraper.scraper_daily import get_syariah_backfill_status
    return jsonify(get_syariah_backfill_status())


@bp_admin.route("/admin/bsjp-status")
def admin_bsjp_status():
    if not is_authed():
        return redirect("/")
    return jsonify(_bsjp_backfill)


@bp_admin.route("/admin/trigger-backtest")
def trigger_backtest():
    if not is_authed():
        return redirect("/")
    days = int(request.args.get("days", 30))
    from algo.algo_backtest import request_backtest
    request_backtest(days)
    return jsonify({"ok": True})


@bp_admin.route("/admin/upload-session", methods=["POST"])
def upload_session():
    if not is_authed():
        return jsonify({"ok": False, "error": "Unauthorized"}), 401
    file = request.files.get("session")
    if not file or not file.filename:
        return jsonify({"ok": False, "error": "No file data"}), 400
    from config import TG_SESSION_PATH
    os.makedirs(os.path.dirname(TG_SESSION_PATH) or "/data", exist_ok=True)
    file.save(TG_SESSION_PATH)
    size = os.path.getsize(TG_SESSION_PATH)
    return jsonify({"ok": True, "message": f"Session uploaded ({size:,} bytes) → {TG_SESSION_PATH}"})


@bp_admin.route("/admin/users")
def list_users():
    if not is_authed():
        return jsonify({"error": "unauthorized"}), 401
    from core.db import get_db, fetchall
    conn = get_db()
    users = fetchall(conn, "SELECT id, username, role, mode, created_at FROM users ORDER BY id")
    return jsonify([dict(u) for u in users])


@bp_admin.route("/admin/users/add", methods=["POST"])
def add_user():
    if not is_authed():
        return jsonify({"ok": False}), 401
    data = request.get_json() or {}
    username = (data.get("username") or "").strip()
    password = (data.get("password") or "").strip()
    role     = data.get("role", "guest")
    mode     = data.get("mode", "general")
    if not username or not password:
        return jsonify({"ok": False, "error": "Username dan password wajib"})
    if role not in ("admin", "guest"):
        return jsonify({"ok": False, "error": "Role harus admin atau guest"})
    if mode not in ("general", "syariah"):
        return jsonify({"ok": False, "error": "Mode harus general atau syariah"})
    from core.auth import register
    ok = register(username, password, role, mode)
    if ok:
        return jsonify({"ok": True})
    return jsonify({"ok": False, "error": "Username sudah dipakai"})


@bp_admin.route("/admin/users/mode/<int:user_id>", methods=["POST"])
def set_user_mode(user_id):
    """Flip an existing account between general and syariah.

    Without this the mode would only ever be settable at creation, leaving every
    pre-existing account — the admin's own included — stuck on 'general'.
    """
    if not is_authed():
        return jsonify({"ok": False}), 401
    mode = (request.get_json() or {}).get("mode", "")
    if mode not in ("general", "syariah"):
        return jsonify({"ok": False, "error": "Mode harus general atau syariah"})
    from core.db import get_db, execute, transaction
    conn = get_db()
    with transaction(conn):
        execute(conn, "UPDATE users SET mode = %s WHERE id = %s", [mode, user_id])
    # The change lands in the target's session only on their next login — their
    # session cookie still carries the old mode until then.
    return jsonify({"ok": True, "mode": mode})


@bp_admin.route("/admin/users/delete/<int:user_id>", methods=["POST"])
def delete_user(user_id):
    if not is_authed():
        return jsonify({"ok": False}), 401
    from core.db import get_db, execute, transaction
    conn = get_db()
    with transaction(conn):
        execute(conn, "DELETE FROM users WHERE id = %s", [user_id])
    return jsonify({"ok": True})


# ── API Keys (multi-key auth for /api/v1/*, see core/api_auth.py) ──────────────

@bp_admin.route("/admin/api-keys")
def list_api_keys():
    if not is_authed():
        return jsonify({"error": "unauthorized"}), 401
    from core.db import get_db, fetchall
    conn = get_db()
    keys = fetchall(conn, """
        SELECT id, name, key_prefix, environment, created_at, last_used_at
        FROM api_keys WHERE revoked = FALSE ORDER BY id
    """)
    return jsonify([dict(k) for k in keys])


@bp_admin.route("/admin/api-keys/add", methods=["POST"])
def add_api_key():
    if not is_authed():
        return jsonify({"ok": False}), 401
    import hashlib
    import secrets as _secrets
    data = request.get_json() or {}
    name        = (data.get("name") or "Default").strip() or "Default"
    environment = data.get("environment", "live")
    if environment not in ("live", "test"):
        return jsonify({"ok": False, "error": "Environment harus live atau test"})

    raw_key   = f"zenith_{environment}_{_secrets.token_urlsafe(24)}"
    key_hash  = hashlib.sha256(raw_key.encode()).hexdigest()
    key_prefix = raw_key[:16]

    from core.db import get_db, execute, transaction
    conn = get_db()
    with transaction(conn):
        execute(conn, """
            INSERT INTO api_keys (name, key_prefix, key_hash, environment)
            VALUES (%s, %s, %s, %s)
        """, [name, key_prefix, key_hash, environment])
    return jsonify({"ok": True, "key": raw_key})


@bp_admin.route("/admin/api-keys/delete/<int:key_id>", methods=["POST"])
def delete_api_key(key_id):
    if not is_authed():
        return jsonify({"ok": False}), 401
    from core.db import get_db, execute, transaction
    conn = get_db()
    with transaction(conn):
        execute(conn, "UPDATE api_keys SET revoked = TRUE WHERE id = %s", [key_id])
    return jsonify({"ok": True})


# ── Wyckoff Recompute (rebuild summary + analytics per date range) ─────────────

_wyckoff_recompute = {
    "status": "idle", "current_date": None,
    "done": 0, "total": 0, "error": None,
}


@bp_admin.route("/admin/wyckoff-recompute")
def admin_wyckoff_recompute():
    if not is_authed():
        return redirect("/")
    if _wyckoff_recompute["status"] == "running":
        return jsonify({"ok": False, "error": "Sudah berjalan, tunggu selesai dulu."})
    date_from = request.args.get("date_from", "").strip()
    date_to   = request.args.get("date_to",   "").strip()
    if not date_from or not date_to:
        return jsonify({"ok": False, "error": "date_from dan date_to wajib (DD-MM-YYYY)"}), 400

    import threading
    from algo.summary_rebuild import rebuild_summary_for_date
    from algo.analytics_daily import compute_analytics_for_date
    from core.db import get_scraper_db, transaction
    from core.utils import date_range
    import logging as _logging
    _log = _logging.getLogger("zenith.admin")

    def _run():
        conn = get_scraper_db()
        dates = date_range(date_from, date_to)
        _wyckoff_recompute.update({
            "status": "running", "total": len(dates),
            "done": 0, "error": None, "current_date": None,
        })
        _log.info("wyckoff_recompute: %d dates %s → %s", len(dates), date_from, date_to)

        for i, d in enumerate(dates):
            _wyckoff_recompute["current_date"] = d
            try:
                with transaction(conn):
                    rebuild_summary_for_date(conn, d)
                with transaction(conn):
                    compute_analytics_for_date(conn, d)
            except Exception as e:
                _log.error("wyckoff_recompute failed %s: %s", d, e)
                conn.rollback()
            _wyckoff_recompute["done"] = i + 1

        _wyckoff_recompute.update({"status": "done", "current_date": None})
        _log.info("wyckoff_recompute done: %d dates", len(dates))
        conn.close()

    threading.Thread(target=_run, daemon=True).start()
    return jsonify({"ok": True, "message": "Wyckoff recompute dimulai di background."})


@bp_admin.route("/admin/wyckoff-recompute-status")
def admin_wyckoff_recompute_status():
    if not is_authed():
        return redirect("/")
    return jsonify(_wyckoff_recompute)


# ── EOD Summary rebuild (raw Telegram → eod_summary rows only, no analytics) ───

_eod_summary_progress = {
    "status": "idle", "current_date": None,
    "done": 0, "total": 0, "error": None,
}


@bp_admin.route("/admin/eod-summary-rebuild")
def admin_eod_summary_rebuild():
    if _eod_summary_progress["status"] == "running":
        return jsonify({"ok": False, "error": "Sudah berjalan, tunggu selesai dulu."})
    date_from = request.args.get("date_from", "").strip()
    date_to   = request.args.get("date_to",   "").strip()
    if not date_from or not date_to:
        return jsonify({"ok": False, "error": "date_from dan date_to wajib (DD-MM-YYYY)"}), 400

    import threading
    from algo.summary_rebuild import rebuild_summary_for_date
    from core.db import get_scraper_db, transaction
    from core.utils import date_range
    import logging as _logging
    _log = _logging.getLogger("zenith.admin")

    def _run():
        conn = get_scraper_db()
        dates = date_range(date_from, date_to)
        _eod_summary_progress.update({
            "status": "running", "total": len(dates),
            "done": 0, "error": None, "current_date": None,
        })
        _log.info("eod_summary_rebuild: %d dates %s → %s", len(dates), date_from, date_to)

        for i, d in enumerate(dates):
            _eod_summary_progress["current_date"] = d
            try:
                with transaction(conn):
                    rebuild_summary_for_date(conn, d)
            except Exception as e:
                _log.error("eod_summary_rebuild failed %s: %s", d, e)
                conn.rollback()
            _eod_summary_progress["done"] = i + 1

        _eod_summary_progress.update({"status": "done", "current_date": None})
        _log.info("eod_summary_rebuild done: %d dates", len(dates))
        conn.close()

    threading.Thread(target=_run, daemon=True).start()
    return jsonify({"ok": True, "message": "EOD Summary rebuild dimulai di background."})


@bp_admin.route("/admin/eod-summary-status")
def admin_eod_summary_status():
    return jsonify(_eod_summary_progress)


# ── BSJP Recompute (enrich analytics + generate signals per date range) ────────

_bsjp_recompute = {
    "status": "idle", "current_date": None,
    "done": 0, "total": 0, "signals": 0, "error": None,
}


@bp_admin.route("/admin/bsjp-recompute")
def admin_bsjp_recompute():
    if not is_authed():
        return redirect("/")
    if _bsjp_recompute["status"] == "running":
        return jsonify({"ok": False, "error": "Sudah berjalan, tunggu selesai dulu."})
    date_from = request.args.get("date_from", "").strip()
    date_to   = request.args.get("date_to",   "").strip()
    if not date_from or not date_to:
        return jsonify({"ok": False, "error": "date_from dan date_to wajib (DD-MM-YYYY)"}), 400

    import threading
    from algo.analytics_bsjp import compute_bsjp_for_date
    from scraper.scraper_daily import run_bsjp_scan
    from core.db import get_scraper_db, transaction
    from core.utils import date_range
    import logging as _logging
    _log = _logging.getLogger("zenith.admin")

    def _run():
        conn = get_scraper_db()
        dates = date_range(date_from, date_to)
        _bsjp_recompute.update({
            "status": "running", "total": len(dates),
            "done": 0, "signals": 0, "error": None, "current_date": None,
        })
        _log.info("bsjp_recompute: %d dates %s → %s", len(dates), date_from, date_to)

        for i, d in enumerate(dates):
            _bsjp_recompute["current_date"] = d
            # d is DD-MM-YYYY; price_history uses YYYY-MM-DD
            d_ymd = f"{d[6:10]}-{d[3:5]}-{d[0:2]}"
            try:
                from algo.summary_rebuild import rebuild_summary_for_date
                from algo.analytics_daily import compute_analytics_for_date
                with transaction(conn):
                    rebuild_summary_for_date(conn, d)
                with transaction(conn):
                    compute_analytics_for_date(conn, d)
                with transaction(conn):
                    compute_bsjp_for_date(conn, d_ymd)
                n = run_bsjp_scan(conn, d)
                _bsjp_recompute["signals"] += n
            except Exception as e:
                _log.error("bsjp_recompute failed %s: %s", d, e)
                conn.rollback()
            _bsjp_recompute["done"] = i + 1

        _bsjp_recompute.update({"status": "done", "current_date": None})
        _log.info("bsjp_recompute done: %d dates, %d signals", len(dates), _bsjp_recompute["signals"])
        conn.close()

    threading.Thread(target=_run, daemon=True).start()
    return jsonify({"ok": True, "message": "BSJP recompute dimulai di background."})


@bp_admin.route("/admin/bsjp-recompute-status")
def admin_bsjp_recompute_status():
    if not is_authed():
        return redirect("/")
    return jsonify(_bsjp_recompute)


# ── Portfolio Recompute (refresh cached Wyckoff+BSJP simulation) ───────────────

@bp_admin.route("/admin/portfolio-recompute")
def admin_portfolio_recompute():
    from algo.algo_portfolio import request_portfolio_sim
    triggered = request_portfolio_sim()
    if not triggered:
        return jsonify({"ok": False, "error": "Sudah berjalan, tunggu selesai dulu."})
    return jsonify({"ok": True, "message": "Portfolio recompute dimulai di background."})


@bp_admin.route("/admin/portfolio-recompute-status")
def admin_portfolio_recompute_status():
    from algo.algo_portfolio import get_portfolio_status
    s = get_portfolio_status()
    if s.get("status") == "error":
        return jsonify({"status": "error", "error": s.get("result")})
    return jsonify(s)


@bp_admin.route("/admin/data-coverage")
def admin_data_coverage():
    if not is_authed():
        return redirect("/")
    from core.db import get_scraper_db, fetchall
    from datetime import datetime
    from config import WIB

    try:
        year  = int(request.args.get("year",  0) or 0)
        month = int(request.args.get("month", 0) or 0)
    except (ValueError, TypeError):
        year = month = 0
    if not year or not month:
        now   = datetime.now(WIB)
        year  = now.year
        month = now.month

    mm      = str(month).zfill(2)
    yyyy    = str(year)
    dmy_pat = f"%-{mm}-{yyyy}"   # matches DD-MM-YYYY
    ymd_pat = f"{yyyy}-{mm}-%"   # matches YYYY-MM-DD

    def _day_dict_dmy(rows):
        out = {}
        for r in rows:
            parts = (r.get("date") or "").split("-")
            if parts and parts[0].isdigit():
                out[str(int(parts[0]))] = int(r.get("cnt") or 0)
        return out

    def _day_dict_ymd(rows):
        out = {}
        for r in rows:
            d = (r.get("date") or "")[8:10]
            if d.isdigit():
                out[str(int(d))] = int(r.get("cnt") or 0)
        return out

    conn = get_scraper_db()
    try:
        sources = []

        rows = fetchall(conn,
            "SELECT date, COUNT(DISTINCT ticker) AS cnt FROM raw_messages "
            "WHERE date LIKE %s GROUP BY date", [dmy_pat])
        sources.append({"key": "raw_messages", "label": "raw_messages",
                        "group": "Mentah", "days": _day_dict_dmy(rows)})

        rows = fetchall(conn,
            "SELECT date, COUNT(DISTINCT ticker) AS cnt FROM raw_mf_messages "
            "WHERE date LIKE %s GROUP BY date", [dmy_pat])
        sources.append({"key": "raw_mf_messages", "label": "raw_mf_messages",
                        "group": "Mentah", "days": _day_dict_dmy(rows)})

        rows = fetchall(conn,
            "SELECT date, COUNT(DISTINCT ticker) AS cnt FROM eod_summary "
            "WHERE date LIKE %s GROUP BY date", [dmy_pat])
        sources.append({"key": "eod_summary", "label": "eod_summary",
                        "group": "EOD", "days": _day_dict_dmy(rows)})

        rows = fetchall(conn,
            "SELECT date, COUNT(DISTINCT ticker) AS cnt FROM price_history "
            "WHERE date LIKE %s GROUP BY date", [ymd_pat])
        sources.append({"key": "price_history", "label": "price_history",
                        "group": "EOD", "days": _day_dict_ymd(rows)})

        rows = fetchall(conn,
            "SELECT LEFT(datetime,10) AS date, COUNT(DISTINCT ticker) AS cnt "
            "FROM price_history_15m WHERE LEFT(datetime,10) LIKE %s "
            "GROUP BY LEFT(datetime,10)", [ymd_pat])
        sources.append({"key": "price_history_15m", "label": "price_history_15m",
                        "group": "Intraday", "days": _day_dict_ymd(rows)})

        rows = fetchall(conn,
            "SELECT date, COUNT(*) AS cnt FROM bsjp_signals "
            "WHERE date LIKE %s GROUP BY date", [dmy_pat])
        sources.append({"key": "bsjp_signals", "label": "bsjp_signals",
                        "group": "BSJP", "days": _day_dict_dmy(rows)})

        rows = fetchall(conn,
            "SELECT date, COUNT(*) AS cnt FROM bsjp_results "
            "WHERE date LIKE %s GROUP BY date", [dmy_pat])
        sources.append({"key": "bsjp_results", "label": "bsjp_results",
                        "group": "BSJP", "days": _day_dict_dmy(rows)})

        rows = fetchall(conn,
            "SELECT date, COUNT(DISTINCT ticker) AS cnt FROM eod_summary "
            "WHERE phase IS NOT NULL AND date LIKE %s GROUP BY date", [dmy_pat])
        sources.append({"key": "wyckoff_signals", "label": "wyckoff_signals",
                        "group": "SIGNALS", "days": _day_dict_dmy(rows)})

        return jsonify({"year": year, "month": month, "sources": sources})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500
    finally:
        conn.close()


# ── Corporate Actions (stock split / rights issue) ────────────────────────────
# status='confirmed' → excluded from Portfolio, BSJP signals and trade history.
# status='suspected' → auto-detected, shown for review, excludes nothing.
# status='rejected'  → tombstone so the detector stops re-flagging the ticker.

@bp_admin.route("/admin/corporate-events")
def admin_corporate_events_list():
    from core.db import get_db, fetchall
    rows = fetchall(get_db(), """
        SELECT ticker, event_type, event_date, detail, status, detected_at FROM corporate_events
        ORDER BY SUBSTRING(event_date,7,4)||SUBSTRING(event_date,4,2)||SUBSTRING(event_date,1,2) DESC
    """)
    return jsonify([dict(r) for r in rows])


@bp_admin.route("/admin/corporate-events/add", methods=["POST"])
def admin_corporate_events_add():
    from core.db import get_db, execute
    import time
    data = request.get_json() or {}
    ticker      = (data.get("ticker") or "").strip().upper()
    event_type  = data.get("event_type") or ""
    event_date  = (data.get("event_date") or "").strip()
    detail      = (data.get("detail") or "").strip() or None
    if not ticker or event_type not in ("stock_split", "rights_issue") or len(event_date) != 10:
        return jsonify({"ok": False, "error": "ticker, event_type (stock_split/rights_issue), event_date (DD-MM-YYYY) wajib"}), 400
    conn = get_db()
    execute(conn, """
        INSERT INTO corporate_events (ticker, event_type, event_date, detail, fetched_at)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (ticker, event_type, event_date) DO UPDATE SET detail = EXCLUDED.detail
    """, [ticker, event_type, event_date, detail, int(time.time())])
    conn.commit()
    return jsonify({"ok": True})


@bp_admin.route("/admin/corporate-events/delete", methods=["POST"])
def admin_corporate_events_delete():
    from core.db import get_db, execute
    data = request.get_json() or {}
    ticker     = data.get("ticker") or ""
    event_type = data.get("event_type") or ""
    event_date = data.get("event_date") or ""
    conn = get_db()
    execute(conn, """
        DELETE FROM corporate_events WHERE ticker=%s AND event_type=%s AND event_date=%s
    """, [ticker, event_type, event_date])
    conn.commit()
    return jsonify({"ok": True})


@bp_admin.route("/admin/corporate-events/approve", methods=["POST"])
def admin_corporate_events_approve():
    """Confirm a suspected CA. Retypes the row to a real event_type — an
    approved CA should carry its true type, not 'auto_detected'."""
    from core.db import get_db, execute
    data       = request.get_json() or {}
    ticker     = (data.get("ticker") or "").strip().upper()
    event_type = data.get("event_type") or ""
    event_date = (data.get("event_date") or "").strip()
    new_type   = data.get("new_type") or "stock_split"
    if not ticker or new_type not in ("stock_split", "rights_issue"):
        return jsonify({"ok": False, "error": "ticker + new_type (stock_split/rights_issue) wajib"}), 400
    conn = get_db()
    try:
        execute(conn, """
            UPDATE corporate_events SET status = 'confirmed', event_type = %s
            WHERE ticker = %s AND event_type = %s AND event_date = %s
        """, [new_type, ticker, event_type, event_date])
        conn.commit()
    except Exception as e:
        conn.rollback()
        return jsonify({"ok": False, "error": str(e)}), 400
    return jsonify({"ok": True})


@bp_admin.route("/admin/corporate-events/reject", methods=["POST"])
def admin_corporate_events_reject():
    """Dismiss a suspected CA. Keeps the row as a tombstone — deleting it would
    make the detector re-flag the same ticker every night."""
    from core.db import get_db, execute
    data = request.get_json() or {}
    conn = get_db()
    execute(conn, """
        UPDATE corporate_events SET status = 'rejected'
        WHERE ticker=%s AND event_type=%s AND event_date=%s
    """, [data.get("ticker") or "", data.get("event_type") or "", data.get("event_date") or ""])
    conn.commit()
    return jsonify({"ok": True})
