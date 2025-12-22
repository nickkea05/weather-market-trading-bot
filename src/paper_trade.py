"""
Paper Trading Bot - Simulates trades without real API calls
Extends main.py functionality with trade logging and position tracking

Railway deployment test - auto-deploy verification
"""

import os
import time
import csv
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

from connection import MarketConnection
from datastream import DataStream, MarketState
import strategy
from strategy import (
    PositionState, 
    execute_trade, 
    calculate_min_profit,
    calculate_balance_ratio,
    TICK_INTERVAL_SEC
)

load_dotenv()


class PaperTradingBot:
    """
    Paper trading bot - simulates trades and tracks position locally.
    Logs all trades to CSV for analysis.
    """
    
    def __init__(self):
        self.connection: MarketConnection = None
        self.datastream: DataStream = None
        self.position_state: PositionState = None
        self._running = False
        self._reconnecting = False
        self._first_tick_logged = False
        
        # Paper trading specific
        self.trade_log = []  # List of all trades: [{timestamp, side, size, price, cost}, ...]
        self.market_slug = None
        self.market_title = None
        self.trades_csv_path = None  # Path to trades CSV file
        self.position_csv_path = "testing_data/position_state.csv"  # Continuously updated position file
        self.last_up_price = None  # Track last prices to determine winner
        self.last_down_price = None
        
        # Internal tracking across markets (in memory only)
        self.market_count = 0
        self.total_profit = 0.0
        self.total_cost = 0.0
        self.wins = 0
        self.losses = 0
    
    def _setup_connection(self) -> bool:
        """Setup connection to current market"""
        print("\n" + "=" * 60)
        print("SETTING UP CONNECTION (PAPER TRADING)")
        print(f"[STRATEGY] Using strategy module: {strategy.__name__} ({strategy.__file__})")
        print("=" * 60)
        
        # Create new connection
        self.connection = MarketConnection()
        
        # Discover market
        if not self.connection.discover_market():
            print("[BOT] Failed to discover market")
            return False
        
        # Check if market is already in progress
        end_timestamp = self.connection.market_data["end_timestamp"]
        time_remaining = self.connection.market_data.get("time_remaining", 0)
        time_elapsed = 900 - time_remaining
        
        if time_elapsed > 60:
            print(f"[BOT] Market already {time_elapsed:.0f}s in progress. Waiting for next market...")
            print(f"[BOT] Time remaining in current market: {time_remaining:.0f}s")
            print(f"[BOT] Waiting {time_remaining + 5}s for fresh market...")
            time.sleep(time_remaining + 5)
            return self._setup_connection()
        
        print(f"[BOT] Market is fresh ({time_elapsed:.0f}s elapsed). Starting bot.")
        
        # Store market info for CSV filename
        self.market_slug = self.connection.market_data["slug"]
        self.market_title = self.connection.market_data["title"]
        
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
        start_timestamp = end_timestamp - 900  # 15 minutes
        
        self.position_state = PositionState(float(start_timestamp))
        print(f"[BOT] PositionState initialized:")
        print(f"      - Market start: {start_timestamp}")
        print(f"      - Market end: {end_timestamp}")
        print(f"      - UP shares: {self.position_state.up_shares}")
        print(f"      - DOWN shares: {self.position_state.down_shares}")
        print(f"      - UP cost: ${self.position_state.up_cost}")
        print(f"      - DOWN cost: ${self.position_state.down_cost}")
        
        # Reset trade log for new market
        self.trade_log = []
        
        # Create trades CSV file for this market
        timestamp = int(start_timestamp)
        start_dt = datetime.fromtimestamp(start_timestamp)
        end_dt = datetime.fromtimestamp(end_timestamp)
        start_str = start_dt.strftime("%I-%M%p").lstrip('0').lower()
        end_str = end_dt.strftime("%I-%M%p").lstrip('0').lower()
        
        Path("testing_data").mkdir(exist_ok=True)
        self.trades_csv_path = f"testing_data/paper-trade_{start_str}_{end_str}_{timestamp}.csv"
        
        # Initialize trades CSV with header
        with open(self.trades_csv_path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['timestamp', 'side', 'size', 'price', 'cost', 'reason'])
        
        print(f"[BOT] Trade log reset for new market")
        print(f"[BOT] Trades will be logged to: {self.trades_csv_path}")
        
        print("\n" + "=" * 60)
        print("STREAMING DATA (PAPER TRADING)")
        print("=" * 60)
        print("[BOT] Waiting for price updates...\n")
        
        return True
    
    def _on_market_close(self):
        """Called when market closes - save trades and reset"""
        if self._reconnecting:
            return
        self._reconnecting = True
        
        print("\n" + "=" * 60)
        print("[BOT] MARKET CLOSED - SAVING TRADES")
        print("=" * 60)
        
        # Save trades to CSV
        if self.trade_log:
            self._save_trades_to_csv()
        
        # Calculate final PnL and save results
        if self.position_state:
            actual_profit, total_cost, worst, best, winner = self._calculate_final_pnl()
            if actual_profit is not None:
                self._save_market_result(actual_profit, total_cost, worst, best, winner)
        
        # Disconnect old connection
        if self.connection:
            self.connection.disconnect()
        
        # Reset datastream
        if self.datastream:
            self.datastream.reset()
        
        # Reset PositionState
        if self.position_state:
            print(f"[BOT] PositionState reset (was: UP={self.position_state.up_shares}, DOWN={self.position_state.down_shares})")
        self.position_state = None
        self._first_tick_logged = False
        self.trade_log = []
        
        # Clear position CSV
        Path("testing_data").mkdir(exist_ok=True)
        with open(self.position_csv_path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['up_shares', 'down_shares', 'up_cost', 'down_cost', 'min_profit'])
            writer.writerow([0, 0, 0, 0, 0])
        print(f"[BOT] Position CSV cleared")
        
        # Wait for new market
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
    
    def _execute_trade(self, trade: dict):
        """
        Execute a trade in paper trading mode.
        Updates PositionState and logs the trade.
        """
        side = trade['side']
        size = trade['size']
        price = trade['price']
        amount = trade.get('amount', size * price)
        reason = trade.get('reason', 'UNKNOWN')
        
        # Update PositionState
        if side == 'UP':
            self.position_state.up_shares += size
            self.position_state.up_cost += amount
        else:  # DOWN
            self.position_state.down_shares += size
            self.position_state.down_cost += amount
        
        # Log trade
        trade_entry = {
            'timestamp': self.position_state.current_time,
            'side': side,
            'size': size,
            'price': price,
            'cost': amount,
            'reason': reason
        }
        self.trade_log.append(trade_entry)
        
        # Append to trades CSV immediately
        if self.trades_csv_path:
            with open(self.trades_csv_path, 'a', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    trade_entry['timestamp'],
                    trade_entry['side'],
                    trade_entry['size'],
                    trade_entry['price'],
                    trade_entry['cost'],
                    trade_entry['reason']
                ])
        
        print(f"[PAPER] Trade executed ({reason}): {side} {size:.2f} shares @ ${price:.3f} = ${amount:.2f}")
        print(f"        Position: UP={self.position_state.up_shares:.2f}, DOWN={self.position_state.down_shares:.2f}")
        print(f"        Costs: UP=${self.position_state.up_cost:.2f}, DOWN=${self.position_state.down_cost:.2f}")
    
    def _tick(self):
        """Called every TICK_INTERVAL_SEC - executes strategy and updates position"""
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
        
        # Store last prices to determine winner at market close
        self.last_up_price = up_price
        self.last_down_price = down_price
        
        # Execute all trading decisions (can be multiple per tick)
        trades = execute_trade(
            self.position_state,
            up_price,
            down_price,
            up_liquidity,
            down_liquidity
        )
        for trade in trades:
            self._execute_trade(trade)
        
        # Update position state CSV (overwrite each tick)
        self._update_position_csv()
    
    def _update_position_csv(self):
        """Update position state CSV file (overwrites each tick)"""
        if not self.position_state:
            return
        
        # Calculate min profit
        min_profit = calculate_min_profit(
            self.position_state.up_shares,
            self.position_state.down_shares,
            self.position_state.up_cost,
            self.position_state.down_cost
        )
        
        # Write position state (overwrites file each time)
        Path("testing_data").mkdir(exist_ok=True)
        with open(self.position_csv_path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['up_shares', 'down_shares', 'up_cost', 'down_cost', 'min_profit'])
            writer.writerow([
                self.position_state.up_shares,
                self.position_state.down_shares,
                self.position_state.up_cost,
                self.position_state.down_cost,
                min_profit
            ])
    
    def _save_trades_to_csv(self):
        """Print summary of trades (trades already saved as they happen)"""
        if not self.trade_log:
            print("[BOT] No trades executed this market")
            return
        
        print(f"[BOT] Market summary: {len(self.trade_log)} trades executed")
        print(f"[BOT] Trades saved to: {self.trades_csv_path}")
    
    def _calculate_final_pnl(self):
        """Calculate final PnL - determine winner from last prices and calculate actual profit"""
        total_cost = self.position_state.up_cost + self.position_state.down_cost
        
        # Calculate worst/best case
        worst = calculate_min_profit(
            self.position_state.up_shares,
            self.position_state.down_shares,
            self.position_state.up_cost,
            self.position_state.down_cost
        )
        profit_if_up = self.position_state.up_shares * 1.0 - total_cost
        profit_if_down = self.position_state.down_shares * 1.0 - total_cost
        best = max(profit_if_up, profit_if_down)
        
        # Determine winner based on last prices (> 0.8 = winner)
        actual_profit = None
        winner = None
        
        if self.last_up_price is not None and self.last_down_price is not None:
            if self.last_up_price > 0.8:
                winner = "UP"
                actual_profit = profit_if_up
            elif self.last_down_price > 0.8:
                winner = "DOWN"
                actual_profit = profit_if_down
            else:
                # Neither side > 0.8, use the higher price
                if self.last_up_price > self.last_down_price:
                    winner = "UP"
                    actual_profit = profit_if_up
                else:
                    winner = "DOWN"
                    actual_profit = profit_if_down
        
        print(f"\n[PAPER] Final Position:")
        print(f"        UP shares: {self.position_state.up_shares:.2f}")
        print(f"        DOWN shares: {self.position_state.down_shares:.2f}")
        print(f"        Total cost: ${total_cost:.2f}")
        print(f"        Worst case profit: ${worst:.2f}")
        print(f"        Best case profit: ${best:.2f}")
        
        if actual_profit is not None:
            print(f"\n[PAPER] Market Outcome:")
            print(f"        Last UP price: ${self.last_up_price:.4f}")
            print(f"        Last DOWN price: ${self.last_down_price:.4f}")
            print(f"        Winner: {winner}")
            print(f"        ACTUAL PROFIT: ${actual_profit:.2f}")
        else:
            print(f"\n[PAPER] Could not determine winner (no last prices available)")
        
        return actual_profit, total_cost, worst, best, winner
    
    def _save_market_result(self, actual_profit, total_cost, worst, best, winner):
        """Update internal stats and save simple summary to CSV"""
        if actual_profit is None:
            return
        
        self.market_count += 1
        
        # Update internal tracking
        self.total_profit += actual_profit
        self.total_cost += total_cost
        if actual_profit > 0:
            self.wins += 1
        else:
            self.losses += 1
        
        # Calculate overall stats
        overall_roi = (self.total_profit / self.total_cost * 100) if self.total_cost > 0 else 0
        win_rate = (self.wins / self.market_count * 100) if self.market_count > 0 else 0
        
        # Calculate average positions for this market
        up_avg = (self.position_state.up_cost / self.position_state.up_shares) if self.position_state.up_shares > 0 else 0
        down_avg = (self.position_state.down_cost / self.position_state.down_shares) if self.position_state.down_shares > 0 else 0
        combined_avg = up_avg + down_avg
        
        # Print summary (stats kept in memory only)
        print(f"\n{'='*80}")
        print(f"MARKET #{self.market_count} COMPLETE")
        print(f"{'='*80}")
        print(f"Market Profit: ${actual_profit:.2f}")
        print(f"Market Cost: ${total_cost:.2f}")
        print(f"Winner: {winner}")
        print(f"Average Positions: UP=${up_avg:.4f}, DOWN=${down_avg:.4f}, Combined=${combined_avg:.4f}")
        print(f"\nOVERALL STATS:")
        print(f"  Markets Traded: {self.market_count}")
        print(f"  Total Profit: ${self.total_profit:.2f}")
        print(f"  Total Cost: ${self.total_cost:.2f}")
        print(f"  Overall ROI: {overall_roi:.2f}%")
        print(f"  Win Rate: {win_rate:.1f}% ({self.wins}W / {self.losses}L)")
        print(f"{'='*80}\n")
    
    def run(self):
        """Main bot loop"""
        print("\n" + "=" * 60)
        print("  POLYMARKET BTC ARBITRAGE BOT (PAPER TRADING)")
        print("=" * 60)
        
        # Initialize position CSV
        Path("testing_data").mkdir(exist_ok=True)
        with open(self.position_csv_path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['up_shares', 'down_shares', 'up_cost', 'down_cost', 'min_profit'])
            writer.writerow([0, 0, 0, 0, 0])
        print(f"[BOT] Position CSV initialized: {self.position_csv_path}")
        print(f"[BOT] Overall stats tracking: In-memory only (no CSV)")
        
        self._running = True
        
        # Setup initial connection
        if not self._setup_connection():
            print("[BOT] Initial setup failed, retrying in 10 seconds...")
            time.sleep(10)
            if not self._setup_connection():
                print("[BOT] Could not establish connection. Exiting.")
                return
        
        # Main loop
        print("\n[BOT] Bot running. Press Ctrl+C to stop.\n")
        
        last_tick = 0
        
        try:
            while self._running:
                # Check connection health
                if not self._reconnecting and not self.connection.is_connected():
                    print("[BOT] Connection lost, reconnecting...")
                    self._on_market_close()
                
                # Run tick every TICK_INTERVAL_SEC seconds
                current_time = time.time()
                if current_time - last_tick >= TICK_INTERVAL_SEC:
                    self._tick()
                    last_tick = current_time
                
                time.sleep(0.1)
                
        except KeyboardInterrupt:
            print("\n[BOT] Shutting down...")
            self._running = False
            if self.connection:
                self.connection.disconnect()
            print("[BOT] Goodbye!")


def main():
    bot = PaperTradingBot()
    bot.run()


if __name__ == "__main__":
    main()

