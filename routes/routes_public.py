"""
routes_public.py — Blueprint: /api/public/performance
Read-only export for the external portfolio site. No new computation and no
new storage — reshapes the already-cached get_portfolio_result() (same data
/api/portfolio already serves) plus one IHSG history call reusing the same
Yahoo endpoint price_cache._fetch_ihsg() uses for the live quote.
"""
import os
import requests
from flask import Blueprint, jsonify, request

bp_public = Blueprint("public", __name__)

EXPORT_SECRET = os.environ.get("PORTFOLIO_EXPORT_SECRET", "")


def _fetch_ihsg_history(range_: str = "2y") -> dict:
    """Raw {dates: [epoch], closes: [float]} for the external portfolio site.

    Deliberately NOT price_cache.get_ihsg_history(), which returns
    {DD-MM-YYYY: close} for the /portfolio benchmark line. Same upstream, two
    different shapes: this one is a published contract consumed by the live
    portfolio site, so collapsing the two would break it.
    """
    try:
        resp = requests.get(
            "https://query1.finance.yahoo.com/v8/finance/chart/%5EJKSE",
            headers={"User-Agent": "Mozilla/5.0"},
            params={"interval": "1d", "range": range_},
            timeout=8,
        )
        result = resp.json().get("chart", {}).get("result", [None])[0]
        if not result:
            return {"dates": [], "closes": []}
        timestamps = result.get("timestamp", []) or []
        closes = result.get("indicators", {}).get("quote", [{}])[0].get("close", []) or []
        return {"dates": timestamps, "closes": closes}
    except Exception:
        return {"dates": [], "closes": []}


def _algo_slice(result: dict, name: str) -> dict:
    stats = result[name]["stats"]
    return {
        "equity": result["equity"][name],
        "profit_factor": stats.get("profit_factor"),
        "total_trades": stats.get("total_trades"),
        "win_rate": stats.get("win_rate"),
        "total_return_pct": stats.get("total_return_pct"),
    }


@bp_public.route("/api/public/performance")
def api_public_performance():
    if not EXPORT_SECRET or request.args.get("secret") != EXPORT_SECRET:
        return jsonify({"error": "unauthorized"}), 401

    from algo.algo_portfolio import get_portfolio_result
    result = get_portfolio_result()
    if not result:
        return jsonify({"error": "no cached result yet — visit /portfolio once to trigger it"}), 503

    return jsonify({
        "labels": result["equity"]["labels"],
        "ihsg": _fetch_ihsg_history(),
        "bsjp": _algo_slice(result, "bsjp"),
        "wyckoff": _algo_slice(result, "wyckoff"),
    })
