# Bot Learning Investigation & Fixes

## Issues Identified

### 1. Low Confidence Trades - Will It Improve With Training?

**Current Situation:**
- Bot is taking many low confidence trades (5-10%)
- Using linear model? **NO** - Using 2-layer neural network with ReLU activation
- Architecture: 32 input → 64 hidden → 32 hidden → 1 output (R-multiple regression)

**Why Low Confidence:**
The neural network predicts **negative R-multiples** for most trades:
- Example: `R-multiple=-2.969 (raw=-15.8) → confidence=4.9%`
- Example: `R-multiple=-0.287 (raw=-0.6) → confidence=42.9%`

**Conversion Formula:**
```python
r_multiple = 3.0 * np.tanh(raw_output / 6.0)  # Compress to -3 to +3 range
confidence = 1.0 / (1.0 + np.exp(-r_multiple))  # Sigmoid conversion

# Mapping:
# R = -3 → 5% confidence
# R = -1 → 27% confidence
# R = 0  → 50% confidence
# R = +1 → 73% confidence
# R = +3 → 95% confidence
```

**Root Cause:**
The model was trained on data where most trades achieved **very low R-multiples**:
- Max R-multiple achieved: **0.44R**
- Average R-multiple: **0.10R**
- Trades above 1R: **0**
- Trades above 2R: **0**

**Will Training Help?**
- ✅ YES - if we fix the exit logic to let winners run longer
- ❌ NO - if we keep exiting at 0.1R average, model will continue predicting low R
- The model is accurately learning that trades exit too early!

