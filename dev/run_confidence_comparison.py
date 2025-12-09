#!/usr/bin/env python3
"""
Confidence Comparison Script
Runs two backtests to compare AI performance:
1. 0% confidence threshold (100% exploration - takes every trade)
2. 70% confidence threshold (baseline)

Uses ES 1-minute bar data from start to finish.
"""

import subprocess
import sys
import os
import json
from datetime import datetime

# Colors for terminal output
GREEN = '\033[92m'
BLUE = '\033[94m'
YELLOW = '\033[93m'
RED = '\033[91m'
RESET = '\033[0m'

def print_header(title):
    """Print a formatted header"""
    print("\n" + "="*80)
    print(f"{BLUE}{title}{RESET}")
    print("="*80 + "\n")

def run_backtest_with_settings(confidence_threshold, exploration_rate, label):
    """
    Run a backtest with specific confidence/exploration settings.
    
    Args:
        confidence_threshold: Confidence threshold (0.0 to 1.0)
        exploration_rate: Exploration rate (0.0 to 1.0)
        label: Label for this run (e.g., "0% Confidence", "70% Confidence")
    
    Returns:
        Dictionary with backtest results or None if failed
    """
    print_header(f"Running Backtest: {label}")
    print(f"Configuration:")
    print(f"  - Confidence Threshold: {confidence_threshold*100:.0f}%")
    print(f"  - Exploration Rate: {exploration_rate*100:.0f}%")
    print(f"  - Symbol: ES")
    print(f"  - Data: All available 1-minute bars\n")
    
    # Get script directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    backtest_script = os.path.join(script_dir, "run_backtest.py")
    
    # Determine the data range by reading the CSV
    csv_path = os.path.join(project_root, "data/historical_data/ES_1min.csv")
    with open(csv_path, 'r') as f:
        lines = f.readlines()
        if len(lines) > 2:
            # Get first data line (skip header)
            first_line = lines[1]
            first_timestamp = first_line.split(',')[0]
            start_date = first_timestamp.split(' ')[0]
            
            # Get last line
            last_line = lines[-1]
            last_timestamp = last_line.split(',')[0]
            end_date = last_timestamp.split(' ')[0]
    
    print(f"Data range: {start_date} to {end_date}")
    
    # Run backtest with full date range
    cmd = [
        sys.executable,
        backtest_script,
        '--symbol', 'ES',
        '--start', start_date,
        '--end', end_date,
        '--confidence-threshold', str(confidence_threshold),
        '--exploration-rate', str(exploration_rate),
        '--log-level', 'WARNING'
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    # Print output
    print(result.stdout)
    if result.stderr:
        print(f"{RED}Errors:{RESET}")
        print(result.stderr)
    
    # Parse the output to extract key metrics
    metrics = extract_metrics_from_output(result.stdout)
    
    return metrics

def extract_metrics_from_output(output):
    """
    Extract key metrics from backtest output.
    
    Args:
        output: String output from backtest
    
    Returns:
        Dictionary with extracted metrics
    """
    metrics = {
        'total_trades': 0,
        'winning_trades': 0,
        'losing_trades': 0,
        'win_rate': 0.0,
        'total_pnl': 0.0,
        'avg_win': 0.0,
        'avg_loss': 0.0,
        'profit_factor': 0.0,
        'max_drawdown': 0.0,
        'return_pct': 0.0
    }
    
    lines = output.split('\n')
    for line in lines:
        line = line.strip()
        
        # Look for metrics in the summary
        if 'Total Trades:' in line or 'Total trades:' in line:
            try:
                # Format: "Total Trades:      508 (Wins: 338, Losses: 170, B/E: 0)"
                parts = line.split('(')
                total = parts[0].split(':')[1].strip().split()[0]
                metrics['total_trades'] = int(total)
                
                # Extract wins and losses from parentheses
                if len(parts) > 1:
                    win_part = parts[1].split(',')[0]  # "Wins: 338"
                    loss_part = parts[1].split(',')[1]  # " Losses: 170"
                    metrics['winning_trades'] = int(win_part.split(':')[1].strip())
                    metrics['losing_trades'] = int(loss_part.split(':')[1].strip())
            except Exception as e:
                print(f"Error parsing total trades: {e}")
        elif 'Win Rate:' in line:
            try:
                metrics['win_rate'] = float(line.split(':')[1].strip().replace('%', ''))
            except:
                pass
        elif 'Net P&L:' in line:
            try:
                # Format: "Net P&L:           $+10,315.86 (+20.63%)"
                pnl_str = line.split(':')[1].strip().split()[0].replace('$', '').replace(',', '').replace('+', '')
                metrics['total_pnl'] = float(pnl_str)
                
                # Extract return percentage
                if '(' in line:
                    ret_str = line.split('(')[1].split(')')[0].replace('%', '').replace('+', '')
                    metrics['return_pct'] = float(ret_str)
            except Exception as e:
                print(f"Error parsing Net P&L: {e}")
        elif 'Avg Win:' in line:
            try:
                avg_str = line.split(':')[1].strip().replace('$', '').replace(',', '')
                metrics['avg_win'] = float(avg_str)
            except:
                pass
        elif 'Avg Loss:' in line:
            try:
                avg_str = line.split(':')[1].strip().replace('$', '').replace(',', '')
                metrics['avg_loss'] = float(avg_str)
            except:
                pass
        elif 'Profit Factor:' in line:
            try:
                metrics['profit_factor'] = float(line.split(':')[1].strip())
            except:
                pass
        elif 'Max Drawdown:' in line:
            try:
                # Format: "Max Drawdown:      $2,250.00 (3.71%)"
                dd_str = line.split(':')[1].strip().split()[0].replace('$', '').replace(',', '')
                metrics['max_drawdown'] = float(dd_str)
            except:
                pass
    
    return metrics

def print_comparison_table(metrics_0, metrics_70):
    """
    Print a side-by-side comparison table of the two backtests.
    
    Args:
        metrics_0: Metrics from 0% confidence backtest
        metrics_70: Metrics from 70% confidence backtest
    """
    print_header("PERFORMANCE COMPARISON")
    
    print(f"{'Metric':<25} {'0% Confidence':<20} {'70% Confidence':<20} {'Difference':<15}")
    print("-" * 80)
    
    # Total Trades
    trades_0 = metrics_0.get('total_trades', 0)
    trades_70 = metrics_70.get('total_trades', 0)
    diff_trades = trades_0 - trades_70
    print(f"{'Total Trades':<25} {trades_0:<20} {trades_70:<20} {diff_trades:+<15}")
    
    # Win Rate
    wr_0 = metrics_0.get('win_rate', 0)
    wr_70 = metrics_70.get('win_rate', 0)
    diff_wr = wr_0 - wr_70
    print(f"{'Win Rate':<25} {wr_0:.1f}%{'':<15} {wr_70:.1f}%{'':<15} {diff_wr:+.1f}%{'':<10}")
    
    # Total P&L
    pnl_0 = metrics_0.get('total_pnl', 0)
    pnl_70 = metrics_70.get('total_pnl', 0)
    diff_pnl = pnl_0 - pnl_70
    color = GREEN if diff_pnl > 0 else RED if diff_pnl < 0 else RESET
    print(f"{'Total P&L':<25} ${pnl_0:,.2f}{'':<10} ${pnl_70:,.2f}{'':<10} {color}${diff_pnl:+,.2f}{RESET}")
    
    # Return %
    ret_0 = metrics_0.get('return_pct', 0)
    ret_70 = metrics_70.get('return_pct', 0)
    diff_ret = ret_0 - ret_70
    color = GREEN if diff_ret > 0 else RED if diff_ret < 0 else RESET
    print(f"{'Return %':<25} {ret_0:+.2f}%{'':<14} {ret_70:+.2f}%{'':<14} {color}{diff_ret:+.2f}%{RESET}")
    
    # Average Win
    avg_win_0 = metrics_0.get('avg_win', 0)
    avg_win_70 = metrics_70.get('avg_win', 0)
    diff_win = avg_win_0 - avg_win_70
    print(f"{'Avg Win':<25} ${avg_win_0:,.2f}{'':<10} ${avg_win_70:,.2f}{'':<10} ${diff_win:+,.2f}")
    
    # Average Loss
    avg_loss_0 = metrics_0.get('avg_loss', 0)
    avg_loss_70 = metrics_70.get('avg_loss', 0)
    diff_loss = avg_loss_0 - avg_loss_70
    print(f"{'Avg Loss':<25} ${avg_loss_0:,.2f}{'':<10} ${avg_loss_70:,.2f}{'':<10} ${diff_loss:+,.2f}")
    
    # Profit Factor
    pf_0 = metrics_0.get('profit_factor', 0)
    pf_70 = metrics_70.get('profit_factor', 0)
    diff_pf = pf_0 - pf_70
    color = GREEN if diff_pf > 0 else RED if diff_pf < 0 else RESET
    print(f"{'Profit Factor':<25} {pf_0:.2f}{'':<16} {pf_70:.2f}{'':<16} {color}{diff_pf:+.2f}{RESET}")
    
    # Max Drawdown
    dd_0 = metrics_0.get('max_drawdown', 0)
    dd_70 = metrics_70.get('max_drawdown', 0)
    diff_dd = dd_0 - dd_70
    color = RED if diff_dd > 0 else GREEN if diff_dd < 0 else RESET
    print(f"{'Max Drawdown':<25} ${dd_0:,.2f}{'':<10} ${dd_70:,.2f}{'':<10} {color}${diff_dd:+,.2f}{RESET}")
    
    print("\n" + "="*80)
    
    # Summary
    if pnl_0 > pnl_70:
        winner = f"{GREEN}0% Confidence (100% Exploration){RESET}"
    elif pnl_70 > pnl_0:
        winner = f"{GREEN}70% Confidence{RESET}"
    else:
        winner = "Tie"
    
    print(f"\n{BLUE}Winner by Total P&L:{RESET} {winner}")
    print(f"\n{YELLOW}Note: 0% confidence means the AI takes EVERY trade signal.")
    print(f"      70% confidence means the AI only takes high-confidence signals.{RESET}\n")

def main():
    """Main entry point"""
    print_header("AI Confidence Comparison Backtest")
    print("This script compares AI performance with different confidence settings:")
    print("  1. 0% Confidence (100% Exploration) - Takes EVERY trade")
    print("  2. 70% Confidence - Takes only high-confidence trades")
    print("\nUsing ES 1-minute bar data from start to finish.\n")
    
    # Run backtest with 0% confidence (100% exploration)
    # Setting confidence_threshold=0.0 means accept all signals above 0%
    metrics_0 = run_backtest_with_settings(
        confidence_threshold=0.0,
        exploration_rate=1.0,  # 100% exploration ensures all signals are taken
        label="0% Confidence (100% Exploration)"
    )
    
    if metrics_0 is None:
        print(f"{RED}Failed to run 0% confidence backtest{RESET}")
        return 1
    
    # Run backtest with 70% confidence
    metrics_70 = run_backtest_with_settings(
        confidence_threshold=0.70,
        exploration_rate=0.30,  # 30% exploration (standard setting)
        label="70% Confidence"
    )
    
    if metrics_70 is None:
        print(f"{RED}Failed to run 70% confidence backtest{RESET}")
        return 1
    
    # Print comparison
    print_comparison_table(metrics_0, metrics_70)
    
    # Save results to file
    results = {
        'timestamp': datetime.now().isoformat(),
        'symbol': 'ES',
        '0_confidence': metrics_0,
        '70_confidence': metrics_70
    }
    
    output_file = 'confidence_comparison_results.json'
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"Results saved to: {output_file}\n")
    
    return 0

if __name__ == '__main__':
    sys.exit(main())
