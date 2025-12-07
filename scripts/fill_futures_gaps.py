"""
Generic Gap Filler for Futures Data
====================================

Fills missing 1-minute bars during trading hours with realistic volumes and prices.
Preserves only legitimate gaps:
- 1 hour daily maintenance (hour 21 UTC)
- Weekend gaps (Friday 22:00 - Sunday 23:00 UTC)
"""

import pandas as pd
from datetime import datetime, timedelta
import pytz
import numpy as np
import sys

def fill_futures_gaps(csv_file: str, symbol: str):
    """Fill missing 1-minute bars in futures data with realistic volumes and prices"""
    
    print("="*70)
    print(f"{symbol} Data Gap Filler")
    print("="*70)
    
    # Load data
    df = pd.read_csv(csv_file)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df = df.sort_values('timestamp').reset_index(drop=True)
    
    print(f"\nOriginal data: {len(df):,} bars")
    print(f"Date range: {df['timestamp'].min()} to {df['timestamp'].max()}")
    
    # Create complete 1-minute timeline
    start_time = df['timestamp'].min()
    end_time = df['timestamp'].max()
    
    print(f"\nGenerating complete 1-minute timeline...")
    
    # Generate all 1-minute timestamps
    all_minutes = []
    current = start_time
    
    while current <= end_time:
        all_minutes.append(current)
        current += timedelta(minutes=1)
    
    print(f"Total possible minutes: {len(all_minutes):,}")
    
    # Create DataFrame with all minutes
    df_complete = pd.DataFrame({'timestamp': all_minutes})
    
    # Merge with existing data
    df_merged = df_complete.merge(df, on='timestamp', how='left')
    
    # Identify missing bars
    missing_mask = df_merged['open'].isna()
    missing_count = missing_mask.sum()
    
    print(f"Missing bars to fill: {missing_count:,}")
    
    if missing_count == 0:
        print("\n✅ No missing bars - data is complete!")
        return df
    
    # Fill missing bars with realistic data
    print(f"\nFilling missing bars with realistic prices and volume...")
    
    # Forward fill prices first
    for col in ['open', 'high', 'low', 'close']:
        df_merged[col] = df_merged[col].ffill()
    
    # Calculate realistic volume based on nearby bars
    df_merged['hour_temp'] = df_merged['timestamp'].dt.hour
    hourly_median_volume = df[df['volume'] > 0].groupby(df['timestamp'].dt.hour)['volume'].median().to_dict()
    
    # Fill missing bars with median volume for that hour
    overall_median = df[df['volume'] > 0]['volume'].median()
    
    for idx in df_merged[missing_mask].index:
        hour = df_merged.loc[idx, 'hour_temp']
        df_merged.loc[idx, 'volume'] = hourly_median_volume.get(hour, overall_median)
    
    # Add small random variation to filled volumes (±20%) to make more realistic
    np.random.seed(42)  # For reproducibility
    filled_indices = df_merged[missing_mask].index
    variation = np.random.uniform(0.8, 1.2, size=len(filled_indices))
    df_merged.loc[filled_indices, 'volume'] = (df_merged.loc[filled_indices, 'volume'] * variation).astype(int)
    
    # For filled bars, add tiny realistic price variation
    # Determine tick size based on symbol
    if symbol in ['MES', 'ES']:
        tick_size = 0.25
    elif symbol in ['MNQ', 'NQ']:
        tick_size = 0.25
    elif symbol in ['MYM', 'YM']:
        tick_size = 1.0
    elif symbol in ['M2K', 'RTY']:
        tick_size = 0.10
    else:
        tick_size = 0.25  # Default
    
    for idx in filled_indices:
        base_price = df_merged.loc[idx, 'close']
        # Vary by ±0-2 ticks
        tick_variation = np.random.choice([-2*tick_size, -tick_size, 0, tick_size, 2*tick_size])
        
        # Slight price movement
        df_merged.loc[idx, 'close'] = base_price + tick_variation
        df_merged.loc[idx, 'open'] = base_price  # Open at previous close
        df_merged.loc[idx, 'high'] = max(base_price, base_price + tick_variation) + np.random.choice([0, tick_size])
        df_merged.loc[idx, 'low'] = min(base_price, base_price + tick_variation) - np.random.choice([0, tick_size])
    
    df_merged.drop('hour_temp', axis=1, inplace=True)
    
    print(f"  ✅ Filled with hourly median volumes + realistic price variation")
    
    # Now remove legitimate gaps (maintenance and weekends)
    print(f"\nRemoving legitimate gaps (maintenance + weekends)...")
    
    df_merged['hour'] = df_merged['timestamp'].dt.hour
    df_merged['day_of_week'] = df_merged['timestamp'].dt.dayofweek
    
    # Remove daily maintenance gap: hour 21 UTC
    maintenance_mask = (df_merged['hour'] == 21)
    
    # Remove weekend gap: Friday 22:00 to Sunday 22:59
    weekend_mask = (
        ((df_merged['day_of_week'] == 4) & (df_merged['hour'] >= 22)) |
        (df_merged['day_of_week'] == 5) |
        ((df_merged['day_of_week'] == 6) & (df_merged['hour'] < 23))
    )
    
    # Combine legitimate gap masks
    legitimate_gaps = maintenance_mask | weekend_mask
    
    print(f"  Maintenance gaps: {maintenance_mask.sum():,} bars")
    print(f"  Weekend gaps: {weekend_mask.sum():,} bars")
    print(f"  Total legitimate gaps: {legitimate_gaps.sum():,} bars")
    
    # Keep only non-gap bars
    df_final = df_merged[~legitimate_gaps].copy()
    
    # Drop helper columns
    df_final = df_final[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
    
    print(f"\nFinal dataset: {len(df_final):,} bars")
    print(f"Added {len(df_final) - len(df):,} bars")
    
    # Verify no small gaps remain
    df_final = df_final.sort_values('timestamp').reset_index(drop=True)
    df_final['time_diff'] = df_final['timestamp'].diff()
    
    small_gaps = df_final[(df_final['time_diff'] > timedelta(minutes=1)) & 
                           (df_final['time_diff'] < timedelta(hours=1))]
    
    if len(small_gaps) > 0:
        print(f"\n⚠️ WARNING: Still {len(small_gaps)} gaps between 1min-1hour:")
        for idx, row in small_gaps.head(10).iterrows():
            print(f"  {row['timestamp']} - gap: {row['time_diff']}")
    else:
        print(f"\n✅ No small gaps - only maintenance and weekend gaps remain!")
    
    # Check weekend gaps are correct (~50 hours)
    weekend_gaps_check = df_final[df_final['time_diff'] > timedelta(hours=24)]
    if len(weekend_gaps_check) > 0:
        print(f"\n📅 Weekend gaps ({len(weekend_gaps_check)}):")
        for idx, row in weekend_gaps_check.head(10).iterrows():
            hours = row['time_diff'].total_seconds() / 3600
            print(f"  {row['timestamp']} - gap: {hours:.1f} hours")
    
    # Save
    backup_file = csv_file.replace('.csv', '_before_fill.csv')
    df.to_csv(backup_file, index=False)
    print(f"\n💾 Backup saved: {backup_file}")
    
    df_final.to_csv(csv_file, index=False)
    print(f"✅ Saved filled data: {csv_file}")
    
    return df_final

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/fill_futures_gaps.py SYMBOL")
        print("Example: python scripts/fill_futures_gaps.py MES")
        sys.exit(1)
    
    symbol = sys.argv[1].upper()
    csv_file = f'data/historical_data/{symbol}_1min.csv'
    
    print(f"\nProcessing: {csv_file}\n")
    fill_futures_gaps(csv_file, symbol)
    
    print("\n" + "="*70)
    print("✅ Complete!")
    print("="*70)
    print(f"\nNext: Run verification:")
    print(f"  python scripts/verify_futures_data.py {symbol}")
