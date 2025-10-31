import asyncio
from datetime import datetime, timedelta
import pytz
from project_x_py import ProjectX
import csv
import os

async def fetch_extended_history():
    """Fetch extended historical data by making multiple requests"""
    print("="*70)
    print("Fetching EXTENDED ES Historical Data")
    print("="*70)
    
    px = ProjectX(
        username='kevinsuero072897@gmail.com',
        api_key='8SIwAhS0+28Qt/yAqNb7a84nfUjd3v4h9IhbVoyOmik='
    )
    
    print("\n[1/4] Authenticating...")
    await px.authenticate()
    print("✓ Authenticated")
    
    all_bars = {}  # Use dict to deduplicate by timestamp
    
    # Make multiple requests for different time periods
    # Each request can return max 20,000 bars
    # 20,000 bars ≈ 14 full trading days
    
    requests = [
        ("Recent data (last 20 days)", 20),
        ("Mid-range (20-40 days ago)", 40),
        ("Older data (40-60 days ago)", 60),
        ("Extended (60-90 days ago)", 90),
    ]
    
    print("\n[2/4] Fetching data in chunks...")
    for desc, days in requests:
        print(f"\n  {desc}...")
        try:
            bars_df = await px.get_bars(
                symbol='ES',
                interval=1,
                unit=2,
                days=days
            )
            
            if bars_df is not None and len(bars_df) > 0:
                print(f"    ✓ Got {len(bars_df):,} bars: {bars_df['timestamp'].min()} to {bars_df['timestamp'].max()}")
                
                # Add to collection (dict deduplicates automatically)
                for row in bars_df.iter_rows(named=True):
                    ts = row['timestamp'].isoformat()
                    all_bars[ts] = {
                        'timestamp': ts,
                        'open': f"{row['open']:.2f}",
                        'high': f"{row['high']:.2f}",
                        'low': f"{row['low']:.2f}",
                        'close': f"{row['close']:.2f}",
                        'volume': str(row['volume'])
                    }
            else:
                print(f"    ✗ No data")
        except Exception as e:
            print(f"    ✗ Error: {e}")
    
    if not all_bars:
        print("\n✗ No data collected!")
        return
    
    print(f"\n[3/4] Deduplicating and sorting...")
    print(f"  Total unique bars: {len(all_bars):,}")
    
    # Sort by timestamp
    sorted_bars = sorted(all_bars.items())
    
    # Save to CSV
    print("\n[4/4] Saving to CSV...")
    output_file = './historical_data/ES_1min.csv'
    os.makedirs('./historical_data', exist_ok=True)
    
    with open(output_file, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        writer.writeheader()
        for _, bar_data in sorted_bars:
            writer.writerow(bar_data)
    
    first_ts = sorted_bars[0][0]
    last_ts = sorted_bars[-1][0]
    
    print(f"✓ Saved {len(sorted_bars):,} bars")
    print(f"  From: {first_ts}")
    print(f"  To:   {last_ts}")
    print(f"\n✓ Complete! Run 'python analyze_coverage.py' for details")

if __name__ == "__main__":
    asyncio.run(fetch_extended_history())
