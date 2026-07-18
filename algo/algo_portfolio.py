"""
algo_portfolio.py — Zenith 2.0 Portfolio Simulation Engine

Simulates equity growth if you followed every signal from each algo with a
FIXED per-signal allocation (no user-tunable budget — owner controls constants
in config.py). The only user control is the date range.

Model (notional, documented intentionally):
  - Each algo starts from a shared notional baseline equity (PF_INITIAL_EQUITY).
  - equity(day) = INITIAL + realized P&L (closed trades ≤ day)
                          + unrealized P&L (open positions marked-to-market at day's close)
  - Per signal we buy floor(ALLOC / (entry × lot_size)) lots (IDX lot = 100 shares),
    min 1 lot. P&L in Rp = lots × lot_size × (exit − entry).

Wyckoff = multi-day swing (BUY → SELL/SL, open positions allowed, MTM curve).
BSJP    = overnight, every trade resolves T+1 (step-wise curve, no open positions).

RULE: Prices come from eod_summary / the existing backtest engines. Zero HTTP here.
"""
import logging
import math
import threading
from collections import defaultdict
from datetime import datetime

from config import WIB, PF_INITIAL_EQUITY, PF_WYCKOFF_INITIAL_EQUITY, PF_BSJP_INITIAL_EQUITY, PF_WYCKOFF_ALLOC, PF_BSJP_ALLOC, PF_LOT_SIZE
from core.db import fetchall
from algo.algo_wyckoff import get_action

log = logging.getLogger("zenith.portfolio")

_pf_lock    = threading.Lock()
_pf_result  = None
_pf_running = False
_pf_error   = None


# ── Date helpers (DD-MM-YYYY domain, matching eod_summary) ────────────────────
def _to_cmp(date_str: str) -> str:
    """DD-MM-YYYY → YYYYMMDD for correct string comparison."""
    if not date_str or len(date_str) != 10:
        return date_str
    return f"{date_str[6:10]}{date_str[3:5]}{date_str[:2]}"


def _label(date_str: str) -> str:
    """DD-MM-YYYY → DD/MM for chart x-axis labels."""
    if not date_str or len(date_str) != 10:
        return date_str
    return f"{date_str[:2]}/{date_str[3:5]}"


def _days_between(d1: str, d2: str) -> int:
    """Calendar days between two DD-MM-YYYY strings."""
    try:
        a = datetime.strptime(d1, "%d-%m-%Y")
        b = datetime.strptime(d2, "%d-%m-%Y")
        return abs((b - a).days)
    except Exception:
        return 0


def _lots(alloc: float, price: float) -> int:
    """Whole lots affordable for `alloc` at `price`. Min 1 (can't take a fractional trade)."""
    if not price or price <= 0:
        return 0
    return max(1, math.floor(alloc / (price * PF_LOT_SIZE)))


def _max_drawdown_pct(series: list) -> float:
    """Largest peak-to-trough drop as a negative %. For equity curves with a
    meaningful baseline (non-zero start). Do NOT use for P&L curves from 0."""
    peak = None
    worst = 0.0
    for v in series:
        if peak is None or v > peak:
            peak = v
        if peak and peak > 0:
            dd = (v - peak) / peak * 100
            if dd < worst:
                worst = dd
    return round(worst, 2)


def _max_drawdown_rp(series: list) -> int:
    """Largest peak-to-trough drop as a negative Rp amount. For P&L curves
    starting from 0 where % is meaningless (tiny peak → enormous %)."""
    peak = None
    worst = 0
    for v in series:
        if peak is None or v > peak:
            peak = v
        if peak is not None:
            dd = v - peak
            if dd < worst:
                worst = dd
    return round(worst)


