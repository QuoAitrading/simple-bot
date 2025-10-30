#!/usr/bin/env python3
"""
COMPREHENSIVE parameter optimization - Testing ALL parameters including:
- Entry parameters (VWAP, RSI)
- Position sizing
- Exit management (breakeven, trailing stops, partial exits)
- Time-based parameters

This tests the COMPLETE parameter space that was missed before.
"""

import os
import sys
from datetime import datetime
import pytz
import logging
import json
from itertools import product

# Set backtest mode BEFORE importing
os.environ['BOT_BACKTEST_MODE'] = 'true'

from config import load_config
from backtesting import BacktestConfig, BacktestEngine
from vwap_bounce_bot import initialize_state, on_tick, check_for_signals, check_exit_conditions, check_daily_reset, state

logging.basicConfig(level=logging.ERROR, format='%(levelname)s: %(message)s')

def run_backtest_with_params(param_dict, symbol, start_date, end_date):
    """Run a single backtest with given parameters"""
    
    bot_config = load_config(backtest_mode=True)
    for key, value in param_dict.items():
        setattr(bot_config, key, value)
    bot_config_dict = bot_config.to_dict()
    
    backtest_config = BacktestConfig(
        start_date=start_date,
        end_date=end_date,
        initial_equity=50000.0,
        symbols=[symbol],
        data_path='./historical_data',
        use_tick_data=False,
        slippage_ticks=bot_config.slippage_ticks,
        commission_per_contract=bot_config.commission_per_contract
    )
    
    engine = BacktestEngine(backtest_config, bot_config_dict)
    et = pytz.timezone('US/Eastern')
    last_position_active = [False]
    
    def vwap_strategy(bars_1min, bars_15min):
        if symbol in state:
            state.pop(symbol)
        initialize_state(symbol)
        last_position_active[0] = False
        
        for bar in bars_1min:
            timestamp = bar['timestamp']
            price = bar['close']
            volume = bar['volume']
            timestamp_ms = int(timestamp.timestamp() * 1000)
            
            timestamp_et = timestamp.astimezone(et)
            check_daily_reset(symbol, timestamp_et)
            
            on_tick(symbol, price, volume, timestamp_ms)
            check_for_signals(symbol)
            check_exit_conditions(symbol)
            
            if symbol in state and 'position' in state[symbol]:
                pos = state[symbol]['position']
                is_active = pos.get('active', False)
                
                if is_active and not last_position_active[0]:
                    engine.current_position = {
                        'symbol': symbol,
                        'side': pos['side'],
                        'quantity': pos.get('quantity', 1),
                        'entry_price': pos['entry_price'],
                        'entry_time': pos.get('entry_time', timestamp),
                        'stop_price': pos.get('stop_price'),
                        'target_price': pos.get('target_price')
                    }
                    last_position_active[0] = True
                
                elif not is_active and last_position_active[0]:
                    if engine.current_position is not None:
                        engine._close_position(timestamp, price, 'bot_exit')
                    last_position_active[0] = False
    
    try:
        results = engine.run_with_strategy(vwap_strategy)
        return results
    except Exception as e:
        return None


