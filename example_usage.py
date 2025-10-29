"""
Example: Running the VWAP Bounce Bot with Backtesting
Demonstrates how to use the backtesting framework
"""

import sys
import os

# Set up environment
os.environ['TOPSTEP_API_TOKEN'] = 'DEMO_TOKEN'

# Run backtest examples

print("="*60)
print("EXAMPLE 1: Basic Backtest")
print("="*60)
print("\nRunning backtest for last 7 days...\n")
os.system("python main.py --mode backtest --days 7 --log-level WARNING")

print("\n" + "="*60)
print("EXAMPLE 2: Backtest with Report")
print("="*60)
print("\nRunning backtest and saving report...\n")
os.system("python main.py --mode backtest --days 7 --report example_report.txt --log-level WARNING")

print("\n" + "="*60)
print("Report saved to: example_report.txt")
print("="*60)

print("\n" + "="*60)
print("EXAMPLE 3: Check Health Endpoint (Dry Run)")
print("="*60)
print("\nTo test the health check endpoint:")
print("  1. Run: python main.py --mode live --dry-run")
print("  2. In another terminal: curl http://localhost:8080/health")
print("  3. Press Ctrl+C to stop the bot")
print("="*60)

print("\n\n✅ Examples completed!")
print("\nNext steps:")
print("  - Review example_report.txt for backtest results")
print("  - Modify backtesting.py to integrate actual trading strategy")
print("  - Test with your own historical data")
print("  - Run live in dry-run mode before production")
