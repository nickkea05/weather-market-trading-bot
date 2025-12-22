#!/usr/bin/env python3
"""
Quick check: does gabagool ever hold BOTH sides simultaneously?
"""

import pandas as pd
import glob

def check_both_sides(csv_path):
    """Check if gabagool ever holds both UP and DOWN at the same time."""
    df = pd.read_csv(csv_path)
    
    up_shares = 0.0
    down_shares = 0.0
    
    both_sides_count = 0
    
    for idx, row in df.iterrows():
        side = row['outcome']
        shares = row['size']
        
        if side == 'Yes':
            up_shares += shares
        else:
            down_shares += shares
        
        # Check if both sides are held
        if up_shares > 0.01 and down_shares > 0.01:
            both_sides_count += 1
            if both_sides_count == 1:
                print(f"First time both sides held: trade #{idx+1}")
                print(f"  UP={up_shares:.2f}, DOWN={down_shares:.2f}")
    
    print(f"Total trades with both sides: {both_sides_count}/{len(df)}")
    print(f"Final: UP={up_shares:.2f}, DOWN={down_shares:.2f}")
    return both_sides_count > 0


# Check a few markets
markets = [
    'testing_data/btc-15m_11-00pm_11-15pm_1765857600_gabagool.csv',
    'testing_data/btc-15m_8-00pm_8-15pm_1765846800_gabagool.csv',
    'testing_data/btc-15m_10-15pm_10-30pm_1765854900_gabagool.csv'
]

for market in markets:
    print(f"\n{'='*60}")
    print(f"Market: {market.split('/')[-1]}")
    print(f"{'='*60}")
    has_both = check_both_sides(market)
    if not has_both:
        print("❌ NEVER held both sides simultaneously!")
    else:
        print("✓ Did hold both sides")

