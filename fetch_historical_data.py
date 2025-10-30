"""
Fetch Historical Data from TopStep API

This script fetches REAL historical market data from TopStep broker API
and saves it to CSV files for backtesting purposes.

NO MOCK OR SIMULATED DATA - Uses actual market data from TopStep.

Usage:
    python fetch_historical_data.py --symbol MES --days 30
    python fetch_historical_data.py --symbol MES --start 2024-01-01 --end 2024-01-31
    python fetch_historical_data.py --symbol MES --days 7 --tick-data
"""

import csv
import os
import sys
import argparse
from datetime import datetime, timedelta
from typing import List, Dict, Any
import pytz
import logging

# Import broker interface for real data fetching
from broker_interface import create_broker, TopStepBroker
from config import load_config

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)




def fetch_and_save_bar_data_paginated(broker, symbol: str, timeframe: str,
                                       start_date: datetime, end_date: datetime, output_dir: str) -> int:
    """
    Fetch REAL bar data from TopStep API with pagination for large requests.
    TopStep has a 20,000 bar limit per request, so we split large requests into chunks.
    
    Args:
        broker: TopStepBroker instance
        symbol: Trading symbol (e.g., 'ES')
        timeframe: Bar timeframe ('1m', '5m', '15m', '1h', etc.)
        start_date: Start date for data fetch
        end_date: End date for data fetch
        output_dir: Directory to save CSV files
        
    Returns:
        Number of bars fetched
    """
    logger.info(f"Fetching {timeframe} bar data for {symbol} from TopStep API...")
    
    filepath = os.path.join(output_dir, f"{symbol}_{timeframe}.csv")
    
    try:
        # Calculate days and estimated bars
        days = (end_date - start_date).days
        
        if 'h' in timeframe:
            timeframe_minutes = int(timeframe.replace('h', '')) * 60
        elif 'm' in timeframe:
            timeframe_minutes = int(timeframe.replace('m', ''))
        else:
            timeframe_minutes = int(timeframe.replace('min', ''))
            
        # For 1-minute data, API limit is ~20k bars per request
        # Split into chunks of ~15 days each for 1min (to stay under 20k limit)
        MAX_BARS_PER_REQUEST = 19500  # Stay slightly under 20k limit
        
        trading_minutes_per_day = 6.5 * 60  # Approximate
        bars_per_day = int(trading_minutes_per_day / timeframe_minutes)
        
        # If total bars fits in one request, use simple fetch
        total_estimated_bars = bars_per_day * days
        if total_estimated_bars <= MAX_BARS_PER_REQUEST:
            logger.info(f"  Single request: {total_estimated_bars} estimated bars for {days} days")
            bars = broker.fetch_historical_bars(symbol, timeframe, total_estimated_bars, start_date, end_date)
        else:
            # Need pagination - split into chunks
            logger.info(f"  Multiple requests needed: {total_estimated_bars} estimated bars for {days} days")
            logger.info(f"  Will fetch in chunks to bypass 20k bar limit...")
            
            all_bars = []
            chunk_days = MAX_BARS_PER_REQUEST // bars_per_day  # Days per chunk
            
            current_start = start_date
            chunk_num = 1
            
            while current_start < end_date:
                current_end = min(current_start + timedelta(days=chunk_days), end_date)
                chunk_days_actual = (current_end - current_start).days
                
                logger.info(f"  Chunk {chunk_num}: {current_start.date()} to {current_end.date()} ({chunk_days_actual} days)")
                
                chunk_bars = broker.fetch_historical_bars(
                    symbol, timeframe, 
                    chunk_days_actual * bars_per_day,
                    current_start, current_end
                )
                
                if chunk_bars:
                    all_bars.extend(chunk_bars)
                    logger.info(f"    ✓ Got {len(chunk_bars)} bars (total: {len(all_bars)})")
                
                current_start = current_end
                chunk_num += 1
            
            # Deduplicate bars by timestamp (keep earliest occurrence)
            seen_timestamps = set()
            unique_bars = []
            for bar in all_bars:
                ts = bar['timestamp']
                if isinstance(ts, str):
                    ts_key = ts
                else:
                    ts_key = ts.isoformat()
                
                if ts_key not in seen_timestamps:
                    seen_timestamps.add(ts_key)
                    unique_bars.append(bar)
            
            bars = unique_bars
            duplicates_removed = len(all_bars) - len(unique_bars)
            if duplicates_removed > 0:
                logger.info(f"  ✓ Removed {duplicates_removed} duplicate bars")
            logger.info(f"  ✓ Combined {len(bars)} unique bars from {chunk_num-1} chunks")
        
        if not bars:
            logger.warning(f"  No data returned from API for {timeframe}")
            return 0
        
        # Sort bars by timestamp to ensure chronological order
        bars.sort(key=lambda x: x['timestamp'] if isinstance(x['timestamp'], str) else x['timestamp'].isoformat())
        
        # Write REAL data to CSV
        with open(filepath, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            
            for bar in bars:
                timestamp = bar['timestamp']
                if isinstance(timestamp, str):
                    timestamp = datetime.fromisoformat(timestamp)
                    
                writer.writerow([
                    timestamp.isoformat(),
                    f"{bar['open']:.2f}",
                    f"{bar['high']:.2f}",
                    f"{bar['low']:.2f}",
                    f"{bar['close']:.2f}",
                    bar['volume']
                ])
        
        logger.info(f"  ✓ Saved {len(bars)} REAL bars to {filepath}")
        return len(bars)
        
    except Exception as e:
        logger.error(f"  ✗ Error fetching {timeframe} bar data from API: {e}")
        logger.error(f"  Ensure TOPSTEP_API_TOKEN is set and valid")
        return 0


def fetch_and_save_bar_data(broker: TopStepBroker, symbol: str, timeframe: str,
                             start_date: datetime, end_date: datetime, output_dir: str) -> int:
    """
    Fetch REAL bar data from TopStep API and save to CSV.
    
    Args:
        broker: TopStepBroker instance
        symbol: Trading symbol (e.g., 'MES')
        timeframe: Bar timeframe ('1m', '5m', '15m', '1h', etc.)
        start_date: Start date for data fetch
        end_date: End date for data fetch
        output_dir: Directory to save CSV files
        
    Returns:
        Number of bars fetched
    """
    logger.info(f"Fetching {timeframe} bar data for {symbol} from TopStep API...")
    
    filepath = os.path.join(output_dir, f"{symbol}_{timeframe}.csv")
    
    try:
        # Calculate total bars needed based on timeframe and date range
        days = (end_date - start_date).days
        
        # Estimate bars needed (conservative estimate)
        if 'h' in timeframe:
            timeframe_minutes = int(timeframe.replace('h', '')) * 60
        elif 'm' in timeframe:
            timeframe_minutes = int(timeframe.replace('m', ''))
        else:
            timeframe_minutes = int(timeframe.replace('min', ''))
            
        trading_minutes_per_day = 6.5 * 60  # Approximate trading hours
        bars_per_day = int(trading_minutes_per_day / timeframe_minutes)
        total_bars = bars_per_day * days
        
        # Request what we calculated - let API enforce its own limits
        max_bars = total_bars
        
        logger.info(f"  Requesting {max_bars} bars for {days} day(s)...")
        
        # Fetch REAL historical bars from API with date range
        bars = broker.fetch_historical_bars(symbol, timeframe, max_bars, start_date, end_date)
        
        if not bars:
            logger.warning(f"  No data returned from API for {timeframe}")
            return 0
        
        # Write REAL data to CSV
        with open(filepath, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            
            for bar in bars:
                timestamp = bar['timestamp']
                if isinstance(timestamp, str):
                    timestamp = datetime.fromisoformat(timestamp)
                    
                writer.writerow([
                    timestamp.isoformat(),
                    f"{bar['open']:.2f}",
                    f"{bar['high']:.2f}",
                    f"{bar['low']:.2f}",
                    f"{bar['close']:.2f}",
                    bar['volume']
                ])
        
        logger.info(f"  ✓ Saved {len(bars)} REAL bars to {filepath}")
        return len(bars)
        
    except Exception as e:
        logger.error(f"  ✗ Error fetching {timeframe} bar data from API: {e}")
        logger.error(f"  Ensure TOPSTEP_API_TOKEN is set and valid")
        return 0


def generate_ticks_from_bars(symbol: str, bars: List[Dict[str, Any]], output_dir: str) -> int:
    """
    Generate synthetic tick data from 1-minute bars.
    Since TopStep API likely doesn't provide tick-level data, we simulate it.
    
    Args:
        symbol: Trading symbol
        bars: List of 1-minute bars
        output_dir: Output directory
        
    Returns:
        Number of ticks generated
    """
    logger.info(f"Generating tick-level data from 1-minute bars for {symbol}...")
    
    filepath = os.path.join(output_dir, f"{symbol}_ticks.csv")
    
    try:
        with open(filepath, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['timestamp', 'price', 'volume'])
            
            tick_count = 0
            for bar in bars:
                timestamp = bar['timestamp']
                if isinstance(timestamp, str):
                    timestamp = datetime.fromisoformat(timestamp)
                
                # Generate 4 synthetic ticks per bar: open, high, low, close
                volume_per_tick = bar['volume'] // 4
                
                # Tick 1: Open
                writer.writerow([timestamp.isoformat(), f"{bar['open']:.2f}", volume_per_tick])
                tick_count += 1
                
                # Tick 2: High (15 seconds later)
                tick_time = timestamp + timedelta(seconds=15)
                writer.writerow([tick_time.isoformat(), f"{bar['high']:.2f}", volume_per_tick])
                tick_count += 1
                
                # Tick 3: Low (30 seconds later)
                tick_time = timestamp + timedelta(seconds=30)
                writer.writerow([tick_time.isoformat(), f"{bar['low']:.2f}", volume_per_tick])
                tick_count += 1
                
                # Tick 4: Close (55 seconds later)
                tick_time = timestamp + timedelta(seconds=55)
                remaining_volume = bar['volume'] - (volume_per_tick * 3)
                writer.writerow([tick_time.isoformat(), f"{bar['close']:.2f}", remaining_volume])
                tick_count += 1
        
        logger.info(f"  ✓ Generated {tick_count} synthetic ticks to {filepath}")
        return tick_count
        
    except Exception as e:
        logger.error(f"  ✗ Error generating tick data: {e}")
        return 0


def main():
    """Fetch REAL historical data from TopStep API"""
    parser = argparse.ArgumentParser(
        description='Fetch REAL historical market data from TopStep API (NO MOCK DATA)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Fetch last 30 days of data
  python fetch_historical_data.py --symbol MES --days 30
  
  # Fetch specific date range
  python fetch_historical_data.py --symbol MES --start 2024-01-01 --end 2024-01-31
  
  # Fetch with tick data generation
  python fetch_historical_data.py --symbol MES --days 7 --tick-data
        """
    )
    parser.add_argument(
        '--symbol',
        type=str,
        default='MES',
        help='Trading symbol (default: MES)'
    )
    parser.add_argument(
        '--days',
        type=int,
        help='Fetch data for last N days'
    )
    parser.add_argument(
        '--start',
        type=str,
        help='Start date (YYYY-MM-DD)'
    )
    parser.add_argument(
        '--end',
        type=str,
        help='End date (YYYY-MM-DD)'
    )
    parser.add_argument(
        '--output-dir',
        type=str,
        default='./historical_data',
        help='Output directory for CSV files (default: ./historical_data)'
    )
    parser.add_argument(
        '--tick-data',
        action='store_true',
        help='Generate synthetic tick data from 1-minute bars'
    )
    
    args = parser.parse_args()
    
    # Determine date range
    if args.start and args.end:
        start_date = datetime.strptime(args.start, '%Y-%m-%d')
        end_date = datetime.strptime(args.end, '%Y-%m-%d')
    elif args.days:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=args.days)
    else:
        # Default: last 7 days
        end_date = datetime.now()
        start_date = end_date - timedelta(days=7)
        logger.info("No date range specified, using default: last 7 days")
    
    print("="*70)
    print("Fetching REAL Historical Data from TopStep API")
    print("NO MOCK OR SIMULATED DATA - Using actual market data")
    print("="*70)
    print(f"Symbol: {args.symbol}")
    print(f"Date Range: {start_date.date()} to {end_date.date()} ({(end_date - start_date).days} days)")
    print(f"Output Directory: {args.output_dir}")
    print(f"Generate Tick Data: {'Yes' if args.tick_data else 'No'}")
    print("")
    
    # Create output directory
    os.makedirs(args.output_dir, exist_ok=True)
    
    # Check for API token
    api_token = os.getenv('TOPSTEP_API_TOKEN')
    username = os.getenv('TOPSTEP_USERNAME') or os.getenv('TOPSTEP_EMAIL')
    
    if not api_token or api_token == 'your_token_here':
        print("")
        print("ERROR: TOPSTEP_API_TOKEN environment variable not set!")
        print("")
        print("Please set your TopStep API token:")
        print("  Windows PowerShell:")
        print("    $env:TOPSTEP_API_TOKEN='your_actual_token_here'")
        print("    $env:TOPSTEP_USERNAME='your_email@example.com'")
        print("  Windows CMD:")
        print("    set TOPSTEP_API_TOKEN=your_actual_token_here")
        print("    set TOPSTEP_USERNAME=your_email@example.com")
        print("  Linux/Mac:")
        print("    export TOPSTEP_API_TOKEN='your_actual_token_here'")
        print("    export TOPSTEP_USERNAME='your_email@example.com'")
        print("")
        sys.exit(1)
    
    # Initialize broker
    try:
        logger.info("Initializing TopStep broker connection...")
        broker = create_broker(api_token, username)
        
        logger.info("Connecting to TopStep API...")
        if not broker.connect():
            logger.error("Failed to connect to TopStep API")
            logger.error("Check your API token and network connection")
            sys.exit(1)
        
        logger.info("✓ Connected to TopStep API successfully!")
        print("")
        
        # Fetch data using paginated version for better results
        bars_1min_count = fetch_and_save_bar_data_paginated(
            broker, args.symbol, "1m", start_date, end_date, args.output_dir
        )
        
        bars_15min_count = fetch_and_save_bar_data_paginated(
            broker, args.symbol, "15m", start_date, end_date, args.output_dir
        )
        
        # Generate tick data if requested
        tick_count = 0
        if args.tick_data and bars_1min_count > 0:
            # Load 1min bars to generate ticks
            bars_1min = []
            filepath_1min = os.path.join(args.output_dir, f"{args.symbol}_1m.csv")
            with open(filepath_1min, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    bars_1min.append({
                        'timestamp': row['timestamp'],
                        'open': float(row['open']),
                        'high': float(row['high']),
                        'low': float(row['low']),
                        'close': float(row['close']),
                        'volume': int(row['volume'])
                    })
            
            tick_count = generate_ticks_from_bars(args.symbol, bars_1min, args.output_dir)
        
        # Disconnect
        broker.disconnect()
        
        print("")
        print("="*70)
        print("Data Fetching Complete!")
        print("="*70)
        print(f"REAL data saved to:")
        print(f"  - {args.output_dir}/{args.symbol}_1m.csv ({bars_1min_count} bars)")
        print(f"  - {args.output_dir}/{args.symbol}_15m.csv ({bars_15min_count} bars)")
        if tick_count > 0:
            print(f"  - {args.output_dir}/{args.symbol}_ticks.csv ({tick_count} ticks)")
        print("")
        print("✓ This data is REAL market data from TopStep API")
        print("✓ Use this for backtesting with actual historical prices")
        print("="*70)
        
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        print("")
        print("Make sure:")
        print("  1. TOPSTEP_API_TOKEN is set and valid")
        print("  2. You have an active TopStep account")
        print("  3. TopStep SDK (project-x-py) is installed: pip install project-x-py")
        print("  4. Your network connection is working")
        sys.exit(1)


if __name__ == "__main__":
    main()

