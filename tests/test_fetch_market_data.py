"""
Discover and fetch the current live BTC 15-minute market on Polymarket
"""

import time
import requests
from datetime import datetime, timezone

GAMMA_API = "https://gamma-api.polymarket.com"


def get_interval_timestamp(offset: int = 0) -> int:
    """
    Get the start timestamp for a 15-minute interval.
    offset=0 for current interval, offset=1 for next interval, etc.
    """
    now = int(time.time())
    interval_start = (now // 900) * 900  # Round down to nearest 15 min
    return interval_start + (offset * 900)


def fetch_market(slug: str) -> dict | None:
    """Fetch market data from Gamma API (try markets first, then events)"""
    # Try markets endpoint first (has more fields)
    url = f"{GAMMA_API}/markets"
    response = requests.get(url, params={"slug": slug}, timeout=10)
    response.raise_for_status()
    
    markets = response.json()
    if markets:
        return markets[0]
    
    # Fallback to events endpoint
    url = f"{GAMMA_API}/events"
    response = requests.get(url, params={"slug": slug}, timeout=10)
    response.raise_for_status()
    
    events = response.json()
    return events[0] if events else None


def calculate_time_remaining(end_date_str: str) -> int:
    """Calculate seconds remaining until market closes"""
    if end_date_str.endswith('Z'):
        end_date = datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))
    else:
        end_date = datetime.fromisoformat(end_date_str)
    
    now = datetime.now(timezone.utc)
    remaining = (end_date - now).total_seconds()
    return max(0, int(remaining))


def parse_json_field(value: str | list) -> list:
    """Parse a JSON string field or return as-is if already a list"""
    if isinstance(value, list):
        return value
    try:
        import json
        return json.loads(value)
    except:
        return []


def main():
    # Try current interval, then next interval if needed
    for offset in [0, 1]:
        timestamp = get_interval_timestamp(offset)
        slug = f"btc-updown-15m-{timestamp}"
        
        label = "current" if offset == 0 else "next"
        print(f"Trying {label} interval: {slug}")
        
        market = fetch_market(slug)
        
        if not market:
            print(f"  -> Not found\n")
            continue
        
        # Check if market is accepting orders
        accepting = market.get("acceptingOrders", False)
        closed = market.get("closed", True)
        
        if closed and not accepting:
            print(f"  -> Found but closed\n")
            continue
        
        # Found a live market!
        print(f"  -> Found live market!\n")
        
        # Parse fields
        title = market.get("title") or market.get("question", "N/A")
        end_date = market.get("endDate", "")
        outcome_prices = parse_json_field(market.get("outcomePrices", "[]"))
        clob_token_ids = parse_json_field(market.get("clobTokenIds", "[]"))
        
        # Calculate time remaining
        time_remaining = calculate_time_remaining(end_date) if end_date else 0
        
        # Format prices
        up_price = outcome_prices[0] if len(outcome_prices) > 0 else "?"
        down_price = outcome_prices[1] if len(outcome_prices) > 1 else "?"
        
        # Print output
        print("=" * 50)
        print("=== POLYMARKET LINK ===")
        print(f"https://polymarket.com/event/{slug}")
        print()
        print("=== MARKET DATA ===")
        print(f"Title: {title}")
        print(f"End Date: {end_date}")
        print(f"Accepting Orders: {accepting}")
        print(f"Prices: Up={up_price}, Down={down_price}")
        print(f"Time Remaining: {time_remaining} seconds")
        print(f"Token IDs: {clob_token_ids}")
        print("=" * 50)
        return
    
    print("No live market found for current or next interval")


if __name__ == "__main__":
    main()
