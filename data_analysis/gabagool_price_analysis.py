#!/usr/bin/env python3
"""
Analyze gabagool's trade prices in the first minute.
Compare to market ask prices to detect limit orders.
"""

import csv
from datetime import datetime
from pathlib import Path


def parse_timestamp(timestamp_str: str) -> float:
    """Parse ISO timestamp to Unix timestamp"""
    try:
        try:
            return float(timestamp_str)
        except ValueError:
            pass
        
        if 'T' in timestamp_str:
            from datetime import timezone
            
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
        
        dt = datetime.strptime(timestamp_str.split('.')[0], "%Y-%m-%d %H:%M:%S")
        if '.' in timestamp_str:
            microseconds = int(timestamp_str.split('.')[1][:6].ljust(6, '0'))
            dt = dt.replace(microsecond=microseconds)
        return dt.timestamp()
    except Exception as e:
        return 0.0


def analyze_11pm_market():
    """Detailed analysis of the 11pm market"""
    
    gabagool_csv = 'testing_data/btc-15m_11-00pm_11-15pm_1765857600_gabagool.csv'
    market_csv = 'testing_data/btc-15m_11-00pm_11-15pm_1765857600_market.csv'
    
    # Get market start time
    market_start_time = None
    with open(market_csv, 'r') as f:
        reader = csv.DictReader(f)
        first_row = next(reader)
        market_start_time = parse_timestamp(first_row['timestamp'])
    
    cutoff_time = market_start_time + 60  # First minute
    
    # Load gabagool trades
    trades = []
    with open(gabagool_csv, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            trade_time = parse_timestamp(row['timestamp'])
            
            if trade_time > cutoff_time:
                break
            
            trades.append({
                'time': trade_time,
                'seconds': trade_time - market_start_time,
                'side': row['outcome'].strip().upper(),
                'size': float(row['size']),
                'cost': float(row['usdcSize']),
                'price': float(row['price'])
            })
    
    print("=" * 100)
    print("GABAGOOL TRADE-BY-TRADE ANALYSIS - 11PM MARKET (First Minute)")
    print("=" * 100)
    print(f"\nTotal Trades: {len(trades)}")
    
    # Group by time (to detect bursts)
    from collections import defaultdict
    by_second = defaultdict(list)
    for t in trades:
        by_second[int(t['seconds'])].append(t)
    
    print(f"\nTrades grouped by second:")
    print(f"  Seconds with trades: {len(by_second)}")
    print(f"  Avg trades per active second: {len(trades) / len(by_second):.1f}")
    
    burst_seconds = [s for s, trades_list in by_second.items() if len(trades_list) > 1]
    print(f"  Seconds with multiple trades (bursts): {len(burst_seconds)}")
    if burst_seconds:
        max_burst = max(len(by_second[s]) for s in burst_seconds)
        print(f"  Max trades in one second: {max_burst}")
    
    # Analyze price distribution
    up_prices = [t['price'] for t in trades if t['side'] == 'UP']
    down_prices = [t['price'] for t in trades if t['side'] == 'DOWN']
    
    print(f"\nPrice Analysis:")
    if up_prices:
        print(f"  UP trades: {len(up_prices)}")
        print(f"    Min: ${min(up_prices):.3f} ({min(up_prices)*100:.1f} cents)")
        print(f"    Max: ${max(up_prices):.3f} ({max(up_prices)*100:.1f} cents)")
        print(f"    Avg: ${sum(up_prices)/len(up_prices):.3f} ({sum(up_prices)/len(up_prices)*100:.1f} cents)")
        print(f"    Median: ${sorted(up_prices)[len(up_prices)//2]:.3f}")
    
    if down_prices:
        print(f"  DOWN trades: {len(down_prices)}")
        print(f"    Min: ${min(down_prices):.3f} ({min(down_prices)*100:.1f} cents)")
        print(f"    Max: ${max(down_prices):.3f} ({max(down_prices)*100:.1f} cents)")
        print(f"    Avg: ${sum(down_prices)/len(down_prices):.3f} ({sum(down_prices)/len(down_prices)*100:.1f} cents)")
        print(f"    Median: ${sorted(down_prices)[len(down_prices)//2]:.3f}")
    
    # Analyze costs
    up_costs = [t['cost'] for t in trades if t['side'] == 'UP']
    down_costs = [t['cost'] for t in trades if t['side'] == 'DOWN']
    
    print(f"\nCost per Trade:")
    if up_costs:
        print(f"  UP trades:")
        print(f"    Min: ${min(up_costs):.2f}")
        print(f"    Max: ${max(up_costs):.2f}")
        print(f"    Avg: ${sum(up_costs)/len(up_costs):.2f}")
    
    if down_costs:
        print(f"  DOWN trades:")
        print(f"    Min: ${min(down_costs):.2f}")
        print(f"    Max: ${max(down_costs):.2f}")
        print(f"    Avg: ${sum(down_costs)/len(down_costs):.2f}")
    
    # Show first 20 trades
    print(f"\nFirst 20 Trades:")
    print(f"{'Time':>8} {'Side':>5} {'Price':>8} {'Size':>10} {'Cost':>8}")
    print("-" * 50)
    for i, t in enumerate(trades[:20]):
        print(f"{t['seconds']:7.1f}s {t['side']:>5} ${t['price']:6.3f} {t['size']:10.2f} ${t['cost']:7.2f}")
    
    # Running balance
    print(f"\nRunning Balance (every 10 trades):")
    print(f"{'Trade#':>8} {'UP Shares':>12} {'DOWN Shares':>12} {'Balance':>10}")
    print("-" * 50)
    
    up_shares = 0.0
    down_shares = 0.0
    for i, t in enumerate(trades):
        if t['side'] == 'UP':
            up_shares += t['size']
        else:
            down_shares += t['size']
        
        if (i + 1) % 10 == 0 or i == len(trades) - 1:
            total = up_shares + down_shares
            up_ratio = up_shares / total if total > 0 else 0
            balance_ratio = abs(up_ratio - 0.5) * 2.0
            print(f"{i+1:8d} {up_shares:12.2f} {down_shares:12.2f} {balance_ratio:10.3f}")


if __name__ == '__main__':
    analyze_11pm_market()

