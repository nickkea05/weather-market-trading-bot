#!/usr/bin/env python3
"""
Analyze gabagool's risk management strategy.

Key questions:
1. How does gabagool keep worst-case profit from going deeply negative?
2. What's their typical combined average throughout the market?
3. How do they respond when min profit goes negative?
4. Do they trade differently early vs late in the market?
5. What's their rebalancing pattern?
"""

import pandas as pd
import glob
from pathlib import Path

def analyze_gabagool_trades(csv_path):
    """Analyze a single market's gabagool trades for risk management insights."""
    df = pd.read_csv(csv_path)
    market_name = Path(csv_path).stem.replace('_gabagool', '')
    
    print(f"\n{'='*80}")
    print(f"Market: {market_name}")
    print(f"{'='*80}")
    
    # Initialize position tracking
    up_shares = 0.0
    down_shares = 0.0
    up_cost = 0.0
    down_cost = 0.0
    
    trades = []
    min_profits = []
    max_profits = []
    avg_profits = []
    combined_avgs = []
    balance_ratios = []
    
    # Also track max imbalance seen during market
    max_balance_ratio = 0.0
    
    for idx, row in df.iterrows():
        side = row['outcome']
        price = row['price']
        shares = row['size']
        amount = price * shares
        
        # Update position
        if side == 'Yes':
            up_shares += shares
            up_cost += amount
        else:
            down_shares += shares
            down_cost += amount
        
        # Calculate metrics
        total_shares = up_shares + down_shares
        if total_shares > 0:
            balance_ratio = abs(up_shares - down_shares) / total_shares
            max_balance_ratio = max(max_balance_ratio, balance_ratio)
        else:
            balance_ratio = 0.0
        
        profit_if_up = up_shares - up_cost
        profit_if_down = down_shares - down_cost
        min_profit = min(profit_if_up, profit_if_down)
        max_profit = max(profit_if_up, profit_if_down)
        avg_profit = (profit_if_up + profit_if_down) / 2.0
        spread = max_profit - min_profit
        
        avg_up = up_cost / up_shares if up_shares > 0 else 0.0
        avg_down = down_cost / down_shares if down_shares > 0 else 0.0
        combined_avg = avg_up + avg_down
        
        trades.append({
            'trade_num': idx + 1,
            'side': side,
            'price': price,
            'shares': shares,
            'amount': amount,
            'up_shares': up_shares,
            'down_shares': down_shares,
            'balance_ratio': balance_ratio,
            'min_profit': min_profit,
            'max_profit': max_profit,
            'avg_profit': avg_profit,
            'spread': spread,
            'combined_avg': combined_avg
        })
        
        min_profits.append(min_profit)
        max_profits.append(max_profit)
        avg_profits.append(avg_profit)
        combined_avgs.append(combined_avg)
        balance_ratios.append(balance_ratio)
    
    trades_df = pd.DataFrame(trades)
    
    # Key insights
    print(f"\nTotal trades: {len(trades)}")
    print(f"Max balance ratio during market: {max_balance_ratio:.4f} ({max_balance_ratio*100:.1f}%)")
    print(f"Final min profit: ${min_profit:.4f}")
    print(f"Final max profit: ${max_profit:.4f}")
    print(f"Final avg profit: ${avg_profit:.4f}")
    print(f"Final spread: ${spread:.4f}")
    print(f"Final combined avg: ${combined_avg:.4f}")
    
    # How often does min profit go negative?
    negative_count = sum(1 for mp in min_profits if mp < 0)
    print(f"\nMin profit went negative: {negative_count}/{len(trades)} times ({100*negative_count/len(trades):.1f}%)")
    
    if negative_count > 0:
        min_negative = min(min_profits)
        print(f"Deepest negative min profit: ${min_negative:.4f}")
        
        # When min profit was negative, was avg profit still positive?
        negative_trades_df = trades_df[trades_df['min_profit'] < 0]
        avg_of_negatives = negative_trades_df['avg_profit'].mean()
        positive_avg_count = sum(1 for ap in negative_trades_df['avg_profit'] if ap > 0)
        print(f"When min profit was negative, avg profit was positive: {positive_avg_count}/{len(negative_trades_df)} times")
        print(f"Average profit during negative min periods: ${avg_of_negatives:.4f}")
        
        # Find when it went negative
        first_negative = next((i for i, mp in enumerate(min_profits) if mp < 0), None)
        if first_negative:
            print(f"First went negative at trade #{first_negative + 1}")
    
    # Combined average stats
    print(f"\nCombined average stats:")
    print(f"  Min: ${min(combined_avgs):.4f}")
    print(f"  Max: ${max(combined_avgs):.4f}")
    print(f"  Mean: ${sum(combined_avgs)/len(combined_avgs):.4f}")
    print(f"  Final: ${combined_avgs[-1]:.4f}")
    
    # How often exceeds 1.02?
    over_102 = sum(1 for ca in combined_avgs if ca >= 1.02)
    print(f"  Times >= 1.02: {over_102}/{len(trades)} ({100*over_102/len(trades):.1f}%)")
    
    # Balance ratio stats
    print(f"\nBalance ratio stats:")
    print(f"  Min: {min(balance_ratios):.4f}")
    print(f"  Max: {max(balance_ratios):.4f}")
    print(f"  Mean: {sum(balance_ratios)/len(balance_ratios):.4f}")
    print(f"  Final: {balance_ratios[-1]:.4f}")
    
    # Relationship between balance ratio and spread
    # Split into high balance (imbalanced) vs low balance (balanced) periods
    if len(trades_df) > 10:
        high_balance_trades = trades_df[trades_df['balance_ratio'] > 0.20]
        low_balance_trades = trades_df[trades_df['balance_ratio'] < 0.10]
        
        if len(high_balance_trades) > 0 and len(low_balance_trades) > 0:
            print(f"\nBalance ratio vs Spread analysis:")
            print(f"  When balanced (<10% ratio): avg spread ${low_balance_trades['spread'].mean():.4f}")
            print(f"  When imbalanced (>20% ratio): avg spread ${high_balance_trades['spread'].mean():.4f}")
            print(f"  → Tighter spread when imbalanced? {high_balance_trades['spread'].mean() < low_balance_trades['spread'].mean()}")
    
    # Rebalancing behavior when min profit is negative
    if negative_count > 0:
        print(f"\nRebalancing behavior when min profit < 0:")
        negative_trades = trades_df[trades_df['min_profit'] < 0]
        
        # Show first few examples
        for idx, trade in negative_trades.head(5).iterrows():
            prev_balance = trades_df.iloc[idx-1]['balance_ratio'] if idx > 0 else 0
            prev_spread = trades_df.iloc[idx-1]['spread'] if idx > 0 else 0
            print(f"  Trade #{trade['trade_num']}: bought {trade['side']} at ${trade['price']:.4f}")
            print(f"    min=${trade['min_profit']:.4f}, avg=${trade['avg_profit']:.4f}, spread=${trade['spread']:.4f} (was ${prev_spread:.4f})")
            print(f"    balance={trade['balance_ratio']:.4f} (was {prev_balance:.4f})")
    
    # Early vs late market analysis
    if len(trades_df) > 30:
        early_trades = trades_df[trades_df.index < len(trades) // 3]
        late_trades = trades_df[trades_df.index >= 2 * len(trades) // 3]
        
        print(f"\nEarly market (first 1/3) vs Late market (last 1/3):")
        print(f"  Early avg spread: ${early_trades['spread'].mean():.4f}")
        print(f"  Late avg spread: ${late_trades['spread'].mean():.4f}")
        print(f"  Early avg balance ratio: {early_trades['balance_ratio'].mean():.4f}")
        print(f"  Late avg balance ratio: {late_trades['balance_ratio'].mean():.4f}")
    
    return trades_df


def main():
    """Analyze all available gabagool trades."""
    gabagool_files = sorted(glob.glob('testing_data/*_gabagool.csv'))
    
    print(f"Found {len(gabagool_files)} gabagool trade files")
    
    all_analyses = []
    for csv_path in gabagool_files:
        try:
            trades_df = analyze_gabagool_trades(csv_path)
            all_analyses.append(trades_df)
        except Exception as e:
            print(f"Error analyzing {csv_path}: {e}")
    
    # Overall summary
    print(f"\n{'='*80}")
    print("OVERALL SUMMARY")
    print(f"{'='*80}")
    
    total_markets = len(all_analyses)
    print(f"Analyzed {total_markets} markets")
    
    if total_markets == 0:
        print("No markets analyzed successfully.")
        return
    
    # Count how many markets had negative min profit
    markets_with_negative = sum(1 for df in all_analyses if (df['min_profit'] < 0).any())
    print(f"\nMarkets where min profit went negative: {markets_with_negative}/{total_markets}")
    
    # Average final metrics across all markets
    final_min_profits = [df.iloc[-1]['min_profit'] for df in all_analyses]
    final_combined_avgs = [df.iloc[-1]['combined_avg'] for df in all_analyses]
    
    print(f"\nFinal min profit across markets:")
    print(f"  Mean: ${sum(final_min_profits)/len(final_min_profits):.4f}")
    print(f"  Min: ${min(final_min_profits):.4f}")
    print(f"  Max: ${max(final_min_profits):.4f}")
    
    print(f"\nFinal combined avg across markets:")
    print(f"  Mean: ${sum(final_combined_avgs)/len(final_combined_avgs):.4f}")
    print(f"  Min: ${min(final_combined_avgs):.4f}")
    print(f"  Max: ${max(final_combined_avgs):.4f}")
    
    # Collect all max balance ratios
    print(f"\n" + "="*80)
    print("KEY INSIGHTS:")
    print("="*80)
    print("1. Gabagool IS an arbitrage trader (holds both sides)")
    print("2. Focus on AVG PROFIT, not just worst-case")
    print("3. In volatile markets (high balance), gabagool keeps TIGHTER spreads")
    print("4. This is opposite of what we're doing with staggered limits!")
    print("="*80)


if __name__ == '__main__':
    main()

