"""
Polymarket API layer.
- Construct event slugs from city + date
- Fetch event data from Gamma API (markets, token IDs, outcomes, prices)
- Prices come from the Gamma API directly (outcomePrices, bestBid, bestAsk)
  because the CLOB /book endpoint returns near-empty books for neg-risk
  multi-outcome markets (which all weather markets are).
- All read-only, no auth needed.
"""

import json
import re
import requests

GAMMA_API = "https://gamma-api.polymarket.com"
CLOB_API = "https://clob.polymarket.com"


def build_slug(city_slug: str, date) -> str:
    """
    Build Polymarket event slug.
    date is a datetime.date object.
    Example: build_slug("nyc", date(2026, 3, 25)) -> "highest-temperature-in-nyc-on-march-25-2026"
    """
    month = date.strftime("%B").lower()
    return f"highest-temperature-in-{city_slug}-on-{month}-{date.day}-{date.year}"


def fetch_event(slug: str):
    """Fetch event from Gamma API by slug. Returns event dict or None."""
    try:
        resp = requests.get(
            f"{GAMMA_API}/events",
            params={"slug": slug},
            timeout=10,
        )
        resp.raise_for_status()
        events = resp.json()
        if events and len(events) > 0:
            return events[0]
    except requests.exceptions.RequestException:
        pass
    return None


def _parse_json_field(value):
    """Parse JSON string field or return as-is if already a list."""
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return []
    return []


def _safe_float(value, default=None):
    """Convert to float safely."""
    if value is None:
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def _clean_label(raw_label: str) -> str:
    """
    Normalize Gamma groupItemTitle into a clean bucket label.
    '50-51°F' -> '50-51'
    '41°F or below' -> '<41'
    '60°F or higher' -> '60+'
    '14°C' -> '14'
    """
    s = raw_label.strip()
    s = s.replace("\u00b0F", "").replace("\u00b0C", "").replace("\u00b0", "")
    s = s.strip()

    m = re.match(r"^(.+?)\s+or\s+below$", s, re.IGNORECASE)
    if m:
        return f"<{m.group(1).strip()}"

    m = re.match(r"^(.+?)\s+or\s+higher$", s, re.IGNORECASE)
    if m:
        return f"{m.group(1).strip()}+"

    return s


def fetch_city_prices(city_slug: str, date):
    """
    Build slug -> fetch event from Gamma API -> extract prices from response.
    Returns list of {label, token_id, yes_bid, yes_ask} or None.
    
    Uses Gamma API outcomePrices/bestBid/bestAsk instead of CLOB /book,
    because CLOB returns near-empty orderbooks for neg-risk weather markets.
    Single API call per city.
    """
    slug = build_slug(city_slug, date)
    event = fetch_event(slug)
    if not event:
        return None

    markets = event.get("markets", [])
    if not markets:
        return None

    results = []
    for market in markets:
        clob_token_ids = _parse_json_field(market.get("clobTokenIds", "[]"))
        if not clob_token_ids:
            continue

        raw_label = market.get("groupItemTitle", "") or ""
        if not raw_label:
            outcomes = _parse_json_field(market.get("outcomes", "[]"))
            raw_label = outcomes[0] if outcomes else "?"

        label = _clean_label(raw_label)

        outcome_prices = _parse_json_field(market.get("outcomePrices", "[]"))
        yes_price = _safe_float(outcome_prices[0]) if outcome_prices else None
        best_bid = _safe_float(market.get("bestBid"))
        best_ask = _safe_float(market.get("bestAsk"))

        results.append({
            "label": label,
            "token_id": clob_token_ids[0],
            "yes_bid": best_bid if best_bid is not None else yes_price,
            "yes_ask": best_ask if best_ask is not None else yes_price,
            "yes_price": yes_price,
        })

    return results if results else None
