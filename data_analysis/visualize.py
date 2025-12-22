"""
Complete market analysis visualization
All charts in one multi-panel figure

Charts:
1. Arb probability by time (average)
2. Individual market curves
3. Price distribution: gabagool buys vs time spent at price
4. Future volatility by entry minute
"""
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
import os
from glob import glob

# Professional styling
plt.rcParams.update({
    'font.family': 'serif',
    'font.serif': ['Palatino', 'Georgia', 'Times New Roman', 'DejaVu Serif'],
    'font.size': 10,
    'axes.labelsize': 11,
    'axes.titlesize': 11,
    'axes.titleweight': 'medium',
    'axes.linewidth': 0.8,
    'axes.edgecolor': '#aaaaaa',
    'axes.labelcolor': '#333333',
    'xtick.labelsize': 9,
    'ytick.labelsize': 9,
    'xtick.color': '#555555',
    'ytick.color': '#555555',
    'legend.fontsize': 9,
    'legend.framealpha': 0.9,
    'figure.facecolor': '#fafafa',
    'axes.facecolor': '#fafafa',
    'axes.grid': True,
    'grid.alpha': 0.4,
    'grid.linewidth': 0.5,
    'grid.color': '#dddddd',
    'lines.linewidth': 1.5,
})


def get_market_files():
    pattern = 'testing_data/btc-15m_*_market.csv'
    return sorted(glob(pattern))


def get_gabagool_files():
    pattern = 'testing_data/btc-15m_*_gabagool.csv'
    return sorted(glob(pattern))


def load_market_data(csv_path):
    df = pd.read_csv(csv_path)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    start_time = df['timestamp'].iloc[0]
    df['seconds_into_market'] = (df['timestamp'] - start_time).dt.total_seconds()
    df['minutes_into_market'] = df['seconds_into_market'] / 60
    return df


def load_gabagool_data(csv_path):
    df = pd.read_csv(csv_path)
    # Keep ALL trades (buys only, but both sides)
    df = df[df['side'] == 'BUY'].copy()
    return df


def analyze_future_arb(df):
    """Calculate if future arb exists for each row"""
    n = len(df)
    up_prices = df['up_best_ask'].values
    down_prices = df['down_best_ask'].values
    
    min_future_down = np.full(n, np.inf)
    min_future_up = np.full(n, np.inf)
    
    current_min_down = np.inf
    current_min_up = np.inf
    
    for i in range(n - 1, -1, -1):
        min_future_down[i] = current_min_down
        min_future_up[i] = current_min_up
        if pd.notna(down_prices[i]):
            current_min_down = min(current_min_down, down_prices[i])
        if pd.notna(up_prices[i]):
            current_min_up = min(current_min_up, up_prices[i])
    
    has_future_arb = np.full(n, False)
    
    for i in range(n):
        up_arb = False
        if pd.notna(up_prices[i]) and min_future_down[i] < np.inf:
            up_arb = (up_prices[i] + min_future_down[i]) < 1.0
        
        down_arb = False
        if pd.notna(down_prices[i]) and min_future_up[i] < np.inf:
            down_arb = (down_prices[i] + min_future_up[i]) < 1.0
        
        has_future_arb[i] = up_arb or down_arb
    
    df['has_future_arb'] = has_future_arb
    return df


def calculate_minute_probabilities(df):
    probs = {}
    for minute in range(15):
        mask = (df['minutes_into_market'] >= minute) & (df['minutes_into_market'] < minute + 1)
        subset = df[mask]
        if len(subset) > 0:
            probs[minute] = subset['has_future_arb'].mean() * 100
        else:
            probs[minute] = np.nan
    return probs


