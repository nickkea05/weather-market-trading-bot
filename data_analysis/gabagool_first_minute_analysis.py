#!/usr/bin/env python3
"""
Analyze gabagool's trading patterns in the first minute of each market.
Focus on: timing, amounts, side selection, balance ratio.
"""

import csv
import os
from datetime import datetime
from pathlib import Path
from collections import defaultdict


def parse_timestamp(timestamp_str: str) -> float:
    """Parse ISO timestamp to Unix timestamp"""
    try:
        # Try Unix timestamp (float) first
        try:
            return float(timestamp_str)
        except ValueError:
            pass
        
        # Try ISO format with T separator (e.g., "2025-12-16T01:00:19+00:00")
        if 'T' in timestamp_str:
            from datetime import timezone
            
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
                dt = dt.replace(microsecond=microseconds, tzinfo=timezone.utc)
            else:
                dt = datetime.strptime(timestamp_clean, "%Y-%m-%dT%H:%M:%S")
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.timestamp()
        
        # Handle format: "2025-12-15 20:00:10.407"
        dt = datetime.strptime(timestamp_str.split('.')[0], "%Y-%m-%d %H:%M:%S")
        # Add microseconds if present
        if '.' in timestamp_str:
            microseconds = int(timestamp_str.split('.')[1][:6].ljust(6, '0'))
            dt = dt.replace(microsecond=microseconds)
        return dt.timestamp()
    except Exception as e:
        print(f"Error parsing timestamp '{timestamp_str}': {e}")
        return 0.0


