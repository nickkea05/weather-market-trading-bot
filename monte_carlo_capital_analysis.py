"""
Monte Carlo simulation to analyze capital requirements for the trading strategy.
Simulates running the strategy with limited capital and tracks:
- Probability of survival (not going broke)
- Maximum drawdown
- Required starting capital
- Win/loss streaks
"""

import subprocess
import re
import glob
import random
from pathlib import Path
from collections import defaultdict

def run_market(market_csv, gabagool_csv):
    """Run paper trade replay and extract profit and cost"""
    try:
        result = subprocess.run(
            ['python', 'src/paper_trade_replay.py', market_csv, gabagool_csv],
            capture_output=True,
            text=True,
            timeout=120
        )
        
        output = result.stdout
        
        # Extract our bot's actual profit
        our_profit_matches = list(re.finditer(r'ACTUAL PROFIT:\s+\$?([-\d.]+)', output))
        if not our_profit_matches:
            return None
        
        profit = float(our_profit_matches[0].group(1))
        
        # Extract total cost
        total_cost_match = re.search(r'Total Cost:\s+\$?([\d.]+)', output)
        total_cost = float(total_cost_match.group(1)) if total_cost_match else 0.0
        
        return {
            'profit': profit,
            'cost': total_cost
        }
            
    except Exception as e:
        return None

def load_all_market_results():
    """Load results from all markets"""
    market_files = sorted(glob.glob('testing_data/*_market.csv'))
    results = []
    
    for market_csv in market_files:
        market_name = Path(market_csv).stem.replace('_market', '')
        gabagool_csv = f'testing_data/{market_name}_gabagool.csv'
        
        if not Path(gabagool_csv).exists():
            continue
        
        result = run_market(market_csv, gabagool_csv)
        if result:
            results.append(result)
    
    return results

