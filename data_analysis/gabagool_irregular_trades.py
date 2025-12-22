"""
Analyze Gabagool's trades to find irregular/defensive trades.
Looking for trades that:
- Don't improve min profit
- Aren't buying the cheapest side
- Seem to be defensive positioning
"""

import pandas as pd
import sys

def calculate_position_metrics(trades):
    """Calculate running position metrics for each trade."""
    metrics = []
    
    up_shares = 0
    down_shares = 0
    up_cost = 0
    down_cost = 0
    
    for idx, trade in trades.iterrows():
        side = trade['side']
        price = trade['price']
        cost = trade['usdcSize']
        shares = trade['size']
        
        # Update position
        if side == 'UP':
            up_shares += shares
            up_cost += cost
        else:
            down_shares += shares
            down_cost += cost
        
        # Calculate metrics
        total_shares = up_shares + down_shares
        balance_ratio = abs(up_shares - down_shares) / total_shares if total_shares > 0 else 0
        
        up_avg = up_cost / up_shares if up_shares > 0 else 0
        down_avg = down_cost / down_shares if down_shares > 0 else 0
        combined_avg = up_avg + down_avg
        
        # Min profit (worst case)
        if up_shares > 0 and down_shares > 0:
            up_profit = down_shares - up_cost  # If UP wins
            down_profit = up_shares - down_cost  # If DOWN wins
            min_profit = min(up_profit, down_profit)
        else:
            min_profit = -max(up_cost, down_cost)
        
        metrics.append({
            'trade_num': idx + 1,
            'side': side,
            'price': price,
            'cost': cost,
            'shares': shares,
            'up_shares': up_shares,
            'down_shares': down_shares,
            'up_avg': up_avg,
            'down_avg': down_avg,
            'combined_avg': combined_avg,
            'balance_ratio': balance_ratio,
            'min_profit': min_profit,
            'total_cost': up_cost + down_cost
        })
    
    return pd.DataFrame(metrics)

def find_irregular_trades(metrics_df):
    """Find trades that seem irregular or defensive."""
    irregular = []
    
    for i in range(1, len(metrics_df)):
        prev = metrics_df.iloc[i-1]
        curr = metrics_df.iloc[i]
        
        # Calculate what was cheap at this moment
        # We need to look at the previous trade to see what the market looked like
        
        # Check for irregular patterns:
        
        # 1. Trade worsens min profit significantly (more than $5)
        min_profit_delta = curr['min_profit'] - prev['min_profit']
        if min_profit_delta < -5:
            irregular.append({
                'trade_num': int(curr['trade_num']),
                'type': 'WORSEN_MIN_PROFIT',
                'side': curr['side'],
                'price': curr['price'],
                'cost': curr['cost'],
                'min_profit_delta': min_profit_delta,
                'prev_min_profit': prev['min_profit'],
                'new_min_profit': curr['min_profit'],
                'balance_ratio': curr['balance_ratio'],
                'combined_avg': curr['combined_avg'],
                'reason': f"Worsened min profit by ${abs(min_profit_delta):.2f}"
            })
        
        # 2. Buying the majority side when already imbalanced (balance_ratio > 0.15)
        if curr['balance_ratio'] > prev['balance_ratio'] and prev['balance_ratio'] > 0.15:
            irregular.append({
                'trade_num': int(curr['trade_num']),
                'type': 'BUY_MAJORITY_SIDE',
                'side': curr['side'],
                'price': curr['price'],
                'cost': curr['cost'],
                'min_profit_delta': min_profit_delta,
                'prev_balance': prev['balance_ratio'],
                'new_balance': curr['balance_ratio'],
                'combined_avg': curr['combined_avg'],
                'reason': f"Bought majority side, increased imbalance from {prev['balance_ratio']:.3f} to {curr['balance_ratio']:.3f}"
            })
        
        # 3. Very small trades (< $1.50) - might be defensive positioning
        if curr['cost'] < 1.5:
            irregular.append({
                'trade_num': int(curr['trade_num']),
                'type': 'SMALL_TRADE',
                'side': curr['side'],
                'price': curr['price'],
                'cost': curr['cost'],
                'min_profit_delta': min_profit_delta,
                'balance_ratio': curr['balance_ratio'],
                'combined_avg': curr['combined_avg'],
                'reason': f"Very small trade (${curr['cost']:.2f})"
            })
    
    return pd.DataFrame(irregular)

def main():
    if len(sys.argv) < 2:
        print("Usage: python gabagool_irregular_trades.py <gabagool_csv>")
        return
    
    gabagool_file = sys.argv[1]
    
    # Load Gabagool trades
    trades_df = pd.read_csv(gabagool_file)
    print(f"Loaded {len(trades_df)} Gabagool trades")
    
    # Calculate metrics
    metrics_df = calculate_position_metrics(trades_df)
    
    # Find irregular trades
    irregular_df = find_irregular_trades(metrics_df)
    
    print(f"\n{'='*100}")
    print(f"FOUND {len(irregular_df)} IRREGULAR TRADES")
    print(f"{'='*100}\n")
    
    # Group by type
    for trade_type in irregular_df['type'].unique():
        type_trades = irregular_df[irregular_df['type'] == trade_type]
        print(f"\n{trade_type}: {len(type_trades)} trades")
        print("-" * 100)
        for _, trade in type_trades.iterrows():
            print(f"Trade #{trade['trade_num']:3d} | {trade['side']:4s} ${trade['price']:.2f} x ${trade['cost']:.2f}")
            print(f"              {trade['reason']}")
            if 'min_profit_delta' in trade:
                print(f"              MinProfit: {trade.get('prev_min_profit', 'N/A'):.2f} -> {trade.get('new_min_profit', trade.get('min_profit_delta', 'N/A')):.2f}")
            print(f"              Balance: {trade['balance_ratio']:.3f} | CombinedAvg: {trade['combined_avg']:.3f}")
            print()
    
    # Show detailed metrics for all trades to help find patterns
    print(f"\n{'='*100}")
    print("DETAILED METRICS FOR ALL TRADES")
    print(f"{'='*100}\n")
    print(metrics_df.to_string())

if __name__ == "__main__":
    main()

