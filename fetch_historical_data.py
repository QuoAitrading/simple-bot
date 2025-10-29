"""
Fetch Historical Data from TopStep API

This script fetches REAL historical market data from TopStep broker API
and saves it to CSV files for backtesting purposes.

NO MOCK OR SIMULATED DATA - Uses actual market data from TopStep.

Usage:
    python fetch_historical_data.py --symbol MES --days 30
    python fetch_historical_data.py --symbol MES --start 2024-01-01 --end 2024-01-31
"""

import csv
import os
import sys
import argparse
from datetime import datetime, timedelta
from typing import List, Dict, Any
import pytz

# Import broker interface for real data fetching
from broker_interface import BrokerInterface
from config import load_config


def fetch_and_save_tick_data(broker: BrokerInterface, symbol: str, start_date: datetime, 
                              end_date: datetime, output_dir: str) -> None:
    """
    Fetch REAL tick data from TopStep API and save to CSV.
    
    Note: TopStep API may not provide tick-level data. 
    This will use the finest granularity available (likely 1-minute bars).
    """
    print(f"Fetching tick/finest granularity data for {symbol}...")
    
    filepath = os.path.join(output_dir, f"{symbol}_ticks.csv")
    
    try:
        # Calculate number of days
        days = (end_date - start_date).days
        
        # Fetch bars in chunks (API may have limits)
        all_bars = []
        for day_offset in range(days + 1):
            current_date = start_date + timedelta(days=day_offset)
            
            # Fetch 1-minute bars for this day from REAL API
            bars = broker.fetch_historical_bars(symbol, "1m", 500)
            
            if bars:
                all_bars.extend(bars)
        
        # Write REAL data to CSV (convert bars to tick-like format)
        with open(filepath, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['timestamp', 'price', 'volume'])
            
            for bar in all_bars:
                # Use bar's close price and volume as tick data
                writer.writerow([
                    bar['timestamp'].isoformat(),
                    f"{bar['close']:.2f}",
                    bar['volume']
                ])
        
        print(f"  ✓ Saved {len(all_bars)} REAL data points to {filepath}")
        
    except Exception as e:
        print(f"  ✗ Error fetching tick data from API: {e}")
        print(f"  Ensure TOPSTEP_API_TOKEN is set and valid")


def fetch_and_save_bar_data(broker: BrokerInterface, symbol: str, timeframe: str,
                             start_date: datetime, end_date: datetime, output_dir: str) -> None:
    """
    Fetch REAL bar data from TopStep API and save to CSV.
    
    Args:
        broker: BrokerInterface instance
        symbol: Trading symbol (e.g., 'MES')
        timeframe: Bar timeframe ('1m', '5m', '15m', '1h', etc.)
        start_date: Start date for data fetch
        end_date: End date for data fetch
        output_dir: Directory to save CSV files
    """
    print(f"Fetching {timeframe} bar data for {symbol} from TopStep API...")
    
    filepath = os.path.join(output_dir, f"{symbol}_{timeframe}.csv")
    
    try:
        # Calculate total bars needed based on timeframe and date range
        days = (end_date - start_date).days
        
        # Estimate bars needed (conservative estimate)
        timeframe_minutes = int(timeframe.replace('m', '').replace('h', '')) * (60 if 'h' in timeframe else 1)
        trading_minutes_per_day = 6.5 * 60  # Approximate
        bars_per_day = int(trading_minutes_per_day / timeframe_minutes)
        total_bars = bars_per_day * days
        
        # Fetch REAL historical bars from API
        bars = broker.fetch_historical_bars(symbol, timeframe, min(total_bars, 5000))
        
        # Write REAL data to CSV
        with open(filepath, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            
            for bar in bars:
                writer.writerow([
                    bar['timestamp'].isoformat(),
                    f"{bar['open']:.2f}",
                    f"{bar['high']:.2f}",
                    f"{bar['low']:.2f}",
                    f"{bar['close']:.2f}",
                    bar['volume']
                ])
        
        print(f"  ✓ Saved {len(bars)} REAL bars to {filepath}")
        
    except Exception as e:
        print(f"  ✗ Error fetching {timeframe} bar data from API: {e}")
        print(f"  Ensure TOPSTEP_API_TOKEN is set and valid")


def main():
    """Fetch REAL historical data from TopStep API"""
    parser = argparse.ArgumentParser(
        description='Fetch REAL historical market data from TopStep API (NO MOCK DATA)'
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
    
    print("="*60)
    print("Fetching REAL Historical Data from TopStep API")
    print("NO MOCK OR SIMULATED DATA - Using actual market data")
    print("="*60)
    print(f"Symbol: {args.symbol}")
    print(f"Date Range: {start_date.date()} to {end_date.date()}")
    print(f"Output Directory: {args.output_dir}")
    print("")
    
    # Create output directory
    os.makedirs(args.output_dir, exist_ok=True)
    
    # Load configuration and initialize broker
    try:
        config = load_config('development')
        
        if not config.api_token or config.api_token == 'your_token_here':
            print("ERROR: TOPSTEP_API_TOKEN not set!")
            print("Set environment variable: export TOPSTEP_API_TOKEN='your_real_token'")
            sys.exit(1)
        
        broker = BrokerInterface(config)
        
        print("Connecting to TopStep API...")
        
        # Fetch REAL data from TopStep API
        fetch_and_save_tick_data(broker, args.symbol, start_date, end_date, args.output_dir)
        fetch_and_save_bar_data(broker, args.symbol, "1min", start_date, end_date, args.output_dir)
        fetch_and_save_bar_data(broker, args.symbol, "15min", start_date, end_date, args.output_dir)
        
        print("")
        print("="*60)
        print("Data Fetching Complete!")
        print("="*60)
        print(f"REAL data saved to:")
        print(f"  - {args.output_dir}/{args.symbol}_ticks.csv")
        print(f"  - {args.output_dir}/{args.symbol}_1min.csv")
        print(f"  - {args.output_dir}/{args.symbol}_15min.csv")
        print("")
        print("This data is REAL market data from TopStep.")
        print("Use this for backtesting with actual historical prices.")
        print("="*60)
        
    except Exception as e:
        print(f"Error: {e}")
        print("Make sure TOPSTEP_API_TOKEN is set and valid")
        print("The script only fetches REAL data from TopStep API")
        sys.exit(1)


if __name__ == "__main__":
    main()
