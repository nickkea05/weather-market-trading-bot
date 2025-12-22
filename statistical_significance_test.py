"""
Statistical significance test for trading strategy profitability.
Tests if the observed profit is statistically significant given n=16 markets.
"""

import subprocess
import re
import glob
import numpy as np
from scipy import stats
from pathlib import Path

def run_market(market_csv, gabagool_csv):
    """Run paper trade replay and extract profit"""
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
        
        # Extract total cost for ROI calculation
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
            results.append(result['profit'])
    
    return results

def statistical_analysis(profits):
    """
    Perform statistical significance testing
    
    Tests:
    1. One-sample t-test: H0: mean = 0 vs H1: mean > 0
    2. Confidence intervals
    3. Power analysis
    4. Sample size requirements
    """
    profits = np.array(profits)
    n = len(profits)
    mean_profit = np.mean(profits)
    std_profit = np.std(profits, ddof=1)  # Sample standard deviation
    se = std_profit / np.sqrt(n)  # Standard error
    
    print(f"\n{'='*80}")
    print(f"STATISTICAL SIGNIFICANCE ANALYSIS")
    print(f"{'='*80}")
    print(f"Sample Size (n): {n}")
    print(f"Mean Profit: ${mean_profit:.2f}")
    print(f"Standard Deviation: ${std_profit:.2f}")
    print(f"Standard Error: ${se:.2f}")
    print(f"{'='*80}\n")
    
    # 1. One-sample t-test (one-tailed: is mean > 0?)
    t_statistic = mean_profit / se
    p_value = 1 - stats.t.cdf(t_statistic, df=n-1)  # One-tailed p-value
    
    print(f"HYPOTHESIS TEST:")
    print(f"  Null Hypothesis (H0): True mean profit = $0 (not profitable)")
    print(f"  Alternative Hypothesis (H1): True mean profit > $0 (profitable)")
    print(f"  Test: One-sample t-test (one-tailed)")
    print(f"  t-statistic: {t_statistic:.4f}")
    print(f"  p-value: {p_value:.6f}")
    
    # Significance levels
    alpha_05 = 0.05
    alpha_01 = 0.01
    alpha_001 = 0.001
    
    print(f"\n  Significance Levels:")
    if p_value < alpha_001:
        print(f"    *** p < 0.001 (HIGHLY SIGNIFICANT) ***")
    elif p_value < alpha_01:
        print(f"    ** p < 0.01 (VERY SIGNIFICANT) **")
    elif p_value < alpha_05:
        print(f"    * p < 0.05 (SIGNIFICANT) *")
    else:
        print(f"    p >= 0.05 (NOT SIGNIFICANT)")
    
    print(f"\n  Interpretation:")
    if p_value < alpha_05:
        print(f"    We reject H0. The strategy is statistically profitable.")
        print(f"    There is {100*(1-p_value):.1f}% confidence the strategy is profitable.")
    else:
        print(f"    We fail to reject H0. Not enough evidence of profitability.")
    
    # 2. Confidence Intervals
    print(f"\n{'='*80}")
    print(f"CONFIDENCE INTERVALS")
    print(f"{'='*80}")
    
    for confidence in [0.90, 0.95, 0.99]:
        alpha = 1 - confidence
        t_critical = stats.t.ppf(1 - alpha/2, df=n-1)  # Two-tailed
        margin = t_critical * se
        ci_lower = mean_profit - margin
        ci_upper = mean_profit + margin
        
        print(f"\n  {confidence*100:.0f}% Confidence Interval:")
        print(f"    Lower bound: ${ci_lower:.2f}")
        print(f"    Upper bound: ${ci_upper:.2f}")
        print(f"    Range: ${ci_upper - ci_lower:.2f}")
        
        if ci_lower > 0:
            print(f"    [OK] Entire interval is positive (profitable)")
        elif ci_upper < 0:
            print(f"    [X] Entire interval is negative (unprofitable)")
        else:
            print(f"    [!] Interval crosses zero (uncertain)")
    
    # 3. Effect Size (Cohen's d)
    cohens_d = mean_profit / std_profit if std_profit > 0 else 0
    print(f"\n{'='*80}")
    print(f"EFFECT SIZE")
    print(f"{'='*80}")
    print(f"  Cohen's d: {cohens_d:.4f}")
    if abs(cohens_d) < 0.2:
        effect_size = "negligible"
    elif abs(cohens_d) < 0.5:
        effect_size = "small"
    elif abs(cohens_d) < 0.8:
        effect_size = "medium"
    else:
        effect_size = "large"
    print(f"  Effect size: {effect_size}")
    
    # 4. Sample Size Requirements
    print(f"\n{'='*80}")
    print(f"SAMPLE SIZE ANALYSIS")
    print(f"{'='*80}")
    
    # How many samples needed for 95% confidence with 80% power?
    # Using formula: n = (Z_alpha + Z_beta)^2 * (std^2) / (mean^2)
    z_alpha = stats.norm.ppf(0.95)  # 1.645 for one-tailed 95%
    z_beta = stats.norm.ppf(0.80)   # 0.84 for 80% power
    
    if mean_profit > 0:
        required_n = ((z_alpha + z_beta) ** 2) * (std_profit ** 2) / (mean_profit ** 2)
        print(f"  Required sample size for 95% confidence, 80% power:")
        print(f"    n = {required_n:.0f} markets")
        print(f"    Current: {n} markets")
        print(f"    Need: {max(0, int(required_n - n))} more markets")
    
    # 5. Risk Assessment
    print(f"\n{'='*80}")
    print(f"RISK ASSESSMENT")
    print(f"{'='*80}")
    
    # Probability of negative profit in next market
    if std_profit > 0:
        z_score_negative = (0 - mean_profit) / std_profit
        prob_negative = stats.norm.cdf(z_score_negative)
        print(f"  Probability of loss in next market: {prob_negative*100:.1f}%")
    
    # Probability of being unprofitable after N more markets
    print(f"\n  Probability of being unprofitable after N more markets:")
    for N in [10, 20, 50, 96]:
        # Using normal approximation
        future_mean = N * mean_profit
        future_std = np.sqrt(N) * std_profit
        if future_std > 0:
            z = (0 - future_mean) / future_std
            prob_unprofitable = stats.norm.cdf(z)
            print(f"    After {N} markets: {prob_unprofitable*100:.1f}%")
    
    # 6. Recommendations
    print(f"\n{'='*80}")
    print(f"RECOMMENDATIONS")
    print(f"{'='*80}")
    
    if p_value < 0.05:
        print(f"  [OK] Results are statistically significant (p = {p_value:.4f})")
        print(f"  [OK] Strategy shows evidence of profitability")
    else:
        print(f"  [!] Results are NOT statistically significant (p = {p_value:.4f})")
        print(f"  [!] Need more data to confirm profitability")
    
    if n < 30:
        print(f"  [!] Sample size (n={n}) is small. More data recommended.")
        if mean_profit > 0:
            print(f"  -> Run full day test (96 markets) for better confidence")
    
    if ci_lower < 0:
        print(f"  [!] Confidence interval includes negative values")
        print(f"  -> True profitability is uncertain")
    
    print(f"\n  Suggested next steps:")
    print(f"    1. Run full day paper trading (96 markets)")
    print(f"    2. Monitor for at least 1 week (672 markets)")
    print(f"    3. Track performance metrics over time")
    print(f"    4. Re-run statistical tests with larger sample")
    
    return {
        'n': n,
        'mean': mean_profit,
        'std': std_profit,
        't_statistic': t_statistic,
        'p_value': p_value,
        'ci_95_lower': ci_lower,
        'ci_95_upper': ci_upper,
        'cohens_d': cohens_d
    }

def main():
    print("Loading historical market results...")
    profits = load_all_market_results()
    
    if not profits:
        print("No market results found!")
        return
    
    print(f"Loaded {len(profits)} market results")
    
    # Run statistical analysis
    results = statistical_analysis(profits)
    
    print(f"\n{'='*80}")
    print(f"SUMMARY")
    print(f"{'='*80}")
    print(f"With n={results['n']} markets:")
    print(f"  Mean profit: ${results['mean']:.2f}")
    print(f"  p-value: {results['p_value']:.6f}")
    if results['p_value'] < 0.05:
        print(f"  [OK] Statistically significant (profitable)")
    else:
        print(f"  [X] Not statistically significant")
    print(f"  95% CI: [${results['ci_95_lower']:.2f}, ${results['ci_95_upper']:.2f}]")
    print(f"{'='*80}\n")

if __name__ == '__main__':
    main()

