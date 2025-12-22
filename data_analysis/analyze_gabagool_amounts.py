"""
Analyze gabagool's trade amounts to understand sizing strategy
"""
import pandas as pd
from pathlib import Path
import glob

def analyze_gabagool_amounts():
    """Analyze all gabagool CSV files to understand trade sizing"""
    
    # Find all gabagool CSV files
    pattern = 'testing_data/btc-15m_*_gabagool.csv'
    files = sorted(glob.glob(pattern))
    
    if not files:
        print("No gabagool CSV files found")
        return
    
    print(f"Found {len(files)} gabagool CSV files\n")
    
    all_amounts = []
    all_trades = []
    
    for filepath in files:
        df = pd.read_csv(filepath)
        amounts = df['usdcSize'].tolist()
        all_amounts.extend(amounts)
        
        for _, row in df.iterrows():
            all_trades.append({
                'file': Path(filepath).name,
                'amount': row['usdcSize'],
                'shares': row['size'],
                'price': row['price'],
                'outcome': row['outcome']
            })
    
    if not all_amounts:
        print("No trades found")
        return
    
    # Convert to DataFrame for analysis
    amounts_df = pd.DataFrame(all_trades)
    
    print("=" * 80)
    print("GABAGOOL TRADE AMOUNT ANALYSIS")
    print("=" * 80)
    
    print(f"\nTotal Trades: {len(all_amounts)}")
    print(f"Total Markets: {len(files)}")
    
    print(f"\n--- Amount Statistics ---")
    print(f"Min Amount: ${min(all_amounts):.4f}")
    print(f"Max Amount: ${max(all_amounts):.4f}")
    print(f"Mean Amount: ${pd.Series(all_amounts).mean():.2f}")
    print(f"Median Amount: ${pd.Series(all_amounts).median():.2f}")
    print(f"Std Dev: ${pd.Series(all_amounts).std():.2f}")
    
    # Percentiles
    print(f"\n--- Percentiles ---")
    for p in [10, 25, 50, 75, 90, 95, 99]:
        val = pd.Series(all_amounts).quantile(p/100)
        print(f"{p}th percentile: ${val:.2f}")
    
    # Distribution analysis
    print(f"\n--- Amount Distribution ---")
    bins = [0, 1, 2, 5, 10, 15, 20, 25, 50, 100, float('inf')]
    labels = ['$0-1', '$1-2', '$2-5', '$5-10', '$10-15', '$15-20', '$20-25', '$25-50', '$50-100', '$100+']
    amounts_df['bin'] = pd.cut(amounts_df['amount'], bins=bins, labels=labels, right=False)
    distribution = amounts_df['bin'].value_counts().sort_index()
    
    for bin_label, count in distribution.items():
        pct = (count / len(amounts_df)) * 100
        print(f"{bin_label}: {count} trades ({pct:.1f}%)")
    
    # Check if amounts are "round" numbers
    print(f"\n--- Round Number Analysis ---")
    round_amounts = [a for a in all_amounts if a % 1 == 0 or a % 0.5 == 0 or a % 0.25 == 0]
    print(f"Round amounts (whole, 0.5, 0.25): {len(round_amounts)} ({len(round_amounts)/len(all_amounts)*100:.1f}%)")
    print(f"Non-round amounts: {len(all_amounts) - len(round_amounts)} ({(len(all_amounts) - len(round_amounts))/len(all_amounts)*100:.1f}%)")
    
    # Show examples of non-round amounts
    non_round = [a for a in all_amounts if a not in round_amounts]
    if non_round:
        print(f"\n--- Examples of Non-Round Amounts ---")
        for amount in sorted(set(non_round))[:20]:
            # Find a trade with this amount
            example = amounts_df[amounts_df['amount'] == amount].iloc[0]
            print(f"${amount:.4f} - {example['shares']:.2f} shares @ ${example['price']:.3f} ({example['outcome']})")
    
    # Check for maximum cap
    print(f"\n--- Maximum Amount Analysis ---")
    max_amount = max(all_amounts)
    trades_at_max = [a for a in all_amounts if a >= max_amount * 0.95]  # Within 5% of max
    print(f"Maximum amount: ${max_amount:.4f}")
    print(f"Trades near max (>= 95% of max): {len(trades_at_max)}")
    
    # Check if there's a pattern around $20
    print(f"\n--- $20 Cap Analysis ---")
    trades_over_20 = [a for a in all_amounts if a > 20]
    trades_at_20 = [a for a in all_amounts if 19.5 <= a <= 20.5]
    print(f"Trades > $20: {len(trades_over_20)}")
    print(f"Trades at ~$20 (19.5-20.5): {len(trades_at_20)}")
    if trades_over_20:
        print(f"Examples of trades > $20:")
        for amount in sorted(set(trades_over_20))[:10]:
            example = amounts_df[amounts_df['amount'] == amount].iloc[0]
            print(f"  ${amount:.4f} - {example['shares']:.2f} shares @ ${example['price']:.3f}")
    
    # Analyze by outcome (UP vs DOWN)
    print(f"\n--- Amount by Outcome ---")
    for outcome in ['Up', 'Down']:
        outcome_amounts = amounts_df[amounts_df['outcome'] == outcome]['amount']
        print(f"\n{outcome}:")
        print(f"  Count: {len(outcome_amounts)}")
        print(f"  Mean: ${outcome_amounts.mean():.2f}")
        print(f"  Median: ${outcome_amounts.median():.2f}")
        print(f"  Max: ${outcome_amounts.max():.4f}")
    
    print("\n" + "=" * 80)

if __name__ == "__main__":
    analyze_gabagool_amounts()

