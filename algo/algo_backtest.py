"""
algo_backtest.py — Zenith 2.0 Backtest Engine
Pair-based backtest: multi-entry BUY → SELL/SL close, mirroring Zenith 1.0 logic.
RULE: Fetch prices from eod_summary (not Yahoo directly).
"""
import logging
import threading
from collections import defaultdict
from datetime import datetime
from config import WIB
from core.db import fetchall
from algo.algo_wyckoff import get_action, get_watch_flag

log = logging.getLogger("zenith.backtest")

_backtest_lock    = threading.Lock()
_backtest_result  = None
_backtest_running = False
_backtest_error   = None

_bsjp_lock    = threading.Lock()
_bsjp_result  = None
_bsjp_running = False
_bsjp_error   = None


def _to_cmp(date_str: str) -> str:
    """Convert DD-MM-YYYY to YYYYMMDD for correct string comparison."""
    if not date_str or len(date_str) != 10:
        return date_str
    return f"{date_str[6:10]}{date_str[3:5]}{date_str[:2]}"


def _dmy_to_ymd(d: str) -> str:
    """Convert DD-MM-YYYY to YYYY-MM-DD (price_history date format)."""
    if not d or len(d) != 10:
        return d
    return f"{d[6:10]}-{d[3:5]}-{d[:2]}"


def _days_between(d1: str, d2: str) -> int:
    """Days between two DD-MM-YYYY strings."""
    try:
        a = datetime.strptime(d1, "%d-%m-%Y")
        b = datetime.strptime(d2, "%d-%m-%Y")
        return abs((b - a).days)
    except Exception:
        return 0