# ── Wyckoff simulation (multi-entry swing, MTM equity) ────────────────────────
def _simulate_wyckoff(conn, date_from: str, date_to: str, axis_dates: list,
                       wyckoff_alloc: int = None, wyckoff_basis: int = None):
    """Walk eod_summary day-by-day, deploying PF_WYCKOFF_ALLOC per BUY signal."""
    alloc = wyckoff_alloc or PF_WYCKOFF_ALLOC
    basis = wyckoff_basis or PF_WYCKOFF_INITIAL_EQUITY
    all_rows = fetchall(conn, """
        SELECT ticker, date, price_close, phase, atr_pct,
               sri, sm_val, bm_val, bm_sma10, price_change_pct, watch
        FROM eod_summary ORDER BY ticker, date
    """)

    fc = _to_cmp(date_from) if date_from else None
    tc = _to_cmp(date_to)   if date_to   else None
    rows = []
    for r in all_rows:
        if not r.get("price_close"):
            continue
        c = _to_cmp(r["date"])
        if fc and c < fc:
            continue
        if tc and c > tc:
            continue
        rows.append(r)

    # Recompute action from current algo settings (don't trust stored column)
    def _recompute_action(r) -> str:
        try:
            sri      = float(r["sri"])      if r.get("sri")      else 0.0
            sm_val   = float(r["sm_val"])   if r.get("sm_val")   else 0.0
            bm_val   = float(r["bm_val"])   if r.get("bm_val")   else 0.0
            bm_sma10 = float(r["bm_sma10"]) if r.get("bm_sma10") else 0.0
            atr_pct  = float(r["atr_pct"])  if r.get("atr_pct")  else 2.5
            pchg     = float(r["price_change_pct"]) if r.get("price_change_pct") else None
            phase    = r.get("phase") or "NEUTRAL"
            total_flow = sm_val + abs(bm_val)
            rsm = round(sm_val / total_flow * 100, 2) if total_flow > 0 else 50.0
            return get_action(phase, pchg, atr_pct, bm_val, bm_sma10, r.get("watch"), sri=sri, rsm=rsm)
        except Exception:
            return "HOLD"

    days_index = defaultdict(dict)
    for r in rows:
        r["action"] = _recompute_action(r)
        days_index[r["date"]][r["ticker"]] = r

    realized      = 0.0                       # Rp, cumulative realized P&L
    open_pos      = defaultdict(list)         # ticker -> [{entry_date, entry_price, lots, phase, sl}]
    last_close    = {}                        # ticker -> most recent close (for MTM)
    trades        = []                        # closed + still-open at end
    eq_values     = []

    for date_str in axis_dates:
        day = days_index.get(date_str, {})

        # refresh last-known close for everything trading today
        for tk, row in day.items():
            if row.get("price_close"):
                last_close[tk] = row["price_close"]

        # 1. daily ATR stop-loss check
        for ticker, positions in list(open_pos.items()):
            if not positions:
                continue
            row   = day.get(ticker)
            price = row["price_close"] if row else None
            if not price:
                continue
            surviving = []
            for pos in positions:
                loss_pct = (price - pos["entry_price"]) / pos["entry_price"] * 100
                if loss_pct <= pos["sl"]:
                    pnl = pos["lots"] * PF_LOT_SIZE * (price - pos["entry_price"])
                    realized += pnl
                    txn_v = pos["lots"] * PF_LOT_SIZE * pos["entry_price"]
                    trades.append({
                        "ticker": ticker, "entry_date": pos["entry_date"], "exit_date": date_str,
                        "entry_price": pos["entry_price"], "exit_price": price,
                        "gain": round(loss_pct, 2), "hold_days": _days_between(pos["entry_date"], date_str),
                        "lots": pos["lots"], "phase": pos["phase"], "reason": "SL",
                        "txn_value": round(txn_v),
                        "pnl_rp": round(pos["lots"] * PF_LOT_SIZE * (price - pos["entry_price"])),
                        "status": "LOSS" if loss_pct <= 0 else "WIN",
                    })
                else:
                    surviving.append(pos)
            open_pos[ticker] = surviving

        # 2. BUY / SELL signals
        for ticker, row in day.items():
            action = row.get("action")
            price  = row.get("price_close")
            if not action or not price:
                continue
            if action == "BUY":
                if open_pos[ticker]:   # already holding — don't stack positions
                    continue
                atr_pct = row.get("atr_pct") or 2.5
                sl      = -min(max(atr_pct * 2.0, 5.0), 12.0)
                lots    = _lots(alloc, price)
                if lots <= 0:
                    continue
                open_pos[ticker].append({
                    "entry_date": date_str, "entry_price": price,
                    "lots": lots, "phase": row.get("phase"), "sl": sl,
                })
            elif action == "SELL" and open_pos[ticker]:
                for pos in open_pos[ticker]:
                    gain = (price - pos["entry_price"]) / pos["entry_price"] * 100
                    pnl  = pos["lots"] * PF_LOT_SIZE * (price - pos["entry_price"])
                    realized += pnl
                    txn_v = pos["lots"] * PF_LOT_SIZE * pos["entry_price"]
                    trades.append({
                        "ticker": ticker, "entry_date": pos["entry_date"], "exit_date": date_str,
                        "entry_price": pos["entry_price"], "exit_price": price,
                        "gain": round(gain, 2), "hold_days": _days_between(pos["entry_date"], date_str),
                        "lots": pos["lots"], "phase": pos["phase"], "reason": "SELL",
                        "txn_value": round(txn_v),
                        "pnl_rp": round(pos["lots"] * PF_LOT_SIZE * (price - pos["entry_price"])),
                        "status": "WIN" if gain > 0 else "LOSS",
                    })
                open_pos[ticker] = []

        # 3. snapshot end-of-day equity (cumulative P&L from 0, no baseline)
        # Wyckoff has concurrent open positions with no capital constraint, so
        # an "equity baseline" is meaningless — show P&L accumulation instead.
        unreal = 0.0
        for ticker, positions in open_pos.items():
            mtm = last_close.get(ticker)
            if not mtm:
                continue
            for pos in positions:
                unreal += pos["lots"] * PF_LOT_SIZE * (mtm - pos["entry_price"])
        eq_values.append(round(realized + unreal))

    # 4. remaining open positions → OPEN trades, marked-to-market at last close
    last_date = axis_dates[-1] if axis_dates else date_to
    for ticker, positions in open_pos.items():
        mtm = last_close.get(ticker)
        for pos in positions:
            if not mtm:
                continue
            gain = (mtm - pos["entry_price"]) / pos["entry_price"] * 100
            txn_v = pos["lots"] * PF_LOT_SIZE * pos["entry_price"]
            trades.append({
                "ticker": ticker, "entry_date": pos["entry_date"], "exit_date": last_date,
                "entry_price": pos["entry_price"], "exit_price": mtm,
                "gain": round(gain, 2), "hold_days": _days_between(pos["entry_date"], last_date),
                "lots": pos["lots"], "phase": pos["phase"], "reason": "—",
                "txn_value": round(txn_v),
                "pnl_rp": round(pos["lots"] * PF_LOT_SIZE * (mtm - pos["entry_price"])),
                "status": "OPEN",
            })

    closed = [t for t in trades if t["status"] != "OPEN"]
    stats  = _build_stats(eq_values, closed, avg_hold_days=True, is_pnl_curve=True,
                          equity_basis=basis)
    stats["open_count"]      = sum(1 for t in trades if t["status"] == "OPEN")
    stats["closed_count"]    = len(closed)
    stats["total_trades"]    = len(trades)
    stats["total_txn_value"] = sum(t.get("txn_value", 0) for t in trades)
    # Capital locked in still-open positions (entry value, not current MTM)
    deployed = sum(
        pos["lots"] * PF_LOT_SIZE * pos["entry_price"]
        for positions in open_pos.values() for pos in positions
    )
    stats["initial_equity"]    = basis
    stats["available_balance"] = round(basis + realized - deployed)
    stats["total_equity"]      = round(basis + (eq_values[-1] if eq_values else 0))
    return eq_values, trades, stats


