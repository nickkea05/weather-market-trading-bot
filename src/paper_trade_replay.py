"""
Paper Trading Replay - Simulates strategy on historical market data
Reads from CSV files and replays the market, running strategy on each data point
"""

import csv
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from strategy import (
    PositionState, 
    execute_trade, 
    calculate_min_profit, 
    calculate_balance_ratio,
    TICK_INTERVAL_SEC
)


class MarketStateSimulator:
    """Simulates MarketState from CSV data"""
    def __init__(self):
        self.up_best_ask: Optional[float] = None
        self.up_ask_liquidity: Optional[float] = None
        self.down_best_ask: Optional[float] = None
        self.down_ask_liquidity: Optional[float] = None
    
    def update_from_row(self, row: dict):
        """Update state from CSV row"""
        if row.get('up_best_ask'):
            try:
                self.up_best_ask = float(row['up_best_ask'])
            except (ValueError, TypeError):
                pass
        
        if row.get('up_liquidity'):
            try:
                self.up_ask_liquidity = float(row['up_liquidity'])
            except (ValueError, TypeError):
                pass
        
        if row.get('down_best_ask'):
            try:
                self.down_best_ask = float(row['down_best_ask'])
            except (ValueError, TypeError):
                pass
        
        if row.get('down_liquidity'):
            try:
                self.down_ask_liquidity = float(row['down_liquidity'])
            except (ValueError, TypeError):
                pass


