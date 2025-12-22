"""
Analyze losing markets to understand why we have high imbalance.
Looks at:
1. Price movement patterns
2. When we built position
3. When market moved against us
4. Why rebalancing failed
"""

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.backends.backend_pdf
from glob import glob
from datetime import datetime
import csv
from pathlib import Path

# Configure matplotlib
plt.rcParams.update({
    'font.family': 'serif',
    'font.serif': ['Times New Roman'],
    'font.size': 10,
    'axes.labelsize': 12,
    'axes.titlesize': 14,
    'xtick.labelsize': 10,
    'ytick.labelsize': 10,
    'legend.fontsize': 10,
    'figure.titlesize': 16,
    'lines.linewidth': 1.5,
    'axes.edgecolor': '0.8',
    'grid.color': '0.9',
    'grid.linestyle': '--',
    'grid.linewidth': 0.5,
    'axes.facecolor': 'white',
    'figure.facecolor': 'white',
    'savefig.dpi': 300,
    'savefig.bbox': 'tight',
})

def load_market_data(csv_path):
    """Load market data and calculate seconds into market"""
    df = pd.read_csv(csv_path)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    market_start_time = df['timestamp'].min()
    df['seconds'] = (df['timestamp'] - market_start_time).dt.total_seconds()
    df['minutes'] = df['seconds'] / 60.0
    
    df['up_best_ask'] = pd.to_numeric(df['up_best_ask'], errors='coerce')
    df['down_best_ask'] = pd.to_numeric(df['down_best_ask'], errors='coerce')
    df['combined'] = df['up_best_ask'] + df['down_best_ask']
    
    df.dropna(subset=['up_best_ask', 'down_best_ask'], inplace=True)
    return df, market_start_time

def load_our_trades(csv_path):
    """Load our bot's trades"""
    if not Path(csv_path).exists():
        return None
    
    trades = []
    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Handle both ISO format and Unix timestamp
            try:
                # Try Unix timestamp first (most common in our CSVs)
                timestamp = pd.to_datetime(float(row['timestamp']), unit='s')
            except:
                # Try ISO format
                try:
                    timestamp = pd.to_datetime(row['timestamp'])
                except:
                    continue
            
            trades.append({
                'timestamp': timestamp,
                'side': row['side'],
                'size': float(row['size']),
                'price': float(row['price']),
                'cost': float(row['cost']),
                'layer': int(row.get('layer', 0))
            })
    
    if not trades:
        return None
    
    df = pd.DataFrame(trades)
    return df

def determine_winner(market_df):
    """Determine market winner from final prices"""
    last_row = market_df.iloc[-1]
    up_price = last_row['up_best_ask']
    down_price = last_row['down_best_ask']
    
    if up_price >= 0.90:
        return 'UP'
    elif down_price >= 0.90:
        return 'DOWN'
    return 'UNKNOWN'

def calculate_position_over_time(trades_df, market_start_time):
    """Calculate our position (shares, costs, balance) over time"""
    if trades_df is None or len(trades_df) == 0:
        return None
    
    trades_df = trades_df.sort_values('timestamp').copy()
    # Ensure both are timezone-naive for subtraction
    if market_start_time.tz is not None:
        market_start_time = market_start_time.tz_localize(None)
    if trades_df['timestamp'].dt.tz is not None:
        trades_df['timestamp'] = trades_df['timestamp'].dt.tz_localize(None)
    
    trades_df['seconds'] = (trades_df['timestamp'] - market_start_time).dt.total_seconds()
    trades_df['minutes'] = trades_df['seconds'] / 60.0
    
    up_shares = 0.0
    down_shares = 0.0
    up_cost = 0.0
    down_cost = 0.0
    
    positions = []
    
    for _, trade in trades_df.iterrows():
        if trade['side'] == 'UP':
            up_shares += trade['size']
            up_cost += trade['cost']
        else:
            down_shares += trade['size']
            down_cost += trade['cost']
        
        total_shares = up_shares + down_shares
        balance_ratio = abs((up_shares / total_shares) - 0.5) * 2.0 if total_shares > 0 else 0.0
        
        total_cost = up_cost + down_cost
        worst_case = min(
            up_shares * 1.0 - total_cost,
            down_shares * 1.0 - total_cost
        )
        
        positions.append({
            'minutes': trade['minutes'],
            'up_shares': up_shares,
            'down_shares': down_shares,
            'up_cost': up_cost,
            'down_cost': down_cost,
            'total_cost': total_cost,
            'balance_ratio': balance_ratio,
            'worst_case': worst_case,
            'layer': trade['layer']
        })
    
    return pd.DataFrame(positions)

