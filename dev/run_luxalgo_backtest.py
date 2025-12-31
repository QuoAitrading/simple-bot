#!/usr/bin/env python3
"""
LuxAlgo SMC + Rejection Strategy Backtest Runner

This script runs backtests for the LuxAlgo SMC + Rejection strategy using
the EXISTING backtest framework with realistic futures hours.

Uses the main backtesting engine from dev/backtesting.py with proper:
- Realistic futures trading hours
- 96 days of real ES 1-minute data
- Proper order simulation and slippage
- No fake data or experience pollution
"""

import argparse
import sys
import os
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import pytz

# CRITICAL: Set backtest mode BEFORE any imports
os.environ['BOT_BACKTEST_MODE'] = 'true'
os.environ['USE_CLOUD_SIGNALS'] = 'false'

# Add parent directory to path to import from src/
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'src'))

# Import backtesting framework (the REAL one)
from backtesting import BacktestConfig, BacktestEngine, PerformanceMetrics, Trade

# Import strategy
from luxalgo_smc_strategy import LuxAlgoSMCStrategy


def run_luxalgo_strategy_backtest(bars_1min: List[Dict[str, Any]], bars_15min: List[Dict[str, Any]], 
                                    strategy: LuxAlgoSMCStrategy, engine: BacktestEngine, symbol: str) -> None:
    """
    Strategy function that processes bars with LuxAlgo SMC strategy.
    This integrates with the existing BacktestEngine infrastructure.
    
    Args:
        bars_1min: List of 1-minute bars
        bars_15min: List of 15-minute bars (unused for now)
        strategy: LuxAlgo SMC strategy instance
        engine: Backtest engine for tracking trades
        symbol: Trading symbol
    """
    logger = logging.getLogger('luxalgo_backtest')
    
    # Track position state
    current_position = None
    
    # Process each bar
    for i, bar in enumerate(bars_1min):
        # Process bar with strategy
        result = strategy.process_bar(bar)
        
        # Check for exit first if in position
        if current_position is not None:
            bar_high = bar['high']
            bar_low = bar['low']
            position_side = current_position['side']
            stop_loss = current_position['stop_price']
            take_profit = current_position['target_price']
            
            exit_price = None
            exit_reason = None
            
            # Check stop loss first (conservative)
            if position_side == 'long':
                if bar_low <= stop_loss:
                    exit_price = stop_loss
                    exit_reason = 'stop_loss'
                elif bar_high >= take_profit:
                    exit_price = take_profit
                    exit_reason = 'take_profit'
            else:  # short
                if bar_high >= stop_loss:
                    exit_price = stop_loss
                    exit_reason = 'stop_loss'
                elif bar_low <= take_profit:
                    exit_price = take_profit
                    exit_reason = 'take_profit'
            
            # Close position if exit triggered
            if exit_price is not None:
                # Calculate P&L
                entry_price = current_position['entry_price']
                if position_side == 'long':
                    price_change = exit_price - entry_price
                else:
                    price_change = entry_price - exit_price
                
                tick_size = strategy.tick_size
                tick_value = 50.0 / 4  # ES: $50 per point / 4 ticks per point = $12.50 per tick
                ticks = price_change / tick_size
                pnl = ticks * tick_value * current_position['quantity']
                
                # Hard cap at $300 loss
                if pnl < -300.0:
                    pnl = -300.0
                
                # Subtract commission
                pnl -= engine.config.commission_per_contract * current_position['quantity']
                
                # Calculate duration
                duration = (bar['timestamp'] - current_position['entry_time']).total_seconds() / 60.0
                
                # Create trade record
                trade = Trade(
                    entry_time=current_position['entry_time'],
                    exit_time=bar['timestamp'],
                    symbol=symbol,
                    side=position_side,
                    quantity=current_position['quantity'],
                    entry_price=entry_price,
                    exit_price=exit_price,
                    stop_price=stop_loss,
                    target_price=take_profit,
                    exit_reason=exit_reason,
                    pnl=pnl,
                    ticks=ticks,
                    duration_minutes=duration
                )
                
                # Record trade
                engine.metrics.add_trade(trade)
                engine.current_equity += pnl
                
                # Clear position
                current_position = None
        
        # Check for new entry signal
        if current_position is None and result['signal'] is not None:
            signal = result['signal']
            
            # Apply slippage
            slippage = engine.config.slippage_ticks * strategy.tick_size
            if signal['signal'] == 'long':
                fill_price = signal['entry_price'] + slippage
            else:
                fill_price = signal['entry_price'] - slippage
            
            # Open position
            current_position = {
                'side': signal['signal'],
                'entry_price': fill_price,
                'stop_price': signal['stop_loss'],
                'target_price': signal['take_profit'],
                'entry_time': bar['timestamp'],
                'quantity': 1,  # Always 1 contract
                'symbol': symbol
            }


