#!/usr/bin/env python3
"""
LuxAlgo SMC Strategy Backtester

Uses the existing backtest infrastructure (BacktestEngine, realistic futures hours, gaps)
but runs the LuxAlgo SMC + Rejection strategy independently for testing.

This is separate from the main bot - purely for strategy validation.
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

# Add parent directory to path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'src'))

# Import backtesting framework
from backtesting import BacktestConfig, BacktestEngine
from backtest_reporter import reset_reporter, get_reporter

# Import the LuxAlgo strategy
from luxalgo_smc_strategy import LuxAlgoSMCStrategy

# Import symbol specs for tick size
from symbol_specs import get_symbol_spec


def parse_arguments():
    """Parse command-line arguments for LuxAlgo SMC backtest"""
    parser = argparse.ArgumentParser(
        description='LuxAlgo SMC + Rejection Strategy Backtester',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run backtest for last 30 days
  python dev/run_luxalgo_backtest.py --days 30
  
  # Run backtest with specific date range
  python dev/run_luxalgo_backtest.py --start 2024-01-01 --end 2024-01-31
  
  # Run with custom parameters
  python dev/run_luxalgo_backtest.py --days 30 --swing-lookback 50 --atr-period 200
        """
    )
    
    parser.add_argument('--start', type=str, help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end', type=str, help='End date (YYYY-MM-DD)')
    parser.add_argument('--days', type=int, default=30, help='Backtest last N days (default: 30)')
    parser.add_argument('--symbol', type=str, default='ES', help='Symbol to backtest (default: ES)')
    parser.add_argument('--data-path', type=str, default=None, help='Path to historical data')
    
    # Strategy parameters
    parser.add_argument('--swing-lookback', type=int, default=50, help='Major swing lookback (default: 50)')
    parser.add_argument('--internal-lookback', type=int, default=5, help='Internal swing lookback (default: 5)')
    parser.add_argument('--atr-period', type=int, default=200, help='ATR period (default: 200)')
    parser.add_argument('--atr-multiplier', type=float, default=2.0, help='ATR multiplier for OB filter (default: 2.0)')
    parser.add_argument('--fvg-multiplier', type=float, default=2.0, help='FVG delta multiplier (default: 2.0)')
    parser.add_argument('--stop-ticks', type=int, default=12, help='Stop loss in ticks (default: 12)')
    parser.add_argument('--target-ticks', type=int, default=12, help='Take profit in ticks (default: 12)')
    
    return parser.parse_args()


def run_luxalgo_backtest(args) -> Dict[str, Any]:
    """
    Run LuxAlgo SMC strategy backtest using existing infrastructure.
    """
    logger = logging.getLogger('luxalgo_backtest')
    
    # Get symbol spec for tick size
    symbol = args.symbol
    symbol_spec = get_symbol_spec(symbol)
    tick_size = symbol_spec.tick_size
    tick_value = symbol_spec.tick_value
    
    # Initialize the LuxAlgo strategy (EXACT match to Pine Script)
    strategy = LuxAlgoSMCStrategy(
        tick_size=tick_size,
        swing_lookback=args.swing_lookback,
        internal_lookback=args.internal_lookback,
        atr_period=args.atr_period,
        stop_loss_ticks=args.stop_ticks,
        take_profit_ticks=args.target_ticks,
        use_auto_threshold=True  # LuxAlgo's Auto Threshold for FVG
    )
    
    # Determine date range
    tz = pytz.timezone("US/Eastern")
    data_path = args.data_path if args.data_path else os.path.join(PROJECT_ROOT, "data/historical_data")
    csv_path = os.path.join(data_path, f"{symbol}_1min.csv")
    
    if args.start and args.end:
        start_date = datetime.strptime(args.start, '%Y-%m-%d')
        end_date = datetime.strptime(args.end, '%Y-%m-%d')
    else:
        # Get end date from data file
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
    
    # Initialize reporter
    reporter = reset_reporter(starting_balance=50000.0, max_contracts=1)
    
    # Print header
    print("\n" + "=" * 70)
    print("  LUXALGO SMC + REJECTION STRATEGY BACKTEST")
    print("=" * 70)
    print(f"  Symbol: {symbol}")
    print(f"  Period: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
    print(f"  Tick Size: ${tick_size}  |  Tick Value: ${tick_value}")
    print("-" * 70)
    print("  STRATEGY PARAMETERS:")
    print(f"    Swing Lookback: {args.swing_lookback} bars (major structure)")
    print(f"    Internal Lookback: {args.internal_lookback} bars (internal structure)")
    print(f"    ATR Period: {args.atr_period} | ATR Multiplier: {args.atr_multiplier}x")
    print(f"    FVG Delta Multiplier: {args.fvg_multiplier}x")
    print(f"    Stop Loss: {args.stop_ticks} ticks | Take Profit: {args.target_ticks} ticks")
    print("=" * 70 + "\n")
    
    # Create backtest config
    backtest_config = BacktestConfig(
        start_date=start_date,
        end_date=end_date,
        initial_equity=50000.0,
        symbols=[symbol],
        data_path=data_path,
        use_tick_data=False
    )
    
    # Create fake bot_config dict for engine
    bot_config = {
        'instrument': symbol,
        'tick_size': tick_size,
        'tick_value': tick_value,
        'account_size': 50000.0,
        'max_contracts': 1
    }
    
    # Create backtest engine
    engine = BacktestEngine(backtest_config, bot_config)
    
    # Tracking variables
    bars_processed = 0
    total_bars = 0
    current_position = None
    trades = []
    
    # Counters for statistics
    total_signals = 0
    long_signals = 0
    short_signals = 0
    structure_breaks = 0
    demand_blocks_created = 0
    supply_blocks_created = 0
    fvgs_created = 0
    
    def luxalgo_strategy_backtest(bars_1min: List[Dict[str, Any]], bars_15min: List[Dict[str, Any]]) -> None:
        """Process bars through LuxAlgo SMC strategy."""
        nonlocal bars_processed, total_bars, current_position
        nonlocal total_signals, long_signals, short_signals, structure_breaks
        nonlocal demand_blocks_created, supply_blocks_created, fvgs_created
        
        total_bars = len(bars_1min)
        progress_interval = max(500, total_bars // 10)
        
        prev_demand_count = 0
        prev_supply_count = 0
        prev_bullish_fvg_count = 0
        prev_bearish_fvg_count = 0
        
        for bar_idx, bar in enumerate(bars_1min):
            bars_processed = bar_idx + 1
            
            # Progress update
            if bars_processed % progress_interval == 0 or bars_processed == total_bars:
                pct = (bars_processed / total_bars) * 100
                print(f"\r  Processing: {bars_processed:,}/{total_bars:,} bars ({pct:.1f}%) | "
                      f"Signals: {total_signals} | Trades: {len(trades)}", end="")
            
            timestamp = bar['timestamp']
            
            # Process bar through strategy
            result = strategy.process_bar(bar)
            
            # Track structure breaks
            if result['structure_break']:
                structure_breaks += 1
                sb = result['structure_break']
                # Only log CHoCH (more significant)
                if sb['type'] == 'CHoCH':
                    print(f"\n  💎 CHoCH {sb['direction']} @ ${sb['level']:.2f}")
            
            # Track new zones
            if result['active_demand_blocks'] > prev_demand_count:
                demand_blocks_created += 1
            if result['active_supply_blocks'] > prev_supply_count:
                supply_blocks_created += 1
            if result['active_bullish_fvgs'] > prev_bullish_fvg_count:
                fvgs_created += 1
            if result['active_bearish_fvgs'] > prev_bearish_fvg_count:
                fvgs_created += 1
                
            prev_demand_count = result['active_demand_blocks']
            prev_supply_count = result['active_supply_blocks']
            prev_bullish_fvg_count = result['active_bullish_fvgs']
            prev_bearish_fvg_count = result['active_bearish_fvgs']
            
            # Check for signals
            signal = result['signal']
            
            if signal and current_position is None:
                total_signals += 1
                
                if signal['signal'] == 'long':
                    long_signals += 1
                else:
                    short_signals += 1
                
                # Log signal
                strength_emoji = "🔥" if signal['strength'] == 'VERY_STRONG' else "✅"
                print(f"\n  {strength_emoji} {signal['signal'].upper()} SIGNAL | "
                      f"{signal['reason']} | Entry: ${signal['entry_price']:.2f} | "
                      f"SL: ${signal['stop_loss']:.2f} | TP: ${signal['take_profit']:.2f}")
                
                # Open position
                current_position = {
                    'side': signal['signal'],
                    'entry_price': signal['entry_price'],
                    'entry_time': timestamp,
                    'stop_loss': signal['stop_loss'],
                    'take_profit': signal['take_profit'],
                    'reason': signal['reason'],
                    'strength': signal['strength']
                }
            
            # Check for exit if in position
            if current_position:
                side = current_position['side']
                entry = current_position['entry_price']
                sl = current_position['stop_loss']
                tp = current_position['take_profit']
                
                exit_price = None
                exit_reason = None
                
                if side == 'long':
                    # Check stop loss
                    if bar['low'] <= sl:
                        exit_price = sl
                        exit_reason = 'stop_loss'
                    # Check take profit
                    elif bar['high'] >= tp:
                        exit_price = tp
                        exit_reason = 'take_profit'
                else:  # short
                    # Check stop loss
                    if bar['high'] >= sl:
                        exit_price = sl
                        exit_reason = 'stop_loss'
                    # Check take profit
                    elif bar['low'] <= tp:
                        exit_price = tp
                        exit_reason = 'take_profit'
                
                if exit_price:
                    # Calculate P&L
                    if side == 'long':
                        pnl = (exit_price - entry) / tick_size * tick_value
                    else:
                        pnl = (entry - exit_price) / tick_size * tick_value
                    
                    # Record trade
                    trade = {
                        'side': side,
                        'entry_price': entry,
                        'exit_price': exit_price,
                        'entry_time': current_position['entry_time'],
                        'exit_time': timestamp,
                        'pnl': pnl,
                        'exit_reason': exit_reason,
                        'reason': current_position['reason'],
                        'strength': current_position['strength']
                    }
                    trades.append(trade)
                    
                    # Log exit
                    pnl_emoji = "💰" if pnl > 0 else "❌"
                    print(f"\n  {pnl_emoji} EXIT {exit_reason.upper()} | P&L: ${pnl:.2f}")
                    
                    current_position = None
        
        print()  # New line after progress
    
    # Run backtest
    engine.run_with_strategy(luxalgo_strategy_backtest)
    
    # Calculate statistics
    total_trades = len(trades)
    winners = [t for t in trades if t['pnl'] > 0]
    losers = [t for t in trades if t['pnl'] <= 0]
    win_rate = (len(winners) / total_trades * 100) if total_trades > 0 else 0
    
    total_pnl = sum(t['pnl'] for t in trades)
    gross_profit = sum(t['pnl'] for t in winners) if winners else 0
    gross_loss = sum(t['pnl'] for t in losers) if losers else 0
    
    avg_winner = gross_profit / len(winners) if winners else 0
    avg_loser = abs(gross_loss / len(losers)) if losers else 0
    profit_factor = gross_profit / abs(gross_loss) if gross_loss != 0 else float('inf')
    
    # Print results
    print("\n" + "=" * 70)
    print("  BACKTEST RESULTS")
    print("=" * 70)
    print(f"\n  📊 MARKET STRUCTURE:")
    print(f"     Structure Breaks (BOS/CHoCH): {structure_breaks}")
    print(f"     Demand Blocks Created: {demand_blocks_created}")
    print(f"     Supply Blocks Created: {supply_blocks_created}")
    print(f"     FVGs Created: {fvgs_created}")
    
    print(f"\n  📈 SIGNALS:")
    print(f"     Total Signals: {total_signals}")
    print(f"     Long Signals: {long_signals}")
    print(f"     Short Signals: {short_signals}")
    
    print(f"\n  💰 TRADE PERFORMANCE:")
    print(f"     Total Trades: {total_trades}")
    print(f"     Winners: {len(winners)} | Losers: {len(losers)}")
    print(f"     Win Rate: {win_rate:.1f}%")
    print(f"     Profit Factor: {profit_factor:.2f}")
    
    print(f"\n  💵 P&L SUMMARY:")
    print(f"     Total P&L: ${total_pnl:.2f}")
    print(f"     Gross Profit: ${gross_profit:.2f}")
    print(f"     Gross Loss: ${gross_loss:.2f}")
    print(f"     Avg Winner: ${avg_winner:.2f}")
    print(f"     Avg Loser: ${avg_loser:.2f}")
    
    # Trade breakdown by reason
    print(f"\n  📋 TRADE BREAKDOWN BY REASON:")
    reasons = {}
    for t in trades:
        reason = t['reason']
        if reason not in reasons:
            reasons[reason] = {'count': 0, 'pnl': 0, 'wins': 0}
        reasons[reason]['count'] += 1
        reasons[reason]['pnl'] += t['pnl']
        if t['pnl'] > 0:
            reasons[reason]['wins'] += 1
    
    for reason, stats in sorted(reasons.items(), key=lambda x: x[1]['count'], reverse=True):
        wr = (stats['wins'] / stats['count'] * 100) if stats['count'] > 0 else 0
        print(f"     {reason}: {stats['count']} trades | WR: {wr:.0f}% | P&L: ${stats['pnl']:.2f}")
    
    print("\n" + "=" * 70)
    
    return {
        'total_trades': total_trades,
        'win_rate': win_rate,
        'profit_factor': profit_factor,
        'total_pnl': total_pnl,
        'trades': trades
    }


def main():
    """Main entry point"""
    args = parse_arguments()
    
    # Setup minimal logging
    logging.basicConfig(level=logging.WARNING)
    
    try:
        results = run_luxalgo_backtest(args)
        
        if results['total_trades'] > 0:
            print(f"\n  ✅ Backtest completed successfully!")
            sys.exit(0)
        else:
            print(f"\n  ⚠️ No trades generated - check strategy parameters")
            sys.exit(1)
    except Exception as e:
        print(f"\n  ❌ Backtest failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
