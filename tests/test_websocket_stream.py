"""
Stream lowest ask prices from Polymarket BTC 15-minute market
Only tracks what matters: best ask price + liquidity at that price
"""

import time
import json
import threading
import requests
from datetime import datetime, timezone
from websocket import WebSocketApp

GAMMA_API = "https://gamma-api.polymarket.com"
WSS_URL = "wss://ws-subscriptions-clob.polymarket.com"


# ============================================================
# Market Discovery
# ============================================================

def get_interval_timestamp(offset: int = 0) -> int:
    now = int(time.time())
    interval_start = (now // 900) * 900
    return interval_start + (offset * 900)


def fetch_market(slug: str) -> dict | None:
    url = f"{GAMMA_API}/markets"
    response = requests.get(url, params={"slug": slug}, timeout=10)
    response.raise_for_status()
    
    markets = response.json()
    if markets:
        return markets[0]
    return None


def parse_json_field(value):
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except:
            return []
    return []


def calculate_time_remaining(end_date_str: str) -> int:
    try:
        if end_date_str.endswith('Z'):
            end_date = datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))
        else:
            end_date = datetime.fromisoformat(end_date_str)
        
        now = datetime.now(timezone.utc)
        remaining = (end_date - now).total_seconds()
        return max(0, int(remaining))
    except:
        return 0


def discover_market():
    """Find the current live BTC 15-min market"""
    print("=" * 60)
    print("MARKET DISCOVERY")
    print("=" * 60)
    
    for offset in [0, 1]:
        timestamp = get_interval_timestamp(offset)
        slug = f"btc-updown-15m-{timestamp}"
        
        market = fetch_market(slug)
        
        if not market:
            continue
        
        if market.get("closed", True) and not market.get("acceptingOrders", False):
            continue
        
        # Parse fields
        title = market.get("title") or market.get("question", "N/A")
        end_date = market.get("endDate", "")
        outcome_prices = parse_json_field(market.get("outcomePrices", "[]"))
        clob_token_ids = parse_json_field(market.get("clobTokenIds", "[]"))
        
        time_remaining = calculate_time_remaining(end_date)
        
        up_price = outcome_prices[0] if len(outcome_prices) > 0 else "?"
        down_price = outcome_prices[1] if len(outcome_prices) > 1 else "?"
        
        print(f"\n=== MARKET FOUND ===")
        print(f"Title: {title}")
        print(f"End Date: {end_date}")
        print(f"Time Remaining: {time_remaining} seconds")
        print(f"Initial Prices: Up={up_price}, Down={down_price}")
        print(f"Token IDs: {[t[:20] + '...' for t in clob_token_ids]}")
        print("=" * 60)
        
        if len(clob_token_ids) >= 2:
            return {
                "slug": slug,
                "title": title,
                "up_token": clob_token_ids[0],
                "down_token": clob_token_ids[1],
                "end_date": end_date,
            }
    
    return None


# ============================================================
# WebSocket Streaming - Simplified
# ============================================================

