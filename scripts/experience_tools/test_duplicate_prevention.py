#!/usr/bin/env python3
"""Test if duplicate prevention is working correctly"""
import json
from collections import Counter

# Load experiences
with open('experiences/ES/signal_experience.json', 'r') as f:
    data = json.load(f)

experiences = data['experiences']
print(f"Total experiences: {len(experiences)}\n")

# Check duplicate keys
exp_keys = [(e['timestamp'], e['symbol'], e['pnl'], e['exit_reason']) for e in experiences]
counter = Counter(exp_keys)

duplicates = {k: v for k, v in counter.items() if v > 1}
print(f"Unique keys: {len(counter)}")
print(f"Duplicates: {len(duplicates)}")

if duplicates:
    print("\n⚠️ DUPLICATES IN FILE (should be 0):")
    for key, count in list(duplicates.items())[:5]:
        print(f"  {key[0]} | {key[1]} | ${key[2]:.2f} | {key[3]} - appears {count} times")
else:
    print("\n✅ No duplicates in file - prevention working correctly!")

# Check if we're blocking different PnL for same timestamp
timestamps = [e['timestamp'] for e in experiences]
timestamp_counter = Counter(timestamps)
same_time_diff_pnl = {ts: count for ts, count in timestamp_counter.items() if count > 1}

if same_time_diff_pnl:
    print(f"\n📊 Same timestamps with different outcomes: {len(same_time_diff_pnl)}")
    for ts in list(same_time_diff_pnl.keys())[:3]:
        same_time = [e for e in experiences if e['timestamp'] == ts]
        print(f"\n  Timestamp: {ts}")
        for e in same_time:
            print(f"    PnL: ${e['pnl']:.2f}, Exit: {e['exit_reason']}, RSI: {e.get('rsi', 'N/A')}")
    print("\n✅ Duplicate prevention allows different outcomes at same time!")
else:
    print("\n⚠️ No trades at same timestamp with different outcomes")
    print("   This is NORMAL - each timestamp only generates one trade in backtest")
