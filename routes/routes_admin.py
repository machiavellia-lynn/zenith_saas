"""
routes_admin.py — Blueprint: /admin/*
RULE: Routing + status reporting only. All ops (rebuild, backfill, scraper) in dedicated modules.
"""
import os
from flask import Blueprint, render_template, jsonify, request, redirect
from core.auth import is_authed

bp_admin = Blueprint("admin", __name__)


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
        return jsonify({"error": "date required"}), 400
    from algo.analytics_daily import compute_analytics_for_date
    from core.db import get_scraper_db, transaction
    conn = get_scraper_db()
    try:
        with transaction(conn):
            n = compute_analytics_for_date(conn, date_str)
        return jsonify({"ok": True, "updated": n})
    finally:
        conn.close()


@bp_admin.route("/admin/recompute-analytics-all")
def recompute_analytics_all():
    if not is_authed():
        return redirect("/")
    import threading
    import logging as _logging
    _log = _logging.getLogger("zenith.admin")

    def _run():
        from algo.analytics_daily import compute_analytics_for_date
        from core.db import get_scraper_db, fetchall
        conn = get_scraper_db()
        try:
            dates = [r["date"] for r in fetchall(conn,
                "SELECT date FROM (SELECT DISTINCT date FROM eod_summary) sub ORDER BY TO_DATE(date,'DD-MM-YYYY')")]
            _log.info("Recomputing analytics for %d dates", len(dates))
            total = 0
            for d in dates:
                try:
                    n = compute_analytics_for_date(conn, d)
                    total += n
                    conn.commit()
                except Exception as e:
                    conn.rollback()
                    _log.error("analytics failed for %s: %s", d, e)
            _log.info("Recompute-all done: %d rows updated", total)
        finally:
            conn.close()

    threading.Thread(target=_run, daemon=True).start()
    return jsonify({"ok": True, "message": "Analytics recompute for all dates started in background"})


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
