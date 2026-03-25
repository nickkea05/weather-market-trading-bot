"""
Refresh module.
Fetches orderbooks for all cities from Polymarket and updates the shared cache.
Called by: `r` command, autoupdate hourly trigger, and initial startup.
"""

from cities import ALL_CITIES
from polymarket import fetch_city_prices


def refresh_all(cache: dict) -> int:
    """
    Refresh orderbooks for every city that has a target date assigned.
    Updates cache in place. Returns count of cities successfully refreshed.

    cache structure: {
        city_slug: {
            "date": date,
            "buckets": [{label, token_id, yes_bid, yes_ask}, ...],
            "center": {label, price},
            "forecast": float or None,
            "forecast_source": "manual" or None,
        }
    }
    """
    refreshed = 0
    for slug, entry in cache.items():
        target_date = entry.get("date")
        if not target_date:
            continue

        if refresh_city(slug, cache):
            refreshed += 1

    return refreshed


def refresh_city(city_slug: str, cache: dict) -> bool:
    """Refresh a single city's orderbook data. Returns True on success."""
    entry = cache.get(city_slug)
    if not entry or not entry.get("date"):
        return False

    target_date = entry["date"]
    prices = fetch_city_prices(city_slug, target_date)
    if prices is None:
        return False

    entry["buckets"] = prices
    entry["center"] = _find_center(prices)
    return True


def _find_center(buckets: list) -> dict:
    """Find the bucket with the highest probability (market center).
    Prefers yes_price (Gamma mid-market) over yes_bid for accuracy."""
    best = {"label": "--", "price": 0.0}
    for b in buckets:
        price = b.get("yes_price") or b.get("yes_bid") or 0.0
        if price > best["price"]:
            best = {"label": b["label"], "price": price}
    return best
