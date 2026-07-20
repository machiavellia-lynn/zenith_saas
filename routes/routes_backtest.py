"""
routes_backtest.py — Blueprint: /api/backtest, /api/backtest/bsjp, /api/ticker-fitness
RULE: Routing only. All backtest computation in algo_backtest.py.
"""
from flask import Blueprint, jsonify, request, redirect
from core.auth import is_authed, current_universe

bp_backtest = Blueprint("backtest", __name__)


@bp_backtest.route("/api/backtest")
def api_backtest():
    if not is_authed():
        return redirect("/")
    from algo.algo_backtest import get_backtest_result, get_backtest_status, request_backtest

    # Trigger new backtest run
    if request.args.get("run") == "1":
        days      = int(request.args.get("days", 30))
        date_from = request.args.get("date_from") or None
        date_to   = request.args.get("date_to") or None
        triggered = request_backtest(days=days, date_from=date_from, date_to=date_to)
        return jsonify({"triggered": triggered})

    # Status polling while running
    if request.args.get("status") == "1":
        return jsonify(get_backtest_status())

    # Return cached result
    result = get_backtest_result()
    if not result:
        return jsonify({"error": "No data yet. Click RUN BACKTEST."})
    return jsonify(result)


@bp_backtest.route("/api/backtest/bsjp")
def api_backtest_bsjp():
    if not is_authed():
        return redirect("/")
    from algo.algo_backtest import get_bsjp_result, get_bsjp_status, request_bsjp_backtest

    if request.args.get("run") == "1":
        date_from = request.args.get("date_from") or None
        date_to   = request.args.get("date_to") or None
        triggered = request_bsjp_backtest(date_from=date_from, date_to=date_to)
        return jsonify({"triggered": triggered})

    if request.args.get("status") == "1":
        return jsonify(get_bsjp_status())

    # One run computes both universes, so a sharia account reads its slice from
    # the same cache rather than kicking off a second backtest.
    result = get_bsjp_result(current_universe())
    if not result:
        request_bsjp_backtest()  # auto-trigger with all available data; no-op if already running
        return jsonify(get_bsjp_status())
    return jsonify(result)


@bp_backtest.route("/api/ticker-fitness")
def api_ticker_fitness():
    if not is_authed():
        return redirect("/")
    ticker = request.args.get("ticker", "").upper()
    if not ticker:
        return jsonify({"error": "ticker required"}), 400
    from algo.algo_backtest import get_ticker_fitness
    from core.db import get_db
    return jsonify(get_ticker_fitness(get_db(), ticker))