def run_backtest(conn, days: int = 30, date_from: str = None, date_to: str = None) -> dict:
    """
    Multi-entry pair-based backtest over eod_summary date range.
    - Each BUY opens a new position (multi-entry, like Zenith 1.0).
    - SELL closes ALL open positions for that ticker.
    - ATR-based stop loss checked daily.
    Returns leaderboard dict matching backtest.html expectations.
    """
    global _backtest_result

    # ── Fetch ALL rows in range (need every day's price for daily SL check) ────
    # Fetch all fields needed to re-compute action live from current algo settings.
    # Do NOT use stored action column — it reflects the algo version at scrape time.
    if date_from and date_to:
        date_from_cmp = _to_cmp(date_from)
        date_to_cmp   = _to_cmp(date_to)
        all_rows = fetchall(conn, """
            SELECT ticker, date, price_close, phase, atr_pct,
                   sri, sm_val, bm_val, bm_sma10, price_change_pct, watch
            FROM eod_summary ORDER BY ticker, date
        """)
        rows = [r for r in all_rows
                if date_from_cmp <= _to_cmp(r["date"]) <= date_to_cmp
                and r.get("price_close")]
    else:
        distinct = fetchall(conn, """
            SELECT date FROM (SELECT DISTINCT date FROM eod_summary) t
            ORDER BY TO_DATE(date, 'DD-MM-YYYY') ASC
        """)
        all_distinct = [r["date"] for r in distinct]
        cutoff_date = all_distinct[-days] if len(all_distinct) >= days else (all_distinct[0] if all_distinct else "01-01-2000")
        cutoff_cmp  = _to_cmp(cutoff_date)
        all_rows = fetchall(conn, """
            SELECT ticker, date, price_close, phase, atr_pct,
                   sri, sm_val, bm_val, bm_sma10, price_change_pct, watch
            FROM eod_summary ORDER BY ticker, date
        """)
        rows = [r for r in all_rows
                if _to_cmp(r["date"]) >= cutoff_cmp and r.get("price_close")]

    # Re-compute action using current algo settings (not stored DB value)
    # rsm is not stored — compute from sm_val + bm_val
    def _recompute_action(r) -> str:
        try:
            sri      = float(r["sri"])      if r.get("sri")      else 0.0
            sm_val   = float(r["sm_val"])   if r.get("sm_val")   else 0.0
            bm_val   = float(r["bm_val"])   if r.get("bm_val")   else 0.0
            bm_sma10 = float(r["bm_sma10"]) if r.get("bm_sma10") else 0.0
            atr_pct  = float(r["atr_pct"])  if r.get("atr_pct")  else 2.5
            pchg     = float(r["price_change_pct"]) if r.get("price_change_pct") else None
            watch    = r.get("watch")
            phase    = r.get("phase") or "NEUTRAL"
            total_flow = sm_val + abs(bm_val)
            rsm = round(sm_val / total_flow * 100, 2) if total_flow > 0 else 50.0
            return get_action(phase, pchg, atr_pct, bm_val, bm_sma10, watch, sri=sri, rsm=rsm)
        except Exception:
            return "HOLD"

    for r in rows:
        r["action"] = _recompute_action(r)

    # ── Index: {date: {ticker: row}} ────────────────────────────────────────────
    days_index = defaultdict(dict)
    for row in rows:
        days_index[row["date"]][row["ticker"]] = row

    sorted_dates = sorted(days_index.keys(), key=_to_cmp)

    # ── Multi-entry position tracking ───────────────────────────────────────────
    trades = []
    open_positions = defaultdict(list)  # {ticker: [{entry_date, entry_price, entry_phase, sl_threshold}, ...]}

    for date_str in sorted_dates:
        day_tickers = days_index[date_str]

        # 1. Check ATR stop loss daily for every open position
        for ticker, positions in list(open_positions.items()):
            if not positions:
                continue
            day_row = day_tickers.get(ticker)
            price   = day_row["price_close"] if day_row else None
            if not price:
                continue

            surviving = []
            for pos in positions:
                loss_pct = (price - pos["entry_price"]) / pos["entry_price"] * 100
                if loss_pct <= pos["sl_threshold"]:
                    trades.append({
                        "ticker":      ticker,
                        "entry_date":  pos["entry_date"],
                        "exit_date":   date_str,
                        "entry_price": pos["entry_price"],
                        "exit_price":  price,
                        "profit":      round(loss_pct, 2),
                        "duration":    _days_between(pos["entry_date"], date_str),
                        "phase":       pos["entry_phase"],
                        "exit_phase":  "SL",
                    })
                else:
                    surviving.append(pos)
            open_positions[ticker] = surviving

        # 2. Process BUY / SELL signals for this day
        for ticker, row in day_tickers.items():
            action = row.get("action")
            price  = row.get("price_close")
            if not action or not price:
                continue

            if action == "BUY":
                if open_positions[ticker]:   # already holding — don't stack
                    continue
                atr_pct      = row.get("atr_pct") or 2.5
                sl_threshold = -min(max(atr_pct * 2.0, 5.0), 12.0)
                open_positions[ticker].append({
                    "entry_date":  date_str,
                    "entry_price": price,
                    "entry_phase": row.get("phase"),
                    "sl_threshold": sl_threshold,
                })

            elif action == "SELL" and open_positions[ticker]:
                for pos in open_positions[ticker]:
                    profit = round((price - pos["entry_price"]) / pos["entry_price"] * 100, 2)
                    trades.append({
                        "ticker":      ticker,
                        "entry_date":  pos["entry_date"],
                        "exit_date":   date_str,
                        "entry_price": pos["entry_price"],
                        "exit_price":  price,
                        "profit":      profit,
                        "duration":    _days_between(pos["entry_date"], date_str),
                        "phase":       pos["entry_phase"],
                        "exit_phase":  row.get("phase"),
                    })
                open_positions[ticker] = []

    # ── Build leaderboard grouped by entry phase ────────────────────────────────
    phase_map = defaultdict(list)
    for t in trades:
        if t.get("profit", 0) < -50:  # exclude extreme losses (rights issue, delisting)
            continue
        phase_map[t["phase"] or "UNKNOWN"].append(t)

    leaderboard = []
    for phase, pt in phase_map.items():
        wins        = [t for t in pt if t["profit"] > 0]
        losses      = [t for t in pt if t["profit"] <= 0]
        gross_profit = sum(t["profit"] for t in wins)
        gross_loss   = abs(sum(t["profit"] for t in losses))
        pf = round(gross_profit / gross_loss, 2) if gross_loss > 0 else None
        leaderboard.append({
            "entry":        phase,
            "trades":       len(pt),
            "wins":         len(wins),
            "losses":       len(losses),
            "win_rate":     round(len(wins) / len(pt) * 100, 1),
            "avg_profit":   round(sum(t["profit"] for t in pt) / len(pt), 2),
            "avg_win":      round(gross_profit / len(wins), 2) if wins else None,
            "avg_loss":     round(-gross_loss / len(losses), 2) if losses else None,
            "avg_duration": round(sum(t["duration"] for t in pt) / len(pt), 1),
            "profit_factor": pf,
            "details": [{
                "ticker":      t["ticker"],
                "entry_date":  t["entry_date"],
                "exit_date":   t["exit_date"],
                "entry_price": t["entry_price"],
                "exit_price":  t["exit_price"],
                "profit":      t["profit"],
                "duration":    t["duration"],
                "exit_phase":  t["exit_phase"],
            } for t in pt],
        })

    valid_trades = [t for t in trades if t.get("profit", 0) >= -50]
    total_wins   = sum(1 for t in valid_trades if t["profit"] > 0)
    total_losses = len(valid_trades) - total_wins
    gross_p      = sum(t["profit"] for t in valid_trades if t["profit"] > 0)
    gross_l      = abs(sum(t["profit"] for t in valid_trades if t["profit"] <= 0))
    overall_pf   = round(gross_p / gross_l, 2) if gross_l > 0 else None
    overall_wr   = round(total_wins / len(valid_trades) * 100, 1) if valid_trades else None

    all_entry_dates = [t["entry_date"] for t in valid_trades]
    all_exit_dates  = [t["exit_date"]  for t in valid_trades]
    all_d = sorted(all_entry_dates + all_exit_dates, key=_to_cmp)
    date_range = f"{all_d[0]} - {all_d[-1]}" if all_d else "-"

    result = {
        "leaderboard":           leaderboard,
        "total_trades":          len(valid_trades),
        "total_wins":            total_wins,
        "total_losses":          total_losses,
        "overall_win_rate":      overall_wr,
        "overall_profit_factor": overall_pf,
        "tickers_tested":        len({t["ticker"] for t in valid_trades}),
        "date_range":            date_range,
        "computed_at":           datetime.now(WIB).strftime("%d-%m-%Y %H:%M"),
    }

    with _backtest_lock:
        _backtest_result = result

    return result


