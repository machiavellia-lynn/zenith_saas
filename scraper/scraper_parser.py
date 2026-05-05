"""
scraper_parser.py — Zenith 2.0 Pure Message Parser
RULE: Pure functions ONLY. Zero DB access, zero side effects.
      Input: raw Telegram message string. Output: list of dict.
"""
import re


# ── Value Parsers ──────────────────────────────────────────────────────────────

def parse_value(s: str) -> float | None:
    if not s:
        return None
    s = s.strip()
    sign = 1
    if s.startswith("+"):
        s = s[1:]
    elif s.startswith("-"):
        sign = -1
        s = s[1:]
    s = s.replace(",", ".")
    try:
        su = s.upper()
        if su.endswith("T") and not su.endswith("JT"):
            return sign * float(s[:-1]) * 1_000_000   # Triliun → Juta
        elif su.endswith("M"):
            return sign * float(s[:-1]) * 1_000        # Miliar → Juta
        elif su.endswith("JT"):
            return sign * float(s[:-2])                 # Juta
        elif su.endswith("RB"):
            return sign * float(s[:-2]) / 1_000         # Ribu → Juta
        else:
            return sign * float(s)
    except ValueError:
        return None


def parse_freq(s: str) -> int | None:
    s = s.strip().lower()
    try:
        if s.endswith("rb"):
            return int(float(s[:-2]) * 1000)
        return int(s)
    except ValueError:
        return None


def parse_volx(s: str) -> float | None:
    s = s.strip().replace(",", "")
    try:
        return float(s)
    except ValueError:
        return None


# ── SM/BM Message Parser ───────────────────────────────────────────────────────

TX_EMOJI = r"[💦🌟💧🔥🥵⭐]️?"

ROW_PATTERN_A = re.compile(
    r"(\d+)" + TX_EMOJI + r"\s+"
    r"([A-Z0-9]+)\s+([\d.]+)\s*([+-]?[\d.]+)\s+"
    r"(\d+rb|\d+)\s+([^\s]+)\s+([^\s]+)\s+([+-][^\s]+)\s+"
    r"([\d,]+\.?\d*)x([^\s]*)"
)
ROW_PATTERN_B = re.compile(
    r"(\d+)" + TX_EMOJI + r"\s+"
    r"([A-Z0-9]+)\s+([\d.]+)\s*([+-]?[\d.]+)\s+"
    r"([^\s]+)\s+([^\s]+)\s+([+-][^\s]+)\s+"
    r"([\d,]+\.?\d*)x([^\s]*)"
)
ROW_PATTERN_C = re.compile(
    r"(\d+)x\s+([A-Z0-9]+)\s+([\d.]+)\s*([+-]?[\d.]+)\s+"
    r"([^\s]+)\s+([^\s]+)\s+([+-]?[^\s]+)\s+[💣]?"
    r"([\d,]+\.?\d*)x([^\s]*)"
)


def detect_format(lines: list[str]) -> str:
    for line in lines:
        if "Freq" in line or "freq" in line:
            return "A"
        if "Tx|Ticker" in line or "Tx|ticker" in line:
            return "C"
    return "B"


def _detect_channel_from_header(lines: list[str], fallback: str) -> str:
    for line in lines:
        if "MF+" in line:
            return "smart"
        if "MF-" in line:
            return "bad"
    return fallback


