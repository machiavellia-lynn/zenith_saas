"""
indicators.py — Shared Technical Indicator Functions
RULE: Pure functions ONLY. No DB, no HTTP. Input: list/float. Output: primitive.
      Shared across all algo modules — do NOT put algo-specific logic here.
"""


def compute_ma(closes: list, period: int):
    """Simple Moving Average. closes = chronological (oldest first).
    Returns None if insufficient data."""
    if len(closes) < period:
        return None
    return round(sum(closes[-period:]) / period, 2)


def compute_rsi14(closes: list):
    """Wilder RSI-14. closes = chronological (oldest first), needs ≥ 15 values."""
    if len(closes) < 15:
        return None
    relevant = closes[-15:]
    diffs    = [relevant[i] - relevant[i - 1] for i in range(1, 15)]
    gains    = [max(d, 0)      for d in diffs]
    losses   = [abs(min(d, 0)) for d in diffs]
    avg_gain = sum(gains)  / 14
    avg_loss = sum(losses) / 14
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100 - 100 / (1 + rs), 1)


def compute_cm_streak(closes: list, ma5):
    """Consecutive Momentum: days close above (+N) or below (-N) MA5.
    Returns None if insufficient data."""
    if ma5 is None or not closes:
        return None
    above  = closes[-1] > ma5
    streak = 0
    for c in reversed(closes):
        if (c > ma5) == above:
            streak += 1
        else:
            break
    return streak if above else -streak
