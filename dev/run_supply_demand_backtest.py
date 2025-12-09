#!/usr/bin/env python3
"""
Supply/Demand Rejection Strategy - Backtesting Runner

This script backtests the supply/demand rejection strategy on historical ES data.
It loads 1-minute ES candles, runs the strategy, and generates a performance report.

The strategy identifies institutional supply/demand zones and trades rejections
when price returns to these zones.

Usage:
    python dev/run_supply_demand_backtest.py --days 30
    python dev/run_supply_demand_backtest.py --start 2024-01-01 --end 2024-01-31
"""

import argparse
import sys
import os
import logging
import csv
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from collections import deque
import pytz

# Add parent directory to path to import from src/
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'src'))

# Import the supply/demand strategy
from supply_demand_bot import SupplyDemandStrategy, Candle, Zone

# Import symbol specs for tick size/value
from symbol_specs import get_symbol_spec


class Trade:
    """Represents a completed trade"""
    def __init__(
        self,
        entry_time: datetime,
        exit_time: datetime,
        side: str,
        entry_price: float,
        exit_price: float,
        stop_price: float,
        target_price: float,
        exit_reason: str,
        tick_size: float,
        tick_value: float
    ):
        self.entry_time = entry_time
        self.exit_time = exit_time
        self.side = side
        self.entry_price = entry_price
        self.exit_price = exit_price
        self.stop_price = stop_price
        self.target_price = target_price
        self.exit_reason = exit_reason
        
        # Calculate P&L
        if side == 'long':
            self.price_change = exit_price - entry_price
        else:  # short
            self.price_change = entry_price - exit_price
        
        self.ticks = self.price_change / tick_size
        self.pnl = self.ticks * tick_value
        self.duration = (exit_time - entry_time).total_seconds() / 60  # minutes