def parse_joker_message(text: str, channel: str) -> list[dict]:
    """Parse SM/BM message. Returns list of row dicts."""
    text = text.replace("`", "")
    lines = text.strip().splitlines()
    results = []

    date_str, time_str = None, None
    for line in lines:
        m = re.search(r"(\d{2}-\d{2}-\d{4}).*?(\d{2}:\d{2}:\d{2})", line)
        if m:
            date_str = m.group(1)
            time_str = m.group(2)
            break
    if not date_str:
        return []

    channel = _detect_channel_from_header(lines, channel)
    fmt = detect_format(lines)

    for line in lines:
        if fmt == "A":
            m = ROW_PATTERN_A.search(line)
            if not m:
                continue
            tx_count     = int(m.group(1))
            ticker       = m.group(2)
            price        = float(m.group(3))
            gain_pct     = float(m.group(4))
            freq         = parse_freq(m.group(5))
            value_raw    = m.group(6)
            avg_mf_raw   = m.group(7)
            mf_delta_raw = m.group(8)
            vol_x        = parse_volx(m.group(9))
            signal       = m.group(10).strip().replace("`", "")
        elif fmt == "B":
            m = ROW_PATTERN_B.search(line)
            if not m:
                continue
            tx_count     = int(m.group(1))
            ticker       = m.group(2)
            price        = float(m.group(3))
            gain_pct     = float(m.group(4))
            freq         = None
            value_raw    = m.group(5)
            avg_mf_raw   = m.group(6)
            mf_delta_raw = m.group(7)
            vol_x        = parse_volx(m.group(8))
            signal       = m.group(9).strip().replace("`", "")
        else:
            m = ROW_PATTERN_C.search(line)
            if not m:
                continue
            tx_count     = int(m.group(1))
            ticker       = m.group(2)
            price        = float(m.group(3))
            gain_pct     = float(m.group(4))
            freq         = None
            value_raw    = m.group(5)
            avg_mf_raw   = m.group(6)
            mf_delta_raw = m.group(7)
            vol_x        = parse_volx(m.group(8))
            signal       = m.group(9).strip().replace("`", "")

        results.append({
            "channel":          channel,
            "date":             date_str,
            "time":             time_str,
            "tx_count":         tx_count,
            "ticker":           ticker,
            "price":            price,
            "gain_pct":         gain_pct,
            "freq":             freq,
            "value_raw":        value_raw,
            "value_numeric":    parse_value(value_raw),
            "avg_mf_raw":       avg_mf_raw,
            "avg_mf_numeric":   parse_value(avg_mf_raw),
            "mf_delta_raw":     mf_delta_raw,
            "mf_delta_numeric": parse_value(mf_delta_raw.lstrip("+")),
            "vol_x":            vol_x,
            "signal":           signal,
        })

    return results


# ── MF+/MF- Message Parser ────────────────────────────────────────────────────

VAL_TOKEN = r"[\d.]+(?:[Jj][Tt]|[Rr][Bb]|[Mm]|[Tt])"
MF_TOKEN  = r"(?:[+-][\d.]+(?:[Jj][Tt]|[Rr][Bb]|[Mm]|[Tt])|0)"

ROW_PATTERN_MF = re.compile(
    r"(\d+)" + TX_EMOJI + r"\s+"
    r"([A-Z0-9]+)\s+([\d.]+)\s*([+-]?[\d.]+)\s+"
    r"(" + VAL_TOKEN + r")\s+(" + MF_TOKEN + r")\s+(" + MF_TOKEN + r")\s+(" + MF_TOKEN + r")\s*"
    r"([🟢🔴⚪️]?)",
    re.UNICODE,
)


def detect_mf_channel(text: str) -> str:
    if re.search(r"\|\s*MF\+\s*\|", text):
        return "mf_plus"
    elif re.search(r"\|\s*MF-\s*\|", text):
        return "mf_minus"
    return "mf_plus"


def parse_mf_message(text: str, fallback_channel: str) -> list[dict]:
    """Parse MF+/MF- message. Returns list of row dicts."""
    text = text.replace("```", "").replace("`", "")
    lines = text.strip().splitlines()
    results = []

    date_str, time_str = None, None
    for line in lines:
        m = re.search(r"(\d{2}-\d{2}-\d{4}).*?(\d{2}:\d{2}:\d{2})", line)
        if m:
            date_str = m.group(1)
            time_str = m.group(2)
            break
    if not date_str:
        return []

    channel = detect_mf_channel(text) or fallback_channel

    for line in lines:
        m = ROW_PATTERN_MF.search(line)
        if not m:
            continue
        results.append({
            "channel":          channel,
            "date":             date_str,
            "time":             time_str,
            "tx_count":         int(m.group(1)),
            "ticker":           m.group(2),
            "price":            float(m.group(3)),
            "gain_pct":         float(m.group(4)),
            "val_raw":          m.group(5),
            "val_numeric":      parse_value(m.group(5)),
            "mf_raw":           m.group(6),
            "mf_numeric":       parse_value(m.group(6)),
            "mft_raw":          m.group(7),
            "mft_numeric":      parse_value(m.group(7)),
            "cm_delta_raw":     m.group(8),
            "cm_delta_numeric": parse_value(m.group(8)),
            "signal":           m.group(9).strip() if m.group(9) else "",
        })

    return results
