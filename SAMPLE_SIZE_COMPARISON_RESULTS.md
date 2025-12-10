# Sample Size Comparison Test Results - 10 vs 20 Samples

## Test Configuration

**Test Date:** December 10, 2025  
**Symbol:** ES (E-mini S&P 500 Futures)  
**Period:** Full 96 days (August 31 - December 5, 2025)  
**Data:** Real ES futures with proper schedule (gaps, maintenance, holidays)  
**Confidence Threshold:** 70%  
**Exploration Rate:** 30%  
**Max Contracts:** 1  

**Important:** Both tests started from the same experience baseline (15,762 experiences) for fair comparison.

---

## Test Results

### TEST 1: 10-Sample Configuration

**Performance:**
- **Total Trades:** 3,222 (Wins: 1,552 | Losses: 1,670)
- **Win Rate:** 48.2%
- **Profit Factor:** 1.09
- **Avg Trade Duration:** 10.1 minutes

**P&L Analysis:**
- **Starting Balance:** $50,000.00
- **Ending Balance:** $67,313.42
- **Net P&L:** **+$17,313.42 (+34.63%)**
- **Avg Win:** $129.80
- **Avg Loss:** $-110.26
- **Largest Win:** $1,322.50
- **Largest Loss:** $-302.50

**Risk Metrics:**
- **Max Drawdown:** $4,459.43 (6.43%)

**Signal Performance:**
- **Total Signals:** 14,343
- **Trades Taken:** 3,222 (22.5%)
- **Trades Rejected:** 11,121 (77.5%)

**RL Learning:**
- **Starting Experiences:** 15,762
- **Ending Experiences:** 18,721
- **New Unique Experiences:** 2,959
- **Execution Time:** 612.1 seconds

---

### TEST 2: 20-Sample Configuration

**Performance:**
- **Total Trades:** 3,067 (Wins: 1,453 | Losses: 1,614)
- **Win Rate:** 47.4%
- **Profit Factor:** 1.09
- **Avg Trade Duration:** 10.1 minutes

**P&L Analysis:**
- **Starting Balance:** $50,000.00
- **Ending Balance:** $65,347.07
- **Net P&L:** **+$15,347.07 (+30.69%)**
- **Avg Win:** $130.17
- **Avg Loss:** $-107.68
- **Largest Win:** $1,197.50
- **Largest Loss:** $-302.50

**Risk Metrics:**
- **Max Drawdown:** $5,300.60 (7.88%)

**Signal Performance:**
- **Total Signals:** 14,380
- **Trades Taken:** 3,067 (21.3%)
- **Trades Rejected:** 11,313 (78.7%)

**RL Learning:**
- **Starting Experiences:** 15,762
- **Ending Experiences:** 18,512
- **New Unique Experiences:** 2,750
- **Execution Time:** 593.1 seconds

---

## Side-by-Side Comparison

| Metric | 10 Samples | 20 Samples | Difference |
|--------|-----------|-----------|------------|
| **Net P&L** | +$17,313.42 | +$15,347.07 | -$1,966.35 |
| **Return %** | +34.63% | +30.69% | -3.94% |
| **Total Trades** | 3,222 | 3,067 | -155 trades |
| **Win Rate** | 48.2% | 47.4% | -0.8% |
| **Profit Factor** | 1.09 | 1.09 | Same |
| **Avg Win** | $129.80 | $130.17 | +$0.37 |
| **Avg Loss** | -$110.26 | -$107.68 | +$2.58 (better) |
| **Max Drawdown** | 6.43% | 7.88% | +1.45% (worse) |
| **Signals Detected** | 14,343 | 14,380 | +37 |
| **Trade Rate** | 22.5% | 21.3% | -1.2% |
| **New Experiences** | 2,959 | 2,750 | -209 |
| **Execution Time** | 612.1s | 593.1s | -19.0s (faster) |

---

## Analysis

### Performance Comparison

**10-Sample Configuration Advantages:**
- ✅ **Higher P&L:** +$1,966.35 more profit (12.8% better)
- ✅ **More Trades:** 155 more trades executed (4.8% increase)
- ✅ **Better Win Rate:** 48.2% vs 47.4% (+0.8%)
- ✅ **Lower Drawdown:** 6.43% vs 7.88% (1.45% better)
- ✅ **More Learning:** 2,959 vs 2,750 new experiences (+7.6%)