**Solution:**
1. Fix exit logic (see Issue #2)
2. Collect new training data with higher R-multiples
3. Retrain model on better exit data
4. Model will then predict higher confidence

---

### 2. Partial Exits Not Triggering - Critical Bug Found!

**Current Situation:**
- Partial exits configured: 2R (50%), 3R (30%), 5R (20%)
- Partial exits triggered: **0 (0.0%)**
- Trades exiting at average: **0.12R**

**Why Partials Not Triggering:**
Found the bug! **Profit protection is exiting trades BEFORE they reach partial targets.**

**The Problem:**
In `comprehensive_exit_logic.py` line 547-550:
```python
# ADAPTIVE: Profit protection only activates after reaching meaningful profit
MIN_R_FOR_PROTECTION = self.exit_params.get('profit_protection_min_r', 2.5)
```

But the **actual default** in `exit_params_config.py` is:
```python
'profit_protection_min_r': {
    'min': 0.5, 'max': 3.0, 'default': 1.0,  # ← DEFAULT IS 1.0R!
}
```

**The Fallback is Wrong:**
The code uses `2.5` as fallback, but the config default is `1.0`. Since the config default loads, profit protection kicks in at **1.0R**, which is:
- **BEFORE** first partial at 2.0R
- **BEFORE** second partial at 3.0R
- **BEFORE** third partial at 5.0R

**Then Profit Drawdown Logic (line 565-597):**
```python
'profit_drawdown_pct': {
    'min': 0.05, 'max': 0.50, 'default': 0.20,  # 20% drawdown allowed
}
```

Once trade reaches 1.0R (or even less), if it gives back 20% of peak profit, it exits via "profit_drawdown".

**Why This Happens:**
1. Trade goes to +0.3R (peak)
2. Profit protection activates (min_r = 1.0R - but this is checking if peak > threshold)
3. Price pulls back to +0.1R
4. Drawdown = (0.3 - 0.1) / 0.3 = 67% > 20% threshold
5. EXIT via "profit_drawdown" at 0.12R average
6. Never reaches 2R for partials!

**Actual Issue:**
Looking more carefully at the code (lines 555-567), the real problem is:
```python
# Only protect profit if we've reached the minimum threshold AND still in profit
if peak_pnl > min_profit_threshold and current_pnl > 0:
```

The threshold converts to dollar value. With `profit_protection_min_r = 1.0`:
- min_profit_threshold = 1.0 * initial_risk_ticks * $12.50 * contracts
- For typical trade with 50 tick risk, 1 contract = $625
- But peak_pnl is in **dollars**, not R-multiples

**The Real Bug:**
The logic checks `peak_pnl > min_profit_threshold`, which means:
- If peak profit > $625 (1.0R equivalent), activate protection
- But trades are hitting $100-300 peaks, which is **0.2R - 0.5R**
- Protection activates at these small profit levels
- Any 20% drawdown from $300 = $60 drawback triggers exit

**Summary:**
Profit drawdown is the exit reason for 80% of trades because:
1. It activates at very low profit levels (actual R-multiples < 1.0)
2. The 20% drawback threshold is too tight for small profits
3. No trades reach 2R+ for partials

---

### 3. Missing Trade Management Logic

**Current Logic:**
- ✅ Breakeven moves (91% WR when activated)
- ✅ Trailing stops
- ✅ Profit protection
- ✅ Time-based exits
- ✅ 131 exit parameters total

**What's Missing:**
The bot HAS comprehensive logic, but it's **not being used optimally**:

1. **Let Winners Run:**
   - Configured: Partials at 2R/3R/5R
   - Reality: Exits at 0.12R average
   - Fix: Adjust profit_drawdown to activate later

2. **Adaptive Trailing:**
   - Has trailing logic
   - Has acceleration logic
   - But never activates because trades exit too early

3. **Partial Exit Intelligence:**
   - Has 3-tier partial system
   - Never triggers because protection exits first
   - Fix: Let trades breathe before protection activates

**Bot Intelligence That EXISTS but Isn't Executing:**
- Regime-based adjustments (volatility, trend, chop)
- Consecutive win/loss streak management
- Session-based behavior (Asia/London/NY)
- Dead trade detection
- Sideways market handling
- Account protection (consecutive losses)
- Volatility spike handling

**All 131 parameters are tracked, but profit_drawdown dominates everything.**

---

## Recommended Fixes

### Fix 1: Adjust Profit Protection Threshold

**Change in `exit_params_config.py`:**
```python
'profit_protection_min_r': {
    'min': 0.5, 'max': 3.0, 
    'default': 2.5,  # ← INCREASE from 1.0 to 2.5
    'description': 'Min R before profit protection kicks in'
}
```

This prevents protection from activating until after first partial (2.0R).

### Fix 2: Loosen Profit Drawback Tolerance

**Change in `exit_params_config.py`:**
```python
'profit_drawdown_pct': {
    'min': 0.05, 'max': 0.50, 
    'default': 0.40,  # ← INCREASE from 0.20 to 0.40
    'description': 'Max % profit to give back before exiting'
}
```

Allows 40% drawback instead of 20%, letting trades breathe.

### Fix 3: Lower First Partial Target (Optional)

If trades still struggle to reach 2R, consider:
```python
'partial_exit_1_r_multiple': {
    'min': 0.8, 'max': 3.0, 
    'default': 1.2,  # ← DECREASE from 2.0 to 1.2
    'description': 'First partial target in R-multiples'
}
```

This gives the bot a chance to lock in some profit at 1.2R.

### Fix 4: Improve Neural Network Training Data

After fixing exits, run several backtests to collect data where:
- Average R-multiple > 0.5R (currently 0.1R)
- Some trades reach 2R+ for partials
- Winners hold longer than 5 minutes average

Then retrain:
```bash
cd dev-tools && python train_model.py
```

---

## What Will Change After Fixes

### Before (Current):
```
Average R: 0.12R
Partials: 0%
Exit reason: profit_drawdown (80%)
Model confidence: 5-10% (negative R predicted)
```

### After (Expected):
```
Average R: 0.5-1.0R (4-8x improvement)
Partials: 20-40% of trades
Exit reason: Mix of partials, trailing, protection
Model confidence: 20-40% average (positive R predicted)
```

### Long-term (After Retraining):
```
Average R: 1.0-2.0R
Partials: 50-70% of trades
Model confidence: 40-60% average
High confidence trades (>60%): Take 2-3 contracts
```

---

## Testing Plan

1. **Apply fixes** to exit_params_config.py
2. **Run 10-day backtest** to verify:
   - Partials triggering (target: 20%+ of trades)
   - Higher average R (target: 0.5R+)
   - Mix of exit reasons (not 80% profit_drawdown)
3. **Compare results**:
   - Before: 77.8% WR, 0.12R avg, $2,061 profit
   - After: Target 70%+ WR, 0.5R+ avg, $3,000+ profit
4. **Collect new training data** (3-5 backtests)
5. **Retrain neural network** with better exit data
6. **Rerun backtest** to verify improved confidence predictions

---

## Answer to Your Questions

### "Is taking very low confidence will eventually will it adjust with more training?"

**Answer:** YES and NO.
- **NO** - if we keep the current exit logic, the model will continue learning that trades exit at 0.12R
- **YES** - if we fix the exit logic first, then the model will learn that trades can reach higher R-multiples

The model is working correctly - it's accurately predicting that trades will exit early based on the training data. We need better training data (higher R-multiples) first.

### "Are we still using linear?"

**Answer:** NO - Using a **2-layer neural network**:
- Layer 1: 32 inputs → 64 neurons (ReLU)
- Layer 2: 64 → 32 neurons (ReLU)
- Output: 32 → 1 (linear regression for R-multiple)

This is a non-linear model with ~4,000 trainable parameters.

### "How do we fix the partial exits?"

**Answer:** The profit_protection_min_r and profit_drawdown_pct are too aggressive:
1. Protection activates too early (1.0R instead of 2.5R+)
2. Drawback tolerance too tight (20% instead of 40%)
3. This exits trades before they reach 2R for first partial

**Fix:** Adjust those 2 parameters in exit_params_config.py.

### "Does it make sense to leave runners, should I exit now, etc - all trade management logic?"

**Answer:** The bot HAS all the logic (131 parameters):
- Partial exits (3 levels)
- Trailing stops
- Breakeven protection
- Regime adjustments
- Time-based exits
- Volatility handling

**Problem:** profit_drawdown is dominating (80% of exits) and triggering too early, preventing other logic from executing.

**Solution:** Fix the 2 parameters above, and the other 129 parameters will get a chance to shine!

### "Is there logic my bot's missing or it's just too simple?"

**Answer:** Bot is NOT too simple - it's TOO AGGRESSIVE with profit protection!

You have:
- 131 exit parameters (very comprehensive)
- Neural network prediction
- Adaptive regime detection
- Session-based logic
- Streak management
- All advanced features

The issue is ONE parameter (`profit_protection_min_r = 1.0`) is causing exits before other logic can activate.

---

## Summary

**Root Cause:** Profit protection activating at 1.0R (or less in practice) with 20% drawback tolerance is exiting trades at 0.12R average, preventing partials and higher R-multiples.

**Impact:** 
- Neural network learns trades exit early → predicts negative R → low confidence
- Partials never trigger → 0% partial exits
- Bot looks like it's not learning → but it's accurately learning the data!

**Fix:**
1. Change `profit_protection_min_r: 1.0 → 2.5`
2. Change `profit_drawdown_pct: 0.20 → 0.40`
3. Run new backtests to collect better training data
4. Retrain neural network
5. Watch confidence predictions improve

**The bot IS learning correctly - it just needs better training data from improved exit logic!**
