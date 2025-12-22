#!/usr/bin/env python3
"""
Analyze which gabagool trades would be BLOCKED by our current strategy logic.

For each gabagool trade, check:
1. Would Layer 1 allow it? (buying minority side with good combined avg?)
2. Would Layer 2 allow it? (improves min profit AND combined avg < 1.02?)

If NEITHER would allow it, the trade is BLOCKED.
Then analyze the pattern of blocked trades to understand what we're missing.
"""

import pandas as pd
import sys

def analyze_blocked_trades(gabagool_csv, market_name):
    """Analyze which trades would be blocked by our strategy."""
    
    df = pd.read_csv(gabagool_csv)
    
    print(f"\n{'='*80}")
    print(f"MARKET: {market_name}")
    print(f"{'='*80}\n")
    
    # Track position
    up_shares = 0.0
    down_shares = 0.0
    up_cost = 0.0
    down_cost = 0.0
    
    blocked_trades = []
    allowed_by_layer1 = []
    allowed_by_layer2 = []
    total_trades = 0
    
    for idx, row in df.iterrows():
        total_trades += 1
        side = row['outcome'].upper()
        price = row['price']
        shares = row['size']
        amount = row['usdcSize']
        
        # Previous state
        prev_up_shares = up_shares
        prev_down_shares = down_shares
        prev_up_cost = up_cost
        prev_down_cost = down_cost
        
        prev_total = prev_up_shares + prev_down_shares
        if prev_total > 0:
            prev_min_profit = min(prev_up_shares - prev_up_cost, prev_down_shares - prev_down_cost)
            prev_avg_up = prev_up_cost / prev_up_shares if prev_up_shares > 0 else 0
            prev_avg_down = prev_down_cost / prev_down_shares if prev_down_shares > 0 else 0
            prev_combined_avg = prev_avg_up + prev_avg_down
            minority_side = 'UP' if prev_up_shares < prev_down_shares else 'DOWN'
        else:
            prev_min_profit = 0
            prev_combined_avg = 0
            minority_side = 'UP'  # Arbitrary for first trade
        
        # Update position
        if side == 'UP':
            up_shares += shares
            up_cost += amount
        else:
            down_shares += shares
            down_cost += amount
        
        # New state
        total_shares = up_shares + down_shares
        min_profit = min(up_shares - up_cost, down_shares - down_cost)
        avg_up = up_cost / up_shares if up_shares > 0 else 0
        avg_down = down_cost / down_shares if down_shares > 0 else 0
        combined_avg = avg_up + avg_down
        
        # CHECK LAYER 1: Buying minority side?
        layer1_allowed = False
        if prev_total == 0:
            # First trade always allowed
            layer1_allowed = True
        elif side == minority_side:
            # Buying minority side
            # Check if combined avg is under 1.00 (our Layer 1 rule)
            if combined_avg < 1.00:
                layer1_allowed = True
        
        # CHECK LAYER 2: Improves min profit AND combined avg < 1.02?
        layer2_allowed = False
        if prev_total > 0:
            if min_profit > prev_min_profit and combined_avg < 1.02:
                layer2_allowed = True
        
        # Is this trade BLOCKED?
        is_blocked = not (layer1_allowed or layer2_allowed)
        
        if is_blocked:
            blocked_trades.append({
                'trade_num': idx + 1,
                'side': side,
                'price': price,
                'amount': amount,
                'prev_min': prev_min_profit,
                'new_min': min_profit,
                'min_delta': min_profit - prev_min_profit,
                'prev_combined': prev_combined_avg,
                'new_combined': combined_avg,
                'minority_side': minority_side,
                'is_minority': side == minority_side,
                'prev_up_shares': prev_up_shares,
                'prev_down_shares': prev_down_shares,
                'new_up_shares': up_shares,
                'new_down_shares': down_shares
            })
        elif layer1_allowed:
            allowed_by_layer1.append(idx + 1)
        elif layer2_allowed:
            allowed_by_layer2.append(idx + 1)
    
    # Print summary
    print(f"Total gabagool trades: {total_trades}")
    print(f"Allowed by Layer 1: {len(allowed_by_layer1)} ({100*len(allowed_by_layer1)/total_trades:.1f}%)")
    print(f"Allowed by Layer 2: {len(allowed_by_layer2)} ({100*len(allowed_by_layer2)/total_trades:.1f}%)")
    print(f"BLOCKED by both: {len(blocked_trades)} ({100*len(blocked_trades)/total_trades:.1f}%)")
    
    if len(blocked_trades) == 0:
        print("\n✓ All gabagool trades would be allowed by our strategy!")
        return
    
    print(f"\n{'-'*80}")
    print(f"ANALYSIS OF {len(blocked_trades)} BLOCKED TRADES:")
    print(f"{'-'*80}\n")
    
    blocked_df = pd.DataFrame(blocked_trades)
    
    # Pattern 1: Are they buying majority or minority?
    buying_majority = blocked_df[~blocked_df['is_minority']]
    print(f"Buying MAJORITY side: {len(buying_majority)}/{len(blocked_trades)} ({100*len(buying_majority)/len(blocked_trades):.1f}%)")
    print(f"Buying MINORITY side: {len(blocked_df[blocked_df['is_minority']])}/{len(blocked_trades)}")
    
    # Pattern 2: Do they improve or worsen min profit?
    improving = blocked_df[blocked_df['min_delta'] > 0]
    worsening = blocked_df[blocked_df['min_delta'] < 0]
    print(f"\nImprove min profit: {len(improving)}/{len(blocked_trades)}")
    print(f"Worsen min profit: {len(worsening)}/{len(blocked_trades)} ({100*len(worsening)/len(blocked_trades):.1f}%)")
    if len(worsening) > 0:
        print(f"  Avg worsening: ${worsening['min_delta'].mean():.2f}")
        print(f"  Max worsening: ${worsening['min_delta'].min():.2f}")
    
    # Pattern 3: Combined avg patterns
    over_100 = blocked_df[blocked_df['new_combined'] >= 1.00]
    over_102 = blocked_df[blocked_df['new_combined'] >= 1.02]
    print(f"\nNew combined avg >= 1.00: {len(over_100)}/{len(blocked_trades)}")
    print(f"New combined avg >= 1.02: {len(over_102)}/{len(blocked_trades)}")
    
    # Pattern 4: Show first few blocked trades in detail
    print(f"\n{'-'*80}")
    print("FIRST 10 BLOCKED TRADES (detailed):")
    print(f"{'-'*80}\n")
    
    for _, trade in blocked_df.head(10).iterrows():
        print(f"Trade #{trade['trade_num']}: Buy {trade['side']} at ${trade['price']:.3f} for ${trade['amount']:.2f}")
        print(f"  Position: UP {trade['prev_up_shares']:.1f} -> {trade['new_up_shares']:.1f}, "
              f"DOWN {trade['prev_down_shares']:.1f} -> {trade['new_down_shares']:.1f}")
        print(f"  Minority side: {trade['minority_side']} (buying {'MINORITY' if trade['is_minority'] else 'MAJORITY'})")
        print(f"  Min profit: ${trade['prev_min']:.2f} -> ${trade['new_min']:.2f} "
              f"({'IMPROVES' if trade['min_delta'] > 0 else 'WORSENS'} by ${abs(trade['min_delta']):.2f})")
        print(f"  Combined avg: ${trade['prev_combined']:.4f} -> ${trade['new_combined']:.4f}")
        print()
    
    # Pattern 5: WHY might these trades be valuable?
    print(f"{'-'*80}")
    print("HYPOTHESIS: Why does gabagool make these 'blocked' trades?")
    print(f"{'-'*80}\n")
    
    # Are they buying at good prices even when it worsens position?
    avg_blocked_price = blocked_df['price'].mean()
    print(f"Average price of blocked trades: ${avg_blocked_price:.3f}")
    
    # Are they maintaining market presence / liquidity provision?
    if len(buying_majority) > 0:
        print(f"\nWhen buying MAJORITY side:")
        print(f"  Average price: ${buying_majority['price'].mean():.3f}")
        print(f"  Average worsening: ${buying_majority['min_delta'].mean():.2f}")
    
    # Summary hypothesis
    print(f"\n{'-'*80}")
    print("KEY INSIGHT:")
    print(f"{'-'*80}")
    print(f"Gabagool makes {len(blocked_trades)} trades that our strategy would block.")
    if len(worsening) > 0:
        print(f"Most of these ({len(worsening)}) WORSEN min profit but might:")
        print(f"  1. Capitalize on good prices (low cost basis)")
        print(f"  2. Build position for future rebalancing")
        print(f"  3. Maintain market presence/liquidity")
    print(f"\nOur strategy is TOO RESTRICTIVE - we need a 3rd condition that allows")
    print(f"trades that worsen position if they have strategic value.")
    
    return blocked_df


