"""
Clean backtest reporter that formats output similar to live trading
Shows trades in a clean, compact format with key metrics
"""

from datetime import datetime
from typing import List, Dict, Any, Optional
import sys


class BacktestReporter:
    """Handles clean formatting of backtest output"""
    
    def __init__(self, starting_balance: float = 50000.0):
        self.starting_balance = starting_balance
        self.trades: List[Dict[str, Any]] = []
        self.daily_pnl: Dict[str, float] = {}
        self.total_bars = 0
        self.signals_count = 0
        self.signals_approved = 0
        self.signals_rejected = 0
        self.trades_count = 0
        self.active_position = None
        
    def print_header(self, start_date: str, end_date: str, symbol: str):
        """Print clean backtest header"""
        print("\n" + "="*100)
        print(f"BACKTEST: {symbol} | {start_date} to {end_date}")
        print(f"Starting Balance: ${self.starting_balance:,.2f}")
        print(f"Daily Loss Limit: $1,000.00")
        print("="*100 + "\n")
        
    def update_progress(self, bars_processed: int, total_bars: int):
        """Update processing progress"""
        self.total_bars = total_bars
        if bars_processed % 1000 == 0 or bars_processed == total_bars:
            # Show progress bar
            progress = bars_processed / total_bars * 100
            print(f"\rProcessing {bars_processed:,}/{total_bars:,} bars... ({progress:.1f}%)", end='', flush=True)
    
    def record_signal(self, approved: bool):
        """Record a signal from RL (approved or rejected)"""
        self.signals_count += 1
        if approved:
            self.signals_approved += 1
        else:
            self.signals_rejected += 1
            
    def record_trade(self, trade_data: Dict[str, Any]):
        """Record a completed trade"""
        self.trades.append(trade_data)
        self.trades_count += 1
        
        # Update daily P&L
        trade_date = trade_data['exit_time'].strftime('%Y-%m-%d')
        if trade_date not in self.daily_pnl:
            self.daily_pnl[trade_date] = 0.0
        self.daily_pnl[trade_date] += trade_data['pnl']
        
        # Print trade in clean format
        self._print_trade(trade_data)
        
    def _print_trade(self, trade: Dict[str, Any]):
        """Print single trade in clean format"""
        # Format: [OK] WIN: LONG 3x | Tue 09/02 05:05 | Entry: $6522.28 > Exit: $6523.53 | P&L: $218.25 | stop_loss | 89min | Conf: 100%
        
        side = trade['side'].upper()
        quantity = trade.get('quantity', 3)
        
        # Date/time
        exit_time = trade['exit_time']
        date_str = exit_time.strftime('%a %m/%d %H:%M')
        
        # Entry/Exit
        entry_price = trade['entry_price']
        exit_price = trade['exit_price']
        
        # P&L
        pnl = trade['pnl']
        pnl_str = f"${pnl:+,.2f}"
        
        # Exit reason
        exit_reason = trade['exit_reason'].replace('_', ' ')
        
        # Duration
        duration_min = int(trade.get('duration_minutes', 0))
        duration_str = f"{duration_min}min"
        
        # Confidence
        confidence = trade.get('confidence', 100)
        conf_str = f"{int(confidence)}%"
        
        # Win/Loss indicator
        status = "WIN" if pnl > 0 else "LOSS" if pnl < 0 else "FLAT"
        
        # Print trade line
        print(f"[OK] {status}: {side} {quantity}x | {date_str} | Entry: ${entry_price:.2f} > Exit: ${exit_price:.2f} | P&L: {pnl_str} | {exit_reason} | {duration_str} | Conf: {conf_str}")
        
    def print_summary(self):
        """Print final backtest summary"""
        print("\n" + "="*100)
        
        if len(self.trades) == 0:
            print("No trades executed")
            print(f"Final Balance: ${self.starting_balance:,.2f}")
            print("="*100 + "\n")
            return
            
        # Calculate metrics
        total_pnl = sum(t['pnl'] for t in self.trades)
        wins = [t for t in self.trades if t['pnl'] > 0]
        losses = [t for t in self.trades if t['pnl'] < 0]
        
        win_rate = len(wins) / len(self.trades) * 100 if self.trades else 0
        avg_win = sum(t['pnl'] for t in wins) / len(wins) if wins else 0
        avg_loss = sum(t['pnl'] for t in losses) / len(losses) if losses else 0
        
        total_win = sum(t['pnl'] for t in wins)
        total_loss = abs(sum(t['pnl'] for t in losses))
        profit_factor = total_win / total_loss if total_loss > 0 else 0
        
        final_balance = self.starting_balance + total_pnl
        return_pct = (total_pnl / self.starting_balance) * 100
        
        # Print summary
        print(f"BACKTEST SUMMARY")
        print(f"-" * 100)
        print(f"Starting Balance: ${self.starting_balance:,.2f}")
        print(f"Final Balance:    ${final_balance:,.2f}")
        print(f"Total P&L:        ${total_pnl:+,.2f} ({return_pct:+.2f}%)")
        print(f"-" * 100)
        print(f"Total Trades:     {len(self.trades)}")
        print(f"Wins:             {len(wins)} ({len(wins)/len(self.trades)*100:.1f}%)")
        print(f"Losses:           {len(losses)} ({len(losses)/len(self.trades)*100:.1f}%)")
        print(f"Win Rate:         {win_rate:.1f}%")
        print(f"Average Win:      ${avg_win:,.2f}")
        print(f"Average Loss:     ${avg_loss:,.2f}")
        print(f"Profit Factor:    {profit_factor:.2f}")
        print(f"-" * 100)
        print(f"Bars Processed:   {self.total_bars:,}")
        print(f"RL Signals:       {self.signals_count} total")
        print(f"  Approved:       {self.signals_approved} ({self.signals_approved/self.signals_count*100 if self.signals_count > 0 else 0:.1f}%)")
        print(f"  Rejected:       {self.signals_rejected} ({self.signals_rejected/self.signals_count*100 if self.signals_count > 0 else 0:.1f}%)")
        print("="*100 + "\n")


# Global reporter instance
_reporter: Optional[BacktestReporter] = None


def get_reporter() -> BacktestReporter:
    """Get the global backtest reporter instance"""
    global _reporter
    if _reporter is None:
        _reporter = BacktestReporter()
    return _reporter


def reset_reporter(starting_balance: float = 50000.0):
    """Reset the global reporter with new starting balance"""
    global _reporter
    _reporter = BacktestReporter(starting_balance)
    return _reporter