def monte_carlo_simulation(market_results, starting_balance, min_balance, num_simulations=1000):
    """
    Run Monte Carlo simulation
    
    Args:
        market_results: List of {profit, cost} dicts from historical markets
        starting_balance: Initial capital
        min_balance: Minimum balance before stopping (safety threshold)
        num_simulations: Number of simulation runs
    """
    print(f"\n{'='*80}")
    print(f"MONTE CARLO SIMULATION")
    print(f"{'='*80}")
    print(f"Starting Balance: ${starting_balance:,.2f}")
    print(f"Minimum Balance (stop trading): ${min_balance:,.2f}")
    print(f"Number of Simulations: {num_simulations:,}")
    print(f"Historical Markets: {len(market_results)}")
    print(f"{'='*80}\n")
    
    # Statistics to track
    survived = 0
    went_broke = 0
    final_balances = []
    max_drawdowns = []
    max_costs_per_market = []
    markets_traded = []
    worst_balances = []
    max_consecutive_losses_list = []
    
    for sim in range(num_simulations):
        balance = starting_balance
        peak_balance = starting_balance
        max_drawdown = 0
        markets_completed = 0
        max_cost_in_sim = 0
        
        # Create a longer sequence by repeating markets (simulates trading many markets)
        # This gives us more realistic scenarios with longer loss streaks
        extended_markets = market_results * 3  # Trade 3 cycles of markets (48 total)
        random.shuffle(extended_markets)
        
        # Track worst consecutive losses
        consecutive_losses = 0
        max_consecutive_losses = 0
        worst_balance = balance
        
        # Trade through markets until we run out of capital or markets
        for market in extended_markets:
            # Check if we have enough capital
            if balance < min_balance:
                break
            
            # Check if we can afford this market
            if balance < market['cost']:
                # Skip this market if we can't afford it
                continue
            
            # Execute trade
            balance += market['profit']  # profit can be negative
            markets_completed += 1
            
            # Track worst balance
            if balance < worst_balance:
                worst_balance = balance
            
            # Track consecutive losses
            if market['profit'] < 0:
                consecutive_losses += 1
                if consecutive_losses > max_consecutive_losses:
                    max_consecutive_losses = consecutive_losses
            else:
                consecutive_losses = 0
            
            # Track max cost
            if market['cost'] > max_cost_in_sim:
                max_cost_in_sim = market['cost']
            
            # Track peak and drawdown
            if balance > peak_balance:
                peak_balance = balance
            
            drawdown = peak_balance - balance
            if drawdown > max_drawdown:
                max_drawdown = drawdown
        
        # Record results
        final_balances.append(balance)
        max_drawdowns.append(max_drawdown)
        max_costs_per_market.append(max_cost_in_sim)
        markets_traded.append(markets_completed)
        worst_balances.append(worst_balance)
        max_consecutive_losses_list.append(max_consecutive_losses)
        
        if balance >= min_balance:
            survived += 1
        else:
            went_broke += 1
    
    # Calculate statistics
    survival_rate = (survived / num_simulations) * 100
    avg_final_balance = sum(final_balances) / len(final_balances)
    avg_max_drawdown = sum(max_drawdowns) / len(max_drawdowns)
    worst_drawdown = max(max_drawdowns)
    avg_markets_traded = sum(markets_traded) / len(markets_traded)
    max_cost_ever = max(max_costs_per_market)
    avg_max_cost = sum(max_costs_per_market) / len(max_costs_per_market)
    avg_worst_balance = sum(worst_balances) / len(worst_balances)
    absolute_worst_balance = min(worst_balances)
    avg_max_consecutive_losses = sum(max_consecutive_losses_list) / len(max_consecutive_losses_list)
    worst_consecutive_losses = max(max_consecutive_losses_list)
    
    # Percentiles
    final_balances_sorted = sorted(final_balances)
    p10_balance = final_balances_sorted[int(len(final_balances_sorted) * 0.10)]
    p50_balance = final_balances_sorted[int(len(final_balances_sorted) * 0.50)]
    p90_balance = final_balances_sorted[int(len(final_balances_sorted) * 0.90)]
    
    print(f"RESULTS:")
    print(f"{'='*80}")
    print(f"Survival Rate: {survival_rate:.1f}% ({survived:,}/{num_simulations:,})")
    print(f"Went Broke: {went_broke:,} ({100-survival_rate:.1f}%)")
    print(f"\nAverage Final Balance: ${avg_final_balance:,.2f}")
    print(f"Median Final Balance (P50): ${p50_balance:,.2f}")
    print(f"10th Percentile: ${p10_balance:,.2f}")
    print(f"90th Percentile: ${p90_balance:,.2f}")
    print(f"\nAverage Markets Traded: {avg_markets_traded:.1f}")
    print(f"\nAverage Max Drawdown: ${avg_max_drawdown:,.2f}")
    print(f"Worst Drawdown: ${worst_drawdown:,.2f}")
    print(f"\nWorst Balance Reached:")
    print(f"  Average: ${avg_worst_balance:,.2f}")
    print(f"  Absolute Worst: ${absolute_worst_balance:,.2f}")
    print(f"\nConsecutive Losses:")
    print(f"  Average Max: {avg_max_consecutive_losses:.1f}")
    print(f"  Worst Streak: {worst_consecutive_losses}")
    print(f"\nMaximum Cost Per Market:")
    print(f"  Average: ${avg_max_cost:,.2f}")
    print(f"  Maximum: ${max_cost_ever:,.2f}")
    print(f"{'='*80}\n")
    
    return {
        'survival_rate': survival_rate,
        'avg_final_balance': avg_final_balance,
        'avg_max_drawdown': avg_max_drawdown,
        'max_cost_ever': max_cost_ever,
        'avg_max_cost': avg_max_cost
    }

