#!/usr/bin/env python3
"""
Compare our bot's behavior to gabagool's in the FIRST MINUTE only.

This is where most of the action happens and where we need to get it right.
"""

import pandas as pd
import sys

def analyze_first_minute(our_trades_csv, gabagool_csv, market_csv, market_name):
    """Compare first 60 seconds only."""
    
    our_df = pd.read_csv(our_trades_csv)
    gaba_df = pd.read_csv(gabagool_csv)
    market_df = pd.read_csv(market_csv)
    
    print(f"\n{'='*80}")
    print(f"MARKET: {market_name} - FIRST MINUTE ONLY")
    print(f"{'='*80}\n")
    
    # Use first trade timestamp as market start (not market data which starts later)
    # Convert gabagool timestamps to numeric
    gaba_df['timestamp_numeric'] = pd.to_datetime(gaba_df['timestamp']).astype(int) / 1e9
    market_start = gaba_df['timestamp_numeric'].min()
    
    # Filter to first 60 seconds after first trade
    our_first_min = our_df[our_df['timestamp'] <= market_start + 60]
    gaba_first_min = gaba_df[gaba_df['timestamp_numeric'] <= market_start + 60]
    
    print(f"Market start time (first trade): {market_start}")
    print(f"First minute window: {market_start} to {market_start + 60}")
    
    # === VOLUME ===
    print(f"\n{'-'*80}")
    print("1. VOLUME & TRADE COUNT (First Minute)")
    print(f"{'-'*80}\n")
    
    print(f"Our trades: {len(our_first_min)}")
    print(f"Gabagool trades: {len(gaba_first_min)}")
    print(f"Trade count ratio: {len(our_first_min)}/{len(gaba_first_min)} = {100*len(our_first_min)/len(gaba_first_min) if len(gaba_first_min) > 0 else 0:.1f}%")
    
    our_spend = our_first_min['cost'].sum()
    gaba_spend = gaba_first_min['usdcSize'].sum()
    print(f"\nOur spend: ${our_spend:.2f}")
    print(f"Gabagool spend: ${gaba_spend:.2f}")
    print(f"Spend ratio: {100*our_spend/gaba_spend if gaba_spend > 0 else 0:.1f}%")
    
    # === PRICES ===
    print(f"\n{'-'*80}")
    print("2. PRICE SELECTION (First Minute)")
    print(f"{'-'*80}\n")
    
    our_up = our_first_min[our_first_min['side'] == 'UP']
    our_down = our_first_min[our_first_min['side'] == 'DOWN']
    gaba_up = gaba_first_min[gaba_first_min['outcome'].str.upper() == 'UP']
    gaba_down = gaba_first_min[gaba_first_min['outcome'].str.upper() == 'DOWN']
    
    if len(our_up) > 0 and len(gaba_up) > 0:
        print(f"UP side:")
        print(f"  Our avg: ${our_up['price'].mean():.4f} (trades: {len(our_up)})")
        print(f"  Gaba avg: ${gaba_up['price'].mean():.4f} (trades: {len(gaba_up)})")
        print(f"  Difference: ${abs(our_up['price'].mean() - gaba_up['price'].mean()):.4f}")
    
    if len(our_down) > 0 and len(gaba_down) > 0:
        print(f"\nDOWN side:")
        print(f"  Our avg: ${our_down['price'].mean():.4f} (trades: {len(our_down)})")
        print(f"  Gaba avg: ${gaba_down['price'].mean():.4f} (trades: {len(gaba_down)})")
        print(f"  Difference: ${abs(our_down['price'].mean() - gaba_down['price'].mean()):.4f}")
    
    # === FINAL POSITION AFTER FIRST MINUTE ===
    print(f"\n{'-'*80}")
    print("3. POSITION AFTER FIRST MINUTE")
    print(f"{'-'*80}\n")
    
    # Calculate our position
    our_up_shares = our_up['size'].sum() if len(our_up) > 0 else 0
    our_down_shares = our_down['size'].sum() if len(our_down) > 0 else 0
    our_up_cost = our_up['cost'].sum() if len(our_up) > 0 else 0
    our_down_cost = our_down['cost'].sum() if len(our_down) > 0 else 0
    
    our_min = min(our_up_shares - our_up_cost, our_down_shares - our_down_cost)
    our_max = max(our_up_shares - our_up_cost, our_down_shares - our_down_cost)
    our_spread = our_max - our_min
    our_balance = abs(our_up_shares - our_down_shares) / (our_up_shares + our_down_shares) if (our_up_shares + our_down_shares) > 0 else 0
    our_combined = (our_up_cost / our_up_shares if our_up_shares > 0 else 0) + (our_down_cost / our_down_shares if our_down_shares > 0 else 0)
    
    # Calculate gabagool's position
    gaba_up_shares = gaba_up['size'].sum() if len(gaba_up) > 0 else 0
    gaba_down_shares = gaba_down['size'].sum() if len(gaba_down) > 0 else 0
    gaba_up_cost = gaba_up['usdcSize'].sum() if len(gaba_up) > 0 else 0
    gaba_down_cost = gaba_down['usdcSize'].sum() if len(gaba_down) > 0 else 0
    
    gaba_min = min(gaba_up_shares - gaba_up_cost, gaba_down_shares - gaba_down_cost)
    gaba_max = max(gaba_up_shares - gaba_up_cost, gaba_down_shares - gaba_down_cost)
    gaba_spread = gaba_max - gaba_min
    gaba_balance = abs(gaba_up_shares - gaba_down_shares) / (gaba_up_shares + gaba_down_shares) if (gaba_up_shares + gaba_down_shares) > 0 else 0
    gaba_combined = (gaba_up_cost / gaba_up_shares if gaba_up_shares > 0 else 0) + (gaba_down_cost / gaba_down_shares if gaba_down_shares > 0 else 0)
    
    print(f"OUR BOT:")
    print(f"  Shares: UP {our_up_shares:.1f}, DOWN {our_down_shares:.1f}")
    print(f"  Cost: UP ${our_up_cost:.2f}, DOWN ${our_down_cost:.2f}")
    print(f"  Avg prices: UP ${our_up_cost/our_up_shares if our_up_shares > 0 else 0:.4f}, DOWN ${our_down_cost/our_down_shares if our_down_shares > 0 else 0:.4f}")
    print(f"  Min profit: ${our_min:.2f}")
    print(f"  Max profit: ${our_max:.2f}")
    print(f"  Spread: ${our_spread:.2f}")
    print(f"  Balance ratio: {our_balance:.4f} ({our_balance*100:.1f}%)")
    print(f"  Combined avg: ${our_combined:.4f}")
    
    print(f"\nGABAGOOL:")
    print(f"  Shares: UP {gaba_up_shares:.1f}, DOWN {gaba_down_shares:.1f}")
    print(f"  Cost: UP ${gaba_up_cost:.2f}, DOWN ${gaba_down_cost:.2f}")
    print(f"  Avg prices: UP ${gaba_up_cost/gaba_up_shares if gaba_up_shares > 0 else 0:.4f}, DOWN ${gaba_down_cost/gaba_down_shares if gaba_down_shares > 0 else 0:.4f}")
    print(f"  Min profit: ${gaba_min:.2f}")
    print(f"  Max profit: ${gaba_max:.2f}")
    print(f"  Spread: ${gaba_spread:.2f}")
    print(f"  Balance ratio: {gaba_balance:.4f} ({gaba_balance*100:.1f}%)")
    print(f"  Combined avg: ${gaba_combined:.4f}")
    
    print(f"\nDIFFERENCE:")
    diff_min = our_min - gaba_min
    diff_spread = our_spread - gaba_spread
    diff_balance = our_balance - gaba_balance
    diff_combined = our_combined - gaba_combined
    
    print(f"  Min profit: ${diff_min:+.2f} ({'WE WIN' if diff_min > 0 else 'GABAGOOL WINS'})")
    print(f"  Spread: ${diff_spread:+.2f} ({'WE TIGHTER' if diff_spread < 0 else 'GABAGOOL TIGHTER'})")
    print(f"  Balance: {diff_balance:+.4f} ({'WE MORE BALANCED' if abs(our_balance) < abs(gaba_balance) else 'GABAGOOL MORE BALANCED'})")
    print(f"  Combined avg: ${diff_combined:+.4f}")
    
    # === KEY INSIGHTS ===
    print(f"\n{'-'*80}")
    print("4. KEY INSIGHTS")
    print(f"{'-'*80}\n")
    
    print(f"Volume gap: We trade {len(gaba_first_min) - len(our_first_min)} fewer times")
    print(f"Min profit gap: ${diff_min:.2f}")
    print(f"Combined avg gap: ${diff_combined:.4f}")
    
    if diff_min < 0:
        print(f"\nWHY ARE WE BEHIND?")
        if diff_combined > 0.01:
            print(f"  1. Combined avg too high: ${diff_combined:.4f} worse")
        if len(our_first_min) < len(gaba_first_min) * 0.5:
            print(f"  2. Not trading enough: {len(our_first_min)} vs {len(gaba_first_min)}")
        if abs(diff_balance) > 0.10:
            print(f"  3. Balance issues: {our_balance:.4f} vs {gaba_balance:.4f}")
    
    return {
        'our_trades': len(our_first_min),
        'gaba_trades': len(gaba_first_min),
        'our_min': our_min,
        'gaba_min': gaba_min,
        'our_combined': our_combined,
        'gaba_combined': gaba_combined
    }


