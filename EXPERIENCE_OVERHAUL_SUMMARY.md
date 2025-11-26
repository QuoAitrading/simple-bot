# Experience System Overhaul - Complete Summary

## Overview
Completely restructured the experience/learning system from RL-focused nested format to flat market state snapshot format.

## Changes Made

### 1. New Market State Structure (16 fields)

**Flat format** - All indicators at top level:
```json
{
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
  "volatility_regime": "MEDIUM"
}
```

### 2. New Indicators Added

1. **returns** - Price change percentage (current vs previous close)
2. **vwap_slope** - VWAP trend direction (5-period slope)
3. **atr_slope** - Volatility trend (5-period ATR slope)
4. **macd_hist** - MACD histogram value (already calculated, now captured)
5. **stoch_k** - Stochastic %K oscillator (14-period)
6. **volume_slope** - Volume trend (5-period slope)
7. **session** - Trading session type (RTH vs ETH)
8. **volatility_regime** - Volatility classification (LOW/MEDIUM/HIGH)

### 3. New Helper Functions Added

**src/quotrading_engine.py:**

- `calculate_slope(values, periods)` - Generic slope calculation for any metric
- `calculate_stochastic(bars, k_period, d_period)` - Stochastic oscillator
- `get_session_type(current_time)` - Classify RTH vs ETH
- `get_volatility_regime(atr, symbol)` - Classify volatility level
- `capture_market_state(symbol, price)` - NEW main function (replaces capture_rl_state)
- `capture_rl_state()` - DEPRECATED (kept for backward compatibility)

### 4. Updated Functions

**src/quotrading_engine.py:**

- Entry logic (lines ~3030-3090): Now captures market state AND converts to RL format for compatibility
- Exit logic (lines ~5780-5820): Records market state snapshot instead of RL experience
- Both long and short signals updated

**src/signal_confidence.py:**

- `record_outcome()` - Updated to save flat market state instead of nested RL structure
- Removed: action, reward, duration fields from storage
- Now saves every 10 states (was 5 trades)

### 5. Data Migration

- **Old format:** 
  ```json
  {
    "state": {...},
    "action": {...},
    "reward": 125.5,
    "duration": 900
  }
  ```

- **New format:** All fields at top level (see structure above)

- **Database cleared:** Old experiences incompatible with new flat structure
- **Backup saved:** `signal_experience.json.backup_old_volume_logic`

## Session Type Classification

**RTH (Regular Trading Hours):**
- ES: 9:30 AM - 4:00 PM ET
- Higher volume, tighter spreads
- Most institutional activity

**ETH (Extended Trading Hours):**
- All other times
- Lower volume, wider spreads
- Overnight gaps

## Volatility Regime Classification

Based on current ATR vs 100-bar average:
- **LOW:** ATR < 75% of average
- **MEDIUM:** ATR between 75-125% of average  
- **HIGH:** ATR > 125% of average

## Calculation Details

### All calculations use 1-min bars for consistency:

1. **Returns:** `(current_close - prev_close) / prev_close`
2. **VWAP Slope:** 5-period percentage change in VWAP
3. **ATR Slope:** 5-period percentage change in ATR
4. **MACD Hist:** From existing `state[symbol]["macd"]` (15-min bars)
5. **Stochastic %K:** `((close - lowest_low) / (highest_high - lowest_low)) * 100` over 14 periods
6. **Volume Slope:** 5-period percentage change in volume
7. **Volume Ratio:** Current 1-min volume / 20-bar 1-min average (VERIFIED CORRECT)

## Backward Compatibility

- Old `capture_rl_state()` marked as deprecated but still works
- Entry logic creates BOTH formats:
  - `entry_market_state` (new flat format)
  - `entry_rl_state` (old format for RL brain compatibility)
- RL brain still receives old format for cloud API compatibility
- Market states saved to local JSON in new format

## Files Modified

1. **src/quotrading_engine.py:**
   - Added 6 new functions (slopes, stochastic, session, volatility, market state)
   - Updated signal entry logic (long and short)
   - Updated exit recording logic

2. **src/signal_confidence.py:**
   - Simplified `record_outcome()` to save flat structure
   - Removed nested state/action/reward structure

3. **data/signal_experience.json:**
   - Cleared (0 experiences)
   - Ready for new format

## Testing Steps

1. **Verify structure:** `python validate_new_structure.py` ✓
2. **Run backtest:** Test that market states are captured correctly
3. **Check JSON:** Verify all 16 fields populated with reasonable values
4. **Validate calculations:** Ensure slopes, stochastic, session all correct

## Expected Behavior

**During backtest:**
- Every trade captures market state at entry
- Market state saved to `signal_experience.json` in flat format
- Log message: "πΎ [MARKET STATE] Recorded state snapshot"
- Saved every 10 states automatically

**What's stored:**
- Timestamp of state capture
- All 16 market indicators
- NO action, reward, or duration

**What's NOT stored:**
- Trade P&L (tracked separately in session stats)
- Trade duration (tracked separately)
- Side (not needed - market state is directional agnostic)

## Advantages of New Format

1. **Cleaner:** Flat structure easier to analyze
2. **More data:** 16 fields vs 10 (60% more information)
3. **Better features:** Slopes capture trends, session captures regime
4. **Live-compatible:** All calculations work on live data
5. **ML-ready:** Can be used for any ML model, not just RL
6. **Continuous:** Market state vs trade outcome decouples learning from execution

## Next Steps

1. Run clean backtest (Nov 1-21) to populate database
2. Verify all 16 fields have reasonable values
3. Analyze patterns in market states
4. Consider using for:
   - Pattern recognition
   - Regime classification
   - Entry timing optimization
   - Risk management
