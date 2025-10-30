#!/usr/bin/env python3
"""
Enhanced parameter optimization - Testing more aggressive configurations
to find higher profit and win rate combinations
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

# Setup logging
logging.basicConfig(
    level=logging.ERROR,
    format='%(levelname)s: %(message)s'
)

def run_backtest_with_params(param_dict, symbol, start_date, end_date):
    """Run a single backtest with given parameters"""
    
    # Load config and override with test parameters
    bot_config = load_config(backtest_mode=True)
    for key, value in param_dict.items():
        setattr(bot_config, key, value)
    bot_config_dict = bot_config.to_dict()
    
    # Setup backtest
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
    
    # Create engine
    engine = BacktestEngine(backtest_config, bot_config_dict)
    
    # Get ET timezone
    et = pytz.timezone('US/Eastern')
    
    # Track position state
    last_position_active = [False]
    
    def vwap_strategy(bars_1min, bars_15min):
        """VWAP strategy with proper position tracking"""
        
        # Clear state fresh for each run
        if symbol in state:
            state.pop(symbol)
        initialize_state(symbol)
        
        last_position_active[0] = False
        
        for bar in bars_1min:
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
            
            # Sync position state with engine
            if symbol in state and 'position' in state[symbol]:
                pos = state[symbol]['position']
                is_active = pos.get('active', False)
                
                # Position opened
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
                
                # Position closed
                elif not is_active and last_position_active[0]:
                    if engine.current_position is not None:
                        engine._close_position(timestamp, price, 'bot_exit')
                    last_position_active[0] = False
    
    # Run backtest
    try:
        results = engine.run_with_strategy(vwap_strategy)
        return results
    except Exception as e:
        print(f"ERROR in backtest: {e}")
        return None


def main():
    print("="*80)
    print("ENHANCED VWAP BOT PARAMETER OPTIMIZATION")
    print("Testing More Aggressive Configurations for Higher Profit & Win Rate")
    print("="*80)
    print()
    
    # Date range - use all available data
    symbol = 'ES'
    tz = pytz.timezone('America/New_York')
    end_date = datetime(2025, 10, 29, tzinfo=tz)
    start_date = datetime(2025, 9, 1, tzinfo=tz)
    
    print(f"Testing Period: {start_date.date()} to {end_date.date()}")
    print(f"Symbol: {symbol}")
    print()
    
    # EXPANDED parameter grid with more aggressive options
    param_grid = {
        # Tighter and wider VWAP bands
        'vwap_std_dev_2': [1.0, 1.2, 1.5, 2.0],
        
        # More extreme RSI thresholds
        'rsi_oversold': [15, 20, 25],
        'rsi_overbought': [70, 75, 80],
        
        # Test both filter states
        'use_rsi_filter': [True, False],
        
        # More aggressive position sizing
        'risk_per_trade': [0.015, 0.02, 0.025],
        
        # Increase max trades per day to capture more opportunities
        'max_trades_per_day': [5, 7, 10],
    }
    
    # Generate all combinations
    param_names = list(param_grid.keys())
    param_values = [param_grid[name] for name in param_names]
    combinations = list(product(*param_values))
    
    total = len(combinations)
    print(f"Testing {total} parameter combinations (EXPANDED SEARCH)...")
    print()
    
    results = []
    best_pnl = -999999
    best_winrate = 0
    best_params_pnl = None
    best_params_winrate = None
    
    for i, combo in enumerate(combinations, 1):
        params = dict(zip(param_names, combo))
        
        print(f"[{i}/{total}] vwap={params['vwap_std_dev_2']}, rsi={params['rsi_oversold']}/{params['rsi_overbought']}, "
              f"rsi_filt={params['use_rsi_filter']}, risk={params['risk_per_trade']}, max_trades={params['max_trades_per_day']}")
        
        result = run_backtest_with_params(params, symbol, start_date, end_date)
        
        if result:
            results.append({
                'params': params,
                'metrics': result
            })
            
            print(f"  -> Trades: {result['total_trades']}, P&L: ${result['total_pnl']:+,.2f}, "
                  f"Win%: {result['win_rate']:.1f}%, Sharpe: {result['sharpe_ratio']:.3f}")
            
            # Track best by P&L
            if result['total_pnl'] > best_pnl:
                best_pnl = result['total_pnl']
                best_params_pnl = params.copy()
            
            # Track best by win rate
            if result['win_rate'] > best_winrate:
                best_winrate = result['win_rate']
                best_params_winrate = params.copy()
        else:
            print(f"  -> FAILED")
        
        print()
    
    print("="*80)
    print("ENHANCED OPTIMIZATION COMPLETE!")
    print("="*80)
    print()
    
    # Sort results
    results_by_pnl = sorted(results, key=lambda x: x['metrics']['total_pnl'], reverse=True)
    results_by_winrate = sorted(results, key=lambda x: x['metrics']['win_rate'], reverse=True)
    results_by_combo = sorted(results, key=lambda x: (x['metrics']['total_pnl'] * x['metrics']['win_rate']), reverse=True)
    
    # Show top 10 by P&L
    print("TOP 10 MOST PROFITABLE (by P&L):")
    print("-"*80)
    for i, r in enumerate(results_by_pnl[:10], 1):
        m = r['metrics']
        p = r['params']
        print(f"\n#{i}: ${m['total_pnl']:+,.2f} P&L, {m['win_rate']:.1f}% Win, {m['sharpe_ratio']:.3f} Sharpe")
        print(f"    vwap={p['vwap_std_dev_2']}, rsi={p['rsi_oversold']}/{p['rsi_overbought']}, "
              f"rsi_filter={p['use_rsi_filter']}, risk={p['risk_per_trade']}, max_trades={p['max_trades_per_day']}")
        print(f"    Trades: {m['total_trades']}, Profit Factor: {m['profit_factor']:.2f}")
    
    print("\n" + "="*80)
    print("TOP 10 HIGHEST WIN RATE:")
    print("-"*80)
    for i, r in enumerate(results_by_winrate[:10], 1):
        m = r['metrics']
        p = r['params']
        print(f"\n#{i}: {m['win_rate']:.1f}% Win, ${m['total_pnl']:+,.2f} P&L, {m['sharpe_ratio']:.3f} Sharpe")
        print(f"    vwap={p['vwap_std_dev_2']}, rsi={p['rsi_oversold']}/{p['rsi_overbought']}, "
              f"rsi_filter={p['use_rsi_filter']}, risk={p['risk_per_trade']}, max_trades={p['max_trades_per_day']}")
        print(f"    Trades: {m['total_trades']}, Profit Factor: {m['profit_factor']:.2f}")
    
    print("\n" + "="*80)
    print("TOP 10 BEST COMBINED (P&L × Win Rate):")
    print("-"*80)
    for i, r in enumerate(results_by_combo[:10], 1):
        m = r['metrics']
        p = r['params']
        combined_score = m['total_pnl'] * m['win_rate'] / 100
        print(f"\n#{i}: ${m['total_pnl']:+,.2f} P&L, {m['win_rate']:.1f}% Win (Score: {combined_score:.1f})")
        print(f"    vwap={p['vwap_std_dev_2']}, rsi={p['rsi_oversold']}/{p['rsi_overbought']}, "
              f"rsi_filter={p['use_rsi_filter']}, risk={p['risk_per_trade']}, max_trades={p['max_trades_per_day']}")
        print(f"    Trades: {m['total_trades']}, Sharpe: {m['sharpe_ratio']:.3f}, PF: {m['profit_factor']:.2f}")
    
    # Save all results
    output = {
        'test_period': {
            'start': start_date.isoformat(),
            'end': end_date.isoformat(),
            'days': (end_date - start_date).days
        },
        'total_combinations': total,
        'successful_runs': len(results),
        'best_by_pnl': {
            'params': best_params_pnl,
            'metrics': results_by_pnl[0]['metrics'] if results_by_pnl else None
        },
        'best_by_winrate': {
            'params': best_params_winrate,
            'metrics': results_by_winrate[0]['metrics'] if results_by_winrate else None
        },
        'best_combined': {
            'params': results_by_combo[0]['params'] if results_by_combo else None,
            'metrics': results_by_combo[0]['metrics'] if results_by_combo else None
        },
        'top_10_by_pnl': results_by_pnl[:10],
        'top_10_by_winrate': results_by_winrate[:10],
        'top_10_combined': results_by_combo[:10]
    }
    
    with open('optimization_enhanced.json', 'w') as f:
        json.dump(output, f, indent=2, default=str)
    
    print("\n" + "="*80)
    print("BEST PARAMETERS TO USE:")
    print("="*80)
    
    if results_by_pnl:
        print("\n🏆 HIGHEST PROFIT:")
        best_pnl_result = results_by_pnl[0]
        for key, value in best_pnl_result['params'].items():
            print(f"  {key}: {value}")
        print(f"  Expected P&L: ${best_pnl_result['metrics']['total_pnl']:+,.2f}")
        print(f"  Win Rate: {best_pnl_result['metrics']['win_rate']:.1f}%")
        print(f"  Trades: {best_pnl_result['metrics']['total_trades']}")
    
    if results_by_winrate:
        print("\n🎯 HIGHEST WIN RATE:")
        best_wr_result = results_by_winrate[0]
        for key, value in best_wr_result['params'].items():
            print(f"  {key}: {value}")
        print(f"  Win Rate: {best_wr_result['metrics']['win_rate']:.1f}%")
        print(f"  Expected P&L: ${best_wr_result['metrics']['total_pnl']:+,.2f}")
        print(f"  Trades: {best_wr_result['metrics']['total_trades']}")
    
    if results_by_combo:
        print("\n⭐ BEST COMBINED (Profit × Win Rate):")
        best_combo_result = results_by_combo[0]
        for key, value in best_combo_result['params'].items():
            print(f"  {key}: {value}")
        print(f"  P&L: ${best_combo_result['metrics']['total_pnl']:+,.2f}")
        print(f"  Win Rate: {best_combo_result['metrics']['win_rate']:.1f}%")
        print(f"  Trades: {best_combo_result['metrics']['total_trades']}")
    
    print("\nResults saved to: optimization_enhanced.json")
    print("="*80)


if __name__ == '__main__':
    main()