def main():
    print("="*80)
    print("COMPREHENSIVE VWAP BOT OPTIMIZATION - ALL PARAMETERS")
    print("Testing Entry, Exit Management, Partial Exits, and Advanced Features")
    print("="*80)
    print()
    
    symbol = 'ES'
    tz = pytz.timezone('America/New_York')
    end_date = datetime(2025, 10, 29, tzinfo=tz)
    start_date = datetime(2025, 9, 1, tzinfo=tz)
    
    print(f"Testing Period: {start_date.date()} to {end_date.date()}")
    print()
    
    # COMPREHENSIVE parameter grid - ALL parameters including exit management
    param_grid = {
        # Entry Parameters (proven best range)
        'vwap_std_dev_2': [1.5, 2.0],
        'rsi_oversold': [20, 25],
        'rsi_overbought': [70, 75],
        
        # Position Sizing
        'risk_per_trade': [0.01, 0.012, 0.015],
        'max_contracts': [1, 2, 3],
        
        # Exit Management - THESE WERE NEVER TESTED!
        'breakeven_enabled': [True, False],
        'trailing_stop_enabled': [True, False],
        'partial_exits_enabled': [True, False],
        
        # Risk/Reward
        'risk_reward_ratio': [2.0, 2.5, 3.0],
    }
    
    param_names = list(param_grid.keys())
    param_values = [param_grid[name] for name in param_names]
    combinations = list(product(*param_values))
    
    total = len(combinations)
    print(f"Testing {total} COMPREHENSIVE combinations...")
    print("Including exit management features that were NEVER tested before!")
    print()
    
    results = []
    best_pnl = -999999
    best_winrate = 0
    best_result = None
    
    for i, combo in enumerate(combinations, 1):
        params = dict(zip(param_names, combo))
        
        print(f"[{i}/{total}] vwap={params['vwap_std_dev_2']}, rsi={params['rsi_oversold']}/{params['rsi_overbought']}, "
              f"risk={params['risk_per_trade']}, contracts={params['max_contracts']}, "
              f"breakeven={params['breakeven_enabled']}, trailing={params['trailing_stop_enabled']}, "
              f"partials={params['partial_exits_enabled']}, r:r={params['risk_reward_ratio']}")
        
        result = run_backtest_with_params(params, symbol, start_date, end_date)
        
        if result:
            results.append({'params': params, 'metrics': result})
            print(f"  -> Trades: {result['total_trades']}, P&L: ${result['total_pnl']:+,.2f}, "
                  f"Win%: {result['win_rate']:.1f}%, PF: {result['profit_factor']:.2f}")
            
            # Track best results
            if result['total_pnl'] > best_pnl:
                best_pnl = result['total_pnl']
                best_result = {'params': params, 'metrics': result}
            
            if result['win_rate'] > best_winrate:
                best_winrate = result['win_rate']
        else:
            print(f"  -> FAILED")
        print()
    
    print("="*80)
    print("COMPREHENSIVE OPTIMIZATION COMPLETE!")
    print("="*80)
    print()
    
    # Sort results
    results_by_pnl = sorted(results, key=lambda x: x['metrics']['total_pnl'], reverse=True)
    results_by_winrate = sorted(results, key=lambda x: x['metrics']['win_rate'], reverse=True)
    results_by_combo = sorted(results, key=lambda x: (x['metrics']['total_pnl'] + x['metrics']['win_rate'] * 10), reverse=True)
    
    # Show top results
    print("TOP 10 BY PROFIT:")
    print("-"*80)
    for i, r in enumerate(results_by_pnl[:10], 1):
        m, p = r['metrics'], r['params']
        print(f"#{i}: ${m['total_pnl']:+,.2f} P&L, {m['win_rate']:.1f}% Win, {m['total_trades']} Trades")
        print(f"    vwap={p['vwap_std_dev_2']}, rsi={p['rsi_oversold']}/{p['rsi_overbought']}, "
              f"risk={p['risk_per_trade']}, contracts={p['max_contracts']}")
        print(f"    breakeven={p['breakeven_enabled']}, trailing={p['trailing_stop_enabled']}, "
              f"partials={p['partial_exits_enabled']}, r:r={p['risk_reward_ratio']}")
        print(f"    Profit Factor: {m['profit_factor']:.2f}, Sharpe: {m['sharpe_ratio']:.3f}\n")
    
    print("\nTOP 10 BY WIN RATE:")
    print("-"*80)
    for i, r in enumerate(results_by_winrate[:10], 1):
        m, p = r['metrics'], r['params']
        print(f"#{i}: {m['win_rate']:.1f}% Win, ${m['total_pnl']:+,.2f} P&L, {m['total_trades']} Trades")
        print(f"    vwap={p['vwap_std_dev_2']}, rsi={p['rsi_oversold']}/{p['rsi_overbought']}, "
              f"risk={p['risk_per_trade']}, contracts={p['max_contracts']}")
        print(f"    breakeven={p['breakeven_enabled']}, trailing={p['trailing_stop_enabled']}, "
              f"partials={p['partial_exits_enabled']}, r:r={p['risk_reward_ratio']}")
        print(f"    Profit Factor: {m['profit_factor']:.2f}, Sharpe: {m['sharpe_ratio']:.3f}\n")
    
    # Save results
    with open('optimization_comprehensive.json', 'w') as f:
        json.dump({
            'test_period': {'start': start_date.isoformat(), 'end': end_date.isoformat()},
            'total_combinations': total,
            'successful_runs': len(results),
            'best_by_pnl': best_result,
            'top_10_by_pnl': results_by_pnl[:10],
            'top_10_by_winrate': results_by_winrate[:10],
            'top_10_combined': results_by_combo[:10],
            'all_results': results
        }, f, indent=2, default=str)
    
    print("\n" + "="*80)
    print("BEST CONFIGURATION FOUND:")
    print("="*80)
    if best_result:
        print("\n🏆 HIGHEST PROFIT CONFIGURATION:")
        for k, v in best_result['params'].items():
            print(f"  {k}: {v}")
        print(f"\nPERFORMANCE:")
        print(f"  Total P&L: ${best_result['metrics']['total_pnl']:+,.2f}")
        print(f"  Win Rate: {best_result['metrics']['win_rate']:.1f}%")
        print(f"  Total Trades: {best_result['metrics']['total_trades']}")
        print(f"  Profit Factor: {best_result['metrics']['profit_factor']:.2f}")
        print(f"  Sharpe Ratio: {best_result['metrics']['sharpe_ratio']:.3f}")
        print(f"  Max Drawdown: ${best_result['metrics']['max_drawdown_dollars']:,.2f} ({best_result['metrics']['max_drawdown_percent']:.2f}%)")
    
    print("\nResults saved to: optimization_comprehensive.json")
    print("="*80)


if __name__ == '__main__':
    main()
