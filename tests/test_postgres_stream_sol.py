"""
PostgreSQL version of test_csv_stream.py - SOLANA
Streams market data to PostgreSQL database instead of CSV files
Auto-creates tables on first run
"""

import os
import time
import json
import threading
import requests
import psycopg2
import signal
import sys
from psycopg2.extras import execute_values
from datetime import datetime, timezone, timedelta
from websocket import WebSocketApp
from dotenv import load_dotenv

load_dotenv()

GAMMA_API = "https://gamma-api.polymarket.com"
DATA_API = "https://data-api.polymarket.com"
WSS_URL = "wss://ws-subscriptions-clob.polymarket.com"

# Traders to track
GABAGOOL_WALLET = "0x6031b6eed1c97e853c6e0f03ad3ce3529351f96d"
TRADER_2_WALLET = "0x63ce342161250d705dc0b16df89036c8e5f9ba9a"
TRACKED_WALLETS = [GABAGOOL_WALLET, TRADER_2_WALLET]


# ============================================================
# Database Connection
# ============================================================

def get_db_connection():
    """Get PostgreSQL connection from Railway SOL_DATABASE_URL"""
    database_url = os.getenv("SOL_DATABASE_URL")
    if not database_url:
        error_msg = """
ERROR: SOL_DATABASE_URL environment variable not set

To fix this in Railway:
1. Go to your Solana PostgreSQL database service
2. Click on the database service
3. Go to the "Connect" or "Variables" tab
4. Find the "Connect" button or "Generate Connection URL"
5. Copy the connection string
6. Go to your data collection service (the one running this script)
7. Go to "Variables" tab
8. Add a new variable: SOL_DATABASE_URL = (paste the connection string)

Alternatively, in Railway:
- Click on your database service
- Look for "Connect" or "Link" option
- Link it to your data collection service
- Railway will automatically add DATABASE_URL (but you need to rename it to SOL_DATABASE_URL)
"""
        raise ValueError(error_msg)
    return psycopg2.connect(database_url)


def init_tables():
    """Create tables if they don't exist"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Market data table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS market_data (
            id SERIAL PRIMARY KEY,
            market_slug VARCHAR(255) NOT NULL,
            market_title TEXT,
            timestamp TIMESTAMP NOT NULL,
            up_best_ask DECIMAL(10, 6),
            up_liquidity DECIMAL(10, 2),
            down_best_ask DECIMAL(10, 6),
            down_liquidity DECIMAL(10, 2),
            combined_cost DECIMAL(10, 6),
            is_arb BOOLEAN,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Trader trades table (tracks multiple traders)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS trader_trades (
            id SERIAL PRIMARY KEY,
            wallet_address VARCHAR(255) NOT NULL,
            market_slug VARCHAR(255) NOT NULL,
            timestamp TIMESTAMP NOT NULL,
            title TEXT,
            outcome VARCHAR(10),
            side VARCHAR(10),
            price DECIMAL(10, 6),
            size DECIMAL(20, 10),
            usdc_size DECIMAL(20, 10),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Create indexes for faster queries
    cur.execute("CREATE INDEX IF NOT EXISTS idx_market_data_slug ON market_data(market_slug)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_market_data_timestamp ON market_data(timestamp)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_trader_trades_slug ON trader_trades(market_slug)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_trader_trades_wallet ON trader_trades(wallet_address)")
    
    # Migrate old gabagool_trades table if it exists (backward compatibility)
    cur.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name = 'gabagool_trades'
        )
    """)
    if cur.fetchone()[0]:
        # Migrate data from old table
        cur.execute("""
            INSERT INTO trader_trades (wallet_address, market_slug, timestamp, title, outcome, side, price, size, usdc_size)
            SELECT %s, market_slug, timestamp, title, outcome, side, price, size, usdc_size
            FROM gabagool_trades
            ON CONFLICT DO NOTHING
        """, (GABAGOOL_WALLET,))
        conn.commit()
        print("[DB] Migrated old gabagool_trades data to trader_trades")
    
    conn.commit()
    cur.close()
    conn.close()
    print("[DB] Tables initialized")


# ============================================================
# Gabagool Trade Fetcher (same as CSV version)
# ============================================================