# ── BSJP simulation (overnight, every trade resolves T+1) ─────────────────────
def _simulate_bsjp(conn, date_from: str, date_to: str, axis_dates: list,
                    bsjp_alloc: int = None, bsjp_initial: int = None):
    """Reuse the BSJP backtest engine, size each trade at PF_BSJP_ALLOC."""
    alloc   = bsjp_alloc   or PF_BSJP_ALLOC
    initial = bsjp_initial or PF_BSJP_INITIAL_EQUITY
    from algo.algo_backtest import run_bsjp_backtest

    bt = run_bsjp_backtest(conn, date_from=date_from, date_to=date_to)

    # flatten all per-setup trade details
    raw = []
    for setup_row in bt.get("leaderboard", []):
        setup = setup_row.get("setup")
        for d in setup_row.get("details", []):
            raw.append({**d, "setup": setup})

    trades = []
    realized_by_date = defaultdict(float)     # exit_date (DD-MM-YYYY) -> realized P&L
    for t in raw:
        entry = t.get("entry")
        exitp = t.get("exit_price")
        if not entry or entry <= 0 or exitp is None:
            continue
        lots  = _lots(alloc, entry)
        txn_v = lots * PF_LOT_SIZE * entry
        pnl   = lots * PF_LOT_SIZE * (exitp - entry)
        realized_by_date[t.get("exit_date")] += pnl
        trades.append({
            "ticker": t.get("ticker"), "date": t.get("date"), "setup": t.get("setup"),
            "entry_price": entry, "exit_price": exitp,
            "gain": t.get("pnl_pct"), "lots": lots,
            "txn_value": round(txn_v),
            "pnl_rp": round(pnl),
            "reason": t.get("reason"), "status": t.get("status"),
        })

    # step-wise cumulative P&L curve from 0 (same model as Wyckoff)
    eq_values = []
    cum = 0.0
    for d in axis_dates:
        cum += realized_by_date.get(d, 0.0)
        eq_values.append(round(cum))

    # P&L sign drives win/loss (backtest stores "Berhasil"/"Gagal")
    for t in trades:
        g = t["gain"]
        t["status"] = "WIN" if (g is not None and g > 0) else "LOSS"

    stats = _build_stats(eq_values, trades, avg_hold_days=False, is_pnl_curve=True,
                         equity_basis=initial)
    stats["open_count"]      = 0
    stats["closed_count"]    = len(trades)
    stats["total_trades"]    = len(trades)
    stats["total_txn_value"] = sum(t.get("txn_value", 0) for t in trades)
    final_eq = round(initial + (eq_values[-1] if eq_values else 0))
    stats["initial_equity"]    = initial
    stats["available_balance"] = final_eq   # all T+1 — no capital locked overnight
    stats["total_equity"]      = final_eq
    return eq_values, trades, stats