def main():
    """Analyze markets 1, 2, and 3."""
    
    markets = [
        ('testing_data/btc-15m_11-00pm_11-15pm_1765857600_gabagool.csv', 'Market 1: 11:00pm'),
        ('testing_data/btc-15m_10-15pm_10-30pm_1765854900_gabagool.csv', 'Market 2: 10:15pm'),
        ('testing_data/btc-15m_8-00pm_8-15pm_1765846800_gabagool.csv', 'Market 3: 8:00pm (volatile)')
    ]
    
    all_blocked = []
    
    for csv_path, name in markets:
        try:
            blocked = analyze_blocked_trades(csv_path, name)
            if blocked is not None and len(blocked) > 0:
                all_blocked.append((name, blocked))
        except Exception as e:
            print(f"Error analyzing {name}: {e}")
            import traceback
            traceback.print_exc()
    
    # Cross-market summary
    if all_blocked:
        print(f"\n{'='*80}")
        print("CROSS-MARKET SUMMARY")
        print(f"{'='*80}\n")
        
        total_blocked = sum(len(b) for _, b in all_blocked)
        print(f"Total blocked trades across all markets: {total_blocked}")
        
        for name, blocked_df in all_blocked:
            print(f"\n{name}:")
            print(f"  Blocked: {len(blocked_df)}")
            print(f"  Buying majority: {len(blocked_df[~blocked_df['is_minority']])}")
            print(f"  Worsening min profit: {len(blocked_df[blocked_df['min_delta'] < 0])}")


if __name__ == '__main__':
    main()

