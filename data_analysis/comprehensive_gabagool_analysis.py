#!/usr/bin/env python3
"""
COMPREHENSIVE GABAGOOL ANALYSIS

Goal: Understand EXACTLY how gabagool creates profit.
Key mystery: We're barely negative, they're barely positive. What's the difference?

Analysis includes:
1. Trade patterns: UP vs DOWN counts, timing, clustering
2. Position management: When do they worsen position vs rebalance?
3. Price patterns: What prices do they buy at? Relationship to market?
4. Spread analysis: How does spread evolve? When do they tighten/loosen?
5. Negative periods: How long in negative? How do they escape?
6. Risk-taking: When do they increase imbalance vs balance?
7. Outcome prediction: Do their trades favor the actual winner?
"""

import pandas as pd
import numpy as np
import glob
from pathlib import Path

def comprehensive_analysis(gabagool_csv, market_csv):
    """Deep dive into a single market."""
    
    # Load data
    gaba_df = pd.read_csv(gabagool_csv)
    market_df = pd.read_csv(market_csv)
    
    market_name = Path(gabagool_csv).stem.replace('_gabagool', '')
    
    print(f"\n{'='*80}")
    print(f"MARKET: {market_name}")
    print(f"{'='*80}")
    
    # Determine actual winner from market data
    final_row = market_df.iloc[-1]
    winner = 'UP' if final_row['up_best_ask'] > final_row['down_best_ask'] else 'DOWN'
    print(f"ACTUAL WINNER: {winner}")
    print(f"Final prices: UP=${final_row['up_best_ask']:.4f}, DOWN=${final_row['down_best_ask']:.4f}")
    
    # Track position through all trades
    up_shares = 0.0
    down_shares = 0.0
    up_cost = 0.0
    down_cost = 0.0
    
    trades = []
    
    for idx, row in gaba_df.iterrows():
        side = row['outcome'].upper()  # Already 'Up' or 'Down' in CSV
        price = row['price']
        shares = row['size']
        amount = row['usdcSize']
        
        # Store previous state
        prev_up_shares = up_shares
        prev_down_shares = down_shares
        prev_up_cost = up_cost
        prev_down_cost = down_cost
        
        # Update position
        if side == 'UP':
            up_shares += shares
            up_cost += amount
        else:
            down_shares += shares
            down_cost += amount
        
        # Calculate metrics
        total_shares = up_shares + down_shares
        balance_ratio = abs(up_shares - down_shares) / total_shares if total_shares > 0 else 0.0
        
        profit_if_up = up_shares - up_cost
        profit_if_down = down_shares - down_cost
        min_profit = min(profit_if_up, profit_if_down)
        max_profit = max(profit_if_up, profit_if_down)
        spread = max_profit - min_profit
        
        # Previous metrics
        prev_total = prev_up_shares + prev_down_shares
        prev_balance_ratio = abs(prev_up_shares - prev_down_shares) / prev_total if prev_total > 0 else 0.0
        prev_profit_up = prev_up_shares - prev_up_cost
        prev_profit_down = prev_down_shares - prev_down_cost
        prev_min = min(prev_profit_up, prev_profit_down) if prev_total > 0 else 0
        prev_spread = max(prev_profit_up, prev_profit_down) - prev_min if prev_total > 0 else 0
        
        # Determine trade type
        minority_side = 'UP' if up_shares < down_shares else 'DOWN'
        is_rebalancing = (side == minority_side and total_shares > 0)
        
        # Did this trade improve or worsen position?
        improved_min = min_profit > prev_min
        reduced_spread = spread < prev_spread
        reduced_imbalance = balance_ratio < prev_balance_ratio
        
        # Is this buying the side that will win?
        buying_winner = (side == winner)
        
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
            'spread': spread,
            'is_rebalancing': is_rebalancing,
            'improved_min': improved_min,
            'reduced_spread': reduced_spread,
            'reduced_imbalance': reduced_imbalance,
            'buying_winner': buying_winner,
            'prev_min': prev_min,
            'prev_spread': prev_spread,
            'prev_balance': prev_balance_ratio
        })
    
    trades_df = pd.DataFrame(trades)
    
    # ========================================================================
    # SECTION 1: TRADE PATTERNS
    # ========================================================================
    print(f"\n{'-'*80}")
    print("1. TRADE PATTERNS")
    print(f"{'-'*80}")
    
    up_trades = trades_df[trades_df['side'] == 'UP']
    down_trades = trades_df[trades_df['side'] == 'DOWN']
    
    print(f"Total trades: {len(trades_df)}")
    print(f"UP trades: {len(up_trades)} ({100*len(up_trades)/len(trades_df):.1f}%)")
    print(f"DOWN trades: {len(down_trades)} ({100*len(down_trades)/len(trades_df):.1f}%)")
    print(f"Bought winner side: {len(trades_df[trades_df['buying_winner']])} times ({100*len(trades_df[trades_df['buying_winner']])/len(trades_df):.1f}%)")
    
    # Price ranges
    print(f"\nPrice ranges:")
    print(f"  UP:   ${up_trades['price'].min():.4f} - ${up_trades['price'].max():.4f} (avg: ${up_trades['price'].mean():.4f})")
    print(f"  DOWN: ${down_trades['price'].min():.4f} - ${down_trades['price'].max():.4f} (avg: ${down_trades['price'].mean():.4f})")
    
    # Trade size ranges
    print(f"\nTrade sizes:")
    print(f"  Min: ${trades_df['amount'].min():.2f}")
    print(f"  Max: ${trades_df['amount'].max():.2f}")
    print(f"  Avg: ${trades_df['amount'].mean():.2f}")
    print(f"  Median: ${trades_df['amount'].median():.2f}")
    
    # ========================================================================
    # SECTION 2: REBALANCING VS RISK-TAKING
    # ========================================================================
    print(f"\n{'-'*80}")
    print("2. REBALANCING VS RISK-TAKING")
    print(f"{'-'*80}")
    
    rebalancing_trades = trades_df[trades_df['is_rebalancing']]
    risk_trades = trades_df[~trades_df['is_rebalancing']]
    
    print(f"Rebalancing trades (buying minority): {len(rebalancing_trades)} ({100*len(rebalancing_trades)/len(trades_df):.1f}%)")
    print(f"Risk trades (buying majority): {len(risk_trades)} ({100*len(risk_trades)/len(trades_df):.1f}%)")
    
    # When they take risk, does it pay off?
    if len(risk_trades) > 0:
        risk_improved = risk_trades[risk_trades['improved_min']]
        print(f"Risk trades that improved min profit: {len(risk_improved)} ({100*len(risk_improved)/len(risk_trades):.1f}%)")
        risk_buying_winner = risk_trades[risk_trades['buying_winner']]
        print(f"Risk trades buying eventual winner: {len(risk_buying_winner)} ({100*len(risk_buying_winner)/len(risk_trades):.1f}%)")
    
    # ========================================================================
    # SECTION 3: POSITION IMPROVEMENT PATTERNS
    # ========================================================================
    print(f"\n{'-'*80}")
    print("3. POSITION IMPROVEMENT PATTERNS")
    print(f"{'-'*80}")
    
    improved_min_trades = trades_df[trades_df['improved_min']]
    worsened_min_trades = trades_df[~trades_df['improved_min']]
    
    print(f"Trades that IMPROVED min profit: {len(improved_min_trades)} ({100*len(improved_min_trades)/len(trades_df):.1f}%)")
    print(f"Trades that WORSENED/maintained min profit: {len(worsened_min_trades)} ({100*len(worsened_min_trades)/len(trades_df):.1f}%)")
    
    # When they worsen, how bad is it?
    if len(worsened_min_trades) > 0:
        worsened_min_trades_copy = worsened_min_trades.copy()
        worsened_min_trades_copy['delta'] = worsened_min_trades_copy['min_profit'] - worsened_min_trades_copy['prev_min']
        print(f"  Max worsening: ${worsened_min_trades_copy['delta'].min():.4f}")
        print(f"  Avg worsening: ${worsened_min_trades_copy['delta'].mean():.4f}")
    
    # Longest consecutive streak of worsening
    max_worsen_streak = 0
    current_streak = 0
    for improved in trades_df['improved_min']:
        if not improved:
            current_streak += 1
            max_worsen_streak = max(max_worsen_streak, current_streak)
        else:
            current_streak = 0
    print(f"Longest streak of consecutive worsening: {max_worsen_streak} trades")
    
    # ========================================================================
    # SECTION 4: NEGATIVE PERIODS
    # ========================================================================
    print(f"\n{'-'*80}")
    print("4. NEGATIVE PERIODS ANALYSIS")
    print(f"{'-'*80}")
    
    negative_trades = trades_df[trades_df['min_profit'] < 0]
    print(f"Trades with negative min profit: {len(negative_trades)} ({100*len(negative_trades)/len(trades_df):.1f}%)")
    
    if len(negative_trades) > 0:
        print(f"Deepest negative: ${negative_trades['min_profit'].min():.4f}")
        
        # How long do they stay negative?
        negative_streaks = []
        current_streak = 0
        for min_p in trades_df['min_profit']:
            if min_p < 0:
                current_streak += 1
            else:
                if current_streak > 0:
                    negative_streaks.append(current_streak)
                current_streak = 0
        
        if negative_streaks:
            print(f"Negative streaks: {len(negative_streaks)} times")
            print(f"  Longest negative streak: {max(negative_streaks)} trades")
            print(f"  Avg negative streak: {np.mean(negative_streaks):.1f} trades")
            
        # When negative, what do they do?
        print(f"\nWhen negative, they:")
        neg_rebalancing = negative_trades[negative_trades['is_rebalancing']]
        print(f"  Rebalance: {len(neg_rebalancing)}/{len(negative_trades)} times ({100*len(neg_rebalancing)/len(negative_trades):.1f}%)")
    else:
        print("NEVER went negative!")
    
    # ========================================================================
    # SECTION 5: SPREAD ANALYSIS
    # ========================================================================
    print(f"\n{'-'*80}")
    print("5. SPREAD ANALYSIS")
    print(f"{'-'*80}")
    
    print(f"Spread range: ${trades_df['spread'].min():.4f} - ${trades_df['spread'].max():.4f}")
    print(f"Average spread: ${trades_df['spread'].mean():.4f}")
    print(f"Final spread: ${trades_df.iloc[-1]['spread']:.4f}")
    
    # Relationship between spread and balance
    high_balance = trades_df[trades_df['balance_ratio'] > 0.20]
    low_balance = trades_df[trades_df['balance_ratio'] < 0.10]
    
    if len(high_balance) > 0 and len(low_balance) > 0:
        print(f"\nSpread vs Balance:")
        print(f"  When balanced (<10%): avg spread ${low_balance['spread'].mean():.4f}")
        print(f"  When imbalanced (>20%): avg spread ${high_balance['spread'].mean():.4f}")
        print(f"  -> Tighter when imbalanced: {high_balance['spread'].mean() < low_balance['spread'].mean()}")
    
    # ========================================================================
    # SECTION 6: BALANCE RATIO PATTERNS
    # ========================================================================
    print(f"\n{'-'*80}")
    print("6. BALANCE RATIO PATTERNS")
    print(f"{'-'*80}")
    
    print(f"Balance ratio range: {trades_df['balance_ratio'].min():.4f} - {trades_df['balance_ratio'].max():.4f}")
    print(f"Average balance ratio: {trades_df['balance_ratio'].mean():.4f}")
    print(f"Final balance ratio: {trades_df.iloc[-1]['balance_ratio']:.4f}")
    
    # How often do they let it drift?
    high_imbalance = trades_df[trades_df['balance_ratio'] > 0.15]
    print(f"Times balance exceeded 15%: {len(high_imbalance)} ({100*len(high_imbalance)/len(trades_df):.1f}%)")
    
    # ========================================================================
    # SECTION 7: FINAL OUTCOME BIAS
    # ========================================================================
    print(f"\n{'-'*80}")
    print("7. OUTCOME BIAS (Do they predict the winner?)")
    print(f"{'-'*80}")
    
    # Split into thirds: early, mid, late
    third = len(trades_df) // 3
    early = trades_df.iloc[:third]
    mid = trades_df.iloc[third:2*third]
    late = trades_df.iloc[2*third:]
    
    print(f"Buying winner side:")
    print(f"  Early (first 1/3): {100*early['buying_winner'].mean():.1f}%")
    print(f"  Mid (middle 1/3): {100*mid['buying_winner'].mean():.1f}%")
    print(f"  Late (last 1/3): {100*late['buying_winner'].mean():.1f}%")
    
    # Final position bias
    final_up_shares = trades_df.iloc[-1]['up_shares']
    final_down_shares = trades_df.iloc[-1]['down_shares']
    print(f"\nFinal position:")
    print(f"  UP: {final_up_shares:.2f} shares")
    print(f"  DOWN: {final_down_shares:.2f} shares")
    print(f"  Heavier on winner? {(winner == 'UP' and final_up_shares > final_down_shares) or (winner == 'DOWN' and final_down_shares > final_up_shares)}")
    
    # ========================================================================
    # SECTION 8: KEY MOMENTS
    # ========================================================================
    print(f"\n{'-'*80}")
    print("8. KEY MOMENTS")
    print(f"{'-'*80}")
    
    # Largest single improvement in min profit
    trades_df_copy = trades_df.copy()
    trades_df_copy['min_improvement'] = trades_df_copy['min_profit'] - trades_df_copy['prev_min']
    best_trade = trades_df_copy.loc[trades_df_copy['min_improvement'].idxmax()]
    print(f"Best single trade (biggest min profit improvement):")
    print(f"  Trade #{best_trade['trade_num']}: bought {best_trade['side']} at ${best_trade['price']:.4f}")
    print(f"  Min profit: ${best_trade['prev_min']:.4f} -> ${best_trade['min_profit']:.4f} (+${best_trade['min_improvement']:.4f})")
    
    # Largest single spread reduction
    trades_df_copy['spread_reduction'] = trades_df_copy['prev_spread'] - trades_df_copy['spread']
    best_tighten = trades_df_copy.loc[trades_df_copy['spread_reduction'].idxmax()]
    if best_tighten['spread_reduction'] > 0:
        print(f"\nBest spread tightening:")
        print(f"  Trade #{best_tighten['trade_num']}: bought {best_tighten['side']} at ${best_tighten['price']:.4f}")
        print(f"  Spread: ${best_tighten['prev_spread']:.4f} -> ${best_tighten['spread']:.4f} (-${best_tighten['spread_reduction']:.4f})")
    
    return trades_df


def main():
    """Analyze all available markets."""
    gabagool_files = sorted(glob.glob('testing_data/*_gabagool.csv'))
    
    print(f"\n{'#'*80}")
    print(f"# COMPREHENSIVE GABAGOOL ANALYSIS")
    print(f"# Found {len(gabagool_files)} markets")
    print(f"{'#'*80}")
    
    all_results = []
    
    for gaba_csv in gabagool_files[:3]:  # Analyze first 3 markets in detail
        market_csv = gaba_csv.replace('_gabagool.csv', '_market.csv')
        if Path(market_csv).exists():
            try:
                result = comprehensive_analysis(gaba_csv, market_csv)
                all_results.append(result)
            except Exception as e:
                print(f"Error analyzing {gaba_csv}: {e}")
    
    print(f"\n{'#'*80}")
    print(f"# ANALYSIS COMPLETE")
    print(f"{'#'*80}")


if __name__ == '__main__':
    main()

