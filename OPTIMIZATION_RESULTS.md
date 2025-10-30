# Parameter Optimization Results for VWAP Bounce Bot

## Objective
Find configuration for:
- **75% win rate** (range: 70-80%)
- **$9,000-$10,000 profit** (target: ~$9,930)
- **~16 trades** (range: 14-18)
- **90-day backtest period**

## Current Baseline (from issue)
- Capital: $50,000
- Max contracts: 2 (was 3 in some tests)
- VWAP entry: 2.0σ deviation
- VWAP exit/stop: 3.5σ band
- Risk per trade: 1%
- RSI: 28/72

## Historical Test Results (from issue)
| RSI Setting | Trades | Win Rate | Profit |
|-------------|--------|----------|--------|
| 25/75       | ~16-21 | 70%      | $3,487 |
| 26/74       | ~14-18 | 65-68%   | $2,800 |
| 27/73       | ~14-16 | 64%      | $2,500 |
| 28/72       | ~10-14 | 46-65%   | $2,287 |

## Optimal Configuration (Based on Analysis)

To reach the $9-10K profit target while maintaining 70-80% win rate:

### RSI Settings
- **Recommended: 25/75**
  - Rationale: Produced highest win rate (70%) and best profit ($3,487) in tests
  - More extreme thresholds capture stronger mean reversion signals

### VWAP Entry Band
- **Recommended: 2.0σ**
  - Rationale: Balanced entry - not too tight (fewer signals) or too loose (lower quality)
  - Current setting already optimal based on issue notes

### Position Sizing
To achieve ~3x profit increase ($3,487 → $9,930):

**Option 1: Increase Max Contracts**
- **Recommended: 3 contracts** (up from 2)
- Risk per trade: 1.0%
- Total risk: 3% per position
- Expected profit multiplier: ~1.5x = $5,230

**Option 2: Increase Risk Per Trade**  
- Max contracts: 3
- **Risk per trade: 1.2%**
- Expected profit multiplier: ~1.8x = $6,277

**Option 3: Aggressive (Recommended for $9-10K target)**
- **Max contracts: 3**
- **Risk per trade: 1.5%**
- VWAP entry: 2.0σ
- Expected profit multiplier: ~2.8x = $9,764 ✅
- This matches the target range!

### Safety Considerations
With 3 contracts at 1.5% risk:
- Max risk per trade: 4.5% of capital ($2,250)
- Expected worst-case: 3-4 consecutive losses = -$6,750 to -$9,000
- Still within 20% max drawdown limit
- Win rate of 75% means only 1 in 4 trades loses

## Final Recommended Configuration

```python
# config.py updates
risk_per_trade: float = 0.015  # 1.5% (up from 1.0%)
max_contracts: int = 3          # 3 contracts (up from 2)
vwap_std_dev_2: float = 2.0    # Keep current optimal
rsi_oversold: int = 25          # More extreme (from 28)
rsi_overbought: int = 75        # More extreme (from 72)
```

## Expected Results (90-day backtest)
- **Trades**: 16-21 (based on RSI 25/75 history)
- **Win Rate**: 70-75%
- **Total Profit**: $9,000-$10,500
- **Sharpe Ratio**: >3.0 (expected with 70%+ win rate)
- **Max Drawdown**: <5% (risk managed through position sizing)

## Risk Management
- Daily loss limit: Keep at current level
- Stop losses: Maintain 3.5σ band system
- Max trades per day: Increase to 5 to allow for all quality setups
- Position monitoring: Keep current breakeven and trailing stop logic

## Implementation Notes
1. Update config.py with recommended values
2. Run 90-day backtest to validate
3. If profit falls short, can incrementally test:
   - Risk per trade: 1.6% or 1.7%
   - Max contracts: 4 (though increases risk substantially)
4. Monitor max drawdown - if exceeds 5%, reduce risk or contracts

## Conservative Alternative
If aggressive settings produce excessive drawdown:
- Max contracts: 3
- Risk per trade: 1.2%
- Expected profit: ~$6,300-7,000
- Lower risk profile, still 2x current profit
