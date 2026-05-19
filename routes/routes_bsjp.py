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
