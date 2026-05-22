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


BLACKLIST = {"HATM", "JAST", "CYBR", "AYLS", "VAST", "VTNY"}

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
    MAX_RPR      = 0.55
    MIN_MF_RATIO = 50.0
    MIN_RSM      = 60.0
    POWER_BREAK_MIN_VALUE = 5_000_000_000

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

        for name, fn in [
            ("POWER_BREAK_V21",   self._setup_power_break_v21),
            ("POWER_BREAK_V22",   self._setup_power_break_v22),
            ("SMA5_BREAKOUT_V13", self._setup_sma5_breakout_v13),
            ("SMA5_BREAKOUT_V11", self._setup_sma5_breakout_v11),
            ("BB_PULLBACK",       self._setup_bb_pullback),
            ("SMA5_PULLBACK_V12", self._setup_sma5_pullback_v12),
        ]:
            if fn(row):
                entry   = round(price_close)
                sl_type = self.SL_MAP[name]
                return {
                    "setup":   name,
                    "entry":   entry,
                    "tp1":     round(price_close * 1.01),
                    "tp2":     round(price_close * 1.02),
                    "sl":      self._compute_sl(row, entry, sl_type),
                    "sl_type": sl_type,
                }
        return None

    def _sm_gate(self, row: dict) -> bool:
        if row.get("phase") in {"UPTHRUST", "DISTRI"}:
            return False
        if _f(row.get("sri"), 0) < self.MIN_SRI:
            return False
        if _f(row.get("rpr"), 1.0) > self.MAX_RPR:
            return False
        if _f(row.get("mf_ratio"), 0) < self.MIN_MF_RATIO:
            return False
        sm  = _f(row.get("sm_val"), 0)
        bm  = abs(_f(row.get("bm_val"), 0))
        rsm = sm / (sm + bm) * 100 if (sm + bm) > 0 else 0
        return rsm >= self.MIN_RSM

    def _compute_sl(self, row: dict, entry: int, sl_type: str) -> int:
        if sl_type == "MA5":
            ma5 = _f(row.get("ma5"), 0)
            return round(ma5) if ma5 > 0 else round(entry * 0.98)
        elif sl_type == "BB_MID":
            bb_mid = _f(row.get("bb_mid"), 0)
            return round(bb_mid) if bb_mid > 0 else round(entry * 0.98)
        return round(entry * 0.98)

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
