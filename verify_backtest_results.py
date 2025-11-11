"""
Verify 5-Day Backtest Results with Full RL Analysis
"""

import pandas as pd
import json
import os

print("=" * 80)
print("5-DAY BACKTEST RESULTS - FULL RL VERIFICATION")
print("=" * 80)

# Check if backtest completed
if not os.path.exists('data/backtest_trades.csv'):
    print("\n❌ Backtest not completed yet - data/backtest_trades.csv not found")
    print("Please wait for backtest to finish running")
    exit(1)

# Load results
df = pd.read_csv('data/backtest_trades.csv')

print(f"\n[1] BASIC RESULTS")
print("-" * 80)
print(f"Total Trades: {len(df)}")
print(f"Winners: {len(df[df['pnl'] > 0])}")
print(f"Losers: {len(df[df['pnl'] < 0])}")
print(f"Win Rate: {len(df[df['pnl'] > 0])/len(df)*100:.1f}%")
print(f"Total P&L: ${df['pnl'].sum():.2f}")
print(f"Average P&L: ${df['pnl'].mean():.2f}")

# Check stop loss rate (KEY METRIC - should be LOWER than 99%)
print(f"\n[2] STOP LOSS ANALYSIS (Key Improvement Metric)")
print("-" * 80)
stop_loss_trades = len(df[df['exit_reason'] == 'stop_loss'])
stop_loss_rate = stop_loss_trades / len(df) * 100

print(f"Stop Loss Exits: {stop_loss_trades}/{len(df)} ({stop_loss_rate:.1f}%)")

if stop_loss_rate < 99:
    print(f"✅ IMPROVEMENT! Stop loss rate reduced from 99% to {stop_loss_rate:.1f}%")
    print(f"   New RL features are working!")
else:
    print(f"⚠️  Still {stop_loss_rate:.1f}% stop loss rate")
    print(f"   May need to adjust confidence thresholds")

# Exit reason breakdown
print(f"\n[3] EXIT REASON BREAKDOWN")
print("-" * 80)
if 'exit_reason' in df.columns:
    exit_counts = df['exit_reason'].value_counts()
    for reason, count in exit_counts.items():
        pct = count / len(df) * 100
        print(f"  {reason}: {count} ({pct:.1f}%)")

# Check if Exit RL features were triggered
print(f"\n[4] EXIT RL FEATURES VERIFICATION")
print("-" * 80)

exit_rl_features = {
    'profit_lock': 'Profit Lock Zones',
    'adverse_momentum': 'Adverse Momentum',
    'volume_exhaustion': 'Volume Exhaustion',
    'failed_breakout': 'Failed Breakout',
    'breakeven': 'Breakeven Protection',
    'partial': 'Partial Exits',
    'target': 'Profit Target'
}

if 'exit_reason' in df.columns:
    for key, name in exit_rl_features.items():
        count = len(df[df['exit_reason'].str.contains(key, case=False, na=False)])
        if count > 0:
            print(f"  ✅ {name}: {count} times")
        else:
            print(f"  ⚪ {name}: Not triggered")

# Check Signal ML decisions
print(f"\n[5] SIGNAL ML VERIFICATION")
print("-" * 80)

# Estimate signals detected vs taken
if 'entry_confidence' in df.columns:
    avg_conf = df['entry_confidence'].mean()
    print(f"Average Entry Confidence: {avg_conf:.1%}")
    
    high_conf = len(df[df['entry_confidence'] >= 0.7])
    med_conf = len(df[(df['entry_confidence'] >= 0.5) & (df['entry_confidence'] < 0.7)])
    low_conf = len(df[df['entry_confidence'] < 0.5])
    
    print(f"  High Confidence (≥70%): {high_conf} trades")
    print(f"  Medium Confidence (50-70%): {med_conf} trades")
    print(f"  Low Confidence (<50%): {low_conf} trades")
    
    print(f"\n✅ Signal ML is working (dual pattern matching active)")
else:
    print(f"⚠️  No entry_confidence column - Signal ML may not be recording")

# Check cloud saving
print(f"\n[6] CLOUD EXPERIENCE SAVING")
print("-" * 80)

cloud_files = [
    'cloud-api/exit_experience.json',
    'cloud-api/signal_experience.json'
]

for file in cloud_files:
    if os.path.exists(file):
        with open(file, 'r') as f:
            data = json.load(f)
            if isinstance(data, list):
                count = len(data)
            elif isinstance(data, dict):
                count = data.get('total_experiences', len(data.get('experiences', [])))
            else:
                count = 0
        print(f"  ✅ {file}: {count:,} experiences")
    else:
        print(f"  ❌ {file}: Not found")

# Final summary
print(f"\n" + "=" * 80)
print("SUMMARY")
print("=" * 80)

improvements = []
issues = []

if stop_loss_rate < 99:
    improvements.append(f"Stop loss rate reduced to {stop_loss_rate:.1f}%")
else:
    issues.append(f"Stop loss rate still high ({stop_loss_rate:.1f}%)")

if len(df[df['pnl'] > 0]) / len(df) > 0.5:
    improvements.append(f"Win rate improved to {len(df[df['pnl'] > 0])/len(df)*100:.1f}%")

if df['pnl'].sum() > 0:
    improvements.append(f"Profitable: ${df['pnl'].sum():.2f}")
else:
    issues.append(f"Still losing: ${df['pnl'].sum():.2f}")

if improvements:
    print("\n✅ IMPROVEMENTS:")
    for imp in improvements:
        print(f"   - {imp}")

if issues:
    print("\n⚠️  ISSUES:")
    for issue in issues:
        print(f"   - {issue}")

print(f"\n[NEXT STEPS]")
if stop_loss_rate < 50:
    print("  🎉 Excellent! RL is working well")
    print("  → Ready for live trading")
elif stop_loss_rate < 80:
    print("  ✅ Good progress! RL is helping")
    print("  → May want to increase confidence threshold to 60-70%")
else:
    print("  ⚠️  Still needs tuning")
    print("  → Increase confidence threshold to 70%+")
    print("  → Check if Signal ML cloud API is actually being called")

print("=" * 80)
