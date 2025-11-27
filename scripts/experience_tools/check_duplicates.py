#!/usr/bin/env python3
"""Check if experiences are truly unique or duplicates"""
import json
from collections import Counter

# Load experiences
with open('experiences/ES/signal_experience.json', 'r') as f:
    data = json.load(f)

experiences = data['experiences']

print(f"Total experiences in file: {len(experiences)}")

# Check for exact duplicates using all fields
exp_hashes = []
for exp in experiences:
    # Create a hash from timestamp, symbol, pnl, exit_reason
    exp_key = (exp['timestamp'], exp['symbol'], exp['pnl'], exp['exit_reason'])
    exp_hashes.append(exp_key)

# Count duplicates
counter = Counter(exp_hashes)
duplicates = {k: v for k, v in counter.items() if v > 1}

print(f"\nUnique experience keys: {len(counter)}")
print(f"Duplicate keys found: {len(duplicates)}")

if duplicates:
    print(f"\n⚠️ DUPLICATES DETECTED!")
    print(f"Showing first 10 duplicates:")
    for i, (key, count) in enumerate(list(duplicates.items())[:10]):
        timestamp, symbol, pnl, reason = key
        print(f"\n{i+1}. Appears {count} times:")
        print(f"   Timestamp: {timestamp}")
        print(f"   Symbol: {symbol}")
        print(f"   PnL: ${pnl:.2f}")
        print(f"   Exit Reason: {reason}")
else:
    print(f"\n✅ NO DUPLICATES! All {len(experiences)} experiences are unique!")

# Check date distribution
timestamps = [exp['timestamp'] for exp in experiences]
unique_dates = set(ts.split('T')[0] for ts in timestamps)
print(f"\nDate range coverage:")
print(f"  Unique dates: {len(unique_dates)}")
print(f"  First date: {min(unique_dates)}")
print(f"  Last date: {max(unique_dates)}")
print(f"  Avg experiences per date: {len(experiences) / len(unique_dates):.1f}")

# Show distribution by date
date_counts = Counter(ts.split('T')[0] for ts in timestamps)
print(f"\nTop 5 dates by experience count:")
for date, count in date_counts.most_common(5):
    print(f"  {date}: {count} experiences")