def find_minimum_capital(market_results, min_balance_threshold=500, target_survival_rate=95):
    """Find minimum starting capital needed for target survival rate"""
    print(f"\n{'='*80}")
    print(f"FINDING MINIMUM CAPITAL REQUIREMENT")
    print(f"{'='*80}")
    print(f"Target Survival Rate: {target_survival_rate}%")
    print(f"Minimum Balance Threshold: ${min_balance_threshold:,.2f}")
    print(f"{'='*80}\n")
    
    # Find max cost to set lower bound
    max_cost = max(m['cost'] for m in market_results)
    print(f"Maximum cost in any market: ${max_cost:,.2f}")
    
    # Binary search for minimum capital
    low = max_cost + min_balance_threshold
    high = max_cost * 5  # Start high
    best_capital = None
    
    print(f"\nTesting capital levels...")
    for test_capital in range(int(low), int(high), 500):
        result = monte_carlo_simulation(market_results, test_capital, min_balance_threshold, num_simulations=500)
        
        if result['survival_rate'] >= target_survival_rate:
            best_capital = test_capital
            print(f"\n{'='*80}")
            print(f"MINIMUM CAPITAL FOUND: ${best_capital:,.2f}")
            print(f"  Survival Rate: {result['survival_rate']:.1f}%")
            print(f"  Max Cost Needed: ${result['max_cost_ever']:,.2f}")
            print(f"{'='*80}")
            break
    
    if not best_capital:
        print(f"\nCould not find capital level with {target_survival_rate}% survival rate")
        print(f"Try increasing the high bound or lowering target survival rate")
    
    return best_capital

def main():
    print("Loading historical market results...")
    market_results = load_all_market_results()
    
    if not market_results:
        print("No market results found!")
        return
    
    # Calculate statistics from historical data
    max_cost = max(m['cost'] for m in market_results)
    avg_cost = sum(m['cost'] for m in market_results) / len(market_results)
    total_profit = sum(m['profit'] for m in market_results)
    wins = [m for m in market_results if m['profit'] > 0]
    losses = [m for m in market_results if m['profit'] <= 0]
    
    print(f"\n{'='*80}")
    print(f"HISTORICAL DATA SUMMARY")
    print(f"{'='*80}")
    print(f"Total Markets: {len(market_results)}")
    print(f"Wins: {len(wins)} ({len(wins)/len(market_results)*100:.1f}%)")
    print(f"Losses: {len(losses)} ({len(losses)/len(market_results)*100:.1f}%)")
    print(f"Total Profit: ${total_profit:,.2f}")
    print(f"\nCost Statistics:")
    print(f"  Average: ${avg_cost:,.2f}")
    print(f"  Maximum: ${max_cost:,.2f}")
    print(f"  Minimum: ${min(m['cost'] for m in market_results):,.2f}")
    print(f"{'='*80}\n")
    
    # Test with $2k starting balance
    print("\n" + "="*80)
    print("TESTING WITH $2,000 STARTING BALANCE")
    print("="*80)
    result_2k = monte_carlo_simulation(market_results, 2000, 1000, num_simulations=1000)
    
    # Test with $3k starting balance
    print("\n" + "="*80)
    print("TESTING WITH $3,000 STARTING BALANCE")
    print("="*80)
    result_3k = monte_carlo_simulation(market_results, 3000, 1500, num_simulations=1000)
    
    # Find minimum capital
    min_capital = find_minimum_capital(market_results, min_balance_threshold=1000, target_survival_rate=95)
    
    print(f"\n{'='*80}")
    print("RECOMMENDATIONS")
    print(f"{'='*80}")
    print(f"Maximum cost per market: ${max_cost:,.2f}")
    print(f"To safely trade, you need at least: ${max_cost + 1000:,.2f}")
    if result_2k['survival_rate'] >= 95:
        print(f"$2,000 starting balance: SAFE (survival rate: {result_2k['survival_rate']:.1f}%)")
    else:
        print(f"$2,000 starting balance: RISKY (survival rate: {result_2k['survival_rate']:.1f}%)")
    if min_capital:
        print(f"Recommended minimum capital: ${min_capital:,.2f}")
    print(f"{'='*80}")

if __name__ == '__main__':
    main()

