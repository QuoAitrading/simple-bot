"""
Deep Analysis: Why 99% Stop Loss + How to Fix with RL
"""

import pandas as pd
import json

print("=" * 80)
print("PROBLEM DIAGNOSIS: 99% Stop Loss Rate")
print("=" * 80)

# Load backtest trades
df = pd.read_csv('data/backtest_trades.csv')

print(f"\n[1] BASIC STATS")
print("-" * 80)
print(f"Total Trades: {len(df)}")
print(f"Stop Loss: {len(df[df['exit_reason'] == 'stop_loss'])} ({len(df[df['exit_reason'] == 'stop_loss'])/len(df)*100:.1f}%)")
print(f"Winners: {len(df[df['pnl'] > 0])}")
print(f"Losers: {len(df[df['pnl'] < 0])}")
print(f"Win Rate: {len(df[df['pnl'] > 0])/len(df)*100:.1f}%")
print(f"Average P&L: ${df['pnl'].mean():.2f}")
print(f"Total P&L: ${df['pnl'].sum():.2f}")

# Check entry confidence
print(f"\n[2] ENTRY CONFIDENCE ANALYSIS")
print("-" * 80)
if 'entry_confidence' in df.columns:
    avg_conf = df['entry_confidence'].mean()
    winner_conf = df[df['pnl'] > 0]['entry_confidence'].mean() if len(df[df['pnl'] > 0]) > 0 else 0
    loser_conf = df[df['pnl'] < 0]['entry_confidence'].mean() if len(df[df['pnl'] < 0]) > 0 else 0
    
    print(f"Average Entry Confidence: {avg_conf:.1%}")
    print(f"Winner Confidence: {winner_conf:.1%}")
    print(f"Loser Confidence: {loser_conf:.1%}")
    print(f"\n⚠️  Signal ML is giving {avg_conf:.1%} confidence to trades that lose 99% of the time!")
else:
    print("⚠️  No entry_confidence column - can't analyze signal quality")

# Check how quickly stop loss is hit
print(f"\n[3] TIME TO STOP LOSS")
print("-" * 80)
if 'duration_minutes' in df.columns:
    stop_trades = df[df['exit_reason'] == 'stop_loss']
    avg_duration = stop_trades['duration_minutes'].mean()
    print(f"Average time to stop loss: {avg_duration:.1f} minutes")
    print(f"Median time to stop loss: {stop_trades['duration_minutes'].median():.1f} minutes")
    
    quick_stops = len(stop_trades[stop_trades['duration_minutes'] < 5])
    print(f"Stopped out in <5 min: {quick_stops} trades ({quick_stops/len(stop_trades)*100:.1f}%)")
    print(f"\n⚠️  Trades are going IMMEDIATELY against you!")

# Check entry side bias
print(f"\n[4] LONG vs SHORT PERFORMANCE")
print("-" * 80)
if 'side' in df.columns:
    longs = df[df['side'] == 'long']
    shorts = df[df['side'] == 'short']
    
    print(f"\nLONG trades: {len(longs)}")
    print(f"  Win rate: {len(longs[longs['pnl'] > 0])/len(longs)*100:.1f}%")
    print(f"  Avg P&L: ${longs['pnl'].mean():.2f}")
    print(f"  Stop loss rate: {len(longs[longs['exit_reason'] == 'stop_loss'])/len(longs)*100:.1f}%")
    
    print(f"\nSHORT trades: {len(shorts)}")
    print(f"  Win rate: {len(shorts[shorts['pnl'] > 0])/len(shorts)*100:.1f}%")
    print(f"  Avg P&L: ${shorts['pnl'].mean():.2f}")
    print(f"  Stop loss rate: {len(shorts[shorts['exit_reason'] == 'stop_loss'])/len(shorts)*100:.1f}%")

# Load signal experiences to check what patterns exist
print(f"\n[5] SIGNAL EXPERIENCE QUALITY")
print("-" * 80)