def analyze_market(gabagool_csv: str, market_csv: str, time_limit_minutes: float = 1.0):
    """Analyze gabagool's trades in the first minute of a market"""
    
    # Get market start time from market CSV
    market_start_time = None
    try:
        with open(market_csv, 'r') as f:
            reader = csv.DictReader(f)
            first_row = next(reader)
            market_start_time = parse_timestamp(first_row['timestamp'])
    except Exception as e:
        print(f"Error reading market CSV {market_csv}: {e}")
        return None
    
    if market_start_time is None or market_start_time == 0:
        print(f"Could not determine market start time for {market_csv}")
        return None
    
    cutoff_time = market_start_time + (time_limit_minutes * 60)
    
    # Analyze gabagool trades
    trades = []
    up_shares = 0.0
    down_shares = 0.0
    up_cost = 0.0
    down_cost = 0.0
    
    try:
        with open(gabagool_csv, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                trade_time = parse_timestamp(row['timestamp'])
                
                # Filter to time limit
                if trade_time > cutoff_time:
                    break
                
                outcome = row['outcome'].strip().upper()
                size = float(row['size'])
                cost = float(row['usdcSize'])
                price = float(row['price'])
                
                trades.append({
                    'time': trade_time,
                    'seconds_from_start': trade_time - market_start_time,
                    'side': outcome,
                    'size': size,
                    'cost': cost,
                    'price': price
                })
                
                if outcome == 'UP':
                    up_shares += size
                    up_cost += cost
                else:
                    down_shares += size
                    down_cost += cost
    except Exception as e:
        print(f"Error reading gabagool CSV {gabagool_csv}: {e}")
        return None
    
    if not trades:
        return None
    
    # Calculate intervals between trades
    intervals = []
    for i in range(1, len(trades)):
        interval = trades[i]['seconds_from_start'] - trades[i-1]['seconds_from_start']
        intervals.append(interval)
    
    # Calculate balance ratio over time
    total_shares = up_shares + down_shares
    up_ratio = up_shares / total_shares if total_shares > 0 else 0
    balance_ratio = abs(up_ratio - 0.5) * 2.0
    
    # Count trades per side
    up_trades = [t for t in trades if t['side'] == 'UP']
    down_trades = [t for t in trades if t['side'] == 'DOWN']
    
    return {
        'market_name': Path(gabagool_csv).stem.replace('_gabagool', ''),
        'total_trades': len(trades),
        'up_trades': len(up_trades),
        'down_trades': len(down_trades),
        'up_shares': up_shares,
        'down_shares': down_shares,
        'up_cost': up_cost,
        'down_cost': down_cost,
        'total_cost': up_cost + down_cost,
        'avg_cost_per_trade': (up_cost + down_cost) / len(trades) if trades else 0,
        'balance_ratio': balance_ratio,
        'up_ratio_pct': up_ratio * 100,
        'down_ratio_pct': (1 - up_ratio) * 100,
        'avg_up_price': up_cost / up_shares if up_shares > 0 else 0,
        'avg_down_price': down_cost / down_shares if down_shares > 0 else 0,
        'first_trade_seconds': trades[0]['seconds_from_start'],
        'last_trade_seconds': trades[-1]['seconds_from_start'],
        'min_interval': min(intervals) if intervals else 0,
        'max_interval': max(intervals) if intervals else 0,
        'avg_interval': sum(intervals) / len(intervals) if intervals else 0,
        'trades': trades
    }


def main():
    testing_data_dir = Path('testing_data')
    
    # Find all gabagool CSVs
    gabagool_files = sorted(testing_data_dir.glob('*_gabagool.csv'))
    
    print(f"Found {len(gabagool_files)} gabagool CSV files")
    print("\n" + "=" * 100)
    print("GABAGOOL FIRST MINUTE ANALYSIS")
    print("=" * 100)
    
    all_results = []
    
    for gabagool_csv in gabagool_files:
        # Find corresponding market CSV
        market_name = str(gabagool_csv.stem).replace('_gabagool', '_market')
        market_csv = gabagool_csv.parent / f"{market_name}.csv"
        
        if not market_csv.exists():
            print(f"\nSkipping {gabagool_csv.name} - market CSV not found")
            continue
        
        result = analyze_market(str(gabagool_csv), str(market_csv), time_limit_minutes=1.0)
        
        if result:
            all_results.append(result)
    
    if not all_results:
        print("\nNo valid results found")
        return
    
    # Print individual market results
    print("\n" + "=" * 100)
    print("INDIVIDUAL MARKET RESULTS (First Minute)")
    print("=" * 100)
    
    for result in all_results:
        print(f"\n{result['market_name']}")
        print("-" * 100)
        print(f"  Total Trades: {result['total_trades']} (UP: {result['up_trades']}, DOWN: {result['down_trades']})")
        print(f"  Total Cost: ${result['total_cost']:.2f} (Avg per trade: ${result['avg_cost_per_trade']:.2f})")
        print(f"  Balance: {result['balance_ratio']:.3f} (UP: {result['up_ratio_pct']:.1f}%, DOWN: {result['down_ratio_pct']:.1f}%)")
        print(f"  Avg Prices: UP ${result['avg_up_price']:.3f}, DOWN ${result['avg_down_price']:.3f}")
        print(f"  Timing: First trade @ {result['first_trade_seconds']:.1f}s, Last @ {result['last_trade_seconds']:.1f}s")
        print(f"  Intervals: Min {result['min_interval']:.2f}s, Max {result['max_interval']:.2f}s, Avg {result['avg_interval']:.2f}s")
    
    # Print aggregate statistics
    print("\n" + "=" * 100)
    print("AGGREGATE STATISTICS (Across All Markets)")
    print("=" * 100)
    
    total_trades = sum(r['total_trades'] for r in all_results)
    avg_trades_per_market = total_trades / len(all_results)
    
    avg_cost_per_market = sum(r['total_cost'] for r in all_results) / len(all_results)
    avg_cost_per_trade = sum(r['avg_cost_per_trade'] for r in all_results) / len(all_results)
    
    avg_balance_ratio = sum(r['balance_ratio'] for r in all_results) / len(all_results)
    
    all_intervals = []
    for r in all_results:
        for i in range(1, len(r['trades'])):
            interval = r['trades'][i]['seconds_from_start'] - r['trades'][i-1]['seconds_from_start']
            all_intervals.append(interval)
    
    print(f"\nMarkets Analyzed: {len(all_results)}")
    print(f"Total Trades: {total_trades}")
    print(f"Avg Trades per Market: {avg_trades_per_market:.1f}")
    print(f"Avg Cost per Market: ${avg_cost_per_market:.2f}")
    print(f"Avg Cost per Trade: ${avg_cost_per_trade:.2f}")
    print(f"Avg Balance Ratio: {avg_balance_ratio:.3f}")
    
    if all_intervals:
        print(f"\nTrade Intervals (all markets combined):")
        print(f"  Min: {min(all_intervals):.2f}s")
        print(f"  Max: {max(all_intervals):.2f}s")
        print(f"  Avg: {sum(all_intervals) / len(all_intervals):.2f}s")
        print(f"  Median: {sorted(all_intervals)[len(all_intervals)//2]:.2f}s")
    
    # Analyze side selection patterns
    print(f"\nSide Selection:")
    total_up_trades = sum(r['up_trades'] for r in all_results)
    total_down_trades = sum(r['down_trades'] for r in all_results)
    print(f"  Total UP trades: {total_up_trades} ({total_up_trades/total_trades*100:.1f}%)")
    print(f"  Total DOWN trades: {total_down_trades} ({total_down_trades/total_trades*100:.1f}%)")


if __name__ == '__main__':
    main()

