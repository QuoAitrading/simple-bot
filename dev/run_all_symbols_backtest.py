#!/usr/bin/env python3
"""
Run Full Backtest for All Symbols
==================================
Runs saturation backtest for all 4 symbols (ES, MES, MNQ, NQ) from first day to last day.

Features:
- First run uses 100% exploration rate to discover initial experiences
- Subsequent runs use 30% exploration rate
- Confidence threshold set to 40%
- Runs from first available day to last day in historical data
- Saves experiences in correct symbol-specific locations
- Ensures all 16 required fields are logged in JSON
"""

import os
import sys
import subprocess
import json
from datetime import datetime

# Add parent directory to path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'src'))

# All symbols to run backtest for
SYMBOLS = ['ES', 'MES', 'MNQ', 'NQ']

def check_experience_file_empty(symbol):
    """Check if the experience file for a symbol is empty or has very few experiences."""
    exp_file = os.path.join(PROJECT_ROOT, f"experiences/{symbol}/signal_experience.json")
    
    if not os.path.exists(exp_file):
        return True
    
    try:
        with open(exp_file, 'r') as f:
            data = json.load(f)
            experiences = data.get('experiences', [])
            # Consider it "empty" if less than 10 experiences
            return len(experiences) < 10
    except Exception as e:
        print(f"Error reading {exp_file}: {e}")
        return True

def run_saturation_backtest(symbol, exploration_rate, max_iterations=100):
    """
    Run saturation backtest for a single symbol.
    
    Args:
        symbol: Trading symbol (ES, MES, MNQ, NQ)
        exploration_rate: Exploration rate (0.0-1.0)
        max_iterations: Maximum number of iterations
    
    Returns:
        True if successful, False otherwise
    """
    print(f"\n{'='*70}")
    print(f"  Running Saturation Backtest for {symbol}")
    print(f"  Exploration Rate: {exploration_rate*100:.0f}%")
    print(f"  Max Iterations: {max_iterations}")
    print(f"{'='*70}\n")
    
    # Build command
    cmd = [
        sys.executable,
        os.path.join(SCRIPT_DIR, "run_saturation_backtest.py"),
        "--symbol", symbol,
        "--exploration", str(exploration_rate),
        "--max-iterations", str(max_iterations)
    ]
    
    # Run the backtest
    try:
        result = subprocess.run(cmd, check=True)
        return result.returncode == 0
    except subprocess.CalledProcessError as e:
        print(f"ERROR: Backtest failed for {symbol} with exit code {e.returncode}")
        return False

def main():
    """Main entry point - run backtest for all symbols."""
    print("="*70)
    print("  FULL BACKTEST FOR ALL SYMBOLS")
    print("="*70)
    print(f"  Symbols: {', '.join(SYMBOLS)}")
    print(f"  Strategy:")
    print(f"    - First run: 100% exploration (if < 10 experiences)")
    print(f"    - Subsequent runs: 30% exploration")
    print(f"    - Confidence threshold: 40%")
    print(f"    - Full date range: First day to last day in data")
    print("="*70)
    print()
    
    # Run backtest for each symbol
    results = {}
    
    for symbol in SYMBOLS:
        print(f"\n{'#'*70}")
        print(f"#  PROCESSING SYMBOL: {symbol}")
        print(f"{'#'*70}")
        
        # Check if this is the first run (no experiences or very few)
        is_first_run = check_experience_file_empty(symbol)
        
        if is_first_run:
            print(f"\n  This is the FIRST RUN for {symbol}")
            print(f"  Using 100% exploration rate to discover initial experiences")
            exploration_rate = 1.0  # 100% exploration for first run
            max_iterations = 50  # Limit first run iterations
        else:
            print(f"\n  This is a SUBSEQUENT RUN for {symbol}")
            print(f"  Using 30% exploration rate")
            exploration_rate = 0.30  # 30% exploration for subsequent runs
            max_iterations = 100  # Full iterations for subsequent runs
        
        # Run the saturation backtest
        success = run_saturation_backtest(symbol, exploration_rate, max_iterations)
        results[symbol] = success
        
        if success:
            print(f"\n✓ SUCCESS: {symbol} backtest completed")
        else:
            print(f"\n✗ FAILED: {symbol} backtest failed")
    
    # Print final summary
    print("\n" + "="*70)
    print("  FINAL SUMMARY")
    print("="*70)
    for symbol, success in results.items():
        status = "✓ SUCCESS" if success else "✗ FAILED"
        print(f"  {symbol}: {status}")
    print("="*70)
    
    # Exit with error if any failed
    all_success = all(results.values())
    sys.exit(0 if all_success else 1)

if __name__ == '__main__':
    main()
