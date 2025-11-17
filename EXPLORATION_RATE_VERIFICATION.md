# Exploration Rate Verification - Live vs Backtest

**Date:** November 17, 2025  
**Purpose:** Confirm exploration is 0% in live mode, 30% in backtest mode

---

## Summary

✅ **CONFIRMED: Exploration is 0% in live trading, 30% in backtest mode**

The code already enforces this behavior correctly. No changes were needed.

---

## Code Verification

### Location: `src/signal_confidence.py`

**Line 456:** Exploration rate enforcement
```python
# LIVE MODE: 0% exploration (pure exploitation of learned intelligence)
# BACKTEST MODE: Use configured exploration_rate (default 5%)
effective_exploration = self.exploration_rate if self.backtest_mode else 0.0
```

**Key Logic:**
- `backtest_mode = False` → `effective_exploration = 0.0` (LIVE)
- `backtest_mode = True` → `effective_exploration = self.exploration_rate` (BACKTEST)

### Line 483-486: Exploration Application
```python
if random.random() < effective_exploration:
    take = random.choice([True, False])
    reason = f"Exploring ({effective_exploration*100:.0f}% random, {len(self.experiences)} exp)"
```

**In Live Mode:**
- `effective_exploration = 0.0`
- `random.random() < 0.0` is always `False`
- Exploration block never executes
- **Result: 0% exploration**

**In Backtest Mode:**
- `effective_exploration = 0.30` (30% from config)
- `random.random() < 0.30` is true ~30% of the time
- Exploration block executes randomly
- **Result: 30% exploration**

---

## Logging Verification

### Line 148-150: Initialization Logs
```python
if self.backtest_mode:
    logger.info(f" BACKTEST MODE: {self.exploration_rate*100:.1f}% exploration enabled (learning mode)")
else:
    logger.info(f" LIVE MODE: 0% exploration (pure exploitation - NO RANDOM TRADES!)")
```

**Output Examples:**

**Live Mode:**
```
INFO: LIVE MODE: 0% exploration (pure exploitation - NO RANDOM TRADES!)
```

**Backtest Mode:**
```
INFO: BACKTEST MODE: 30.0% exploration enabled (learning mode)
```

---

## Configuration Settings

### Live Mode Settings
From `src/signal_confidence.py` initialization:
```python
self.exploration_rate = exploration_rate if exploration_rate is not None else 0.05  # Default 5%
```

However, this is **overridden** by the `effective_exploration` logic:
```python
effective_exploration = 0.0  # Always 0 in live mode
```

**Result:** Even if `exploration_rate = 0.05` is set, live mode uses 0.0

### Backtest Mode Settings
From `dev-tools/full_backtest.py`:
```python
CONFIG = {
    "exploration_rate": 0.30,  # 30% exploration rate (HIGH - for testing and building dataset)
    ...
}
```

**Result:** Backtest mode uses 30% exploration

---

## Why This Design?

### Live Trading = Pure Exploitation
```
❌ NO exploration (no random trades)
✅ Use learned intelligence only
✅ Maximize profit from known patterns
✅ Never take random risks with real money
```

**Reason:** You don't want the bot taking random trades with real money. Live trading should only use the neural network's learned intelligence.

### Backtesting = Learning Mode
```
✅ 30% exploration (random trades for learning)
✅ Discover new profitable patterns
✅ Build diverse experience dataset
✅ Avoid overfitting to known patterns
```

**Reason:** Backtesting is for learning. Exploration helps discover new patterns and builds a more robust dataset for training the neural network.

---

## Testing Verification

### Test 1: Live Mode Behavior
```python
# Initialize in live mode
scorer = SignalConfidence(backtest_mode=False, exploration_rate=0.30)

# effective_exploration will be 0.0 (not 0.30)
# Exploration block will never execute
```

### Test 2: Backtest Mode Behavior
```python
# Initialize in backtest mode  
scorer = SignalConfidence(backtest_mode=True, exploration_rate=0.30)

# effective_exploration will be 0.30
# Exploration block will execute ~30% of the time
```

### Test 3: Exploration Rate Override
```python
# Even with high exploration_rate, live mode uses 0
scorer = SignalConfidence(backtest_mode=False, exploration_rate=0.50)

# effective_exploration = 0.0 (overridden)
# NO exploration in live mode
```

---

## Backtest Verification

From previous backtest results:

**Expected behavior with 30% exploration:**
```
97 signals detected
30% exploration = ~29 signals explored
Result: ~29 trades taken (before bug fix: only 7)
```

**After exploration bug fix:**
- Exploration working correctly
- 30% of signals get explored randomly
- Learning from diverse experiences

---

## Summary

### ✅ Live Mode (backtest_mode=False)
- Exploration: **0%** (hardcoded)
- Behavior: Pure exploitation
- Logic: `effective_exploration = 0.0`
- No random trades taken

### ✅ Backtest Mode (backtest_mode=True)  
- Exploration: **30%** (from CONFIG)
- Behavior: Learning mode
- Logic: `effective_exploration = 0.30`
- Random trades for discovery

### Code Path
```
backtest_mode? 
├─ No (Live)  → effective_exploration = 0.0  → 0% exploration
└─ Yes (Test) → effective_exploration = 0.30 → 30% exploration
```

---

## Conclusion

**No changes needed.** The code already implements the correct behavior:
- Live trading: 0% exploration (safe, no random trades)
- Backtesting: 30% exploration (learning, pattern discovery)

The exploration rate is correctly enforced through the `effective_exploration` variable which is set based on the `backtest_mode` flag.
