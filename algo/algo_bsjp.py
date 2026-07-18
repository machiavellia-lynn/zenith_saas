"""algo/algo_bsjp.py — BSJP signal generation. Pure functions, zero DB.

Setup priority (urutan cek):
1. POWER_BREAK_V21  — breakout with prev close below MA5
2. POWER_BREAK_V22  — breakout in sideways range
3. SMA5_BREAKOUT_V13 — trending, break prev high, streak >= 3
4. SMA5_BREAKOUT_V11 — fresh MA5 cross (streak == 1)
5. BB_PULLBACK       — pullback ke BB midline, first touch
6. SMA5_PULLBACK_V12 — pullback ke MA5, streak >= 1
"""

def _f(val, default=None):
    try: return float(val) if val is not None else default
    except (ValueError, TypeError): return default

def _b(val):
    if isinstance(val, bool): return val
    if isinstance(val, str): return val.lower() in ("true", "1", "yes")
    return bool(val) if val is not None else False

def _i(val, default=0):
    try: return int(val) if val is not None else default
    except (ValueError, TypeError): return default


# Static quality blacklist — permanent, manual. NOT for corporate actions:
# CA tickers are dated and data-driven, and live in the corporate_events table.
# Consumers should call algo.corporate_actions.excluded_tickers(conn), which
# merges this set with confirmed CA tickers.
BLACKLIST = {"HATM", "JAST", "CYBR", "AYLS", "VAST", "VTNY"}


def _to_tick(price: float) -> int:
    """Round price to nearest valid IDX tick (fraksi harga BEI)."""
    if price < 200:
        tick = 1
    elif price < 500:
        tick = 2
    elif price < 5000:
        tick = 5
    else:
        tick = 25
    return int(round(price / tick) * tick)

def _is_ara(row: dict) -> bool:
    price  = _f(row.get("price_close"), 0)
    change = _f(row.get("price_change_pct"), 0)
    if price < 200:     return change > 34
    elif price <= 5000: return change > 24
    else:               return change > 19


SETUP_WR = {
    "SMA5_BREAKOUT_V13": 0.784,
    "SMA5_PULLBACK_V12": 0.638,
    "BB_PULLBACK":       0.596,
    "SMA5_BREAKOUT_V11": 0.550,
    "POWER_BREAK_V21":   0.520,
    "POWER_BREAK_V22":   0.520,
}

def _compute_score(row: dict, setup: str) -> float:
    def _fv(v, d=0.0):
        try: return float(v) if v is not None else d
        except: return d

    sm  = _fv(row.get("sm_val"))
    bm  = abs(_fv(row.get("bm_val")))
    rsm = sm / (sm + bm) * 100 if (sm + bm) > 0 else 0
    rsm_n = max(0.0, min(1.0, (rsm - 60) / 40))

    sri_n     = max(0.0, min(1.0, (_fv(row.get("sri"), 1.2) - 1.2) / 3.8))
    setup_wr  = SETUP_WR.get(setup, 0.5)
    close_pos = max(0.0, min(1.0, _fv(row.get("close_pos"), 0.5)))
    mf_n      = max(0.0, min(1.0, (_fv(row.get("mf_ratio"), 50) - 50) / 50))

    return round(rsm_n*0.30 + sri_n*0.25 + setup_wr*0.25 + close_pos*0.10 + mf_n*0.10, 4)


