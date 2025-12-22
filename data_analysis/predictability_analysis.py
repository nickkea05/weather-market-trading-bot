"""
Analysis: When does it become clear which side will win?

For each market, tracks:
- At each point in time, which side is >50 cents (more likely to win)
- Whether that prediction is correct (that side actually wins)
- Accuracy over time to see when predictions become reliable
"""

import pandas as pd
import numpy as np
from glob import glob
from pathlib import Path
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from collections import defaultdict

# Matplotlib style
plt.style.use('seaborn-v0_8-darkgrid')
plt.rcParams['figure.figsize'] = (12, 8)
plt.rcParams['font.size'] = 10
plt.rcParams['axes.labelsize'] = 12
plt.rcParams['axes.titlesize'] = 14
plt.rcParams['xtick.labelsize'] = 10
plt.rcParams['ytick.labelsize'] = 10
plt.rcParams['legend.fontsize'] = 10

def get_market_files():
    """Get all market CSV files"""
    pattern = 'testing_data/btc-15m_*_market.csv'
    files = glob(pattern)
    return sorted(files)

def load_market_data(csv_path):
    """Load market data from CSV"""
    df = pd.read_csv(csv_path)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    return df

def determine_winner(df):
    """Determine which side won based on final prices"""
    if len(df) == 0:
        return None
    
    last_row = df.iloc[-1]
    up_price = float(last_row['up_best_ask'])
    down_price = float(last_row['down_best_ask'])
    
    # Winner is the side that reaches >= 0.90
    if up_price >= 0.90:
        return 'UP'
    elif down_price >= 0.90:
        return 'DOWN'
    else:
        # If neither reached 0.90, use the higher price
        if up_price > down_price:
            return 'UP'
        else:
            return 'DOWN'

def analyze_market_predictability(df, market_name):
    """Analyze when predictions become reliable for a single market"""
    winner = determine_winner(df)
    if winner is None:
        return None
    
    # Calculate seconds into market
    start_time = df['timestamp'].iloc[0]
    df['seconds_into_market'] = (df['timestamp'] - start_time).dt.total_seconds()
    
    # For each row, determine which side is predicted to win (>50 cents)
    predictions = []
    for idx, row in df.iterrows():
        up_price = float(row['up_best_ask'])
        down_price = float(row['down_best_ask'])
        seconds = row['seconds_into_market']
        
        # Predict UP if up_price > 0.50, else DOWN
        if up_price > 0.50:
            predicted = 'UP'
        elif down_price > 0.50:
            predicted = 'DOWN'
        else:
            # If both are <= 0.50, predict the higher one
            predicted = 'UP' if up_price >= down_price else 'DOWN'
        
        is_correct = (predicted == winner)
        
        predictions.append({
            'seconds': seconds,
            'up_price': up_price,
            'down_price': down_price,
            'predicted': predicted,
            'actual_winner': winner,
            'is_correct': is_correct
        })
    
    return pd.DataFrame(predictions)

def analyze_all_markets():
    """Analyze all markets and aggregate results"""
    market_files = get_market_files()
    
    all_predictions = []
    market_results = []
    
    for market_file in market_files:
        market_name = Path(market_file).stem
        print(f"Analyzing {market_name}...")
        
        df = load_market_data(market_file)
        predictions_df = analyze_market_predictability(df, market_name)
        
        if predictions_df is None:
            continue
        
        # Add market identifier
        predictions_df['market'] = market_name
        all_predictions.append(predictions_df)
        
        # Calculate overall accuracy for this market
        total = len(predictions_df)
        correct = predictions_df['is_correct'].sum()
        accuracy = correct / total if total > 0 else 0
        
        market_results.append({
            'market': market_name,
            'winner': predictions_df['actual_winner'].iloc[0],
            'total_predictions': total,
            'correct_predictions': correct,
            'accuracy': accuracy
        })
    
    if not all_predictions:
        print("No market data found!")
        return None, None
    
    combined_df = pd.concat(all_predictions, ignore_index=True)
    market_summary = pd.DataFrame(market_results)
    
    return combined_df, market_summary

