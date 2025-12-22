#!/usr/bin/env python3
"""Test script to verify CSV file writing on Railway"""

import csv
from pathlib import Path
from datetime import datetime

# Create directory if it doesn't exist
Path("testing_data").mkdir(exist_ok=True)

csv_path = "testing_data/market_results.csv"

# Test data
fieldnames = [
    'market_number', 'timestamp', 'market_slug', 'profit', 'total_cost', 'roi',
    'worst_case', 'best_case', 'winner', 'total_trades', 'arb_trades', 
    'accumulate_trades', 'rebalance_trades', 'up_shares', 'down_shares',
    'up_avg', 'down_avg', 'running_avg_profit', 'running_total_profit',
    'running_total_cost', 'running_avg_roi', 'running_avg_trades',
    'win_rate', 'total_wins', 'total_losses'
]

# Test data rows
test_data = [
    {
        'market_number': 1,
        'timestamp': datetime.now().isoformat(),
        'market_slug': 'test-market-1',
        'profit': 10.50,
        'total_cost': 100.00,
        'roi': 10.5,
        'worst_case': 5.00,
        'best_case': 15.00,
        'winner': 'UP',
        'total_trades': 20,
        'arb_trades': 5,
        'accumulate_trades': 15,
        'rebalance_trades': 0,
        'up_shares': 50.0,
        'down_shares': 50.0,
        'up_avg': 0.50,
        'down_avg': 0.50,
        'running_avg_profit': 10.50,
        'running_total_profit': 10.50,
        'running_total_cost': 100.00,
        'running_avg_roi': 10.5,
        'running_avg_trades': 20,
        'win_rate': 100.0,
        'total_wins': 1,
        'total_losses': 0
    },
    {
        'market_number': 2,
        'timestamp': datetime.now().isoformat(),
        'market_slug': 'test-market-2',
        'profit': -5.25,
        'total_cost': 150.00,
        'roi': -3.5,
        'worst_case': -10.00,
        'best_case': 0.00,
        'winner': 'DOWN',
        'total_trades': 25,
        'arb_trades': 8,
        'accumulate_trades': 17,
        'rebalance_trades': 0,
        'up_shares': 75.0,
        'down_shares': 75.0,
        'up_avg': 0.52,
        'down_avg': 0.48,
        'running_avg_profit': 2.625,
        'running_total_profit': 5.25,
        'running_total_cost': 250.00,
        'running_avg_roi': 3.5,
        'running_avg_trades': 22.5,
        'win_rate': 50.0,
        'total_wins': 1,
        'total_losses': 1
    }
]

print("=" * 80)
print("TESTING CSV FILE WRITE")
print("=" * 80)
print(f"Writing to: {csv_path}")
print(f"Absolute path: {Path(csv_path).absolute()}")

try:
    # Write to CSV
    with open(csv_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in test_data:
            writer.writerow(row)
    
    print(f"[SUCCESS] File written successfully!")
    
    # Verify by reading it back
    print(f"\nVerifying file contents...")
    with open(csv_path, 'r', newline='') as f:
        content = f.read()
        lines = content.strip().split('\n')
        print(f"[SUCCESS] File has {len(lines)} lines (including header)")
        print(f"\nFirst 3 lines:")
        for i, line in enumerate(lines[:3], 1):
            print(f"  {i}: {line[:100]}..." if len(line) > 100 else f"  {i}: {line}")
    
    # Check file size
    file_size = Path(csv_path).stat().st_size
    print(f"\n[SUCCESS] File size: {file_size} bytes")
    print(f"[SUCCESS] File exists: {Path(csv_path).exists()}")
    
    print("\n" + "=" * 80)
    print("TEST COMPLETE - File write appears successful!")
    print("=" * 80)
    
except Exception as e:
    print(f"\n[ERROR] ERROR writing file: {e}")
    import traceback
    traceback.print_exc()
    print("=" * 80)

