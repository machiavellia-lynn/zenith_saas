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


def compute_ma50(closes: list):
    """Simple Moving Average 50 hari. closes = oldest-first. Returns None if < 50 data points."""
    return compute_ma(closes, 50)


def compute_bollinger_bands(closes: list, period: int = 20, std_dev: float = 2.0):
    """Bollinger Bands (SMA ± std_dev × population σ). closes = oldest-first.
    Returns {"upper", "mid", "lower", "width"} or None if < period data points."""
    if len(closes) < period:
        return None
    window = closes[-period:]
    mid    = sum(window) / period
    variance = sum((x - mid) ** 2 for x in window) / period
    sigma  = variance ** 0.5
    band   = std_dev * sigma
    upper  = mid + band
    lower  = mid - band
    width  = (upper - lower) / mid * 100 if mid != 0 else None
    return {
        "upper": round(upper, 2),
        "mid":   round(mid,   2),
        "lower": round(lower, 2),
        "width": round(width, 4) if width is not None else None,
    }


def detect_sideways(closes: list, ma5, ma34, bb_width) -> bool:
    """True jika saham konsolidasi sideways. closes = oldest-first.
    Kondisi: BB menyempit (< 8%), gap MA5-MA34 < 3%, range 10 hari < 8%."""
    if ma5 is None or ma34 is None or bb_width is None or ma34 == 0:
        return False
    if bb_width >= 8.0:
        return False
    if abs(ma5 - ma34) / ma34 * 100 >= 3.0:
        return False
    window = closes[-10:] if len(closes) >= 10 else closes
    lo = min(window)
    if lo == 0:
        return False
    if (max(window) - lo) / lo * 100 >= 8.0:
        return False
    return True


def compute_close_position(close: float, high, low) -> float | None:
    """Posisi close dalam range hari ini: (close - low) / (high - low).
    Output 0.0–1.0. Returns None jika high == low atau input None."""
    if close is None or high is None or low is None:
        return None
    if high == low:
        return None
    return round((close - low) / (high - low), 4)


def compute_mf_ratio(mf_plus, mf_minus) -> float | None:
    """Rasio MF+ terhadap total: mf_plus / (mf_plus + |mf_minus|) × 100.
    Returns None jika salah satu None atau total == 0."""
    if mf_plus is None or mf_minus is None:
        return None
    total = mf_plus + abs(mf_minus)
    if total == 0:
        return None
    return round(mf_plus / total * 100, 2)


def compute_ma5_price_streak(closes: list, ma5_values: list) -> int:
    """Consecutive days close di atas/bawah MA5. Both lists oldest-first.
    +N = close > ma5 selama N hari berturut dari hari ini. -N = close ≤ ma5. 0 jika data kosong."""
    n = min(len(closes), len(ma5_values))
    if n == 0:
        return 0
    today_ma5 = ma5_values[-1]
    if today_ma5 is None:
        return 0
    today_above = closes[-1] > today_ma5
    streak = 0
    for i in range(n):
        idx = n - 1 - i
        m = ma5_values[idx]
        if m is None:
            break
        if (closes[idx] > m) == today_above:
            streak += 1
        else:
            break
    return streak if today_above else -streak


def compute_days_since_near_level(closes: list, level: float, tolerance_pct: float = 2.0):
    """Berapa hari sejak close terakhir mendekati `level`. closes = oldest-first.
    None = first touch terkonfirmasi. N = N hari lalu terakhir menyentuh (1 = kemarin)."""
    if not closes or level == 0:
        return None
    for i in range(1, len(closes)):
        c = closes[-(i + 1)]
        if abs(c - level) / level * 100 <= tolerance_pct:
            return i
    return None