def calculate_accuracy_by_time(combined_df):
    """Calculate prediction accuracy at each second/minute"""
    # Round to nearest 10 seconds for binning
    combined_df['time_bin'] = (combined_df['seconds'] // 10) * 10
    
    accuracy_by_time = []
    
    for time_bin in sorted(combined_df['time_bin'].unique()):
        time_data = combined_df[combined_df['time_bin'] == time_bin]
        total = len(time_data)
        correct = time_data['is_correct'].sum()
        accuracy = correct / total if total > 0 else 0
        
        accuracy_by_time.append({
            'seconds': time_bin,
            'minutes': time_bin / 60.0,
            'total_predictions': total,
            'correct_predictions': correct,
            'accuracy': accuracy
        })
    
    return pd.DataFrame(accuracy_by_time)

def create_accuracy_chart(accuracy_df, pdf):
    """Create chart showing prediction accuracy over time"""
    fig, ax = plt.subplots(figsize=(12, 8))
    
    # Plot accuracy
    ax.plot(accuracy_df['minutes'], accuracy_df['accuracy'] * 100, 
            linewidth=2, color='#2E86AB', label='Prediction Accuracy')
    
    # Add 50% line (random chance)
    ax.axhline(y=50, color='gray', linestyle='--', linewidth=1, alpha=0.7, label='Random (50%)')
    
    # Add 80% threshold line
    ax.axhline(y=80, color='green', linestyle='--', linewidth=1, alpha=0.7, label='80% Threshold')
    
    ax.set_xlabel('Minutes into Market', fontsize=12)
    ax.set_ylabel('Prediction Accuracy (%)', fontsize=12)
    ax.set_title('When Can We Predict the Winner?\n(Accuracy of ">50 cents" prediction over time)', fontsize=14, fontweight='bold')
    ax.set_ylim(0, 105)
    ax.set_xlim(0, 15)
    ax.grid(True, alpha=0.3)
    ax.legend(loc='best')
    
    # Find when accuracy crosses 80%
    high_confidence = accuracy_df[accuracy_df['accuracy'] >= 0.80]
    if len(high_confidence) > 0:
        first_80 = high_confidence.iloc[0]
        ax.axvline(x=first_80['minutes'], color='green', linestyle=':', linewidth=2, alpha=0.7)
        ax.text(first_80['minutes'], 85, f"80% at {first_80['minutes']:.1f} min", 
                rotation=90, verticalalignment='bottom', fontsize=9)
    
    plt.tight_layout()
    pdf.savefig(fig, bbox_inches='tight')
    plt.close()

def create_prediction_distribution_chart(combined_df, pdf):
    """Show distribution of predictions vs actual winners"""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
    
    # Chart 1: Prediction distribution
    predicted_counts = combined_df['predicted'].value_counts()
    ax1.bar(predicted_counts.index, predicted_counts.values, color=['#2E86AB', '#A23B72'], alpha=0.7)
    ax1.set_xlabel('Predicted Winner', fontsize=12)
    ax1.set_ylabel('Number of Predictions', fontsize=12)
    ax1.set_title('Distribution of Predictions', fontsize=13, fontweight='bold')
    ax1.grid(True, alpha=0.3, axis='y')
    
    # Chart 2: Accuracy by predicted side
    accuracy_by_side = []
    for side in ['UP', 'DOWN']:
        side_data = combined_df[combined_df['predicted'] == side]
        if len(side_data) > 0:
            accuracy = side_data['is_correct'].sum() / len(side_data)
            accuracy_by_side.append({'side': side, 'accuracy': accuracy * 100})
    
    if accuracy_by_side:
        acc_df = pd.DataFrame(accuracy_by_side)
        ax2.bar(acc_df['side'], acc_df['accuracy'], color=['#2E86AB', '#A23B72'], alpha=0.7)
        ax2.set_xlabel('Predicted Winner', fontsize=12)
        ax2.set_ylabel('Accuracy (%)', fontsize=12)
        ax2.set_title('Prediction Accuracy by Side', fontsize=13, fontweight='bold')
        ax2.set_ylim(0, 105)
        ax2.axhline(y=50, color='gray', linestyle='--', linewidth=1, alpha=0.7)
        ax2.grid(True, alpha=0.3, axis='y')
    
    plt.tight_layout()
    pdf.savefig(fig, bbox_inches='tight')
    plt.close()

def create_individual_market_chart(combined_df, pdf):
    """Show accuracy for each individual market"""
    markets = combined_df['market'].unique()
    n_markets = len(markets)
    
    # Create subplots (4 per row)
    n_cols = 4
    n_rows = (n_markets + n_cols - 1) // n_cols
    
    fig, axes = plt.subplots(n_rows, n_cols, figsize=(16, 4 * n_rows))
    axes = axes.flatten() if n_rows > 1 else [axes] if n_rows == 1 else axes
    
    for idx, market in enumerate(markets):
        ax = axes[idx]
        market_data = combined_df[combined_df['market'] == market].copy()
        
        # Calculate accuracy by time for this market
        market_data['time_bin'] = (market_data['seconds'] // 30) * 30  # 30-second bins
        time_accuracy = []
        
        for time_bin in sorted(market_data['time_bin'].unique()):
            time_data = market_data[market_data['time_bin'] == time_bin]
            if len(time_data) > 0:
                accuracy = time_data['is_correct'].sum() / len(time_data)
                time_accuracy.append({
                    'minutes': time_bin / 60.0,
                    'accuracy': accuracy
                })
        
        if time_accuracy:
            acc_df = pd.DataFrame(time_accuracy)
            winner = market_data['actual_winner'].iloc[0]
            ax.plot(acc_df['minutes'], acc_df['accuracy'] * 100, linewidth=1.5, alpha=0.7)
            ax.axhline(y=50, color='gray', linestyle='--', linewidth=0.5, alpha=0.5)
            ax.set_title(f"{Path(market).name[:20]}...\nWinner: {winner}", fontsize=9)
            ax.set_xlabel('Minutes', fontsize=8)
            ax.set_ylabel('Accuracy %', fontsize=8)
            ax.set_ylim(0, 105)
            ax.set_xlim(0, 15)
            ax.grid(True, alpha=0.2)
    
    # Hide unused subplots
    for idx in range(n_markets, len(axes)):
        axes[idx].axis('off')
    
    plt.suptitle('Prediction Accuracy by Market (Individual)', fontsize=14, fontweight='bold', y=0.995)
    plt.tight_layout()
    pdf.savefig(fig, bbox_inches='tight')
    plt.close()

def print_summary(accuracy_df, market_summary):
    """Print summary statistics"""
    print("\n" + "="*80)
    print("PREDICTABILITY ANALYSIS SUMMARY")
    print("="*80)
    
    print(f"\nTotal Markets Analyzed: {len(market_summary)}")
    print(f"Overall Accuracy: {market_summary['accuracy'].mean()*100:.1f}%")
    
    print(f"\nAccuracy by Time:")
    print(f"{'Minutes':<10} {'Accuracy':<12} {'Predictions':<15} {'Status':<20}")
    print("-" * 60)
    
    for _, row in accuracy_df.iterrows():
        if row['total_predictions'] > 0:
            status = "HIGH CONFIDENCE" if row['accuracy'] >= 0.80 else "MODERATE" if row['accuracy'] >= 0.60 else "LOW"
            print(f"{row['minutes']:<10.1f} {row['accuracy']*100:<12.1f}% {row['total_predictions']:<15} {status:<20}")
    
    # Find when accuracy becomes reliable
    high_conf = accuracy_df[accuracy_df['accuracy'] >= 0.80]
    if len(high_conf) > 0:
        first_reliable = high_conf.iloc[0]
        print(f"\n[INFO] Predictions become 80%+ accurate at {first_reliable['minutes']:.1f} minutes")
    
    moderate_conf = accuracy_df[accuracy_df['accuracy'] >= 0.60]
    if len(moderate_conf) > 0:
        first_moderate = moderate_conf.iloc[0]
        print(f"[INFO] Predictions become 60%+ accurate at {first_moderate['minutes']:.1f} minutes")
    
    print(f"\nMarket-by-Market Results:")
    print(f"{'Market':<40} {'Winner':<8} {'Accuracy':<12}")
    print("-" * 65)
    for _, row in market_summary.iterrows():
        print(f"{row['market'][:38]:<40} {row['winner']:<8} {row['accuracy']*100:<12.1f}%")

def main():
    """Main analysis function"""
    print("="*80)
    print("PREDICTABILITY ANALYSIS")
    print("When does it become clear which side will win?")
    print("="*80)
    
    # Analyze all markets
    combined_df, market_summary = analyze_all_markets()
    
    if combined_df is None:
        print("No data to analyze!")
        return
    
    # Calculate accuracy over time
    accuracy_df = calculate_accuracy_by_time(combined_df)
    
    # Create visualizations
    output_path = 'testing_data/predictability_analysis.pdf'
    with PdfPages(output_path) as pdf:
        create_accuracy_chart(accuracy_df, pdf)
        create_prediction_distribution_chart(combined_df, pdf)
        create_individual_market_chart(combined_df, pdf)
    
    print(f"\n[SUCCESS] Analysis complete! Saved to {output_path}")
    
    # Print summary
    print_summary(accuracy_df, market_summary)

if __name__ == '__main__':
    main()

