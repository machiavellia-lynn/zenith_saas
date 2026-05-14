"""
tests/test_algo_wyckoff.py — Unit tests for algo/algo_wyckoff.py
"""
import pytest
from algo.algo_wyckoff import (
    classify_zenith_v3_1,
    get_action,
    get_watch_flag,
    detect_trade_detail_gate,
    get_ma_structure,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def classify(sri, rsm, rpr, pchg, bm_val=0, bm_sma10=0, atr_pct=2.0):
    return classify_zenith_v3_1(sri, rsm, rpr, pchg, bm_val, bm_sma10, atr_pct)


# ── classify_zenith_v3_1 ──────────────────────────────────────────────────────

def test_phase_neutral_when_pchg_none():
    assert classify(3.0, 70, 0.2, None) == "NEUTRAL"

def test_phase_sos():
    # pchg > th_up (1.6), rsm > 65, sri > 3.0
    assert classify(sri=3.5, rsm=70, rpr=0.2, pchg=2.0) == "SOS"

def test_phase_sos_relaxed_rsm():
    # v3.1: sri > 4.0 allows rsm > 60
    assert classify(sri=4.5, rsm=62, rpr=0.2, pchg=2.0) == "SOS"

def test_phase_upthrust():
    # pchg up, rsm < 40, rpr > 0.6
    assert classify(sri=1.0, rsm=30, rpr=0.7, pchg=2.0) == "UPTHRUST"

def test_phase_absorb():
    # sri > 2.0, rsm > 65, price flat
    assert classify(sri=2.5, rsm=70, rpr=0.2, pchg=0.1) == "ABSORB"

def test_phase_spring():
    # price down, rsm > 60, sri > 1.5
    assert classify(sri=2.0, rsm=65, rpr=0.2, pchg=-1.5) == "SPRING"

def test_phase_distri():
    # rsm < 40, price slightly down, rpr > 0.4, bm_gate open
    assert classify(sri=0.5, rsm=30, rpr=0.5, pchg=-0.5, bm_val=0, bm_sma10=0) == "DISTRI"

def test_phase_accum():
    # rsm > 60, sri > 1.0, no strong directional move
    assert classify(sri=1.5, rsm=65, rpr=0.2, pchg=0.3) == "ACCUM"

def test_phase_distri_blocked_by_bm_gate():
    # bm_gate fails: bm_val < bm_sma10 * 0.5 → should NOT return DISTRI
    result = classify(sri=0.5, rsm=30, rpr=0.5, pchg=-0.5, bm_val=10, bm_sma10=100)
    assert result != "DISTRI"


# ── get_action ────────────────────────────────────────────────────────────────

def test_action_sell_on_distri():
    assert get_action("DISTRI", pchg=-1.0) == "SELL"

def test_action_sell_on_upthrust():
    assert get_action("UPTHRUST", pchg=2.0) == "SELL"

def test_action_hold_on_neutral():
    assert get_action("NEUTRAL", pchg=0.0) == "HOLD"

def test_action_buy_sos_clean():
    # SOS, sri and rsm pass filters, no gate triggered
    result = get_action("SOS", pchg=1.5, atr_pct=2.0, bm_val=0, bm_sma10=0,
                         sri=2.0, rsm=75.0)
    assert result == "BUY"

def test_action_hold_gate_a():
    # Gate A: bm_val > bm_sma10 * 1.0
    result = get_action("SOS", pchg=1.5, atr_pct=2.0, bm_val=150, bm_sma10=100,
                         sri=2.0, rsm=75.0)
    assert result == "HOLD"

def test_action_hold_gate_b():
    result = get_action("SPRING", pchg=-3.0, atr_pct=2.0,
                         watch_flag="ARB_SPRING", sri=2.0, rsm=75.0)
    assert result == "HOLD"

def test_action_hold_gate_c_sos():
    # Gate C SOS: pchg >= max(atr*2.5, 6.0) → 6.0
    result = get_action("SOS", pchg=6.5, atr_pct=2.0, bm_val=0, bm_sma10=0,
                         sri=2.0, rsm=75.0)
    assert result == "HOLD"

def test_action_hold_low_sri():
    result = get_action("SOS", pchg=1.5, atr_pct=2.0, bm_val=0, bm_sma10=0,
                         sri=1.0, rsm=75.0)
    assert result == "HOLD"

def test_action_hold_low_rsm():
    result = get_action("SOS", pchg=1.5, atr_pct=2.0, bm_val=0, bm_sma10=0,
                         sri=2.0, rsm=65.0)
    assert result == "HOLD"


# ── get_watch_flag ────────────────────────────────────────────────────────────

def test_watch_flag_arb_spring():
    # SPRING with drop > 1.5 × ATR(2.0) = 3.0
    assert get_watch_flag("SPRING", pchg=-3.5, atr_pct=2.0) == "ARB_SPRING"

def test_watch_flag_none_normal_spring():
    assert get_watch_flag("SPRING", pchg=-2.0, atr_pct=2.0) is None

def test_watch_flag_none_other_phase():
    assert get_watch_flag("SOS", pchg=-4.0, atr_pct=2.0) is None


# ── detect_trade_detail_gate ──────────────────────────────────────────────────

def test_gate_a_active():
    result = detect_trade_detail_gate("SOS", pchg=1.5, bm_val=120, bm_sma10=100)
    assert result == "Gate A"

def test_gate_b_active():
    result = detect_trade_detail_gate("SPRING", pchg=-4.0, bm_val=0, bm_sma10=0, atr_pct=2.0)
    assert result == "Gate B"

def test_gate_c_active():
    # action=BUY, pchg >= max(atr*3.0, 6.0) = 6.0
    result = detect_trade_detail_gate("SOS", pchg=7.0, bm_val=0, bm_sma10=0,
                                       atr_pct=2.0, action="BUY")
    assert result == "Gate C"

def test_no_gate():
    result = detect_trade_detail_gate("SOS", pchg=1.5, bm_val=0, bm_sma10=0,
                                       atr_pct=2.0, action="BUY")
    assert result is None


# ── get_ma_structure ──────────────────────────────────────────────────────────

def test_ma_structure_strong_uptrend():
    assert get_ma_structure(110, ma5=105, ma13=100, ma34=90, ma200=80) == "Strong Uptrend"

def test_ma_structure_strong_downtrend():
    assert get_ma_structure(70, ma5=75, ma13=80, ma34=90, ma200=100) == "Strong Downtrend"

def test_ma_structure_cluster_uptrend():
    # gap < 3%: ma5=100, ma13=101, ma34=102 → gap = 2/100 = 2%
    assert get_ma_structure(110, ma5=100, ma13=101, ma34=102, ma200=90) == "Cluster on Macro Uptrend"

def test_ma_structure_cluster_downtrend():
    assert get_ma_structure(80, ma5=100, ma13=101, ma34=102, ma200=90) == "Cluster on Macro Downtrend"

def test_ma_structure_na_on_none():
    assert get_ma_structure(None, ma5=100, ma13=101, ma34=102) == "N/A"
    assert get_ma_structure(100, ma5=None, ma13=101, ma34=102) == "N/A"
