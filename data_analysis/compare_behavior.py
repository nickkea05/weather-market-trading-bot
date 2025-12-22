#!/usr/bin/env python3
"""
Compare our bot's behavior to gabagool's across 3 markets.

Find key differences:
1. Trade timing - when do we diverge?
2. Price selection - do we buy at different prices?
3. Balance management - who stays more balanced?
4. Min profit trajectory - who goes more negative?
5. Volume - who trades more?
6. Critical moments - where do we make different decisions?
"""

import pandas as pd
import sys

def analyze_market(our_trades_csv, gabagool_csv, market_csv, market_name):
    """Compare our trades vs gabagool for one market."""
    
    our_df = pd.read_csv(our_trades_csv)
    gaba_df = pd.read_csv(gabagool_csv)
    market_df = pd.read_csv(market_csv)
    
    print(f"\n{'='*80}")
    print(f"MARKET: {market_name}")
    print(f"{'='*80}\n")
    
    # Determine winner
    final_row = market_df.iloc[-1]
    winner = 'UP' if final_row['up_best_ask'] > final_row['down_best_ask'] else 'DOWN'
    print(f"Winner: {winner} (final prices: UP=${final_row['up_best_ask']:.4f}, DOWN=${final_row['down_best_ask']:.4f})\n")
    
    # === SECTION 1: VOLUME & TRADE COUNT ===
    print(f"{'-'*80}")
    print("1. VOLUME & TRADE COUNT")
    print(f"{'-'*80}\n")
    
    print(f"Our trades: {len(our_df)}")
    print(f"Gabagool trades: {len(gaba_df)}")
    print(f"Trade count ratio: {len(our_df)}/{len(gaba_df)} = {100*len(our_df)/len(gaba_df):.1f}%")
    
    our_total_spend = our_df['cost'].sum()
    gaba_total_spend = gaba_df['usdcSize'].sum()
    print(f"\nOur total spend: ${our_total_spend:.2f}")
    print(f"Gabagool total spend: ${gaba_total_spend:.2f}")
    print(f"Spend ratio: {100*our_total_spend/gaba_total_spend:.1f}%")
    
    # === SECTION 2: PRICE SELECTION ===
    print(f"\n{'-'*80}")
    print("2. PRICE SELECTION")
    print(f"{'-'*80}\n")
    
    our_up = our_df[our_df['side'] == 'UP']
    our_down = our_df[our_df['side'] == 'DOWN']
    gaba_up = gaba_df[gaba_df['outcome'].str.upper() == 'UP']
    gaba_down = gaba_df[gaba_df['outcome'].str.upper() == 'DOWN']
    
    print("UP side prices:")
    if len(our_up) > 0 and len(gaba_up) > 0:
        print(f"  Our avg: ${our_up['price'].mean():.4f} (range: ${our_up['price'].min():.4f}-${our_up['price'].max():.4f})")
        print(f"  Gaba avg: ${gaba_up['price'].mean():.4f} (range: ${gaba_up['price'].min():.4f}-${gaba_up['price'].max():.4f})")
        print(f"  Difference: ${abs(our_up['price'].mean() - gaba_up['price'].mean()):.4f}")
    
    print("\nDOWN side prices:")
    if len(our_down) > 0 and len(gaba_down) > 0:
        print(f"  Our avg: ${our_down['price'].mean():.4f} (range: ${our_down['price'].min():.4f}-${our_down['price'].max():.4f})")
        print(f"  Gaba avg: ${gaba_down['price'].mean():.4f} (range: ${gaba_down['price'].min():.4f}-${gaba_down['price'].max():.4f})")
        print(f"  Difference: ${abs(our_down['price'].mean() - gaba_down['price'].mean()):.4f}")
    
    # === SECTION 3: FINAL OUTCOMES ===
    print(f"\n{'-'*80}")
    print("3. FINAL OUTCOMES")
    print(f"{'-'*80}\n")
    
    # Calculate our final position
    our_up_shares = 0.0
    our_down_shares = 0.0
    our_up_cost = 0.0
    our_down_cost = 0.0
    
    for _, row in our_df.iterrows():
        if row['side'] == 'UP':
            our_up_shares += row['size']
            our_up_cost += row['cost']
        else:
            our_down_shares += row['size']
            our_down_cost += row['cost']
    
    our_min_profit = min(our_up_shares - our_up_cost, our_down_shares - our_down_cost)
    our_max_profit = max(our_up_shares - our_up_cost, our_down_shares - our_down_cost)
    our_spread = our_max_profit - our_min_profit
    our_balance = abs(our_up_shares - our_down_shares) / (our_up_shares + our_down_shares) if (our_up_shares + our_down_shares) > 0 else 0
    our_combined_avg = (our_up_cost / our_up_shares if our_up_shares > 0 else 0) + (our_down_cost / our_down_shares if our_down_shares > 0 else 0)
    
    # Calculate gabagool's final position
    gaba_up_shares = 0.0
    gaba_down_shares = 0.0
    gaba_up_cost = 0.0
    gaba_down_cost = 0.0
    
    for _, row in gaba_df.iterrows():
        if row['outcome'].upper() == 'UP':
            gaba_up_shares += row['size']
            gaba_up_cost += row['usdcSize']
        else:
            gaba_down_shares += row['size']
            gaba_down_cost += row['usdcSize']
    
    gaba_min_profit = min(gaba_up_shares - gaba_up_cost, gaba_down_shares - gaba_down_cost)
    gaba_max_profit = max(gaba_up_shares - gaba_up_cost, gaba_down_shares - gaba_down_cost)
    gaba_spread = gaba_max_profit - gaba_min_profit
    gaba_balance = abs(gaba_up_shares - gaba_down_shares) / (gaba_up_shares + gaba_down_shares) if (gaba_up_shares + gaba_down_shares) > 0 else 0
    gaba_combined_avg = (gaba_up_cost / gaba_up_shares if gaba_up_shares > 0 else 0) + (gaba_down_cost / gaba_down_shares if gaba_down_shares > 0 else 0)
    
    print(f"OUR BOT:")
    print(f"  Position: UP {our_up_shares:.1f} @ ${our_up_cost/our_up_shares if our_up_shares > 0 else 0:.4f}, DOWN {our_down_shares:.1f} @ ${our_down_cost/our_down_shares if our_down_shares > 0 else 0:.4f}")
    print(f"  Min profit: ${our_min_profit:.2f}")
    print(f"  Max profit: ${our_max_profit:.2f}")
    print(f"  Spread: ${our_spread:.2f}")
    print(f"  Balance ratio: {our_balance:.4f} ({our_balance*100:.1f}%)")
    print(f"  Combined avg: ${our_combined_avg:.4f}")
    
    print(f"\nGABAGOOL:")
    print(f"  Position: UP {gaba_up_shares:.1f} @ ${gaba_up_cost/gaba_up_shares if gaba_up_shares > 0 else 0:.4f}, DOWN {gaba_down_shares:.1f} @ ${gaba_down_cost/gaba_down_shares if gaba_down_shares > 0 else 0:.4f}")
    print(f"  Min profit: ${gaba_min_profit:.2f}")
    print(f"  Max profit: ${gaba_max_profit:.2f}")
    print(f"  Spread: ${gaba_spread:.2f}")
    print(f"  Balance ratio: {gaba_balance:.4f} ({gaba_balance*100:.1f}%)")
    print(f"  Combined avg: ${gaba_combined_avg:.4f}")
    
    print(f"\nDIFFERENCE:")
    print(f"  Min profit delta: ${our_min_profit - gaba_min_profit:.2f} ({'we are BETTER' if our_min_profit > gaba_min_profit else 'gabagool is BETTER'})")
    print(f"  Spread delta: ${our_spread - gaba_spread:.2f} ({'we are TIGHTER' if our_spread < gaba_spread else 'gabagool is TIGHTER'})")
    print(f"  Balance delta: {abs(our_balance - gaba_balance):.4f} ({'we are MORE balanced' if our_balance < gaba_balance else 'gabagool is MORE balanced'})")
    print(f"  Combined avg delta: ${our_combined_avg - gaba_combined_avg:.4f}")
    
    # === SECTION 4: LAYER USAGE ===
    print(f"\n{'-'*80}")
    print("4. LAYER USAGE")
    print(f"{'-'*80}\n")
    
    if 'layer' in our_df.columns:
        layer1_trades = len(our_df[our_df['layer'] == 1])
        layer2_trades = len(our_df[our_df['layer'] == 2])
        print(f"Layer 1 trades: {layer1_trades} ({100*layer1_trades/len(our_df):.1f}%)")
        print(f"Layer 2 trades: {layer2_trades} ({100*layer2_trades/len(our_df):.1f}%)")
        
        # Price comparison by layer
        l1_trades = our_df[our_df['layer'] == 1]
        l2_trades = our_df[our_df['layer'] == 2]
        if len(l1_trades) > 0:
            print(f"\nLayer 1 avg price: ${l1_trades['price'].mean():.4f}")
        if len(l2_trades) > 0:
            print(f"Layer 2 avg price: ${l2_trades['price'].mean():.4f}")
    
    # === SECTION 5: SIDE BIAS ===
    print(f"\n{'-'*80}")
    print("5. SIDE BIAS (Did we favor the winner?)")
    print(f"{'-'*80}\n")
    
    our_winner_trades = len(our_df[our_df['side'] == winner])
    gaba_winner_trades = len(gaba_df[gaba_df['outcome'].str.upper() == winner])
    
    print(f"Our trades on winner ({winner}): {our_winner_trades}/{len(our_df)} ({100*our_winner_trades/len(our_df):.1f}%)")
    print(f"Gabagool trades on winner ({winner}): {gaba_winner_trades}/{len(gaba_df)} ({100*gaba_winner_trades/len(gaba_df):.1f}%)")
    
    our_winner_bias = our_winner_trades / len(our_df) if len(our_df) > 0 else 0
    gaba_winner_bias = gaba_winner_trades / len(gaba_df) if len(gaba_df) > 0 else 0
    print(f"\nWinner bias difference: {abs(our_winner_bias - gaba_winner_bias)*100:.1f}% ({'we favor winner MORE' if our_winner_bias > gaba_winner_bias else 'gabagool favors winner MORE'})")
    
    # === SECTION 6: CRITICAL INSIGHT ===
    print(f"\n{'-'*80}")
    print("6. CRITICAL INSIGHT")
    print(f"{'-'*80}\n")
    
    if our_min_profit < gaba_min_profit:
        diff = gaba_min_profit - our_min_profit
        print(f"⚠️ We are ${diff:.2f} BEHIND gabagool in min profit")
        print(f"\nPossible reasons:")
        print(f"  1. Worse prices? Delta: ${abs(our_df['price'].mean() - gaba_df['price'].mean()):.4f}")
        print(f"  2. Worse balance? Our: {our_balance:.4f}, Gaba: {gaba_balance:.4f}")
        print(f"  3. Higher combined avg? Our: ${our_combined_avg:.4f}, Gaba: ${gaba_combined_avg:.4f}")
        print(f"  4. Wrong side bias? We favor winner {our_winner_bias*100:.1f}%, Gaba {gaba_winner_bias*100:.1f}%")
    else:
        diff = our_min_profit - gaba_min_profit
        print(f"✓ We are ${diff:.2f} AHEAD of gabagool in min profit!")
    
    return {
        'our_min': our_min_profit,
        'gaba_min': gaba_min_profit,
        'our_spread': our_spread,
        'gaba_spread': gaba_spread,
        'our_trades': len(our_df),
        'gaba_trades': len(gaba_df)
    }


