"""
tests/test_analytics_daily.py — Unit tests for algo/analytics_daily.py

Strategy:
- _compute_atr_pct_hlc: pure function → direct tests (incl. regression for cc8ab41)
- _compute_one: patches fetchall + _get_prev_close to avoid DB
"""
import pytest
from algo.analytics_daily import _compute_atr_pct_hlc, _compute_one


# ── _compute_atr_pct_hlc ──────────────────────────────────────────────────────

def test_atr_empty_returns_default():
    assert _compute_atr_pct_hlc([]) == 2.5

def test_atr_single_row_returns_default():
    assert _compute_atr_pct_hlc([{"close": 100, "high": 105, "low": 95}]) == 2.5

def test_atr_uses_true_range_not_close_to_close():
    """Regression: cc8ab41 — ATR must use H/L/C True Range, not close-to-close."""
    rows = [
        {"close": 100, "high": 100, "low": 100},   # baseline
        {"close": 102, "high": 110, "low": 98},    # big range
    ]
    # TR = max(H-L=12, |H-prev_C|=10, |L-prev_C|=2) = 12
    # ATR% = 12/100*100 = 12.0%
    # close-to-close would wrongly give 2.0% — that's the old bug
    result = _compute_atr_pct_hlc(rows)
    assert result == 12.0, f"Expected 12.0 (True Range), got {result} (likely close-to-close regression)"

def test_atr_fallback_to_close_when_no_hl():
    """When high/low missing, fallback: H=L=C, so TR = |C - prev_C|."""
    rows = [
        {"close": 100, "high": None, "low": None},
        {"close": 103, "high": None, "low": None},
    ]
    # TR = max(0, |100-100|, |100-100|) with H=L=C=103 and prev_C=100
    # TR = max(103-103=0, |103-100|=3, |103-100|=3) = 3; ATR% = 3/100*100 = 3.0%
    result = _compute_atr_pct_hlc(rows)
    assert result == 3.0

def test_atr_multi_row_averages_period():
    rows = [
        {"close": 100, "high": 102, "low": 98},
        {"close": 100, "high": 104, "low": 96},   # TR = max(8, 4, 4) = 8 → 8%
        {"close": 100, "high": 106, "low": 94},   # TR = max(12, 6, 6) = 12 → 12%
    ]
    result = _compute_atr_pct_hlc(rows, period=2)
    assert result == 10.0  # avg(8%, 12%) = 10%

def test_atr_skips_zero_prev_close():
    rows = [
        {"close": 0,   "high": 0,   "low": 0},
        {"close": 100, "high": 105, "low": 95},
    ]
    # prev_c = 0 → skip, no valid TR → default 2.5
    assert _compute_atr_pct_hlc(rows) == 2.5

def test_atr_period_clamp():
    """If fewer rows than period, use all available."""
    rows = [
        {"close": 100, "high": 105, "low": 95},
        {"close": 102, "high": 107, "low": 97},   # TR = max(10, 7, 3) = 10 → 10%
    ]
    # Only 1 TR value, period=14 → still returns average of 1 value
    result = _compute_atr_pct_hlc(rows, period=14)
    assert result == 10.0


# ── _compute_one (mocked DB) ──────────────────────────────────────────────────

def _make_row(sm_val=100, bm_val=40, tx_sm=10, tx_bm=4, tx_count=14,
              price_close=1000, vwap_sm=950):
    return {
        "ticker": "BBRI", "sm_val": sm_val, "bm_val": bm_val,
        "tx_sm": tx_sm, "tx_bm": tx_bm, "tx_count": tx_count,
        "price_close": price_close, "vwap_sm": vwap_sm, "vwap_bm": None,
    }

def _make_ph(n=20, base_close=1000):
    """Generate n price_history rows with slight variation."""
    return [
        {"close": base_close + i, "high": base_close + i + 5,
         "low": base_close + i - 5, "date": f"2025-01-{i+1:02d}"}
        for i in range(n)
    ]

def _make_history(n=10, sm_val=100, bm_val=40):
    return [{"sm_val": sm_val, "bm_val": bm_val, "tx_count": 14,
             "tx_sm": 10, "tx_bm": 4, "price_close": 1000,
             "volx_gap": None}] * n


def _run_compute_one(row=None, history=None, ph=None, prev_close=950):
    row     = row     or _make_row()
    history = history or _make_history()
    ph      = ph      or _make_ph()
    return _compute_one("BBRI", "14-05-2026", row, history, ph, prev_close)


class TestComputeOne:
    def test_returns_all_keys(self):
        result = _run_compute_one()
        expected = {"sri", "mes", "volx_gap", "rpr", "atr_pct", "price_close",
                    "price_change_pct", "sm_sma10", "bm_sma10", "ma5", "ma13",
                    "ma34", "ma200", "rsi14", "cm_streak", "ma_structure",
                    "phase", "action", "watch", "trade_gate", "narrative"}
        assert expected.issubset(result.keys())

    def test_sri_zero_when_no_sm_history(self):
        history = [{"sm_val": 0, "bm_val": 40, "tx_count": 14,
                    "tx_sm": 0, "tx_bm": 4, "price_close": 1000,
                    "volx_gap": None}] * 5
        result = _run_compute_one(history=history)
        assert result["sri"] == 0

    def test_sri_positive_when_sm_dominant(self):
        # sm_val=200 with history mean=100 → SRI=2.0
        row = _make_row(sm_val=200)
        result = _run_compute_one(row=row)
        assert result["sri"] == pytest.approx(2.0, rel=0.1)

    def test_rpr_correct(self):
        # tx_bm=4, tx_total=14 → RPR = 4/14 ≈ 0.286
        result = _run_compute_one()
        assert result["rpr"] == pytest.approx(4 / 14, rel=0.01)

    def test_volx_gap_correct(self):
        # price_close=1000, vwap_sm=950 → volx_gap = (1000-950)/950*100 ≈ 5.26%
        result = _run_compute_one()
        assert result["volx_gap"] == pytest.approx((1000 - 950) / 950 * 100, rel=0.01)

    def test_volx_gap_none_when_no_price(self):
        row = _make_row(price_close=None)
        result = _run_compute_one(row=row, prev_close=None)
        assert result["volx_gap"] is None

    def test_price_change_pct_correct(self):
        # price_close=1000, prev_close=950 → change = (1000-950)/950*100 ≈ 5.26%
        result = _run_compute_one()
        assert result["price_change_pct"] == pytest.approx(5.26, rel=0.01)

    def test_price_change_pct_none_when_no_prev(self):
        result = _run_compute_one(prev_close=None)
        assert result["price_change_pct"] is None

    def test_phase_is_valid_string(self):
        result = _run_compute_one()
        valid_phases = {"SOS", "SPRING", "ABSORB", "ACCUM", "UPTHRUST", "DISTRI", "NEUTRAL"}
        assert result["phase"] in valid_phases

    def test_action_is_valid_string(self):
        result = _run_compute_one()
        assert result["action"] in {"BUY", "SELL", "HOLD"}

    def test_ma_structure_not_na_with_enough_history(self):
        ph = _make_ph(n=210)
        result = _run_compute_one(ph=ph)
        assert result["ma_structure"] != "N/A"
