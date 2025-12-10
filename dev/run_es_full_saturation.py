#!/usr/bin/env python3
"""
ES BOS/FVG Full Saturation Backtest Script
===========================================

Two-Phase Backtest Strategy:
1. Phase 1 (Initial Learning): 100% exploration, 0% confidence threshold
   - Take EVERY signal to build initial experience base
   - Run full backtest from start to finish
   
2. Phase 2 (Optimization): 70% confidence threshold, 30% exploration
   - Use learned patterns to filter signals
   - Continue running until saturation (no new unique patterns)
   - Verify RL and pattern matching are correct

This ensures:
- Clean ES signals format
- Correct BOS and FVG strategy implementation
- Proper RL experience saving (no duplicates based on pattern)
- Pattern matching with correct percentages
- Profitable AI strategy over time
"""

import argparse
import sys
import os
import logging
from datetime import datetime
import json
import pytz

# CRITICAL: Set backtest mode BEFORE any imports
os.environ['BOT_BACKTEST_MODE'] = 'true'
os.environ['USE_CLOUD_SIGNALS'] = 'false'

# Add parent directory to path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'src'))

from backtesting import BacktestConfig, BacktestEngine
from backtest_reporter import reset_reporter, get_reporter
from config import load_config
from signal_confidence import SignalConfidenceRL
from symbol_specs import get_symbol_spec


