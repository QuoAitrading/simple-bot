#!/usr/bin/env python3
"""
LuxAlgo SMC + Rejection Strategy Backtest Runner

This script runs backtests for the LuxAlgo SMC + Rejection strategy using
the existing backtest framework with realistic futures hours.
"""

import argparse
import sys
import os
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import pytz
import csv

# Add parent directory to path to import from src/
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'src'))

# Import strategy
from luxalgo_smc_strategy import LuxAlgoSMCStrategy


class LuxAlgoBacktester:
    """
    Backtester for LuxAlgo SMC + Rejection Strategy.
    
    Uses realistic futures market hours and proper order execution simulation.
    """
    
    def __init__(self,
                 strategy: LuxAlgoSMCStrategy,
                 initial_capital: float = 50000.0,
                 commission_per_contract: float = 2.50,
                 slippage_ticks: float = 0.5,
                 contracts_per_trade: int = 1):
        """
        Initialize backtester.
        
        Args:
            strategy: LuxAlgoSMCStrategy instance
            initial_capital: Starting capital
            commission_per_contract: Round-trip commission
            slippage_ticks: Average slippage in ticks
            contracts_per_trade: Number of contracts per trade
        """
        self.strategy = strategy
        self.initial_capital = initial_capital
        self.commission_per_contract = commission_per_contract
        self.slippage_ticks = slippage_ticks
        self.contracts_per_trade = contracts_per_trade
        
        # State
        self.current_position = None
        self.equity = initial_capital
        self.trades = []
        self.equity_curve = []
        
        self.logger = logging.getLogger(__name__)
    
    def _is_market_hours(self, timestamp: datetime) -> bool:
        """
        Check if timestamp is within regular futures trading hours.
        
        Futures trade nearly 24 hours, but we focus on regular session:
        Sunday 6:00 PM ET - Friday 5:00 PM ET (with daily breaks)
        """
        if timestamp.tzinfo is None:
            # Assume UTC, convert to Eastern
            eastern = pytz.timezone('US/Eastern')
            timestamp_utc = pytz.UTC.localize(timestamp)
            timestamp = timestamp_utc.astimezone(eastern)
        
        # For simplicity, accept all hours (futures trade 23.5 hours/day)
        # The CSV data already contains realistic futures hours
        return True
    
    def _simulate_fill(self, signal: Dict[str, Any], current_bar: Dict[str, Any]) -> float:
        """
        Simulate realistic order fill with slippage.
        
        Args:
            signal: Signal dictionary with entry_price
            current_bar: Current bar data
        
        Returns:
            Actual fill price
        """
        entry_price = signal['entry_price']
        signal_type = signal['signal']
        
        # Apply slippage
        slippage = self.slippage_ticks * self.strategy.tick_size
        
        if signal_type == 'long':
            # Long entry - assume we pay the ask (worse price)
            fill_price = entry_price + slippage
        else:
            # Short entry - assume we sell at bid (worse price)
            fill_price = entry_price - slippage
        
        return fill_price
    
    def _check_exit(self, current_bar: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Check if position should be exited.
        
        Returns:
            Exit info dictionary or None
        """
        if self.current_position is None:
            return None
        
        bar_high = current_bar['high']
        bar_low = current_bar['low']
        position_type = self.current_position['signal']
        stop_loss = self.current_position['stop_loss']
        take_profit = self.current_position['take_profit']
        
        # Check stop loss first (conservative)
        if position_type == 'long':
            if bar_low <= stop_loss:
                return {
                    'exit_price': stop_loss,
                    'exit_reason': 'stop_loss',
                    'timestamp': current_bar['timestamp']
                }
            # Check take profit
            if bar_high >= take_profit:
                return {
                    'exit_price': take_profit,
                    'exit_reason': 'take_profit',
                    'timestamp': current_bar['timestamp']
                }
        else:  # short
            if bar_high >= stop_loss:
                return {
                    'exit_price': stop_loss,
                    'exit_reason': 'stop_loss',
                    'timestamp': current_bar['timestamp']
                }
            # Check take profit
            if bar_low <= take_profit:
                return {
                    'exit_price': take_profit,
                    'exit_reason': 'take_profit',
                    'timestamp': current_bar['timestamp']
                }
        
        return None
    
    def _calculate_pnl(self, entry_price: float, exit_price: float, signal_type: str) -> float:
        """
        Calculate P&L for a trade.
        
        Args:
            entry_price: Entry price
            exit_price: Exit price
            signal_type: 'long' or 'short'
        
        Returns:
            P&L in dollars (including commission)
        """
        # ES futures: 1 point = $50, tick = 0.25 = $12.50
        point_value = 50.0
        
        if signal_type == 'long':
            pnl = (exit_price - entry_price) * point_value * self.contracts_per_trade
        else:
            pnl = (entry_price - exit_price) * point_value * self.contracts_per_trade
        
        # Subtract commission
        pnl -= self.commission_per_contract * self.contracts_per_trade
        
        return pnl
    
    def run(self, bars: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Run backtest on historical data.
        
        Args:
            bars: List of bar dictionaries
        
        Returns:
            Backtest results dictionary
        """
        self.logger.info(f"Starting backtest with {len(bars)} bars...")
        
        for i, bar in enumerate(bars):
            # Check if market hours
            if not self._is_market_hours(bar['timestamp']):
                continue
            
            # Process bar with strategy
            result = self.strategy.process_bar(bar)
            
            # Check for exit first
            if self.current_position is not None:
                exit_info = self._check_exit(bar)
                if exit_info:
                    # Close position
                    entry_price = self.current_position['entry_price']
                    exit_price = exit_info['exit_price']
                    signal_type = self.current_position['signal']
                    
                    pnl = self._calculate_pnl(entry_price, exit_price, signal_type)
                    self.equity += pnl
                    
                    # Record trade
                    entry_time = self.current_position['entry_time']
                    duration = (exit_info['timestamp'] - entry_time).total_seconds() / 60.0
                    
                    trade = {
                        'entry_time': entry_time,
                        'exit_time': exit_info['timestamp'],
                        'signal': signal_type,
                        'entry_price': entry_price,
                        'exit_price': exit_price,
                        'stop_loss': self.current_position['stop_loss'],
                        'take_profit': self.current_position['take_profit'],
                        'exit_reason': exit_info['exit_reason'],
                        'pnl': pnl,
                        'duration_minutes': duration,
                        'strength': self.current_position['strength'],
                        'reason': self.current_position['reason']
                    }
                    self.trades.append(trade)
                    
                    # Log trade
                    if i % 100 == 0:
                        self.logger.info(
                            f"Trade #{len(self.trades)}: {signal_type.upper()} "
                            f"Entry={entry_price:.2f} Exit={exit_price:.2f} "
                            f"P&L=${pnl:.2f} Reason={exit_info['exit_reason']}"
                        )
                    
                    # Clear position
                    self.current_position = None
            
            # Check for new entry signal
            if self.current_position is None and result['signal'] is not None:
                signal = result['signal']
                
                # Simulate fill
                fill_price = self._simulate_fill(signal, bar)
                
                # Open position
                self.current_position = {
                    'signal': signal['signal'],
                    'entry_price': fill_price,
                    'stop_loss': signal['stop_loss'],
                    'take_profit': signal['take_profit'],
                    'entry_time': bar['timestamp'],
                    'strength': signal['strength'],
                    'reason': signal['reason']
                }
                
                if len(self.trades) % 50 == 0:
                    self.logger.info(
                        f"New {signal['signal'].upper()} signal at {bar['timestamp']}: "
                        f"Entry={fill_price:.2f} SL={signal['stop_loss']:.2f} "
                        f"TP={signal['take_profit']:.2f} ({signal['strength']})"
                    )
            
            # Record equity
            self.equity_curve.append({
                'timestamp': bar['timestamp'],
                'equity': self.equity
            })
        
        # Calculate statistics
        return self._calculate_statistics()
    
    def _calculate_statistics(self) -> Dict[str, Any]:
        """Calculate backtest statistics."""
        if len(self.trades) == 0:
            return {
                'total_trades': 0,
                'total_pnl': 0,
                'win_rate': 0,
                'avg_win': 0,
                'avg_loss': 0,
                'profit_factor': 0,
                'max_drawdown': 0,
                'final_equity': self.equity
            }
        
        # Basic stats
        wins = [t for t in self.trades if t['pnl'] > 0]
        losses = [t for t in self.trades if t['pnl'] <= 0]
        
        total_pnl = sum(t['pnl'] for t in self.trades)
        win_rate = len(wins) / len(self.trades) * 100 if len(self.trades) > 0 else 0
        
        avg_win = sum(t['pnl'] for t in wins) / len(wins) if len(wins) > 0 else 0
        avg_loss = sum(t['pnl'] for t in losses) / len(losses) if len(losses) > 0 else 0
        
        gross_wins = sum(t['pnl'] for t in wins) if len(wins) > 0 else 0
        gross_losses = abs(sum(t['pnl'] for t in losses)) if len(losses) > 0 else 0
        profit_factor = gross_wins / gross_losses if gross_losses > 0 else float('inf')
        
        # Max drawdown
        peak = self.initial_capital
        max_dd = 0
        for point in self.equity_curve:
            equity = point['equity']
            if equity > peak:
                peak = equity
            dd = (peak - equity) / peak * 100 if peak > 0 else 0
            if dd > max_dd:
                max_dd = dd
        
        # Average trade duration
        avg_duration = sum(t['duration_minutes'] for t in self.trades) / len(self.trades)
        
        # Count by exit reason
        stop_losses = len([t for t in self.trades if t['exit_reason'] == 'stop_loss'])
        take_profits = len([t for t in self.trades if t['exit_reason'] == 'take_profit'])
        
        return {
            'total_trades': len(self.trades),
            'winning_trades': len(wins),
            'losing_trades': len(losses),
            'total_pnl': total_pnl,
            'win_rate': win_rate,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'profit_factor': profit_factor,
            'max_drawdown_pct': max_dd,
            'final_equity': self.equity,
            'return_pct': (self.equity - self.initial_capital) / self.initial_capital * 100,
            'avg_duration_minutes': avg_duration,
            'stop_losses': stop_losses,
            'take_profits': take_profits,
            'trades': self.trades
        }


def load_csv_data(file_path: str, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None) -> List[Dict[str, Any]]:
    """
    Load historical data from CSV file.
    
    Args:
        file_path: Path to CSV file
        start_date: Optional start date filter
        end_date: Optional end date filter
    
    Returns:
        List of bar dictionaries
    """
    bars = []
    
    with open(file_path, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                # Parse timestamp
                timestamp = datetime.strptime(row['timestamp'], '%Y-%m-%d %H:%M:%S')
                timestamp = pytz.UTC.localize(timestamp)
                
                # Apply date filters
                if start_date and timestamp < start_date:
                    continue
                if end_date and timestamp > end_date:
                    continue
                
                bar = {
                    'timestamp': timestamp,
                    'open': float(row['open']),
                    'high': float(row['high']),
                    'low': float(row['low']),
                    'close': float(row['close']),
                    'volume': float(row['volume']) if 'volume' in row else 0
                }
                bars.append(bar)
            except (ValueError, KeyError) as e:
                continue
    
    return bars


def print_results(results: Dict[str, Any]):
    """Print backtest results."""
    print("\n" + "="*80)
    print("LuxAlgo SMC + Rejection Strategy Backtest Results")
    print("="*80)
    print(f"\nTotal Trades:        {results['total_trades']}")
    print(f"Winning Trades:      {results['winning_trades']} ({results['winning_trades']/results['total_trades']*100:.1f}%)")
    print(f"Losing Trades:       {results['losing_trades']} ({results['losing_trades']/results['total_trades']*100:.1f}%)")
    print(f"\nWin Rate:            {results['win_rate']:.2f}%")
    print(f"Profit Factor:       {results['profit_factor']:.2f}")
    print(f"\nTotal P&L:           ${results['total_pnl']:.2f}")
    print(f"Return:              {results['return_pct']:.2f}%")
    print(f"Final Equity:        ${results['final_equity']:.2f}")
    print(f"\nAverage Win:         ${results['avg_win']:.2f}")
    print(f"Average Loss:        ${results['avg_loss']:.2f}")
    print(f"\nMax Drawdown:        {results['max_drawdown_pct']:.2f}%")
    print(f"Avg Trade Duration:  {results['avg_duration_minutes']:.1f} minutes")
    print(f"\nExit Breakdown:")
    print(f"  Take Profits:      {results['take_profits']} ({results['take_profits']/results['total_trades']*100:.1f}%)")
    print(f"  Stop Losses:       {results['stop_losses']} ({results['stop_losses']/results['total_trades']*100:.1f}%)")
    print("="*80 + "\n")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='LuxAlgo SMC + Rejection Strategy Backtest',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument('--symbol', type=str, default='ES',
                        help='Symbol to backtest (default: ES)')
    parser.add_argument('--data-file', type=str,
                        help='Path to CSV data file (default: data/historical_data/{SYMBOL}_1min.csv)')
    parser.add_argument('--days', type=int, default=30,
                        help='Number of days to backtest (default: 30)')
    parser.add_argument('--start', type=str,
                        help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end', type=str,
                        help='End date (YYYY-MM-DD)')
    parser.add_argument('--capital', type=float, default=50000.0,
                        help='Initial capital (default: 50000)')
    parser.add_argument('--contracts', type=int, default=1,
                        help='Contracts per trade (default: 1)')
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
    if args.data_file:
        data_file = args.data_file
    else:
        data_file = os.path.join(PROJECT_ROOT, 'data', 'historical_data', f'{args.symbol}_1min.csv')
    
    if not os.path.exists(data_file):
        logger.error(f"Data file not found: {data_file}")
        return 1
    
    # Parse dates
    end_date = None
    start_date = None
    
    if args.end:
        end_date = datetime.strptime(args.end, '%Y-%m-%d')
        end_date = pytz.UTC.localize(end_date)
    else:
        end_date = datetime.now(pytz.UTC)
    
    if args.start:
        start_date = datetime.strptime(args.start, '%Y-%m-%d')
        start_date = pytz.UTC.localize(start_date)
    else:
        start_date = end_date - timedelta(days=args.days)
    
    logger.info(f"Loading data from {data_file}...")
    logger.info(f"Date range: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
    
    # Load data
    bars = load_csv_data(data_file, start_date, end_date)
    
    if len(bars) == 0:
        logger.error("No data loaded!")
        return 1
    
    logger.info(f"Loaded {len(bars)} bars")
    
    # Determine tick size
    tick_size = 0.25 if args.symbol in ['ES', 'MES'] else 0.25
    
    # Create strategy
    strategy = LuxAlgoSMCStrategy(
        tick_size=tick_size,
        stop_loss_ticks=args.stop_ticks,
        take_profit_ticks=args.target_ticks
    )
    
    # Create backtester
    backtester = LuxAlgoBacktester(
        strategy=strategy,
        initial_capital=args.capital,
        contracts_per_trade=args.contracts
    )
    
    # Run backtest
    logger.info("Running backtest...")
    results = backtester.run(bars)
    
    # Print results
    print_results(results)
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
