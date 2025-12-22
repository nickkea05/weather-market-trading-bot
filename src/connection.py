"""
Connection module - establishes connection with Polymarket
Handles: slug calculation, market discovery, WebSocket connection
"""

import time
import json
import threading
import requests
from datetime import datetime, timezone
from typing import Callable, Optional
from websocket import WebSocketApp

GAMMA_API = "https://gamma-api.polymarket.com"
WSS_URL = "wss://ws-subscriptions-clob.polymarket.com"


class MarketConnection:
    """Manages connection to Polymarket for a single market"""
    
    def __init__(self):
        self.market_data: Optional[dict] = None
        self.ws: Optional[WebSocketApp] = None
        self.ws_thread: Optional[threading.Thread] = None
        self._connected = False
        self._running = False
        
        # Callbacks for data events
        self._on_message_callback: Optional[Callable] = None
        self._on_market_close_callback: Optional[Callable] = None
    
    @staticmethod
    def get_interval_timestamp(offset: int = 0) -> int:
        """Calculate 15-minute interval start timestamp"""
        now = int(time.time())
        interval_start = (now // 900) * 900
        return interval_start + (offset * 900)
    
    @staticmethod
    def _parse_json_field(value) -> list:
        """Parse JSON string field or return as-is if already a list"""
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            try:
                return json.loads(value)
            except:
                return []
        return []
    
    def _fetch_market(self, slug: str) -> Optional[dict]:
        """Fetch market data from Gamma API"""
        try:
            url = f"{GAMMA_API}/markets"
            response = requests.get(url, params={"slug": slug}, timeout=10)
            response.raise_for_status()
            
            markets = response.json()
            return markets[0] if markets else None
        except Exception as e:
            print(f"[CONNECTION] Error fetching market: {e}")
            return None
    
    def discover_market(self) -> bool:
        """
        Find the current active BTC 15-minute market.
        Returns True if market found, False otherwise.
        """
        print("\n[CONNECTION] Discovering market...")
        
        for offset in [0, 1]:
            timestamp = self.get_interval_timestamp(offset)
            slug = f"btc-updown-15m-{timestamp}"
            
            label = "current" if offset == 0 else "next"
            print(f"[CONNECTION] Trying {label} interval: {slug}")
            
            market = self._fetch_market(slug)
            
            if not market:
                continue
            
            closed = market.get("closed", True)
            accepting = market.get("acceptingOrders", False)
            
            if closed and not accepting:
                print(f"[CONNECTION] Market closed, trying next...")
                continue
            
            # Parse market data
            title = market.get("title") or market.get("question", "Unknown")
            end_date = market.get("endDate", "")
            clob_token_ids = self._parse_json_field(market.get("clobTokenIds", "[]"))
            outcomes = self._parse_json_field(market.get("outcomes", "[]"))
            outcome_prices = self._parse_json_field(market.get("outcomePrices", "[]"))
            
            if len(clob_token_ids) < 2:
                print(f"[CONNECTION] Invalid token IDs, skipping...")
                continue
            
            # Calculate time remaining
            time_remaining = self._calculate_time_remaining(end_date)
            
            # Store market data
            self.market_data = {
                "slug": slug,
                "title": title,
                "end_date": end_date,
                "end_timestamp": self._parse_end_timestamp(end_date),
                "time_remaining": time_remaining,
                "up_token": clob_token_ids[0],
                "down_token": clob_token_ids[1],
                "outcomes": outcomes,
                "initial_prices": outcome_prices,
                "accepting_orders": accepting,
            }
            
            print(f"\n[CONNECTION] === MARKET FOUND ===")
            print(f"[CONNECTION] Title: {title}")
            print(f"[CONNECTION] End: {end_date}")
            print(f"[CONNECTION] Time Remaining: {time_remaining}s")
            print(f"[CONNECTION] Up Token: {clob_token_ids[0][:30]}...")
            print(f"[CONNECTION] Down Token: {clob_token_ids[1][:30]}...")
            
            return True
        
        print("[CONNECTION] No active market found")
        return False
    
    def _calculate_time_remaining(self, end_date_str: str) -> int:
        """Calculate seconds until market closes"""
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
    
    def _parse_end_timestamp(self, end_date_str: str) -> int:
        """Parse end date to Unix timestamp"""
        try:
            if end_date_str.endswith('Z'):
                end_date = datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))
            else:
                end_date = datetime.fromisoformat(end_date_str)
            return int(end_date.timestamp())
        except:
            return 0
    
    def set_message_callback(self, callback: Callable):
        """Set callback for WebSocket messages"""
        self._on_message_callback = callback
    
    def set_market_close_callback(self, callback: Callable):
        """Set callback for when market closes"""
        self._on_market_close_callback = callback
    
    def connect_websocket(self) -> bool:
        """
        Establish WebSocket connection to market channel.
        Returns True if connection established.
        """
        if not self.market_data:
            print("[CONNECTION] No market data, call discover_market() first")
            return False
        
        print(f"\n[CONNECTION] Connecting to WebSocket...")
        
        self._running = True
        
        ws_url = f"{WSS_URL}/ws/market"
        
        self.ws = WebSocketApp(
            ws_url,
            on_open=self._on_ws_open,
            on_message=self._on_ws_message,
            on_error=self._on_ws_error,
            on_close=self._on_ws_close
        )
        
        # Run WebSocket in background thread
        self.ws_thread = threading.Thread(target=self.ws.run_forever, daemon=True)
        self.ws_thread.start()
        
        # Wait for connection
        timeout = 10
        start = time.time()
        while not self._connected and (time.time() - start) < timeout:
            time.sleep(0.1)
        
        if self._connected:
            print("[CONNECTION] WebSocket connected successfully")
            return True
        else:
            print("[CONNECTION] WebSocket connection timeout")
            return False
    
    def _on_ws_open(self, ws):
        """Handle WebSocket open"""
        self._connected = True
        
        # Subscribe to market channel with token IDs
        subscribe_msg = {
            "assets_ids": [self.market_data["up_token"], self.market_data["down_token"]],
            "type": "market"
        }
        ws.send(json.dumps(subscribe_msg))
        print("[CONNECTION] Subscribed to market channel")
        
        # Start ping thread
        ping_thread = threading.Thread(target=self._ping_loop, args=(ws,), daemon=True)
        ping_thread.start()
        
        # Start market expiry monitor
        expiry_thread = threading.Thread(target=self._monitor_expiry, daemon=True)
        expiry_thread.start()
    
    def _ping_loop(self, ws):
        """Send periodic pings to keep connection alive"""
        while self._running and self._connected:
            try:
                ws.send("PING")
                time.sleep(10)
            except:
                break
    
    def _monitor_expiry(self):
        """Monitor for market expiry and trigger callback"""
        if not self.market_data:
            return
        
        end_timestamp = self.market_data.get("end_timestamp", 0)
        
        while self._running and self._connected:
            now = int(time.time())
            
            if now >= end_timestamp:
                print("\n[CONNECTION] Market has expired!")
                if self._on_market_close_callback:
                    self._on_market_close_callback()
                break
            
            # Also check periodically if market is still accepting orders
            time.sleep(1)
    
    def _on_ws_message(self, ws, message):
        """Handle WebSocket message - pass to callback"""
        if message == "PONG":
            return
        
        if self._on_message_callback:
            self._on_message_callback(message)
    
    def _on_ws_error(self, ws, error):
        """Handle WebSocket error"""
        print(f"[CONNECTION] WebSocket error: {error}")
    
    def _on_ws_close(self, ws, close_status_code, close_msg):
        """Handle WebSocket close"""
        self._connected = False
        print(f"[CONNECTION] WebSocket closed: {close_status_code}")
    
    def disconnect(self):
        """Disconnect WebSocket"""
        self._running = False
        self._connected = False
        if self.ws:
            self.ws.close()
        print("[CONNECTION] Disconnected")
    
    def is_connected(self) -> bool:
        """Check if WebSocket is connected"""
        return self._connected
    
    def get_time_remaining(self) -> int:
        """Get current time remaining until market closes"""
        if not self.market_data:
            return 0
        return self._calculate_time_remaining(self.market_data.get("end_date", ""))