def run_phase_1_initial_learning():
    """
    Phase 1: Initial Learning Phase
    - 100% exploration (take every signal)
    - 0% confidence threshold
    - Build base experience set
    """
    print("=" * 80)
    print("  PHASE 1: INITIAL LEARNING (100% Exploration)")
    print("=" * 80)
    print("  Taking EVERY signal to build experience base...")
    print("  Exploration: 100% | Confidence Threshold: 0%")
    print("=" * 80)
    print()
    
    # Import bot module
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "quotrading_engine",
        os.path.join(PROJECT_ROOT, "src/quotrading_engine.py")
    )
    bot_module = importlib.util.module_from_spec(spec)
    sys.modules['quotrading_engine'] = bot_module
    sys.modules['capitulation_reversal_bot'] = bot_module
    spec.loader.exec_module(bot_module)
    
    # Setup for ES
    symbol = 'ES'
    symbol_spec = get_symbol_spec(symbol)
    
    # Update bot module config
    bot_module.CONFIG['instrument'] = symbol
    bot_module.CONFIG['tick_size'] = symbol_spec.tick_size
    bot_module.CONFIG['tick_value'] = symbol_spec.tick_value
    bot_module._bot_config.instrument = symbol
    bot_module._bot_config.tick_size = symbol_spec.tick_size
    bot_module._bot_config.tick_value = symbol_spec.tick_value
    bot_module.SYMBOL_SPEC = symbol_spec
    
    # Reset capitulation detector
    import capitulation_detector
    capitulation_detector._detector = None
    
    # Initialize RL brain with 100% exploration, 0% threshold
    signal_exp_file = os.path.join(PROJECT_ROOT, f"experiences/{symbol}/signal_experience.json")
    rl_brain = SignalConfidenceRL(
        experience_file=signal_exp_file,
        backtest_mode=True,
        confidence_threshold=0.0,  # Take every signal (0% threshold)
        exploration_rate=1.0,      # 100% exploration
        min_exploration=1.0,
        exploration_decay=1.0
    )
    
    bot_module.__dict__['rl_brain'] = rl_brain
    
    # Load bot config
    bot_config = load_config(backtest_mode=True)
    bot_config.instrument = symbol
    bot_config.account_size = 50000.0
    bot_config.max_contracts = 1
    bot_config.tick_size = symbol_spec.tick_size
    bot_config.tick_value = symbol_spec.tick_value
    bot_config_dict = bot_config.to_dict()
    
    # Get date range from ES data
    data_path = os.path.join(PROJECT_ROOT, "data/historical_data")
    csv_path = os.path.join(data_path, f"{symbol}_1min.csv")
    
    tz = pytz.timezone('US/Eastern')
    with open(csv_path, 'r') as f:
        lines = f.readlines()
        first_line = lines[1]
        first_timestamp = first_line.split(',')[0]
        if '+' in first_timestamp:
            first_timestamp = first_timestamp.split('+')[0]
        start_date = datetime.strptime(first_timestamp, '%Y-%m-%d %H:%M:%S')
        start_date = tz.localize(start_date.replace(hour=0, minute=0, second=0))
        
        last_line = lines[-1]
        last_timestamp = last_line.split(',')[0]
        if '+' in last_timestamp:
            last_timestamp = last_timestamp.split('+')[0]
        end_date = datetime.strptime(last_timestamp, '%Y-%m-%d %H:%M:%S')
        end_date = tz.localize(end_date.replace(hour=23, minute=59, second=59))
    
    print(f"  Date Range: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
    print(f"  Total Bars: {len(lines) - 1:,}")
    print()
    
    # Create backtest config
    backtest_config = BacktestConfig(
        start_date=start_date,
        end_date=end_date,
        initial_equity=50000.0,
        symbols=[symbol],
        data_path=data_path,
        use_tick_data=False
    )
    
    # Create backtest engine
    engine = BacktestEngine(backtest_config, bot_config_dict)
    
    # Setup bot functions
    initialize_state = bot_module.initialize_state
    inject_complete_bar = bot_module.inject_complete_bar
    check_daily_reset = bot_module.check_daily_reset
    check_vwap_reset = bot_module.check_vwap_reset
    state = bot_module.state
    
    initialize_state(symbol)
    
    class BotRLReferences:
        def __init__(self):
            self.signal_rl = rl_brain
    
    engine.set_bot_instance(BotRLReferences())
    
    eastern_tz = pytz.timezone("US/Eastern")
    prev_position_active = False
    last_exit_reason = 'bot_exit'
    
    def strategy_func(bars_1min, bars_15min):
        nonlocal prev_position_active, last_exit_reason
        
        for bar in bars_1min:
            timestamp = bar['timestamp']
            timestamp_eastern = timestamp.astimezone(eastern_tz)
            
            check_daily_reset(symbol, timestamp_eastern)
            check_vwap_reset(symbol, timestamp_eastern)
            inject_complete_bar(symbol, bar)
            
            if symbol in state and 'position' in state[symbol]:
                pos = state[symbol]['position']
                current_active = pos.get('active', False)
                
                if current_active or (not current_active and prev_position_active):
                    if 'last_exit_reason' in state[symbol]:
                        last_exit_reason = state[symbol]['last_exit_reason']
                
                prev_position_active = current_active
                
                if pos.get('active') and engine.current_position is None:
                    engine.current_position = {
                        'symbol': symbol,
                        'side': pos['side'],
                        'quantity': pos.get('quantity', 1),
                        'entry_price': pos['entry_price'],
                        'entry_time': pos.get('entry_time', timestamp),
                        'stop_price': pos.get('stop_price'),
                        'target_price': pos.get('target_price')
                    }
                elif not pos.get('active') and engine.current_position is not None:
                    exit_price = bar['close']
                    engine._close_position(timestamp, exit_price, last_exit_reason)
                    last_exit_reason = 'bot_exit'
    
    # Run backtest
    import io
    import contextlib
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        engine.run_with_strategy(strategy_func)
    
    # Save experiences
    rl_brain.save_experience()
    
    # Print results
    phase1_experiences = len(rl_brain.experiences)
    print()
    print("  " + "=" * 76)
    print(f"  ✓ PHASE 1 COMPLETE: {phase1_experiences} experiences collected")
    print("  " + "=" * 76)
    print()
    
    return phase1_experiences


def run_phase_2_saturation(initial_experiences):
    """
    Phase 2: Optimization & Saturation
    - 70% confidence threshold
    - 30% exploration
    - Run until saturated (no new patterns)
    """
    print("=" * 80)
    print("  PHASE 2: OPTIMIZATION & SATURATION (70% Confidence, 30% Exploration)")
    print("=" * 80)
    print("  Running backtests until no new patterns are discovered...")
    print("  Confidence Threshold: 70% | Exploration: 30%")
    print("=" * 80)
    print()
    
    iteration = 0
    consecutive_zero = 0
    max_iterations = 100
    max_consecutive_zero = 3
    
    while iteration < max_iterations:
        iteration += 1
        
        # Import bot module fresh for each iteration
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "quotrading_engine",
            os.path.join(PROJECT_ROOT, "src/quotrading_engine.py")
        )
        bot_module = importlib.util.module_from_spec(spec)
        sys.modules['quotrading_engine'] = bot_module
        sys.modules['capitulation_reversal_bot'] = bot_module
        spec.loader.exec_module(bot_module)
        
        # Setup for ES
        symbol = 'ES'
        symbol_spec = get_symbol_spec(symbol)
        
        bot_module.CONFIG['instrument'] = symbol
        bot_module.CONFIG['tick_size'] = symbol_spec.tick_size
        bot_module.CONFIG['tick_value'] = symbol_spec.tick_value
        bot_module._bot_config.instrument = symbol
        bot_module._bot_config.tick_size = symbol_spec.tick_size
        bot_module._bot_config.tick_value = symbol_spec.tick_value
        bot_module.SYMBOL_SPEC = symbol_spec
        
        import capitulation_detector
        capitulation_detector._detector = None
        
        # Initialize RL brain with 70% threshold, 30% exploration
        signal_exp_file = os.path.join(PROJECT_ROOT, f"experiences/{symbol}/signal_experience.json")
        rl_brain = SignalConfidenceRL(
            experience_file=signal_exp_file,
            backtest_mode=True,
            confidence_threshold=0.70,  # 70% confidence threshold
            exploration_rate=0.30,      # 30% exploration
            min_exploration=0.30,
            exploration_decay=1.0
        )
        
        bot_module.__dict__['rl_brain'] = rl_brain
        
        experiences_before = len(rl_brain.experiences)
        
        # Load bot config
        bot_config = load_config(backtest_mode=True)
        bot_config.instrument = symbol
        bot_config.account_size = 50000.0
        bot_config.max_contracts = 1
        bot_config.tick_size = symbol_spec.tick_size
        bot_config.tick_value = symbol_spec.tick_value
        bot_config_dict = bot_config.to_dict()
        
        # Get date range
        data_path = os.path.join(PROJECT_ROOT, "data/historical_data")
        csv_path = os.path.join(data_path, f"{symbol}_1min.csv")
        
        tz = pytz.timezone('US/Eastern')
        with open(csv_path, 'r') as f:
            lines = f.readlines()
            first_line = lines[1]
            first_timestamp = first_line.split(',')[0]
            if '+' in first_timestamp:
                first_timestamp = first_timestamp.split('+')[0]
            start_date = datetime.strptime(first_timestamp, '%Y-%m-%d %H:%M:%S')
            start_date = tz.localize(start_date.replace(hour=0, minute=0, second=0))
            
            last_line = lines[-1]
            last_timestamp = last_line.split(',')[0]
            if '+' in last_timestamp:
                last_timestamp = last_timestamp.split('+')[0]
            end_date = datetime.strptime(last_timestamp, '%Y-%m-%d %H:%M:%S')
            end_date = tz.localize(end_date.replace(hour=23, minute=59, second=59))
        
        # Create backtest config
        backtest_config = BacktestConfig(
            start_date=start_date,
            end_date=end_date,
            initial_equity=50000.0,
            symbols=[symbol],
            data_path=data_path,
            use_tick_data=False
        )
        
        engine = BacktestEngine(backtest_config, bot_config_dict)
        
        initialize_state = bot_module.initialize_state
        inject_complete_bar = bot_module.inject_complete_bar
        check_daily_reset = bot_module.check_daily_reset
        check_vwap_reset = bot_module.check_vwap_reset
        state = bot_module.state
        
        initialize_state(symbol)
        
        class BotRLReferences:
            def __init__(self):
                self.signal_rl = rl_brain
        
        engine.set_bot_instance(BotRLReferences())
        
        eastern_tz = pytz.timezone("US/Eastern")
        prev_position_active = False
        last_exit_reason = 'bot_exit'
        
        def strategy_func(bars_1min, bars_15min):
            nonlocal prev_position_active, last_exit_reason
            
            for bar in bars_1min:
                timestamp = bar['timestamp']
                timestamp_eastern = timestamp.astimezone(eastern_tz)
                
                check_daily_reset(symbol, timestamp_eastern)
                check_vwap_reset(symbol, timestamp_eastern)
                inject_complete_bar(symbol, bar)
                
                if symbol in state and 'position' in state[symbol]:
                    pos = state[symbol]['position']
                    current_active = pos.get('active', False)
                    
                    if current_active or (not current_active and prev_position_active):
                        if 'last_exit_reason' in state[symbol]:
                            last_exit_reason = state[symbol]['last_exit_reason']
                    
                    prev_position_active = current_active
                    
                    if pos.get('active') and engine.current_position is None:
                        engine.current_position = {
                            'symbol': symbol,
                            'side': pos['side'],
                            'quantity': pos.get('quantity', 1),
                            'entry_price': pos['entry_price'],
                            'entry_time': pos.get('entry_time', timestamp),
                            'stop_price': pos.get('stop_price'),
                            'target_price': pos.get('target_price')
                        }
                    elif not pos.get('active') and engine.current_position is not None:
                        exit_price = bar['close']
                        engine._close_position(timestamp, exit_price, last_exit_reason)
                        last_exit_reason = 'bot_exit'
        
        # Run backtest with suppressed output
        import io
        import contextlib
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            engine.run_with_strategy(strategy_func)
        
        # Save experiences
        rl_brain.save_experience()
        
        experiences_after = len(rl_brain.experiences)
        new_experiences = experiences_after - experiences_before
        
        # Print progress
        status = "✓" if new_experiences > 0 else "○"
        print(f"  {status} Iteration {iteration:3d}: {experiences_before:5d} → {experiences_after:5d} (+{new_experiences:3d} new)")
        
        # Check for saturation
        if new_experiences == 0:
            consecutive_zero += 1
            if consecutive_zero >= max_consecutive_zero:
                print()
                print(f"  ✓ SATURATION REACHED after {consecutive_zero} consecutive iterations with 0 new patterns")
                break
        else:
            consecutive_zero = 0
    
    # Print summary
    print()
    print("  " + "=" * 76)
    print("  PHASE 2 COMPLETE - SATURATION SUMMARY")
    print("  " + "=" * 76)
    
    # Load final experience count
    signal_exp_file = os.path.join(PROJECT_ROOT, f"experiences/ES/signal_experience.json")
    with open(signal_exp_file, 'r') as f:
        data = json.load(f)
        final_experiences = len(data.get('experiences', []))
    
    print(f"  Initial Experiences:  {initial_experiences}")
    print(f"  Final Experiences:    {final_experiences}")
    print(f"  New Patterns Learned: {final_experiences - initial_experiences}")
    print(f"  Total Iterations:     {iteration}")
    print("  " + "=" * 76)
    print()


