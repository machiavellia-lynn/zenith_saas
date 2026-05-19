"""
routes/routes_bsjp.py — BSJP Signal endpoints

GET /bsjp              → halaman BSJP signals (HTML)
GET /api/bsjp/signals  → list signal hari ini (JSON)
GET /api/bsjp/history  → history signal N hari lalu (JSON)
"""
from flask import Blueprint, jsonify, request, render_template
from core.db import get_db, fetchall
from core.auth import require_auth
from datetime import datetime, timezone, timedelta

bp_bsjp = Blueprint("bsjp", __name__)
WIB     = timezone(timedelta(hours=7))


@bp_bsjp.route("/bsjp")
@require_auth
def page_bsjp():
    return render_template("bsjp.html")


@bp_bsjp.route("/api/bsjp/signals")
@require_auth
def api_bsjp_signals():
    """
    Return list signal BSJP hari ini, sorted by score DESC.
    Query params:
      date   — DD-MM-YYYY (default: hari ini)
      status — ESTIMASI | CONFIRMED | INVALID | ALL (default: ALL)
    """
    date_str = request.args.get("date") or _today_dmy()
    status   = request.args.get("status", "ALL").upper()

    sql    = "SELECT * FROM bsjp_signals WHERE date = %s"
    params = [date_str]
    if status != "ALL":
        sql    += " AND status = %s"
        params.append(status)
    sql += " ORDER BY score DESC NULLS LAST"

    rows = fetchall(get_db(), sql, params)
    return jsonify({"success": True, "date": date_str, "count": len(rows), "signals": rows})


@bp_bsjp.route("/api/bsjp/history")
@require_auth
def api_bsjp_history():
    """
    Query params:
      ticker — filter by ticker (opsional)
      days   — lookback (default 30)
      status — filter status (default CONFIRMED)
    """
    ticker = request.args.get("ticker", "").upper() or None
    days   = int(request.args.get("days", 30))
    status = request.args.get("status", "CONFIRMED").upper()

    sql    = "SELECT * FROM bsjp_signals WHERE status = %s"
    params = [status]
    if ticker:
        sql    += " AND ticker = %s"
        params.append(ticker)
    sql += " ORDER BY date DESC LIMIT %s"
    params.append(days * 50)

    rows = fetchall(get_db(), sql, params)
    return jsonify({"success": True, "count": len(rows), "signals": rows})


def _today_dmy() -> str:
    return datetime.now(WIB).strftime("%d-%m-%Y")
