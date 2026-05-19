"""
routes_admin.py — Blueprint: /admin/*
RULE: Routing + status reporting only. All ops (rebuild, backfill, scraper) in dedicated modules.
"""
import os
from flask import Blueprint, render_template, jsonify, request, redirect
from core.auth import is_authed

bp_admin = Blueprint("admin", __name__)

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


@bp_admin.route("/admin/backfill-prices")
def admin_backfill_prices():
    if not is_authed():
        return redirect("/")
    days      = int(request.args.get("days", 30))
    date_from = request.args.get("date_from", "").strip() or None
    date_to   = request.args.get("date_to", "").strip() or None

    from data.price_fetch import backfill_prices
    from algo.analytics_daily import compute_analytics_for_date
    from core.db import get_scraper_db, fetchall
    from datetime import datetime
    import logging
    log = logging.getLogger("zenith.admin")

    conn = get_scraper_db()
    try:
        prices_updated = backfill_prices(conn, days=days, date_from=date_from, date_to=date_to)

        from data.price_fetch import backfill_price_history_200d
        backfill_price_history_200d(conn)
        conn.commit()

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
            for d in dates_to_recompute:
                try:
                    n = compute_analytics_for_date(conn, d)
                    analytics_recomputed += n
                    conn.commit()
                except Exception as e:
                    log.error(f"Analytics recompute failed for {d}: {e}")
                    conn.rollback()

        return jsonify({
            "ok": True,
            "prices_updated": prices_updated,
            "analytics_recomputed": analytics_recomputed,
            "date_from": date_from,
            "date_to": date_to,
            "days": days if not date_from else None,
        })
    except Exception as e:
        log.error(f"Backfill prices failed: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500
    finally:
        conn.close()


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


@bp_admin.route("/admin/backfill-intraday")
def admin_backfill_intraday():
    if not is_authed():
        return redirect("/")
    date_from = request.args.get("date_from", "").strip()
    date_to   = request.args.get("date_to",   "").strip()
    if not date_from or not date_to:
        return jsonify({"ok": False, "error": "date_from dan date_to wajib (DD-MM-YYYY)"}), 400

    import threading
    from data.price_fetch import backfill_intraday_15m
    from core.db import get_scraper_db
    import logging as _logging
    _log = _logging.getLogger("zenith.admin")

    def _run():
        conn = get_scraper_db()
        try:
            res = backfill_intraday_15m(conn, date_from, date_to)
            conn.commit()
            _log.info("backfill_intraday_15m done: %s", res)
        except Exception as e:
            conn.rollback()
            _log.error("backfill_intraday_15m failed: %s", e)
        finally:
            conn.close()

    threading.Thread(target=_run, daemon=True).start()
    return jsonify({"ok": True, "message": f"Intraday 15m backfill dimulai ({date_from} → {date_to}). Cek server log untuk progress."})


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

    import threading, time as _time
    from datetime import datetime, timedelta
    from data.price_fetch import _fetch_ohlcv_history
    from core.db import get_scraper_db, fetchall, execute
    from config import WIB
    import logging as _logging
    _log = _logging.getLogger("zenith.admin")

    fmt = "%d-%m-%Y"
    try:
        dt_f = datetime.strptime(date_from, fmt).replace(tzinfo=WIB)
        dt_t = datetime.strptime(date_to,   fmt).replace(tzinfo=WIB) + timedelta(days=1)
    except ValueError:
        return jsonify({"ok": False, "error": "Format tanggal salah, gunakan DD-MM-YYYY"}), 400

    _ohlcv_daily_all.update({
        "status": "idle", "current_ticker": None,
        "done": 0, "total": 0, "rows_total": 0,
        "error": None, "date_from": date_from, "date_to": date_to,
    })

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
        finally:
            conn.close()

        _ohlcv_daily_all.update({
            "status": "running", "total": len(tickers),
            "done": 0, "rows_total": 0, "error": None,
        })
        _log.info("ohlcv_daily_all: %d tickers, %s → %s", len(tickers), date_from, date_to)

        for i, ticker in enumerate(tickers):
            _ohlcv_daily_all["current_ticker"] = ticker
            conn = get_scraper_db()
            try:
                _, ohlcv_rows = _fetch_ohlcv_history(ticker, dt_f, dt_t)
                inserted = 0
                for r in ohlcv_rows:
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
                        _log.warning("ohlcv_daily insert fail ticker=%s date=%s: %s", ticker, r.get("date"), e)
                conn.commit()
                _ohlcv_daily_all["rows_total"] += inserted
            except Exception as e:
                conn.rollback()
                _log.error("ohlcv_daily_all failed ticker=%s: %s", ticker, e)
            finally:
                conn.close()

            _ohlcv_daily_all["done"] = i + 1
            if i < len(tickers) - 1:
                _time.sleep(0.5)

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
        return "Unauthorized", 401
    data = request.get_data()
    if not data:
        return "No file data", 400
    from config import TG_SESSION_PATH
    os.makedirs(os.path.dirname(TG_SESSION_PATH) or "/data", exist_ok=True)
    with open(TG_SESSION_PATH, "wb") as f:
        f.write(data)
    return f"✅ Session uploaded ({len(data):,} bytes) → {TG_SESSION_PATH}"


@bp_admin.route("/admin/users")
def list_users():
    if not is_authed():
        return jsonify({"error": "unauthorized"}), 401
    from core.db import get_db, fetchall
    conn = get_db()
    users = fetchall(conn, "SELECT id, username, role, created_at FROM users ORDER BY id")
    return jsonify([dict(u) for u in users])


@bp_admin.route("/admin/users/add", methods=["POST"])
def add_user():
    if not is_authed():
        return jsonify({"ok": False}), 401
    data = request.get_json() or {}
    username = (data.get("username") or "").strip()
    password = (data.get("password") or "").strip()
    role     = data.get("role", "guest")
    if not username or not password:
        return jsonify({"ok": False, "error": "Username dan password wajib"})
    if role not in ("admin", "guest"):
        return jsonify({"ok": False, "error": "Role harus admin atau guest"})
    from core.auth import register
    ok = register(username, password, role)
    if ok:
        return jsonify({"ok": True})
    return jsonify({"ok": False, "error": "Username sudah dipakai"})


@bp_admin.route("/admin/users/delete/<int:user_id>", methods=["POST"])
def delete_user(user_id):
    if not is_authed():
        return jsonify({"ok": False}), 401
    from core.db import get_db, execute, transaction
    conn = get_db()
    with transaction(conn):
        execute(conn, "DELETE FROM users WHERE id = %s", [user_id])
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
    from core.db import get_scraper_db, fetchall, transaction
    import logging as _logging
    _log = _logging.getLogger("zenith.admin")

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
            _wyckoff_recompute.update({"status": "error", "error": str(e)})
            conn.close()
            return

        dates = [r["date"] for r in rows]
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
    from core.db import get_scraper_db, fetchall, transaction
    import logging as _logging
    _log = _logging.getLogger("zenith.admin")

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
            _bsjp_recompute.update({"status": "error", "error": str(e)})
            conn.close()
            return

        dates = [r["date"] for r in rows]
        _bsjp_recompute.update({
            "status": "running", "total": len(dates),
            "done": 0, "signals": 0, "error": None, "current_date": None,
        })
        _log.info("bsjp_recompute: %d dates %s → %s", len(dates), date_from, date_to)

        for i, d in enumerate(dates):
            _bsjp_recompute["current_date"] = d
            try:
                with transaction(conn):
                    compute_bsjp_for_date(conn, d)
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