def main():
    """Main entry point"""
    # Suppress all logging for clean output
    logging.basicConfig(level=logging.CRITICAL)
    for logger_name in ['quotrading_engine', 'backtesting', 'signal_confidence', 
                        'regime_detection', 'capitulation_detector', 'root', '__main__']:
        logging.getLogger(logger_name).setLevel(logging.CRITICAL)
    logging.getLogger().setLevel(logging.CRITICAL)
    
    print()
    print("╔" + "=" * 78 + "╗")
    print("║" + " " * 78 + "║")
    print("║" + "  ES BOS/FVG STRATEGY - FULL SATURATION BACKTEST".center(78) + "║")
    print("║" + " " * 78 + "║")
    print("╚" + "=" * 78 + "╝")
    print()
    
    # Phase 1: Initial learning
    phase1_experiences = run_phase_1_initial_learning()
    
    # Phase 2: Saturation
    run_phase_2_saturation(phase1_experiences)
    
    print()
    print("╔" + "=" * 78 + "╗")
    print("║" + " " * 78 + "║")
    print("║" + "  ✓ FULL SATURATION BACKTEST COMPLETE".center(78) + "║")
    print("║" + " " * 78 + "║")
    print("╚" + "=" * 78 + "╝")
    print()


if __name__ == '__main__':
    main()
