#!/usr/bin/env python3
"""
Simple manual parameter optimization using main.py backtest
Tests different parameter combinations and finds the best one
"""

import os
import subprocess
import json
from itertools import product
from datetime import datetime

# Define parameters to test (smaller set for speed)
param_grid = {
    'vwap_std_dev_2': [1.5, 2.0, 2.5],
    'rsi_oversold': [20, 25, 30],
    'rsi_overbought': [70, 75, 80],
    'use_rsi_filter': [True, False],
    'risk_per_trade': [0.01, 0.012]
}

def run_backtest_with_params(params):
    """Run a single backtest with given parameters"""
    # Set environment variables for parameters
    env = os.environ.copy()
    env['BOT_BACKTEST_MODE'] = 'true'
    
    # Override parameters via environment
    for key, value in params.items():
        env_key = f'BOT_{key.upper()}'
        env[env_key] = str(value)
    
    # Run backtest using main.py
    cmd = [
        'python3', 'main.py',
        '--mode', 'backtest',
        '--start', '2025-10-01',
        '--end', '2025-10-29',
        '--initial-equity', '50000'
    ]
    
    result = subprocess.run(
        cmd,
        env=env,
        capture_output=True,
        text=True,
        cwd='/home/runner/work/simple-bot/simple-bot'
    )
    
    # Parse output for results
    output = result.stdout + result.stderr
    
    # Extract metrics from output
    metrics = {
        'total_trades': 0,
        'total_pnl': 0.0,
        'win_rate': 0.0,
        'sharpe_ratio': 0.0,
        'profit_factor': 0.0
    }
    
    for line in output.split('\n'):
        if 'Total Trades:' in line:
            try:
                metrics['total_trades'] = int(line.split(':')[1].strip())
            except:
                pass
        elif 'Total P&L:' in line:
            try:
                pnl_str = line.split(':')[1].strip().replace('$', '').replace(',', '').replace('+', '')
                metrics['total_pnl'] = float(pnl_str)
            except:
                pass
        elif 'Win Rate:' in line:
            try:
                metrics['win_rate'] = float(line.split(':')[1].strip().replace('%', ''))
            except:
                pass
        elif 'Sharpe Ratio:' in line:
            try:
                metrics['sharpe_ratio'] = float(line.split(':')[1].strip())
            except:
                pass
        elif 'Profit Factor:' in line:
            try:
                metrics['profit_factor'] = float(line.split(':')[1].strip())
            except:
                pass
    
    return metrics

def main():
    print("="*80)
    print("MANUAL PARAMETER OPTIMIZATION FOR VWAP BOT")
    print("="*80)
    print()
    
    # Generate all parameter combinations
    param_names = list(param_grid.keys())
    param_values = [param_grid[name] for name in param_names]
    combinations = list(product(*param_values))
    
    total = len(combinations)
    print(f"Testing {total} parameter combinations...")
    print()
    
    results = []
    
    for i, combo in enumerate(combinations, 1):
        params = dict(zip(param_names, combo))
        print(f"[{i}/{total}] Testing: {params}")
        
        metrics = run_backtest_with_params(params)
        
        result = {
            'params': params,
            'metrics': metrics
        }
        results.append(result)
        
        print(f"  -> Trades: {metrics['total_trades']}, P&L: ${metrics['total_pnl']:+.2f}, Sharpe: {metrics['sharpe_ratio']:.4f}")
        print()
    
    # Find best parameters
    print("="*80)
    print("OPTIMIZATION COMPLETE!")
    print("="*80)
    print()
    
    # Sort by Sharpe ratio (best risk-adjusted returns)
    results_sorted = sorted(results, key=lambda x: x['metrics']['sharpe_ratio'], reverse=True)
    
    print("TOP 5 PARAMETER COMBINATIONS (by Sharpe Ratio):")
    print("-"*80)
    for i, result in enumerate(results_sorted[:5], 1):
        print(f"\n#{i}")
        print(f"Parameters: {result['params']}")
        print(f"Metrics:")
        for key, value in result['metrics'].items():
            if 'pnl' in key:
                print(f"  {key}: ${value:+,.2f}")
            elif 'rate' in key or 'sharpe' in key or 'factor' in key:
                print(f"  {key}: {value:.2f}")
            else:
                print(f"  {key}: {value}")
    
    # Save results
    output_file = 'manual_optimization_results.json'
    with open(output_file, 'w') as f:
        json.dump({
            'timestamp': datetime.now().isoformat(),
            'total_combinations': total,
            'all_results': results_sorted,
            'best_params': results_sorted[0]['params'] if results_sorted else None,
            'best_metrics': results_sorted[0]['metrics'] if results_sorted else None
        }, f, indent=2)
    
    print(f"\n\nResults saved to: {output_file}")
    
    if results_sorted:
        print("\nBEST PARAMETERS:")
        for key, value in results_sorted[0]['params'].items():
            print(f"  {key}: {value}")

if __name__ == '__main__':
    main()
