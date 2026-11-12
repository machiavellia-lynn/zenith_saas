"""
routes_api.py — Blueprint: /api/v1/*
RULE: Read-only external data API, gated by X-API-Key (core.api_auth). Routing +
      filter parsing only — no business logic, no writes.
"""
import json
import logging
from flask import Blueprint, jsonify, request

from core.api_auth import require_api_key
from core.db import get_db, fetchall

bp_api = Blueprint("api_v1", __name__, url_prefix="/api/v1")
log = logging.getLogger("zenith.routes.api")


@bp_api.before_request
def _guard():
    return require_api_key()


# ── Helpers ──────────────────────────────────────────────────────────────────

def _pagination():
    try:
        limit = int(request.args.get("limit", 500))
    except (TypeError, ValueError):
        limit = 500
    limit = max(1, min(limit, 5000))
    try:
        offset = int(request.args.get("offset", 0))
    except (TypeError, ValueError):
        offset = 0
    return limit, max(0, offset)


def _date_clause(col: str, date_from: str | None, date_to: str | None):
    """col stores DD-MM-YYYY text. Returns (sql_fragment_or_None, params)."""
    expr = f"TO_DATE({col}, 'DD-MM-YYYY')"
    if date_from and date_to:
        return f"{expr} BETWEEN TO_DATE(%s, 'DD-MM-YYYY') AND TO_DATE(%s, 'DD-MM-YYYY')", [date_from, date_to]
    if date_from:
        return f"{expr} >= TO_DATE(%s, 'DD-MM-YYYY')", [date_from]
    if date_to:
        return f"{expr} <= TO_DATE(%s, 'DD-MM-YYYY')", [date_to]
    return None, []


def _fetch(table: str, order_expr: str, where: list[str], params: list, limit: int, offset: int):
    conn = get_db()
    sql = f"SELECT * FROM {table}"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += f" ORDER BY {order_expr} LIMIT %s OFFSET %s"
    return fetchall(conn, sql, params + [limit, offset])


def _envelope(rows: list[dict], limit: int, offset: int):
    return jsonify({"count": len(rows), "limit": limit, "offset": offset, "data": rows})


# ── eod_summary ──────────────────────────────────────────────────────────────
@bp_api.route("/eod-summary")
def api_eod_summary():
    ticker = request.args.get("ticker")
    limit, offset = _pagination()
    where, params = [], []
    if ticker:
        where.append("ticker = %s")
        params.append(ticker.upper())
    clause, dparams = _date_clause("date", request.args.get("date_from"), request.args.get("date_to"))
    if clause:
        where.append(clause)
        params += dparams
    rows = _fetch("eod_summary", "TO_DATE(date, 'DD-MM-YYYY') DESC, ticker", where, params, limit, offset)
    return _envelope(rows, limit, offset)


# ── price_history ────────────────────────────────────────────────────────────
@bp_api.route("/price-history")
def api_price_history():
    ticker = request.args.get("ticker")
    limit, offset = _pagination()
    where, params = [], []
    if ticker:
        where.append("ticker = %s")
        params.append(ticker.upper())
    clause, dparams = _date_clause("date", request.args.get("date_from"), request.args.get("date_to"))
    if clause:
        where.append(clause)
        params += dparams
    rows = _fetch("price_history", "TO_DATE(date, 'DD-MM-YYYY') DESC, ticker", where, params, limit, offset)
    return _envelope(rows, limit, offset)


# ── price_history_15m ────────────────────────────────────────────────────────
@bp_api.route("/price-history-15m")
def api_price_history_15m():
    ticker = request.args.get("ticker")
    date = request.args.get("date")  # YYYY-MM-DD
    limit, offset = _pagination()
    where, params = [], []
    if ticker:
        where.append("ticker = %s")
        params.append(ticker.upper())
    if date:
        where.append("LEFT(datetime, 10) = %s")
        params.append(date)
    rows = _fetch("price_history_15m", "datetime DESC, ticker", where, params, limit, offset)
    return _envelope(rows, limit, offset)


# ── raw_messages (SM/BM) ─────────────────────────────────────────────────────
@bp_api.route("/raw-messages")
def api_raw_messages():
    ticker = request.args.get("ticker")
    channel = request.args.get("channel")  # smart | bad
    limit, offset = _pagination()
    where, params = [], []
    if ticker:
        where.append("ticker = %s")
        params.append(ticker.upper())
    if channel:
        where.append("channel = %s")
        params.append(channel)
    clause, dparams = _date_clause("date", request.args.get("date_from"), request.args.get("date_to"))
    if clause:
        where.append(clause)
        params += dparams
    rows = _fetch("raw_messages", "TO_DATE(date, 'DD-MM-YYYY') DESC, time DESC", where, params, limit, offset)
    return _envelope(rows, limit, offset)


