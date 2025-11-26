"""
Validate New Market State Structure
=====================================
This script demonstrates the new market state format that will be saved.
"""

import json

# New market state structure WITH OUTCOMES
example_experience = {
    # Market State (16 fields)
    "timestamp": "2025-11-24T20:09:24.117260",
    "symbol": "ES",
    "price": 5042.75,
    "returns": -0.0003,
    "vwap_distance": 0.02,
    "vwap_slope": -0.0015,
    "atr": 2.5,
    "atr_slope": 0.02,
    "rsi": 45.2,
    "macd_hist": -1.3,
    "stoch_k": 72.4,
    "volume_ratio": 1.3,
    "volume_slope": 0.42,
    "hour": 14,
    "session": "RTH",
    "regime": "NORMAL_CHOPPY",
    "volatility_regime": "MEDIUM",
    
    # Trade Outcome (what RL brain needs to learn!)
    "outcome": {
        "pnl": 125.5,
        "duration_minutes": 15.0,
        "mfe": 200.0,  # Max Favorable Excursion
        "mae": 50.0,   # Max Adverse Excursion
        "took_trade": True
    }
}

print("=" * 80)
print("NEW EXPERIENCE STRUCTURE (Market State + Outcomes)")
print("=" * 80)
print("\nThis is what will be saved in signal_experience.json:\n")
print(json.dumps(example_experience, indent=2))

print("\n" + "=" * 80)
print("KEY DIFFERENCES FROM OLD FORMAT")
print("=" * 80)
print("\nOLD FORMAT (nested, less data):")
print("""
{
  "state": {
    "rsi": 45.2,
    "vwap_distance": 0.02,
    ...only 10 fields...
  },
  "action": {"took_trade": true},
  "reward": 125.5,
  "duration": 900
}
""")

print("\nNEW FORMAT (flat, more data + better outcomes):")
print("""
{
  ...16 market indicators at top level...
  "rsi": 45.2,
  "vwap_distance": 0.02,
  "vwap_slope": -0.0015,  <- NEW!
  "stoch_k": 72.4,        <- NEW!
  "session": "RTH",       <- NEW!
  ...
  
  "outcome": {
    "pnl": 125.5,
    "duration_minutes": 15.0,
    "mfe": 200.0,  <- NEW! (Max profit during trade)
    "mae": 50.0,   <- NEW! (Max loss during trade)
    "took_trade": true
  }
}
""")

print("\n" + "=" * 80)
print("WHAT'S NEW")
print("=" * 80)
print("\nAdded Market Indicators:")
print("  βretums: Price change (percentage)")
print("  β vwap_slope: VWAP trend direction")
print("  β atr_slope: Volatility trend")
print("  β macd_hist: MACD histogram value")
print("  β stoch_k: Stochastic %K (momentum)")
print("  β volume_slope: Volume trend")
print("  β session: RTH vs ETH classification")
print("  β volatility_regime: LOW/MEDIUM/HIGH")

print("\nImproved Outcome Tracking:")
print("  β pnl: Profit/loss (KEPT - RL brain needs this!)")
print("  β duration_minutes: How long trade lasted")
print("  β mfe: Max Favorable Excursion (best profit during trade)")
print("  β mae: Max Adverse Excursion (worst loss during trade)")
print("  β took_trade: Whether trade was taken")

print("\nRemoved/Changed:")
print("  - day_of_week (removed - not useful)")
print("  - recent_pnl (removed - not in state)")
print("  - streak (removed - not in state)")
print("  - side (removed - not in state)")
print("  - Flattened structure (no nested 'state', 'action')")

print("\n" + "=" * 80)
print("TOTAL: 16 market indicators + 5 outcome fields = 21 fields")
print("=" * 80)

# Check current database
try:
    with open("data/signal_experience.json", "r") as f:
        data = json.load(f)
        count = len(data.get("experiences", []))
        print(f"\nCurrent experience count: {count}")
        if count > 0:
            print("\nFirst experience:")
            print(json.dumps(data["experiences"][0], indent=2))
except Exception as e:
    print(f"\nCould not read database: {e}")

print("\n" + "=" * 80)
print("HOW RL BRAIN USES THIS")
print("=" * 80)
print("\nRL brain looks at market state and asks:")
print('  "Last time I saw RSI=45, VWAP distance=0.02, regime=NORMAL_CHOPPY..."')
print('  "...what was the average PNL?"')
print('')
print("If average PNL > 0 β Take trade")
print("If average PNL < 0 β Skip trade")
print('')
print("MFE/MAE help understand:")
print("  - Risk (how bad can it get? = MAE)")
print("  - Reward potential (how good can it get? = MFE)")
print("  - Whether to use tight or wide stops")

print("\n" + "=" * 80)
print("READY FOR BACKTEST")
print("=" * 80)
print("\nRun a backtest to populate the database.")
print("Each trade will save:")
print("  β 16 market indicators (what the market looked like)")
print("  β 5 outcome metrics (what happened)")
print("\nRL brain will learn which market conditions = profitable trades!")