def fetch_trader_trades(wallet_address: str, market_slug: str, market_title: str, start_time: datetime, end_time: datetime) -> list:
    """Fetch gabagool's trades for a specific market within a time window"""
    url = f"{DATA_API}/activity"
    
    print(f"[TRADER] Fetching trades for {wallet_address[:10]}...")
    
    try:
        all_trades = []
        seen_keys = set()
        offset = 0
        max_pages = 10
        
        while offset < max_pages * 500:
            params = {
                "user": wallet_address,
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
                key = (t.get('timestamp'), t.get('price'), t.get('size'), t.get('outcome'))
                if key in seen_keys:
                    continue
                seen_keys.add(key)
                all_trades.append(t)
                new_count += 1
            
            print(f"[TRADER] Offset {offset}: {len(trades)} returned, {new_count} new")
            
            if new_count == 0:
                break
            
            offset += 500
        
        print(f"[TRADER] Total fetched: {len(all_trades)} unique trades")
        
        # Filter for this specific SOL market and time window
        filtered = []
        for t in all_trades:
            title = t.get('title', '')
            
            if 'Solana Up or Down' not in title:
                continue
            if 'AM-' not in title and 'PM-' not in title:
                continue
            
            ts_raw = t.get('timestamp', '')
            if ts_raw:
                try:
                    if isinstance(ts_raw, int):
                        trade_time = datetime.fromtimestamp(ts_raw, tz=timezone.utc)
                    elif isinstance(ts_raw, str):
                        if ts_raw.isdigit():
                            trade_time = datetime.fromtimestamp(int(ts_raw), tz=timezone.utc)
                        elif ts_raw.endswith('Z'):
                            trade_time = datetime.fromisoformat(ts_raw.replace('Z', '+00:00'))
                        else:
                            trade_time = datetime.fromisoformat(ts_raw)
                            if trade_time.tzinfo is None:
                                trade_time = trade_time.replace(tzinfo=timezone.utc)
                    else:
                        continue
                    
                    buffer = timedelta(minutes=2)
                    if trade_time < (start_time - buffer) or trade_time > (end_time + buffer):
                        continue
                        
                except Exception as e:
                    print(f"[GABAGOOL] Error parsing timestamp: {e}")
                    continue
            
            filtered.append({
                'timestamp': trade_time,
                'title': title,
                'outcome': t.get('outcome', ''),
                'side': t.get('side', ''),
                'price': t.get('price', ''),
                'size': t.get('size', ''),
                'usdcSize': t.get('usdcSize', '')
            })
        
        filtered.sort(key=lambda x: x['timestamp'])
        
        print(f"[TRADER] Found {len(filtered)} trades for this market")
        return filtered
        
    except Exception as e:
        print(f"[TRADER] Error fetching trades for {wallet_address[:10]}: {e}")
        return []


def save_trader_trades_to_db(wallet_address: str, market_slug: str, trades: list):
    """Save trader's trades to PostgreSQL"""
    if not trades:
        print(f"[TRADER] No trades to save for {wallet_address[:10]} in this market")
        return
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Prepare data for bulk insert
        values = []
        for t in trades:
            values.append((
                wallet_address,
                market_slug,
                t['timestamp'],
                t.get('title', ''),
                t.get('outcome', ''),
                t.get('side', ''),
                t.get('price'),
                t.get('size'),
                t.get('usdcSize')
            ))
        
        execute_values(
            cur,
            """INSERT INTO trader_trades 
               (wallet_address, market_slug, timestamp, title, outcome, side, price, size, usdc_size)
               VALUES %s""",
            values
        )
        
        conn.commit()
        print(f"[TRADER] Saved {len(trades)} trades for {wallet_address[:10]} to database")
    except Exception as e:
        conn.rollback()
        print(f"[TRADER] Error saving to database: {e}")
    finally:
        cur.close()
        conn.close()


# ============================================================
# PostgreSQL Data Stream
# ============================================================

class PostgresDataStream:
    """Streams market data to PostgreSQL instead of CSV"""
    
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
        
        # Batch insert for performance (insert every N rows or every few seconds)
        self.pending_rows = []
        self.last_insert = time.time()
        self.batch_size = 50  # Insert every 50 rows
        self.batch_interval = 2  # Or every 2 seconds (reduced to minimize data loss on restart)
        
        print(f"[DB] Writing market data for: {market_slug}")
    
    def process_message(self, raw_message: str):
        """Process WebSocket message and write to database"""
        if raw_message == "PONG":
            return
        
        try:
            data = json.loads(raw_message)
        except json.JSONDecodeError:
            return
        
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
        """Update state and queue for database insert"""
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
            self._queue_row()
    
    def _queue_row(self):
        """Queue row for batch insert"""
        timestamp = datetime.now(timezone.utc)
        
        combined = None
        is_arb = False
        if self.up_best_ask and self.down_best_ask:
            combined = self.up_best_ask + self.down_best_ask
            is_arb = combined < 1.0
        
        self.pending_rows.append((
            self.market_slug,
            self.market_title,
            timestamp,
            self.up_best_ask,
            self.up_ask_liquidity,
            self.down_best_ask,
            self.down_ask_liquidity,
            combined,
            is_arb
        ))
        
        # Insert if batch size reached or time interval passed
        now = time.time()
        if len(self.pending_rows) >= self.batch_size or (now - self.last_insert) >= self.batch_interval:
            self._flush_rows()
        
        # Also print to console for visibility
        up_str = f"${self.up_best_ask:.3f}" if self.up_best_ask else "---"
        down_str = f"${self.down_best_ask:.3f}" if self.down_best_ask else "---"
        combined_str = f"${combined:.3f}" if combined else "---"
        print(f"[DB] {timestamp.strftime('%H:%M:%S')} | Up: {up_str} | Down: {down_str} | Combined: {combined_str}")
    
    def _flush_rows(self):
        """Insert pending rows to database"""
        if not self.pending_rows:
            return
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        try:
            execute_values(
                cur,
                """INSERT INTO market_data 
                   (market_slug, market_title, timestamp, up_best_ask, up_liquidity, 
                    down_best_ask, down_liquidity, combined_cost, is_arb)
                   VALUES %s""",
                self.pending_rows
            )
            conn.commit()
            print(f"[DB] Inserted {len(self.pending_rows)} rows")
        except Exception as e:
            conn.rollback()
            print(f"[DB] Error inserting rows: {e}")
        finally:
            cur.close()
            conn.close()
        
        self.pending_rows = []
        self.last_insert = time.time()
    
    def reset(self):
        """Called when market closes - flush any remaining rows"""
        self._flush_rows()
        print(f"[DB] Market closed. Data saved for: {self.market_slug}")


# ============================================================
# Market Discovery (same as CSV version)
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
    print("\n[DISCOVERY] Looking for active SOL market...")
    
    for offset in [0, 1]:
        timestamp = get_interval_timestamp(offset)
        slug = f"sol-updown-15m-{timestamp}"
        
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

class PostgresBot:
    """Bot that streams to PostgreSQL"""
    
    def __init__(self):
        self.datastream: PostgresDataStream = None
        self.ws: WebSocketApp = None
        self._running = False
        self._reconnecting = False
        # Track trades for each wallet separately
        self._trader_trades = {wallet: [] for wallet in TRACKED_WALLETS}
        self._trader_seen = {wallet: set() for wallet in TRACKED_WALLETS}
    
    def _on_ws_open(self, ws):
        print("[WS] Connected, subscribing...")
        subscribe_msg = {
            "assets_ids": [self.up_token, self.down_token],
            "type": "market"
        }
        ws.send(json.dumps(subscribe_msg))
        print("[WS] Subscribed. Streaming to database...")
        
        def ping():
            while self._running:
                try:
                    ws.send("PING")
                    time.sleep(10)
                except:
                    break
        threading.Thread(target=ping, daemon=True).start()
        
        def monitor():
            while self._running:
                now = int(time.time())
                if now >= self.end_timestamp:
                    print("\n[BOT] Market expired!")
                    self._on_market_close()
                    break
                time.sleep(1)
        threading.Thread(target=monitor, daemon=True).start()
        
        def periodic_trader_fetch():
            fetch_interval = 180
            last_fetch = time.time()
            
            while self._running and not self._reconnecting:
                now = time.time()
                
                if now - last_fetch >= fetch_interval:
                    if self.datastream and not self._reconnecting:
                        # Fetch trades for all tracked wallets
                        for wallet in TRACKED_WALLETS:
                            print(f"\n[TRADER] Periodic fetch for {wallet[:10]}...")
                            trades = fetch_trader_trades(
                                wallet_address=wallet,
                                market_slug=self.datastream.market_slug,
                                market_title=self.datastream.market_title,
                                start_time=self.datastream.start_time,
                                end_time=self.datastream.end_time
                            )
                            
                            for t in trades:
                                key = (t['timestamp'], t['price'], t['size'], t['outcome'])
                                if key not in self._trader_seen[wallet]:
                                    self._trader_seen[wallet].add(key)
                                    self._trader_trades[wallet].append(t)
                            
                            print(f"[TRADER] {wallet[:10]}: {len(self._trader_trades[wallet])} unique trades so far")
                        last_fetch = now
                
                if int(now) >= self.end_timestamp:
                    break
                    
                time.sleep(10)
        
        threading.Thread(target=periodic_trader_fetch, daemon=True).start()
    
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
            
            # Final fetch for all tracked wallets
            for wallet in TRACKED_WALLETS:
                print(f"\n[BOT] Final fetch for {wallet[:10]}...")
                final_trades = fetch_trader_trades(
                    wallet_address=wallet,
                    market_slug=self.datastream.market_slug,
                    market_title=self.datastream.market_title,
                    start_time=self.datastream.start_time,
                    end_time=self.datastream.end_time
                )
                
                for t in final_trades:
                    key = (t['timestamp'], t['price'], t['size'], t['outcome'])
                    if key not in self._trader_seen[wallet]:
                        self._trader_seen[wallet].add(key)
                        self._trader_trades[wallet].append(t)
                
                self._trader_trades[wallet].sort(key=lambda x: x['timestamp'])
                
                print(f"[TRADER] {wallet[:10]}: Total accumulated: {len(self._trader_trades[wallet])} trades")
                
                save_trader_trades_to_db(
                    wallet_address=wallet,
                    market_slug=self.datastream.market_slug,
                    trades=self._trader_trades[wallet]
                )
                
                self._trader_trades[wallet] = []
                self._trader_seen[wallet] = set()
        
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
        
        start_date = end_date - timedelta(minutes=15)
        
        if wait_for_fresh:
            now = int(time.time())
            time_remaining = self.end_timestamp - now
            time_elapsed = 900 - time_remaining
            
            if time_elapsed > 60:
                print(f"[BOT] Market already {time_elapsed:.0f}s in progress. Waiting for next market...")
                print(f"[BOT] Time remaining in current market: {time_remaining:.0f}s")
                
                wait_time = time_remaining + 5
                print(f"[BOT] Waiting {wait_time:.0f}s for fresh market...")
                time.sleep(wait_time)
                
                return self._setup(wait_for_fresh=False)
            else:
                print(f"[BOT] Market is fresh ({time_elapsed:.0f}s elapsed). Starting collection.")
        
        print(f"[BOT] Market window: {start_date.strftime('%H:%M:%S')} - {end_date.strftime('%H:%M:%S')} UTC")
        
        self.datastream = PostgresDataStream(
            market_slug=market["slug"],
            market_title=market["title"],
            up_token=self.up_token,
            down_token=self.down_token,
            start_time=start_date,
            end_time=end_date
        )
        
        ws_url = f"{WSS_URL}/ws/market"
        self.ws = WebSocketApp(
            ws_url,
            on_open=self._on_ws_open,
            on_message=self._on_ws_message,
            on_error=self._on_ws_error,
            on_close=self._on_ws_close
        )
        
        ws_thread = threading.Thread(target=self.ws.run_forever, daemon=True)
        ws_thread.start()
        
        return True
    
    def _cleanup(self):
        """Graceful shutdown - flush all pending data"""
        print("\n[BOT] Shutting down gracefully...")
        self._running = False
        
        # Flush any pending market data
        if self.datastream:
            print("[BOT] Flushing pending market data...")
            self.datastream._flush_rows()
        
        # Close websocket
        if self.ws:
            self.ws.close()
        
        print("[BOT] Cleanup complete.")
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully"""
        print(f"\n[BOT] Received signal {signum}, shutting down...")
        self._cleanup()
        sys.exit(0)
    
    def run(self):
        print("=" * 60)
        print("  POSTGRESQL DATA COLLECTOR + TRADER TRACKER - SOLANA")
        print(f"  Tracking wallets:")
        for wallet in TRACKED_WALLETS:
            print(f"    - {wallet[:10]}...")
        print("=" * 60)
        
        # Initialize database tables
        init_tables()
        
        # Register signal handlers for graceful shutdown
        signal.signal(signal.SIGTERM, self._signal_handler)  # Railway sends SIGTERM on restart
        signal.signal(signal.SIGINT, self._signal_handler)   # Ctrl+C
        
        self._running = True
        
        if not self._setup(wait_for_fresh=True):
            print("[BOT] Failed to setup. Exiting.")
            return
        
        print("\n[BOT] Running. Press Ctrl+C to stop.\n")
        
        try:
            while self._running:
                time.sleep(1)
        except KeyboardInterrupt:
            self._cleanup()
            print("[BOT] Done!")


if __name__ == "__main__":
    bot = PostgresBot()
    bot.run()

