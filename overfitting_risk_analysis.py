"""
Analyze the risk of overfitting and whether the 16 test markets are representative.
Tests if the strategy's performance is due to:
1. Overfitting to these specific markets
2. These markets being "lucky" outliers
3. True edge that generalizes
"""

import subprocess
import re
import glob
import numpy as np
from scipy import stats
from pathlib import Path
import random

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
        our_profit_matches = list(re.finditer(r'ACTUAL PROFIT:\s+\$?([-\d.]+)', output))
        if not our_profit_matches:
            return None
        
        profit = float(our_profit_matches[0].group(1))
        return profit
    except:
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
        
        profit = run_market(market_csv, gabagool_csv)
        if profit is not None:
            results.append(profit)
    
    return results

def bootstrap_analysis(profits, n_bootstrap=10000):
    """
    Bootstrap resampling to estimate:
    1. Confidence in mean profit
    2. Risk that we got "lucky" with these 16 markets
    3. Probability that true mean is negative
    """
    n = len(profits)
    profits = np.array(profits)
    
    # Bootstrap: resample with replacement
    bootstrap_means = []
    for _ in range(n_bootstrap):
        sample = np.random.choice(profits, size=n, replace=True)
        bootstrap_means.append(np.mean(sample))
    
    bootstrap_means = np.array(bootstrap_means)
    
    # Calculate percentiles
    ci_95_lower = np.percentile(bootstrap_means, 2.5)
    ci_95_upper = np.percentile(bootstrap_means, 97.5)
    ci_90_lower = np.percentile(bootstrap_means, 5)
    ci_90_upper = np.percentile(bootstrap_means, 95)
    
    # Probability that true mean is negative
    prob_negative = np.mean(bootstrap_means < 0)
    
    # Probability that true mean is > $20 (meaningful profit)
    prob_meaningful = np.mean(bootstrap_means > 20)
    
    return {
        'ci_95_lower': ci_95_lower,
        'ci_95_upper': ci_95_upper,
        'ci_90_lower': ci_90_lower,
        'ci_90_upper': ci_90_upper,
        'prob_negative': prob_negative,
        'prob_meaningful': prob_meaningful,
        'bootstrap_means': bootstrap_means
    }

def permutation_test(profits, n_permutations=10000):
    """
    Permutation test: What if profits were randomly distributed?
    Tests if our observed profit is significantly different from random chance.
    """
    observed_mean = np.mean(profits)
    n = len(profits)
    
    # Create null distribution by randomly permuting signs
    permuted_means = []
    for _ in range(n_permutations):
        # Randomly flip signs (null hypothesis: profit is random)
        permuted = np.array(profits) * np.random.choice([-1, 1], size=n)
        permuted_means.append(np.mean(permuted))
    
    # P-value: probability of getting mean >= observed by chance
    p_value = np.mean(np.array(permuted_means) >= observed_mean)
    
    return {
        'p_value': p_value,
        'observed_mean': observed_mean,
        'null_distribution': permuted_means
    }

def jackknife_analysis(profits):
    """
    Jackknife resampling: Remove one market at a time
    Tests how dependent our results are on any single market
    """
    n = len(profits)
    jackknife_means = []
    
    for i in range(n):
        # Remove market i
        sample = [profits[j] for j in range(n) if j != i]
        jackknife_means.append(np.mean(sample))
    
    jackknife_means = np.array(jackknife_means)
    
    # How much does removing one market change the mean?
    original_mean = np.mean(profits)
    max_change = np.max(np.abs(jackknife_means - original_mean))
    avg_change = np.mean(np.abs(jackknife_means - original_mean))
    
    # Which markets are most influential?
    changes = np.abs(jackknife_means - original_mean)
    most_influential = np.argmax(changes)
    
    return {
        'max_change': max_change,
        'avg_change': avg_change,
        'most_influential_index': most_influential,
        'jackknife_means': jackknife_means
    }