class BSJPAlgo:
    name = "BSJP"
    MIN_SRI      = 1.2
    MIN_RSM      = 60.0
    POWER_BREAK_MIN_VALUE = 5_000_000_000

    # RPR dicek per-setup (bukan di SM Gate)
    SETUP_MAX_RPR = {
        "POWER_BREAK_V21":   0.45,
        "POWER_BREAK_V22":   0.35,
        "SMA5_BREAKOUT_V13": 0.40,
        "SMA5_BREAKOUT_V11": 0.25,
        "BB_PULLBACK":       0.25,
        "SMA5_PULLBACK_V12": 0.50,
    }

    SL_MAP = {
        "POWER_BREAK_V21":   "FIXED_2PCT",
        "POWER_BREAK_V22":   "FIXED_2PCT",
        "SMA5_BREAKOUT_V13": "MA5",
        "SMA5_BREAKOUT_V11": "MA5",
        "BB_PULLBACK":       "BB_MID",
        "SMA5_PULLBACK_V12": "MA5",
    }

    def signal_detail(self, ticker: str, row: dict) -> dict | None:
        price_close = _f(row.get("price_close"))
        if not price_close or price_close <= 0:
            return None
        if not self._sm_gate(row):
            return None

        rpr = _f(row.get("rpr"), 1.0)
        for name, fn in [
            ("POWER_BREAK_V21",   self._setup_power_break_v21),
            ("POWER_BREAK_V22",   self._setup_power_break_v22),
            ("SMA5_BREAKOUT_V13", self._setup_sma5_breakout_v13),
            ("SMA5_BREAKOUT_V11", self._setup_sma5_breakout_v11),
            ("BB_PULLBACK",       self._setup_bb_pullback),
            ("SMA5_PULLBACK_V12", self._setup_sma5_pullback_v12),
        ]:
            if rpr <= self.SETUP_MAX_RPR[name] and fn(row):
                entry   = _to_tick(price_close)
                sl_type = self.SL_MAP[name]
                return {
                    "setup":   name,
                    "entry":   entry,
                    "tp1":     _to_tick(price_close * 1.01),
                    "tp2":     _to_tick(price_close * 1.02),
                    "sl":      self._compute_sl(row, entry, sl_type),
                    "sl_type": sl_type,
                }
        return None

    def _sm_gate(self, row: dict) -> bool:
        if row.get("phase") in {"UPTHRUST", "DISTRI"}:
            return False
        if _f(row.get("sri"), 0) < self.MIN_SRI:
            return False
        sm  = _f(row.get("sm_val"), 0)
        bm  = abs(_f(row.get("bm_val"), 0))
        rsm = sm / (sm + bm) * 100 if (sm + bm) > 0 else 0
        return rsm >= self.MIN_RSM

    def _compute_sl(self, row: dict, entry: int, sl_type: str) -> int:
        if sl_type == "MA5":
            ma5 = _f(row.get("ma5"), 0)
            return _to_tick(ma5) if ma5 > 0 else _to_tick(entry * 0.98)
        elif sl_type == "BB_MID":
            bb_mid = _f(row.get("bb_mid"), 0)
            return _to_tick(bb_mid) if bb_mid > 0 else _to_tick(entry * 0.98)
        return _to_tick(entry * 0.98)

    def _setup_power_break_v21(self, row: dict) -> bool:
        return (
            _f(row.get("price_change_pct"), 0) >= 10.0
            and _f(row.get("price_close"), 0) > _f(row.get("ma5"), 0)
            and _b(row.get("prev_close_below_ma5"))
            and _f(row.get("daily_value"), 0) >= self.POWER_BREAK_MIN_VALUE
        )

    def _setup_power_break_v22(self, row: dict) -> bool:
        return (
            _f(row.get("price_change_pct"), 0) >= 10.0
            and _f(row.get("price_close"), 0) > _f(row.get("ma5"), 0)
            and _b(row.get("is_sideways"))
            and _f(row.get("daily_value"), 0) >= self.POWER_BREAK_MIN_VALUE
        )

    def _setup_sma5_breakout_v13(self, row: dict) -> bool:
        return (
            _i(row.get("ma5_price_streak"), 0) >= 3
            and _b(row.get("prev_high_break"))
            and _f(row.get("price_change_pct"), 0) > 0
            and _f(row.get("price_close"), 0) > _f(row.get("ma5"), 0)
        )

    def _setup_sma5_breakout_v11(self, row: dict) -> bool:
        return (
            _b(row.get("prev_close_below_ma5"))
            and _f(row.get("price_change_pct"), 0) > 0
            and _f(row.get("price_close"), 0) > _f(row.get("ma5"), 0)
            and _i(row.get("ma5_price_streak"), 0) == 1
        )

    def _setup_bb_pullback(self, row: dict) -> bool:
        bb_mid = _f(row.get("bb_mid"), None)
        if bb_mid is None:
            return False
        price_close = _f(row.get("price_close"), 0)
        days_since  = row.get("days_since_near_bb_mid")
        first_touch = (days_since is None or _i(days_since, -1) >= 10)
        return (
            _f(row.get("price_change_pct"), 0) < 0
            and price_close >= bb_mid
            and price_close <= bb_mid * 1.03
            and first_touch
        )

    def _setup_sma5_pullback_v12(self, row: dict) -> bool:
        return (
            _f(row.get("price_change_pct"), 0) < 0
            and _f(row.get("price_close"), 0) >= _f(row.get("ma5"), 0)
            and _i(row.get("ma5_price_streak"), 0) >= 1
        )


def eval_exit_15m(entry: int, tp1: int, tp2: int, sl: int, candles: list) -> dict:
    """Evaluate BSJP exit via 15m candles (oldest-first).
    candles: list of dicts with keys: datetime, open, high, low, close."""
    if not candles:
        return {"status": "Gagal", "reason": "NO_DATA", "exit_price": None, "pnl_pct": None}

    for i, c in enumerate(candles):
        o = _f(c.get("open"))
        h = _f(c.get("high"))
        l = _f(c.get("low"))
        t = c.get("datetime")

        if o is None:
            continue

        if i == 0:
            # Gap check first — the realistic fill if price already jumped past
            # a level at the open. If it didn't gap, fall through to the same
            # intra-candle high/low check every later candle gets below —
            # a stop or target can still be hit within candle 0's own range.
            if o <= sl:
                return _exit_res("Gagal", "SL[gap]", o, t, entry)
            if tp2 and o >= tp2:
                return _exit_res("Berhasil", "TP2[gap]", o, t, entry)
            if tp1 and o >= tp1:
                if h and tp2 and h >= tp2:
                    return _exit_res("Berhasil", "TP2", tp2, t, entry)
                return _exit_res("Berhasil", "TP1[gap]", o, t, entry)

        if l is not None and l <= sl:
            mid = (sl + tp1) / 2 if tp1 else sl
            if h and tp2 and h >= tp2:
                return _exit_res("Gagal", "SL", sl, t, entry) if o <= mid else _exit_res("Berhasil", "TP2", tp2, t, entry)
            if h and tp1 and h >= tp1:
                return _exit_res("Gagal", "SL", sl, t, entry) if o <= mid else _exit_res("Berhasil", "TP1", tp1, t, entry)
            return _exit_res("Gagal", "SL", sl, t, entry)
        if h and tp2 and h >= tp2:
            return _exit_res("Berhasil", "TP2", tp2, t, entry)
        if h and tp1 and h >= tp1:
            return _exit_res("Berhasil", "TP1", tp1, t, entry)

    last = candles[-1]
    lc = _f(last.get("close")) or entry
    return _exit_res("Gagal", "NO_TARGET", lc, last.get("datetime"), entry)


def _exit_res(status, reason, exit_price, exit_time, entry):
    ep  = round(exit_price) if exit_price else None
    pnl = round((exit_price - entry) / entry * 100, 4) if entry and exit_price else None
    return {"status": status, "reason": reason, "exit_price": ep, "exit_time": exit_time, "pnl_pct": pnl}
