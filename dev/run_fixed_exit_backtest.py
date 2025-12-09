#!/usr/bin/env python3
"""
Fixed Exit Backtest - Tests bot performance with fixed stops and targets.

This backtest variation tests:
1. FIXED STOP LOSS: Flush Low/High ± 2 ticks (already standard behavior)
2. FIXED TAKE PROFIT: Exit at VWAP (no trailing stop)
3. ALL SIGNALS: Takes every signal (no confidence filter) vs 70% confidence

Compares bot performance with fixed exits vs current trailing stop approach.
"""

import argparse
import sys
import os
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from types import ModuleType
import pytz

# CRITICAL: Set backtest mode BEFORE any imports that load the bot module
os.environ['BOT_BACKTEST_MODE'] = 'true'
os.environ['USE_CLOUD_SIGNALS'] = 'false'
# CRITICAL: Disable trailing stop and use fixed VWAP target
os.environ['FIXED_EXIT_MODE'] = 'true'

# Add parent directory to path to import from src/
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'src'))

# Import backtesting framework from dev
from backtesting import BacktestConfig, BacktestEngine, ReportGenerator
from backtest_reporter import reset_reporter, get_reporter

# Import production bot modules
from config import load_config
from monitoring import setup_logging
from signal_confidence import SignalConfidenceRL


