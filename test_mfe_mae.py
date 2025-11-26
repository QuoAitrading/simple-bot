"""
Test MFE/MAE Calculation
========================
Verify that market state + outcomes are captured correctly during backtest.
"""

print("=" * 80)
print("MFE/MAE TRACKING TEST")
print("=" * 80)

print("\nWhat we added:")
print("-" * 80)
print("1. Track highest_price_reached and lowest_price_reached on EVERY bar")
print("2. Calculate MFE (Max Favorable Excursion) at exit")
print("3. Calculate MAE (Max Adverse Excursion) at exit")
print("4. Save to experience database with market state")

print("\n" + "=" * 80)
print("EXAMPLE CALCULATION")
print("=" * 80)

# Simulate a long trade
entry_price = 5000.00
exit_price = 5010.00  # +$125 profit
highest_price = 5020.00  # Best price during trade
lowest_price = 4995.00   # Worst price during trade

tick_size = 0.25
tick_value = 12.50

print(f"\nLONG TRADE EXAMPLE:")
print(f"  Entry: ${entry_price:.2f}")
print(f"  Exit:  ${exit_price:.2f}")
print(f"  Best price reached:  ${highest_price:.2f}")
print(f"  Worst price reached: ${lowest_price:.2f}")

# Calculate actual P&L
pnl_ticks = (exit_price - entry_price) / tick_size
pnl = pnl_ticks * tick_value
print(f"\n  Actual P&L: {pnl_ticks} ticks = ${pnl:.2f}")

# Calculate MFE (best profit during trade)
mfe_ticks = (highest_price - entry_price) / tick_size
mfe = mfe_ticks * tick_value
print(f"\n  MFE (Max profit during trade):")
print(f"    ({highest_price:.2f} - {entry_price:.2f}) / {tick_size} = {mfe_ticks} ticks")
print(f"    {mfe_ticks} ticks × ${tick_value} = ${mfe:.2f}")

# Calculate MAE (worst loss during trade)
mae_ticks = (entry_price - lowest_price) / tick_size
mae = mae_ticks * tick_value
print(f"\n  MAE (Max loss during trade):")
print(f"    ({entry_price:.2f} - {lowest_price:.2f}) / {tick_size} = {mae_ticks} ticks")
print(f"    {mae_ticks} ticks × ${tick_value} = ${mae:.2f}")

print(f"\n" + "=" * 80)
print("INSIGHTS FROM MFE/MAE")
print("=" * 80)
print(f"\n  Final P&L:    ${pnl:.2f}")
print(f"  Best profit:  ${mfe:.2f} (left ${mfe - pnl:.2f} on table)")
print(f"  Worst loss:   ${mae:.2f} (went ${mae:.2f} against before winning)")
print(f"\n  MFE/MAE ratio: {mfe/mae if mae > 0 else 0:.2f}")
print(f"  P&L efficiency: {pnl/mfe*100 if mfe > 0 else 0:.1f}% (captured {pnl/mfe*100 if mfe > 0 else 0:.1f}% of max profit)")

print("\n" + "=" * 80)
print("WHAT GETS SAVED TO DATABASE")
print("=" * 80)

experience_example = {
    "timestamp": "2025-11-21T14:30:00",
    "symbol": "ES",
    "price": entry_price,
    "rsi": 45.2,
    "vwap_distance": 0.02,
    "regime": "NORMAL_CHOPPY",
    "session": "RTH",
    # ... 16 total market indicators ...
    
    "outcome": {
        "pnl": pnl,
        "duration_minutes": 15.0,
        "mfe": mfe,
        "mae": mae,
        "took_trade": True
    }
}

import json
print("\n" + json.dumps(experience_example, indent=2))

print("\n" + "=" * 80)
print("HOW RL BRAIN USES THIS")
print("=" * 80)
print("""
When RL brain sees a new signal with similar market conditions:
  
  1. Find past experiences with similar RSI, VWAP distance, regime, etc.
  
  2. Calculate statistics:
     - Average P&L: "This pattern usually makes $X"
     - Average MFE: "This pattern usually reaches max profit of $Y"
     - Average MAE: "This pattern usually goes $Z against you"
     - MFE/MAE ratio: "Risk/reward profile"
     
  3. Make decision:
     - If avg P&L > 0 and acceptable MAE β TAKE TRADE
     - If avg P&L < 0 or MAE too high β SKIP TRADE
     
  4. Better yet:
     - Use MFE to set better profit targets
     - Use MAE to set wider stops (don't get shaken out)
""")

print("\n" + "=" * 80)
print("VERIFICATION CHECKLIST")
print("=" * 80)
print("""
βοΈ Track highest/lowest price on EVERY bar (check_exit_conditions)
βοΈ Calculate MFE/MAE at trade exit (handle_exit_orders)
βοΈ Pass MFE/MAE in execution_data to save_trade_experience
βοΈ Save market state + outcomes in record_outcome
βοΈ All 16 market indicators captured
βοΈ Flat structure (no nested state/action)

Ready to run backtest and verify!
""")

print("=" * 80)
print("RUN BACKTEST TO TEST")
print("=" * 80)
print("\nCommand:")
print("  python dev/run_backtest.py --start 2025-11-01 --end 2025-11-21")
print("\nThen check:")
print("  data/signal_experience.json")
print("\nLook for:")
print('  - "outcome": {"pnl": ..., "mfe": ..., "mae": ...}')
print("  - All 16 market indicators at top level")
print("  - MFE > 0 (best profit reached)")
print("  - MAE > 0 (worst loss during trade)")
