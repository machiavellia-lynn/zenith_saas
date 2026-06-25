"""
routes_portfolio.py — Blueprint: /portfolio, /api/portfolio
RULE: Routing only. All simulation logic in algo/algo_portfolio.py.
"""
from flask import Blueprint, render_template, jsonify, request, redirect
from core.auth import is_authed

bp_portfolio = Blueprint("portfolio", __name__)


@bp_portfolio.route("/portfolio")
def portfolio_page():
    if not is_authed():
        return redirect("/")
    return render_template("portfolio.html")


@bp_portfolio.route("/api/portfolio")
def api_portfolio():
    if not is_authed():
        return redirect("/")
    from algo.algo_portfolio import (
        get_portfolio_result, get_portfolio_status, request_portfolio_sim,
    )

    # Date-range change: filter cached result in-memory (fast path, no DB re-run)
    if request.args.get("run") == "1":
        date_from = request.args.get("date_from") or None
        date_to   = request.args.get("date_to") or None
        from algo.algo_portfolio import filter_result
        cached = get_portfolio_result()
        if cached:
            return jsonify(filter_result(cached, date_from, date_to))
        # No cache yet — trigger full simulation
        triggered = request_portfolio_sim()
        return jsonify({"triggered": triggered})

    # Status polling while running
    if request.args.get("status") == "1":
        return jsonify(get_portfolio_status())

    # Return cached result (auto-trigger over all data on first visit)
    result = get_portfolio_result()
    if not result:
        request_portfolio_sim()  # no-op if already running
        return jsonify(get_portfolio_status())
    return jsonify(result)
