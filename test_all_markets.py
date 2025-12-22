"""
Test all markets and aggregate profit/loss results
"""

import subprocess
import re
import glob
from pathlib import Path

def run_market(market_csv, gabagool_csv):
    """Run paper trade replay and extract profit and trade stats"""
    try:
        result = subprocess.run(
            ['python', 'src/paper_trade_replay.py', market_csv, gabagool_csv],
            capture_output=True,
            text=True,
            timeout=120
        )
        
        output = result.stdout
        
        # Extract our bot's actual profit (first occurrence, under "OUR BOT")
        our_profit_matches = list(re.finditer(r'ACTUAL PROFIT:\s+\$?([-\d.]+)', output))
        if not our_profit_matches:
            print(f"  WARNING: Could not extract our profit from {market_csv}")
            return None
        
        profit = float(our_profit_matches[0].group(1))
        
        # Extract Gabagool's actual profit (second occurrence, under "GABAGOOL")
        gabagool_profit = None
        if len(our_profit_matches) > 1:
            gabagool_profit = float(our_profit_matches[1].group(1))
        else:
            # Try to find it in the GABAGOOL section specifically
            gabagool_section = re.search(r'GABAGOOL.*?ACTUAL PROFIT:\s+\$?([-\d.]+)', output, re.DOTALL)
            if gabagool_section:
                gabagool_profit = float(gabagool_section.group(1))
        
        # Extract trade counts by type: "ARB: 44, ACCUMULATE: 143, REBALANCE: 33"
        trade_counts_match = re.search(r'ARB:\s*(\d+),\s*ACCUMULATE:\s*(\d+),\s*REBALANCE:\s*(\d+)', output)
        arb_count = int(trade_counts_match.group(1)) if trade_counts_match else 0
        accumulate_count = int(trade_counts_match.group(2)) if trade_counts_match else 0
        rebalance_count = int(trade_counts_match.group(3)) if trade_counts_match else 0
        
        # Extract total shares: "UP Shares: 1500.31" and "DOWN Shares: 1172.70"
        up_shares_match = re.search(r'UP Shares:\s*([\d.]+)', output)
        down_shares_match = re.search(r'DOWN Shares:\s*([\d.]+)', output)
        total_shares = 0
        if up_shares_match and down_shares_match:
            total_shares = float(up_shares_match.group(1)) + float(down_shares_match.group(1))
        
        # Extract averages: "UP Average: $0.478 (47.8 cents)"
        up_avg_match = re.search(r'UP Average:\s+\$?([\d.]+)', output)
        down_avg_match = re.search(r'DOWN Average:\s+\$?([\d.]+)', output)
        up_avg = float(up_avg_match.group(1)) if up_avg_match else 0.0
        down_avg = float(down_avg_match.group(1)) if down_avg_match else 0.0
        
        # Extract total cost: "Total Cost: $1271.00"
        total_cost_match = re.search(r'Total Cost:\s+\$?([\d.]+)', output)
        total_cost = float(total_cost_match.group(1)) if total_cost_match else 0.0
        
        # Find worst case profit (max drawdown) by looking for the lowest MinProfit in trades
        min_profit_values = re.findall(r'MinProfit:\s+\$?\s*([-\d.]+)', output)
        max_drawdown = min([float(v) for v in min_profit_values]) if min_profit_values else 0.0
        
        # Extract Gabagool stats if available
        gabagool_cost = None
        gabagool_trades = None
        if gabagool_profit is not None:
            # Extract Gabagool total cost
            gabagool_cost_match = re.search(r'GABAGOOL.*?Total Cost:\s+\$?([\d.]+)', output, re.DOTALL)
            if gabagool_cost_match:
                gabagool_cost = float(gabagool_cost_match.group(1))
            
            # Extract Gabagool trade count
            gabagool_trades_match = re.search(r'GABAGOOL.*?Total Trades:\s+(\d+)', output, re.DOTALL)
            if gabagool_trades_match:
                gabagool_trades = int(gabagool_trades_match.group(1))
        
        return {
            'profit': profit,
            'gabagool_profit': gabagool_profit,
            'gabagool_cost': gabagool_cost,
            'gabagool_trades': gabagool_trades,
            'arb_count': arb_count,
            'accumulate_count': accumulate_count,
            'rebalance_count': rebalance_count,
            'total_shares': total_shares,
            'up_avg': up_avg,
            'down_avg': down_avg,
            'total_cost': total_cost,
            'max_drawdown': max_drawdown
        }
            
    except subprocess.TimeoutExpired:
        print(f"  TIMEOUT: {market_csv}")
        return None
    except Exception as e:
        print(f"  ERROR: {market_csv} - {e}")
        return None

