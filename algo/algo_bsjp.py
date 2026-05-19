"""algo/algo_bsjp.py — BSJP signal generation. Pure functions, zero DB."""

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
    "TRENDING_PREV_HIGH": 0.784,
    "PULLBACK_MA5":       0.638,
    "PULLBACK_BB":        0.596,
    "CROSS_MA5":          0.550,
    "BREAKOUT_MA5":       0.520,
    "BREAKOUT_SIDEWAYS":  0.520,
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
    MIN_MF_RATIO = 50.0
    MIN_RSM      = 60.0
    BREAKOUT_MIN_VALUE = 5_000_000_000

    SETUP_MAX_RPR = {
        "BREAKOUT_MA5":       0.45,
        "BREAKOUT_SIDEWAYS":  0.35,
        "TRENDING_PREV_HIGH": 0.40,
        "CROSS_MA5":          0.25,
        "PULLBACK_BB":        0.25,
        "PULLBACK_MA5":       0.50,
    }

    def signal_detail(self, ticker: str, row: dict) -> dict | None:
        price_close = _f(row.get("price_close"))
        if not price_close or price_close <= 0:
            return None
        if not self._sm_gate(row):
            return None

        rpr = _f(row.get("rpr"), 1.0)
        for name, fn in [
            ("BREAKOUT_MA5",       self._setup_breakout_ma5),
            ("BREAKOUT_SIDEWAYS",  self._setup_breakout_sideways),
            ("TRENDING_PREV_HIGH", self._setup_trending_prev_high),
            ("CROSS_MA5",          self._setup_cross_ma5),
            ("PULLBACK_BB",        self._setup_pullback_bb),
            ("PULLBACK_MA5",       self._setup_pullback_ma5),
        ]:
            if rpr <= self.SETUP_MAX_RPR[name] and fn(row):
                entry = round(price_close)
                return {
                    "setup": name,
                    "entry": entry,
                    "tp1":   round(price_close * 1.01),
                    "tp2":   round(price_close * 1.02),
                    "sl":    self._resolve_sl(name, row, entry),
                }
        return None

    def _sm_gate(self, row):
        if row.get("phase") in {"UPTHRUST", "DISTRI"}:
            return False
        if _f(row.get("sri"), 0) < self.MIN_SRI:
            return False
        if _f(row.get("mf_ratio"), 0) < self.MIN_MF_RATIO:
            return False
        sm  = _f(row.get("sm_val"), 0)
        bm  = abs(_f(row.get("bm_val"), 0))
        rsm = sm / (sm + bm) * 100 if (sm + bm) > 0 else 0
        return rsm >= self.MIN_RSM

    def _resolve_sl(self, setup, row, entry):
        if setup in ("BREAKOUT_MA5", "BREAKOUT_SIDEWAYS"):
            return round(entry * 0.98)
        elif setup in ("TRENDING_PREV_HIGH", "CROSS_MA5", "PULLBACK_MA5"):
            ma5 = _f(row.get("ma5"), 0)
            return round(ma5) if ma5 > 0 else round(entry * 0.98)
        elif setup == "PULLBACK_BB":
            bb_mid = _f(row.get("bb_mid"), 0)
            return round(bb_mid) if bb_mid > 0 else round(entry * 0.98)
        return round(entry * 0.98)

    def _setup_breakout_ma5(self, row):
        return (
            _f(row.get("price_change_pct"), 0) >= 10.0
            and _f(row.get("price_close"), 0) > _f(row.get("ma5"), 0)
            and _b(row.get("prev_close_below_ma5"))
            and _f(row.get("daily_value"), 0) >= self.BREAKOUT_MIN_VALUE
        )

    def _setup_breakout_sideways(self, row):
        return (
            _f(row.get("price_change_pct"), 0) >= 10.0
            and _f(row.get("price_close"), 0) > _f(row.get("ma5"), 0)
            and _b(row.get("is_sideways"))
            and _f(row.get("daily_value"), 0) >= self.BREAKOUT_MIN_VALUE
        )

    def _setup_trending_prev_high(self, row):
        return (
            _i(row.get("ma5_price_streak"), 0) >= 3
            and _b(row.get("prev_high_break"))
            and _f(row.get("price_change_pct"), 0) > 0
            and _f(row.get("price_close"), 0) > _f(row.get("ma5"), 0)
        )

    def _setup_cross_ma5(self, row):
        return (
            _b(row.get("prev_close_below_ma5"))
            and _f(row.get("price_change_pct"), 0) > 0
            and _f(row.get("price_close"), 0) > _f(row.get("ma5"), 0)
            and _i(row.get("ma5_price_streak"), 0) == 1
        )

    def _setup_pullback_bb(self, row):
        bb_mid = _f(row.get("bb_mid"), None)
        if bb_mid is None:
            return False
        price_close = _f(row.get("price_close"), 0)
        days_since  = row.get("days_since_near_bb_mid")
        first_touch = days_since is None or _i(days_since, -1) >= 10
        return (
            _f(row.get("price_change_pct"), 0) < 0
            and price_close >= bb_mid
            and price_close <= bb_mid * 1.03
            and first_touch
        )

    def _setup_pullback_ma5(self, row):
        return (
            _f(row.get("price_change_pct"), 0) < 0
            and _f(row.get("price_close"), 0) >= _f(row.get("ma5"), 0)
            and _i(row.get("ma5_price_streak"), 0) >= 1
        )
