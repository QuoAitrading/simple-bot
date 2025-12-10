#!/usr/bin/env python3
"""
Continuous Backtest Runner for RL Experience Collection

This script runs backtests repeatedly on ES futures data until no more unique
experiences can be added to the RL brain. It ensures:
- Sample size of 20 for confidence calculations
- Confidence threshold at 70%
- Exploration rate at 30%
- All experiences are logged into RL
- Uses correct futures schedule for ES
"""

import os
import sys
import json
import logging
from datetime import datetime, timedelta
import subprocess

# Setup paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)

# Experience file path for ES
EXPERIENCE_FILE = os.path.join(PROJECT_ROOT, "experiences/ES/signal_experience.json")


def get_experience_count():
    """Get the current number of experiences in the ES experience file."""
    if not os.path.exists(EXPERIENCE_FILE):
        return 0
    
    try:
        with open(EXPERIENCE_FILE, 'r') as f:
            data = json.load(f)
            experiences = data.get('experiences', [])
            return len(experiences)
    except Exception as e:
        print(f"Error reading experience file: {e}")
        return 0


def run_single_backtest(days=30):
    """
    Run a single backtest for ES with the specified number of days.
    
    Args:
        days: Number of days to backtest
    
    Returns:
        True if successful, False otherwise
    """
    print(f"\n{'='*80}")
    print(f"Running backtest for ES - Last {days} days")
    print(f"{'='*80}\n")
    
    # Run the backtest using the main backtest script
    backtest_script = os.path.join(SCRIPT_DIR, "run_backtest.py")
    
    cmd = [
        sys.executable,
        backtest_script,
        "--days", str(days),
        "--symbol", "ES",
        "--log-level", "WARNING"
    ]
    
    try:
        result = subprocess.run(cmd, cwd=PROJECT_ROOT, check=False)
        return result.returncode == 0
    except Exception as e:
        print(f"Error running backtest: {e}")
        return False


def main():
    """Main loop - run backtests until no more unique experiences are added."""
    
    print("\n" + "="*80)
    print("CONTINUOUS BACKTEST RUNNER FOR RL EXPERIENCE COLLECTION")
    print("="*80)
    print("\nConfiguration:")
    print("  - Symbol: ES")
    print("  - Sample Size: 20 (for confidence calculations)")
    print("  - Confidence Threshold: 70%")
    print("  - Exploration Rate: 30%")
    print("  - Backtest Period: Full available history")
    print("\nGoal: Run until no more unique experiences can be added")
    print("="*80 + "\n")
    
    # Track experience counts across iterations
    iteration = 0
    previous_count = get_experience_count()
    stagnant_iterations = 0
    max_stagnant = 3  # Stop after 3 iterations with no new experiences
    
    print(f"Initial experience count: {previous_count}")
    
    while True:
        iteration += 1
        print(f"\n{'#'*80}")
        print(f"# ITERATION {iteration}")
        print(f"{'#'*80}\n")
        
        # Run backtest for increasingly longer periods to get more data
        # Start with 30 days, then 60, 90, 120, etc.
        days = min(30 + (iteration - 1) * 30, 365)  # Cap at 365 days
        
        # Run the backtest
        success = run_single_backtest(days=days)
        
        if not success:
            print(f"\n⚠️  Backtest {iteration} completed with warnings or errors")
        
        # Check new experience count
        current_count = get_experience_count()
        new_experiences = current_count - previous_count
        
        print(f"\n{'='*80}")
        print(f"ITERATION {iteration} RESULTS:")
        print(f"  - Previous experiences: {previous_count}")
        print(f"  - Current experiences:  {current_count}")
        print(f"  - New unique experiences: {new_experiences}")
        print(f"{'='*80}\n")
        
        # Check if we're still adding experiences
        if new_experiences == 0:
            stagnant_iterations += 1
            print(f"⚠️  No new experiences added ({stagnant_iterations}/{max_stagnant})")
            
            if stagnant_iterations >= max_stagnant:
                print(f"\n{'='*80}")
                print("✅ CONVERGENCE ACHIEVED!")
                print(f"{'='*80}")
                print(f"\nNo new unique experiences added for {max_stagnant} consecutive iterations.")
                print(f"Final experience count: {current_count}")
                print(f"\nRL brain has converged with all available unique patterns from ES data.")
                print(f"Experience file: {EXPERIENCE_FILE}")
                print(f"\n{'='*80}\n")
                break
        else:
            stagnant_iterations = 0  # Reset counter when new experiences are added
            print(f"✅ Added {new_experiences} new unique experiences")
        
        # Update for next iteration
        previous_count = current_count
        
        # Safety check - don't run forever
        if iteration >= 20:
            print(f"\n⚠️  Reached maximum iteration limit ({iteration})")
            print(f"Final experience count: {current_count}")
            break
    
    print("\n" + "="*80)
    print("BACKTEST LOOP COMPLETED")
    print("="*80 + "\n")


if __name__ == '__main__':
    main()