def main():
    market_files = get_market_files()
    gabagool_files = get_gabagool_files()
    
    if not market_files:
        print('No market files found in testing_data/')
        return
    
    print(f'Found {len(market_files)} market files')
    print(f'Found {len(gabagool_files)} gabagool files')
    
    # ========== PROCESS MARKET DATA ==========
    market_probs = {}
    all_market_dfs = []
    
    for f in market_files:
        name = os.path.basename(f).replace('btc-15m_', '').replace('_market.csv', '')
        time_label = name.split('_')[0]
        
        df = load_market_data(f)
        df = analyze_future_arb(df)
        
        probs = calculate_minute_probabilities(df)
        market_probs[time_label] = probs
        all_market_dfs.append(df)
        
        print(f'  {time_label}: {len(df)} points, arb rate: {df["has_future_arb"].mean()*100:.1f}%')
    
    combined_market = pd.concat(all_market_dfs, ignore_index=True)
    
    # Calculate average arb probs
    minutes = np.array(list(range(15)))
    avg_probs = {}
    for minute in minutes:
        probs_for_minute = []
        for market, probs in market_probs.items():
            if minute in probs and not np.isnan(probs[minute]):
                probs_for_minute.append(probs[minute])
        if probs_for_minute:
            avg_probs[minute] = np.mean(probs_for_minute)
        else:
            avg_probs[minute] = np.nan
    
    avg_vals = np.array([avg_probs.get(m, np.nan) for m in minutes])
    
    # ========== PROCESS GABAGOOL DATA ==========
    all_gabagool_prices = []
    for f in gabagool_files:
        df = load_gabagool_data(f)
        if 'price' in df.columns and len(df) > 0:
            all_gabagool_prices.extend(df['price'].dropna().tolist())
    
    print(f'\nTotal gabagool buys: {len(all_gabagool_prices)}')
    
    # Get ALL prices from market data (both up and down, not just cheaper)
    all_up_prices = combined_market['up_best_ask'].dropna().tolist()
    all_down_prices = combined_market['down_best_ask'].dropna().tolist()
    all_market_prices = all_up_prices + all_down_prices
    
    # ========== CALCULATE FUTURE VOLATILITY ==========
    future_vol = {m: [] for m in minutes}
    
    for df in all_market_dfs:
        df['cheaper_price'] = df[['up_best_ask', 'down_best_ask']].min(axis=1)
        
        for entry_minute in minutes:
            future_data = df[df['minutes_into_market'] >= entry_minute]['cheaper_price'].dropna()
            if len(future_data) > 10:
                price_range = future_data.max() - future_data.min()
                future_vol[entry_minute].append(price_range * 100)  # cents
    
    avg_future_vol = []
    for m in minutes:
        if future_vol[m]:
            avg_future_vol.append(np.mean(future_vol[m]))
        else:
            avg_future_vol.append(np.nan)
    
    # ========== CREATE MULTI-PAGE PDF ==========
    output_path = 'testing_data/market_analysis.pdf'
    
    # Colors
    light_blue = '#7eb8da'
    navy = '#1a3a5c'
    fill_color = '#2c5aa0'
    soft_blue = '#6baed6'
    soft_purple = '#8da0cb'
    soft_teal = '#66c2a5'
    gold = '#d4a84b'
    
    # Pre-calculate entry value for later use
    arb_prob_normalized = np.array([avg_probs.get(m, 0) for m in minutes]) / 100
    vol_max = max([v for v in avg_future_vol if not np.isnan(v)])
    vol_normalized = np.array([v / vol_max if not np.isnan(v) else 0 for v in avg_future_vol])
    entry_value = arb_prob_normalized * vol_normalized * 100
    
    peak_minute = minutes[np.argmax(entry_value)]
    peak_value = max(entry_value)
    cutoff_50 = None
    for m, v in zip(minutes, entry_value):
        if v < peak_value * 0.5 and cutoff_50 is None:
            cutoff_50 = m
    
    valid_mask = ~np.isnan(avg_vals)
    valid_mins = minutes[valid_mask]
    valid_vals = avg_vals[valid_mask]
    
    with PdfPages(output_path) as pdf:
        
        # ===== PAGE 1: Average arb probability =====
        fig1, ax1 = plt.subplots(figsize=(10, 6))
        fig1.patch.set_facecolor('#fafafa')
        
        ax1.fill_between(valid_mins, 0, valid_vals, alpha=0.12, color=fill_color, linewidth=0)
        ax1.plot(valid_mins, valid_vals, '-', color=navy, linewidth=2.2)
        ax1.axhline(y=50, color='#888888', linestyle='--', linewidth=0.8, alpha=0.6)
        
        ax1.set_xlabel('Minutes into Market')
        ax1.set_ylabel('Probability of Future Arb (%)')
        ax1.set_title(f'Arb Probability Over Time (n={len(market_files)} markets)', pad=10)
        ax1.set_xticks(minutes)
        ax1.set_ylim(0, 100)
        ax1.set_xlim(-0.3, 14.3)
        ax1.spines['top'].set_visible(False)
        ax1.spines['right'].set_visible(False)
        
        plt.tight_layout()
        pdf.savefig(fig1, facecolor='#fafafa')
        plt.close(fig1)
        
        # ===== PAGE 2: Individual markets =====
        fig2, ax2 = plt.subplots(figsize=(10, 6))
        fig2.patch.set_facecolor('#fafafa')
        
        first = True
        for market, probs in market_probs.items():
            vals = np.array([probs.get(m, np.nan) for m in minutes])
            valid_mask_ind = ~np.isnan(vals)
            valid_mins_ind = minutes[valid_mask_ind]
            valid_vals_ind = vals[valid_mask_ind]
            
            if len(valid_mins_ind) > 0:
                label = 'Individual' if first else None
                ax2.plot(valid_mins_ind, valid_vals_ind, '-', color=light_blue, 
                        linewidth=1.2, alpha=0.55, label=label)
                first = False
        
        ax2.plot(valid_mins, valid_vals, '-', color=navy, linewidth=2.5, label='Average', zorder=10)
        ax2.axhline(y=50, color='#888888', linestyle='--', linewidth=0.8, alpha=0.6)
        
        ax2.set_xlabel('Minutes into Market')
        ax2.set_ylabel('Probability of Future Arb (%)')
        ax2.set_title('Individual Market Curves', pad=10)
        ax2.set_xticks(minutes)
        ax2.set_ylim(0, 100)
        ax2.set_xlim(-0.3, 14.3)
        ax2.spines['top'].set_visible(False)
        ax2.spines['right'].set_visible(False)
        ax2.legend(loc='lower left', frameon=True, edgecolor='#cccccc', fancybox=False)
        
        plt.tight_layout()
        pdf.savefig(fig2, facecolor='#fafafa')
        plt.close(fig2)
        
        # ===== PAGE 3: Price distribution =====
        fig3, ax3 = plt.subplots(figsize=(10, 6))
        fig3.patch.set_facecolor('#fafafa')
        
        price_bins = np.arange(0, 1.05, 0.05)
        price_centers = [(price_bins[i] + price_bins[i+1]) / 2 for i in range(len(price_bins)-1)]
        
        if all_gabagool_prices and all_market_prices:
            market_counts, _ = np.histogram(all_market_prices, bins=price_bins)
            gabagool_counts, _ = np.histogram(all_gabagool_prices, bins=price_bins)
            
            market_pct = (market_counts / market_counts.sum()) * 100
            gabagool_pct = (gabagool_counts / gabagool_counts.sum()) * 100
            
            ax3.plot(price_centers, market_pct, '-', color=soft_purple, linewidth=2,
                    label='Time at price', marker='o', markersize=4, 
                    markeredgecolor='white', markeredgewidth=0.8)
            ax3.plot(price_centers, gabagool_pct, '-', color=soft_teal, linewidth=2,
                    label='Gabagool buys', marker='o', markersize=4,
                    markeredgecolor='white', markeredgewidth=0.8)
            
            ax3.fill_between(price_centers, market_pct, gabagool_pct, 
                            where=(gabagool_pct > market_pct), alpha=0.15, color=soft_teal,
                            interpolate=True)
            ax3.fill_between(price_centers, market_pct, gabagool_pct, 
                            where=(gabagool_pct <= market_pct), alpha=0.15, color=soft_purple,
                            interpolate=True)
            
            ax3.set_xlabel('Price')
            ax3.set_ylabel('% of Total')
            ax3.set_title('Price Distribution: Opportunity vs Gabagool', pad=10)
            ax3.set_xticks([0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9])
            ax3.set_xticklabels(['10c', '20c', '30c', '40c', '50c', '60c', '70c', '80c', '90c'])
            ax3.set_xlim(0, 1)
            ax3.legend(frameon=True, edgecolor='#cccccc', fancybox=False, loc='upper right')
            ax3.spines['top'].set_visible(False)
            ax3.spines['right'].set_visible(False)
            
            correlation = np.corrcoef(market_pct, gabagool_pct)[0, 1]
            ax3.text(0.02, 0.98, f'Correlation: {correlation:.2f}', 
                    transform=ax3.transAxes, fontsize=9, verticalalignment='top',
                    bbox=dict(boxstyle='round', facecolor='white', edgecolor='#cccccc', alpha=0.9))
        else:
            ax3.text(0.5, 0.5, 'No gabagool data available', ha='center', va='center', 
                    transform=ax3.transAxes, fontsize=11, color='#888888')
            ax3.set_title('Price Distribution', pad=10)
        
        plt.tight_layout()
        pdf.savefig(fig3, facecolor='#fafafa')
        plt.close(fig3)
        
        # ===== PAGE 4: Future volatility =====
        fig4, ax4 = plt.subplots(figsize=(10, 6))
        fig4.patch.set_facecolor('#fafafa')
        
        ax4.plot(minutes, avg_future_vol, '-', color=soft_blue, linewidth=2.2,
                marker='o', markersize=5, markeredgecolor='white', markeredgewidth=1)
        ax4.fill_between(minutes, avg_future_vol, alpha=0.12, color=soft_blue)
        
        ax4.set_xlabel('Entry Minute')
        ax4.set_ylabel('Remaining Price Range (cents)')
        ax4.set_title('Future Volatility by Entry Time', pad=10)
        ax4.set_xticks(minutes)
        ax4.spines['top'].set_visible(False)
        ax4.spines['right'].set_visible(False)
        
        plt.tight_layout()
        pdf.savefig(fig4, facecolor='#fafafa')
        plt.close(fig4)
        
        # ===== PAGE 5: Entry Value =====
        fig5, ax5 = plt.subplots(figsize=(10, 6))
        fig5.patch.set_facecolor('#fafafa')
        
        ax5.plot(minutes, entry_value, '-', color=gold, linewidth=2.5,
                marker='o', markersize=6, markeredgecolor='white', markeredgewidth=1.2)
        ax5.fill_between(minutes, entry_value, alpha=0.15, color=gold)
        
        for i, (m, v) in enumerate(zip(minutes, entry_value)):
            if v > 0:
                ax5.annotate(f'{v:.0f}', (m, v), textcoords="offset points", 
                            xytext=(0, 8), ha='center', fontsize=8, color='#555555')
        
        ax5.set_xlabel('Entry Minute')
        ax5.set_ylabel('Entry Value Score')
        ax5.set_title('Entry Value = Arb Probability x Future Volatility (normalized)', pad=10)
        ax5.set_xticks(minutes)
        ax5.set_xlim(-0.3, 14.3)
        ax5.set_ylim(0, max(entry_value) * 1.2)
        ax5.spines['top'].set_visible(False)
        ax5.spines['right'].set_visible(False)
        
        interpretation = f'Peak value at minute {peak_minute} (score: {peak_value:.0f})'
        if cutoff_50:
            interpretation += f'\nValue drops below 50% at minute {cutoff_50}'
        
        ax5.text(0.98, 0.95, interpretation, transform=ax5.transAxes, fontsize=9, 
                verticalalignment='top', horizontalalignment='right',
                bbox=dict(boxstyle='round', facecolor='white', edgecolor='#cccccc', alpha=0.9))
        
        plt.tight_layout()
        pdf.savefig(fig5, facecolor='#fafafa')
        plt.close(fig5)
    
    print(f'\nPDF saved to: {output_path} (5 pages)')
    
    # ========== PRINT SUMMARIES ==========
    print('\n' + '=' * 60)
    print('COMBINED METRICS BY MINUTE')
    print('=' * 60)
    print(f'{"Min":>4} | {"Arb Prob":>10} | {"Volatility":>12} | {"Entry Value":>12}')
    print('-' * 60)
    for m in minutes:
        arb = avg_probs.get(m, np.nan)
        vol = avg_future_vol[m] if m < len(avg_future_vol) else np.nan
        val = entry_value[m] if m < len(entry_value) else np.nan
        
        arb_str = f'{arb:.1f}%' if not np.isnan(arb) else '--'
        vol_str = f'{vol:.1f}c' if not np.isnan(vol) else '--'
        val_str = f'{val:.1f}' if not np.isnan(val) else '--'
        
        print(f'{m:>4} | {arb_str:>10} | {vol_str:>12} | {val_str:>12}')
    print('=' * 60)
    
    # Key insights
    print('\nKEY INSIGHTS:')
    print(f'  - Peak entry value: minute {peak_minute} (score: {peak_value:.0f})')
    if cutoff_50:
        print(f'  - Value drops below 50% of peak at minute {cutoff_50}')
    
    # Find where entry value drops below certain thresholds
    for threshold in [75, 50, 25]:
        for m, v in zip(minutes, entry_value):
            if v < peak_value * (threshold / 100):
                print(f'  - Value drops below {threshold}% at minute {m}')
                break
    
    if all_gabagool_prices:
        print('\n' + '=' * 60)
        print('GABAGOOL PRICE ANALYSIS')
        print('=' * 60)
        print(f'Total buys: {len(all_gabagool_prices)}')
        print(f'Avg buy price: ${np.mean(all_gabagool_prices):.3f}')
        print(f'Median buy price: ${np.median(all_gabagool_prices):.3f}')
        print(f'Price range: ${np.min(all_gabagool_prices):.3f} - ${np.max(all_gabagool_prices):.3f}')


if __name__ == "__main__":
    main()
