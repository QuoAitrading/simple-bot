#!/usr/bin/env python3
"""
Quick parameter test - tests a small subset of promising parameters
Based on issue data: best was RSI 25/75 with 70% win rate and $3,487 profit
"""

import os
os.environ['BOT_BACKTEST_MODE'] = 'true'

from optimize_parameters import run_single_backtest
import json

# Test most promising combinations based on issue feedback
test_configs = [
    # Issue mentions RSI 25/75 was best so far
    {'name': 'Baseline (RSI 28/72, 2.0σ, 1%, 2 contracts)', 'rsi_os': 28, 'rsi_ob': 72, 'vwap': 2.0, 'risk': 0.01, 'contracts': 2},
    {'name': 'Best so far (RSI 25/75, 2.0σ, 1%, 2 contracts)', 'rsi_os': 25, 'rsi_ob': 75, 'vwap': 2.0, 'risk': 0.01, 'contracts': 2},
    
    # Test higher contracts with RSI 25/75
    {'name': 'RSI 25/75, 2.0σ, 1%, 3 contracts', 'rsi_os': 25, 'rsi_ob': 75, 'vwap': 2.0, 'risk': 0.01, 'contracts': 3},
    {'name': 'RSI 25/75, 2.0σ, 1%, 4 contracts', 'rsi_os': 25, 'rsi_ob': 75, 'vwap': 2.0, 'risk': 0.01, 'contracts': 4},
    
    # Test higher risk with RSI 25/75 and 3 contracts
    {'name': 'RSI 25/75, 2.0σ, 1.2%, 3 contracts', 'rsi_os': 25, 'rsi_ob': 75, 'vwap': 2.0, 'risk': 0.012, 'contracts': 3},
    {'name': 'RSI 25/75, 2.0σ, 1.5%, 3 contracts', 'rsi_os': 25, 'rsi_ob': 75, 'vwap': 2.0, 'risk': 0.015, 'contracts': 3},
    
    # Test tighter VWAP entry with RSI 25/75
    {'name': 'RSI 25/75, 1.8σ, 1%, 3 contracts', 'rsi_os': 25, 'rsi_ob': 75, 'vwap': 1.8, 'risk': 0.01, 'contracts': 3},
    {'name': 'RSI 25/75, 2.2σ, 1%, 3 contracts', 'rsi_os': 25, 'rsi_ob': 75, 'vwap': 2.2, 'risk': 0.01, 'contracts': 3},
    
    # Test other RSI combinations with 3 contracts
    {'name': 'RSI 26/74, 2.0σ, 1%, 3 contracts', 'rsi_os': 26, 'rsi_ob': 74, 'vwap': 2.0, 'risk': 0.01, 'contracts': 3},
    {'name': 'RSI 27/73, 2.0σ, 1%, 3 contracts', 'rsi_os': 27, 'rsi_ob': 73, 'vwap': 2.0, 'risk': 0.01, 'contracts': 3},
]

print("=" * 100)
print("QUICK PARAMETER TEST - VWAP BOUNCE BOT")
print("=" * 100)
print("Testing most promising parameter combinations")
print(f"Data period: 7 days (targets scaled from 90-day target)")
print(f"90-day targets: 75% win rate, $9-10K profit, ~16 trades")
print(f"7-day scaled: 75% win rate, ~$800-1000 profit, ~1-2 trades")
print("=" * 100)
print()

results = []

for i, config in enumerate(test_configs, 1):
    print(f"\n[{i}/{len(test_configs)}] {config['name']}")
    print("-" * 100)
    
    result = run_single_backtest(
        rsi_oversold=config['rsi_os'],
        rsi_overbought=config['rsi_ob'],
        vwap_entry_dev=config['vwap'],
        risk_per_trade=config['risk'],
        max_contracts=config['contracts'],
        days=7,
        initial_equity=50000.0
    )
    
    result['config_name'] = config['name']
    result['params'] = config
    results.append(result)
    
    trades = result.get('total_trades', 0)
    win_rate = result.get('win_rate', 0)
    pnl = result.get('total_pnl', 0)
    sharpe = result.get('sharpe_ratio', 0)
    
    print(f"Results: {trades} trades, {win_rate:.1f}% win rate, ${pnl:+.2f} P&L, Sharpe: {sharpe:.2f}")
    
    # Estimate 90-day performance
    if trades > 0:
        est_trades_90 = trades * 13
        est_pnl_90 = pnl * 13
        print(f"Estimated 90-day: {est_trades_90:.0f} trades, ${est_pnl_90:+.2f} profit")
        
        # Check if meets targets
        meets_targets = (win_rate >= 70 and est_pnl_90 >= 9000 and est_trades_90 >= 14)
        if meets_targets:
            print("✅ MEETS TARGET CRITERIA!")

# Find best result
print("\n" + "=" * 100)
print("SUMMARY OF ALL TESTS")
print("=" * 100)

# Sort by a composite score
scored_results = []
for r in results:
    if r.get('total_trades', 0) > 0:
        # Score prioritizes win rate > 70%, then profit
        score = 0
        win_rate = r.get('win_rate', 0)
        pnl = r.get('total_pnl', 0)
        trades = r.get('total_trades', 0)
        
        if win_rate >= 70:
            score += 10000
            score += pnl
        else:
            score += win_rate * 10
            score += pnl * 0.5
        
        r['score'] = score
        scored_results.append(r)

scored_results.sort(key=lambda x: x['score'], reverse=True)

print(f"\n{'Rank':<6} {'Config':<50} {'Trades':<8} {'Win %':<8} {'P&L':<12} {'Sharpe':<8}")
print("-" * 100)

for i, r in enumerate(scored_results[:10], 1):
    print(f"{i:<6} {r['config_name']:<50} {r['total_trades']:<8} {r['win_rate']:<8.1f} ${r['total_pnl']:<11.2f} {r.get('sharpe_ratio', 0):<8.2f}")

if scored_results:
    best = scored_results[0]
    params = best['params']
    
    print("\n" + "=" * 100)
    print("RECOMMENDED CONFIGURATION")
    print("=" * 100)
    print(f"Config: {best['config_name']}")
    print(f"\nParameters:")
    print(f"  RSI Oversold/Overbought: {params['rsi_os']}/{params['rsi_ob']}")
    print(f"  VWAP Entry Deviation: {params['vwap']}σ")
    print(f"  Risk per Trade: {params['risk']*100:.1f}%")
    print(f"  Max Contracts: {params['contracts']}")
    print(f"\n7-Day Results:")
    print(f"  Trades: {best['total_trades']}")
    print(f"  Win Rate: {best['win_rate']:.1f}%")
    print(f"  Total P&L: ${best['total_pnl']:+.2f}")
    print(f"  Sharpe Ratio: {best.get('sharpe_ratio', 0):.2f}")
    print(f"\nEstimated 90-Day Results:")
    print(f"  Trades: ~{best['total_trades'] * 13:.0f}")
    print(f"  Total P&L: ~${best['total_pnl'] * 13:+.2f}")
    print("=" * 100)
    
    # Save results
    with open('quick_test_results.json', 'w') as f:
        json.dump({'best': best, 'all_results': scored_results}, f, indent=2)
    print("\nResults saved to: quick_test_results.json")