def main():
    """Analyze all 3 markets."""
    
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
            result = analyze_market(market['our'], market['gaba'], market['market'], market['name'])
            results.append((market['name'], result))
        except Exception as e:
            print(f"Error analyzing {market['name']}: {e}")
            import traceback
            traceback.print_exc()
    
    # SUMMARY
    print(f"\n{'='*80}")
    print("CROSS-MARKET SUMMARY")
    print(f"{'='*80}\n")
    
    total_our_min = sum(r['our_min'] for _, r in results)
    total_gaba_min = sum(r['gaba_min'] for _, r in results)
    total_our_trades = sum(r['our_trades'] for _, r in results)
    total_gaba_trades = sum(r['gaba_trades'] for _, r in results)
    
    print(f"Total min profit:")
    print(f"  Our bot: ${total_our_min:.2f}")
    print(f"  Gabagool: ${total_gaba_min:.2f}")
    print(f"  Difference: ${total_our_min - total_gaba_min:.2f}")
    
    print(f"\nTotal trades:")
    print(f"  Our bot: {total_our_trades}")
    print(f"  Gabagool: {total_gaba_trades}")
    print(f"  Ratio: {100*total_our_trades/total_gaba_trades:.1f}%")
    
    print(f"\n{'-'*80}")
    print("KEY TAKEAWAY:")
    print(f"{'-'*80}")
    if total_our_min < total_gaba_min:
        print(f"We are ${total_gaba_min - total_our_min:.2f} behind gabagool across all markets.")
        print("Main differences to investigate:")
        print("  - Price selection (are we buying at worse prices?)")
        print("  - Trade timing (are we missing key opportunities?)")
        print("  - Side selection (are we biasing wrong side?)")
    else:
        print(f"We are ${total_our_min - total_gaba_min:.2f} AHEAD of gabagool! 🎉")


if __name__ == '__main__':
    main()

