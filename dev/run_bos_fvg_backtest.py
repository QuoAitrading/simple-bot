#!/usr/bin/env python3
"""
BOS + FVG Strategy Backtest Runner

Backtests the Break of Structure + Fair Value Gap scalping strategy
on historical ES 1-minute data.

Usage:
    python dev/run_bos_fvg_backtest.py --days 30 --symbol ES
    python dev/run_bos_fvg_backtest.py --start 2025-11-01 --end 2025-12-01
"""

import sys
import os

import pandas as pd
import logging
from datetime import datetime, timedelta
import pytz
import argparse
from typing import List, Dict, Optional

# Import directly from the file to avoid dependency issues
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from bos_fvg_bot import BOSFVGStrategy


# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('bos_fvg_backtest')


class BOSFVGBacktest:
    """Backtest runner for BOS + FVG strategy"""
    
    def __init__(
        self,
        strategy: BOSFVGStrategy,
        initial_balance: float = 50000.0,
        contracts: int = 1,
        commission_per_contract: float = 2.50
    ):
        self.strategy = strategy
        self.initial_balance = initial_balance
        self.balance = initial_balance
        self.contracts = contracts
        self.commission = commission_per_contract
        
        self.trades: List[Dict] = []
        self.current_position: Optional[Dict] = None
        self.equity_curve: List[Dict] = []
        
        self.max_balance = initial_balance
        self.max_drawdown = 0.0
    
    def run(self, data: pd.DataFrame) -> Dict:
        """Run backtest on historical data"""
        logger.info(f"Starting BOS+FVG backtest on {len(data)} candles")
        logger.info(f"Period: {data.index[0]} to {data.index[-1]}")
        
        for idx, row in data.iterrows():
            candle_data = {
                'timestamp': idx,
                'open': row['open'],
                'high': row['high'],
                'low': row['low'],
                'close': row['close'],
                'volume': row.get('volume', 0)
            }
            
            # Update open position
            if self.current_position:
                self._update_position(candle_data)
            
            # Get new signal
            signal = self.strategy.process_candle(candle_data)
            
            # Execute signal if no position
            if signal and not self.current_position:
                self._open_position(signal, candle_data)
            
            # Track equity
            self.equity_curve.append({
                'timestamp': idx,
                'balance': self.balance,
                'position': self.current_position['side'] if self.current_position else None
            })
            
            # Update max balance and drawdown
            if self.balance > self.max_balance:
                self.max_balance = self.balance
            current_dd = (self.max_balance - self.balance) / self.max_balance * 100
            if current_dd > self.max_drawdown:
                self.max_drawdown = current_dd
        
        return self._generate_report()
    
    def _open_position(self, signal: Dict, candle_data: Dict):
        """Open a new position"""
        self.current_position = {
            'side': signal['signal'],
            'entry': signal['entry'],
            'stop': signal['stop_loss'],
            'target': signal['take_profit'],
            'entry_time': candle_data['timestamp'],
            'reason': signal['reason'],
            'fvg_range': signal.get('fvg_range', 'N/A')
        }
        
        # Pay commission
        self.balance -= self.commission * self.contracts
        
        logger.info(f"Opened {signal['signal']} - Entry: {signal['entry']:.2f}, Stop: {signal['stop_loss']:.2f}, Target: {signal['take_profit']:.2f}")
    
    def _update_position(self, candle_data: Dict):
        """Update open position and check for exit"""
        if not self.current_position:
            return
        
        pos = self.current_position
        high = candle_data['high']
        low = candle_data['low']
        
        exit_price = None
        exit_reason = None
        
        # Check LONG position
        if pos['side'] == 'LONG':
            # Check stop loss
            if low <= pos['stop']:
                exit_price = pos['stop']
                exit_reason = 'stop_loss'
            # Check target
            elif high >= pos['target']:
                exit_price = pos['target']
                exit_reason = 'target'
        
        # Check SHORT position
        elif pos['side'] == 'SHORT':
            # Check stop loss
            if high >= pos['stop']:
                exit_price = pos['stop']
                exit_reason = 'stop_loss'
            # Check target
            elif low <= pos['target']:
                exit_price = pos['target']
                exit_reason = 'target'
        
        # Close position if exit triggered
        if exit_price:
            self._close_position(exit_price, exit_reason, candle_data['timestamp'])
    
    def _close_position(self, exit_price: float, exit_reason: str, exit_time: datetime):
        """Close the current position"""
        pos = self.current_position
        
        # Calculate P&L
        if pos['side'] == 'LONG':
            price_diff = exit_price - pos['entry']
        else:  # SHORT
            price_diff = pos['entry'] - exit_price
        
        ticks = price_diff / self.strategy.tick_size
        pnl = ticks * self.strategy.tick_value * self.contracts
        
        # Apply commission
        pnl -= self.commission * self.contracts
        self.balance += pnl
        
        # Calculate duration
        duration = (exit_time - pos['entry_time']).total_seconds() / 60
        
        # Record trade
        trade = {
            'entry_time': pos['entry_time'],
            'exit_time': exit_time,
            'side': pos['side'],
            'entry': pos['entry'],
            'exit': exit_price,
            'pnl': pnl,
            'ticks': ticks,
            'reason': exit_reason,
            'duration_minutes': duration,
            'fvg_range': pos.get('fvg_range', 'N/A')
        }
        self.trades.append(trade)
        
        logger.info(f"Closed {pos['side']} - Exit: {exit_reason}, P&L: ${pnl:.2f} ({ticks:.1f} ticks), Duration: {duration:.0f}m, Balance: ${self.balance:.2f}")
        
        self.current_position = None
    
    def _generate_report(self) -> Dict:
        """Generate backtest performance report"""
        if not self.trades:
            logger.warning("No trades executed during backtest")
            return {}
        
        df_trades = pd.DataFrame(self.trades)
        
        winning_trades = df_trades[df_trades['pnl'] > 0]
        losing_trades = df_trades[df_trades['pnl'] < 0]
        
        total_trades = len(df_trades)
        num_winners = len(winning_trades)
        num_losers = len(losing_trades)
        win_rate = (num_winners / total_trades * 100) if total_trades > 0 else 0
        
        total_pnl = df_trades['pnl'].sum()
        avg_win = winning_trades['pnl'].mean() if num_winners > 0 else 0
        avg_loss = losing_trades['pnl'].mean() if num_losers > 0 else 0
        avg_trade = df_trades['pnl'].mean()
        
        gross_profit = winning_trades['pnl'].sum() if num_winners > 0 else 0
        gross_loss = abs(losing_trades['pnl'].sum()) if num_losers > 0 else 0
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else 0
        
        total_return = ((self.balance - self.initial_balance) / self.initial_balance) * 100
        
        avg_duration = df_trades['duration_minutes'].mean()
        
        # Get strategy stats
        stats = self.strategy.get_statistics()
        
        report = {
            'total_trades': total_trades,
            'winning_trades': num_winners,
            'losing_trades': num_losers,
            'win_rate': win_rate,
            'total_pnl': total_pnl,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'avg_trade': avg_trade,
            'profit_factor': profit_factor,
            'max_drawdown': self.max_drawdown,
            'total_return': total_return,
            'final_balance': self.balance,
            'avg_duration': avg_duration,
            'fvgs_created': stats['fvgs_created'],
            'fvgs_filled': stats['fvgs_filled'],
            'bos_count': stats['bos_count'],
            'trades': df_trades.to_dict('records')
        }
        
        return report
    
    def print_report(self, report: Dict, start_date: datetime, end_date: datetime):
        """Print formatted backtest report"""
        print("\n" + "="*70)
        print(" BOS + FVG SCALPING STRATEGY - BACKTEST RESULTS")
        print("="*70)
        print()
        print(f"Period: {start_date} to {end_date}")
        days = (end_date - start_date).days
        print(f"Duration: {days} days")
        print()
        print("--- PERFORMANCE METRICS ---")
        print(f"Total Trades: {report['total_trades']}")
        print(f"Winning Trades: {report['winning_trades']} ({report['win_rate']:.1f}%)")
        print(f"Losing Trades: {report['losing_trades']}")
        print(f"Win Rate: {report['win_rate']:.1f}%")
        print()
        print("--- P&L METRICS ---")
        print(f"Total P&L: ${report['total_pnl']:.2f}")
        print(f"Average Win: ${report['avg_win']:.2f}")
        print(f"Average Loss: ${report['avg_loss']:.2f}")
        print(f"Average Trade: ${report['avg_trade']:.2f}")
        print(f"Profit Factor: {report['profit_factor']:.2f}")
        print()
        print("--- RISK METRICS ---")
        print(f"Max Drawdown: {report['max_drawdown']:.2f}%")
        print(f"Return: {report['total_return']:.2f}%")
        print(f"Final Balance: ${report['final_balance']:.2f}")
        print()
        print("--- STRATEGY STATISTICS ---")
        print(f"BOS Detected: {report['bos_count']}")
        print(f"FVGs Created: {report['fvgs_created']}")
        print(f"FVGs Filled (Traded): {report['fvgs_filled']}")
        print(f"Trades per Day: {report['total_trades']/days:.2f}")
        print()
        print("--- TRADE DETAILS ---")
        print(f"Average Trade Duration: {report['avg_duration']:.1f} minutes")
        print()
        print("First 10 Trades:")
        print(f"{'Time':<20} {'Side':<6} {'Entry':<8} {'Exit':<8} {'P&L':<12} {'Reason':<12}")
        print("-"*70)
        for trade in report['trades'][:10]:
            print(f"{str(trade['entry_time']):<20} {trade['side']:<6} {trade['entry']:<8.2f} "
                  f"{trade['exit']:<8.2f} ${trade['pnl']:<11.2f} {trade['reason']:<12}")
        if len(report['trades']) > 10:
            print(f"... and {len(report['trades']) - 10} more trades")
        print()
        print("="*70)