def request_backtest(days: int = 30, date_from: str = None, date_to: str = None):
    """Non-blocking backtest trigger from HTTP thread."""
    global _backtest_running, _backtest_error

    def _run():
        global _backtest_running, _backtest_error
        try:
            from core.db import get_db
            conn = get_db()
            run_backtest(conn, days=days, date_from=date_from, date_to=date_to)
            _backtest_error = None
        except Exception as e:
            log.error("Backtest error: %s", e)
            _backtest_error = str(e)
        finally:
            # Worker threads get their own thread-local connection and never
            # pass through Flask's teardown, so they must close it themselves —
            # otherwise the thread dies leaving it 'idle in transaction'.
            from core.db import close_db
            close_db()
            _backtest_running = False

    with _backtest_lock:
        if _backtest_running:
            return False
        _backtest_running = True
        _backtest_error   = None

    threading.Thread(target=_run, daemon=True, name="backtest").start()
    return True


def get_backtest_status() -> dict:
    with _backtest_lock:
        if _backtest_running:
            return {"status": "running"}
        if _backtest_error:
            return {"status": "error", "result": _backtest_error}
        return {"status": "done"}


def get_backtest_result() -> dict | None:
    with _backtest_lock:
        return _backtest_result


def _dmy_to_ymd(date_dmy: str) -> str:
    """Convert DD-MM-YYYY → YYYY-MM-DD."""
    if not date_dmy or len(date_dmy) != 10:
        return date_dmy
    return f"{date_dmy[6:10]}-{date_dmy[3:5]}-{date_dmy[:2]}"


