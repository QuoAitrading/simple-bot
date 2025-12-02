#!/usr/bin/env python3
"""
Simple script to download ES data for the last 3 days from TopStep  
"""
import sys
import os
import asyncio
from datetime import datetime, timedelta
import pytz
import logging

# Suppress project_x_py loggers before importing the SDK
class _SuppressProjectXLoggers(logging.Filter):
    def filter(self, record):
        return not record.name.startswith('project_x_py')

logging.getLogger().addFilter(_SuppressProjectXLoggers())

_px_logger = logging.getLogger('project_x_py')
_px_logger.setLevel(logging.CRITICAL + 1)
_px_logger.propagate = False
_px_logger.handlers = []
_px_logger.addHandler(logging.NullHandler())
_px_logger.disabled = True

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), 'src'))

from project_x_py import ProjectX, ProjectXConfig
from config import load_config

async def main():
    print("🔌 Connecting to TopStep...")
    
    config = load_config()
    api_token = getattr(config, 'broker_token', None) or config.api_token
    username = getattr(config, 'broker_username', None) or config.username
    
    client = ProjectX(username=username, api_key=api_token, config=ProjectXConfig())
    await client.authenticate()
    print("✅ Connected")
    
    # Find ES contract
    print("\n🔍 Finding ES contract...")
    instruments = await client.search_instruments(query="ES")
    es = instruments[0]
    
    contract_id = es.id
    symbol_name = es.name
    print(f"   Found: {symbol_name} ({contract_id})")
    
    # Define full date range (Aug 31 to Now)
    tz = pytz.timezone('America/New_York')
    # Start from Aug 31
    start_dt_naive = datetime(2025, 8, 31, 18, 0, 0)
    end_dt_naive = datetime(2025, 11, 26, 23, 59, 59)
    
    print(f"\n📊 Fetching FULL HISTORY from {start_dt_naive} to {end_dt_naive} (ET)...")
    print("   This will overwrite the existing file to ensure consistency and fix all gaps.")
    
    csv_path = 'data/historical_data/ES_1min.csv'
    
    # Create/Overwrite file with header
    with open(csv_path, 'w') as f:
        f.write("timestamp,open,high,low,close,volume\n")
        
    # Fetch in 1-day chunks to avoid limits and ensure reliability
    current_naive = start_dt_naive
    total_bars = 0
    
    while current_naive < end_dt_naive:
        # Calculate next day naive
        next_naive = current_naive + timedelta(days=1)
        if next_naive > end_dt_naive:
            next_naive = end_dt_naive
            
        # Localize both to get correct UTC timestamps for the API
        current_start = tz.localize(current_naive)
        current_end = tz.localize(next_naive)
        
        print(f"   Fetching: {current_start} -> {current_end}")
        
        try:
            # Fetch chunk
            bars = await client.get_bars(
                symbol=symbol_name,
                start_time=current_start,
                end_time=current_end,
                interval=1,
                unit=2,  # Minutes
                limit=5000 # Ensure we get all bars for the day
            )
            
            # Check if empty (works for list or DataFrame if we check length carefully)
            is_empty = False
            if bars is None:
                is_empty = True
            elif hasattr(bars, 'is_empty'):
                is_empty = bars.is_empty()
            elif hasattr(bars, '__len__'):
                is_empty = len(bars) == 0
            
            if is_empty:
                print("   ⚠️ No bars in this chunk (might be weekend)")
            else:
                # Convert to list if needed
                if hasattr(bars, 'to_dicts'):
                    bars_list = bars.to_dicts()
                elif hasattr(bars, 'to_dict'):
                    bars_list = bars.to_dict('records')
                else:
                    bars_list = bars
                
                print(f"   ✅ Got {len(bars_list)} bars")
                
                # Process and append
                chunk_bars = []
                for bar in bars_list:
                    # Handle timestamp
                    ts_val = bar.get('timestamp') or bar.get('time') or bar.get('date') or bar.get('ts') or bar.get('datetime')
                    
                    if ts_val is None:
                        continue
                        
                    # Normalize to datetime
                    if isinstance(ts_val, (int, float)):
                        if ts_val > 10000000000: ts_val /= 1000.0
                        ts_obj = datetime.fromtimestamp(ts_val, tz=pytz.UTC).astimezone(tz)
                    elif isinstance(ts_val, datetime):
                        if ts_val.tzinfo is None: ts_val = pytz.UTC.localize(ts_val)
                        ts_obj = ts_val.astimezone(tz)
                    else:
                        continue
                        
                    chunk_bars.append((ts_obj, bar))
                
                # Sort
                chunk_bars.sort(key=lambda x: x[0])
                
                # Write chunk
                with open(csv_path, 'a') as f:
                    for ts_obj, bar in chunk_bars:
                        o = bar.get('open')
                        h = bar.get('high')
                        l = bar.get('low')
                        c = bar.get('close')
                        v = bar.get('volume') or bar.get('vol') or 0
                        f.write(f"{ts_obj.strftime('%Y-%m-%d %H:%M:%S')},{o},{h},{l},{c},{v}\n")
                
                total_bars += len(chunk_bars)
                print(f"   📝 Appended {len(chunk_bars)} bars (Total: {total_bars})")
                
        except Exception as e:
            print(f"   ❌ Error fetching chunk: {e}")
            import traceback
            traceback.print_exc()
        
        # Move to next day
        current_naive = next_naive
        # Small pause to be nice to API
        await asyncio.sleep(0.5)

    print(f"\n✅ COMPLETE! Downloaded {total_bars} bars to {csv_path}")

if __name__ == "__main__":
    asyncio.run(main())
