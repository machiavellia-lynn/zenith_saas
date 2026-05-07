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
    return jsonify(get_backfill_status())


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


@bp_admin.route("/admin/backfill-prices")
def admin_backfill_prices():
    if not is_authed():
        return redirect("/")
    days      = int(request.args.get("days", 30))
    date_from = request.args.get("date_from", "").strip()
    date_to   = request.args.get("date_to", "").strip()
    delay_ms  = int(request.args.get("delay_ms", 333))

    import threading
    from data.price_fetch import backfill_prices
    from algo.analytics_daily import compute_analytics_for_date
    from core.db import get_scraper_db, fetchall
    from datetime import datetime
    import logging

    def _backfill_task():
        log = logging.getLogger("zenith.admin")
        conn = get_scraper_db()
        try:
            prices_updated = backfill_prices(
                conn,
                days=days,
                date_from=date_from,
                date_to=date_to,
                delay_ms=delay_ms
            )

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
                        compute_analytics_for_date(conn, d)
                        conn.commit()
                    except Exception as e:
                        log.error(f"Analytics recompute failed for {d}: {e}")
                        conn.rollback()
            log.info(f"✅ Backfill complete: {prices_updated} prices updated")
        except Exception as e:
            log.error(f"❌ Backfill failed: {e}")
        finally:
            conn.close()

    threading.Thread(target=_backfill_task, daemon=True).start()
    return jsonify({
        "ok": True,
        "status": "Backfill started in background",
        "date_from": date_from or None,
        "date_to": date_to or None,
        "days": days if not date_from else None,
    })


@bp_admin.route("/admin/backfill-200d")
def admin_backfill_200d():
    if not is_authed():
        return redirect("/")
    import threading
    from data.price_fetch import backfill_price_history_200d
    from core.db import get_db
    threading.Thread(target=lambda: backfill_price_history_200d(get_db()), daemon=True).start()
    return jsonify({"ok": True})


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
