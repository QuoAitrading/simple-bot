#!/usr/bin/env python3
"""Quick test to verify backtest integration works"""

import os
import sys
from datetime import datetime
import pytz

# Set backtest mode BEFORE importing
os.environ['BOT_BACKTEST_MODE'] = 'true'

from config import load_config
from backtesting import BacktestConfig, BacktestEngine
from vwap_bounce_bot import initialize_state, on_tick, check_for_signals, check_exit_conditions, check_daily_reset, state

# Load config
bot_config = load_config(backtest_mode=True)
bot_config_dict = bot_config.to_dict()
symbol = bot_config_dict['instrument']

# Setup backtest
tz = pytz.timezone(bot_config.timezone)
end_date = datetime(2025, 10, 29, tzinfo=tz)
start_date = datetime(2025, 10, 1, tzinfo=tz)

backtest_config = BacktestConfig(
    start_date=start_date,
    end_date=end_date,
    initial_equity=50000.0,
    symbols=[symbol],
    data_path='./historical_data',
    use_tick_data=False
)

# Create engine
engine = BacktestEngine(backtest_config, bot_config_dict)

# Get ET timezone
et = pytz.timezone('US/Eastern')

def vwap_strategy(bars_1min, bars_15min):
    """Test strategy"""
    # Clear state
    if symbol in state:
        state.pop(symbol)
    initialize_state(symbol)
    
    print(f"Processing {len(bars_1min)} bars...")
    
    for i, bar in enumerate(bars_1min):
        timestamp = bar['timestamp']
        price = bar['close']
        volume = bar['volume']
        timestamp_ms = int(timestamp.timestamp() * 1000)
        
        # Reset daily counters
        timestamp_et = timestamp.astimezone(et)
        check_daily_reset(symbol, timestamp_et)
        
        # Process
        on_tick(symbol, price, volume, timestamp_ms)
        check_for_signals(symbol)
        check_exit_conditions(symbol)
        
        # Debug output every 1000 bars
        if i > 0 and i % 1000 == 0:
            print(f"  Processed {i} bars, daily trades: {state[symbol]['daily_trade_count']}")

# Run backtest
print("Running test backtest...")
results = engine.run_with_strategy(vwap_strategy)

# Check bot state after run
print(f"\nBot state after backtest:")
if symbol in state:
    print(f"  Daily trade count: {state[symbol]['daily_trade_count']}")
    print(f"  Daily P&L: ${state[symbol]['daily_pnl']:.2f}")
    print(f"  Session trades: {len(state[symbol]['session_stats']['trades'])}")

print("\nRESULTS:")
print(f"Total Trades: {results['total_trades']}")
print(f"Total P&L: ${results['total_pnl']:+,.2f}")
print(f"Win Rate: {results['win_rate']:.2f}%")
print(f"Sharpe Ratio: {results['sharpe_ratio']:.4f}")
