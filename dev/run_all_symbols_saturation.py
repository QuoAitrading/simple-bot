#!/usr/bin/env python3
"""
Run saturation backtests for all symbols (ES, MES, NQ, MNQ) with NEW regime configuration.
Ensures each symbol has its own RL experiences and runs until saturation (no new experiences).
"""

import subprocess
import sys
import os
from datetime import datetime

# Symbols to backtest
SYMBOLS = ['ES', 'MES', 'NQ', 'MNQ']

# Backtest parameters
EXPLORATION_RATE = 0.30  # 30% exploration
MAX_ITERATIONS = 100
MIN_NEW_EXPERIENCES = 0
CONSECUTIVE_ZERO = 3

def run_saturation_backtest(symbol):
    """Run saturation backtest for a single symbol."""
    print(f"\n{'='*80}")
    print(f"Starting saturation backtest for {symbol}")
    print(f"{'='*80}")
    
    cmd = [
        'python', 'dev/run_saturation_backtest.py',
        '--symbol', symbol,
        '--exploration', str(EXPLORATION_RATE),
        '--max-iterations', str(MAX_ITERATIONS),
        '--min-new-experiences', str(MIN_NEW_EXPERIENCES),
        '--consecutive-zero', str(CONSECUTIVE_ZERO)
    ]
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=False, text=True)
        print(f"\n✓ {symbol} saturation backtest completed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"\n✗ {symbol} saturation backtest failed with error code {e.returncode}")
        return False

def main():
    """Run saturation backtests for all symbols."""
    print("="*80)
    print("MULTI-SYMBOL SATURATION BACKTEST")
    print("="*80)
    print(f"Symbols: {', '.join(SYMBOLS)}")
    print(f"Exploration Rate: {EXPLORATION_RATE*100}%")
    print(f"Max Iterations: {MAX_ITERATIONS}")
    print(f"Stopping when {CONSECUTIVE_ZERO} consecutive iterations add 0 experiences")
    print("="*80)
    
    start_time = datetime.now()
    results = {}
    
    for symbol in SYMBOLS:
        success = run_saturation_backtest(symbol)
        results[symbol] = success
    
    end_time = datetime.now()
    duration = end_time - start_time
    
    # Summary
    print("\n" + "="*80)
    print("SATURATION BACKTEST SUMMARY")
    print("="*80)
    
    for symbol, success in results.items():
        status = "✓ SUCCESS" if success else "✗ FAILED"
        print(f"{symbol:6s}: {status}")
    
    print(f"\nTotal Duration: {duration}")
    print("="*80)
    
    # Check if all succeeded
    all_success = all(results.values())
    if all_success:
        print("\n✓ All symbols completed saturation successfully!")
        return 0
    else:
        print("\n✗ Some symbols failed - check logs above")
        return 1

if __name__ == '__main__':
    sys.exit(main())
