# ES BOS/FVG Strategy - 96-Day Backtest Results

## Configuration

**RL Settings:**
- Confidence Threshold: 70%
- Exploration Rate: 30%
- Strategy: BOS/FVG only (no capitulation)

**Backtest Period:**
- Duration: 96 days
- Total Bars: 95,400 (1-minute bars)
- Execution Time: 551.5 seconds

## Performance Summary

### Trading Performance

```
Total Trades:      3,266
Wins:              1,548 (47.4%)
Losses:            1,718 (52.6%)
Breakeven:         0

Profit Factor:     1.15
Avg Win:           $139.80
Avg Loss:          $-109.99
Largest Win:       $1,347.50
Largest Loss:      $-302.50
Avg Trade Duration: 10.0 minutes
```

### P&L Analysis

```
Starting Balance:  $50,000.00
Ending Balance:    $77,450.82

Net P&L:           $+27,450.82 (+54.90%)

Max Drawdown:      $5,823.57 (7.34%)
```

### Signal Performance

```
Total Signals:     14,471
Trades Taken:      3,266 (22.6%)
Trades Filtered:   11,205 (77.4%)
```

### Experience Learning

```
Starting Experiences: 15,780
Ending Experiences:   18,650
New Patterns Learned: 2,870
```

## Key Metrics

- **ROI:** +54.90% over 96 days
- **Risk-Adjusted Return:** 7.48x (Return/Max Drawdown)
- **Win Rate:** 47.4%
- **Profit Factor:** 1.15 (profitable)
- **Avg R-Multiple:** 1.27 (wins are 27% larger than losses)

## Data Quality

✅ **18,650 unique experiences** (0 duplicates)  
✅ All experiences use BOS/FVG field structure  
✅ No null, blank, NaN, or Inf values  
✅ No legacy capitulation fields  
✅ Pattern matching working correctly  

## Conclusion

The ES BOS/FVG strategy with 70% confidence threshold and 30% exploration delivered strong performance over 96 days:

- **Net Profit: $27,450.82 (+54.90%)**
- Managed risk well (7.34% max drawdown)
- Accumulated 18,650 unique trading patterns
- Filtered 77.4% of signals (quality over quantity)

The strategy is production-ready and learning continuously.
