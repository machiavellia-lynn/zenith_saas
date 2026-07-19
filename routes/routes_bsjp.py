"""routes/routes_bsjp.py — BSJP Signal endpoints"""
from flask import Blueprint, jsonify, request, render_template
from core.db import get_db, fetchall
from core.auth import require_auth, current_universe
from algo.corporate_actions import ca_tickers, suspected_tickers
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
    conn = get_db()
    # Sharia accounts read their own TOP_N slice, ranked over sharia candidates
    # only — not the full-universe rows with the non-sharia ones removed, which
    # would leave the freed slots empty instead of promoted. See run_bsjp_scan.
    rows = fetchall(conn,
        "SELECT * FROM bsjp_signals WHERE date = %s AND universe = %s "
        "ORDER BY day_rank ASC NULLS LAST",
        [date_str, current_universe()])
    # Backstop: run_bsjp_scan now filters CA tickers before insert, but rows
    # written before that landed still carry them — drop them on read.
    ca_set   = ca_tickers(conn)
    susp_set = suspected_tickers(conn)
    rows = [r for r in rows if r["ticker"] not in ca_set]
    for r in rows:
        r["is_ca_suspected"] = r["ticker"] in susp_set
    return jsonify({"date": date_str, "count": len(rows), "signals": rows})


@bp_bsjp.route("/api/bsjp/results")
@require_auth
def api_bsjp_results():
    date_str = request.args.get("date") or _today_dmy()
    # bsjp_results carries no universe of its own — an exit outcome for a
    # (date, ticker) is the same whichever universe picked it — so scope it to
    # the tickers this account's signals actually contain.
    rows = fetchall(get_db(), """
        SELECT r.* FROM bsjp_results r
        WHERE r.date = %s
          AND EXISTS (SELECT 1 FROM bsjp_signals s
                      WHERE s.date = r.date AND s.ticker = r.ticker
                        AND s.universe = %s)
        ORDER BY r.id
    """, [date_str, current_universe()])
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
