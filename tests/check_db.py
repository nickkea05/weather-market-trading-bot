"""
Quick script to check PostgreSQL database tables and data
"""

import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()


def get_db_connection():
    """Get PostgreSQL connection from Railway DATABASE_URL"""
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise ValueError("DATABASE_URL environment variable not set")
    return psycopg2.connect(database_url)


def check_tables():
    """Check what tables exist and their row counts"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("=" * 60)
    print("DATABASE TABLES")
    print("=" * 60)
    
    # List all tables
    cur.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public'
        ORDER BY table_name
    """)
    
    tables = cur.fetchall()
    print(f"\nFound {len(tables)} table(s):")
    for (table_name,) in tables:
        print(f"  - {table_name}")
    
    # Check market_data table
    if any(t[0] == 'market_data' for t in tables):
        cur.execute("SELECT COUNT(*) FROM market_data")
        count = cur.fetchone()[0]
        print(f"\nmarket_data: {count} rows")
        
        if count > 0:
            cur.execute("SELECT DISTINCT market_slug FROM market_data ORDER BY market_slug")
            slugs = cur.fetchall()
            print(f"  Markets: {len(slugs)}")
            for (slug,) in slugs[:5]:  # Show first 5
                cur.execute("SELECT COUNT(*) FROM market_data WHERE market_slug = %s", (slug,))
                row_count = cur.fetchone()[0]
                print(f"    - {slug}: {row_count} rows")
            if len(slugs) > 5:
                print(f"    ... and {len(slugs) - 5} more")
            
            # Show latest row
            cur.execute("SELECT market_slug, timestamp, up_best_ask, down_best_ask FROM market_data ORDER BY timestamp DESC LIMIT 1")
            latest = cur.fetchone()
            if latest:
                print(f"\n  Latest row:")
                print(f"    Market: {latest[0]}")
                print(f"    Time: {latest[1]}")
                print(f"    UP: ${latest[2]:.3f}" if latest[2] else "    UP: None")
                print(f"    DOWN: ${latest[3]:.3f}" if latest[3] else "    DOWN: None")
    
    # Check trader_trades table (new structure)
    if any(t[0] == 'trader_trades' for t in tables):
        GABAGOOL_WALLET = "0x6031b6eed1c97e853c6e0f03ad3ce3529351f96d"
        TRADER_2_WALLET = "0x63ce342161250d705dc0b16df89036c8e5f9ba9a"
        
        cur.execute("SELECT COUNT(*) FROM trader_trades")
        total_count = cur.fetchone()[0]
        print(f"\ntrader_trades: {total_count} total rows")
        
        # Show breakdown by wallet
        for wallet, name in [(GABAGOOL_WALLET, "Gabagool"), (TRADER_2_WALLET, "Trader 2")]:
            cur.execute("SELECT COUNT(*) FROM trader_trades WHERE wallet_address = %s", (wallet,))
            wallet_count = cur.fetchone()[0]
            print(f"  {name} ({wallet[:10]}...): {wallet_count} trades")
            
            if wallet_count > 0:
                cur.execute("""
                    SELECT DISTINCT market_slug 
                    FROM trader_trades 
                    WHERE wallet_address = %s 
                    ORDER BY market_slug
                """, (wallet,))
                slugs = cur.fetchall()
                print(f"    Markets: {len(slugs)}")
                for (slug,) in slugs[:3]:
                    cur.execute("""
                        SELECT COUNT(*) 
                        FROM trader_trades 
                        WHERE market_slug = %s AND wallet_address = %s
                    """, (slug, wallet))
                    trade_count = cur.fetchone()[0]
                    print(f"      - {slug}: {trade_count} trades")
                if len(slugs) > 3:
                    print(f"      ... and {len(slugs) - 3} more")
    
    # Check old gabagool_trades table (backward compatibility)
    elif any(t[0] == 'gabagool_trades' for t in tables):
        cur.execute("SELECT COUNT(*) FROM gabagool_trades")
        count = cur.fetchone()[0]
        print(f"\ngabagool_trades (old table): {count} rows")
        
        if count > 0:
            cur.execute("SELECT DISTINCT market_slug FROM gabagool_trades ORDER BY market_slug")
            slugs = cur.fetchall()
            print(f"  Markets: {len(slugs)}")
            for (slug,) in slugs[:5]:
                cur.execute("SELECT COUNT(*) FROM gabagool_trades WHERE market_slug = %s", (slug,))
                trade_count = cur.fetchone()[0]
                print(f"    - {slug}: {trade_count} trades")
            if len(slugs) > 5:
                print(f"    ... and {len(slugs) - 5} more")
    
    cur.close()
    conn.close()
    
    print("\n" + "=" * 60)


if __name__ == "__main__":
    try:
        check_tables()
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

