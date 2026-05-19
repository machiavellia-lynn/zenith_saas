"""
algo/algo_bsjp.py — BSJP Overnight Swing Algorithm (6 setups)

Pure functions only — zero DB, zero HTTP.
Entry EOD, exit N+1 berdasarkan TP/SL.

Setup priority (urutan cek):
1. POWER_BREAK_V21
2. POWER_BREAK_V22
3. SMA5_BREAKOUT_V13
4. SMA5_BREAKOUT_V11
5. BB_PULLBACK
6. SMA5_PULLBACK_V12
"""


def _f(val, default=None):
    try:
        return float(val) if val is not None else default
    except (ValueError, TypeError):
        return default


def _b(val):
    if isinstance(val, bool):
        return val
    if isinstance(val, str):
        return val.lower() in ("true", "1", "yes")
    return bool(val) if val is not None else False


def _i(val, default=0):
    try:
        return int(val) if val is not None else default
    except (ValueError, TypeError):
        return default


class BSJPAlgo:
    """BSJP overnight swing: 6 setups, TP/SL exit."""

    name = "BSJP"

    # SM Gate thresholds
    MIN_SRI      = 1.2
    MAX_RPR      = 0.55
    MIN_MF_RATIO = 50.0
    MIN_RSM      = 60.0

    # Setup-specific
    POWER_BREAK_MIN_VALUE = 5_000_000_000  # 5 Miliar IDR

    SL_MAP = {
        "POWER_BREAK_V21":   "FIXED_2PCT",
        "POWER_BREAK_V22":   "FIXED_2PCT",
        "SMA5_BREAKOUT_V13": "MA5",
        "SMA5_BREAKOUT_V11": "MA5",
        "BB_PULLBACK":       "BB_MID",
        "SMA5_PULLBACK_V12": "MA5",
    }

    def signal(self, ticker: str, row: dict) -> str | None:
        return "BUY" if self.signal_detail(ticker, row) else None

    def signal_detail(self, ticker: str, row: dict) -> dict | None:
        """
        Return detail signal atau None.
        {
            "action": "BUY",
            "setup":  str,
            "entry":  int,
            "tp1":    int,
            "tp2":    int,
            "sl":     int,
            "sl_type": str,
        }
        """
        price_close = _f(row.get("price_close"))
        if price_close is None or price_close <= 0:
            return None

        if not self._sm_gate(row):
            return None

        setups = [
            ("POWER_BREAK_V21",   self._setup_power_break_v21),
            ("POWER_BREAK_V22",   self._setup_power_break_v22),
            ("SMA5_BREAKOUT_V13", self._setup_sma5_breakout_v13),
            ("SMA5_BREAKOUT_V11", self._setup_sma5_breakout_v11),
            ("BB_PULLBACK",       self._setup_bb_pullback),
            ("SMA5_PULLBACK_V12", self._setup_sma5_pullback_v12),
        ]

        for name, fn in setups:
            if fn(row):
                entry   = round(price_close)
                sl_type = self.SL_MAP[name]
                sl      = self._compute_sl(row, entry, sl_type)
                return {
                    "action":  "BUY",
                    "setup":   name,
                    "entry":   entry,
                    "tp1":     round(price_close * 1.01),
                    "tp2":     round(price_close * 1.02),
                    "sl":      sl,
                    "sl_type": sl_type,
                }

        return None

    def _compute_sl(self, row: dict, entry: int, sl_type: str) -> int:
        if sl_type == "MA5":
            ma5 = _f(row.get("ma5"), 0)
            return round(ma5) if ma5 > 0 else round(entry * 0.98)
        elif sl_type == "BB_MID":
            bb_mid = _f(row.get("bb_mid"), 0)
            return round(bb_mid) if bb_mid > 0 else round(entry * 0.98)
        return round(entry * 0.98)

    def _sm_gate(self, row: dict) -> bool:
        phase = row.get("phase", "")
        if phase in {"UPTHRUST", "DISTRI"}:
            return False
        if _f(row.get("sri"), 0) < self.MIN_SRI:
            return False
        if _f(row.get("rpr"), 1) > self.MAX_RPR:
            return False
        if _f(row.get("mf_ratio"), 0) < self.MIN_MF_RATIO:
            return False
        sm  = _f(row.get("sm_val"), 0)
        bm  = abs(_f(row.get("bm_val"), 0))
        rsm = sm / (sm + bm) * 100 if (sm + bm) > 0 else 0
        if rsm < self.MIN_RSM:
            return False
        return True

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
