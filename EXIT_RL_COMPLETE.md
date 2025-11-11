# Exit RL System - Complete Feature Set ✅

## What the Exit RL System Now Learns

The adaptive exit system uses reinforcement learning to optimize **ALL** aspects of trade management based on past outcomes.

### ✅ Complete Learning Parameters

#### 1. **Stop Loss Management** (Already Implemented)
- `stop_mult`: Distance multiplier for initial stop loss
- **Learns**: Optimal stop distance per regime (tight vs wide stops)
- **Analysis**: Which stop distances minimize losses while allowing winners to run

#### 2. **Breakeven Management** (Already Implemented)
- `breakeven_mult`: When to move stop to breakeven
- **Learns**: Optimal breakeven timing (early protection vs giving room)
- **Analysis**: Does early BE lock in small wins? Does late BE miss runners?

#### 3. **Trailing Stop Management** (Already Implemented)
- `trailing_mult`: Distance for trailing stop
- **Learns**: Optimal trail distance per regime (tight vs loose trailing)
- **Analysis**: Tight trails maximize profits? Loose trails catch big moves?

#### 4. **Partial Exit R-Multiples** ✅ NEW
- `partial_1_r`: R-multiple for first partial (e.g., 2.0 = take 50% @ 2R)
- `partial_2_r`: R-multiple for second partial (e.g., 3.0 = take 30% @ 3R)
- `partial_3_r`: R-multiple for runner exit (e.g., 5.0 = exit runner @ 5R)
- **Learns**: When to take profits (2R vs 2.5R vs 3R+)
- **Analysis**: Which R-multiples capture the most profit without giving back?

#### 5. **Partial Exit Percentages** ✅ NEW
- `partial_1_pct`: How much to exit first time (e.g., 0.50 = 50%)
- `partial_2_pct`: How much to exit second time (e.g., 0.30 = 30%)
- `partial_3_pct`: How much to leave as runner (e.g., 0.20 = 20%)
- **Learns**: Aggressive (70% @ 2R) vs Patient (40% @ 2.5R) scaling
- **Analysis**: Does aggressive scaling lock in profits? Does patient scaling catch runners?

#### 6. **Sideways/Stalling Timeout** ✅ NEW
- `sideways_timeout_minutes`: Exit runner if no progress for X minutes
- **Learns**: When to give up on stalled runners (10 min vs 20 min vs 30 min)
- **Analysis**: Do stalled runners eventually run? Or do they reverse?

#### 7. **Runner Hold Criteria** ✅ NEW
- `runner_hold_criteria.min_r_multiple`: Minimum R-multiple to justify holding (e.g., 6.0)
- `runner_hold_criteria.min_duration_minutes`: Minimum time to hold runner (e.g., 30 min)
- `runner_hold_criteria.max_drawdown_pct`: Max drawdown before exit (e.g., 0.25 = 25%)
- **Learns**: When to let runners run vs exit early
- **Analysis**: Do 6R+ runners justify the hold time? Do drawdowns predict reversals?

---

## Learning Algorithm Functions

### Core Learning Functions

1. **`update_learned_parameters()`** - Main learning orchestrator
   - Calls all sub-learning functions
   - Groups outcomes by regime
   - Updates learned parameters every 3 exits

2. **`_learn_partial_exit_params()`** - Learns partial exit R-multiples and percentages
   - Analyzes early (2R), mid (2.5R), late (3R+) partial timing
   - Compares aggressive (60%+) vs patient (40%-) scaling
   - Adjusts toward best-performing strategy

3. **`_learn_sideways_timeout()`** - Learns sideways timeout
   - Finds trades with runners (3R+)
   - Compares quick winners (<15min) vs slow winners (>20min) vs stalled losers
   - Tightens timeout if stalled trades lose, loosens if slow winners profit

4. **`_learn_runner_hold_criteria()`** ✅ NEW - Learns runner hold criteria
   - Analyzes high (6R+), med (4-6R), low (3-4R) runners
   - Compares long holds (30+ min) vs short holds (<20 min)
   - Tightens max drawdown if high-drawdown trades lose
   - Adjusts min R-multiple and min duration toward best outcomes

5. **`_learn_scaling_strategies()`** - Learns from market context
   - Analyzes aggressive vs patient scaling in different conditions
   - Tracks when 70%+ @ 2R works best (choppy, high RSI, afternoon)
   - Tracks when holding past 3R works best (trending, high volume)

6. **`_learn_from_market_patterns()`** - Learns from market context
   - Analyzes RSI, volume, time-of-day patterns
   - Learns when tight exits work (high RSI, choppy)
   - Learns when loose exits work (trending, high volume)

