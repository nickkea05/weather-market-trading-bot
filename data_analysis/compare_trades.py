"""
Compare our paper trading results with gabagool's trades
"""
import pandas as pd
from pathlib import Path
from typing import Optional

def load_our_trades(csv_path: str) -> pd.DataFrame:
    """Load our paper trading CSV"""
    df = pd.read_csv(csv_path)
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s', errors='coerce')
    return df

def load_gabagool_trades(csv_path: str) -> pd.DataFrame:
    """Load gabagool's trades CSV"""
    df = pd.read_csv(csv_path)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    return df

def calculate_position(trades_df: pd.DataFrame, is_gabagool: bool = False) -> dict:
    """Calculate final position from trades"""
    up_shares = 0.0
    down_shares = 0.0
    up_cost = 0.0
    down_cost = 0.0
    up_prices = []
    down_prices = []
    
    if is_gabagool:
        # Gabagool format: outcome='Up'/'Down', size, usdcSize
        for _, row in trades_df.iterrows():
            outcome = str(row['outcome']).strip()
            size = float(row['size'])
            cost = float(row['usdcSize'])
            price = float(row['price'])
            
            if outcome.lower() == 'up':
                up_shares += size
                up_cost += cost
                up_prices.append(price)
            elif outcome.lower() == 'down':
                down_shares += size
                down_cost += cost
                down_prices.append(price)
    else:
        # Our format: side='UP'/'DOWN', size, cost
        for _, row in trades_df.iterrows():
            side = str(row['side']).strip()
            size = float(row['size'])
            cost = float(row['cost'])
            price = float(row['price'])
            
            if side.upper() == 'UP':
                up_shares += size
                up_cost += cost
                up_prices.append(price)
            elif side.upper() == 'DOWN':
                down_shares += size
                down_cost += cost
                down_prices.append(price)
    
    # Calculate averages
    avg_up_price = sum(up_prices) / len(up_prices) if up_prices else 0.0
    avg_down_price = sum(down_prices) / len(down_prices) if down_prices else 0.0
    
    # Calculate worst/best case profit
    total_cost = up_cost + down_cost
    profit_if_up = up_shares * 1.0 - total_cost
    profit_if_down = down_shares * 1.0 - total_cost
    worst_case = min(profit_if_up, profit_if_down)
    best_case = max(profit_if_up, profit_if_down)
    
    return {
        'up_shares': up_shares,
        'down_shares': down_shares,
        'up_cost': up_cost,
        'down_cost': down_cost,
        'total_cost': total_cost,
        'avg_up_price': avg_up_price,
        'avg_down_price': avg_down_price,
        'profit_if_up': profit_if_up,
        'profit_if_down': profit_if_down,
        'worst_case': worst_case,
        'best_case': best_case,
        'total_trades': len(trades_df)
    }

def determine_winner(market_csv_path: str) -> Optional[str]:
    """Determine winner from market CSV"""
    df = pd.read_csv(market_csv_path)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df = df.sort_values('timestamp')
    
    last_row = df.iloc[-1]
    up_price = float(last_row.get('up_best_ask', 0) or 0)
    down_price = float(last_row.get('down_best_ask', 0) or 0)
    
    if up_price >= 0.90:
        return 'UP'
    elif down_price >= 0.90:
        return 'DOWN'
    else:
        return 'UP' if up_price > down_price else 'DOWN'