def analyze_market(market_csv, trades_csv, pdf):
    """Analyze a single market"""
    market_name = Path(market_csv).stem.replace('_market', '')
    print(f"\nAnalyzing {market_name}...")
    
    # Load data
    market_df, market_start_time = load_market_data(market_csv)
    trades_df = load_our_trades(trades_csv)
    winner = determine_winner(market_df)
    
    if trades_df is None or len(trades_df) == 0:
        print(f"  No trades found for {market_name}")
        return
    
    # Use first market data timestamp as reference (more reliable alignment)
    market_start_ref = market_df['timestamp'].iloc[0]
    position_df = calculate_position_over_time(trades_df, market_start_ref)
    if position_df is None:
        return
    
    # Calculate final metrics
    final_pos = position_df.iloc[-1]
    total_trades = len(trades_df)
    
    # Determine if we won or lost
    total_cost = final_pos['total_cost']
    profit_if_up = final_pos['up_shares'] * 1.0 - total_cost
    profit_if_down = final_pos['down_shares'] * 1.0 - total_cost
    actual_profit = profit_if_up if winner == 'UP' else profit_if_down if winner == 'DOWN' else None
    
    won = actual_profit is not None and actual_profit > 0
    
    profit_str = f"${actual_profit:.2f}" if actual_profit is not None else "N/A"
    print(f"  Winner: {winner}, Our Profit: {profit_str}, Won: {won}")
    print(f"  Total Trades: {total_trades}, Final Balance: {final_pos['balance_ratio']:.3f}")
    print(f"  Final Worst Case: ${final_pos['worst_case']:.2f}")
    
    # Only analyze losing markets
    if not won or actual_profit is None:
        print(f"  *** LOSING MARKET - Analyzing patterns ***")
        
        # Create analysis plots
        fig, axes = plt.subplots(3, 1, figsize=(12, 10))
        
        # Plot 1: Price movement over time
        ax1 = axes[0]
        ax1.plot(market_df['minutes'], market_df['up_best_ask'], label='UP Price', color='blue', alpha=0.7)
        ax1.plot(market_df['minutes'], market_df['down_best_ask'], label='DOWN Price', color='red', alpha=0.7)
        ax1.axhline(y=0.50, color='gray', linestyle='--', linewidth=0.8, alpha=0.5)
        ax1.set_xlabel('Minutes into Market')
        ax1.set_ylabel('Price')
        ax1.set_title(f'{market_name} - Price Movement (Winner: {winner})')
        ax1.legend()
        ax1.grid(True, alpha=0.3)
        
        # Mark our trades
        if len(trades_df) > 0:
            market_start_ref = market_df['timestamp'].iloc[0]
            if market_start_ref.tz is not None:
                market_start_ref = market_start_ref.tz_localize(None)
            for _, trade in trades_df.iterrows():
                trade_ts = trade['timestamp']
                if trade_ts.tz is not None:
                    trade_ts = trade_ts.tz_localize(None)
                trade_minutes = (trade_ts - market_start_ref).total_seconds() / 60.0
                if trade_minutes < 0 or trade_minutes > 15:
                    continue  # Skip trades outside market window
                price = market_df[market_df['minutes'] <= trade_minutes]['up_best_ask'].iloc[-1] if trade['side'] == 'UP' else market_df[market_df['minutes'] <= trade_minutes]['down_best_ask'].iloc[-1]
                color = 'blue' if trade['side'] == 'UP' else 'red'
                marker = '^' if trade['layer'] == 1 else 'v'
                ax1.scatter(trade_minutes, price, color=color, marker=marker, s=30, alpha=0.6, edgecolors='black', linewidths=0.5)
        
        # Plot 2: Our position over time
        ax2 = axes[1]
        ax2.plot(position_df['minutes'], position_df['up_shares'], label='UP Shares', color='blue', alpha=0.7)
        ax2.plot(position_df['minutes'], position_df['down_shares'], label='DOWN Shares', color='red', alpha=0.7)
        ax2.set_xlabel('Minutes into Market')
        ax2.set_ylabel('Shares')
        ax2.set_title('Our Position Over Time')
        ax2.legend()
        ax2.grid(True, alpha=0.3)
        
        # Plot 3: Balance ratio and worst case over time
        ax3 = axes[2]
        ax3_twin = ax3.twinx()
        
        line1 = ax3.plot(position_df['minutes'], position_df['balance_ratio'], label='Balance Ratio', color='green', linewidth=2)
        line2 = ax3_twin.plot(position_df['minutes'], position_df['worst_case'], label='Worst Case Profit', color='orange', linewidth=2)
        
        ax3.axhline(y=0.15, color='red', linestyle='--', linewidth=1, alpha=0.5, label='15% Imbalance Threshold')
        ax3_twin.axhline(y=-100, color='red', linestyle='--', linewidth=1, alpha=0.5, label='MAX_LOSS Limit')
        
        ax3.set_xlabel('Minutes into Market')
        ax3.set_ylabel('Balance Ratio', color='green')
        ax3_twin.set_ylabel('Worst Case Profit ($)', color='orange')
        ax3.set_title('Balance Ratio and Risk Over Time')
        
        # Combine legends
        lines = line1 + line2
        labels = [l.get_label() for l in lines]
        ax3.legend(lines, labels, loc='upper left')
        ax3.grid(True, alpha=0.3)
        
        plt.tight_layout()
        pdf.savefig(fig)
        plt.close()
        
        # Print key insights
        print(f"\n  KEY INSIGHTS:")
        
        # When did imbalance start?
        high_imbalance = position_df[position_df['balance_ratio'] > 0.15]
        if len(high_imbalance) > 0:
            first_imbalance = high_imbalance.iloc[0]
            print(f"  - First high imbalance (>15%) at {first_imbalance['minutes']:.1f} minutes")
            print(f"    Position: {first_imbalance['up_shares']:.0f} UP, {first_imbalance['down_shares']:.0f} DOWN")
        
        # When did we hit MAX_LOSS?
        near_max_loss = position_df[position_df['worst_case'] <= -95]
        if len(near_max_loss) > 0:
            first_max_loss = near_max_loss.iloc[0]
            print(f"  - Hit near MAX_LOSS (-$95) at {first_max_loss['minutes']:.1f} minutes")
            print(f"    Balance at that time: {first_max_loss['balance_ratio']:.3f}")
            print(f"    Could we rebalance? {'NO - blocked by safety check' if first_max_loss['worst_case'] <= -99 else 'YES - but restrictions prevented it'}")
        
        # Price movement analysis
        early_prices = market_df[market_df['minutes'] <= 5]
        late_prices = market_df[market_df['minutes'] >= 10]
        
        if len(early_prices) > 0 and len(late_prices) > 0:
            early_up_avg = early_prices['up_best_ask'].mean()
            early_down_avg = early_prices['down_best_ask'].mean()
            late_up_avg = late_prices['up_best_ask'].mean()
            late_down_avg = late_prices['down_best_ask'].mean()
            
            early_winner = 'UP' if early_up_avg > 0.50 else 'DOWN'
            late_winner = 'UP' if late_up_avg > 0.50 else 'DOWN'
            
            print(f"  - Early market (0-5 min): {early_winner} favored ({early_up_avg:.3f} vs {early_down_avg:.3f})")
            print(f"  - Late market (10-15 min): {late_winner} favored ({late_up_avg:.3f} vs {late_down_avg:.3f})")
            
            if early_winner != late_winner:
                print(f"  - *** MARKET REVERSED from {early_winner} to {late_winner} ***")
            elif early_winner != winner:
                print(f"  - *** Market favored {early_winner} but {winner} won (late reversal) ***")
        
        # Trade distribution
        layer1_trades = trades_df[trades_df['layer'] == 1]
        layer2_trades = trades_df[trades_df['layer'] == 2]
        print(f"  - Layer 1 trades: {len(layer1_trades)} ({len(layer1_trades)/total_trades*100:.1f}%)")
        print(f"  - Layer 2 trades: {len(layer2_trades)} ({len(layer2_trades)/total_trades*100:.1f}%)")
        
        # When did we stop trading?
        if len(trades_df) > 0:
            last_trade = trades_df.iloc[-1]
            # Use market_start_ref for consistency
            market_start_ref = market_df['timestamp'].iloc[0]
            if market_start_ref.tz is not None:
                market_start_ref = market_start_ref.tz_localize(None)
            if last_trade['timestamp'].tz is not None:
                last_trade_ts = last_trade['timestamp'].tz_localize(None)
            else:
                last_trade_ts = last_trade['timestamp']
            last_trade_minutes = (last_trade_ts - market_start_ref).total_seconds() / 60.0
            print(f"  - Last trade at {last_trade_minutes:.1f} minutes (market ends at 15.0)")
            if last_trade_minutes < 12:
                print(f"  - *** STOPPED TRADING EARLY - likely blocked by restrictions ***")