def run_bsjp_backtest(conn, date_from: str = None, date_to: str = None,
                       universe: str = "full") -> dict:
    """
    BSJP backtest: PRE-based signals, paritas penuh dengan bsjp_view.py --rank.
    - Signal dari harga 15:45 (PRE proxy); entry tetap EOD close (IEP)
    - Exit via 15m candles kronologis (eval_exit_15m)
    - Hanya PRE+FINAL dan PRE_ONLY dihitung; FINAL_ONLY dibuang
    date_from, date_to: DD-MM-YYYY

    Both universes ('full' and 'syariah') are always computed — the scoring pass
    and the 15m candle fetch are shared — and both are cached. `universe` only
    selects which one is returned.
    """
    global _bsjp_result
    from algo.algo_bsjp import BSJPAlgo, _is_ara, _compute_score, _to_tick, eval_exit_15m
    from algo.corporate_actions import excluded_tickers
    from core.utils import syariah_tickers
    from collections import defaultdict as _dd

    algo  = BSJPAlgo()
    # 2026-07-19: was 10 @ PF_BSJP_ALLOC=15jt. Concentrating the same daily
    # capital into fewer, bigger picks measured better net (fee-adjusted)
    # return — see config.py's PF_BSJP_ALLOC comment for the numbers. Must
    # match scraper_daily.py's TOP_N_BSJP — no shared constant between the
    # backtest engine and the live scanner, so this needs updating in both
    # places by hand.
    TOP_N = 5
    UNIVERSES = ("full", "syariah")

    _empty = {
        "leaderboard": [], "total_trades": 0, "total_wins": 0, "total_losses": 0,
        "overall_win_rate": None, "overall_expectancy": None, "setup_count": 0,
        "date_range": "-", "computed_at": datetime.now(WIB).strftime("%d-%m-%Y %H:%M"),
    }
    _empty_all = {u: dict(_empty) for u in UNIVERSES}

    # ── Fetch semua EOD data ─────────────────────────────────────────────────────
    # Local bsjp_view.py reads from eod_summary only (no JOIN).
    # eod_summary.days_since_near_bb_mid is always NULL (column added via ALTER TABLE
    # but never populated) → Python None → PULLBACK_BB first-touch filter always passes.
    # We must NOT use ph.days_since_near_bb_mid (has real values → blocks candidates).
    all_rows = fetchall(conn, """
        SELECT e.ticker, e.date,
               e.sm_val, e.bm_val, e.sri, e.rpr, e.mf_ratio,
               e.price_close, e.price_change_pct, e.phase,
               COALESCE(e.ma5,          ph.ma5)          AS ma5,
               COALESCE(e.bb_mid,       ph.bb_mid)        AS bb_mid,
               COALESCE(e.bb_upper,     ph.bb_upper)      AS bb_upper,
               COALESCE(e.bb_lower,     ph.bb_lower)      AS bb_lower,
               COALESCE(e.is_sideways,  ph.is_sideways)   AS is_sideways,
               COALESCE(e.close_pos,    ph.close_pos)     AS close_pos,
               COALESCE(e.prev_high_break, ph.prev_high_break) AS prev_high_break,
               COALESCE(e.prev_close_below_ma5, ph.prev_close_below_ma5) AS prev_close_below_ma5,
               COALESCE(e.ma5_price_streak,     ph.ma5_price_streak)     AS ma5_price_streak,
               COALESCE(e.daily_value,          ph.daily_value)          AS daily_value,
               e.days_since_near_bb_mid
        FROM eod_summary e
        LEFT JOIN price_history ph
          ON ph.ticker = e.ticker
          AND ph.date = substr(e.date,7,4)||'-'||substr(e.date,4,2)||'-'||substr(e.date,1,2)
        WHERE e.price_close IS NOT NULL
        ORDER BY e.ticker, e.date
    """)
    if not all_rows:
        with _bsjp_lock:
            _bsjp_result = _empty_all
        return _empty

    all_days: dict = _dd(dict)
    for r in all_rows:
        all_days[r["date"]][r["ticker"]] = r

    all_sorted_dates = sorted(all_days.keys(), key=_to_cmp)

    # Build next-trading-day map from price_history (actual IDX calendar, not
    # eod_summary which only has days with Telegram data).  BSJP exits T+1 using
    # 15m candles — the exit date must be the real next bursa day regardless of
    # whether eod_summary has data for it.
    _ph_rows = fetchall(conn, "SELECT DISTINCT date FROM price_history ORDER BY date")
    if _ph_rows:
        _ph_dmy = sorted(
            [f"{r['date'][8:10]}-{r['date'][5:7]}-{r['date'][:4]}" for r in _ph_rows],
            key=_to_cmp,
        )
        date_to_next = {d: _ph_dmy[i + 1] for i, d in enumerate(_ph_dmy[:-1])}
    else:
        date_to_next = {
            d: all_sorted_dates[i + 1]
            for i, d in enumerate(all_sorted_dates)
            if i + 1 < len(all_sorted_dates)
        }

    if date_from and date_to:
        fc = _to_cmp(date_from)
        tc = _to_cmp(date_to)
        signal_dates = [d for d in all_sorted_dates if fc <= _to_cmp(d) <= tc]
    else:
        signal_dates = all_sorted_dates

    if not signal_dates:
        with _bsjp_lock:
            _bsjp_result = _empty_all
        return _empty

    # ── Batch-fetch harga 15:45 dan 09:00 untuk PRE signal ──────────────────────
    signal_ymds = list({_dmy_to_ymd(d) for d in signal_dates})
    pre_1545: dict = {}  # {(date_ymd, ticker): close}
    pre_0900: dict = {}  # {(date_ymd, ticker): open}

    if signal_ymds:
        for r in fetchall(conn, """
            SELECT LEFT(datetime, 10) AS date_ymd, ticker, close
            FROM price_history_15m
            WHERE LEFT(datetime, 10) = ANY(%s) AND RIGHT(datetime, 5) = '15:45'
        """, [signal_ymds]):
            v = r.get("close")
            if v is not None:
                try:
                    pre_1545[(str(r["date_ymd"]), r["ticker"])] = float(v)
                except (ValueError, TypeError):
                    pass

        for r in fetchall(conn, """
            SELECT LEFT(datetime, 10) AS date_ymd, ticker, open
            FROM price_history_15m
            WHERE LEFT(datetime, 10) = ANY(%s) AND RIGHT(datetime, 5) = '09:00'
        """, [signal_ymds]):
            v = r.get("open")
            if v is not None:
                try:
                    pre_0900[(str(r["date_ymd"]), r["ticker"])] = float(v)
                except (ValueError, TypeError):
                    pass

    dates_with_pre = {k[0] for k in pre_1545}

    # ── Pass 1: PRE signals only — ticker wajib punya 15:45 dan 09:00 candle ──────
    # day_results is keyed by universe: the scoring pass is shared, but each
    # universe gets its own TOP_N slice (see the slicing loop below).
    day_results: dict = {u: [] for u in UNIVERSES}
    ph15_needed: set  = set()
    # Resolved once, outside the loop — same displacement reasoning as the live
    # scan: a CA ticker reaching pre_pool would eat a TOP_N slot.
    excluded = excluded_tickers(conn)
    syr      = syariah_tickers()

    for date_str in signal_dates:
        next_date = date_to_next.get(date_str)
        if not next_date:
            continue
        date_ymd = _dmy_to_ymd(date_str)
        if date_ymd not in dates_with_pre:
            continue  # tidak ada data 15m sama sekali untuk tanggal ini

        pre_pool = []
        for ticker, row in all_days[date_str].items():
            if ticker in excluded:
                continue
            close_1545 = pre_1545.get((date_ymd, ticker))
            open_0900  = pre_0900.get((date_ymd, ticker))
            if not close_1545 or not open_0900 or open_0900 <= 0:
                continue  # wajib ada 15:45 dan 09:00 — tidak ada = skip

            pre_row = dict(row)
            pre_row["price_close"]      = close_1545
            pre_row["price_change_pct"] = (close_1545 - open_0900) / open_0900 * 100

            if _is_ara(pre_row):
                continue
            sig = algo.signal_detail(ticker, pre_row)
            if not sig:
                continue

            eod_close = float(row.get("price_close") or 0)
            if not eod_close > 0:
                continue
            entry_new    = _to_tick(eod_close)
            sig["entry"] = entry_new
            sig["tp1"]   = _to_tick(eod_close * 1.01)
            sig["tp2"]   = _to_tick(eod_close * 1.02)
            sig["sl"]    = algo._compute_sl(row, entry_new, sig["sl_type"])
            score        = _compute_score(pre_row, sig["setup"])
            pre_pool.append((score, ticker, sig))

        if not pre_pool:
            continue

        pre_pool.sort(key=lambda x: -x[0])
        next_ymd = _dmy_to_ymd(next_date)

        # One scored pool, one TOP_N slice per universe. The sharia slice must
        # re-rank from sharia-only candidates so lower-ranked sharia signals are
        # promoted into the slots the excluded tickers would have taken. Filtering
        # the 'full' trades afterwards would instead leave those slots empty and
        # understate the sharia strategy — measured: cutting 30% of the universe
        # costs only ~6% of trades precisely because of this promotion.
        #
        # `u` here — NOT `universe` — on purpose: this function also takes a
        # `universe` parameter, and Python for-loops don't scope their target
        # variable. Reusing the name silently clobbered the parameter on every
        # date with a non-empty pool, so `return results.get(universe)` always
        # read back "syariah" regardless of what the caller asked for — every
        # 'full' backtest/portfolio caller was silently getting syariah-only
        # results. Do not rename this back to `universe`.
        for u, pool in (
            ("full",    pre_pool),
            ("syariah", [c for c in pre_pool if c[1] in syr]),
        ):
            day_trades = [(ticker, sig) for _, ticker, sig in pool[:TOP_N]]
            if not day_trades:
                continue
            for ticker, _ in day_trades:
                ph15_needed.add((next_ymd, ticker))
            day_results[u].append((date_str, next_date, next_ymd, day_trades))

    # ── Pass 2: batch-fetch 15m candles untuk exit ───────────────────────────────
    candles_map: dict = _dd(list)
    if ph15_needed:
        next_ymds  = list({k[0] for k in ph15_needed})
        tickers_15 = list({k[1] for k in ph15_needed})
        for r in fetchall(conn, """
            SELECT datetime, ticker, open, high, low, close
            FROM price_history_15m
            WHERE LEFT(datetime, 10) = ANY(%s) AND ticker = ANY(%s)
            ORDER BY ticker, datetime
        """, [next_ymds, tickers_15]):
            key = (str(r["datetime"])[:10], r["ticker"])
            if key in ph15_needed:
                candles_map[key].append(r)

    # ── Pass 3: evaluate exits + build leaderboard, once per universe ────────────
    # candles_map is shared: Pass 2 fetched the union of both universes' picks,
    # so the second universe costs no extra query — only the in-memory replay.
    def _evaluate(day_res: list) -> dict:
        setup_trades: dict = _dd(list)
        for date_str, next_date, next_ymd, day_trades in day_res:
            for ticker, sig in day_trades:
                candles = candles_map.get((next_ymd, ticker))
                if not candles:
                    setup_trades[sig["setup"]].append({
                        "ticker":     ticker,
                        "date":       date_str,
                        "exit_date":  next_date,
                        "exit_time":  None,
                        "entry":      sig["entry"],
                        "exit_price": None,
                        "status":     "NO_DATA",
                        "reason":     "Data 15m tidak lengkap",
                        "pnl_pct":    None,
                    })
                    continue
                res       = eval_exit_15m(sig["entry"], sig["tp1"], sig["tp2"], sig["sl"], candles)
                t_str     = str(res.get("exit_time") or "")
                exit_time = t_str[-5:] if len(t_str) >= 5 else None
                setup_trades[sig["setup"]].append({
                    "ticker":     ticker,
                    "date":       date_str,
                    "exit_date":  next_date,
                    "exit_time":  exit_time,
                    "entry":      sig["entry"],
                    "exit_price": res.get("exit_price") or sig["entry"],
                    "status":     res["status"],
                    "reason":     res["reason"],
                    "pnl_pct":    res.get("pnl_pct"),
                })

        leaderboard = []
        for setup, trades in setup_trades.items():
            wins      = [t for t in trades if t["status"] == "Berhasil"]
            losses    = [t for t in trades if t["status"] == "Gagal"]
            total     = len(trades)
            all_pnl   = [t["pnl_pct"] for t in trades  if t["pnl_pct"] is not None]
            win_pnl   = [t["pnl_pct"] for t in wins     if t["pnl_pct"] is not None]
            loss_pnl  = [t["pnl_pct"] for t in losses   if t["pnl_pct"] is not None]
            leaderboard.append({
                "setup":      setup,
                "total":      total,
                "wins":       len(wins),
                "losses":     len(losses),
                "win_rate":   round(len(wins) / total * 100, 1) if total else 0,
                "expectancy": round(sum(all_pnl)  / total,       2) if all_pnl  else 0,
                "avg_win":    round(sum(win_pnl)  / len(win_pnl),  2) if win_pnl  else None,
                "avg_loss":   round(sum(loss_pnl) / len(loss_pnl), 2) if loss_pnl else None,
                "details":    trades,
            })
        leaderboard.sort(key=lambda x: x["expectancy"], reverse=True)

        all_trades = [t for tl in setup_trades.values() for t in tl]
        total      = len(all_trades)
        total_wins = sum(1 for t in all_trades if t["status"] == "Berhasil")
        all_pnl    = [t["pnl_pct"] for t in all_trades if t["pnl_pct"] is not None]

        return {
            "leaderboard":        leaderboard,
            "total_trades":       total,
            "total_wins":         total_wins,
            "total_losses":       total - total_wins,
            "overall_win_rate":   round(total_wins / total * 100, 1) if total else None,
            "overall_expectancy": round(sum(all_pnl) / total, 2)     if all_pnl else None,
            "setup_count":        len(leaderboard),
            "date_range":         f"{signal_dates[0]} - {signal_dates[-1]}" if signal_dates else "-",
            "computed_at":        datetime.now(WIB).strftime("%d-%m-%Y %H:%M"),
        }

    results = {u: _evaluate(day_results[u]) for u in UNIVERSES}

    with _bsjp_lock:
        _bsjp_result = results

    log.info("BSJP backtest: %d trades full / %d syariah",
             results["full"]["total_trades"], results["syariah"]["total_trades"])

    return results.get(universe) or results["full"]