def main():
    # Find all market CSV files
    market_files = sorted(glob.glob('testing_data/*_market.csv'))
    
    if not market_files:
        print("No market files found!")
        return
    
    print(f"Found {len(market_files)} markets to test")
    print("=" * 80)
    
    results = []
    
    for market_csv in market_files:
        # Find corresponding gabagool file
        market_name = Path(market_csv).stem.replace('_market', '')
        gabagool_csv = f'testing_data/{market_name}_gabagool.csv'
        
        if not Path(gabagool_csv).exists():
            print(f"SKIP: {market_name} (no gabagool file)")
            continue
        
        print(f"\nTesting: {market_name}")
        result = run_market(market_csv, gabagool_csv)
        
        if result is not None:
            results.append({
                'market': market_name,
                'profit': result['profit'],
                'gabagool_profit': result.get('gabagool_profit'),
                'gabagool_cost': result.get('gabagool_cost'),
                'gabagool_trades': result.get('gabagool_trades'),
                'arb_count': result['arb_count'],
                'accumulate_count': result['accumulate_count'],
                'rebalance_count': result['rebalance_count'],
                'total_shares': result['total_shares'],
                'up_avg': result['up_avg'],
                'down_avg': result['down_avg'],
                'total_cost': result['total_cost'],
                'max_drawdown': result['max_drawdown']
            })
            status = "WIN" if result['profit'] > 0 else "LOSS"
            combined_avg = result['up_avg'] + result['down_avg']
            roi = (result['profit'] / result['total_cost'] * 100) if result['total_cost'] > 0 else 0
            
            # Show comparison if Gabagool data available
            if result.get('gabagool_profit') is not None:
                gabagool_status = "WIN" if result['gabagool_profit'] > 0 else "LOSS"
                diff = result['profit'] - result['gabagool_profit']
                print(f"  Result: {status} ${result['profit']:.2f} | ROI: {roi:+.1f}% | MaxDD: ${result['max_drawdown']:.2f}")
                print(f"  Gabagool: {gabagool_status} ${result['gabagool_profit']:.2f} | Diff: ${diff:+.2f}")
            else:
                print(f"  Result: {status} ${result['profit']:.2f} | ROI: {roi:+.1f}% | MaxDD: ${result['max_drawdown']:.2f}")
    
    # Print summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    
    if not results:
        print("No results to summarize")
        return
    
    total_profit = sum(r['profit'] for r in results)
    total_cost = sum(r['total_cost'] for r in results)
    overall_roi = (total_profit / total_cost * 100) if total_cost > 0 else 0
    
    # Calculate Gabagool totals
    gabagool_results = [r for r in results if r.get('gabagool_profit') is not None]
    total_gabagool_profit = sum(r['gabagool_profit'] for r in gabagool_results) if gabagool_results else None
    total_gabagool_cost = sum(r['gabagool_cost'] for r in gabagool_results) if gabagool_results and all(r.get('gabagool_cost') for r in gabagool_results) else None
    gabagool_overall_roi = (total_gabagool_profit / total_gabagool_cost * 100) if total_gabagool_cost and total_gabagool_cost > 0 else None
    
    wins = [r for r in results if r['profit'] > 0]
    losses = [r for r in results if r['profit'] <= 0]
    gabagool_wins = [r for r in gabagool_results if r['gabagool_profit'] > 0] if gabagool_results else []
    gabagool_losses = [r for r in gabagool_results if r['gabagool_profit'] <= 0] if gabagool_results else []
    
    print(f"\nTotal Markets: {len(results)}")
    if gabagool_results:
        print(f"Markets with Gabagool data: {len(gabagool_results)}")
    print(f"\n--- OUR BOT ---")
    print(f"Wins: {len(wins)}")
    print(f"Losses: {len(losses)}")
    print(f"Win Rate: {len(wins)/len(results)*100:.1f}%")
    print(f"\nTotal P&L: ${total_profit:.2f}")
    print(f"Total Cost: ${total_cost:.2f}")
    print(f"Overall ROI: {overall_roi:+.2f}%")
    print(f"Average P&L per market: ${total_profit/len(results):.2f}")
    
    if gabagool_results:
        print(f"\n--- GABAGOOL ---")
        print(f"Wins: {len(gabagool_wins)}")
        print(f"Losses: {len(gabagool_losses)}")
        print(f"Win Rate: {len(gabagool_wins)/len(gabagool_results)*100:.1f}%")
        print(f"\nTotal P&L: ${total_gabagool_profit:.2f}")
        if total_gabagool_cost:
            print(f"Total Cost: ${total_gabagool_cost:.2f}")
            print(f"Overall ROI: {gabagool_overall_roi:+.2f}%")
        print(f"Average P&L per market: ${total_gabagool_profit/len(gabagool_results):.2f}")
        print(f"\n--- COMPARISON ---")
        profit_diff = total_profit - total_gabagool_profit
        print(f"Profit Difference: ${profit_diff:+.2f} ({'+' if profit_diff > 0 else ''}{profit_diff/total_gabagool_profit*100:.1f}%)" if total_gabagool_profit != 0 else f"Profit Difference: ${profit_diff:+.2f}")
    
    if wins:
        avg_win = sum(r['profit'] for r in wins) / len(wins)
        avg_win_roi = sum((r['profit'] / r['total_cost'] * 100) for r in wins) / len(wins)
        print(f"Average Win: ${avg_win:.2f} ({avg_win_roi:+.1f}% ROI)")
    
    if losses:
        avg_loss = sum(r['profit'] for r in losses) / len(losses)
        avg_loss_roi = sum((r['profit'] / r['total_cost'] * 100) for r in losses) / len(losses)
        print(f"Average Loss: ${avg_loss:.2f} ({avg_loss_roi:.1f}% ROI)")
    
    # Max drawdown stats
    avg_max_drawdown = sum(r['max_drawdown'] for r in results) / len(results)
    worst_drawdown = min(r['max_drawdown'] for r in results)
    print(f"\nAverage Max Drawdown: ${avg_max_drawdown:.2f}")
    print(f"Worst Drawdown: ${worst_drawdown:.2f}")
    
    # Trade statistics
    avg_arb = sum(r['arb_count'] for r in results) / len(results)
    avg_accumulate = sum(r['accumulate_count'] for r in results) / len(results)
    avg_rebalance = sum(r['rebalance_count'] for r in results) / len(results)
    avg_total_trades = avg_arb + avg_accumulate + avg_rebalance
    avg_shares = sum(r['total_shares'] for r in results) / len(results)
    
    # Average prices
    avg_up_avg = sum(r['up_avg'] for r in results) / len(results)
    avg_down_avg = sum(r['down_avg'] for r in results) / len(results)
    avg_combined = avg_up_avg + avg_down_avg
    
    print(f"\n--- TRADE STATISTICS (Average per market) ---")
    print(f"Total Trades: {avg_total_trades:.1f}")
    print(f"  ARB: {avg_arb:.1f} ({avg_arb/avg_total_trades*100:.1f}%)")
    print(f"  ACCUMULATE: {avg_accumulate:.1f} ({avg_accumulate/avg_total_trades*100:.1f}%)")
    print(f"  REBALANCE: {avg_rebalance:.1f} ({avg_rebalance/avg_total_trades*100:.1f}%)")
    print(f"Total Shares: {avg_shares:.1f}")
    print(f"\n--- AVERAGE PRICES ---")
    print(f"UP Average: ${avg_up_avg:.3f}")
    print(f"DOWN Average: ${avg_down_avg:.3f}")
    print(f"Combined Average: ${avg_combined:.3f} ({'PROFIT' if avg_combined < 1.0 else 'LOSS'} position)")
    
    # Show all results
    print("\n" + "=" * 80)
    print("DETAILED RESULTS")
    print("=" * 80)
    
    for r in sorted(results, key=lambda x: x['profit'], reverse=True):
        status = "WIN " if r['profit'] > 0 else "LOSS"
        if r.get('gabagool_profit') is not None:
            gabagool_status = "WIN " if r['gabagool_profit'] > 0 else "LOSS"
            diff = r['profit'] - r['gabagool_profit']
            print(f"{status} ${r['profit']:8.2f} | {gabagool_status} ${r['gabagool_profit']:8.2f} | Diff: ${diff:+.2f} - {r['market']}")
        else:
            print(f"{status} ${r['profit']:8.2f} - {r['market']}")
    
    print("\n" + "=" * 80)
    if total_profit > 0:
        print(f"OUR BOT - NET POSITIVE: ${total_profit:.2f}")
    else:
        print(f"OUR BOT - NET NEGATIVE: ${total_profit:.2f}")
    
    if total_gabagool_profit is not None:
        if total_gabagool_profit > 0:
            print(f"GABAGOOL - NET POSITIVE: ${total_gabagool_profit:.2f}")
        else:
            print(f"GABAGOOL - NET NEGATIVE: ${total_gabagool_profit:.2f}")
        profit_diff = total_profit - total_gabagool_profit
        print(f"DIFFERENCE: ${profit_diff:+.2f}")
    print("=" * 80)

if __name__ == '__main__':
    main()