---

## What the Bot Learns Per Regime

### Example: `HIGH_VOL_TRENDING` Regime

```python
'HIGH_VOL_TRENDING': {
    # Stop/BE/Trail management
    'breakeven_mult': 0.85,  # Quick BE in volatile trends
    'trailing_mult': 1.1,    # Loose trail to let trends run
    'stop_mult': 4.2,        # Wide initial stop for volatility
    
    # Partial exit R-multiples (WHEN to take profits)
    'partial_1_r': 2.5,      # First partial @ 2.5R (let it run more)
    'partial_2_r': 4.0,      # Second partial @ 4R
    'partial_3_r': 6.0,      # Runner exit @ 6R
    
    # Partial exit percentages (HOW MUCH to take)
    'partial_1_pct': 0.40,   # Take 40% first (patient scaling)
    'partial_2_pct': 0.30,   # Take 30% second
    'partial_3_pct': 0.30,   # Leave 30% as runner
    
    # Sideways timeout (WHEN to give up)
    'sideways_timeout_minutes': 20,  # Give trends time to develop
    
    # Runner hold criteria (WHEN to let it run)
    'runner_hold_criteria': {
        'min_r_multiple': 8.0,           # Target 8R+ in trending markets
        'min_duration_minutes': 40,      # Hold for 40+ min
        'max_drawdown_pct': 0.20         # Tight 20% max drawdown
    }
}
```

---

## How It Learns

### Data Collection
- Every trade exit saves:
  - Exit parameters used (stops, BE, trail, partials, timeout)
  - Trade outcome (P&L, R-multiple, duration, exit reason)
  - Market context (RSI, volume, time, regime, streak, ATR)
  - Partial exit decisions (when, how much, at what R)
  - Runner behavior (duration, drawdown, final R-multiple)

### Analysis (Every 3 Exits)
- Groups trades by regime (HIGH_VOL_TRENDING, LOW_VOL_CHOPPY, etc.)
- Compares outcomes:
  - **Early vs late partials**: Did 2R partials work better than 3R?
  - **Aggressive vs patient scaling**: Did 70% @ 2R beat 40% @ 2.5R?
  - **Quick vs slow holds**: Did 30+ min holds justify the wait?
  - **High vs low R targets**: Did 8R+ runners beat 4-6R runners?
  - **Tight vs loose drawdowns**: Did 25% drawdown predict reversals?

### Adjustment
- Moves learned parameters 10% toward best-performing strategy
- Clamps to reasonable ranges (e.g., `partial_1_r` between 1.5-3.5)
- Logs insights: "AGGRESSIVE scaling better in CHOPPY markets"
- Adapts over time as market conditions change

---

## Cloud Learning Pool

If `cloud_api_url` is configured:
- **Saves** every exit to cloud pool (shared across all bots)
- **Fetches** 10,000+ community experiences on startup
- **Learns** from collective wisdom of all traders
- **Re-learns** every 3 exits with updated pool

---

## Summary: Complete Trade Management

The exit RL system now learns **EVERYTHING** about trade management:

✅ **Initial Risk**: How wide should stops be?  
✅ **Protection**: When to move to breakeven?  
✅ **Profit Capture**: When to take partials? (2R vs 2.5R vs 3R)  
✅ **Position Sizing**: How much to exit? (50% vs 40% vs 70%)  
✅ **Runner Management**: When to let it run? (6R target vs 8R)  
✅ **Timeout Logic**: When to give up on stalled trades? (10 min vs 20 min)  
✅ **Drawdown Control**: Max drawdown before exit? (20% vs 25% vs 30%)  
✅ **Trailing Strategy**: How tight to trail profits? (tight vs loose)  

**Result**: Fully adaptive exit system that learns optimal trade management for every market regime.

---

## Files Modified

1. **`src/adaptive_exits.py`**
   - Added `runner_hold_criteria` to all regime definitions
   - Implemented `_learn_runner_hold_criteria()` function
   - Updated `update_learned_parameters()` to call new learning function
   - Now learns 7 categories of exit parameters (was 3)

---

## Next Steps

The exit RL system is now **COMPLETE**. It learns:
- ✅ Stop loss distances
- ✅ Breakeven timing
- ✅ Trailing stop distances
- ✅ Partial exit R-multiples
- ✅ Partial exit percentages
- ✅ Sideways timeout
- ✅ Runner hold criteria

**The bot will continuously improve its trade management as it learns from every exit.**
