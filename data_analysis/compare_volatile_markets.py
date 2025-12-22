#!/usr/bin/env python3
"""
Analyze how gabagool handles volatile markets (2 & 3) vs our bot.
Focus on understanding how they keep tight spreads.
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


def analyze_market(market_name: str, gabagool_csv: str, market_csv: str):
    """Detailed analysis of a single market"""
    
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
    print(f"{market_name} - GABAGOOL ANALYSIS")
    print("=" * 120)
    
    # Simulate position
    up_shares = 0.0
    down_shares = 0.0
    up_cost = 0.0
    down_cost = 0.0
    
    min_profit_history = []
    combined_avg_history = []
    times_violated_1_dollar = 0
    times_went_negative = 0
    max_negative = 0
    
    for i, trade in enumerate(trades):
        if trade['side'] == 'UP':
            up_shares += trade['size']
            up_cost += trade['cost']
        else:
            down_shares += trade['size']
            down_cost += trade['cost']
        
        # Calculate metrics
        avg_up = up_cost / up_shares if up_shares > 0 else 0
        avg_down = down_cost / down_shares if down_shares > 0 else 0
        combined_avg = avg_up + avg_down
        
        profit_if_up = up_shares * 1.0 - (up_cost + down_cost)
        profit_if_down = down_shares * 1.0 - (up_cost + down_cost)
        min_profit = min(profit_if_up, profit_if_down)
        
        min_profit_history.append(min_profit)
        combined_avg_history.append(combined_avg)
        
        if combined_avg >= 1.0:
            times_violated_1_dollar += 1
        
        if min_profit < 0:
            times_went_negative += 1
            max_negative = min(max_negative, min_profit)
    
    print(f"\nKey Metrics:")
    print(f"  Total Trades: {len(trades)}")
    print(f"  Final Min Profit: ${min_profit_history[-1]:.2f}")
    print(f"  Final Combined Avg: ${combined_avg_history[-1]:.3f}")
    print(f"  Times Combined Avg >= $1.00: {times_violated_1_dollar} ({times_violated_1_dollar/len(trades)*100:.1f}%)")
    print(f"  Times Min Profit < $0: {times_went_negative} ({times_went_negative/len(trades)*100:.1f}%)")
    print(f"  Max Negative Min Profit: ${max_negative:.2f}")
    
    # Analyze rebalancing speed
    imbalance_events = []
    for i, trade in enumerate(trades):
        # Calculate balance after this trade
        up_s = sum(t['size'] for t in trades[:i+1] if t['side'] == 'UP')
        down_s = sum(t['size'] for t in trades[:i+1] if t['side'] == 'DOWN')
        total = up_s + down_s
        balance_ratio = abs((up_s/total) - 0.5) * 2.0 if total > 0 else 0
        
        if balance_ratio > 0.15 and i+1 < len(trades):
            # Significantly imbalanced - what does next trade do?
            next_trade = trades[i+1]
            minority_side = 'UP' if up_s < down_s else 'DOWN'
            rebalances = next_trade['side'] == minority_side
            imbalance_events.append({
                'trade': i+1,
                'balance': balance_ratio,
                'rebalances': rebalances,
                'next_side': next_trade['side']
            })
    
    print(f"\nImbalance Events (>15%):")
    print(f"  Total events: {len(imbalance_events)}")
    rebalanced = sum(1 for e in imbalance_events if e['rebalances'])
    print(f"  Times rebalanced immediately: {rebalanced} ({rebalanced/len(imbalance_events)*100:.1f}% if >0 events)")
    
    # Show some examples
    if imbalance_events:
        print(f"\n  Examples:")
        for event in imbalance_events[:5]:
            action = "REBALANCED" if event['rebalances'] else "DID NOT rebalance"
            print(f"    Trade #{event['trade']}: {event['balance']:.3f} imbalanced -> {action} (bought {event['next_side']})")
    
    print()


def main():
    print("\n" + "=" * 120)
    print("VOLATILE MARKETS ANALYSIS - How Does Gabagool Keep Tight Spreads?")
    print("=" * 120)
    
    # Market 2: 10:15pm
    analyze_market(
        "MARKET 2 (10:15pm)",
        'testing_data/btc-15m_10-15pm_10-30pm_1765854900_gabagool.csv',
        'testing_data/btc-15m_10-15pm_10-30pm_1765854900_market.csv'
    )
    
    # Market 3: 8:00pm
    analyze_market(
        "MARKET 3 (8:00pm)",
        'testing_data/btc-15m_8-00pm_8-15pm_1765846800_gabagool.csv',
        'testing_data/btc-15m_8-00pm_8-15pm_1765846800_market.csv'
    )


if __name__ == '__main__':
    main()

