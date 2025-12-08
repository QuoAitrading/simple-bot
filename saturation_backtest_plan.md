# Multi-Symbol Saturation Backtest Plan

## Objective
Run saturation backtests for all 4 symbols (ES, MES, NQ, MNQ) with the NEW regime configuration until no new experiences can be added.

## Symbols to Process
1. **ES** (E-mini S&P 500) - Currently: 703 experiences
2. **MES** (Micro E-mini S&P 500) - Currently: 535 experiences
3. **NQ** (E-mini NASDAQ-100) - Currently: 57 experiences
4. **MNQ** (Micro E-mini NASDAQ-100) - Currently: 36 experiences

## Configuration

### NEW Regime Filter (Active)
✅ **Trading Allowed**:
- HIGH_VOL_CHOPPY
- NORMAL_CHOPPY
- NORMAL
- LOW_VOL_RANGING

❌ **Trading Blocked**:
- HIGH_VOL_TRENDING
- NORMAL_TRENDING
- LOW_VOL_TRENDING

### RL Parameters
- **Exploration Rate**: 30% (0.30)
- **Confidence Threshold**: 70% (0.70)
- **Max Iterations**: 100 per symbol
- **Stop Condition**: 3 consecutive iterations with 0 new experiences

## Process

### Script: `dev/run_all_symbols_saturation.py`

The script will:
1. Run saturation backtest for each symbol sequentially
2. For each symbol:
   - Load symbol-specific configuration (tick size, tick value)
   - Load existing RL experiences from `experiences/{SYMBOL}/signal_experience.json`
   - Run backtest iterations until saturation
   - Save updated experiences after each iteration
   - Stop when no new experiences are added for 3 consecutive iterations

### Individual Symbol Command
```bash
python dev/run_saturation_backtest.py --symbol ES
python dev/run_saturation_backtest.py --symbol MES
python dev/run_saturation_backtest.py --symbol NQ
python dev/run_saturation_backtest.py --symbol MNQ
```

### All Symbols at Once
```bash
python dev/run_all_symbols_saturation.py
```

## Expected Outcomes

### Per Symbol
Each symbol will have:
- **Saturated RL experiences**: Maximum unique patterns discovered
- **Symbol-specific file**: `experiences/{SYMBOL}/signal_experience.json`
- **Proper configuration**: Each RL uses correct symbol specs (tick size/value)
- **Quality data**: Only experiences from NEW tradeable regimes added going forward

### Verification
After completion, verify:
1. Each symbol has dedicated experience file
2. No duplicate experiences in any file
3. New experiences only from tradeable regimes
4. Each symbol's RL loads correctly in live trading

## Expected Duration

Approximate time per symbol:
- **ES**: 5-15 iterations × 60s = 5-15 minutes
- **MES**: 5-15 iterations × 60s = 5-15 minutes  
- **NQ**: 10-20 iterations × 60s = 10-20 minutes (fewer experiences currently)
- **MNQ**: 10-20 iterations × 60s = 10-20 minutes (fewer experiences currently)

**Total estimated time**: 30-70 minutes for all 4 symbols

## Post-Saturation State

After saturation, each symbol will have:
- Maximum pattern diversity discovered from historical data
- Only high-quality, non-duplicate experiences
- Ready for live trading with optimized RL decision-making
- NEW regime filter ensuring only reversal-friendly environments are traded

## Monitoring Progress

During execution, you'll see:
```
Iteration 1/100: +15 new experiences (total: 718)
Iteration 2/100: +8 new experiences (total: 726)
Iteration 3/100: +3 new experiences (total: 729)
...
Iteration 15/100: +0 new experiences (total: 745)
Iteration 16/100: +0 new experiences (total: 745)
Iteration 17/100: +0 new experiences (total: 745)

✓ Saturation reached - no new experiences for 3 consecutive iterations
```

## Next Steps

1. Run `python dev/run_all_symbols_saturation.py`
2. Monitor progress for each symbol
3. Verify completion and experience counts
4. Ready for live trading with optimized, saturated RL for all symbols
