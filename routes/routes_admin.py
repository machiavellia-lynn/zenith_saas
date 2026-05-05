"""
routes_admin.py — Blueprint: /admin/*
RULE: Routing + status reporting only. All ops (rebuild, backfill, scraper) in dedicated modules.
"""
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
        return jsonify({"error": "date required"}), 400
    from algo.summary_rebuild import rebuild_summary_for_date
    from core.db import get_db, transaction
    conn = get_db()
    with transaction(conn):
        rebuild_summary_for_date(conn, date_str)
    return jsonify({"ok": True})


@bp_admin.route("/admin/recompute-analytics")
def recompute_analytics():
    if not is_authed():
        return redirect("/")
    date_str = request.args.get("date", "")
    if not date_str:
        return jsonify({"error": "date required"}), 400
    from algo.analytics_daily import compute_analytics_for_date
    from core.db import get_db, transaction
    conn = get_db()
    with transaction(conn):
        n = compute_analytics_for_date(conn, date_str)
    return jsonify({"ok": True, "updated": n})


@bp_admin.route("/admin/backfill-prices")
def admin_backfill_prices():
    if not is_authed():
        return redirect("/")
    days = int(request.args.get("days", 30))
    import threading
    from data.price_fetch import backfill_prices
    from core.db import get_db
    threading.Thread(target=lambda: backfill_prices(get_db(), days=days), daemon=True).start()
    return jsonify({"ok": True, "days": days})


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
