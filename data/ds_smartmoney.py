"""
ds_smartmoney.py — DataSectors Institutional Flow (Tier 3)
PLACEHOLDER: Fetch institutional flow signal per ticker (on-demand, not batch).
Displayed as badge: ACCUMULATION / DISTRIBUTION / NEUTRAL.
Does NOT affect Zenith signal — conviction layer only.
"""
from config import DS_API_KEY, DS_BASE_URL, DS_ENABLED


def get_inst_flow(conn, ticker: str) -> dict | None:
    """
    Get institutional flow signal for ticker.
    Checks inst_flow_cache first (TTL: DS_CACHE_TTL = 1 day).
    Falls back to DataSectors API fetch if cache expired.
    Returns: {"signal": "ACCUMULATION"|"DISTRIBUTION"|"NEUTRAL"} or None.
    """
    raise NotImplementedError(
        "ds_smartmoney not yet implemented. Requires DATASECTORS_API_KEY."
    )


def _fetch_from_api(ticker: str) -> str | None:
    """Hit DataSectors /api/institutional-flow/{symbol}. Returns signal string."""
    raise NotImplementedError("ds_smartmoney._fetch_from_api — TODO")
