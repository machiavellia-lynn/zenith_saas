"""routes/routes_bsjp.py — BSJP Signal endpoints"""
from flask import Blueprint, jsonify, request, render_template
from core.db import get_db, fetchall
from core.auth import require_auth
from datetime import datetime, timezone, timedelta

bp_bsjp = Blueprint("bsjp", __name__)
WIB = timezone(timedelta(hours=7))


def _today_dmy() -> str:
    return datetime.now(WIB).strftime("%d-%m-%Y")


@bp_bsjp.route("/bsjp")
@require_auth
def page_bsjp():
    return render_template("bsjp.html")


@bp_bsjp.route("/api/bsjp/signals")
@require_auth
def api_bsjp_signals():
    date_str = request.args.get("date") or _today_dmy()
    rows = fetchall(get_db(),
        "SELECT * FROM bsjp_signals WHERE date = %s ORDER BY day_rank ASC NULLS LAST",
        [date_str])
    return jsonify({"date": date_str, "count": len(rows), "signals": rows})


@bp_bsjp.route("/api/bsjp/results")
@require_auth
def api_bsjp_results():
    date_str = request.args.get("date") or _today_dmy()
    rows = fetchall(get_db(),
        "SELECT * FROM bsjp_results WHERE date = %s ORDER BY id",
        [date_str])
    return jsonify({"date": date_str, "count": len(rows), "results": rows})


@bp_bsjp.route("/api/bsjp/compute", methods=["POST"])
@require_auth
def api_bsjp_compute():
    """Trigger PRE signal generation untuk tanggal tertentu (DD-MM-YYYY)."""
    body     = request.get_json(silent=True) or {}
    date_str = body.get("date") or _today_dmy()
    from algo.analytics_bsjp import generate_bsjp_signals
    n = generate_bsjp_signals(get_db(), date_str)
    return jsonify({"date": date_str, "signals_generated": n})


@bp_bsjp.route("/api/bsjp/backfill", methods=["POST"])
@require_auth
def api_bsjp_backfill():
    """Backfill bsjp_signals untuk date range (DD-MM-YYYY). Runs in background."""
    body      = request.get_json(silent=True) or {}
    date_from = body.get("date_from")
    date_to   = body.get("date_to")
    if not date_from or not date_to:
        return jsonify({"error": "date_from and date_to required (DD-MM-YYYY)"}), 400
    from algo.analytics_bsjp import request_bsjp_backfill
    triggered = request_bsjp_backfill(date_from, date_to)
    return jsonify({"triggered": triggered, "date_from": date_from, "date_to": date_to})


@bp_bsjp.route("/api/bsjp/backfill/status")
@require_auth
def api_bsjp_backfill_status():
    from algo.analytics_bsjp import get_backfill_status
    return jsonify(get_backfill_status())
