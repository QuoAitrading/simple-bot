#!/usr/bin/env python3
"""
Parameter Optimization Script for VWAP Bounce Bot
Systematically tests different parameter combinations to find optimal backtest results
Target: 75% win rate, $9-10K profit, ~16 trades over 90 days (or scaled for available data)
"""

import os
import sys
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Tuple
import pytz

# Import bot modules
from config import load_config, BotConfiguration
from backtesting import BacktestConfig, BacktestEngine, ReportGenerator
from vwap_bounce_bot import initialize_state, on_tick, check_for_signals, check_exit_conditions, check_daily_reset, state


def run_single_backtest(
    rsi_oversold: int,
    rsi_overbought: int,
    vwap_entry_dev: float,
    risk_per_trade: float,
    max_contracts: int,
    days: int = 7,
    initial_equity: float = 50000.0
) -> Dict[str, Any]:
    """
    Run a single backtest with specified parameters.
    
    Returns:
        Dictionary with backtest results
    """
    # Create configuration with test parameters
    bot_config = BotConfiguration()
    bot_config.backtest_mode = True
    bot_config.instrument = "ES"
    bot_config.rsi_oversold = rsi_oversold
    bot_config.rsi_overbought = rsi_overbought
    bot_config.vwap_std_dev_2 = vwap_entry_dev
    bot_config.risk_per_trade = risk_per_trade
    bot_config.max_contracts = max_contracts
    
    # Set to high trade limit for testing
    bot_config.max_trades_per_day = 100
    
    # Date range
    tz = pytz.timezone(bot_config.timezone)
    end_date = datetime.now(tz)
    start_date = end_date - timedelta(days=days)
    
    # Create backtest configuration
    backtest_config = BacktestConfig(
        start_date=start_date,
        end_date=end_date,
        initial_equity=initial_equity,
        symbols=["ES"],
        data_path="./historical_data",
        use_tick_data=False
    )
    
    # Create backtest engine
    bot_config_dict = bot_config.to_dict()
    engine = BacktestEngine(backtest_config, bot_config_dict)
    
    # Initialize bot state
    symbol = "ES"
    initialize_state(symbol)
    
    # Get ET timezone for daily reset
    et = pytz.timezone('US/Eastern')
    
    def vwap_strategy_backtest(bars_1min: List[Dict[str, Any]], bars_15min: List[Dict[str, Any]]) -> None:
        """Run VWAP strategy on historical data"""
        for bar in bars_1min:
            timestamp = bar['timestamp']
            price = bar['close']
            volume = bar['volume']
            timestamp_ms = int(timestamp.timestamp() * 1000)
            
            # Check for daily reset
            timestamp_et = timestamp.astimezone(et)
            check_daily_reset(symbol, timestamp_et)
            
            # Process tick
            on_tick(symbol, price, volume, timestamp_ms)
            
            # Check for signals
            check_for_signals(symbol)
            
            # Check for exits
            check_exit_conditions(symbol)
            
            # Update backtest engine with position
            if symbol in state and 'position' in state[symbol]:
                pos = state[symbol]['position']
                
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
                    exit_price = price
                    exit_time = timestamp
                    exit_reason = 'bot_exit'
                    engine._close_position(exit_time, exit_price, exit_reason)
    
    try:
        results = engine.run_with_strategy(vwap_strategy_backtest)
        return results
    except Exception as e:
        logging.error(f"Backtest failed: {e}")
        return {
            'total_trades': 0,
            'total_pnl': 0,
            'win_rate': 0,
            'error': str(e)
        }


