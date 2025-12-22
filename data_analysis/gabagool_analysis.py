"""
Gabagool Trade Analysis
Compare gabagool's trading patterns to our calculated metrics
"""
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from glob import glob

# Professional styling
plt.rcParams.update({
    'font.family': 'serif',
    'font.serif': ['Palatino', 'Georgia', 'Times New Roman'],
    'font.size': 10,
    'axes.labelsize': 11,
    'axes.titlesize': 12,
    'figure.facecolor': '#fafafa',
    'axes.facecolor': '#fafafa',
    'axes.grid': True,
    'grid.alpha': 0.4,
    'grid.linewidth': 0.5,
})


def get_files():
    market_files = sorted(glob('testing_data/btc-15m_*_market.csv'))
    gabagool_files = sorted(glob('testing_data/btc-15m_*_gabagool.csv'))
    return market_files, gabagool_files


def load_market_data(csv_path):
    df = pd.read_csv(csv_path)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    start = df['timestamp'].min()
    df['seconds_in'] = (df['timestamp'] - start).dt.total_seconds()
    df['minute'] = (df['seconds_in'] // 60).astype(int)
    return df


def load_gabagool_data(csv_path):
    df = pd.read_csv(csv_path)
    df = df[df['side'] == 'BUY'].copy()
    df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True).dt.tz_localize(None)
    start = df['timestamp'].min()
    df['seconds_in'] = (df['timestamp'] - start).dt.total_seconds()
    df['minute'] = (df['seconds_in'] // 60).astype(int)
    return df


def calculate_entry_value(market_files):
    """Calculate our entry value metric by minute"""
    minutes = list(range(15))
    
    # Arb probability by minute
    arb_probs = {m: [] for m in minutes}
    future_vols = {m: [] for m in minutes}
    
    for f in market_files:
        df = load_market_data(f)
        df['cheap'] = df[['up_best_ask', 'down_best_ask']].min(axis=1)
        
        # Calculate arb probability
        n = len(df)
        up = df['up_best_ask'].values
        down = df['down_best_ask'].values
        
        min_future_down = np.full(n, np.inf)
        min_future_up = np.full(n, np.inf)
        curr_min_down, curr_min_up = np.inf, np.inf
        
        for i in range(n-1, -1, -1):
            min_future_down[i] = curr_min_down
            min_future_up[i] = curr_min_up
            if pd.notna(down[i]): curr_min_down = min(curr_min_down, down[i])
            if pd.notna(up[i]): curr_min_up = min(curr_min_up, up[i])
        
        has_arb = np.array([
            (pd.notna(up[i]) and min_future_down[i] < np.inf and up[i] + min_future_down[i] < 1.0) or
            (pd.notna(down[i]) and min_future_up[i] < np.inf and down[i] + min_future_up[i] < 1.0)
            for i in range(n)
        ])
        df['has_arb'] = has_arb
        
        for m in minutes:
            subset = df[df['minute'] == m]
            if len(subset) > 0:
                arb_probs[m].append(subset['has_arb'].mean() * 100)
                
                # Future volatility
                future = df[df['minute'] >= m]['cheap'].dropna()
                if len(future) > 0:
                    future_vols[m].append((future.max() - future.min()) * 100)
    
    # Average across markets
    avg_arb = {m: np.mean(arb_probs[m]) if arb_probs[m] else 0 for m in minutes}
    avg_vol = {m: np.mean(future_vols[m]) if future_vols[m] else 0 for m in minutes}
    
    # Normalize and combine
    max_vol = max(avg_vol.values()) if max(avg_vol.values()) > 0 else 1
    entry_value = {m: (avg_arb[m] / 100) * (avg_vol[m] / max_vol) * 100 for m in minutes}
    
    return avg_arb, avg_vol, entry_value


def calculate_gabagool_frequency(gabagool_files):
    """Calculate gabagool's trade frequency by minute"""
    minutes = list(range(15))
    trades_by_minute = {m: [] for m in minutes}
    volume_by_minute = {m: [] for m in minutes}
    
    for f in gabagool_files:
        df = load_gabagool_data(f)
        
        for m in minutes:
            subset = df[df['minute'] == m]
            # Count unique timestamps (treating same-second orders as one trade)
            unique_trades = len(subset['timestamp'].drop_duplicates())
            trades_by_minute[m].append(unique_trades)
            
            # Total volume (USDC)
            if 'usdcSize' in subset.columns:
                volume_by_minute[m].append(subset['usdcSize'].sum())
    
    # Average across markets
    avg_trades = {m: np.mean(trades_by_minute[m]) if trades_by_minute[m] else 0 for m in minutes}
    avg_volume = {m: np.mean(volume_by_minute[m]) if volume_by_minute[m] else 0 for m in minutes}
    
    return avg_trades, avg_volume


def main():
    market_files, gabagool_files = get_files()
    
    if not market_files or not gabagool_files:
        print("No data files found!")
        return
    
    print(f"Analyzing {len(market_files)} markets, {len(gabagool_files)} gabagool files")
    
    # Calculate metrics
    print("Calculating entry value...")
    arb_prob, future_vol, entry_value = calculate_entry_value(market_files)
    
    print("Calculating gabagool frequency...")
    gab_trades, gab_volume = calculate_gabagool_frequency(gabagool_files)
    
    minutes = list(range(15))
    
    # Normalize for comparison
    max_trades = max(gab_trades.values()) if max(gab_trades.values()) > 0 else 1
    max_volume = max(gab_volume.values()) if max(gab_volume.values()) > 0 else 1
    max_entry = max(entry_value.values()) if max(entry_value.values()) > 0 else 1
    
    trades_norm = {m: gab_trades[m] / max_trades * 100 for m in minutes}
    volume_norm = {m: gab_volume[m] / max_volume * 100 for m in minutes}
    entry_norm = {m: entry_value[m] / max_entry * 100 for m in minutes}
    
    # Colors
    entry_color = '#2c5aa0'
    trades_color = '#e07b39'
    volume_color = '#5a9e6f'
    
    # Create PDF
    output_path = 'testing_data/gabagool_analysis.pdf'
    
    with PdfPages(output_path) as pdf:
        
        # === PAGE 1: Entry Value vs Trade Frequency ===
        fig1, ax1 = plt.subplots(figsize=(10, 6))
        fig1.patch.set_facecolor('#fafafa')
        
        ax1.plot(minutes, [entry_norm[m] for m in minutes], '-', color=entry_color, 
                linewidth=2.5, label='Our Entry Value', marker='o', markersize=5,
                markeredgecolor='white', markeredgewidth=1)
        ax1.plot(minutes, [trades_norm[m] for m in minutes], '-', color=trades_color,
                linewidth=2.5, label='Gabagool Trade Freq', marker='s', markersize=5,
                markeredgecolor='white', markeredgewidth=1)
        
        ax1.fill_between(minutes, [entry_norm[m] for m in minutes], alpha=0.1, color=entry_color)
        ax1.fill_between(minutes, [trades_norm[m] for m in minutes], alpha=0.1, color=trades_color)
        
        ax1.set_xlabel('Minute into Market')
        ax1.set_ylabel('Normalized Value (0-100)')
        ax1.set_title('Entry Value vs Gabagool Trade Frequency', pad=15)
        ax1.set_xticks(minutes)
        ax1.legend(loc='upper right', frameon=True, edgecolor='#cccccc')
        ax1.spines['top'].set_visible(False)
        ax1.spines['right'].set_visible(False)
        
        # Correlation
        corr = np.corrcoef([entry_norm[m] for m in minutes], [trades_norm[m] for m in minutes])[0,1]
        ax1.text(0.02, 0.98, f'Correlation: {corr:.3f}', transform=ax1.transAxes, 
                fontsize=10, verticalalignment='top',
                bbox=dict(boxstyle='round', facecolor='white', edgecolor='#cccccc'))
        
        plt.tight_layout()
        pdf.savefig(fig1, facecolor='#fafafa')
        plt.close(fig1)
        
        # === PAGE 2: Entry Value vs Volume ===
        fig2, ax2 = plt.subplots(figsize=(10, 6))
        fig2.patch.set_facecolor('#fafafa')
        
        ax2.plot(minutes, [entry_norm[m] for m in minutes], '-', color=entry_color,
                linewidth=2.5, label='Our Entry Value', marker='o', markersize=5,
                markeredgecolor='white', markeredgewidth=1)
        ax2.plot(minutes, [volume_norm[m] for m in minutes], '-', color=volume_color,
                linewidth=2.5, label='Gabagool Volume ($)', marker='s', markersize=5,
                markeredgecolor='white', markeredgewidth=1)
        
        ax2.fill_between(minutes, [entry_norm[m] for m in minutes], alpha=0.1, color=entry_color)
        ax2.fill_between(minutes, [volume_norm[m] for m in minutes], alpha=0.1, color=volume_color)
        
        ax2.set_xlabel('Minute into Market')
        ax2.set_ylabel('Normalized Value (0-100)')
        ax2.set_title('Entry Value vs Gabagool Volume (USDC)', pad=15)
        ax2.set_xticks(minutes)
        ax2.legend(loc='upper right', frameon=True, edgecolor='#cccccc')
        ax2.spines['top'].set_visible(False)
        ax2.spines['right'].set_visible(False)
        
        corr_vol = np.corrcoef([entry_norm[m] for m in minutes], [volume_norm[m] for m in minutes])[0,1]
        ax2.text(0.02, 0.98, f'Correlation: {corr_vol:.3f}', transform=ax2.transAxes,
                fontsize=10, verticalalignment='top',
                bbox=dict(boxstyle='round', facecolor='white', edgecolor='#cccccc'))
        
        plt.tight_layout()
        pdf.savefig(fig2, facecolor='#fafafa')
        plt.close(fig2)
        
        # === PAGE 3: Raw Numbers Table ===
        fig3, ax3 = plt.subplots(figsize=(10, 8))
        fig3.patch.set_facecolor('#fafafa')
        ax3.axis('off')
        
        table_data = []
        for m in minutes:
            table_data.append([
                m,
                f'{arb_prob[m]:.1f}%',
                f'{future_vol[m]:.1f}c',
                f'{entry_value[m]:.1f}',
                f'{gab_trades[m]:.1f}',
                f'${gab_volume[m]:.0f}'
            ])
        
        table = ax3.table(
            cellText=table_data,
            colLabels=['Minute', 'Arb Prob', 'Future Vol', 'Entry Value', 'Gab Trades', 'Gab Volume'],
            loc='center',
            cellLoc='center'
        )
        table.auto_set_font_size(False)
        table.set_fontsize(10)
        table.scale(1.2, 1.8)
        
        # Style header
        for i in range(6):
            table[(0, i)].set_facecolor('#2c5aa0')
            table[(0, i)].set_text_props(color='white', weight='bold')
        
        ax3.set_title('Raw Data by Minute', pad=20, fontsize=14)
        
        plt.tight_layout()
        pdf.savefig(fig3, facecolor='#fafafa')
        plt.close(fig3)
        
        # === PAGE 4: Gabagool trades by minute (individual markets) ===
        fig4, ax4 = plt.subplots(figsize=(10, 6))
        fig4.patch.set_facecolor('#fafafa')
        
        # Plot each market's trade distribution
        for gf in gabagool_files:
            df = load_gabagool_data(gf)
            trades_per_min = []
            for m in minutes:
                trades_per_min.append(len(df[df['minute'] == m]['timestamp'].drop_duplicates()))
            ax4.plot(minutes, trades_per_min, '-', color='#7eb8da', alpha=0.4, linewidth=1)
        
        # Average line
        ax4.plot(minutes, [gab_trades[m] for m in minutes], '-', color='#1a3a5c', 
                linewidth=2.5, label='Average')
        
        ax4.set_xlabel('Minute into Market')
        ax4.set_ylabel('Number of Trades')
        ax4.set_title('Gabagool Trades by Minute (each market + average)', pad=15)
        ax4.set_xticks(minutes)
        ax4.legend(loc='upper right', frameon=True, edgecolor='#cccccc')
        ax4.spines['top'].set_visible(False)
        ax4.spines['right'].set_visible(False)
        
        plt.tight_layout()
        pdf.savefig(fig4, facecolor='#fafafa')
        plt.close(fig4)
    
    print(f'\nPDF saved to: {output_path}')
    
    # Print summary
    print('\n' + '=' * 60)
    print('CORRELATION SUMMARY')
    print('=' * 60)
    print(f'Entry Value vs Trade Frequency: {corr:.3f}')
    print(f'Entry Value vs Volume:          {corr_vol:.3f}')
    
    if corr > 0.8:
        print('\n-> HIGH correlation with trade frequency!')
        print('   Gabagool\'s trading intensity matches our entry value well.')
    elif corr > 0.5:
        print('\n-> MODERATE correlation with trade frequency.')
        print('   Some alignment, but other factors at play.')
    else:
        print('\n-> LOW correlation with trade frequency.')
        print('   Our entry value may not capture gabagool\'s decision logic.')


if __name__ == "__main__":
    main()

