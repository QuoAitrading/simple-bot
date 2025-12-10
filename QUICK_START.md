# Quick Start Guide - RL Backtest Updates

## What Changed?

This update improves the RL (Reinforcement Learning) backtesting system with:

1. **Sample Size: 10 → 20** - More robust confidence calculations
2. **Confidence Threshold: 70%** - High-quality trade selection
3. **Exploration Rate: 30%** - Balanced learning and exploitation
4. **Automated Backtest Loop** - Runs until learning converges

## Verify Changes

Run the verification script to confirm all changes are correct:

```bash
cd /home/runner/work/simple-bot/simple-bot
python dev/verify_rl_updates.py
```

Expected output:
```
✅ ALL VERIFICATIONS PASSED!

Summary of Verified Changes:
  ✅ Sample size: 10 → 20
  ✅ Confidence threshold: 70% (0.7)
  ✅ Exploration rate: 30% (0.3)
  ✅ Continuous backtest runner created
  ✅ Documentation complete
```

## Run a Single Backtest

Test the new configuration with a single backtest:

```bash
cd /home/runner/work/simple-bot/simple-bot
python dev/run_backtest.py --days 2 --symbol ES --log-level WARNING
```

Look for these indicators in the output:

1. **Sample Size = 20**:
   ```
   [RL Confidence] 44.4% - 20 similar: 55% WR, $6 avg
   ```

2. **Confidence Threshold = 70%**:
   ```
   RL Confidence Threshold: 70.0%
   [RL Decision Check] Confidence 40.1% vs Threshold 70.0% = FAIL
   ```

3. **Exploration Rate = 30%**:
   ```
   RL Exploration Rate: 30.0%
   [RL Decision] ✅ EXPLORATION TRADE (was rejected but exploring)
   ```

4. **Experiences Logged**:
   ```
   Saving RL experiences...
   [OK] Signal RL experiences saved to experiences/ES/signal_experience.json
      Total experiences: 12757
      New experiences this backtest: 31
   ```

## Run Continuous Backtest Loop (Advanced)

To collect all unique experiences from ES data until convergence:

```bash
cd /home/runner/work/simple-bot/simple-bot
python dev/run_full_backtest_loop.py
```

This will:
- Run backtest iteration 1 (30 days)
- Run backtest iteration 2 (60 days)
- Run backtest iteration 3 (90 days)
- Continue until 3 consecutive iterations add 0 new experiences
- Report final convergence and total experience count

**Note**: This can take considerable time depending on available data.

## Configuration

All settings are in `config.json`:

```json
{
  "rl_confidence_threshold": 0.7,  // 70% confidence required
  "rl_exploration_rate": 0.3       // 30% exploration rate
}
```

## What to Expect

### With 70% Confidence Threshold

Most signals will be **rejected** because they don't meet the high confidence bar:

```
[RL Decision Check] Confidence 40.1% vs Threshold 70.0% = FAIL
[RL Decision] ❌ TRADE REJECTED (confidence < threshold)
```

Only high-quality setups with strong historical performance will **pass**:

```
[RL Confidence] 72.5% - 20 similar: 80% WR, $150 avg
[RL Decision Check] Confidence 72.5% vs Threshold 70.0% = PASS
[RL Decision] ✅ TRADE APPROVED (confidence > threshold)
```

### With 30% Exploration Rate

Approximately 30% of rejected trades will be taken for exploration:

```
[RL Decision Check] Confidence 50.2% vs Threshold 70.0% = FAIL
[RL Decision] ✅ EXPLORATION TRADE (was rejected but exploring)
```

This allows the system to:
- Discover new profitable patterns
- Prevent over-fitting to existing data
- Continue learning during backtests

### With 20 Sample Size

Each confidence calculation uses 20 most similar historical trades:

```
[RL Confidence] 44.4% - 20 similar: 55% WR, $6 avg
```

This provides:
- More stable win rate estimates
- Better statistical significance
- Reduced variance in confidence scores
- More reliable pattern matching

## Files Modified

1. **src/signal_confidence.py** - Core RL confidence calculation logic
2. **dev/run_full_backtest_loop.py** - New continuous backtest runner
3. **dev/verify_rl_updates.py** - Verification script

## Documentation

See `BACKTEST_RL_UPDATES.md` for complete technical documentation.

## Troubleshooting

**Q: Verification script fails?**
A: Check that you're in the correct directory and all files are committed.

**Q: Backtest shows different sample size?**
A: Check that you're running the latest code. Run `git status` to confirm.

**Q: Too many trades being rejected?**
A: This is expected with 70% confidence threshold. Only ~30% exploration trades will be taken.

**Q: Continuous loop takes too long?**
A: You can stop it at any time (Ctrl+C). Experiences are saved after each iteration.

## Next Steps

1. ✅ Run verification script to confirm changes
2. ✅ Run single backtest to test configuration
3. ⏱️ Run continuous loop to collect all experiences (optional, takes time)
4. 📊 Review backtest results and RL performance
5. 🚀 Deploy to live trading with trained RL brain

---

**Summary**: All requested changes have been successfully implemented and verified. The RL system now uses 20 samples for confidence calculations, requires 70% confidence for trade approval, and explores 30% of rejected trades to continue learning.