class PaperTradingReplay:
    """
    Replays a market from CSV data and runs strategy.
    Outputs trades for comparison with gabagool.
    """
    
    def __init__(self, market_csv_path: str, time_limit_minutes: Optional[float] = None):
        self.market_csv_path = market_csv_path
        self.position_state: PositionState = None
        self.trade_log = []
        self.market_data_rows = []
        self.market_start_time = None
        self.market_end_time = None
        self.time_limit_minutes = time_limit_minutes  # None = full market, otherwise limit to N minutes
        
    def _load_market_data(self):
        """Load and parse market CSV file"""
        print(f"[REPLAY] Loading market data from: {self.market_csv_path}")
        
        with open(self.market_csv_path, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                self.market_data_rows.append(row)
        
        if not self.market_data_rows:
            raise ValueError("No data in CSV file")
        
        # Parse first and last timestamps to get market duration
        first_timestamp = self._parse_timestamp(self.market_data_rows[0]['timestamp'])
        last_timestamp = self._parse_timestamp(self.market_data_rows[-1]['timestamp'])
        
        self.market_start_time = first_timestamp
        
        # Filter to time limit if specified
        if self.time_limit_minutes is not None:
            time_limit_seconds = self.time_limit_minutes * 60
            cutoff_timestamp = first_timestamp + time_limit_seconds
            self.market_data_rows = [
                row for row in self.market_data_rows 
                if self._parse_timestamp(row['timestamp']) <= cutoff_timestamp
            ]
            self.market_end_time = min(cutoff_timestamp, last_timestamp)
            print(f"[REPLAY] Filtered to first {self.time_limit_minutes} minutes")
        else:
            self.market_end_time = last_timestamp
        
        print(f"[REPLAY] Loaded {len(self.market_data_rows)} data points")
        print(f"[REPLAY] Market duration: {(self.market_end_time - self.market_start_time):.1f} seconds")
        
        return True
    
    def _parse_timestamp(self, timestamp_str: str) -> float:
        """Parse ISO timestamp to Unix timestamp"""
        try:
            from datetime import timezone, timedelta
            
            # Try Unix timestamp (float) first
            try:
                return float(timestamp_str)
            except ValueError:
                pass
            
            # Try ISO format with T separator (e.g., "2025-12-16T01:00:19+00:00")
            if 'T' in timestamp_str:
                # Check if it has timezone info
                has_utc = '+00:00' in timestamp_str or 'Z' in timestamp_str
                
                # Remove timezone info for parsing
                if '+' in timestamp_str:
                    timestamp_clean = timestamp_str.split('+')[0]
                elif 'Z' in timestamp_str:
                    timestamp_clean = timestamp_str.split('Z')[0]
                else:
                    timestamp_clean = timestamp_str
                
                if '.' in timestamp_clean:
                    dt = datetime.strptime(timestamp_clean.split('.')[0], "%Y-%m-%dT%H:%M:%S")
                    microseconds = int(timestamp_clean.split('.')[1][:6].ljust(6, '0'))
                    dt = dt.replace(microsecond=microseconds)
                else:
                    dt = datetime.strptime(timestamp_clean, "%Y-%m-%dT%H:%M:%S")
                
                # If timestamp is UTC, mark it as such
                if has_utc:
                    dt = dt.replace(tzinfo=timezone.utc)
                    return dt.timestamp()
                else:
                    return dt.timestamp()
            
            # Handle format: "2025-12-15 20:00:10.407"
            dt = datetime.strptime(timestamp_str.split('.')[0], "%Y-%m-%d %H:%M:%S")
            # Add microseconds if present
            if '.' in timestamp_str:
                microseconds = int(timestamp_str.split('.')[1][:6].ljust(6, '0'))
                dt = dt.replace(microsecond=microseconds)
            return dt.timestamp()
        except Exception as e:
            print(f"[REPLAY] Error parsing timestamp '{timestamp_str}': {e}")
            return time.time()
    
    def _execute_trade(self, trade: dict):
        """Execute a trade - update PositionState and log"""
        side = trade['side']
        size = trade['size']
        price = trade['price']
        amount = trade.get('amount', size * price)
        reason = trade.get('reason', 'UNKNOWN')
        up_price_at_time = trade.get('up_price_at_time', 0)
        down_price_at_time = trade.get('down_price_at_time', 0)
        
        # Update PositionState
        if side == 'UP':
            self.position_state.up_shares += size
            self.position_state.up_cost += amount
        else:  # DOWN
            self.position_state.down_shares += size
            self.position_state.down_cost += amount
        
        # Calculate metrics after trade
        avg_up = self.position_state.up_cost / self.position_state.up_shares if self.position_state.up_shares > 0 else 0
        avg_down = self.position_state.down_cost / self.position_state.down_shares if self.position_state.down_shares > 0 else 0
        
        balance_ratio = calculate_balance_ratio(self.position_state.up_shares, self.position_state.down_shares)
        
        # Calculate worst-case profit
        min_profit = calculate_min_profit(
            self.position_state.up_shares,
            self.position_state.down_shares,
            self.position_state.up_cost,
            self.position_state.down_cost
        )
        
        # Print trade with reason and BOTH market prices
        print(f"[TRADE #{len(self.trade_log)+1:2d}] {reason:18s} {side:>4} ${price:.3f} x {size:6.2f} = ${amount:6.2f} | Market: UP=${up_price_at_time:.3f} DOWN=${down_price_at_time:.3f} | Pos: UP {self.position_state.up_shares:6.1f}@${avg_up:.3f} DOWN {self.position_state.down_shares:6.1f}@${avg_down:.3f} | MinProfit: ${min_profit:7.2f}")
        
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
    
    def _simulate_tick(self, row: dict, market_state: MarketStateSimulator):
        """Simulate one tick - update state and run strategy"""
        # Update simulated market state
        market_state.update_from_row(row)
        
        # Update position state time
        row_timestamp = self._parse_timestamp(row['timestamp'])
        self.position_state.current_time = row_timestamp
        
        # Get prices and liquidity
        up_price = market_state.up_best_ask
        down_price = market_state.down_best_ask
        up_liquidity = market_state.up_ask_liquidity or 0.0
        down_liquidity = market_state.down_ask_liquidity or 0.0
        
        # Skip if prices not available
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
        for trade in trades:
            # Add market prices to trade for logging
            trade['up_price_at_time'] = up_price
            trade['down_price_at_time'] = down_price
            self._execute_trade(trade)
    
    def _save_trades_to_csv(self, output_path: str):
        """Save trades to CSV file"""
        if not self.trade_log:
            print("[REPLAY] No trades executed")
            return
        
        with open(output_path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['timestamp', 'side', 'size', 'price', 'cost', 'reason'])
            for trade in self.trade_log:
                writer.writerow([
                    trade['timestamp'],
                    trade['side'],
                    trade['size'],
                    trade['price'],
                    trade['cost'],
                    trade.get('reason', 'UNKNOWN')
                ])
        
        print(f"[REPLAY] Saved {len(self.trade_log)} trades to {output_path}")
    
    def _find_gabagool_csv(self) -> Optional[str]:
        """Find corresponding gabagool CSV file"""
        market_path = Path(self.market_csv_path)
        market_name = market_path.stem  # e.g., "btc-15m_11-00pm_11-15pm_1765857600_market"
        
        # Remove "_market" suffix and add "_gabagool"
        if market_name.endswith('_market'):
            base_name = market_name[:-7]  # Remove "_market"
            gabagool_name = f"{base_name}_gabagool.csv"
            gabagool_path = market_path.parent / gabagool_name
            
            if gabagool_path.exists():
                return str(gabagool_path)
        
        return None
    
    def _print_gabagool_trades(self, gabagool_csv_path: str):
        """Print all gabagool trades for comparison"""
        try:
            import csv
            
            # Calculate cutoff timestamp if time limit is set
            cutoff_timestamp = None
            if self.time_limit_minutes is not None and self.market_start_time is not None:
                cutoff_timestamp = self.market_start_time + (self.time_limit_minutes * 60)
            
            trades = []
            with open(gabagool_csv_path, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # Filter by time limit if set
                    if cutoff_timestamp is not None:
                        trade_timestamp = self._parse_timestamp(row.get('timestamp', ''))
                        if trade_timestamp > cutoff_timestamp:
                            continue  # Skip trades after time limit
                    
                    outcome = str(row.get('outcome', '')).strip()
                    size = float(row.get('size', 0))
                    cost = float(row.get('usdcSize', 0))
                    price = float(row.get('price', 0))
                    
                    trades.append({
                        'side': outcome.upper(),
                        'size': size,
                        'cost': cost,
                        'price': price
                    })
            
            if not trades:
                print("\n[GABAGOOL] No trades found")
                return
            
            print("\n" + "=" * 100)
            print("GABAGOOL TRADES")
            print("=" * 100)
            
            # Simulate gabagool's position
            up_shares = 0.0
            down_shares = 0.0
            up_cost = 0.0
            down_cost = 0.0
            
            for i, trade in enumerate(trades):
                if trade['side'] == 'UP':
                    up_shares += trade['size']
                    up_cost += trade['cost']
                else:
                    down_shares += trade['size']
                    down_cost += trade['cost']
                
                # Calculate metrics after trade
                avg_up = up_cost / up_shares if up_shares > 0 else 0
                avg_down = down_cost / down_shares if down_shares > 0 else 0
                
                total_shares = up_shares + down_shares
                up_ratio = up_shares / total_shares if total_shares > 0 else 0
                balance_ratio = abs(up_ratio - 0.5) * 2.0
                
                # Calculate worst-case profit
                worst_case = calculate_min_profit(up_shares, down_shares, up_cost, down_cost)
                
                # Print trade
                side = trade['side']
                price = trade['price']
                size = trade['size']
                amount = trade['cost']
                print(f"[TRADE #{i+1:2d}] {side:>4} ${price:.3f} x {size:6.2f} = ${amount:6.2f} | UP {up_shares:6.1f}@${avg_up:.3f} DOWN {down_shares:6.1f}@${avg_down:.3f} | MinProfit: ${worst_case:7.2f} | Bal: {balance_ratio:.3f}")
            
            print("=" * 100)
            
        except Exception as e:
            print(f"\n[GABAGOOL] Error printing trades: {e}")
    
    def _calculate_gabagool_position(self, gabagool_csv_path: str) -> Optional[dict]:
        """Calculate gabagool's final position from CSV (filtered to time limit if set)"""
        try:
            import csv
            
            up_shares = 0.0
            down_shares = 0.0
            up_cost = 0.0
            down_cost = 0.0
            up_prices = []
            down_prices = []
            
            # Calculate cutoff timestamp if time limit is set
            cutoff_timestamp = None
            if self.time_limit_minutes is not None and self.market_start_time is not None:
                cutoff_timestamp = self.market_start_time + (self.time_limit_minutes * 60)
            
            with open(gabagool_csv_path, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # Filter by time limit if set
                    if cutoff_timestamp is not None:
                        trade_timestamp = self._parse_timestamp(row.get('timestamp', ''))
                        if trade_timestamp > cutoff_timestamp:
                            continue  # Skip trades after time limit
                    
                    outcome = str(row.get('outcome', '')).strip()
                    size = float(row.get('size', 0))
                    cost = float(row.get('usdcSize', 0))
                    price = float(row.get('price', 0))
                    
                    if outcome.lower() == 'up':
                        up_shares += size
                        up_cost += cost
                        up_prices.append(price)
                    elif outcome.lower() == 'down':
                        down_shares += size
                        down_cost += cost
                        down_prices.append(price)
            
            total_cost = up_cost + down_cost
            profit_if_up = up_shares * 1.0 - total_cost
            profit_if_down = down_shares * 1.0 - total_cost
            worst_case = min(profit_if_up, profit_if_down)
            best_case = max(profit_if_up, profit_if_down)
            
            avg_up_price = sum(up_prices) / len(up_prices) if up_prices else 0.0
            avg_down_price = sum(down_prices) / len(down_prices) if down_prices else 0.0
            
            return {
                'up_shares': up_shares,
                'down_shares': down_shares,
                'up_cost': up_cost,
                'down_cost': down_cost,
                'total_cost': total_cost,
                'avg_up_price': avg_up_price,
                'avg_down_price': avg_down_price,
                'profit_if_up': profit_if_up,
                'profit_if_down': profit_if_down,
                'worst_case': worst_case,
                'best_case': best_case,
                'total_trades': len(up_prices) + len(down_prices)
            }
        except Exception as e:
            print(f"[REPLAY] Error calculating gabagool position: {e}")
            return None
    
    def _calculate_final_pnl(self, winner: Optional[str] = None):
        """Calculate final PnL for both our bot and gabagool"""
        # Calculate our position
        worst = calculate_min_profit(
            self.position_state.up_shares,
            self.position_state.down_shares,
            self.position_state.up_cost,
            self.position_state.down_cost
        )
        
        total_cost = self.position_state.up_cost + self.position_state.down_cost
        profit_if_up = self.position_state.up_shares * 1.0 - total_cost
        profit_if_down = self.position_state.down_shares * 1.0 - total_cost
        best = max(profit_if_up, profit_if_down)
        
        # Calculate actual PnL if winner is known
        our_actual_profit = None
        if winner == 'UP':
            our_actual_profit = profit_if_up
        elif winner == 'DOWN':
            our_actual_profit = profit_if_down
        
        # Calculate average prices
        our_up_trades = [t for t in self.trade_log if t['side'] == 'UP']
        our_down_trades = [t for t in self.trade_log if t['side'] == 'DOWN']
        our_avg_up_price = sum(t['price'] for t in our_up_trades) / len(our_up_trades) if our_up_trades else 0.0
        our_avg_down_price = sum(t['price'] for t in our_down_trades) / len(our_down_trades) if our_down_trades else 0.0
        
        # Try to load and calculate gabagool position
        gabagool_csv = self._find_gabagool_csv()
        gabagool_pos = None
        if gabagool_csv:
            gabagool_pos = self._calculate_gabagool_position(gabagool_csv)
        
        # Calculate balance ratio for our bot
        our_balance_ratio = calculate_balance_ratio(self.position_state.up_shares, self.position_state.down_shares)
        our_total_shares = self.position_state.up_shares + self.position_state.down_shares
        our_up_ratio = (self.position_state.up_shares / our_total_shares * 100) if our_total_shares > 0 else 0.0
        our_down_ratio = (self.position_state.down_shares / our_total_shares * 100) if our_total_shares > 0 else 0.0
        
        # Calculate trade counts by reason
        arb_trades = [t for t in self.trade_log if t.get('reason') == 'ARB']
        accumulate_trades = [t for t in self.trade_log if t.get('reason') == 'ACCUMULATE']
        rebalance_trades = [t for t in self.trade_log if t.get('reason') == 'CRITICAL_REBALANCE']
        
        # Print our position
        print(f"\n" + "=" * 80)
        print("OUR BOT - FINAL POSITION")
        if self.time_limit_minutes is not None:
            print(f"(First {self.time_limit_minutes} minutes only)")
        print("=" * 80)
        print(f"Total Trades: {len(self.trade_log)}")
        print(f"  ARB: {len(arb_trades)}, ACCUMULATE: {len(accumulate_trades)}, REBALANCE: {len(rebalance_trades)}")
        print(f"UP Shares: {self.position_state.up_shares:.2f}")
        print(f"DOWN Shares: {self.position_state.down_shares:.2f}")
        print(f"Balance Ratio: {our_balance_ratio:.3f} (UP: {our_up_ratio:.1f}%, DOWN: {our_down_ratio:.1f}%)")
        print(f"UP Cost: ${self.position_state.up_cost:.2f}")
        print(f"DOWN Cost: ${self.position_state.down_cost:.2f}")
        print(f"Total Cost: ${total_cost:.2f}")
        print(f"UP Average: ${our_avg_up_price:.3f} ({our_avg_up_price*100:.1f} cents)")
        print(f"DOWN Average: ${our_avg_down_price:.3f} ({our_avg_down_price*100:.1f} cents)")
        print(f"Worst Case Profit: ${worst:.2f}")
        print(f"Best Case Profit: ${best:.2f}")
        if winner:
            print(f"Winner: {winner}")
            if our_actual_profit is not None:
                print(f"ACTUAL PROFIT: ${our_actual_profit:.2f}")
        else:
            print(f"Winner: Unknown")
        
        # Print gabagool position if available
        if gabagool_pos:
            gabagool_actual = gabagool_pos['profit_if_up'] if winner == 'UP' else gabagool_pos['profit_if_down'] if winner == 'DOWN' else None
            
            # Calculate balance ratio for gabagool
            gabagool_total_shares = gabagool_pos['up_shares'] + gabagool_pos['down_shares']
            if gabagool_total_shares > 0:
                gabagool_up_ratio = gabagool_pos['up_shares'] / gabagool_total_shares
                gabagool_balance_ratio = abs(gabagool_up_ratio - 0.5) * 2.0
                gabagool_up_pct = gabagool_up_ratio * 100
                gabagool_down_pct = (1 - gabagool_up_ratio) * 100
            else:
                gabagool_balance_ratio = 0.0
                gabagool_up_pct = 0.0
                gabagool_down_pct = 0.0
            
            print(f"\n" + "=" * 80)
            print("GABAGOOL - FINAL POSITION")
            if self.time_limit_minutes is not None:
                print(f"(First {self.time_limit_minutes} minutes only)")
            print("=" * 80)
            print(f"Total Trades: {gabagool_pos['total_trades']}")
            print(f"UP Shares: {gabagool_pos['up_shares']:.2f}")
            print(f"DOWN Shares: {gabagool_pos['down_shares']:.2f}")
            print(f"Balance Ratio: {gabagool_balance_ratio:.3f} (UP: {gabagool_up_pct:.1f}%, DOWN: {gabagool_down_pct:.1f}%)")
            print(f"UP Cost: ${gabagool_pos['up_cost']:.2f}")
            print(f"DOWN Cost: ${gabagool_pos['down_cost']:.2f}")
            print(f"Total Cost: ${gabagool_pos['total_cost']:.2f}")
            print(f"UP Average: ${gabagool_pos['avg_up_price']:.3f} ({gabagool_pos['avg_up_price']*100:.1f} cents)")
            print(f"DOWN Average: ${gabagool_pos['avg_down_price']:.3f} ({gabagool_pos['avg_down_price']*100:.1f} cents)")
            print(f"Worst Case Profit: ${gabagool_pos['worst_case']:.2f}")
            print(f"Best Case Profit: ${gabagool_pos['best_case']:.2f}")
            if winner and gabagool_actual is not None:
                print(f"Winner: {winner}")
                print(f"ACTUAL PROFIT: ${gabagool_actual:.2f}")
            
            # Comparison
            if our_actual_profit is not None and gabagool_actual is not None:
                print(f"\n" + "=" * 80)
                print("COMPARISON")
                print("=" * 80)
                print(f"Trade Count: {gabagool_pos['total_trades']} vs {len(self.trade_log)} ({gabagool_pos['total_trades']/len(self.trade_log):.2f}x)")
                print(f"Total Cost: ${gabagool_pos['total_cost']:.2f} vs ${total_cost:.2f} ({gabagool_pos['total_cost']/total_cost:.2f}x)")
                print(f"Profit Difference: ${gabagool_actual - our_actual_profit:.2f}")
        else:
            print(f"\n[REPLAY] Gabagool CSV not found - skipping comparison")
    
    def run(self, speed: str = 'fast', tick_interval: Optional[float] = None):
        """
        Run replay simulation
        
        Args:
            speed: 'fast' (instant) or 'realtime' (respect timestamps)
            tick_interval: If provided, only process rows every N seconds (simulates tick rate)
        """
        print("\n" + "=" * 60)
        print("  PAPER TRADING REPLAY")
        print("=" * 60)
        if self.time_limit_minutes is not None:
            print(f"[REPLAY] TIME LIMIT: First {self.time_limit_minutes} minutes only")
        print()
        
        # Load market data
        self._load_market_data()
        
        # Initialize PositionState
        self.position_state = PositionState(self.market_start_time)
        
        print(f"[REPLAY] PositionState initialized (start: {self.market_start_time})")
        print(f"[REPLAY] Running in '{speed}' mode\n")
        
        # Simulate market state
        market_state = MarketStateSimulator()
        
        # Process rows
        last_processed_time = self.market_start_time
        rows_processed = 0
        
        for i, row in enumerate(self.market_data_rows):
            row_timestamp = self._parse_timestamp(row['timestamp'])
            
            # If tick_interval specified, only process every N seconds
            if tick_interval:
                if row_timestamp - last_processed_time < tick_interval:
                    continue
                last_processed_time = row_timestamp
            
            # Simulate tick
            self._simulate_tick(row, market_state)
            rows_processed += 1
            
            # Progress update
            if (i + 1) % 1000 == 0:
                elapsed = row_timestamp - self.market_start_time
                print(f"[REPLAY] Processed {i+1}/{len(self.market_data_rows)} rows ({elapsed:.1f}s into market)")
            
            # If realtime mode, sleep to match timestamps
            if speed == 'realtime' and i < len(self.market_data_rows) - 1:
                next_timestamp = self._parse_timestamp(self.market_data_rows[i + 1]['timestamp'])
                sleep_time = next_timestamp - row_timestamp
                if sleep_time > 0 and sleep_time < 1.0:  # Don't sleep too long
                    time.sleep(sleep_time)
        
        print(f"\n[REPLAY] Replay complete: {rows_processed} ticks processed")
        
        # Print gabagool trades for comparison
        # Gabagool trades removed from logs per user request
        # gabagool_csv = self._find_gabagool_csv()
        # if gabagool_csv:
        #     self._print_gabagool_trades(gabagool_csv)
        
        # Determine winner from last data point
        winner = self._determine_winner()
        
        # Calculate final PnL
        if self.position_state:
            self._calculate_final_pnl(winner)
        
        # Save trades
        output_filename = self.market_csv_path.replace('_market.csv', '_marketpapertrades.csv')
        self._save_trades_to_csv(output_filename)
        
        print(f"\n[REPLAY] Replay finished. Compare with gabagool CSV for same market.")
    
    def _determine_winner(self) -> Optional[str]:
        """Determine winner from last data point - side above 0.90 wins"""
        if not self.market_data_rows:
            return None
        
        last_row = self.market_data_rows[-1]
        
        try:
            up_price = float(last_row.get('up_best_ask', 0) or 0)
            down_price = float(last_row.get('down_best_ask', 0) or 0)
            
            # Side above 0.90 wins (other side would be below 0.10)
            if up_price >= 0.90:
                print(f"[REPLAY] Winner determined: UP (final price: ${up_price:.3f})")
                return 'UP'
            elif down_price >= 0.90:
                print(f"[REPLAY] Winner determined: DOWN (final price: ${down_price:.3f})")
                return 'DOWN'
            else:
                # Neither above 0.90 - market might not have resolved yet
                # Use whichever is higher
                if up_price > down_price:
                    print(f"[REPLAY] Winner inferred: UP (UP=${up_price:.3f}, DOWN=${down_price:.3f})")
                    return 'UP'
                else:
                    print(f"[REPLAY] Winner inferred: DOWN (UP=${up_price:.3f}, DOWN=${down_price:.3f})")
                    return 'DOWN'
        except (ValueError, TypeError):
            print(f"[REPLAY] Could not determine winner from last data point")
            return None


def main():
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python paper_trade_replay.py <market_csv_path> [speed] [time_limit_minutes]")
        print("  speed: 'fast' (default) or 'realtime'")
        print("  time_limit_minutes: Limit replay to first N minutes (default: full market)")
        print("\nExample:")
        print("  python paper_trade_replay.py testing_data/btc-15m_11-00pm_11-15pm_1765857600_market.csv fast 1")
        return
    
    market_csv = sys.argv[1]
    speed = sys.argv[2] if len(sys.argv) > 2 else 'fast'
    time_limit_minutes = float(sys.argv[3]) if len(sys.argv) > 3 else None
    
    if not Path(market_csv).exists():
        print(f"Error: File not found: {market_csv}")
        return
    
    replay = PaperTradingReplay(market_csv, time_limit_minutes=time_limit_minutes)
    replay.run(speed=speed, tick_interval=TICK_INTERVAL_SEC)


if __name__ == "__main__":
    main()