def print_results(results: Dict[str, Any], symbol: str, start_date: str, end_date: str):
    """Print backtest results."""
    print("\n" + "="*80)
    print("LuxAlgo SMC + Rejection Strategy Backtest Results")
    print("="*80)
    print(f"\nSymbol: {symbol}")
    print(f"Period: {start_date} to {end_date}")
    print(f"\nTotal Trades:        {results['total_trades']}")
    if results['total_trades'] > 0:
        wins = sum(1 for t in results.get('trades', []) if t.pnl > 0) if 'trades' in results else 0
        print(f"Winning Trades:      {wins} ({wins/results['total_trades']*100:.1f}%)")
        print(f"Losing Trades:       {results['total_trades'] - wins} ({(results['total_trades'] - wins)/results['total_trades']*100:.1f}%)")
    print(f"\nWin Rate:            {results['win_rate']:.2f}%")
    print(f"Profit Factor:       {results['profit_factor']:.2f}")
    print(f"\nTotal P&L:           ${results['total_pnl']:.2f}")
    print(f"Return:              {results['total_return']:.2f}%")
    print(f"Final Equity:        ${results['final_equity']:.2f}")
    print(f"\nAverage Win:         ${results['average_win']:.2f}")
    print(f"Average Loss:        ${results['average_loss']:.2f}")
    print(f"\nMax Drawdown:        ${results['max_drawdown_dollars']:.2f} ({results['max_drawdown_percent']:.2f}%)")
    print("="*80 + "\n")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='LuxAlgo SMC + Rejection Strategy Backtest (Uses Main Backtester)',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument('--symbol', type=str, default='ES',
                        help='Symbol to backtest (default: ES)')
    parser.add_argument('--days', type=int,
                        help='Number of days to backtest (default: all available data)')
    parser.add_argument('--start', type=str,
                        help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end', type=str,
                        help='End date (YYYY-MM-DD)')
    parser.add_argument('--capital', type=float, default=50000.0,
                        help='Initial capital (default: 50000)')
    parser.add_argument('--stop-ticks', type=int, default=12,
                        help='Stop loss in ticks (default: 12)')
    parser.add_argument('--target-ticks', type=int, default=12,
                        help='Take profit in ticks (default: 12)')
    parser.add_argument('--verbose', action='store_true',
                        help='Enable verbose logging')
    
    args = parser.parse_args()
    
    # Setup logging
    log_level = logging.INFO if args.verbose else logging.WARNING
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)
    
    # Determine data file
    data_path = os.path.join(PROJECT_ROOT, 'data', 'historical_data')
    
    # Parse dates
    tz = pytz.UTC
    
    if args.end:
        end_date = datetime.strptime(args.end, '%Y-%m-%d')
        end_date = tz.localize(end_date.replace(hour=23, minute=59, second=59))
    else:
        # Get last date from data
        csv_file = os.path.join(data_path, f'{args.symbol}_1min.csv')
        if os.path.exists(csv_file):
            with open(csv_file, 'r') as f:
                lines = f.readlines()
                if len(lines) > 1:
                    last_line = lines[-1]
                    last_timestamp = last_line.split(',')[0]
                    end_date = datetime.strptime(last_timestamp, '%Y-%m-%d %H:%M:%S')
                    end_date = tz.localize(end_date)
                else:
                    end_date = datetime.now(tz)
        else:
            logger.error(f"Data file not found: {csv_file}")
            return 1
    
    if args.start:
        start_date = datetime.strptime(args.start, '%Y-%m-%d')
        start_date = tz.localize(start_date)
    elif args.days:
        start_date = end_date - timedelta(days=args.days)
    else:
        # Use all available data (96 days)
        start_date = end_date - timedelta(days=96)
    
    logger.info(f"Date range: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
    
    # Determine tick size
    tick_size = 0.25 if args.symbol in ['ES', 'MES'] else 0.25
    
    # Create strategy
    strategy = LuxAlgoSMCStrategy(
        tick_size=tick_size,
        stop_loss_ticks=args.stop_ticks,
        take_profit_ticks=args.target_ticks
    )
    
    # Create backtest configuration using the REAL backtest framework
    backtest_config = BacktestConfig(
        start_date=start_date,
        end_date=end_date,
        initial_equity=args.capital,
        symbols=[args.symbol],
        data_path=data_path,
        slippage_ticks=0.5,
        commission_per_contract=2.50,
        use_tick_data=False  # Use 1-min bars (default for realistic futures hours)
    )
    
    # Bot config for the engine
    bot_config = {
        'instrument': args.symbol,
        'tick_size': tick_size,
        'tick_value': 12.50,  # ES: $12.50 per tick
        'account_size': args.capital
    }
    
    # Create backtest engine (the REAL one with futures hours support)
    logger.info("Creating backtest engine with realistic futures hours...")
    engine = BacktestEngine(backtest_config, bot_config)
    
    # Create strategy function that integrates with engine
    def strategy_func(bars_1min, bars_15min):
        run_luxalgo_strategy_backtest(bars_1min, bars_15min, strategy, engine, args.symbol)
    
    # Run backtest
    logger.info("Running backtest...")
    logger.info(f"Using {len(engine.data_loader.load_bar_data(args.symbol, '1min'))} bars of REAL data")
    
    results = engine.run_with_strategy(strategy_func)
    
    # Print results
    print_results(results, args.symbol, start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d'))
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
