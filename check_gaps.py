import pandas as pd
import numpy as np

print("📊 Analyzing ES_1min.csv for gaps...")

# Load data
df = pd.read_csv('data/historical_data/ES_1min.csv')
df['timestamp'] = pd.to_datetime(df['timestamp'])
df = df.sort_values('timestamp')

# Calculate time difference between consecutive bars
df['diff'] = df['timestamp'].diff()

# Define gap threshold (e.g., > 2 hours to catch missing sessions, ignoring 1h maintenance)
# Weekend gap is usually ~48 hours (Fri 5pm to Sun 6pm)
gap_threshold = pd.Timedelta(hours=2)

# Find gaps
gaps = df[df['diff'] > gap_threshold]

print(f"\n📅 Data Range: {df['timestamp'].min()} to {df['timestamp'].max()}")
print(f"Total Bars: {len(df):,}")

print("\n🔍 Unexpected Gaps (excluding weekends):")
print("-" * 60)

unexpected_gaps = 0

for idx, row in gaps.iterrows():
    prev_time = df.loc[idx-1, 'timestamp']
    curr_time = row['timestamp']
    duration = row['diff']
    hours = duration.total_seconds() / 3600
    
    # Standard weekend is ~49 hours (Fri 17:00 to Sun 18:00)
    # Allow some flexibility (40-60 hours)
    is_weekend_duration = 40 < hours < 60
    
    if not is_weekend_duration:
        unexpected_gaps += 1
        print(f"⚠️ GAP: {prev_time} -> {curr_time} (Duration: {duration})")
        
        # Check if it's a holiday (Labor Day was Sept 1, 2025)
        if prev_time.month == 9 and prev_time.day == 1:
             print("   ℹ️ Note: This overlaps with Labor Day (Sept 1)")

print("-" * 60)
if unexpected_gaps == 0:
    print("✅ No unexpected gaps found! Data is continuous (ignoring weekends).")
else:
    print(f"⚠️ Found {unexpected_gaps} unexpected gaps.")
