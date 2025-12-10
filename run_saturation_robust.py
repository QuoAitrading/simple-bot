#!/usr/bin/env python3
"""
Robust saturation script that handles timeouts and continues until saturation
"""
import subprocess
import json
import time
import sys

MAX_ITERATIONS = 10
CONSECUTIVE_ZERO_STOP = 2
TIMEOUT_SECONDS = 900  # 15 minutes per iteration

print("="*80)
print("ES BOS/FVG SATURATION - Robust Mode")
print("="*80)

iteration = 0
consecutive_zero = 0

while iteration < MAX_ITERATIONS:
    iteration += 1
    
    # Get count before
    with open('experiences/ES/signal_experience.json', 'r') as f:
        before = len(json.load(f).get('experiences', []))
    
    print(f"\n[{iteration}] Starting: {before:,} experiences", flush=True)
    
    try:
        # Run backtest with timeout
        result = subprocess.run(
            ["python3", "dev/run_backtest.py", "--symbol", "ES", "--days", "96"],
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SECONDS
        )
        print(f"[{iteration}] Backtest completed", flush=True)
    except subprocess.TimeoutExpired:
        print(f"[{iteration}] Backtest timed out after {TIMEOUT_SECONDS}s (but may have saved data)", flush=True)
    
    # Get count after
    with open('experiences/ES/signal_experience.json', 'r') as f:
        after = len(json.load(f).get('experiences', []))
    
    new = after - before
    print(f"[{iteration}] Result: {before:,} → {after:,} (+{new:,})", flush=True)
    
    if new == 0:
        consecutive_zero += 1
        print(f"[{iteration}] No new experiences ({consecutive_zero}/{CONSECUTIVE_ZERO_STOP})", flush=True)
        if consecutive_zero >= CONSECUTIVE_ZERO_STOP:
            print(f"\n{'='*80}")
            print(f"SATURATION REACHED after {iteration} iterations")
            print(f"Final: {after:,} experiences")
            print(f"{'='*80}")
            sys.exit(0)
    else:
        consecutive_zero = 0

print(f"\n{'='*80}")
print(f"MAX ITERATIONS REACHED")
print(f"Final: {after:,} experiences")
print(f"{'='*80}")
