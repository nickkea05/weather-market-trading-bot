"""
Test script that streams market data to CSV files
Creates a new CSV file for each 15-minute market
Also fetches gabagool's trades when each market closes
"""

import os
import csv
import time
import json
import threading
import requests
from datetime import datetime, timezone, timedelta
from websocket import WebSocketApp

GAMMA_API = "https://gamma-api.polymarket.com"
DATA_API = "https://data-api.polymarket.com"
WSS_URL = "wss://ws-subscriptions-clob.polymarket.com"
CSV_FOLDER = "testing_data"

# Gabagool's wallet address (proxy wallet used for trading)
GABAGOOL_WALLET = "0x6031b6eed1c97e853c6e0f03ad3ce3529351f96d"


# ============================================================
# Filename Helper
# ============================================================

def get_readable_filename(market_slug: str, start_time: datetime, end_time: datetime, suffix: str) -> str:
    """
    Create a human-readable filename like:
    btc-15m_5-00pm_5-15pm_1765525500_market.csv
    Times are displayed in ET (Eastern Time)
    """
    # Extract timestamp from slug (last part)
    timestamp = market_slug.split('-')[-1]
    
    # Convert UTC to ET (UTC-5, or UTC-4 during DST)
    try:
        from zoneinfo import ZoneInfo
        et_tz = ZoneInfo("America/New_York")
    except ImportError:
        # Fallback for older Python
        et_tz = timezone(timedelta(hours=-5))
    
    start_et = start_time.astimezone(et_tz)
    end_et = end_time.astimezone(et_tz)
    
    # Format times as H-MMam/pm (e.g., 5-30pm)
    start_str = start_et.strftime("%I-%M%p").lstrip("0").lower()
    end_str = end_et.strftime("%I-%M%p").lstrip("0").lower()
    
    # Create readable name: btc-15m_H-MMam_H-MMpm_timestamp_suffix.csv
    return f"btc-15m_{start_str}_{end_str}_{timestamp}_{suffix}.csv"


# ============================================================
# Gabagool Trade Fetcher
# ============================================================