# ── Shared stats ──────────────────────────────────────────────────────────────
def _build_stats(eq_values: list, closed_trades: list, avg_hold_days: bool,
                 is_pnl_curve: bool = False, equity_basis: int = None) -> dict:
    """
    equity_basis — denominator for total_return_pct.
                   Defaults to PF_INITIAL_EQUITY when not supplied.
    is_pnl_curve=True  → eq_values is cumulative P&L from 0.
                         return_pct = final_pnl / equity_basis × 100.
    is_pnl_curve=False → eq_values starts from equity_basis.
                         return_pct = (final − equity_basis) / equity_basis × 100.
    """
    basis  = equity_basis if equity_basis is not None else PF_INITIAL_EQUITY
    final  = eq_values[-1] if eq_values else (0 if is_pnl_curve else basis)
    wins   = [t for t in closed_trades if (t.get("gain") or 0) > 0]
    losses = [t for t in closed_trades if (t.get("gain") or 0) <= 0]
    n      = len(closed_trades)

    gross_w = sum(t["lots"] * PF_LOT_SIZE * (t["exit_price"] - t["entry_price"]) for t in wins)
    gross_l = abs(sum(t["lots"] * PF_LOT_SIZE * (t["exit_price"] - t["entry_price"]) for t in losses))
    pf = round(gross_w / gross_l, 2) if gross_l > 0 else None

    avg_hold = None
    if avg_hold_days and closed_trades:
        avg_hold = round(sum(t.get("hold_days", 0) for t in closed_trades) / len(closed_trades), 1)

    if is_pnl_curve:
        total_return_pct = round(final / basis * 100, 2) if basis else 0.0
        initial_equity   = None
        max_dd_pct       = None
        max_dd_rp        = _max_drawdown_rp(eq_values)
    else:
        total_return_pct = round((final - basis) / basis * 100, 2)
        initial_equity   = basis
        max_dd_pct       = _max_drawdown_pct(eq_values)
        max_dd_rp        = None

    return {
        "initial_equity":   initial_equity,
        "final_equity":     final,
        "total_return_pct": total_return_pct,
        "win_rate":         round(len(wins) / n * 100, 1) if n else None,
        "max_drawdown_pct": max_dd_pct,
        "max_drawdown_rp":  max_dd_rp,
        "avg_hold":         avg_hold,
        "profit_factor":    pf,
    }


