"""
routes_portfolio.py — Blueprint: /portfolio, /api/portfolio
RULE: Routing only. All simulation logic in algo/algo_portfolio.py.
"""
from flask import Blueprint, render_template, jsonify, request, redirect
from core.auth import is_authed, current_universe

bp_portfolio = Blueprint("portfolio", __name__)


def _with_ihsg(result: dict) -> dict:
    """Attach IHSG daily closes aligned 1:1 with the result's date axis.

    Benchmark overlay only — decorative, so a Yahoo failure degrades to nulls
    rather than breaking the response. Returns a shallow copy: the plain path
    hands back the cached simulation object itself, which must not be mutated.
    """
    from data.price_cache import get_ihsg_history

    axis = result.get("axis_dates") or []
    if not axis:
        return result

    hist = get_ihsg_history()
    series, last = [], None
    for d in axis:
        v = hist.get(d)
        if v is None:
            # Carry the previous close across days IDX has no bar for (the axis
            # unions price_history, which can hold dates Yahoo doesn't return).
            v = last
        else:
            last = v
        series.append(v)

    out = dict(result)
    out["ihsg"] = series
    return out


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
    # since the underlying simulation is expensive to run.
    # The only request-driven knob here is the date range, which is a free in-memory
    # slice of the one dev-configured cached result — never a new simulation.
    # Any "what-if my own budget" recalculation happens client-side in the browser,
    # scaling the returned trades/equity — see templates/portfolio.html's viewData().
    # Sharia accounts get their own simulation, not a filtered view of the full
    # one: BSJP re-ranks per universe, so its trades are not a subset.
    universe = current_universe()

    if request.args.get("run") == "1":
        date_from = request.args.get("date_from") or None
        date_to   = request.args.get("date_to") or None

        cached = get_portfolio_result(universe)
        if cached:
            return jsonify(_with_ihsg(filter_result(cached, date_from, date_to)))

        triggered = request_portfolio_sim(universe=universe)
        return jsonify({"triggered": triggered})

    # Status polling while running
    if request.args.get("status") == "1":
        return jsonify(get_portfolio_status(universe))

    # Return cached result (auto-trigger over all data on first visit)
    result = get_portfolio_result(universe)
    if not result:
        request_portfolio_sim(universe=universe)  # no-op if already running
        return jsonify(get_portfolio_status(universe))
    return jsonify(_with_ihsg(result))