def fetch_gabagool_trades(market_slug: str, market_title: str, start_time: datetime, end_time: datetime) -> list:
    """
    Fetch gabagool's trades for a specific market within a time window.
    Uses pagination to get ALL trades (gabagool often makes 200-400+ trades per 15-min market).
    
    Args:
        market_slug: The market slug (e.g., btc-updown-15m-1765525500)
        market_title: The market title to filter by (e.g., "Bitcoin Up or Down - December 15...")
        start_time: Start of the time window
        end_time: End of the time window
    
    Returns:
        List of filtered trades
    """
    url = f"{DATA_API}/activity"
    
    print(f"[GABAGOOL] Fetching trades for {GABAGOOL_WALLET[:10]}...")
    
    try:
        # Use pagination to get all trades (API returns max 500 per request)
        all_trades = []
        seen_keys = set()  # Deduplicate
        offset = 0
        max_pages = 10  # Safety limit (5000 trades max)
        
        while offset < max_pages * 500:
            params = {
                "user": GABAGOOL_WALLET,
                "type": "TRADE",
                "limit": 500,
                "offset": offset
            }
            
            response = requests.get(url, params=params, timeout=30)
            if response.status_code != 200:
                print(f"[GABAGOOL] Error: HTTP {response.status_code}")
                break
            
            trades = response.json()
            if not trades:
                break
            
            new_count = 0
            for t in trades:
                # Dedupe key
                key = (t.get('timestamp'), t.get('price'), t.get('size'), t.get('outcome'))
                if key in seen_keys:
                    continue
                seen_keys.add(key)
                all_trades.append(t)
                new_count += 1
            
            print(f"[GABAGOOL] Offset {offset}: {len(trades)} returned, {new_count} new")
            
            if new_count == 0:
                # No new unique trades, we've hit the end
                break
            
            offset += 500
        
        print(f"[GABAGOOL] Total fetched: {len(all_trades)} unique trades")
        
        # Filter for this specific BTC market and time window
        filtered = []
        for t in all_trades:
            title = t.get('title', '')
            
            # Must be Bitcoin Up or Down 15-min market (not ETH, not hourly)
            # 15-min titles look like: "Bitcoin Up or Down - December 15, 5:45PM-6:00PM ET"
            # Hourly titles look like: "Bitcoin Up or Down - December 15, 5PM ET"
            if 'Bitcoin Up or Down' not in title:
                continue
            # 15-min markets have a time range with dash (e.g., "5:45PM-6:00PM")
            if 'AM-' not in title and 'PM-' not in title:
                continue
            
            # Check timestamp is within our window
            ts_raw = t.get('timestamp', '')
            if ts_raw:
                try:
                    # Handle both integer (Unix seconds) and string (ISO) timestamps
                    if isinstance(ts_raw, int):
                        # Unix timestamp in seconds
                        trade_time = datetime.fromtimestamp(ts_raw, tz=timezone.utc)
                    elif isinstance(ts_raw, str):
                        if ts_raw.isdigit():
                            # String but actually a number
                            trade_time = datetime.fromtimestamp(int(ts_raw), tz=timezone.utc)
                        elif ts_raw.endswith('Z'):
                            trade_time = datetime.fromisoformat(ts_raw.replace('Z', '+00:00'))
                        else:
                            trade_time = datetime.fromisoformat(ts_raw)
                            if trade_time.tzinfo is None:
                                trade_time = trade_time.replace(tzinfo=timezone.utc)
                    else:
                        continue
                    
                    # Check if within our market window (with some buffer)
                    buffer = timedelta(minutes=2)
                    if trade_time < (start_time - buffer) or trade_time > (end_time + buffer):
                        continue
                        
                except Exception as e:
                    print(f"[GABAGOOL] Error parsing timestamp: {e}")
                    continue
            
            filtered.append({
                'timestamp': trade_time.isoformat(),  # Store as ISO string for readability
                'title': title,
                'outcome': t.get('outcome', ''),
                'side': t.get('side', ''),
                'price': t.get('price', ''),
                'size': t.get('size', ''),
                'usdcSize': t.get('usdcSize', '')
            })
        
        # Sort by timestamp ascending (oldest first)
        filtered.sort(key=lambda x: x['timestamp'])
        
        print(f"[GABAGOOL] Found {len(filtered)} trades for this market")
        return filtered
        
    except Exception as e:
        print(f"[GABAGOOL] Error fetching trades: {e}")
        return []


def save_gabagool_trades(market_slug: str, start_time: datetime, end_time: datetime, trades: list):
    """Save gabagool's trades to a CSV file paired with market data"""
    # Use same readable filename format
    filename = get_readable_filename(market_slug, start_time, end_time, "gabagool")
    csv_path = os.path.join(CSV_FOLDER, filename)
    
    if not trades:
        print(f"[GABAGOOL] No trades to save for this market")
        # Still create empty file so pairing is clear
        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=[
                'timestamp', 'title', 'outcome', 'side', 'price', 'size', 'usdcSize'
            ])
            writer.writeheader()
        print(f"[GABAGOOL] Created empty file: {csv_path}")
        return
    
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=[
            'timestamp', 'title', 'outcome', 'side', 'price', 'size', 'usdcSize'
        ])
        writer.writeheader()
        writer.writerows(trades)
    
    print(f"[GABAGOOL] Saved {len(trades)} trades to {csv_path}")


