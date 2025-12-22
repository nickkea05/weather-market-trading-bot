"""
Export PostgreSQL database to CSV files
Converts market_data and gabagool_trades tables to CSV files matching the format
used by test_csv_stream.py for compatibility with paper_trade_replay.py
"""

import os
import csv
import psycopg2
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

CSV_FOLDER = "testing_data"


def get_readable_filename(market_slug: str, start_time: datetime, end_time: datetime, suffix: str) -> str:
    """Create readable filename like: btc-15m_5-00pm_5-15pm_1765525500_market.csv"""
    timestamp = market_slug.split('-')[-1]
    
    try:
        from zoneinfo import ZoneInfo
        et_tz = ZoneInfo("America/New_York")
    except ImportError:
        from datetime import timedelta
        et_tz = timezone(timedelta(hours=-5))
    
    start_et = start_time.astimezone(et_tz)
    end_et = end_time.astimezone(et_tz)
    
    start_str = start_et.strftime("%I-%M%p").lstrip("0").lower()
    end_str = end_et.strftime("%I-%M%p").lstrip("0").lower()
    
    return f"btc-15m_{start_str}_{end_str}_{timestamp}_{suffix}.csv"


def get_db_connection():
    """Get PostgreSQL connection from Railway DATABASE_URL"""
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise ValueError("DATABASE_URL environment variable not set")
    return psycopg2.connect(database_url)


def export_market_data():
    """Export market_data table to CSV files, one per market"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Get all unique market slugs
    cur.execute("SELECT DISTINCT market_slug, MIN(timestamp) as start_time, MAX(timestamp) as end_time FROM market_data GROUP BY market_slug ORDER BY start_time")
    markets = cur.fetchall()
    
    print(f"[EXPORT] Found {len(markets)} markets to export")
    
    os.makedirs(CSV_FOLDER, exist_ok=True)
    
    for market_slug, start_time, end_time in markets:
        # Get market title (from first row)
        cur.execute("SELECT market_title FROM market_data WHERE market_slug = %s LIMIT 1", (market_slug,))
        title_row = cur.fetchone()
        market_title = title_row[0] if title_row else None
        
        # Get all data for this market
        cur.execute("""
            SELECT timestamp, up_best_ask, up_liquidity, down_best_ask, down_liquidity, combined_cost, is_arb
            FROM market_data
            WHERE market_slug = %s
            ORDER BY timestamp
        """, (market_slug,))
        
        rows = cur.fetchall()
        
        if not rows:
            continue
        
        # Create filename
        filename = get_readable_filename(market_slug, start_time, end_time, "market")
        csv_path = os.path.join(CSV_FOLDER, filename)
        
        # Write to CSV
        with open(csv_path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                'timestamp',
                'up_best_ask',
                'up_liquidity',
                'down_best_ask',
                'down_liquidity',
                'combined_cost',
                'is_arb'
            ])
            
            for row in rows:
                writer.writerow(row)
        
        print(f"[EXPORT] Exported {len(rows)} rows to {filename}")
    
    cur.close()
    conn.close()


def export_trader_trades():
    """Export trader_trades table to CSV files, one per market per trader"""
    # Wallet addresses (same as in test_postgres_stream.py)
    GABAGOOL_WALLET = "0x6031b6eed1c97e853c6e0f03ad3ce3529351f96d"
    TRADER_2_WALLET = "0x63ce342161250d705dc0b16df89036c8e5f9ba9a"
    TRACKED_WALLETS = [GABAGOOL_WALLET, TRADER_2_WALLET]
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Check if trader_trades table exists, otherwise check old gabagool_trades
    cur.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name = 'trader_trades'
        )
    """)
    has_trader_trades = cur.fetchone()[0]
    
    if has_trader_trades:
        # New table structure - export by wallet
        for wallet in TRACKED_WALLETS:
            # Get wallet name for filename
            if wallet == GABAGOOL_WALLET:
                wallet_name = "gabagool"
            else:
                wallet_name = f"trader_{wallet[:8]}"
            
            # Get all unique market slugs for this wallet
            cur.execute("""
                SELECT DISTINCT market_slug 
                FROM trader_trades 
                WHERE wallet_address = %s
                ORDER BY market_slug
            """, (wallet,))
            markets = cur.fetchall()
            
            print(f"[EXPORT] Found {len(markets)} markets with trades for {wallet_name}")
            
            for (market_slug,) in markets:
                # Get trades for this market and wallet
                cur.execute("""
                    SELECT timestamp, title, outcome, side, price, size, usdc_size
                    FROM trader_trades
                    WHERE market_slug = %s AND wallet_address = %s
                    ORDER BY timestamp
                """, (market_slug, wallet))
                
                rows = cur.fetchall()
                
                if not rows:
                    continue
                
                # Get start/end times from market_data to create filename
                cur.execute("""
                    SELECT MIN(timestamp), MAX(timestamp)
                    FROM market_data
                    WHERE market_slug = %s
                """, (market_slug,))
                time_row = cur.fetchone()
                
                if not time_row or not time_row[0]:
                    start_time = rows[0][0]
                    end_time = rows[-1][0]
                else:
                    start_time = time_row[0]
                    end_time = time_row[1]
                
                # Create filename with wallet name
                filename = get_readable_filename(market_slug, start_time, end_time, wallet_name)
                csv_path = os.path.join(CSV_FOLDER, filename)
                
                # Write to CSV
                with open(csv_path, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow([
                        'timestamp',
                        'title',
                        'outcome',
                        'side',
                        'price',
                        'size',
                        'usdcSize'
                    ])
                    
                    for row in rows:
                        writer.writerow([
                            row[0].isoformat() if isinstance(row[0], datetime) else row[0],
                            row[1], row[2], row[3], row[4], row[5], row[6]
                        ])
                
                print(f"[EXPORT] Exported {len(rows)} {wallet_name} trades to {filename}")
    else:
        # Old table structure - check for gabagool_trades
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'gabagool_trades'
            )
        """)
        if cur.fetchone()[0]:
            print("[EXPORT] Found old gabagool_trades table - please run migration first")
    
    cur.close()
    conn.close()


def main():
    print("=" * 60)
    print("  EXPORT POSTGRESQL DATABASE TO CSV")
    print("=" * 60)
    print()
    
    try:
        print("[EXPORT] Exporting market data...")
        export_market_data()
        print()
        
        print("[EXPORT] Exporting trader trades...")
        export_trader_trades()
        print()
        
        print("[EXPORT] Export complete! CSV files saved to:", CSV_FOLDER)
        
    except Exception as e:
        print(f"[EXPORT] Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()