class BestAskTracker:
    """Only tracks lowest ask price and liquidity for each outcome"""
    
    def __init__(self, slug: str, up_token: str, down_token: str):
        self.slug = slug
        self.up_token = up_token
        self.down_token = down_token
        self.ws = None
        
        # Track best ask and liquidity
        self.up_best_ask = None
        self.up_ask_liquidity = None
        self.down_best_ask = None
        self.down_ask_liquidity = None
        
        print(f"\nTracking best asks for: {slug}")
    
    def on_open(self, ws):
        print(f"[Connected] Subscribing to market channel...")
        
        subscribe_msg = {
            "assets_ids": [self.up_token, self.down_token],
            "type": "market"
        }
        ws.send(json.dumps(subscribe_msg))
        print(f"[Subscribed] Streaming best asks only...\n")
        print("-" * 60)
        
        # Start ping thread
        ping_thread = threading.Thread(target=self.ping_loop, args=(ws,), daemon=True)
        ping_thread.start()
    
    def ping_loop(self, ws):
        while True:
            try:
                ws.send("PING")
                time.sleep(10)
            except:
                break
    
    def on_message(self, ws, message):
        if message == "PONG":
            return
        
        try:
            data = json.loads(message)
        except:
            return
        
        event_type = data.get("event_type", "")
        
        if event_type == "book":
            self.handle_book(data)
        elif event_type == "price_change":
            self.handle_price_change(data)
    
    def handle_book(self, data):
        """Extract best ask and liquidity from full order book"""
        asset_id = data.get("asset_id", "")
        asks = data.get("asks", [])
        
        if not asks:
            return
        
        # Find best (lowest) ask price and its liquidity
        best_ask = None
        best_ask_liquidity = 0
        
        for ask in asks:
            price = float(ask.get("price", 999))
            size = float(ask.get("size", 0))
            
            if best_ask is None or price < best_ask:
                best_ask = price
                best_ask_liquidity = size
            elif price == best_ask:
                best_ask_liquidity += size
        
        self.update_best_ask(asset_id, best_ask, best_ask_liquidity, source="book")
    
    def handle_price_change(self, data):
        """Extract best ask from price change events"""
        for change in data.get("price_changes", []):
            if not isinstance(change, dict):
                continue
            
            asset_id = change.get("asset_id", "")
            best_ask_str = change.get("best_ask")
            
            if best_ask_str:
                try:
                    best_ask = float(best_ask_str)
                    # Price change doesn't give liquidity, keep existing
                    self.update_best_ask(asset_id, best_ask, None, source="price_change")
                except:
                    pass
    
    def update_best_ask(self, asset_id: str, best_ask: float, liquidity: float | None, source: str):
        """Update best ask if changed and log"""
        changed = False
        
        if asset_id == self.up_token:
            if best_ask != self.up_best_ask:
                self.up_best_ask = best_ask
                changed = True
            if liquidity is not None and liquidity != self.up_ask_liquidity:
                self.up_ask_liquidity = liquidity
                changed = True
                
        elif asset_id == self.down_token:
            if best_ask != self.down_best_ask:
                self.down_best_ask = best_ask
                changed = True
            if liquidity is not None and liquidity != self.down_ask_liquidity:
                self.down_ask_liquidity = liquidity
                changed = True
        
        if changed:
            self.print_state()
    
    def print_state(self):
        """Print current best asks and combined cost"""
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        
        up_str = f"${self.up_best_ask:.3f}" if self.up_best_ask else "---"
        down_str = f"${self.down_best_ask:.3f}" if self.down_best_ask else "---"
        
        up_liq = f"{self.up_ask_liquidity:.1f}" if self.up_ask_liquidity else "?"
        down_liq = f"{self.down_ask_liquidity:.1f}" if self.down_ask_liquidity else "?"
        
        # Calculate combined cost (what matters for arb)
        combined = ""
        if self.up_best_ask and self.down_best_ask:
            total = self.up_best_ask + self.down_best_ask
            combined = f" | Combined: ${total:.3f}"
            if total < 1.0:
                combined += " ✓ ARB OPPORTUNITY"
        
        print(f"[{timestamp}] Up: {up_str} ({up_liq}) | Down: {down_str} ({down_liq}){combined}")
    
    def on_error(self, ws, error):
        print(f"\n[ERROR] {error}")
    
    def on_close(self, ws, close_status_code, close_msg):
        print(f"\n[CLOSED] {close_status_code} - {close_msg}")
    
    def run(self):
        ws_url = f"{WSS_URL}/ws/market"
        
        self.ws = WebSocketApp(
            ws_url,
            on_open=self.on_open,
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close
        )
        
        self.ws.run_forever()


# ============================================================
# Main
# ============================================================

def main():
    market = discover_market()
    
    if not market:
        print("No live market found")
        return
    
    tracker = BestAskTracker(
        slug=market["slug"],
        up_token=market["up_token"],
        down_token=market["down_token"]
    )
    
    try:
        tracker.run()
    except KeyboardInterrupt:
        print("\n[Stopped]")


if __name__ == "__main__":
    main()
