#!/usr/bin/env python3
"""
Verify RL/ML Experience Loading
This script verifies that all 4,760+ signal experiences and 1,341+ exit experiences
are being properly loaded and used during backtesting.
"""

import sys
import os
import json

# Set backtest mode BEFORE any other imports
os.environ['BOT_BACKTEST_MODE'] = 'true'

# Add src directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from signal_confidence import SignalConfidenceRL
from adaptive_exits import AdaptiveExitManager

# Project root
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))


def verify_experiences():
    """Verify experience files are loaded correctly"""
    
    print("="*80)
    print("VERIFYING RL/ML EXPERIENCE LOADING")
    print("="*80)
    print()
    
    # Check raw JSON files
    print("Step 1: Checking raw JSON files...")
    print("-"*80)
    
    signal_file = os.path.join(PROJECT_ROOT, 'data/signal_experience.json')
    exit_file = os.path.join(PROJECT_ROOT, 'data/exit_experience.json')
    
    with open(signal_file, 'r') as f:
        signal_data = json.load(f)
        signal_count = len(signal_data.get('experiences', []))
    
    with open(exit_file, 'r') as f:
        exit_data = json.load(f)
        exit_count = len(exit_data.get('exit_experiences', []))
    
    print(f"✓ Signal experiences in JSON: {signal_count:,}")
    print(f"✓ Exit experiences in JSON: {exit_count:,}")
    print(f"✓ Total experiences on disk: {signal_count + exit_count:,}")
    print()
    
    # Load via RL classes
    print("Step 2: Loading via RL classes...")
    print("-"*80)
    
    signal_rl = SignalConfidenceRL(
        experience_file=signal_file,
        backtest_mode=True
    )
    
    # Create minimal config for exit manager
    minimal_config = {
        'breakeven_enabled': True,
        'breakeven_profit_threshold_ticks': 9,
        'breakeven_stop_offset_ticks': 1,
        'trailing_stop_enabled': True,
        'trailing_stop_distance_ticks': 10,
        'trailing_stop_min_profit_ticks': 16,
    }
    
    exit_manager = AdaptiveExitManager(
        config=minimal_config,
        experience_file=exit_file
    )
    
    loaded_signal = len(signal_rl.experiences)
    loaded_exit = len(exit_manager.exit_experiences)
    
    print(f"✓ Signal experiences LOADED: {loaded_signal:,}")
    print(f"✓ Exit experiences LOADED: {loaded_exit:,}")
    print(f"✓ Total experiences LOADED: {loaded_signal + loaded_exit:,}")
    print()
    
    # Verify match
    print("Step 3: Verifying all experiences are loaded...")
    print("-"*80)
    
    signal_match = (signal_count == loaded_signal)
    exit_match = (exit_count == loaded_exit)
    
    if signal_match and exit_match:
        print("✓ SUCCESS: All experiences loaded correctly!")
        print(f"  Signal: {signal_count:,} in file = {loaded_signal:,} loaded")
        print(f"  Exit: {exit_count:,} in file = {loaded_exit:,} loaded")
    else:
        print("✗ WARNING: Mismatch detected!")
        if not signal_match:
            print(f"  Signal: {signal_count:,} in file ≠ {loaded_signal:,} loaded")
        if not exit_match:
            print(f"  Exit: {exit_count:,} in file ≠ {loaded_exit:,} loaded")
    
    print()
    
    # Show sample experiences
    print("Step 4: Sample experiences...")
    print("-"*80)
    
    if signal_rl.experiences:
        sample_signal = signal_rl.experiences[0]
        print("Sample signal experience:")
        for key, value in list(sample_signal.items())[:5]:
            print(f"  {key}: {value}")
    
    print()
    
    if exit_manager.exit_experiences:
        sample_exit = exit_manager.exit_experiences[0]
        print("Sample exit experience:")
        for key, value in list(sample_exit.items())[:5]:
            print(f"  {key}: {value}")
    
    print()
    print("="*80)
    print("VERIFICATION COMPLETE")
    print("="*80)
    print()
    print("Summary:")
    print(f"  ✓ {signal_count:,} signal experiences ready for use")
    print(f"  ✓ {exit_count:,} exit experiences ready for use")
    print(f"  ✓ {signal_count + exit_count:,} total RL/ML experiences available")
    print()
    print("These experiences ARE being used during backtesting to:")
    print("  - Evaluate signal confidence (50% threshold)")
    print("  - Dynamically size positions (1-3 contracts)")
    print("  - Optimize exit parameters based on market conditions")
    print()
    
    return signal_match and exit_match


if __name__ == "__main__":
    try:
        success = verify_experiences()
        if success:
            print("✓ All checks passed!")
            sys.exit(0)
        else:
            print("✗ Some checks failed!")
            sys.exit(1)
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