def main():
    """Analyze first minute of 3 markets."""
    
    markets = [
        {
            'name': 'Market 1: 11:00pm',
            'our': 'testing_data/btc-15m_11-00pm_11-15pm_1765857600_marketpapertrades.csv',
            'gaba': 'testing_data/btc-15m_11-00pm_11-15pm_1765857600_gabagool.csv',
            'market': 'testing_data/btc-15m_11-00pm_11-15pm_1765857600_market.csv'
        },
        {
            'name': 'Market 2: 10:15pm',
            'our': 'testing_data/btc-15m_10-15pm_10-30pm_1765854900_marketpapertrades.csv',
            'gaba': 'testing_data/btc-15m_10-15pm_10-30pm_1765854900_gabagool.csv',
            'market': 'testing_data/btc-15m_10-15pm_10-30pm_1765854900_market.csv'
        },
        {
            'name': 'Market 3: 8:00pm (volatile)',
            'our': 'testing_data/btc-15m_8-00pm_8-15pm_1765846800_marketpapertrades.csv',
            'gaba': 'testing_data/btc-15m_8-00pm_8-15pm_1765846800_gabagool.csv',
            'market': 'testing_data/btc-15m_8-00pm_8-15pm_1765846800_market.csv'
        }
    ]
    
    results = []
    
    for market in markets:
        try:
            result = analyze_first_minute(market['our'], market['gaba'], market['market'], market['name'])
            results.append((market['name'], result))
        except Exception as e:
            print(f"Error analyzing {market['name']}: {e}")
            import traceback
            traceback.print_exc()
    
    # === SUMMARY ===
    print(f"\n{'='*80}")
    print("FIRST MINUTE SUMMARY - ALL 3 MARKETS")
    print(f"{'='*80}\n")
    
    total_our_trades = sum(r['our_trades'] for _, r in results)
    total_gaba_trades = sum(r['gaba_trades'] for _, r in results)
    total_our_min = sum(r['our_min'] for _, r in results)
    total_gaba_min = sum(r['gaba_min'] for _, r in results)
    avg_our_combined = sum(r['our_combined'] for _, r in results) / len(results)
    avg_gaba_combined = sum(r['gaba_combined'] for _, r in results) / len(results)
    
    print(f"Total trades (first minute):")
    print(f"  Our bot: {total_our_trades}")
    print(f"  Gabagool: {total_gaba_trades}")
    print(f"  Ratio: {100*total_our_trades/total_gaba_trades if total_gaba_trades > 0 else 0:.1f}%")
    
    print(f"\nTotal min profit (first minute):")
    print(f"  Our bot: ${total_our_min:.2f}")
    print(f"  Gabagool: ${total_gaba_min:.2f}")
    print(f"  Gap: ${total_our_min - total_gaba_min:.2f}")
    
    print(f"\nAvg combined average (first minute):")
    print(f"  Our bot: ${avg_our_combined:.4f}")
    print(f"  Gabagool: ${avg_gaba_combined:.4f}")
    print(f"  Gap: ${avg_our_combined - avg_gaba_combined:.4f}")
    
    print(f"\n{'-'*80}")
    if total_our_min < total_gaba_min:
        gap = total_gaba_min - total_our_min
        print(f"We are ${gap:.2f} behind gabagool in FIRST MINUTE alone.")
        print(f"\nThis is where we need to fix our strategy!")
    else:
        print("We're ahead! Strategy is working for first minute.")


if __name__ == '__main__':
    main()