# ── raw_mf_messages (MF+/MF-) ────────────────────────────────────────────────
@bp_api.route("/raw-mf-messages")
def api_raw_mf_messages():
    ticker = request.args.get("ticker")
    channel = request.args.get("channel")  # mf_plus | mf_minus
    limit, offset = _pagination()
    where, params = [], []
    if ticker:
        where.append("ticker = %s")
        params.append(ticker.upper())
    if channel:
        where.append("channel = %s")
        params.append(channel)
    clause, dparams = _date_clause("date", request.args.get("date_from"), request.args.get("date_to"))
    if clause:
        where.append(clause)
        params += dparams
    rows = _fetch("raw_mf_messages", "TO_DATE(date, 'DD-MM-YYYY') DESC, time DESC", where, params, limit, offset)
    return _envelope(rows, limit, offset)


# ── ticker_universe ──────────────────────────────────────────────────────────
@bp_api.route("/tickers")
def api_tickers():
    is_active = request.args.get("is_active")
    limit, offset = _pagination()
    where, params = [], []
    if is_active is not None:
        where.append("is_active = %s")
        params.append(is_active.lower() in ("1", "true", "yes"))
    rows = _fetch("ticker_universe", "ticker", where, params, limit, offset)
    return _envelope(rows, limit, offset)


# ── trade_journal ────────────────────────────────────────────────────────────
@bp_api.route("/trade-journal")
def api_trade_journal():
    ticker = request.args.get("ticker")
    status = request.args.get("status")  # open | closed
    limit, offset = _pagination()
    where, params = [], []
    if ticker:
        where.append("ticker = %s")
        params.append(ticker.upper())
    if status:
        where.append("status = %s")
        params.append(status)
    clause, dparams = _date_clause("entry_date", request.args.get("date_from"), request.args.get("date_to"))
    if clause:
        where.append(clause)
        params += dparams
    rows = _fetch("trade_journal", "TO_DATE(entry_date, 'DD-MM-YYYY') DESC", where, params, limit, offset)
    return _envelope(rows, limit, offset)


# ── bsjp_signals ─────────────────────────────────────────────────────────────
@bp_api.route("/bsjp-signals")
def api_bsjp_signals():
    ticker = request.args.get("ticker")
    limit, offset = _pagination()
    # This is a machine/site integration (API-key auth, no user session), so
    # there's no per-user mode to read — always the general/full universe.
    # Without this, every date now returns 'full' and 'syariah' rows mixed
    # together (up to 20 rows/date with duplicate day_rank 1-10) since
    # bsjp_signals gained the universe column — see [[project_syariah_universe_mode]].
    where, params = ["universe = 'full'"], []
    if ticker:
        where.append("ticker = %s")
        params.append(ticker.upper())
    clause, dparams = _date_clause("date", request.args.get("date_from"), request.args.get("date_to"))
    if clause:
        where.append(clause)
        params += dparams
    rows = _fetch("bsjp_signals", "TO_DATE(date, 'DD-MM-YYYY') DESC, day_rank", where, params, limit, offset)
    return _envelope(rows, limit, offset)


# ── bsjp_results ─────────────────────────────────────────────────────────────
@bp_api.route("/bsjp-results")
def api_bsjp_results():
    ticker = request.args.get("ticker")
    limit, offset = _pagination()
    where, params = [], []
    if ticker:
        where.append("ticker = %s")
        params.append(ticker.upper())
    clause, dparams = _date_clause("date", request.args.get("date_from"), request.args.get("date_to"))
    if clause:
        where.append(clause)
        params += dparams
    rows = _fetch("bsjp_results", "TO_DATE(date, 'DD-MM-YYYY') DESC", where, params, limit, offset)
    return _envelope(rows, limit, offset)


# ── portfolio performance ────────────────────────────────────────────────────
def _algo_slice(result: dict, name: str) -> dict:
    stats = result[name]["stats"]
    return {
        "profit_factor":    stats.get("profit_factor"),
        "total_trades":     stats.get("total_trades"),
        "win_rate":         stats.get("win_rate"),
        "total_return_pct": stats.get("total_return_pct"),
        "total_equity":     stats.get("total_equity"),
    }


@bp_api.route("/portfolio-performance")
def api_portfolio_performance():
    """profit_factor / total_trades / win_rate / total_return_pct for both
    algos — the summary /api/v1/bsjp-results and /api/v1/backtest-cache don't
    actually carry (both tables are currently unpopulated; this reads the same
    in-memory cached simulation /api/portfolio and /api/public/performance do).
    Machine/site integration (API-key auth, no user session) — always the
    general/full universe, same reasoning as /api/v1/bsjp-signals.
    """
    from algo.algo_portfolio import get_portfolio_result

    result = get_portfolio_result("full")
    if not result:
        return jsonify({"error": "no cached portfolio result yet — visit /portfolio once to trigger it"}), 503

    return jsonify({
        "date_range":  result.get("date_range"),
        "computed_at": result.get("computed_at"),
        "bsjp":        _algo_slice(result, "bsjp"),
        "wyckoff":     _algo_slice(result, "wyckoff"),
    })