class BacktestRunner:
    """
    Runs backtest for supply/demand strategy
    """
    
    def __init__(
        self,
        symbol: str = 'ES',
        initial_balance: float = 50000.0,
        commission_per_contract: float = 2.50,
        contracts: int = 1,
        logger: Optional[logging.Logger] = None
    ):
        self.symbol = symbol
        self.initial_balance = initial_balance
        self.commission_per_contract = commission_per_contract
        self.contracts = contracts
        self.logger = logger or logging.getLogger(__name__)
        
        # Get symbol specifications
        symbol_spec = get_symbol_spec(symbol)
        self.tick_size = symbol_spec.tick_size
        self.tick_value = symbol_spec.tick_value
        
        # Initialize strategy
        self.strategy = SupplyDemandStrategy(
            tick_size=self.tick_size,
            tick_value=self.tick_value,
            logger=self.logger
        )
        
        # Trading state
        self.balance = initial_balance
        self.position: Optional[Dict] = None
        self.trades: List[Trade] = []
        self.equity_curve: List[Tuple[datetime, float]] = []
        
    def load_data(self, file_path: str, start_date: datetime, end_date: datetime) -> List[Candle]:
        """
        Load historical candle data from CSV file
        
        Expected CSV format:
        timestamp,open,high,low,close,volume,time_diff
        """
        candles = []
        
        self.logger.info(f"Loading data from {file_path}")
        
        with open(file_path, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    # Parse timestamp
                    timestamp_str = row['timestamp']
                    timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
                    
                    # Make timezone-aware in UTC (data is in UTC)
                    timestamp = pytz.UTC.localize(timestamp)
                    
                    # Filter by date range
                    if timestamp < start_date or timestamp > end_date:
                        continue
                    
                    candle = Candle(
                        timestamp=timestamp,
                        open=float(row['open']),
                        high=float(row['high']),
                        low=float(row['low']),
                        close=float(row['close']),
                        volume=float(row['volume'])
                    )
                    candles.append(candle)
                    
                except (KeyError, ValueError) as e:
                    self.logger.warning(f"Skipping invalid row: {row} - {e}")
                    continue
        
        self.logger.info(f"Loaded {len(candles)} candles from {start_date} to {end_date}")
        return candles
    
    def check_position_exit(self, candle: Candle) -> bool:
        """
        Check if current position should be exited based on stop/target
        
        Returns True if position was closed
        """
        if not self.position:
            return False
        
        side = self.position['side']
        entry_price = self.position['entry_price']
        stop_price = self.position['stop_price']
        target_price = self.position['target_price']
        entry_time = self.position['entry_time']
        
        exit_price = None
        exit_reason = None
        
        if side == 'long':
            # Check if stop hit
            if candle.low <= stop_price:
                exit_price = stop_price
                exit_reason = 'stop_loss'
            # Check if target hit
            elif candle.high >= target_price:
                exit_price = target_price
                exit_reason = 'target'
        else:  # short
            # Check if stop hit
            if candle.high >= stop_price:
                exit_price = stop_price
                exit_reason = 'stop_loss'
            # Check if target hit
            elif candle.low <= target_price:
                exit_price = target_price
                exit_reason = 'target'
        
        if exit_price is not None:
            # Close position
            trade = Trade(
                entry_time=entry_time,
                exit_time=candle.timestamp,
                side=side,
                entry_price=entry_price,
                exit_price=exit_price,
                stop_price=stop_price,
                target_price=target_price,
                exit_reason=exit_reason,
                tick_size=self.tick_size,
                tick_value=self.tick_value
            )
            
            # Update balance (subtract commission for round-trip)
            pnl_after_commission = (trade.pnl * self.contracts) - self.commission_per_contract
            self.balance += pnl_after_commission
            
            self.trades.append(trade)
            self.position = None
            
            self.logger.info(
                f"Closed {side.upper()} - Exit: {exit_reason}, "
                f"P&L: ${pnl_after_commission:.2f} ({trade.ticks:.1f} ticks), "
                f"Duration: {trade.duration:.0f}m, Balance: ${self.balance:.2f}"
            )
            
            return True
        
        return False
    
    def run_backtest(
        self,
        start_date: datetime,
        end_date: datetime,
        data_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Run the backtest
        
        Args:
            start_date: Start date for backtest
            end_date: End date for backtest
            data_path: Optional path to data directory
            
        Returns:
            Dictionary with backtest results
        """
        # Determine data file path
        if data_path is None:
            data_path = os.path.join(PROJECT_ROOT, 'data', 'historical_data')
        
        data_file = os.path.join(data_path, f'{self.symbol}_1min.csv')
        
        if not os.path.exists(data_file):
            raise FileNotFoundError(f"Data file not found: {data_file}")
        
        # Load data
        candles = self.load_data(data_file, start_date, end_date)
        
        if not candles:
            raise ValueError("No candles loaded. Check date range and data file.")
        
        self.logger.info(f"Starting backtest from {start_date} to {end_date}")
        self.logger.info(f"Initial balance: ${self.initial_balance:.2f}")
        self.logger.info(f"Symbol: {self.symbol}, Tick size: {self.tick_size}, Tick value: ${self.tick_value:.2f}")
        
        # Process each candle
        for i, candle in enumerate(candles):
            # Check if we need to exit current position
            if self.position:
                self.check_position_exit(candle)
            
            # Process candle through strategy
            signal = self.strategy.process_candle(candle)
            
            # Record equity
            if i % 100 == 0:  # Record every 100 candles
                self.equity_curve.append((candle.timestamp, self.balance))
            
            # If we have a signal and no position, enter trade
            if signal and not self.position:
                self.position = {
                    'side': signal['signal'],
                    'entry_price': signal['entry_price'],
                    'stop_price': signal['stop_price'],
                    'target_price': signal['target_price'],
                    'entry_time': signal['timestamp'],
                    'zone': signal['zone']
                }
                
                self.logger.info(
                    f"Opened {signal['signal'].upper()} - Entry: {signal['entry_price']:.2f}, "
                    f"Stop: {signal['stop_price']:.2f}, Target: {signal['target_price']:.2f}, "
                    f"Risk: {signal['risk_ticks']:.1f} ticks"
                )
        
        # Close any remaining position at last candle
        if self.position:
            last_candle = candles[-1]
            self.position['stop_price'] = last_candle.close  # Force close at current price
            self.position['target_price'] = last_candle.close
            self.check_position_exit(last_candle)
        
        # Generate results
        return self._generate_results(candles[0].timestamp, candles[-1].timestamp)
    
    def _generate_results(self, start_time: datetime, end_time: datetime) -> Dict[str, Any]:
        """Generate backtest results summary"""
        
        if not self.trades:
            return {
                'start_time': start_time,
                'end_time': end_time,
                'total_trades': 0,
                'winning_trades': 0,
                'losing_trades': 0,
                'win_rate': 0,
                'total_pnl': 0,
                'average_win': 0,
                'average_loss': 0,
                'average_trade': 0,
                'profit_factor': 0,
                'max_drawdown': 0,
                'final_balance': self.balance,
                'return_pct': 0,
                'average_duration_minutes': 0,
                'strategy_stats': self.strategy.get_statistics(),
                'trades': []
            }
        
        # Calculate statistics
        winning_trades = [t for t in self.trades if t.pnl > 0]
        losing_trades = [t for t in self.trades if t.pnl <= 0]
        
        total_trades = len(self.trades)
        win_rate = len(winning_trades) / total_trades * 100 if total_trades > 0 else 0
        
        total_pnl = sum(t.pnl * self.contracts for t in self.trades)
        total_pnl_after_commission = total_pnl - (total_trades * self.commission_per_contract)
        
        average_win = sum(t.pnl for t in winning_trades) / len(winning_trades) if winning_trades else 0
        average_loss = sum(t.pnl for t in losing_trades) / len(losing_trades) if losing_trades else 0
        
        # Calculate max drawdown
        peak = self.initial_balance
        max_dd = 0
        for _, equity in self.equity_curve:
            if equity > peak:
                peak = equity
            dd = (peak - equity) / peak * 100 if peak > 0 else 0
            if dd > max_dd:
                max_dd = dd
        
        # Calculate average trade duration
        avg_duration = sum(t.duration for t in self.trades) / len(self.trades) if self.trades else 0
        
        return {
            'start_time': start_time,
            'end_time': end_time,
            'total_trades': total_trades,
            'winning_trades': len(winning_trades),
            'losing_trades': len(losing_trades),
            'win_rate': win_rate,
            'total_pnl': total_pnl_after_commission,
            'average_win': average_win * self.contracts,
            'average_loss': average_loss * self.contracts,
            'average_trade': total_pnl_after_commission / total_trades if total_trades > 0 else 0,
            'profit_factor': abs(sum(t.pnl for t in winning_trades) / sum(t.pnl for t in losing_trades)) if losing_trades and sum(t.pnl for t in losing_trades) != 0 else 0,
            'max_drawdown': max_dd,
            'final_balance': self.balance,
            'return_pct': (self.balance - self.initial_balance) / self.initial_balance * 100,
            'average_duration_minutes': avg_duration,
            'strategy_stats': self.strategy.get_statistics(),
            'trades': self.trades
        }


def print_results(results: Dict[str, Any]):
    """Print backtest results in a formatted way"""
    print("\n" + "="*70)
    print(" SUPPLY/DEMAND REJECTION STRATEGY - BACKTEST RESULTS")
    print("="*70)
    
    print(f"\nPeriod: {results['start_time']} to {results['end_time']}")
    print(f"Duration: {(results['end_time'] - results['start_time']).days} days")
    
    print("\n--- PERFORMANCE METRICS ---")
    print(f"Total Trades: {results['total_trades']}")
    print(f"Winning Trades: {results['winning_trades']} ({results['win_rate']:.1f}%)")
    print(f"Losing Trades: {results['losing_trades']}")
    print(f"Win Rate: {results['win_rate']:.1f}%")
    
    print("\n--- P&L METRICS ---")
    print(f"Total P&L: ${results['total_pnl']:.2f}")
    print(f"Average Win: ${results['average_win']:.2f}")
    print(f"Average Loss: ${results['average_loss']:.2f}")
    print(f"Average Trade: ${results['average_trade']:.2f}")
    print(f"Profit Factor: {results['profit_factor']:.2f}")
    
    print("\n--- RISK METRICS ---")
    print(f"Max Drawdown: {results['max_drawdown']:.2f}%")
    print(f"Return: {results['return_pct']:.2f}%")
    print(f"Final Balance: ${results['final_balance']:.2f}")
    
    print("\n--- STRATEGY STATISTICS ---")
    stats = results['strategy_stats']
    print(f"Zones Created: {stats['zones_created']}")
    print(f"Zones Deleted: {stats['zones_deleted']}")
    print(f"Active Supply Zones: {stats['active_supply_zones']}")
    print(f"Active Demand Zones: {stats['active_demand_zones']}")
    print(f"Signals Generated: {stats['signals_generated']}")
    print(f"Candles Processed: {stats['candles_processed']}")
    
    print("\n--- TRADE DETAILS ---")
    print(f"Average Trade Duration: {results['average_duration_minutes']:.1f} minutes")
    
    # Show first 10 trades
    if results['trades']:
        print("\nFirst 10 Trades:")
        print(f"{'Time':<20} {'Side':<6} {'Entry':<8} {'Exit':<8} {'P&L':<10} {'Reason':<12}")
        print("-" * 70)
        for trade in results['trades'][:10]:
            print(
                f"{trade.entry_time.strftime('%Y-%m-%d %H:%M'):<20} "
                f"{trade.side.upper():<6} "
                f"{trade.entry_price:<8.2f} "
                f"{trade.exit_price:<8.2f} "
                f"${trade.pnl:<9.2f} "
                f"{trade.exit_reason:<12}"
            )
        if len(results['trades']) > 10:
            print(f"... and {len(results['trades']) - 10} more trades")
    
    print("\n" + "="*70)


def parse_arguments():
    """Parse command-line arguments"""
    parser = argparse.ArgumentParser(
        description='Supply/Demand Rejection Strategy - Backtesting',
        formatter_class=argparse.RawDescriptionHelpFormatter
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
        '--data-path',
        type=str,
        help='Path to historical data directory'
    )
    
    parser.add_argument(
        '--contracts',
        type=int,
        default=1,
        help='Number of contracts to trade (default: 1)'
    )
    
    parser.add_argument(
        '--initial-balance',
        type=float,
        default=50000.0,
        help='Initial account balance (default: 50000)'
    )
    
    parser.add_argument(
        '--log-level',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
        default='INFO',
        help='Logging level (default: INFO)'
    )
    
    return parser.parse_args()


def main():
    """Main entry point"""
    args = parse_arguments()
    
    # Setup logging
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger('supply_demand_backtest')
    
    # Determine date range
    if args.days:
        end_date = datetime.now(pytz.UTC)
        start_date = end_date - timedelta(days=args.days)
    elif args.start and args.end:
        start_date = datetime.strptime(args.start, '%Y-%m-%d')
        end_date = datetime.strptime(args.end, '%Y-%m-%d')
        start_date = pytz.UTC.localize(start_date)
        end_date = pytz.UTC.localize(end_date)
    else:
        # Default to last 30 days
        end_date = datetime.now(pytz.UTC)
        start_date = end_date - timedelta(days=30)
    
    logger.info(f"Backtesting {args.symbol} from {start_date} to {end_date}")
    
    # Create backtest runner
    runner = BacktestRunner(
        symbol=args.symbol,
        initial_balance=args.initial_balance,
        contracts=args.contracts,
        logger=logger
    )
    
    # Run backtest
    try:
        results = runner.run_backtest(
            start_date=start_date,
            end_date=end_date,
            data_path=args.data_path
        )
        
        # Print results
        print_results(results)
        
    except Exception as e:
        logger.error(f"Backtest failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