def load_data(symbol: str, start_date: datetime, end_date: datetime) -> pd.DataFrame:
    """Load historical data from CSV"""
    data_file = f'data/historical_data/{symbol}_1min.csv'
    
    if not os.path.exists(data_file):
        logger.error(f"Data file not found: {data_file}")
        sys.exit(1)
    
    logger.info(f"Loading data from {data_file}")
    df = pd.read_csv(data_file)
    df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)
    df.set_index('timestamp', inplace=True)
    
    # Filter date range
    df = df[(df.index >= start_date) & (df.index <= end_date)]
    
    logger.info(f"Loaded {len(df)} candles from {df.index[0]} to {df.index[-1]}")
    return df


def main():
    parser = argparse.ArgumentParser(description='BOS + FVG Strategy Backtest')
    parser.add_argument('--symbol', type=str, default='ES', help='Symbol to backtest')
    parser.add_argument('--days', type=int, help='Number of days to backtest (from most recent)')
    parser.add_argument('--start', type=str, help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end', type=str, help='End date (YYYY-MM-DD)')
    parser.add_argument('--contracts', type=int, default=1, help='Number of contracts')
    
    args = parser.parse_args()
    
    # Determine date range
    if args.start and args.end:
        start_date = datetime.strptime(args.start, '%Y-%m-%d').replace(tzinfo=pytz.UTC)
        end_date = datetime.strptime(args.end, '%Y-%m-%d').replace(tzinfo=pytz.UTC)
    elif args.days:
        end_date = datetime.now(pytz.UTC)
        start_date = end_date - timedelta(days=args.days)
    else:
        # Default: last 30 days
        end_date = datetime.now(pytz.UTC)
        start_date = end_date - timedelta(days=30)
    
    # Load data
    data = load_data(args.symbol, start_date, end_date)
    
    if data.empty:
        logger.error("No data available for the specified date range")
        sys.exit(1)
    
    # Initialize strategy
    strategy = BOSFVGStrategy(
        tick_size=0.25,
        tick_value=12.50,  # ES full contract
        swing_lookback=5,
        min_fvg_ticks=2,
        max_fvg_ticks=20,
        fvg_expiry_minutes=60,
        stop_loss_ticks=2,
        risk_reward_ratio=1.5,
        max_active_fvgs=10,
        logger=logger
    )
    
    # Run backtest
    backtest = BOSFVGBacktest(
        strategy=strategy,
        initial_balance=50000.0,
        contracts=args.contracts,
        commission_per_contract=2.50
    )
    
    report = backtest.run(data)
    
    if report:
        backtest.print_report(report, data.index[0], data.index[-1])


if __name__ == '__main__':
    main()
