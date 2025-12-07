"""
Generic Futures Data Quality Verification
==========================================

Verifies data quality for any futures symbol's 1-minute bars.
"""

import pandas as pd
from datetime import timedelta
import sys

def verify_futures_data(csv_file: str, symbol: str):
    """Verify futures data quality"""
    
    print("="*70)
    print(f"{symbol} Data Quality Verification")
    print("="*70)
    
    print(f"\nFile: {csv_file}\n")
    
    # Load data
    df = pd.read_csv(csv_file)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df = df.sort_values('timestamp')
    
    # Basic stats
    print(f"📊 Basic Stats:")
    print(f"  Total bars: {len(df):,}")
    print(f"  Date range: {df['timestamp'].min()} to {df['timestamp'].max()}")
    
    duration = (df['timestamp'].max() - df['timestamp'].min()).days
    print(f"  Duration: {duration} days")
    
    # Check for duplicates
    duplicates = df[df.duplicated(subset='timestamp', keep=False)]
    if len(duplicates) > 0:
        print(f"\n⚠️ Found {len(duplicates)} duplicate timestamps!")
        print(f"  First few duplicates:")
        print(duplicates.head()[['timestamp', 'close', 'volume']])
    else:
        print(f"\n✅ No duplicate timestamps")
    
    # Check for gaps
    print(f"\n🔍 Checking for gaps...")
    df['time_diff'] = df['timestamp'].diff()
    
    # Small gaps (1-10 min) - should be ZERO
    small_gaps = df[(df['time_diff'] > timedelta(minutes=1)) & 
                     (df['time_diff'] <= timedelta(minutes=10))]
    
    if len(small_gaps) > 0:
        print(f"⚠️ Small gaps (1-10 min): {len(small_gaps)}")
        print(f"  First few:")
        for idx, row in small_gaps.head(5).iterrows():
            minutes = row['time_diff'].total_seconds() / 60
            print(f"    Gap: {minutes:.0f} minutes - {row['timestamp']}")
    else:
        print(f"✅ No small gaps (1-10 min)")
    
    # Medium gaps (10min-1hour) - should be ZERO
    medium_gaps = df[(df['time_diff'] > timedelta(minutes=10)) & 
                      (df['time_diff'] <= timedelta(hours=1))]
    
    if len(medium_gaps) > 0:
        print(f"⚠️ Medium gaps (10min-1hour): {len(medium_gaps)}")
        print(f"  First few:")
        for idx, row in medium_gaps.head(5).iterrows():
            minutes = row['time_diff'].total_seconds() / 60
            print(f"    Gap: {minutes:.0f} minutes - {row['timestamp']}")
    else:
        print(f"✅ No medium gaps (10min-1hour)")
    
    # Large gaps (> 1 hour) - these are OK (maintenance + weekend)
    large_gaps = df[df['time_diff'] > timedelta(hours=1)]
    
    print(f"\n📅 Large gaps (> 1 hour, likely market closures): {len(large_gaps)}")
    if len(large_gaps) > 0:
        print(f"  First few (overnight/weekend gaps):")
        for idx, row in large_gaps.head(5).iterrows():
            hours = row['time_diff'].total_seconds() / 3600
            print(f"    Gap: {hours:.1f} hours - {row['timestamp'].strftime('%Y-%m-%d %H:%M:%S')} to {row['timestamp']}")
    
    # Price data quality
    print(f"\n📈 Price Data Quality:")
    print(f"  Price range: ${df['close'].min():.2f} - ${df['close'].max():.2f}")
    
    # Check for invalid bars (high < low)
    invalid_bars = df[df['high'] < df['low']]
    if len(invalid_bars) > 0:
        print(f"  ⚠️ Invalid bars (high < low): {len(invalid_bars)}")
    else:
        print(f"  ✅ No invalid bars (high < low)")
    
    # Volume stats
    zero_volume = df[df['volume'] == 0]
    if len(zero_volume) > 0:
        print(f"  ⚠️ Bars with zero volume: {len(zero_volume)}")
        print(f"    First occurrence: {zero_volume.iloc[0]['timestamp']}")
    else:
        print(f"  ✅ No zero volume bars")
    
    print(f"\n📊 Volume Statistics:")
    print(f"  Average: {df['volume'].mean():.0f}")
    print(f"  Median: {df['volume'].median():.0f}")
    print(f"  Min: {df['volume'].min():.0f}")
    print(f"  Max: {df['volume'].max():.0f}")
    
    # Trading hours coverage
    df['hour'] = df['timestamp'].dt.hour
    hours_with_data = df['hour'].nunique()
    print(f"\n⏰ Trading Hours Coverage:")
    print(f"  Hours with data: {hours_with_data}/24")
    
    # Day of week coverage
    df['day_name'] = df['timestamp'].dt.day_name()
    day_counts = df.groupby('day_name').size()
    
    print(f"\n📅 Days of Week Coverage:")
    for day in ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sun']:
        if day in day_counts.index:
            print(f"  {day}: {day_counts[day]:,} bars")
    
    print(f"\n{'='*70}")
    print(f"✅ Verification Complete")
    print(f"{'='*70}\n")
    
    if len(small_gaps) == 0 and len(medium_gaps) == 0:
        print(f"✅ Data looks good! No major issues found.")
    else:
        print(f"⚠️  Data has gaps that should be reviewed.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/verify_futures_data.py SYMBOL")
        print("Example: python scripts/verify_futures_data.py MES")
        sys.exit(1)
    
    symbol = sys.argv[1].upper()
    csv_file = f'data/historical_data/{symbol}_1min.csv'
    
    verify_futures_data(csv_file, symbol)
