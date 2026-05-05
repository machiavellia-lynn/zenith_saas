"""
ds_fundamental.py — DataSectors Fundamental Warnings (Tier 2)
PLACEHOLDER: Fetch corporate events, dividends, splits per ticker.
Logic in analytics_daily.py: if CA/dividend within 30 days → set warning flag.
"""
from config import DS_API_KEY, DS_BASE_URL, DS_ENABLED


def fetch_corporate_events(conn, ticker: str):
    """
    Fetch corporate events for ticker from DataSectors API.
    Cache results in corporate_events table (TTL: weekly fetch).
    Returns list of event dicts or [].
    """
    raise NotImplementedError(
        "ds_fundamental not yet implemented. Requires DATASECTORS_API_KEY."
    )


def get_upcoming_events(conn, ticker: str, within_days: int = 30) -> list[dict]:
    """
    Return events from corporate_events table within N days.
    Called by analytics_daily.py to set warning flags.
    """
    raise NotImplementedError("ds_fundamental.get_upcoming_events — TODO")