def request_bsjp_backtest(date_from: str = None, date_to: str = None):
    """Non-blocking BSJP backtest trigger."""
    global _bsjp_running, _bsjp_error

    def _run():
        global _bsjp_running, _bsjp_error
        try:
            from core.db import get_db
            run_bsjp_backtest(get_db(), date_from=date_from, date_to=date_to)
            _bsjp_error = None
        except Exception as e:
            log.error("BSJP backtest error: %s", e)
            _bsjp_error = str(e)
        finally:
            from core.db import close_db
            close_db()
            _bsjp_running = False

    with _bsjp_lock:
        if _bsjp_running:
            return False
        _bsjp_running = True
        _bsjp_error   = None

    threading.Thread(target=_run, daemon=True, name="bsjp-backtest").start()
    return True


def get_bsjp_status() -> dict:
    with _bsjp_lock:
        if _bsjp_running:
            return {"status": "running"}
        if _bsjp_error:
            return {"status": "error", "result": _bsjp_error}
        return {"status": "done"}


def get_bsjp_result(universe: str = "full") -> dict | None:
    """Cached BSJP backtest for one universe ('full' or 'syariah').

    run_bsjp_backtest computes both in a single pass and stores them keyed by
    universe, so switching modes never triggers a recompute.
    """
    with _bsjp_lock:
        if not _bsjp_result:
            return None
        return _bsjp_result.get(universe) or _bsjp_result.get("full")


