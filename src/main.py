"""
BTC Statistical Arbitrage Bot for Polymarket
Main entry point - coordinates connection, datastream, and bot logic
"""

import os
import time
from dotenv import load_dotenv

from connection import MarketConnection
from datastream import DataStream, MarketState
from strategy import (
    PositionState, 
    execute_trade,
    calculate_min_profit,
    calculate_balance_ratio,
    TICK_INTERVAL_SEC
)

load_dotenv()


class ArbitrageBot:
    """
    Main bot class that coordinates:
    - Market connection (discovery + WebSocket)
    - Data streaming (price tracking)
    - Auto-reconnection on market close
    """
    
    def __init__(self):
        self.connection: MarketConnection = None
        self.datastream: DataStream = None
        self.position_state: PositionState = None
        self._running = False
        self._reconnecting = False  # Prevent double reconnection
        self._first_tick_logged = False  # Track if we've logged first tick
    
    def _setup_connection(self) -> bool:
        """Setup connection to current market"""
        print("\n" + "=" * 60)
        print("SETTING UP CONNECTION")
        print("=" * 60)
        
        # Create new connection
        self.connection = MarketConnection()
        
        # Discover market
        if not self.connection.discover_market():
            print("[BOT] Failed to discover market")
            return False
        
        # Check if market is already in progress
        # If more than 60 seconds have elapsed, wait for next market
        end_timestamp = self.connection.market_data["end_timestamp"]
        time_remaining = self.connection.market_data.get("time_remaining", 0)
        time_elapsed = 900 - time_remaining  # 900 seconds = 15 minutes
        
        if time_elapsed > 60:
            print(f"[BOT] Market already {time_elapsed:.0f}s in progress. Waiting for next market...")
            print(f"[BOT] Time remaining in current market: {time_remaining:.0f}s")
            print(f"[BOT] Waiting {time_remaining + 5}s for fresh market...")  # Add buffer
            time.sleep(time_remaining + 5)
            # Recursively try again to get the next market
            return self._setup_connection()
        
        print(f"[BOT] Market is fresh ({time_elapsed:.0f}s elapsed). Starting bot.")
        
        # Create datastream with token IDs
        self.datastream = DataStream(
            up_token=self.connection.market_data["up_token"],
            down_token=self.connection.market_data["down_token"],
            verbose=True
        )
        
        # Set callbacks
        self.connection.set_message_callback(self.datastream.process_message)
        self.connection.set_market_close_callback(self._on_market_close)
        
        # Connect WebSocket
        if not self.connection.connect_websocket():
            print("[BOT] Failed to connect WebSocket")
            return False
        
        # Initialize PositionState for new market
        # Market is 15 minutes, so start_time = end_timestamp - 900 seconds
        start_timestamp = end_timestamp - 900  # 15 minutes = 900 seconds
        
        self.position_state = PositionState(float(start_timestamp))
        print(f"[BOT] PositionState initialized:")
        print(f"      - Market start: {start_timestamp}")
        print(f"      - Market end: {end_timestamp}")
        print(f"      - UP shares: {self.position_state.up_shares}")
        print(f"      - DOWN shares: {self.position_state.down_shares}")
        print(f"      - UP cost: ${self.position_state.up_cost}")
        print(f"      - DOWN cost: ${self.position_state.down_cost}")
        
        print("\n" + "=" * 60)
        print("STREAMING DATA")
        print("=" * 60)
        print("[BOT] Waiting for price updates...\n")
        
        return True
    
    def _on_market_close(self):
        """Called when market closes - trigger reconnection"""
        # Prevent multiple simultaneous reconnection attempts
        if self._reconnecting:
            return
        self._reconnecting = True
        
        print("\n" + "=" * 60)
        print("[BOT] MARKET CLOSED - RECONNECTING TO NEW MARKET")
        print("=" * 60)
        
        # Disconnect old connection
        if self.connection:
            self.connection.disconnect()
        
        # Reset datastream
        if self.datastream:
            self.datastream.reset()
        
        # Reset PositionState (will be re-initialized when new market is found)
        if self.position_state:
            print(f"[BOT] PositionState reset (was: UP={self.position_state.up_shares}, DOWN={self.position_state.down_shares})")
        self.position_state = None
        self._first_tick_logged = False  # Reset for next market
        
        # Wait a moment for new market to be available
        print("[BOT] Waiting 5 seconds for new market...")
        time.sleep(5)
        
        # Setup new connection
        if self._running:
            success = self._setup_connection()
            if not success:
                print("[BOT] Failed to reconnect, will retry in 10 seconds...")
                time.sleep(10)
                if self._running:
                    self._setup_connection()
        
        self._reconnecting = False
    
    def get_current_state(self) -> MarketState:
        """Get current market state - for bot trading logic"""
        if self.datastream:
            return self.datastream.get_state()
        return MarketState()
    
    def _tick(self):
        """
        Called every TICK_INTERVAL_SEC seconds.
        Fetches prices from datastream and calls strategy layers.
        Common code for both paper trading and real trading.
        """
        if not self.datastream or not self.position_state:
            return
        
        # Update current time
        self.position_state.current_time = time.time()
        seconds_into_market = self.position_state.get_seconds_into_market()
        
        # Log first successful tick
        if not self._first_tick_logged:
            print(f"[BOT] First tick executed - PositionState active (seconds into market: {seconds_into_market:.1f})")
            self._first_tick_logged = True
        
        # Get prices and liquidity from datastream
        market_state = self.datastream.state
        up_price = market_state.up_best_ask
        down_price = market_state.down_best_ask
        up_liquidity = market_state.up_ask_liquidity or 0.0
        down_liquidity = market_state.down_ask_liquidity or 0.0
        
        # Skip if prices not available yet
        if up_price is None or down_price is None:
            return
        
        # Execute all trading decisions (can be multiple per tick)
        trades = execute_trade(
            self.position_state,
            up_price,
            down_price,
            up_liquidity,
            down_liquidity
        )
        
        # TODO: Execute trades (will be different for paper vs real)
        # For now, just log that we got trade signals
        for trade in trades:
            print(f"[TICK] Trade: {trade}")
    
    def run(self):
        """Main bot loop"""
        print("\n" + "=" * 60)
        print("  POLYMARKET BTC ARBITRAGE BOT")
        print("=" * 60)
        
        # Check for private key (for future trading)
        private_key = os.getenv("POLYMARKET_PRIVATE_KEY")
        if private_key:
            print("[BOT] Private key loaded")
        else:
            print("[BOT] WARNING: No private key found (read-only mode)")
        
        self._running = True
        
        # Setup initial connection
        if not self._setup_connection():
            print("[BOT] Initial setup failed, retrying in 10 seconds...")
            time.sleep(10)
            if not self._setup_connection():
                print("[BOT] Could not establish connection. Exiting.")
                return
        
        # Main loop - keep running until interrupted
        print("\n[BOT] Bot running. Press Ctrl+C to stop.\n")
        
        last_tick = 0
        
        try:
            while self._running:
                # Check connection health (skip if already reconnecting)
                if not self._reconnecting and not self.connection.is_connected():
                    print("[BOT] Connection lost, reconnecting...")
                    self._on_market_close()
                
                # Run tick every TICK_INTERVAL_SEC seconds
                current_time = time.time()
                if current_time - last_tick >= TICK_INTERVAL_SEC:
                    self._tick()
                    last_tick = current_time
                
                # Sleep briefly to avoid busy loop
                time.sleep(0.1)
                
        except KeyboardInterrupt:
            print("\n[BOT] Shutting down...")
            self._running = False
            if self.connection:
                self.connection.disconnect()
            print("[BOT] Goodbye!")


def main():
    bot = ArbitrageBot()
    bot.run()


if __name__ == "__main__":
    main()