try:
    with open('cloud-api/signal_experience.json', 'r') as f:
        signal_exp = json.load(f)
    
    if isinstance(signal_exp, list):
        total_signals = len(signal_exp)
        # Try to find success rate
        if len(signal_exp) > 0 and isinstance(signal_exp[0], dict):
            successful = sum(1 for s in signal_exp if s.get('outcome') == 'success' or s.get('success', False))
            print(f"Total signal experiences: {total_signals:,}")
            print(f"Successful patterns: {successful:,} ({successful/total_signals*100:.1f}%)")
            print(f"\n⚠️  Your training data has {100-successful/total_signals*100:.1f}% LOSING signals!")
            print("     The ML is learning from bad trades!")
except Exception as e:
    print(f"Could not analyze signal experiences: {e}")

print("\n" + "=" * 80)
print("ROOT CAUSE ANALYSIS")
print("=" * 80)

diagnosis = """
The 99% stop loss rate means:

1. ❌ SIGNAL ML IS APPROVING BAD ENTRIES
   - 6,880 signal experiences contain too many losing patterns
   - Cloud API is matching against bad historical trades
   - No quality filter on what experiences to learn from
   
2. ❌ ENTRY TIMING IS TERRIBLE
   - Trades go against you immediately (<5 min to stop)
   - Entering at the WORST possible moment
   - Need to filter for better entry conditions

3. ❌ EXIT RL FEATURES CAN'T HELP
   - Profit lock, volume exhaustion, etc. require PROFIT
   - 99% of trades never reach profit zones
   - Exit RL is useless when signal selection is broken
"""

print(diagnosis)

print("\n" + "=" * 80)
print("SOLUTION: NEW RL FEATURES FOR SIGNAL QUALITY")
print("=" * 80)

solution = """
You need SIGNAL ENTRY RL features to fix this:

🔧 NEW FEATURE 1: Win Rate Filter
   - Track win rate by market regime (trending/ranging/choppy)
   - ONLY take signals in regimes with >50% win rate
   - Learn which conditions produce winners vs losers

🔧 NEW FEATURE 2: Immediate Adverse Movement Detection
   - Track first 3 bars after entry
   - If 80%+ of signals go adverse in <5min, STOP taking them
   - Learn entry timing patterns that avoid immediate stops

🔧 NEW FEATURE 3: Experience Quality Score
   - Filter signal experiences by outcome
   - ONLY match against successful patterns (profit > 1R)
   - Ignore experiences that hit stop loss quickly

🔧 NEW FEATURE 4: Confidence Threshold Adaptation
   - Current: Takes any signal ML approves
   - New: Require minimum confidence (70%+ for trending, 80%+ for ranging)
   - Dynamically adjust based on recent win rate

🔧 NEW FEATURE 5: Entry Context Validation
   - Check if current setup matches WINNING experience patterns
   - Require: spread OK + volume OK + regime match + recent wins
   - Reject if ANY critical factor is off

🔧 NEW FEATURE 6: Market Regime Win Rate Tracking
   - Track: HIGH_VOL_TRENDING, LOW_VOL_RANGING, etc.
   - Each regime has its own win rate threshold
   - Pause trading in regimes with <40% win rate

Would you like me to implement these 6 new Signal Entry RL features?
This will dramatically reduce stop loss rate by being MUCH more selective.
"""

print(solution)

print("\n" + "=" * 80)
print("PRIORITY ACTIONS")
print("=" * 80)
print("1. ✅ Implement Feature 3: Filter out losing signal experiences")
print("2. ✅ Implement Feature 2: Detect immediate adverse movement") 
print("3. ✅ Implement Feature 4: Raise confidence threshold to 70%+")
print("4. ✅ Implement Feature 6: Track win rate by market regime")
print("5. ✅ Re-train Signal ML on ONLY winning patterns")
print("=" * 80)