def compare_trades(market_csv_path: str, our_trades_csv: str, gabagool_csv: str):
    """Compare our trades with gabagool's"""
    print("=" * 80)
    print("TRADE COMPARISON ANALYSIS")
    print("=" * 80)
    
    # Load trades
    print(f"\n[LOADING] Our trades: {our_trades_csv}")
    our_trades = load_our_trades(our_trades_csv)
    print(f"[LOADING] Gabagool trades: {gabagool_csv}")
    gabagool_trades = load_gabagool_trades(gabagool_csv)
    
    # Calculate positions
    print("\n[CALCULATING] Position metrics...")
    our_pos = calculate_position(our_trades, is_gabagool=False)
    gabagool_pos = calculate_position(gabagool_trades, is_gabagool=True)
    
    # Determine winner
    winner = determine_winner(market_csv_path)
    print(f"\n[WINNER] Market resolved: {winner}")
    
    # Calculate actual profits
    our_actual = our_pos['profit_if_up'] if winner == 'UP' else our_pos['profit_if_down']
    gabagool_actual = gabagool_pos['profit_if_up'] if winner == 'UP' else gabagool_pos['profit_if_down']
    
    # Print comparison
    print("\n" + "=" * 80)
    print("OUR BOT - FINAL POSITION")
    print("=" * 80)
    print(f"Total Trades: {our_pos['total_trades']}")
    print(f"UP Shares: {our_pos['up_shares']:.2f}")
    print(f"DOWN Shares: {our_pos['down_shares']:.2f}")
    print(f"UP Cost: ${our_pos['up_cost']:.2f}")
    print(f"DOWN Cost: ${our_pos['down_cost']:.2f}")
    print(f"Total Cost: ${our_pos['total_cost']:.2f}")
    print(f"UP Average: ${our_pos['avg_up_price']:.3f} ({our_pos['avg_up_price']*100:.1f} cents)")
    print(f"DOWN Average: ${our_pos['avg_down_price']:.3f} ({our_pos['avg_down_price']*100:.1f} cents)")
    print(f"Worst Case Profit: ${our_pos['worst_case']:.2f}")
    print(f"Best Case Profit: ${our_pos['best_case']:.2f}")
    print(f"Actual Profit ({winner} won): ${our_actual:.2f}")
    
    print("\n" + "=" * 80)
    print("GABAGOOL - FINAL POSITION")
    print("=" * 80)
    print(f"Total Trades: {gabagool_pos['total_trades']}")
    print(f"UP Shares: {gabagool_pos['up_shares']:.2f}")
    print(f"DOWN Shares: {gabagool_pos['down_shares']:.2f}")
    print(f"UP Cost: ${gabagool_pos['up_cost']:.2f}")
    print(f"DOWN Cost: ${gabagool_pos['down_cost']:.2f}")
    print(f"Total Cost: ${gabagool_pos['total_cost']:.2f}")
    print(f"UP Average: ${gabagool_pos['avg_up_price']:.3f} ({gabagool_pos['avg_up_price']*100:.1f} cents)")
    print(f"DOWN Average: ${gabagool_pos['avg_down_price']:.3f} ({gabagool_pos['avg_down_price']*100:.1f} cents)")
    print(f"Worst Case Profit: ${gabagool_pos['worst_case']:.2f}")
    print(f"Best Case Profit: ${gabagool_pos['best_case']:.2f}")
    print(f"Actual Profit ({winner} won): ${gabagool_actual:.2f}")
    
    print("\n" + "=" * 80)
    print("COMPARISON METRICS")
    print("=" * 80)
    print(f"Trade Count Ratio: {gabagool_pos['total_trades']} / {our_pos['total_trades']} = {gabagool_pos['total_trades']/our_pos['total_trades']:.2f}x")
    print(f"Total Cost Ratio: ${gabagool_pos['total_cost']:.2f} / ${our_pos['total_cost']:.2f} = {gabagool_pos['total_cost']/our_pos['total_cost']:.2f}x")
    print(f"Profit Difference: ${gabagool_actual - our_actual:.2f}")
    print(f"Profit Ratio: {gabagool_actual/our_actual:.2f}x" if our_actual != 0 else "Profit Ratio: N/A (our profit was $0)")
    
    # Trade size analysis
    if not gabagool_trades.empty:
        our_sizes = our_trades['size'].tolist()
        gabagool_sizes = gabagool_trades['size'].tolist()
        
        print("\n" + "=" * 80)
        print("TRADE SIZE ANALYSIS")
        print("=" * 80)
        print(f"Our Trade Sizes:")
        print(f"  Min: {min(our_sizes):.2f}, Max: {max(our_sizes):.2f}, Avg: {sum(our_sizes)/len(our_sizes):.2f}")
        print(f"  Unique sizes: {sorted(set(our_sizes))}")
        print(f"Gabagool Trade Sizes:")
        print(f"  Min: {min(gabagool_sizes):.2f}, Max: {max(gabagool_sizes):.2f}, Avg: {sum(gabagool_sizes)/len(gabagool_sizes):.2f}")
        print(f"  Unique sizes (first 20): {sorted(set(gabagool_sizes))[:20]}")
    
    print("\n" + "=" * 80)

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 4:
        print("Usage: python compare_trades.py <market_csv> <our_trades_csv> <gabagool_csv>")
        print("\nExample:")
        print("  python compare_trades.py testing_data/btc-15m_11-00pm_11-15pm_1765857600_market.csv \\")
        print("                            testing_data/btc-15m_11-00pm_11-15pm_1765857600_marketpapertrades.csv \\")
        print("                            testing_data/btc-15m_11-00pm_11-15pm_1765857600_gabagool.csv")
        sys.exit(1)
    
    market_csv = sys.argv[1]
    our_trades_csv = sys.argv[2]
    gabagool_csv = sys.argv[3]
    
    compare_trades(market_csv, our_trades_csv, gabagool_csv)