**20-Sample Configuration Advantages:**
- ✅ **Better Avg Win:** $130.17 vs $129.80 (+$0.37)
- ✅ **Smaller Avg Loss:** -$107.68 vs -$110.26 (+$2.58 better)
- ✅ **Faster Execution:** 593.1s vs 612.1s (3.1% faster)
- ✅ **More Selective:** 21.3% vs 22.5% trade rate (1.2% fewer trades)

### Decision Quality

**10 Samples:**
- More aggressive trade selection (22.5% take rate)
- Higher volume of experiences collected
- Slightly higher win rate
- Better risk-adjusted returns (lower drawdown)

**20 Samples:**
- More conservative trade selection (21.3% take rate)
- Better loss control (smaller average loss)
- Slightly higher average win
- Stricter quality filter (more rejections)

### Statistical Significance

Both configurations showed:
- **Same Profit Factor:** 1.09 (consistent profitability)
- **Same Avg Duration:** 10.1 minutes (similar trade characteristics)
- **Same Max Loss:** $-302.50 (identical worst-case risk)
- **Positive Returns:** Both profitable with 30%+ returns

---

## Data Quality Verification

✅ **Real Market Data:**
- Both tests used identical ES futures 1-minute bars
- 95,400 bars processed (same dataset)
- Proper futures schedule with gaps, maintenance, weekends

✅ **No Fake/Duplicate Data:**
- All 2,959 experiences from 10-sample test are unique patterns
- All 2,750 experiences from 20-sample test are unique patterns
- Pattern-based deduplication working correctly
- No data pollution in either test

✅ **RL Decision Making:**
- Both tests: 70% confidence threshold enforced
- Both tests: 30% exploration rate active
- Both tests: RL controlling all trade approvals
- Both tests: Started from same baseline (15,762 experiences)

✅ **Fair Comparison:**
- Same starting point (experience file restored between tests)
- Same configuration (70/30 split)
- Same data (full 96 days)
- Same symbol (ES futures)
- Same contract size (1 contract)

---

## Conclusion

### Test 1 Winner: 10-Sample Configuration

The 10-sample configuration **outperformed** the 20-sample configuration by:
- **$1,966.35 more profit** (12.8% higher return)
- **155 more trades** executed
- **0.8% higher win rate**
- **1.45% lower maximum drawdown**

### Why 10 Samples Performed Better

1. **More Aggressive Learning:** With only 10 samples required, the system was more willing to take trades, leading to more opportunities and more learning experiences collected.

2. **Earlier Pattern Recognition:** The 10-sample threshold is reached faster (after 10 experiences vs 20), allowing the RL brain to start making informed decisions sooner.

3. **Higher Trade Volume:** More trades (3,222 vs 3,067) provided more opportunities to capture profitable moves, despite slightly higher losses on average.

4. **Better Risk Management:** Lower drawdown despite higher trade volume suggests the 10-sample system made better risk-adjusted decisions.

### When 20 Samples Might Be Better

The 20-sample configuration showed advantages in:
- **Quality over quantity:** Smaller average loss ($107.68 vs $110.26)
- **Selectivity:** More conservative with 1.2% fewer trades taken
- **Efficiency:** Faster execution time

This suggests 20 samples could be better for:
- More conservative trading styles
- Accounts with stricter risk limits
- Markets with higher transaction costs

### Recommendation

Based on this 96-day backtest comparison:

**For Maximum Profit:** Use **10 samples** - delivers higher returns with acceptable risk
**For Conservative Trading:** Use **20 samples** - more selective with better loss control

Both configurations are viable and profitable. The choice depends on trading objectives:
- **Aggressive growth:** 10 samples (+34.63% return)
- **Conservative growth:** 20 samples (+30.69% return)

---

## Technical Notes

**Configuration Files:**
- Both tests verified: `rl_confidence_threshold: 0.7`
- Both tests verified: `rl_exploration_rate: 0.3`
- Both tests verified: `max_contracts: 1`

**Execution Environment:**
- Python-based backtesting framework
- Full BOS+FVG strategy implementation
- Real-time RL decision making
- Proper futures trading hours enforcement

**Data Integrity:**
- Experience file backed up before tests
- Experience file restored between tests
- All new experiences are unique (hash-based deduplication)
- No artificial data or patterns