def main():
    """Analyze all markets and focus on losing ones"""
    print("=" * 80)
    print("LOSING MARKET ANALYSIS")
    print("=" * 80)
    
    market_files = glob('testing_data/btc-15m_*_market.csv')
    market_files.sort()
    
    losing_markets = []
    
    # First pass: identify losing markets
    for market_file in market_files:
        market_name = Path(market_file).stem.replace('_market', '')
        trades_file = market_file.replace('_market.csv', '_marketpapertrades.csv')
        
        if not Path(trades_file).exists():
            continue
        
        market_df, _ = load_market_data(market_file)
        trades_df = load_our_trades(trades_file)
        winner = determine_winner(market_df)
        
        if trades_df is None or len(trades_df) == 0:
            continue
        
        position_df = calculate_position_over_time(trades_df, market_df['timestamp'].min())
        if position_df is None:
            continue
        
        final_pos = position_df.iloc[-1]
        total_cost = final_pos['total_cost']
        profit_if_up = final_pos['up_shares'] * 1.0 - total_cost
        profit_if_down = final_pos['down_shares'] * 1.0 - total_cost
        actual_profit = profit_if_up if winner == 'UP' else profit_if_down if winner == 'DOWN' else None
        
        if actual_profit is not None and actual_profit <= 0:
            losing_markets.append((market_file, trades_file, actual_profit, final_pos['balance_ratio']))
    
    print(f"\nFound {len(losing_markets)} losing markets")
    print("=" * 80)
    
    if not losing_markets:
        print("No losing markets found. All markets were profitable!")
        return
    
    # Sort by loss amount
    losing_markets.sort(key=lambda x: x[2])
    
    # Analyze each losing market
    output_path = 'testing_data/losing_markets_analysis.pdf'
    with matplotlib.backends.backend_pdf.PdfPages(output_path) as pdf:
        for market_file, trades_file, profit, balance_ratio in losing_markets:
            analyze_market(market_file, trades_file, pdf)
    
    print(f"\n" + "=" * 80)
    print(f"Analysis complete! Saved to {output_path}")
    print("=" * 80)
    
    # Summary statistics
    print(f"\nSUMMARY:")
    print(f"  Total losing markets: {len(losing_markets)}")
    print(f"  Average loss: ${sum(x[2] for x in losing_markets) / len(losing_markets):.2f}")
    print(f"  Average balance ratio: {sum(x[3] for x in losing_markets) / len(losing_markets):.3f}")
    print(f"  Markets with balance > 0.15: {sum(1 for x in losing_markets if x[3] > 0.15)}")

if __name__ == "__main__":
    main()

