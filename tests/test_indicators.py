"""
tests/test_indicators.py — Unit tests for algo/indicators.py
"""
import pytest
from algo.indicators import (
    compute_ma, compute_rsi14, compute_cm_streak,
    compute_ma5_price_streak, compute_days_since_near_level,
)


# ── compute_ma ────────────────────────────────────────────────────────────────

def test_ma_basic():
    assert compute_ma([1, 2, 3, 4, 5], 3) == 4.0

def test_ma_full_window():
    assert compute_ma([10, 20, 30], 3) == 20.0

def test_ma_insufficient_data():
    assert compute_ma([1, 2], 3) is None

def test_ma_single_value():
    assert compute_ma([5], 1) == 5.0

def test_ma_uses_last_n():
    # period=2, should use last 2 values [4,5] not [1,2]
    assert compute_ma([1, 2, 3, 4, 5], 2) == 4.5


# ── compute_rsi14 ─────────────────────────────────────────────────────────────

def test_rsi_insufficient_data():
    assert compute_rsi14([1] * 14) is None

def test_rsi_all_gains_returns_100():
    closes = list(range(1, 17))  # 16 values, always going up
    assert compute_rsi14(closes) == 100.0

def test_rsi_all_losses_returns_0():
    closes = list(range(16, 0, -1))  # 16 values, always going down
    assert compute_rsi14(closes) == 0.0

def test_rsi_range():
    import random
    random.seed(42)
    closes = [100 + random.uniform(-2, 2) for _ in range(20)]
    rsi = compute_rsi14(closes)
    assert rsi is not None
    assert 0 <= rsi <= 100


# ── compute_cm_streak ─────────────────────────────────────────────────────────

def test_cm_streak_above():
    closes = [10, 11, 12, 13]
    ma5 = 9.0
    assert compute_cm_streak(closes, ma5) == 4  # all above

def test_cm_streak_below():
    closes = [10, 9, 8, 7]
    ma5 = 11.0
    assert compute_cm_streak(closes, ma5) == -4  # all below

def test_cm_streak_mixed():
    # last 3 above, then 1 below
    closes = [5, 10, 11, 12]
    ma5 = 9.0
    assert compute_cm_streak(closes, ma5) == 3

def test_cm_streak_none_ma():
    assert compute_cm_streak([1, 2, 3], None) is None

def test_cm_streak_empty():
    assert compute_cm_streak([], 10.0) is None


# ── compute_ma5_price_streak ──────────────────────────────────────────────────

def test_ma5_price_streak_all_above():
    closes   = [96, 98, 101, 103, 105]   # oldest-first, all above ma5
    ma5_vals = [100, 100, 100, 100, 100]
    assert compute_ma5_price_streak(closes, ma5_vals) == 3  # only last 3 above

def test_ma5_price_streak_all_below():
    closes   = [105, 103, 99, 97, 95]
    ma5_vals = [100, 100, 100, 100, 100]
    assert compute_ma5_price_streak(closes, ma5_vals) == -3

def test_ma5_price_streak_full_above():
    closes   = [101, 102, 103, 104, 105]
    ma5_vals = [100, 100, 100, 100, 100]
    assert compute_ma5_price_streak(closes, ma5_vals) == 5

def test_ma5_price_streak_empty():
    assert compute_ma5_price_streak([], []) == 0

def test_ma5_price_streak_none_ma5():
    assert compute_ma5_price_streak([105], [None]) == 0


# ── compute_days_since_near_level ─────────────────────────────────────────────

def test_days_since_near_level_yesterday():
    # oldest-first: today=101, yesterday=99, level=100, tol=2%
    closes = [120, 115, 102, 100, 98, 99, 101]
    assert compute_days_since_near_level(closes, 100, 2.0) == 1

def test_days_since_near_level_two_days_ago():
    closes = [120, 115, 99, 110, 112]   # closes[-3]=99 → 2 days ago
    assert compute_days_since_near_level(closes, 100, 2.0) == 2

def test_days_since_near_level_first_touch():
    closes = [125, 120, 118, 115, 101]
    assert compute_days_since_near_level(closes, 100, 2.0) is None

def test_days_since_near_level_empty():
    assert compute_days_since_near_level([], 100) is None
