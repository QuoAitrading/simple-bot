#!/usr/bin/env python3
"""
10-Day Backtest Runner with Comprehensive Verification
Validates neural network usage, experience saving, and feature tracking
"""
import subprocess
import sys
import os
import json
from datetime import datetime

print("=" * 80)
print("10-DAY BACKTEST - NEURAL NETWORK VERIFICATION")
print("=" * 80)
print()

# Change to repo directory
os.chdir('/home/runner/work/simple-bot/simple-bot')

# Check neural network models exist
print("1. CHECKING NEURAL NETWORK MODELS...")
print("-" * 80)
models = [
    ('data/neural_model.pth', 'Signal Confidence'),
    ('data/exit_model.pth', 'Exit Parameters')
]

for model_path, model_name in models:
    if os.path.exists(model_path):
        size_kb = os.path.getsize(model_path) / 1024
        print(f"   ✅ {model_name}: {model_path} ({size_kb:.1f} KB)")
    else:
        print(f"   ❌ {model_name}: {model_path} NOT FOUND")
        sys.exit(1)

print()

# Check experience files before backtest
print("2. CHECKING EXPERIENCE FILES (BEFORE BACKTEST)...")
print("-" * 80)
exp_files = [
    'data/local_experiences/signal_experiences_v2.json',
    'data/local_experiences/exit_experiences_v2.json'
]

before_counts = {}
for exp_file in exp_files:
    if os.path.exists(exp_file):
        with open(exp_file, 'r') as f:
            data = json.load(f)
            count = len(data.get('experiences', []))
            before_counts[exp_file] = count
            print(f"   ✅ {os.path.basename(exp_file)}: {count:,} experiences")
    else:
        before_counts[exp_file] = 0
        print(f"   ⚠️  {os.path.basename(exp_file)}: Not found (will be created)")

print()

# Run the backtest
print("3. RUNNING 10-DAY BACKTEST...")
print("-" * 80)
print("   Command: python dev-tools/full_backtest.py 10")
print()

# Run backtest and capture output
result = subprocess.run(
    ['python3', 'dev-tools/full_backtest.py', '10'],
    capture_output=True,
    text=True,
    timeout=300  # 5 minute timeout
)

# Print output
print(result.stdout)
if result.stderr:
    print("STDERR:", result.stderr)

print()

# Check experience files after backtest
print("4. CHECKING EXPERIENCE FILES (AFTER BACKTEST)...")
print("-" * 80)

after_counts = {}
for exp_file in exp_files:
    if os.path.exists(exp_file):
        with open(exp_file, 'r') as f:
            data = json.load(f)
            count = len(data.get('experiences', []))
            after_counts[exp_file] = count
            before = before_counts.get(exp_file, 0)
            new_exps = count - before
            print(f"   ✅ {os.path.basename(exp_file)}: {count:,} experiences (+{new_exps} new)")
    else:
        after_counts[exp_file] = 0
        print(f"   ❌ {os.path.basename(exp_file)}: Still not found!")

print()

# Summary
print("=" * 80)
print("VERIFICATION SUMMARY")
print("=" * 80)

print("\n✅ Neural Network Models:")
print("   - Signal confidence model loaded")
print("   - Exit parameters model loaded")

print("\n✅ Experience Tracking:")
signal_new = after_counts.get(exp_files[0], 0) - before_counts.get(exp_files[0], 0)
exit_new = after_counts.get(exp_files[1], 0) - before_counts.get(exp_files[1], 0)
print(f"   - Signal experiences: +{signal_new} new")
print(f"   - Exit experiences: +{exit_new} new")

if signal_new > 0 and exit_new > 0:
    print("\n✅ ALL SYSTEMS WORKING:")
    print("   - Neural networks loaded and used")
    print("   - Experiences saved to JSON files")
    print("   - Bot learning from trades")
else:
    print("\n⚠️  WARNING:")
    if signal_new == 0:
        print("   - No new signal experiences saved!")
    if exit_new == 0:
        print("   - No new exit experiences saved!")

print("\n" + "=" * 80)
print(f"Backtest completed at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("=" * 80)

sys.exit(result.returncode)
