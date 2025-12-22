"""
Test: Can we find the BTC Up/Down 15-minute market using the timestamp pattern?
"""

import time
import requests

GAMMA_API = "https://gamma-api.polymarket.com"


def get_current_btc_market_slug():
    """Calculate the current 15-minute interval's market slug"""
    now = int(time.time())
    interval_start = (now // 900) * 900  # Round down to nearest 15 min
    return f"btc-updown-15m-{interval_start}"


def get_market_by_slug(slug: str):
    """Fetch a market from Gamma API by slug"""
    url = f"{GAMMA_API}/markets"
    params = {"slug": slug}
    
    response = requests.get(url, params=params, timeout=10)
    response.raise_for_status()
    
    markets = response.json()
    return markets[0] if markets else None


def main():
    # Calculate current market slug
    slug = get_current_btc_market_slug()
    print(f"Looking for market: {slug}")
    print(f"URL would be: https://polymarket.com/event/{slug}")
    print()
    
    # Try to fetch it
    print("Fetching from Gamma API...")
    market = get_market_by_slug(slug)
    
    if market:
        print("\n SUCCESS! Found market:")
        print(f"  Question: {market.get('question', 'N/A')}")
        print(f"  Condition ID: {market.get('conditionId', 'N/A')}")
        print(f"  End Date: {market.get('endDate', 'N/A')}")
        print(f"  Outcomes: {market.get('outcomes', 'N/A')}")
        print(f"  Token IDs: {market.get('clobTokenIds', 'N/A')}")
    else:
        print("\n FAILED - Market not found")
        print("Trying to fetch any recent btc-updown market...")
        
        # Fallback: search for any btc-updown market
        response = requests.get(f"{GAMMA_API}/markets", params={"_limit": 50, "closed": "false"})
        markets = response.json()
        btc_markets = [m for m in markets if 'btc-updown' in m.get('slug', '').lower()]
        
        if btc_markets:
            print(f"\nFound {len(btc_markets)} btc-updown markets:")
            for m in btc_markets[:5]:
                print(f"  - {m.get('slug')}")


if __name__ == "__main__":
    main()

