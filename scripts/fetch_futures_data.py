"""
Fetch Historical Futures Data from TopStep
===========================================

Generic script to fetch 1-minute historical data for any futures symbol.

Usage: python scripts/fetch_futures_data.py SYMBOL [--start YYYY-MM-DD] [--end YYYY-MM-DD]
Example: python scripts/fetch_futures_data.py MNQ --start 2025-10-06 --end 2025-12-07
"""
import pandas as pd
from datetime import datetime, timedelta
import pytz
import asyncio
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from project_x_py import ProjectX, ProjectXConfig
import argparse

load_dotenv()

async def fetch_futures_data(symbol: str, start_date: str = None, end_date: str = None):
    """Fetch historical futures data from TopStep"""
    
    # Default dates if not provided
    if end_date is None:
        end = datetime.now(pytz.UTC)
    else:
        end = datetime.strptime(end_date, "%Y-%m-%d").replace(tzinfo=pytz.UTC)
    
    if start_date is None:
        # Default to 60 days back
        start = end - timedelta(days=60)
    else:
        start = datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=pytz.UTC)
    
    days_to_fetch = (end.date() - start.date()).days
    
    print(f"Fetching {symbol} historical data...")
    print(f"  Date range: {start.date()} to {end.date()}")
    print(f"  Days: {days_to_fetch}")
    
    # Get credentials
    api_token = os.getenv('TOPSTEP_API_TOKEN')
    username = os.getenv('TOPSTEP_USERNAME')
    
    if not api_token or not username:
        print("❌ Error: Missing TOPSTEP_API_TOKEN or TOPSTEP_USERNAME in .env")
        return False
    
    # Connect to API
    client = ProjectX(
        username=username,
        api_key=api_token,
        config=ProjectXConfig()
    )
    
    await client.authenticate()
    print("✅ Authenticated")
    
    # Fetch data in chunks
    all_bars = []
    chunk_days = 7
    current_start = start
    
    while current_start < end:
        current_end = min(current_start + timedelta(days=chunk_days), end)
        print(f"  Fetching {current_start.strftime('%Y-%m-%d')} to {current_end.strftime('%Y-%m-%d')}...")
        
        bars_df = await client.get_bars(
            symbol=symbol,
            interval=1,
            unit=2,
            start_time=current_start,
            end_time=current_end,
            limit=10000
        )
        
        if bars_df is not None and len(bars_df) > 0:
            if hasattr(bars_df, 'to_pandas'):
                chunk_df = bars_df.to_pandas()
            else:
                chunk_df = bars_df
            all_bars.append(chunk_df)
            print(f"    ✅ {len(chunk_df)} bars")
        
        current_start = current_end
        await asyncio.sleep(0.5)
    
    if not all_bars:
        print("❌ No data fetched!")
        return False
    
    # Combine all chunks
    df = pd.concat(all_bars, ignore_index=True)
    
    if 'time' in df.columns:
        df.rename(columns={'time': 'timestamp'}, inplace=True)
    
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    if df['timestamp'].dt.tz is not None:
        df['timestamp'] = df['timestamp'].dt.tz_convert('UTC').dt.tz_localize(None)
    
    df = df.drop_duplicates(subset='timestamp', keep='last')
    df = df.sort_values('timestamp')
    
    # Save to file
    Path('data/historical_data').mkdir(parents=True, exist_ok=True)
    output_file = f'data/historical_data/{symbol}_1min.csv'
    df.to_csv(output_file, index=False)
    print(f"\n✅ Saved {len(df):,} bars to {output_file}")
    print(f"   Date range: {df['timestamp'].min()} to {df['timestamp'].max()}")
    
    return True

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Fetch futures historical data from TopStep')
    parser.add_argument('symbol', help='Futures symbol (e.g., ES, MES, NQ, MNQ)')
    parser.add_argument('--start', help='Start date (YYYY-MM-DD)', default=None)
    parser.add_argument('--end', help='End date (YYYY-MM-DD)', default=None)
    
    args = parser.parse_args()
    
    success = asyncio.run(fetch_futures_data(args.symbol.upper(), args.start, args.end))
    
    if success:
        print("\n" + "="*70)
        print("Next steps:")
        print(f"  1. Fill gaps: python scripts/fill_futures_gaps.py {args.symbol.upper()}")
        print(f"  2. Verify: python scripts/verify_futures_data.py {args.symbol.upper()}")
        print("="*70)