def analyze_representativeness(profits):
    """
    Analyze if these 16 markets are representative
    Tests for outliers, skewness, and unusual patterns
    """
    profits = np.array(profits)
    
    # Outlier detection
    q1 = np.percentile(profits, 25)
    q3 = np.percentile(profits, 75)
    iqr = q3 - q1
    outliers = profits[(profits < q1 - 1.5*iqr) | (profits > q3 + 1.5*iqr)]
    
    # Skewness and kurtosis
    skewness = stats.skew(profits)
    kurtosis = stats.kurtosis(profits)
    
    # Test for normality (if normal, more likely representative)
    shapiro_stat, shapiro_p = stats.shapiro(profits)
    
    # Wins vs losses distribution
    wins = profits[profits > 0]
    losses = profits[profits <= 0]
    win_rate = len(wins) / len(profits)
    
    return {
        'outliers': outliers,
        'n_outliers': len(outliers),
        'skewness': skewness,
        'kurtosis': kurtosis,
        'is_normal': shapiro_p > 0.05,
        'shapiro_p': shapiro_p,
        'win_rate': win_rate,
        'avg_win': np.mean(wins) if len(wins) > 0 else 0,
        'avg_loss': np.mean(losses) if len(losses) > 0 else 0
    }

def main():
    print("="*80)
    print("OVERFITTING RISK ANALYSIS")
    print("="*80)
    print("\nAnalyzing if the 16 test markets are representative...")
    print("Testing risk that strategy is overfit to these specific markets.\n")
    
    profits = load_all_market_results()
    
    if not profits or len(profits) < 16:
        print("Need at least 16 markets for analysis")
        return
    
    profits = profits[:16]  # Use exactly 16 for analysis
    print(f"Analyzing {len(profits)} markets")
    print(f"Observed mean profit: ${np.mean(profits):.2f}")
    print(f"Standard deviation: ${np.std(profits, ddof=1):.2f}\n")
    
    # 1. Bootstrap Analysis
    print("="*80)
    print("1. BOOTSTRAP ANALYSIS (Resampling with replacement)")
    print("="*80)
    bootstrap = bootstrap_analysis(profits)
    
    print(f"95% Confidence Interval: [${bootstrap['ci_95_lower']:.2f}, ${bootstrap['ci_95_upper']:.2f}]")
    print(f"90% Confidence Interval: [${bootstrap['ci_90_lower']:.2f}, ${bootstrap['ci_90_upper']:.2f}]")
    print(f"\nProbability true mean is NEGATIVE: {bootstrap['prob_negative']*100:.1f}%")
    print(f"Probability true mean is > $20: {bootstrap['prob_meaningful']*100:.1f}%")
    
    if bootstrap['ci_95_lower'] < 0:
        print("\n[!] WARNING: 95% CI includes negative values")
        print("    -> True profitability is uncertain")
    else:
        print("\n[OK] 95% CI is entirely positive")
    
    # 2. Permutation Test
    print("\n" + "="*80)
    print("2. PERMUTATION TEST (Random chance test)")
    print("="*80)
    perm = permutation_test(profits)
    print(f"Observed mean: ${perm['observed_mean']:.2f}")
    print(f"P-value (chance of this by random): {perm['p_value']:.4f}")
    
    if perm['p_value'] < 0.05:
        print("[OK] Results unlikely due to random chance")
    else:
        print("[!] Results could be due to random chance")
    
    # 3. Jackknife Analysis
    print("\n" + "="*80)
    print("3. JACKKNIFE ANALYSIS (Dependency on individual markets)")
    print("="*80)
    jack = jackknife_analysis(profits)
    print(f"Average change when removing one market: ${jack['avg_change']:.2f}")
    print(f"Maximum change: ${jack['max_change']:.2f}")
    print(f"Most influential market index: {jack['most_influential_index']}")
    
    if jack['max_change'] > np.mean(profits) * 0.5:
        print("[!] WARNING: Results heavily dependent on single markets")
        print("    -> High overfitting risk")
    else:
        print("[OK] Results not overly dependent on single markets")
    
    # 4. Representativeness Analysis
    print("\n" + "="*80)
    print("4. REPRESENTATIVENESS ANALYSIS")
    print("="*80)
    rep = analyze_representativeness(profits)
    
    print(f"Outliers detected: {rep['n_outliers']}")
    if rep['n_outliers'] > 0:
        print(f"  Outlier values: {rep['outliers']}")
    
    print(f"\nDistribution statistics:")
    print(f"  Skewness: {rep['skewness']:.2f} (0 = normal, >1 = right-skewed)")
    print(f"  Kurtosis: {rep['kurtosis']:.2f} (0 = normal, >3 = heavy tails)")
    print(f"  Normal distribution? {rep['is_normal']} (p={rep['shapiro_p']:.4f})")
    
    print(f"\nWin/Loss pattern:")
    print(f"  Win rate: {rep['win_rate']*100:.1f}%")
    print(f"  Average win: ${rep['avg_win']:.2f}")
    print(f"  Average loss: ${rep['avg_loss']:.2f}")
    
    if not rep['is_normal']:
        print("\n[!] Distribution is NOT normal")
        print("    -> Markets may not be representative")
        print("    -> Results might not generalize")
    
    # 5. Overfitting Risk Assessment
    print("\n" + "="*80)
    print("5. OVERFITTING RISK ASSESSMENT")
    print("="*80)
    
    risk_factors = []
    
    if bootstrap['prob_negative'] > 0.10:
        risk_factors.append(f"10%+ chance true mean is negative")
    
    if bootstrap['ci_95_lower'] < 0:
        risk_factors.append("95% CI crosses zero")
    
    if perm['p_value'] > 0.05:
        risk_factors.append("Results could be random chance")
    
    if jack['max_change'] > np.mean(profits) * 0.5:
        risk_factors.append("Heavily dependent on single markets")
    
    if rep['n_outliers'] > len(profits) * 0.25:
        risk_factors.append("Many outliers (25%+)")
    
    if not rep['is_normal']:
        risk_factors.append("Non-normal distribution")
    
    if len(risk_factors) == 0:
        print("[OK] LOW overfitting risk")
        print("    Strategy likely generalizes well")
    elif len(risk_factors) <= 2:
        print("[!] MODERATE overfitting risk")
        print("    Some concerns, but strategy may still work")
        print(f"    Risk factors: {', '.join(risk_factors)}")
    else:
        print("[!] HIGH overfitting risk")
        print("    Strategy may be overfit to these 16 markets")
        print(f"    Risk factors: {', '.join(risk_factors)}")
    
    # 6. Recommendations
    print("\n" + "="*80)
    print("6. RECOMMENDATIONS")
    print("="*80)
    
    print("\nTo reduce overfitting risk:")
    print("  1. Test on OUT-OF-SAMPLE data (new markets)")
    print("  2. Run full day test (96 markets) - different time periods")
    print("  3. Test across different market conditions (volatile, calm, etc.)")
    print("  4. Use walk-forward analysis (train on first N, test on next M)")
    print("  5. Monitor performance degradation over time")
    
    if bootstrap['prob_negative'] > 0.15:
        print("\n[!] HIGH RISK: >15% chance strategy is unprofitable")
        print("    -> Do NOT deploy with real money yet")
        print("    -> Need more data to confirm")
    elif bootstrap['prob_negative'] > 0.05:
        print("\n[!] MODERATE RISK: 5-15% chance strategy is unprofitable")
        print("    -> Proceed with caution")
        print("    -> Start with small position sizes")
    else:
        print("\n[OK] LOW RISK: <5% chance strategy is unprofitable")
        print("    -> Strategy likely profitable, but still test more")
    
    print("\n" + "="*80)

if __name__ == '__main__':
    main()

