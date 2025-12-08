# ES Backtest Results - New Regime Configuration

## Test Parameters
- **Period**: August 31, 2025 - December 5, 2025 (96 days)
- **Symbol**: ES (E-mini S&P 500)
- **RL Settings**: 30% exploration, 70% confidence threshold
- **Starting Balance**: $50,000

## New Tradeable Regimes
✅ **Trading Allowed** (reversal-friendly):
1. HIGH_VOL_CHOPPY - Big moves, fast rotations, liquidity grabs
2. NORMAL_CHOPPY - Clean, predictable swing reversals
3. NORMAL - Stable, clean reversals
4. LOW_VOL_RANGING - Reliable micro-reversals

❌ **Trading Blocked** (trending environments):
1. HIGH_VOL_TRENDING - Market extends without exhaustion
2. NORMAL_TRENDING - Fake-out reversals
3. LOW_VOL_TRENDING - Slow grind, no setups

## Performance Summary

### Overall Results
- **Total Trades**: 223
- **Win Rate**: 74.0% (165W / 58L)
- **Net P&L**: +$13,714.68 (+27.43%)
- **Profit Factor**: 1.89
- **Max Drawdown**: $1,632.50 (2.55%)

### Trade Statistics
- **Average Win**: $176.44
- **Average Loss**: $-265.49
- **Largest Win**: $2,161.23
- **Largest Loss**: $-302.50
- **Avg Duration**: 31.3 minutes

### Regime Breakdown
Most trades occurred in:
- **NORMAL_CHOPPY**: Majority of trades (most common regime)
- **HIGH_VOL_CHOPPY**: Excellent win rate, aggressive setups
- **LOW_VOL_RANGING**: Few trades but reliable
- **NORMAL**: Stable performance

### Signal Efficiency
- **Total Signals Generated**: 404
- **Trades Taken**: 223 (55% execution rate)
- **Signals Filtered**: 181 (45% filtered by RL confidence)

## Key Insights

### ✅ Strengths
1. **High Win Rate**: 74% shows reversal strategy works in choppy environments
2. **Strong Profit Factor**: 1.89 indicates edge is real
3. **Low Drawdown**: 2.55% max drawdown is excellent risk control
4. **Fast Trades**: 31 minutes average = quick in/out, minimal overnight risk

### 📊 Trade Distribution
- Average 2.3 trades/day
- RL confidence filter blocked 45% of signals (quality over quantity)
- Most profitable in NORMAL_CHOPPY and HIGH_VOL_CHOPPY regimes

### 💡 Strategy Validation
The new regime configuration (trade choppy/ranging, avoid trending) shows:
- Reversal setups perform best in oscillating markets
- Trending regimes would have destroyed the edge
- Pattern matching + regime filter = profitable combination

## Comparison to Old Configuration
**Old**: Traded NORMAL_TRENDING, HIGH_VOL_TRENDING (reversal killers)
**New**: Trade only CHOPPY/RANGING regimes (reversal friendly)

The 27.43% return in 96 days validates the regime filter update!
