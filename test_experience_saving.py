"""
Test that signal experiences are being saved correctly to the 6,880 pool
"""
import json

# Check before
with open('cloud-api/signal_experience.json', 'r') as f:
    data = json.load(f)
    before_count = len(data['experiences'])
    print(f"✅ BEFORE: {before_count:,} experiences in pool")
    print(f"   File has these keys: {list(data.keys())[:5]}...")

# Show sample experience
sample = data['experiences'][0]
print(f"\n📋 Sample experience format:")
print(f"   - timestamp: {sample.get('timestamp', 'N/A')}")
print(f"   - state keys: {list(sample.get('state', {}).keys())}")
print(f"   - reward: {sample.get('reward', 'N/A')}")
print(f"   - took_trade: {sample.get('action', {}).get('took_trade', 'N/A')}")

print(f"\n🎯 When backtest runs, it will:")
print(f"   1. Load these {before_count:,} experiences")
print(f"   2. Use them for dual pattern matching")
print(f"   3. APPEND new trades to this same array")
print(f"   4. Save back to same file (growing the pool)")
print(f"\n   Example: 6,880 + 27 new trades = 6,907 total")
print(f"\n✅ This way bot learns from ALL past data + new backtests!")
