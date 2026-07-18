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
        get_portfolio_result, get_portfolio_status, request_portfolio_sim, filter_result,
    )

    # Capital/allocation are NOT client-configurable — they're fixed in config.py
    # (PF_BSJP_INITIAL_EQUITY, PF_BSJP_ALLOC, ...) and only change via a code deploy,
    # since the underlying simulation is what actually calls the paid DataSectors API.
    # The only request-driven knob here is the date range, which is a free in-memory
    # slice of the one dev-configured cached result — never a new simulation.
    # Any "what-if my own budget" recalculation happens client-side in the browser,
    # scaling the returned trades/equity — see templates/portfolio.html's viewData().
    if request.args.get("run") == "1":
        date_from = request.args.get("date_from") or None
        date_to   = request.args.get("date_to") or None

        cached = get_portfolio_result()
        if cached:
            return jsonify(filter_result(cached, date_from, date_to))

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
