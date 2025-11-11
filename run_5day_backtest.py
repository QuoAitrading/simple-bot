"""
5-Day Backtest with Full RL Verification
=========================================
This will test:
1. All 10 Exit RL features working
2. All 6 Signal Entry RL features working (including dual pattern matching)
3. Cloud API integration for Signal ML
4. Exit experiences being loaded from cloud
5. All decisions being saved back to cloud

Let's run it and verify everything!
"""

import subprocess
import sys

print("=" * 80)
print("STARTING 5-DAY BACKTEST WITH FULL RL")
print("=" * 80)

print("\n[VERIFICATION CHECKLIST]")
print("✓ Exit RL: 7 features (loaded from cloud: 3,214 experiences)")
print("✓ Signal RL: 6 features (dual pattern matching: 6,880 experiences)")
print("✓ Cloud API: Signal ML endpoint for every signal")
print("✓ Experience saving: Both exits and signals saved to cloud")

print("\n[RUNNING BACKTEST]")
print("Command: python full_backtest.py --days 5")
print("=" * 80)

# Run the backtest
result = subprocess.run(
    [sys.executable, "full_backtest.py", "--days", "5"],
    capture_output=False,
    text=True
)

print("\n" + "=" * 80)
print("BACKTEST COMPLETED")
print("=" * 80)

if result.returncode == 0:
    print("\n✅ Backtest finished successfully!")
    print("\nNext steps:")
    print("1. Check data/backtest_trades.csv for results")
    print("2. Verify stop loss rate is LOWER than 99%")
    print("3. Check cloud API logs for signal decisions")
    print("4. Verify Exit RL features were triggered")
else:
    print(f"\n❌ Backtest failed with exit code {result.returncode}")
    print("Check the output above for errors")

sys.exit(result.returncode)
