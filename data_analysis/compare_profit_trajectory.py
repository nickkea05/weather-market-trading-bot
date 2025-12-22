#!/usr/bin/env python3
"""
Compare profit trajectory between our bot and gabagool.
Analyze WHEN and WHY gabagool stays positive on both sides.
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


def analyze_gabagool_strategy():
    """Analyze gabagool's trading strategy in detail"""
    
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
    
    print("=" * 120)
    print("GABAGOOL STRATEGY ANALYSIS - 11PM MARKET (First Minute)")
    print("=" * 120)
    
    # Simulate position
    up_shares = 0.0
    down_shares = 0.0
    up_cost = 0.0
    down_cost = 0.0
    
    consecutive_up = 0
    consecutive_down = 0
    max_consecutive_up = 0
    max_consecutive_down = 0
    
    switches = []  # Track when gabagool switches sides
    profit_positive_trades = []  # Track when min profit becomes positive
    
    print(f"\nTrade-by-Trade Analysis:")
    print("-" * 120)
    
    for i, trade in enumerate(trades):
        prev_up_shares = up_shares
        prev_down_shares = down_shares
        
        if trade['side'] == 'UP':
            up_shares += trade['size']
            up_cost += trade['cost']
            consecutive_up += 1
            if consecutive_down > 0:
                switches.append({'trade': i+1, 'from': 'DOWN', 'to': 'UP', 'consecutive': consecutive_down})
            consecutive_down = 0
            max_consecutive_up = max(max_consecutive_up, consecutive_up)
        else:
            down_shares += trade['size']
            down_cost += trade['cost']
            consecutive_down += 1
            if consecutive_up > 0:
                switches.append({'trade': i+1, 'from': 'UP', 'to': 'DOWN', 'consecutive': consecutive_up})
            consecutive_up = 0
            max_consecutive_down = max(max_consecutive_down, consecutive_down)
        
        # Calculate metrics
        avg_up = up_cost / up_shares if up_shares > 0 else 0
        avg_down = down_cost / down_shares if down_shares > 0 else 0
        
        profit_if_up = up_shares * 1.0 - (up_cost + down_cost)
        profit_if_down = down_shares * 1.0 - (up_cost + down_cost)
        min_profit = min(profit_if_up, profit_if_down)
        
        total_shares = up_shares + down_shares
        up_ratio = up_shares / total_shares if total_shares > 0 else 0
        balance_ratio = abs(up_ratio - 0.5) * 2.0
        
        # Track when min profit becomes positive
        if min_profit > 0 and (not profit_positive_trades or profit_positive_trades[-1] != i+1):
            profit_positive_trades.append(i+1)
        
        # Print every 5 trades for readability
        if (i+1) % 5 == 0 or i < 10 or min_profit > 0:
            side_indicator = f"{trade['side']:>4}"
            print(f"Trade #{i+1:2d}: {side_indicator} ${trade['price']:.3f} | UP {up_shares:6.1f}@${avg_up:.3f} DOWN {down_shares:6.1f}@${avg_down:.3f} | MinProfit: ${min_profit:7.2f} | Bal: {balance_ratio:.3f}")
    
    print("\n" + "=" * 120)
    print("KEY INSIGHTS")
    print("=" * 120)
    
    print(f"\n1. CONSECUTIVE TRADES:")
    print(f"   - Max consecutive UP trades: {max_consecutive_up}")
    print(f"   - Max consecutive DOWN trades: {max_consecutive_down}")
    print(f"   - Total switches between sides: {len(switches)}")
    
    if switches:
        print(f"\n   Side switches:")
        for switch in switches[:10]:  # Show first 10
            print(f"      Trade #{switch['trade']}: {switch['from']} -> {switch['to']} (after {switch['consecutive']} {switch['from']} trades)")
    
    print(f"\n2. PROFIT TRAJECTORY:")
    if profit_positive_trades:
        print(f"   - Min profit became positive at trade #{profit_positive_trades[0]}")
        print(f"   - Times it went positive: {len(profit_positive_trades)}")
    else:
        print(f"   - Min profit NEVER became positive in first minute")
    
    # Analyze price patterns
    up_prices = [t['price'] for t in trades if t['side'] == 'UP']
    down_prices = [t['price'] for t in trades if t['side'] == 'DOWN']
    
    print(f"\n3. PRICE PATTERNS:")
    print(f"   UP trades:")
    print(f"      - Count: {len(up_prices)}")
    print(f"      - Below $0.50: {len([p for p in up_prices if p < 0.50])} ({len([p for p in up_prices if p < 0.50])/len(up_prices)*100:.1f}%)")
    print(f"      - $0.50-$0.55: {len([p for p in up_prices if 0.50 <= p < 0.55])}")
    print(f"      - Above $0.55: {len([p for p in up_prices if p >= 0.55])}")
    
    print(f"   DOWN trades:")
    print(f"      - Count: {len(down_prices)}")
    print(f"      - Below $0.45: {len([p for p in down_prices if p < 0.45])} ({len([p for p in down_prices if p < 0.45])/len(down_prices)*100:.1f}%)")
    print(f"      - $0.45-$0.50: {len([p for p in down_prices if 0.45 <= p < 0.50])}")
    print(f"      - Above $0.50: {len([p for p in down_prices if p >= 0.50])}")
    
    # Analyze when balance matters
    print(f"\n4. BALANCE STRATEGY:")
    imbalanced_trades = [(i+1, t) for i, t in enumerate(trades)]
    
    # Calculate balance at each trade
    up_s = 0.0
    down_s = 0.0
    for i, trade in enumerate(trades):
        if trade['side'] == 'UP':
            up_s += trade['size']
        else:
            down_s += trade['size']
        
        total = up_s + down_s
        ratio = abs((up_s/total) - 0.5) * 2.0 if total > 0 else 0
        
        if ratio > 0.15:  # Significantly imbalanced
            next_trade = trades[i+1] if i+1 < len(trades) else None
            if next_trade:
                minority_side = 'UP' if up_s < down_s else 'DOWN'
                does_rebalance = next_trade['side'] == minority_side
                if not does_rebalance and i+1 <= 20:
                    print(f"   Trade #{i+1}: Imbalanced {ratio:.3f} but next trade is {next_trade['side']} (NOT rebalancing)")


if __name__ == '__main__':
    analyze_gabagool_strategy()

