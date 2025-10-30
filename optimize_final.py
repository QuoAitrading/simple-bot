#!/usr/bin/env python3
"""
Optimized approach - test the best base parameters with different scaling strategies
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
    print("OPTIMIZED PARAMETER SEARCH - Higher Profit & Win Rate Focus")
    print("="*80)
    print()
    
    symbol = 'ES'
    tz = pytz.timezone('America/New_York')
    end_date = datetime(2025, 10, 29, tzinfo=tz)
    start_date = datetime(2025, 9, 1, tzinfo=tz)
    
    print(f"Testing Period: {start_date.date()} to {end_date.date()}")
    print()
    
    # Start with the best baseline (1.5 VWAP, RSI 20/70) and explore variations
    param_grid = {
        'vwap_std_dev_2': [1.5, 2.0],  # Best performer + baseline
        'rsi_oversold': [15, 20],  # Even more extreme
        'rsi_overbought': [70, 75],
        'use_rsi_filter': [True, False],
        'risk_per_trade': [0.012, 0.015, 0.02],  # Scale up position size
        'max_contracts': [2, 3],  # Allow more contracts
        'risk_reward_ratio': [2.0, 2.5, 3.0],  # Better targets
    }
    
    param_names = list(param_grid.keys())
    param_values = [param_grid[name] for name in param_names]
    combinations = list(product(*param_values))
    
    total = len(combinations)
    print(f"Testing {total} combinations...")
    print()
    
    results = []
    
    for i, combo in enumerate(combinations, 1):
        params = dict(zip(param_names, combo))
        
        print(f"[{i}/{total}] vwap={params['vwap_std_dev_2']}, rsi={params['rsi_oversold']}/{params['rsi_overbought']}, "
              f"risk={params['risk_per_trade']}, contracts={params['max_contracts']}, r:r={params['risk_reward_ratio']}")
        
        result = run_backtest_with_params(params, symbol, start_date, end_date)
        
        if result:
            results.append({'params': params, 'metrics': result})
            print(f"  -> Trades: {result['total_trades']}, P&L: ${result['total_pnl']:+,.2f}, "
                  f"Win%: {result['win_rate']:.1f}%, Sharpe: {result['sharpe_ratio']:.3f}")
        else:
            print(f"  -> FAILED")
        print()
    
    print("="*80)
    print("OPTIMIZATION COMPLETE!")
    print("="*80)
    print()
    
    # Sort by different criteria
    results_by_pnl = sorted(results, key=lambda x: x['metrics']['total_pnl'], reverse=True)
    results_by_winrate = sorted(results, key=lambda x: x['metrics']['win_rate'], reverse=True)
    results_by_combo = sorted(results, key=lambda x: (x['metrics']['total_pnl'] + x['metrics']['win_rate'] * 10), reverse=True)
    
    # Show top results
    print("TOP 5 BY PROFIT:")
    print("-"*80)
    for i, r in enumerate(results_by_pnl[:5], 1):
        m, p = r['metrics'], r['params']
        print(f"#{i}: ${m['total_pnl']:+,.2f} P&L, {m['win_rate']:.1f}% Win")
        print(f"    vwap={p['vwap_std_dev_2']}, rsi={p['rsi_oversold']}/{p['rsi_overbought']}, "
              f"risk={p['risk_per_trade']}, contracts={p['max_contracts']}, r:r={p['risk_reward_ratio']}")
        print(f"    Trades: {m['total_trades']}, PF: {m['profit_factor']:.2f}, Sharpe: {m['sharpe_ratio']:.3f}\n")
    
    print("\nTOP 5 BY WIN RATE:")
    print("-"*80)
    for i, r in enumerate(results_by_winrate[:5], 1):
        m, p = r['metrics'], r['params']
        print(f"#{i}: {m['win_rate']:.1f}% Win, ${m['total_pnl']:+,.2f} P&L")
        print(f"    vwap={p['vwap_std_dev_2']}, rsi={p['rsi_oversold']}/{p['rsi_overbought']}, "
              f"risk={p['risk_per_trade']}, contracts={p['max_contracts']}, r:r={p['risk_reward_ratio']}")
        print(f"    Trades: {m['total_trades']}, PF: {m['profit_factor']:.2f}, Sharpe: {m['sharpe_ratio']:.3f}\n")
    
    # Save results
    with open('optimization_final.json', 'w') as f:
        json.dump({
            'test_period': {'start': start_date.isoformat(), 'end': end_date.isoformat()},
            'total_combinations': total,
            'best_by_pnl': {'params': results_by_pnl[0]['params'], 'metrics': results_by_pnl[0]['metrics']} if results_by_pnl else None,
            'best_by_winrate': {'params': results_by_winrate[0]['params'], 'metrics': results_by_winrate[0]['metrics']} if results_by_winrate else None,
            'best_combined': {'params': results_by_combo[0]['params'], 'metrics': results_by_combo[0]['metrics']} if results_by_combo else None,
            'all_results': results
        }, f, indent=2, default=str)
    
    print("\n" + "="*80)
    print("BEST PARAMETERS:")
    print("="*80)
    if results_by_pnl:
        print("\n🏆 FOR MAXIMUM PROFIT:")
        for k, v in results_by_pnl[0]['params'].items():
            print(f"  {k}: {v}")
        print(f"  Expected P&L: ${results_by_pnl[0]['metrics']['total_pnl']:+,.2f}")
        print(f"  Win Rate: {results_by_pnl[0]['metrics']['win_rate']:.1f}%")
    
    print("\nResults saved to: optimization_final.json")

if __name__ == '__main__':
    main()
