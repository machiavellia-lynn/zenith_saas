"""
price_datasectors.py — DataSectors API Price Source (Tier 1)
PLACEHOLDER: Not active. Replace price_fetch.py after DataSectors stable for 2+ weeks.
API key required: DATASECTORS_API_KEY env var.
"""
from config import DS_API_KEY, DS_BASE_URL, DS_ENABLED


def fetch_close_datasectors(ticker: str, date_str: str):
    """
    Fetch close price for ticker on date_str from DataSectors API.
    Endpoint: /api/chart-saham/{symbol}/latest
    Returns (close, volume) or (None, None) on failure/not enabled.
    """
    raise NotImplementedError(
        "price_datasectors not yet implemented. "
        "Set DATASECTORS_API_KEY and implement after 2-week stability check."
    )


def enrich_daily_prices_ds(conn, date_str: str):
    """Replace enrich_daily_prices() in price_fetch.py with DataSectors source."""
    raise NotImplementedError("price_datasectors.enrich_daily_prices_ds — TODO")
