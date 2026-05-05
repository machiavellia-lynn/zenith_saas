"""
routes_backtest.py — Blueprint: /backtest, /api/backtest, /api/ticker-fitness
RULE: Routing only. All backtest computation in algo_backtest.py.
"""
from flask import Blueprint, render_template, jsonify, request, redirect
from core.auth import is_authed

bp_backtest = Blueprint("backtest", __name__)


@bp_backtest.route("/backtest")
def backtest_page():
    if not is_authed():
        return redirect("/")
    return render_template("backtest.html")


@bp_backtest.route("/api/backtest")
def api_backtest():
    if not is_authed():
        return redirect("/")
    from algo.algo_backtest import get_backtest_result
    result = get_backtest_result()
    if not result:
        return jsonify({"status": "not_ready"})
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