def test_parameter_grid():
    """
    Test a grid of parameters systematically.
    """
    print("=" * 80)
    print("PARAMETER OPTIMIZATION FOR VWAP BOUNCE BOT")
    print("=" * 80)
    print(f"Target: 75% win rate, $9-10K profit, ~16 trades")
    print(f"Note: We have 7 days of data, so targets will be scaled accordingly")
    print(f"Expected scaled targets: ~2-3 trades, ~$800-1200 profit for 7 days")
    print("=" * 80)
    print()
    
    # Parameter ranges to test
    rsi_pairs = [
        (25, 75),
        (26, 74),
        (27, 73),
        (28, 72),  # Current baseline
        (29, 71),
        (30, 70)
    ]
    
    vwap_entry_devs = [1.5, 1.8, 2.0, 2.2, 2.5]  # Current baseline is 2.0
    risk_per_trades = [0.008, 0.01, 0.012, 0.015]  # Current baseline is 0.01 (1%)
    max_contracts_list = [2, 3, 4]  # Current baseline is 2
    
    results_log = []
    best_result = None
    best_score = -999999
    
    test_count = 0
    total_tests = len(rsi_pairs) * len(vwap_entry_devs) * len(risk_per_trades) * len(max_contracts_list)
    
    print(f"Total parameter combinations to test: {total_tests}")
    print()
    
    # Test each combination
    for rsi_os, rsi_ob in rsi_pairs:
        for vwap_dev in vwap_entry_devs:
            for risk in risk_per_trades:
                for max_contracts in max_contracts_list:
                    test_count += 1
                    
                    print(f"\n[{test_count}/{total_tests}] Testing:")
                    print(f"  RSI: {rsi_os}/{rsi_ob}, VWAP Entry: {vwap_dev}σ, Risk: {risk*100:.1f}%, Max Contracts: {max_contracts}")
                    
                    result = run_single_backtest(
                        rsi_oversold=rsi_os,
                        rsi_overbought=rsi_ob,
                        vwap_entry_dev=vwap_dev,
                        risk_per_trade=risk,
                        max_contracts=max_contracts,
                        days=7,
                        initial_equity=50000.0
                    )
                    
                    trades = result.get('total_trades', 0)
                    win_rate = result.get('win_rate', 0)
                    pnl = result.get('total_pnl', 0)
                    sharpe = result.get('sharpe_ratio', 0)
                    
                    print(f"  Results: {trades} trades, {win_rate:.1f}% win rate, ${pnl:+.2f} P&L, Sharpe: {sharpe:.2f}")
                    
                    # Log result
                    result_entry = {
                        'rsi_oversold': rsi_os,
                        'rsi_overbought': rsi_ob,
                        'vwap_entry_dev': vwap_dev,
                        'risk_per_trade': risk,
                        'max_contracts': max_contracts,
                        'total_trades': trades,
                        'win_rate': win_rate,
                        'total_pnl': pnl,
                        'sharpe_ratio': sharpe
                    }
                    results_log.append(result_entry)
                    
                    # Scoring function: prioritize win rate > 70%, then P&L, then Sharpe
                    # For 7 days, we expect ~1/13th of 90-day targets
                    # Target: 70-80% win rate, ~$800+ profit, 2-3+ trades
                    score = 0
                    if trades >= 2:  # Need minimum trades
                        if win_rate >= 70:
                            score += 10000  # High priority for good win rate
                            score += pnl  # Then optimize for profit
                            score += sharpe * 100  # Bonus for good Sharpe
                        else:
                            score += win_rate * 10  # Lower score for lower win rate
                            score += pnl * 0.5
                    
                    if score > best_score:
                        best_score = score
                        best_result = result_entry
                        print(f"  *** NEW BEST RESULT (score: {score:.0f}) ***")
    
    # Print summary
    print("\n" + "=" * 80)
    print("OPTIMIZATION COMPLETE")
    print("=" * 80)
    
    if best_result:
        print("\nBEST CONFIGURATION FOUND:")
        print(f"  RSI: {best_result['rsi_oversold']}/{best_result['rsi_overbought']}")
        print(f"  VWAP Entry: {best_result['vwap_entry_dev']}σ")
        print(f"  Risk per Trade: {best_result['risk_per_trade']*100:.1f}%")
        print(f"  Max Contracts: {best_result['max_contracts']}")
        print(f"\nRESULTS:")
        print(f"  Total Trades: {best_result['total_trades']}")
        print(f"  Win Rate: {best_result['win_rate']:.1f}%")
        print(f"  Total P&L: ${best_result['total_pnl']:+.2f}")
        print(f"  Sharpe Ratio: {best_result['sharpe_ratio']:.2f}")
        print(f"\nNote: These results are for 7 days. For 90 days (13x), expect:")
        print(f"  ~{best_result['total_trades'] * 13:.0f} trades")
        print(f"  ${best_result['total_pnl'] * 13:+.2f} profit")
    else:
        print("\nNo valid results found.")
    
    # Save all results to JSON
    output_file = "optimization_results.json"
    with open(output_file, 'w') as f:
        json.dump({
            'test_date': datetime.now().isoformat(),
            'total_tests': total_tests,
            'best_result': best_result,
            'all_results': results_log
        }, f, indent=2)
    
    print(f"\nAll results saved to: {output_file}")
    
    return best_result


if __name__ == "__main__":
    # Configure logging to be less verbose
    logging.basicConfig(
        level=logging.WARNING,
        format='%(levelname)s: %(message)s'
    )
    
    best_config = test_parameter_grid()
    
    if best_config:
        print("\n" + "=" * 80)
        print("RECOMMENDED CONFIG.PY UPDATES:")
        print("=" * 80)
        print(f"Line 22: risk_per_trade: float = {best_config['risk_per_trade']}")
        print(f"Line 23: max_contracts: int = {best_config['max_contracts']}")
        print(f"Line 34: vwap_std_dev_2: float = {best_config['vwap_entry_dev']}")
        print(f"Line 50: rsi_oversold: int = {best_config['rsi_oversold']}")
        print(f"Line 51: rsi_overbought: int = {best_config['rsi_overbought']}")
        print("=" * 80)