# ── Public: run / async wrappers ──────────────────────────────────────────────
def simulate_portfolio(conn, date_from: str = None, date_to: str = None,
                        user_params: dict = None) -> dict:
    """Full portfolio simulation across both algos over a shared date axis."""
    global _pf_result

    up = user_params or {}
    # One canonical trading-day axis drives both curves so they line up 1:1.
    axis_dates = _axis_dates(conn, date_from, date_to)
    labels     = [_label(d) for d in axis_dates]

    wy_eq, wy_trades, wy_stats = _simulate_wyckoff(
        conn, date_from, date_to, axis_dates,
        wyckoff_alloc=up.get("wyckoff_alloc"), wyckoff_basis=up.get("wyckoff_basis"))
    bs_eq, bs_trades, bs_stats = _simulate_bsjp(
        conn, date_from, date_to, axis_dates,
        bsjp_alloc=up.get("bsjp_alloc"), bsjp_initial=up.get("bsjp_capital"))

    result = {
        "equity": {
            "labels":  labels,
            "wyckoff": wy_eq,
            "bsjp":    bs_eq,
        },
        "wyckoff": {"stats": wy_stats, "trades": wy_trades},
        "bsjp":    {"stats": bs_stats, "trades": bs_trades},
        "axis_dates":  axis_dates,
        "date_range":  f"{axis_dates[0]} - {axis_dates[-1]}" if axis_dates else "-",
        "computed_at": datetime.now(WIB).strftime("%d-%m-%Y %H:%M"),
        "user_params": {
            "bsjp_capital":  up.get("bsjp_capital")  or PF_BSJP_INITIAL_EQUITY,
            "bsjp_alloc":    up.get("bsjp_alloc")    or PF_BSJP_ALLOC,
            "wyckoff_alloc": up.get("wyckoff_alloc") or PF_WYCKOFF_ALLOC,
            "wyckoff_basis": up.get("wyckoff_basis") or PF_WYCKOFF_INITIAL_EQUITY,
        },
    }

    with _pf_lock:
        _pf_result = result
    return result


def filter_result(full: dict, date_from: str, date_to: str) -> dict:
    """Slice a cached full-range result to [date_from, date_to] in-memory — no DB."""
    axis_dates = full.get("axis_dates") or []
    if not axis_dates:
        return full

    fc = _to_cmp(date_from) if date_from else None
    tc = _to_cmp(date_to)   if date_to   else None

    idxs = [i for i, d in enumerate(axis_dates)
             if (not fc or _to_cmp(d) >= fc) and (not tc or _to_cmp(d) <= tc)]
    if not idxs:
        return full

    sub_dates  = [axis_dates[i]                    for i in idxs]
    sub_labels = [full["equity"]["labels"][i]       for i in idxs]
    sub_wy     = [full["equity"]["wyckoff"][i]      for i in idxs]
    sub_bs     = [full["equity"]["bsjp"][i]         for i in idxs]

    # Normalise both curves to start from 0 at the selected period start
    wy_base = sub_wy[0] if sub_wy else 0
    bs_base = sub_bs[0] if sub_bs else 0
    sub_wy = [v - wy_base for v in sub_wy]
    sub_bs = [v - bs_base for v in sub_bs]

    def _in(d_str):
        c = _to_cmp(d_str or "")
        return (not fc or c >= fc) and (not tc or c <= tc)

    wy_trades = [t for t in full["wyckoff"]["trades"] if _in(t.get("entry_date", ""))]
    bs_trades = [t for t in full["bsjp"]["trades"]    if _in(t.get("date", ""))]

    wy_closed = [t for t in wy_trades if t.get("status") != "OPEN"]
    wy_open   = [t for t in wy_trades if t.get("status") == "OPEN"]
    wy_stats  = _build_stats(sub_wy, wy_closed, avg_hold_days=True, is_pnl_curve=True,
                             equity_basis=PF_WYCKOFF_INITIAL_EQUITY)
    wy_stats.update({
        "open_count":      len(wy_open),
        "closed_count":    len(wy_closed),
        "total_trades":    len(wy_trades),
        "total_txn_value": sum(t.get("txn_value", 0) for t in wy_trades),
    })
    # Absolute equity: wy_base = P&L already accumulated before this sub-period
    wy_deployed = sum(t.get("lots", 0) * PF_LOT_SIZE * t.get("entry_price", 0) for t in wy_open)
    wy_realized = sum(t.get("pnl_rp", 0) for t in wy_closed)
    wy_stats["initial_equity"]    = PF_WYCKOFF_INITIAL_EQUITY
    wy_stats["available_balance"] = round(PF_WYCKOFF_INITIAL_EQUITY + wy_base + wy_realized - wy_deployed)
    wy_stats["total_equity"]      = round(PF_WYCKOFF_INITIAL_EQUITY + wy_base + (sub_wy[-1] if sub_wy else 0))

    bs_stats = _build_stats(sub_bs, bs_trades, avg_hold_days=False, is_pnl_curve=True,
                            equity_basis=PF_BSJP_INITIAL_EQUITY)
    bs_stats.update({
        "open_count":      0,
        "closed_count":    len(bs_trades),
        "total_trades":    len(bs_trades),
        "total_txn_value": sum(t.get("txn_value", 0) for t in bs_trades),
    })
    bs_total = round(PF_BSJP_INITIAL_EQUITY + bs_base + (sub_bs[-1] if sub_bs else 0))
    bs_stats["initial_equity"]    = PF_BSJP_INITIAL_EQUITY
    bs_stats["available_balance"] = bs_total
    bs_stats["total_equity"]      = bs_total

    return {
        "equity": {"labels": sub_labels, "wyckoff": sub_wy, "bsjp": sub_bs},
        "wyckoff": {"stats": wy_stats, "trades": wy_trades},
        "bsjp":    {"stats": bs_stats, "trades": bs_trades},
        "axis_dates":  sub_dates,
        "date_range":  f"{sub_dates[0]} - {sub_dates[-1]}",
        "computed_at": full["computed_at"],
        "user_params": full.get("user_params"),
    }


