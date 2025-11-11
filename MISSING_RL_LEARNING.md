# Missing RL Learning in Backtest

## ❌ PROBLEM FOUND:

The backtest is **saving experiences to cloud** BUT **not updating local RL feature tracking**!

### What's Currently Happening:
✅ Saving signal experiences to cloud API
✅ Saving exit experiences to cloud API  
✅ Loading experiences from cloud for decision making
✅ Dual pattern matching working (Feature 3)

### What's MISSING:
❌ **Feature 1: Regime Win Rate Tracking** - `regime_win_rates` not being updated
❌ **Feature 2: Adverse Movement Tracker** - `adverse_movement_tracker` not being updated
❌ **Feature 6: Paused Regimes** - Bad regimes not being paused

## Why This Matters:

Without calling `record_outcome()`, the bot can't:
1. Track which regimes are losing (Feature 1)
2. Detect if setups go adverse immediately (Feature 2)
3. Pause bad regimes automatically (Feature 6)

## What Needs to be Added:

After each trade exits, need to call:

```python
# Update Signal RL tracking (Features 1, 2, 6)
signal_ml.record_outcome(
    state=active_trade.entry_state,
    took_trade=True,
    outcome={
        'win': total_pnl > 0,
        'pnl': total_pnl,
        'duration': duration,
        'exit_reason': exit_reason,
        'went_adverse_immediately': duration < 5 and total_pnl < 0
    },
    regime=active_trade.entry_state.get('regime', 'NORMAL')
)
```

This will:
- ✅ Update `regime_win_rates` for Feature 1
- ✅ Track `adverse_movement_tracker` for Feature 2
- ✅ Pause bad regimes for Feature 6
- ✅ Continue saving to cloud API (already working)

## Current State:

**Cloud Saving**: ✅ Working (6,880 → 6,885 experiences)
**Local RL Features**: ❌ Not updating during backtest
**Dual Pattern Matching**: ✅ Working (using cloud experiences)

**FIX NEEDED**: Add `record_outcome()` call in backtest after each trade