# ── backtest_cache ───────────────────────────────────────────────────────────
@bp_api.route("/backtest-cache")
def api_backtest_cache():
    run_id = request.args.get("run_id")
    limit, offset = _pagination()
    where, params = [], []
    if run_id:
        where.append("run_id = %s")
        params.append(run_id)
    rows = _fetch("backtest_cache", "id DESC", where, params, limit, offset)
    for r in rows:
        if isinstance(r.get("result"), str):
            try:
                r["result"] = json.loads(r["result"])
            except (ValueError, TypeError):
                pass
    return _envelope(rows, limit, offset)


# ── corporate_events ──────────────────────────────────────────────────────────
@bp_api.route("/corporate-events")
def api_corporate_events():
    ticker = request.args.get("ticker")
    event_type = request.args.get("event_type")
    limit, offset = _pagination()
    where, params = [], []
    if ticker:
        where.append("ticker = %s")
        params.append(ticker.upper())
    if event_type:
        where.append("event_type = %s")
        params.append(event_type)
    rows = _fetch("corporate_events", "ticker, event_date DESC", where, params, limit, offset)
    return _envelope(rows, limit, offset)


# ── Discovery ────────────────────────────────────────────────────────────────
_TABLES = [
    {"path": "/api/v1/eod-summary", "table": "eod_summary",
     "description": "Daily per-ticker analytics summary (SM/BM, money flow, price, Wyckoff phase/action, MAs, RSI, Bollinger Bands, BSJP indicators).",
     "filters": ["ticker", "date_from", "date_to", "limit", "offset"]},
    {"path": "/api/v1/price-history", "table": "price_history",
     "description": "Daily OHLCV + technical indicators per ticker.",
     "filters": ["ticker", "date_from", "date_to", "limit", "offset"]},
    {"path": "/api/v1/price-history-15m", "table": "price_history_15m",
     "description": "15-minute intraday OHLCV candles (WIB).",
     "filters": ["ticker", "date (YYYY-MM-DD)", "limit", "offset"]},
    {"path": "/api/v1/raw-messages", "table": "raw_messages",
     "description": "Raw Telegram Smart Money / Bad Money (SM/BM) tape.",
     "filters": ["ticker", "channel (smart|bad)", "date_from", "date_to", "limit", "offset"]},
    {"path": "/api/v1/raw-mf-messages", "table": "raw_mf_messages",
     "description": "Raw Telegram Money Flow (MF+/MF-) tape.",
     "filters": ["ticker", "channel (mf_plus|mf_minus)", "date_from", "date_to", "limit", "offset"]},
    {"path": "/api/v1/tickers", "table": "ticker_universe",
     "description": "Master list of tracked IDX tickers.",
     "filters": ["is_active", "limit", "offset"]},
    {"path": "/api/v1/trade-journal", "table": "trade_journal",
     "description": "Wyckoff algo live trade log.",
     "filters": ["ticker", "status (open|closed)", "date_from", "date_to", "limit", "offset"]},
    {"path": "/api/v1/bsjp-signals", "table": "bsjp_signals",
     "description": "BSJP (Beli Sore Jual Pagi) day-trade signals. Always the general/full-universe picks, not the syariah-restricted set.",
     "filters": ["ticker", "date_from", "date_to", "limit", "offset"]},
    {"path": "/api/v1/bsjp-results", "table": "bsjp_results",
     "description": "BSJP trade outcomes.",
     "filters": ["ticker", "date_from", "date_to", "limit", "offset"]},
    {"path": "/api/v1/portfolio-performance", "table": None,
     "description": "Summary stats (profit_factor, total_trades, win_rate, total_return_pct, "
                     "total_equity) for BSJP and Wyckoff — not a raw table, reads the cached "
                     "portfolio simulation.",
     "filters": []},
    {"path": "/api/v1/backtest-cache", "table": "backtest_cache",
     "description": "Cached backtest run results.",
     "filters": ["run_id", "limit", "offset"]},
    {"path": "/api/v1/corporate-events", "table": "corporate_events",
     "description": "Corporate action events with review status (confirmed / suspected / rejected).",
     "filters": ["ticker", "event_type", "limit", "offset"]},
]


@bp_api.route("/tables")
def api_tables():
    return jsonify({"count": len(_TABLES), "data": _TABLES})
