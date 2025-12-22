"""
Quick test to verify gabagool trade fetching works correctly.
Fetches last 15 minutes of BTC trades and saves to CSV.
"""

import os
import csv
import requests
from datetime import datetime, timezone, timedelta

DATA_API = "https://data-api.polymarket.com"
CSV_FOLDER = "testing_data"
GABAGOOL_WALLET = "0x6031b6eed1c97e853c6e0f03ad3ce3529351f96d"


def fetch_and_save():
    # Time window: last 15 minutes
    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(minutes=15)
    
    print(f"Fetching gabagool trades from {start_time} to {end_time}")
    print(f"Wallet: {GABAGOOL_WALLET}")
    
    url = f"{DATA_API}/activity"
    params = {
        "user": GABAGOOL_WALLET,
        "type": "TRADE",
        "limit": 500
    }
    
    response = requests.get(url, params=params, timeout=30)
    print(f"API Status: {response.status_code}")
    
    if response.status_code != 200:
        print(f"Error: {response.text}")
        return
    
    trades = response.json()
    print(f"Total trades fetched: {len(trades)}")
    
    if trades:
        print(f"\nFirst trade sample:")
        print(f"  Keys: {list(trades[0].keys())}")
        print(f"  timestamp type: {type(trades[0].get('timestamp'))}")
        print(f"  timestamp value: {trades[0].get('timestamp')}")
    
    # Filter for BTC and time window
    filtered = []
    for t in trades:
        title = t.get('title', '')
        
        # Must be Bitcoin Up or Down 15-min market (not ETH, not hourly)
        # 15-min titles: "Bitcoin Up or Down - December 15, 5:45PM-6:00PM ET"
        # Hourly titles: "Bitcoin Up or Down - December 15, 5PM ET"
        if 'Bitcoin Up or Down' not in title:
            continue
        # 15-min markets have a time range with dash (e.g., "5:45PM-6:00PM")
        if 'AM-' not in title and 'PM-' not in title:
            continue
        
        ts_raw = t.get('timestamp', '')
        if ts_raw:
            try:
                # Handle both integer (Unix seconds) and string (ISO) timestamps
                if isinstance(ts_raw, int):
                    trade_time = datetime.fromtimestamp(ts_raw, tz=timezone.utc)
                elif isinstance(ts_raw, str):
                    if ts_raw.isdigit():
                        trade_time = datetime.fromtimestamp(int(ts_raw), tz=timezone.utc)
                    elif ts_raw.endswith('Z'):
                        trade_time = datetime.fromisoformat(ts_raw.replace('Z', '+00:00'))
                    else:
                        trade_time = datetime.fromisoformat(ts_raw)
                        if trade_time.tzinfo is None:
                            trade_time = trade_time.replace(tzinfo=timezone.utc)
                else:
                    print(f"Unknown timestamp type: {type(ts_raw)}")
                    continue
                
                # Check if within window
                buffer = timedelta(minutes=2)
                if trade_time < (start_time - buffer) or trade_time > (end_time + buffer):
                    continue
                
                filtered.append({
                    'timestamp': trade_time.isoformat(),
                    'title': title,
                    'outcome': t.get('outcome', ''),
                    'side': t.get('side', ''),
                    'price': t.get('price', ''),
                    'size': t.get('size', ''),
                    'usdcSize': t.get('usdcSize', '')
                })
                    
            except Exception as e:
                print(f"Error parsing timestamp {ts_raw}: {e}")
                continue
    
    print(f"\nFiltered BTC trades in last 15 min: {len(filtered)}")
    
    # Save to CSV
    os.makedirs(CSV_FOLDER, exist_ok=True)
    csv_path = os.path.join(CSV_FOLDER, "TEST_gabagool_fetch.csv")
    
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=[
            'timestamp', 'title', 'outcome', 'side', 'price', 'size', 'usdcSize'
        ])
        writer.writeheader()
        writer.writerows(filtered)
    
    print(f"\nSaved to: {csv_path}")
    
    if filtered:
        print("\nSample trades:")
        for trade in filtered[:5]:
            print(f"  {trade['timestamp']} | {trade['outcome']} | {trade['side']} | ${trade['price']} | {trade['size']} shares")


if __name__ == "__main__":
    fetch_and_save()