def get_ticker_fitness(conn, ticker: str, days: int = 90) -> dict:
    """
    Per-ticker backtest stats extracted from cached _backtest_result.
    Returns the full format expected by flow.html loadTickerFitness().
    """
    with _backtest_lock:
        cached = _backtest_result

    if not cached:
        return {"ticker": ticker, "total_trades": 0, "error": "No backtest data"}

    period   = cached.get("date_range", "")
    computed = cached.get("computed_at", "")

    # Extract all trades for this ticker from the leaderboard details
    ticker_trades = []
    entry_phase_map = defaultdict(list)

    for entry_row in cached.get("leaderboard", []):
        entry_phase = entry_row.get("entry", "")
        for d in entry_row.get("details", []):
            if d["ticker"] == ticker and d.get("profit", 0) >= -50:
                trade = {**d, "entry_phase": entry_phase}
                ticker_trades.append(trade)
                entry_phase_map[entry_phase].append(trade)

    if not ticker_trades:
        return {"ticker": ticker, "total_trades": 0, "period": period}

    wins   = [t for t in ticker_trades if t["profit"] > 0]
    losses = [t for t in ticker_trades if t["profit"] <= 0]
    gp     = sum(t["profit"] for t in wins)
    gl     = abs(sum(t["profit"] for t in losses))
    pf     = round(gp / gl, 2) if gl > 0 else (99.0 if gp > 0 else 0)

    # Per-phase breakdown
    phase_stats = []
    best_phase  = None
    best_gp     = -999

    for ph, ph_trades in entry_phase_map.items():
        ph_wins = [t for t in ph_trades if t["profit"] > 0]
        ph_gl   = abs(sum(t["profit"] for t in ph_trades if t["profit"] <= 0))
        ph_gp   = sum(t["profit"] for t in ph_trades if t["profit"] > 0)
        ph_pf   = round(ph_gp / ph_gl, 2) if ph_gl > 0 else (99.0 if ph_gp > 0 else 0)
        ph_wr   = round(len(ph_wins) / len(ph_trades) * 100, 1) if ph_trades else 0
        ph_avg  = round(sum(t["profit"] for t in ph_trades) / len(ph_trades), 2)
        phase_stats.append({
            "phase": ph, "trades": len(ph_trades),
            "win_rate": ph_wr, "profit_factor": ph_pf, "avg_profit": ph_avg,
        })
        if ph_gp > best_gp:
            best_gp    = ph_gp
            best_phase = {
                "phase": ph, "win_rate": ph_wr, "profit_factor": ph_pf,
                "avg_profit": ph_avg, "trades": len(ph_trades),
            }

    trades_sorted = sorted(
        ticker_trades,
        key=lambda t: _to_cmp(t.get("entry_date", "")),
        reverse=True,
    )

    return {
        "ticker":        ticker,
        "total_trades":  len(ticker_trades),
        "win_rate":      round(len(wins) / len(ticker_trades) * 100, 1),
        "profit_factor": pf,
        "avg_profit":    round(sum(t["profit"] for t in ticker_trades) / len(ticker_trades), 2),
        "best_phase":    best_phase,
        "phase_stats":   sorted(phase_stats, key=lambda x: x["avg_profit"], reverse=True),
        "wins":          len(wins),
        "losses":        len(losses),
        "period":        period,
        "computed_at":   computed,
        "trades":        trades_sorted,
    }