def parse_arguments():
    """Parse command-line arguments for backtest"""
    parser = argparse.ArgumentParser(
        description='Fixed Exit Backtest - Tests fixed stops and targets',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run backtest for ES with all available data
  python dev/run_fixed_exit_backtest.py --symbol ES
  
  # Run with specific date range
  python dev/run_fixed_exit_backtest.py --symbol ES --start 2024-01-01 --end 2024-12-31
  
  # Compare all signals vs 70% confidence
  python dev/run_fixed_exit_backtest.py --symbol ES --compare-confidence
        """
    )
    
    parser.add_argument(
        '--start',
        type=str,
        help='Backtest start date (YYYY-MM-DD)'
    )
    
    parser.add_argument(
        '--end',
        type=str,
        help='Backtest end date (YYYY-MM-DD)'
    )
    
    parser.add_argument(
        '--days',
        type=int,
        help='Backtest for last N days (alternative to --start/--end)'
    )
    
    parser.add_argument(
        '--symbol',
        type=str,
        default='ES',
        help='Trading symbol (default: ES)'
    )
    
    parser.add_argument(
        '--compare-confidence',
        action='store_true',
        help='Run two backtests: one with all signals, one with 70%% confidence filter'
    )
    
    parser.add_argument(
        '--data-path',
        type=str,
        default=None,
        help='Path to historical data directory'
    )
    
    parser.add_argument(
        '--log-level',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
        default='INFO',
        help='Logging level (default: INFO)'
    )
    
    return parser.parse_args()


def initialize_rl_brains_for_backtest(bot_config, confidence_threshold=0.0, exploration_rate=1.0) -> Tuple[Any, ModuleType]:
    """
    Initialize RL brain for backtest mode.
    
    Args:
        bot_config: Bot configuration object
        confidence_threshold: Minimum confidence to take signal (0.0 = take all)
        exploration_rate: Exploration rate (1.0 = take all, 0.3 = 30% exploration)
    
    Returns:
        Tuple of (rl_brain, bot_module)
    """
    logger = logging.getLogger('backtest')
    
    # Import the bot module
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "quotrading_engine",
        os.path.join(PROJECT_ROOT, "src/quotrading_engine.py")
    )
    bot_module = importlib.util.module_from_spec(spec)
    sys.modules['quotrading_engine'] = bot_module
    sys.modules['capitulation_reversal_bot'] = bot_module
    
    # Load the module
    spec.loader.exec_module(bot_module)
    
    # Get symbol for symbol-specific experience folder
    symbol = bot_config.instrument
    
    # Update CONFIG with symbol-specific tick size/value
    from symbol_specs import get_symbol_spec
    symbol_spec = get_symbol_spec(symbol)
    
    bot_module.CONFIG['instrument'] = symbol
    bot_module.CONFIG['tick_size'] = symbol_spec.tick_size
    bot_module.CONFIG['tick_value'] = symbol_spec.tick_value
    bot_module._bot_config.instrument = symbol
    bot_module._bot_config.tick_size = symbol_spec.tick_size
    bot_module._bot_config.tick_value = symbol_spec.tick_value
    bot_module.SYMBOL_SPEC = symbol_spec
    
    # Reset capitulation detector for new symbol
    import capitulation_detector
    capitulation_detector._detector = None
    
    # Initialize RL brain with specified confidence threshold
    signal_exp_file = os.path.join(PROJECT_ROOT, f"experiences/{symbol}/signal_experience.json")
    rl_brain = SignalConfidenceRL(
        experience_file=signal_exp_file,
        backtest_mode=True,
        confidence_threshold=confidence_threshold,
        exploration_rate=exploration_rate,
        min_exploration=exploration_rate,
        exploration_decay=1.0  # No decay
    )
    
    # Set the global rl_brain in the bot module
    bot_module.__dict__['rl_brain'] = rl_brain
    
    return rl_brain, bot_module


def run_single_backtest(args: argparse.Namespace, confidence_threshold: float, exploration_rate: float, label: str) -> Dict[str, Any]:
    """
    Run a single backtest with specified confidence settings.
    
    Args:
        args: Command-line arguments
        confidence_threshold: Minimum confidence to take signal
        exploration_rate: Exploration rate
        label: Label for this backtest run
    
    Returns:
        Dictionary with backtest results
    """
    logger = logging.getLogger('backtest')
    
    # Get reporter for this run
    reporter = get_reporter()
    
    # Load configuration
    bot_config = load_config(backtest_mode=True)
    bot_config.account_size = 50000.0
    bot_config.max_contracts = 1
    bot_config.daily_loss_limit = 1000.0
    bot_config.shadow_mode = False
    
    if args.symbol:
        bot_config.instrument = args.symbol
    
    symbol = bot_config.instrument
    
    # Update tick size/value for symbol
    from symbol_specs import get_symbol_spec
    symbol_spec = get_symbol_spec(symbol)
    bot_config.tick_size = symbol_spec.tick_size
    bot_config.tick_value = symbol_spec.tick_value
    
    bot_config_dict = bot_config.to_dict()
    
    # Determine date range
    tz = pytz.timezone(bot_config.timezone)
    
    if args.start and args.end:
        start_date = datetime.strptime(args.start, '%Y-%m-%d')
        end_date = datetime.strptime(args.end, '%Y-%m-%d')
    elif args.days:
        data_path = args.data_path if args.data_path else os.path.join(PROJECT_ROOT, "data/historical_data")
        csv_path = os.path.join(data_path, f"{symbol}_1min.csv")
        
        if os.path.exists(csv_path):
            with open(csv_path, 'r') as f:
                lines = f.readlines()
                if len(lines) > 1:
                    last_line = lines[-1]
                    last_timestamp = last_line.split(',')[0]
                    if '+' in last_timestamp:
                        last_timestamp = last_timestamp.split('+')[0]
                    end_date = datetime.strptime(last_timestamp, '%Y-%m-%d %H:%M:%S')
                    end_date = tz.localize(end_date.replace(hour=23, minute=59, second=59))
                else:
                    end_date = datetime.now(tz)
        else:
            end_date = datetime.now(tz)
        
        start_date = end_date - timedelta(days=args.days)
    else:
        # Use all available data
        data_path = args.data_path if args.data_path else os.path.join(PROJECT_ROOT, "data/historical_data")
        csv_path = os.path.join(data_path, f"{symbol}_1min.csv")
        
        if os.path.exists(csv_path):
            with open(csv_path, 'r') as f:
                lines = f.readlines()
                if len(lines) > 1:
                    # Get first date
                    first_line = lines[1]  # Skip header
                    first_timestamp = first_line.split(',')[0]
                    if '+' in first_timestamp:
                        first_timestamp = first_timestamp.split('+')[0]
                    start_date = datetime.strptime(first_timestamp, '%Y-%m-%d %H:%M:%S')
                    start_date = tz.localize(start_date.replace(hour=0, minute=0, second=0))
                    
                    # Get last date
                    last_line = lines[-1]
                    last_timestamp = last_line.split(',')[0]
                    if '+' in last_timestamp:
                        last_timestamp = last_timestamp.split('+')[0]
                    end_date = datetime.strptime(last_timestamp, '%Y-%m-%d %H:%M:%S')
                    end_date = tz.localize(end_date.replace(hour=23, minute=59, second=59))
                else:
                    end_date = datetime.now(tz)
                    start_date = end_date - timedelta(days=7)
        else:
            end_date = datetime.now(tz)
            start_date = end_date - timedelta(days=7)
    
    # Print header
    print("\n" + "="*80)
    print(f"FIXED EXIT BACKTEST - {label}")
    print("="*80)
    print(f"Symbol: {symbol}")
    print(f"Date Range: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
    print(f"Confidence Threshold: {confidence_threshold:.0%}")
    print(f"Exploration Rate: {exploration_rate:.0%}")
    print(f"")
    print(f"Exit Strategy:")
    print(f"  - Stop Loss: Flush Low/High ± 2 ticks (fixed)")
    print(f"  - Take Profit: VWAP (fixed, no trailing)")
    print("="*80)
    print()
    
    reporter.print_header(
        start_date=start_date.strftime('%Y-%m-%d'),
        end_date=end_date.strftime('%Y-%m-%d'),
        symbol=symbol,
        config=bot_config_dict
    )
    
    # Create backtest configuration
    data_path = args.data_path if args.data_path else os.path.join(PROJECT_ROOT, "data/historical_data")
    
    backtest_config = BacktestConfig(
        start_date=start_date,
        end_date=end_date,
        initial_equity=bot_config.account_size,
        symbols=[symbol],
        data_path=data_path,
        use_tick_data=False
    )
    
    # Suppress verbose logging
    logger.setLevel(logging.CRITICAL)
    
    # Create backtest engine
    engine = BacktestEngine(backtest_config, bot_config_dict)
    
    if hasattr(engine, 'logger'):
        engine.logger.setLevel(logging.CRITICAL)
    
    # Initialize RL brain and bot module
    rl_brain, bot_module = initialize_rl_brains_for_backtest(bot_config, confidence_threshold, exploration_rate)
    
    initial_experience_count = len(rl_brain.experiences) if rl_brain else 0
    
    # Import bot functions
    initialize_state = bot_module.initialize_state
    inject_complete_bar = bot_module.inject_complete_bar
    check_for_signals = bot_module.check_for_signals
    check_exit_conditions = bot_module.check_exit_conditions
    check_daily_reset = bot_module.check_daily_reset
    check_vwap_reset = bot_module.check_vwap_reset
    state = bot_module.state
    
    # Initialize bot state
    initialize_state(symbol)
    
    # Create bot instance for RL tracking
    class BotRLReferences:
        def __init__(self):
            self.signal_rl = rl_brain
    
    bot_ref = BotRLReferences()
    engine.set_bot_instance(bot_ref)
    
    eastern_tz = pytz.timezone("US/Eastern")
    
    # Track state for backtest
    prev_position_active = False
    bars_processed = 0
    total_bars = 0
    trade_confidences = {}
    last_exit_reason = 'bot_exit'
    
    def fixed_exit_strategy_backtest(bars_1min: List[Dict[str, Any]], bars_15min: List[Dict[str, Any]]) -> None:
        """Fixed exit strategy integrated with backtest engine."""
        nonlocal prev_position_active, bars_processed, total_bars, last_exit_reason
        total_bars = len(bars_1min)
        
        for bar_idx, bar in enumerate(bars_1min):
            bars_processed = bar_idx + 1
            
            # Update progress
            progress_interval = max(500, total_bars // 10)
            if bars_processed % progress_interval == 0 or bars_processed == total_bars:
                reporter.update_progress(bars_processed, total_bars)
            
            timestamp = bar['timestamp']
            timestamp_eastern = timestamp.astimezone(eastern_tz)
            
            # Daily reset
            check_daily_reset(symbol, timestamp_eastern)
            check_vwap_reset(symbol, timestamp_eastern)
            
            # Inject bar data
            inject_complete_bar(symbol, bar)
            
            # Track position state
            if symbol in state and 'position' in state[symbol]:
                pos = state[symbol]['position']
                current_active = pos.get('active', False)
                
                if current_active or (not current_active and prev_position_active):
                    if 'last_exit_reason' in state[symbol]:
                        last_exit_reason = state[symbol]['last_exit_reason']
                
                if current_active and not prev_position_active:
                    entry_time = pos.get('entry_time', timestamp)
                    entry_time_key = str(entry_time)
                    confidence = state[symbol].get('entry_rl_confidence', 0.5)
                    if confidence <= 1.0:
                        confidence = confidence * 100
                    trade_confidences[entry_time_key] = confidence
                    
                    regime = state[symbol].get('current_regime', 'UNKNOWN')
                    trade_confidences[f"{entry_time_key}_regime"] = regime
                
                prev_position_active = current_active
                
                # Update backtest engine with current position
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
                    exit_time = timestamp
                    engine._close_position(exit_time, exit_price, last_exit_reason)
                    last_exit_reason = 'bot_exit'
        
        print()  # New line after progress
    
    # Run backtest
    results = engine.run_with_strategy(fixed_exit_strategy_backtest)
    
    # Get trades and add to reporter
    if hasattr(engine, 'metrics') and hasattr(engine.metrics, 'trades'):
        for trade in engine.metrics.trades:
            entry_time_key = str(trade.entry_time)
            confidence = trade_confidences.get(entry_time_key, 50)
            regime = trade_confidences.get(f"{entry_time_key}_regime", "")
            
            trade_dict = {
                'side': trade.side,
                'quantity': trade.quantity,
                'entry_price': trade.entry_price,
                'exit_price': trade.exit_price,
                'entry_time': trade.entry_time,
                'exit_time': trade.exit_time,
                'pnl': trade.pnl,
                'exit_reason': trade.exit_reason,
                'duration_minutes': trade.duration_minutes,
                'confidence': confidence,
                'regime': regime
            }
            reporter.record_trade(trade_dict)
    
    if results:
        reporter.total_bars = total_bars
    
    # Print summary
    reporter.print_summary()
    
    # Save RL experiences
    print("Saving RL experiences...")
    experience_path = f"experiences/{symbol}/signal_experience.json"
    if rl_brain is not None and hasattr(rl_brain, 'save_experience'):
        rl_brain.save_experience()
        final_experience_count = len(rl_brain.experiences)
        new_experiences = final_experience_count - initial_experience_count
        print(f"[OK] Signal RL experiences saved to {experience_path}")
        print(f"   Total experiences: {final_experience_count}")
        print(f"   New experiences this backtest: {new_experiences}")
    
    return results


def main():
    """Main entry point for fixed exit backtesting"""
    args = parse_arguments()
    
    # Setup logging
    bot_config = load_config(backtest_mode=True)
    config_dict = {'log_directory': os.path.join(PROJECT_ROOT, 'logs')}
    logger = setup_logging(config_dict)
    
    # Suppress verbose logging
    import warnings
    warnings.filterwarnings('ignore')
    
    logging.getLogger('root').setLevel(logging.CRITICAL)
    logging.getLogger('backtesting').setLevel(logging.CRITICAL)
    logging.getLogger('urllib3').setLevel(logging.CRITICAL)
    logging.getLogger('asyncio').setLevel(logging.CRITICAL)
    logging.getLogger('quotrading_engine').setLevel(logging.INFO)
    logging.getLogger('regime_detection').setLevel(logging.WARNING)
    logging.getLogger('signal_confidence').setLevel(logging.WARNING)
    
    # Message filter for clean output
    class BacktestMessageFilter(logging.Filter):
        def filter(self, record):
            reporter = get_reporter()
            msg = record.getMessage()
            if 'SIGNAL APPROVED' in msg:
                reporter.record_signal(approved=True)
                return False
            elif 'Signal Declined' in msg:
                reporter.record_signal(approved=False)
                return False
            elif 'Exploring' in msg:
                return False
            elif 'LONG SIGNAL' in msg or 'SHORT SIGNAL' in msg:
                return False
            return record.levelno >= logging.WARNING
    
    qte_logger = logging.getLogger('quotrading_engine')
    qte_logger.addFilter(BacktestMessageFilter())
    
    if args.compare_confidence:
        # Run two backtests and compare
        print("\n" + "="*80)
        print("RUNNING COMPARISON: ALL SIGNALS vs 70% CONFIDENCE")
        print("="*80)
        
        # First run: All signals (0% confidence threshold, 100% exploration)
        print("\n\nRUN 1: Taking ALL signals (no confidence filter)")
        print("-"*80)
        reporter1 = reset_reporter(starting_balance=50000.0, max_contracts=1)
        results1 = run_single_backtest(args, confidence_threshold=0.0, exploration_rate=1.0, label="ALL SIGNALS")
        
        # Second run: 70% confidence threshold (30% exploration as before)
        print("\n\nRUN 2: Taking signals with 70% confidence threshold")
        print("-"*80)
        reporter2 = reset_reporter(starting_balance=50000.0, max_contracts=1)
        results2 = run_single_backtest(args, confidence_threshold=0.70, exploration_rate=0.30, label="70% CONFIDENCE")
        
        # Print comparison
        print("\n\n" + "="*80)
        print("COMPARISON RESULTS")
        print("="*80)
        print(f"\n{'Metric':<30} {'ALL SIGNALS':<20} {'70% CONFIDENCE':<20} {'DIFFERENCE':<20}")
        print("-"*90)
        
        metrics = [
            ('Total Trades', 'total_trades', ''),
            ('Total PnL', 'total_pnl', '$'),
            ('Win Rate', 'win_rate', '%'),
            ('Average Win', 'average_win', '$'),
            ('Average Loss', 'average_loss', '$'),
            ('Profit Factor', 'profit_factor', ''),
            ('Max Drawdown', 'max_drawdown_dollars', '$'),
            ('Final Equity', 'final_equity', '$'),
            ('Total Return', 'total_return', '%'),
        ]
        
        for label, key, prefix in metrics:
            val1 = results1.get(key, 0) if results1 else 0
            val2 = results2.get(key, 0) if results2 else 0
            
            if prefix == '$':
                diff = val1 - val2
                print(f"{label:<30} {prefix}{val1:>18,.2f} {prefix}{val2:>18,.2f} {prefix}{diff:>18,.2f}")
            elif prefix == '%':
                diff = val1 - val2
                print(f"{label:<30} {val1:>18.2f}{prefix} {val2:>18.2f}{prefix} {diff:>18.2f}{prefix}")
            else:
                diff = val1 - val2
                print(f"{label:<30} {val1:>19.2f} {val2:>19.2f} {diff:>19.2f}")
        
        print("="*80)
        
        sys.exit(0)
    else:
        # Single run with all signals
        reporter = reset_reporter(starting_balance=50000.0, max_contracts=1)
        results = run_single_backtest(args, confidence_threshold=0.0, exploration_rate=1.0, label="ALL SIGNALS - FIXED EXITS")
        
        if results and results.get('total_trades', 0) > 0:
            sys.exit(0)
        else:
            sys.exit(1)


if __name__ == '__main__':
    main()
