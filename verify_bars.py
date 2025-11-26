import pandas as pd
from datetime import datetime, timedelta
import pytz

# Load CSV
df = pd.read_csv('data/historical_data/ES_1min.csv')
print(f'Total bars: {len(df):,}')
print(f'Date range: {df["timestamp"].iloc[0]} to {df["timestamp"].iloc[-1]}')
print()

# Parse timestamps as UTC
df['dt'] = pd.to_datetime(df['timestamp'])
df['dt_utc'] = df['dt'].dt.tz_localize('UTC')
eastern = pytz.timezone('US/Eastern')
df['dt_et'] = df['dt_utc'].dt.tz_convert(eastern)

# Check for gaps (should be exactly 1 minute apart)
df['time_diff'] = df['dt'].diff()
gaps = df[df['time_diff'] > timedelta(minutes=1)]

print('=== GAPS (> 1 minute) ===')
if len(gaps) > 0:
    print(f'Found {len(gaps)} gaps:')
    for idx, row in gaps.head(20).iterrows():
        prev_time = df.iloc[idx-1]['dt_et']
        curr_time = row['dt_et']
        gap_minutes = (row['dt'] - df.iloc[idx-1]['dt']).total_seconds() / 60
        print(f'{prev_time} -> {curr_time} (gap: {gap_minutes:.0f} min)')
else:
    print('No gaps found - all bars exactly 1 minute apart ✓')
print()

# Check maintenance hours (5:00 PM - 6:00 PM ET)
maintenance_bars = df[df['dt_et'].dt.hour.isin([17])]
print(f'=== MAINTENANCE HOURS (5:00-6:00 PM ET) ===')
print(f'Bars during 5:00 PM ET hour: {len(maintenance_bars)}')
if len(maintenance_bars) > 0:
    print('Sample bars during maintenance:')
    print(maintenance_bars[['timestamp', 'dt_et']].head(10).to_string(index=False))
else:
    print('No bars during maintenance hour ✓')
print()

# Check trading hours distribution
df['hour_et'] = df['dt_et'].dt.hour
print('=== HOURLY DISTRIBUTION (ET) ===')
hourly = df.groupby('hour_et').size().sort_index()
for hour, count in hourly.items():
    marker = ' ← MAINTENANCE' if hour == 17 else ''
    print(f'{hour:02d}:00 ET: {count:,} bars{marker}')