def _axis_dates(conn, date_from: str, date_to: str) -> list:
    """Distinct trading dates (DD-MM-YYYY) within range, oldest first.
    Union of eod_summary and price_history calendars: BSJP exit dates are
    computed off price_history's trading calendar (see run_bsjp_backtest),
    and must always land on this axis — otherwise a trade whose exit date has
    no eod_summary row (e.g. a day Telegram scraping was down) has its P&L
    silently dropped from the cumulative equity curve while still being
    counted in the trade log."""
    dates_dmy = {r["date"] for r in fetchall(conn, "SELECT DISTINCT date FROM eod_summary")}
    for r in fetchall(conn, "SELECT DISTINCT date FROM price_history"):
        d = r["date"]  # YYYY-MM-DD
        if d and len(d) == 10:
            dates_dmy.add(f"{d[8:10]}-{d[5:7]}-{d[:4]}")

    fc = _to_cmp(date_from) if date_from else None
    tc = _to_cmp(date_to)   if date_to   else None
    dates = []
    for d in dates_dmy:
        c = _to_cmp(d)
        if fc and c < fc:
            continue
        if tc and c > tc:
            continue
        dates.append(d)
    return sorted(dates, key=_to_cmp)


def request_portfolio_sim(date_from: str = None, date_to: str = None,
                           user_params: dict = None) -> bool:
    """Non-blocking trigger from the HTTP thread (BSJP backtest is slow)."""
    global _pf_running, _pf_error

    def _run():
        global _pf_running, _pf_error
        try:
            from core.db import get_db
            simulate_portfolio(get_db(), date_from=date_from, date_to=date_to,
                               user_params=user_params)
            _pf_error = None
        except Exception as e:
            log.error("Portfolio sim error: %s", e)
            _pf_error = str(e)
        finally:
            _pf_running = False

    with _pf_lock:
        if _pf_running:
            return False
        _pf_running = True
        _pf_error   = None

    threading.Thread(target=_run, daemon=True, name="portfolio-sim").start()
    return True


def get_portfolio_status() -> dict:
    with _pf_lock:
        if _pf_running:
            return {"status": "running"}
        if _pf_error:
            return {"status": "error", "result": _pf_error}
        return {"status": "done"}


def get_portfolio_result() -> dict | None:
    with _pf_lock:
        return _pf_result