class CSVDataStream:
    """Streams market data to CSV file instead of console"""
    
    def __init__(self, market_slug: str, market_title: str, up_token: str, down_token: str, 
                 start_time: datetime, end_time: datetime):
        self.market_slug = market_slug
        self.market_title = market_title
        self.up_token = up_token
        self.down_token = down_token
        self.start_time = start_time
        self.end_time = end_time
        
        # State tracking
        self.up_best_ask = None
        self.up_ask_liquidity = None
        self.down_best_ask = None
        self.down_ask_liquidity = None
        
        # CSV setup with readable filename
        filename = get_readable_filename(market_slug, start_time, end_time, "market")
        self.csv_path = os.path.join(CSV_FOLDER, filename)
        self._init_csv()
        
        print(f"[CSV] Writing market data to: {self.csv_path}")
    
    def _init_csv(self):
        """Create CSV file with headers"""
        os.makedirs(CSV_FOLDER, exist_ok=True)
        
        with open(self.csv_path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                'timestamp',
                'up_best_ask',
                'up_liquidity',
                'down_best_ask',
                'down_liquidity',
                'combined_cost',
                'is_arb'
            ])
    
    def process_message(self, raw_message: str):
        """Process WebSocket message and write to CSV"""
        if raw_message == "PONG":
            return
        
        try:
            data = json.loads(raw_message)
        except json.JSONDecodeError:
            return
        
        # Handle list messages
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    self._process_event(item)
        elif isinstance(data, dict):
            self._process_event(data)
    
    def _process_event(self, data: dict):
        """Process a single event"""
        event_type = data.get("event_type", "")
        
        if event_type == "book":
            self._handle_book(data)
        elif event_type == "price_change":
            self._handle_price_change(data)
    
    def _handle_book(self, data: dict):
        """Extract best ask and liquidity from order book"""
        asset_id = data.get("asset_id", "")
        asks = data.get("asks", [])
        
        if not asks:
            return
        
        best_ask = None
        best_ask_liquidity = 0.0
        
        for ask in asks:
            if not isinstance(ask, dict):
                continue
            try:
                price = float(ask.get("price", 999))
                size = float(ask.get("size", 0))
                
                if best_ask is None or price < best_ask:
                    best_ask = price
                    best_ask_liquidity = size
                elif price == best_ask:
                    best_ask_liquidity += size
            except (ValueError, TypeError):
                continue
        
        if best_ask is not None:
            self._update_state(asset_id, best_ask, best_ask_liquidity)
    
    def _handle_price_change(self, data: dict):
        """Extract best ask from price change events"""
        for change in data.get("price_changes", []):
            if not isinstance(change, dict):
                continue
            
            asset_id = change.get("asset_id", "")
            best_ask_str = change.get("best_ask")
            
            if best_ask_str:
                try:
                    best_ask = float(best_ask_str)
                    self._update_state(asset_id, best_ask, None)
                except (ValueError, TypeError):
                    pass
    
    def _update_state(self, asset_id: str, best_ask: float, liquidity: float | None):
        """Update state and write to CSV"""
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
            self._write_row()
    
    def _write_row(self):
        """Write current state to CSV"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        
        combined = None
        is_arb = False
        if self.up_best_ask and self.down_best_ask:
            combined = self.up_best_ask + self.down_best_ask
            is_arb = combined < 1.0
        
        with open(self.csv_path, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                timestamp,
                self.up_best_ask,
                self.up_ask_liquidity,
                self.down_best_ask,
                self.down_ask_liquidity,
                combined,
                is_arb
            ])
        
        # Also print to console for visibility
        up_str = f"${self.up_best_ask:.3f}" if self.up_best_ask else "---"
        down_str = f"${self.down_best_ask:.3f}" if self.down_best_ask else "---"
        combined_str = f"${combined:.3f}" if combined else "---"
        print(f"[CSV] {timestamp} | Up: {up_str} | Down: {down_str} | Combined: {combined_str}")
    
    def reset(self):
        """Called when market closes"""
        print(f"[CSV] Market closed. Data saved to: {self.csv_path}")


# ============================================================
# Market Discovery (copied from connection.py)
# ============================================================

def get_interval_timestamp(offset: int = 0) -> int:
    now = int(time.time())
    interval_start = (now // 900) * 900
    return interval_start + (offset * 900)


def parse_json_field(value) -> list:
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except:
            return []
    return []


def fetch_market(slug: str) -> dict | None:
    try:
        url = f"{GAMMA_API}/markets"
        response = requests.get(url, params={"slug": slug}, timeout=10)
        response.raise_for_status()
        markets = response.json()
        return markets[0] if markets else None
    except Exception as e:
        print(f"[ERROR] Fetching market: {e}")
        return None


def discover_market() -> dict | None:
    """Find current active market"""
    print("\n[DISCOVERY] Looking for active market...")
    
    for offset in [0, 1]:
        timestamp = get_interval_timestamp(offset)
        slug = f"btc-updown-15m-{timestamp}"
        
        market = fetch_market(slug)
        if not market:
            continue
        
        if market.get("closed", True) and not market.get("acceptingOrders", False):
            continue
        
        title = market.get("title") or market.get("question", "Unknown")
        end_date = market.get("endDate", "")
        clob_token_ids = parse_json_field(market.get("clobTokenIds", "[]"))
        
        if len(clob_token_ids) < 2:
            continue
        
        print(f"[DISCOVERY] Found: {title}")
        print(f"[DISCOVERY] Slug: {slug}")
        
        return {
            "slug": slug,
            "title": title,
            "end_date": end_date,
            "up_token": clob_token_ids[0],
            "down_token": clob_token_ids[1],
        }
    
    return None


# ============================================================
# WebSocket Connection
# ============================================================

class CSVBot:
    """Bot that streams to CSV"""
    
    def __init__(self):
        self.datastream: CSVDataStream = None
        self.ws: WebSocketApp = None
        self._running = False
        self._reconnecting = False
        # Gabagool trade accumulation (fetched periodically to prevent data loss)
        self._gabagool_trades = []
        self._gabagool_seen = set()
    
    def _on_ws_open(self, ws):
        print("[WS] Connected, subscribing...")
        subscribe_msg = {
            "assets_ids": [self.up_token, self.down_token],
            "type": "market"
        }
        ws.send(json.dumps(subscribe_msg))
        print("[WS] Subscribed. Streaming to CSV...")
        
        # Start ping thread
        def ping():
            while self._running:
                try:
                    ws.send("PING")
                    time.sleep(10)
                except:
                    break
        threading.Thread(target=ping, daemon=True).start()
        
        # Start expiry monitor
        def monitor():
            while self._running:
                now = int(time.time())
                if now >= self.end_timestamp:
                    print("\n[BOT] Market expired!")
                    self._on_market_close()
                    break
                time.sleep(1)
        threading.Thread(target=monitor, daemon=True).start()
        
        # Start periodic gabagool fetcher (every 3 minutes)
        # This prevents trades from aging out of the API before market close
        def periodic_gabagool_fetch():
            fetch_interval = 180  # 3 minutes
            last_fetch = time.time()
            
            while self._running and not self._reconnecting:
                now = time.time()
                
                # Fetch if 3 minutes have passed
                if now - last_fetch >= fetch_interval:
                    if self.datastream and not self._reconnecting:
                        print(f"\n[GABAGOOL] Periodic fetch (preventing data loss)...")
                        trades = fetch_gabagool_trades(
                            market_slug=self.datastream.market_slug,
                            market_title=self.datastream.market_title,
                            start_time=self.datastream.start_time,
                            end_time=self.datastream.end_time
                        )
                        
                        # Accumulate trades (dedupe by key)
                        for t in trades:
                            key = (t['timestamp'], t['price'], t['size'], t['outcome'])
                            if key not in self._gabagool_seen:
                                self._gabagool_seen.add(key)
                                self._gabagool_trades.append(t)
                        
                        print(f"[GABAGOOL] Accumulated: {len(self._gabagool_trades)} unique trades so far")
                        last_fetch = now
                
                # Check if market ended
                if int(now) >= self.end_timestamp:
                    break
                    
                time.sleep(10)
        
        threading.Thread(target=periodic_gabagool_fetch, daemon=True).start()
    
    def _on_ws_message(self, ws, message):
        if self.datastream:
            self.datastream.process_message(message)
    
    def _on_ws_error(self, ws, error):
        print(f"[WS] Error: {error}")
    
    def _on_ws_close(self, ws, code, msg):
        print(f"[WS] Closed: {code}")
    
    def _on_market_close(self):
        if self._reconnecting:
            return
        self._reconnecting = True
        
        print("\n" + "=" * 60)
        print("[BOT] MARKET CLOSED")
        print("=" * 60)
        
        if self.ws:
            self.ws.close()
        
        if self.datastream:
            self.datastream.reset()
            
            # Final gabagool fetch to catch any last trades
            print("\n[BOT] Final gabagool fetch...")
            final_trades = fetch_gabagool_trades(
                market_slug=self.datastream.market_slug,
                market_title=self.datastream.market_title,
                start_time=self.datastream.start_time,
                end_time=self.datastream.end_time
            )
            
            # Add any new trades from final fetch
            for t in final_trades:
                key = (t['timestamp'], t['price'], t['size'], t['outcome'])
                if key not in self._gabagool_seen:
                    self._gabagool_seen.add(key)
                    self._gabagool_trades.append(t)
            
            # Sort all accumulated trades by timestamp
            self._gabagool_trades.sort(key=lambda x: x['timestamp'])
            
            print(f"[GABAGOOL] Total accumulated: {len(self._gabagool_trades)} trades")
            
            # Save all accumulated trades
            save_gabagool_trades(
                market_slug=self.datastream.market_slug,
                start_time=self.datastream.start_time,
                end_time=self.datastream.end_time,
                trades=self._gabagool_trades
            )
            
            # Reset accumulation for next market
            self._gabagool_trades = []
            self._gabagool_seen = set()
        
        print("\n[BOT] Waiting 5 seconds for new market...")
        time.sleep(5)
        
        if self._running:
            self._setup()
        
        self._reconnecting = False
    
    def _setup(self, wait_for_fresh: bool = False) -> bool:
        market = discover_market()
        if not market:
            print("[BOT] No market found")
            return False
        
        self.up_token = market["up_token"]
        self.down_token = market["down_token"]
        
        # Parse end timestamp
        end_date_str = market["end_date"]
        try:
            if end_date_str.endswith('Z'):
                end_date = datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))
            else:
                end_date = datetime.fromisoformat(end_date_str)
            self.end_timestamp = int(end_date.timestamp())
        except:
            end_date = datetime.now(timezone.utc) + timedelta(minutes=15)
            self.end_timestamp = int(time.time()) + 900
        
        # Calculate start time (15 minutes before end)
        start_date = end_date - timedelta(minutes=15)
        
        # Check if we should wait for a fresh market (to avoid partial data)
        if wait_for_fresh:
            now = int(time.time())
            time_remaining = self.end_timestamp - now
            time_elapsed = 900 - time_remaining  # 900 seconds = 15 minutes
            
            # If more than 60 seconds have elapsed, wait for next market
            if time_elapsed > 60:
                print(f"[BOT] Market already {time_elapsed:.0f}s in progress. Waiting for next market...")
                print(f"[BOT] Time remaining in current market: {time_remaining:.0f}s")
                
                # Wait for current market to end + buffer
                wait_time = time_remaining + 5
                print(f"[BOT] Waiting {wait_time:.0f}s for fresh market...")
                time.sleep(wait_time)
                
                # Recursively setup with fresh market (but don't wait again)
                return self._setup(wait_for_fresh=False)
            else:
                print(f"[BOT] Market is fresh ({time_elapsed:.0f}s elapsed). Starting collection.")
        
        print(f"[BOT] Market window: {start_date.strftime('%H:%M:%S')} - {end_date.strftime('%H:%M:%S')} UTC")
        
        # Create CSV datastream with market info
        self.datastream = CSVDataStream(
            market_slug=market["slug"],
            market_title=market["title"],
            up_token=self.up_token,
            down_token=self.down_token,
            start_time=start_date,
            end_time=end_date
        )
        
        # Connect WebSocket
        ws_url = f"{WSS_URL}/ws/market"
        self.ws = WebSocketApp(
            ws_url,
            on_open=self._on_ws_open,
            on_message=self._on_ws_message,
            on_error=self._on_ws_error,
            on_close=self._on_ws_close
        )
        
        # Run in background
        ws_thread = threading.Thread(target=self.ws.run_forever, daemon=True)
        ws_thread.start()
        
        return True
    
    def run(self):
        print("=" * 60)
        print("  CSV DATA COLLECTOR + GABAGOOL TRACKER")
        print(f"  Tracking wallet: {GABAGOOL_WALLET[:10]}...")
        print("=" * 60)
        
        self._running = True
        
        # On initial startup, wait for fresh market to avoid partial data
        if not self._setup(wait_for_fresh=True):
            print("[BOT] Failed to setup. Exiting.")
            return
        
        print("\n[BOT] Running. Press Ctrl+C to stop.\n")
        
        try:
            while self._running:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n[BOT] Stopping...")
            self._running = False
            if self.ws:
                self.ws.close()
            print("[BOT] Done!")


if __name__ == "__main__":
    bot = CSVBot()
    bot.run()


