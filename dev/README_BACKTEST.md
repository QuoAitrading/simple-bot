# Backtest Documentation

## Running Full Backtest for All Symbols

### Quick Start

Run a full saturation backtest for all 4 symbols (ES, MES, MNQ, NQ):

```bash
python dev/run_all_symbols_backtest.py
```

This will:
- Run backtests from first to last day of available historical data
- Use 100% exploration for first run (if < 10 experiences exist)
- Use 30% exploration for subsequent runs
- Set confidence threshold to 40%
- Save experiences in symbol-specific folders (`experiences/ES/`, `experiences/MES/`, etc.)
- Run until saturation (no new unique experiences added)

### Running Individual Symbol Backtest

To run saturation backtest for a single symbol:

```bash
# First run with 100% exploration
python dev/run_saturation_backtest.py --symbol ES --exploration 1.0 --max-iterations 50

# Subsequent runs with 30% exploration
python dev/run_saturation_backtest.py --symbol ES --exploration 0.30 --max-iterations 100
```

### Configuration

The backtest uses:
- **Confidence Threshold**: 40% (0.40) - configured in `run_saturation_backtest.py`
- **Exploration Rate**: 
  - First run: 100% (discovers initial experiences)
  - Subsequent runs: 30% (refines existing knowledge)
- **Date Range**: Automatically uses full range from historical data
- **Futures Hours**: Follows actual market hours from historical data (includes early closes, holidays, etc.)

### Experience Files

Each symbol has its own experience file:
- `experiences/ES/signal_experience.json`
- `experiences/MES/signal_experience.json`
- `experiences/MNQ/signal_experience.json`
- `experiences/NQ/signal_experience.json`

### 16-Field JSON Structure

Each experience contains 16 core fields for duplicate detection:

**Pattern Matching Fields (12):**
1. flush_size_ticks
2. flush_velocity
3. volume_climax_ratio
4. flush_direction
5. rsi
6. distance_from_flush_low
7. reversal_candle
8. no_new_extreme
9. vwap_distance_ticks
10. regime
11. session
12. hour

**Metadata Fields (4):**
13. symbol
14. timestamp
15. pnl
16. took_trade

Additional metadata fields may be present (mfe, mae, exit_reason, etc.) but these 16 core fields are used for duplicate prevention.

### Historical Data Requirements

The backtest expects 1-minute bar data in CSV format:
- Location: `data/historical_data/`
- Format: `{SYMBOL}_1min.csv`
- Required columns: timestamp, open, high, low, close, volume

Available symbols:
- **ES**: Full history available in data (95,760 bars, 84 trading days)
- **MES**: Full history available in data (58,057 bars, 51 trading days)
- **MNQ**: Full history available in data (60,872 bars, 53 trading days)
- **NQ**: Full history available in data (58,055 bars, 51 trading days)

*Note: Exact date ranges depend on your historical data files. The backtest automatically detects and uses the full range.*

### Understanding Results

After running the backtest, you'll see:
- Number of new experiences added per iteration
- Saturation status (when no new unique experiences are found)
- Total experiences in the database
- Win rate and other statistics in the experience file

Example output:
```
✓ Iteration   1:  930 →  945 (+15 new)
✓ Iteration   2:  945 →  952 (+ 7 new)
○ Iteration   3:  952 →  952 (+ 0 new)
✓ SATURATION REACHED after 3 consecutive iterations with 0 new experiences
```

### Troubleshooting

**No experiences added:**
- This is normal if the market conditions in the data don't trigger the bot's signal logic
- ES has 930 experiences showing the system works correctly
- MES, MNQ, NQ may have fewer signals due to different market characteristics or shorter data history

**Duplicate prevention:**
- The system uses hash-based duplicate detection on all 16 core fields
- Duplicate trades are automatically filtered out
- This ensures the experience database only contains unique market conditions

**Saturation:**
- Saturation is reached when the bot has seen all unique patterns in the historical data
- This is the desired end state for training
- Further iterations won't add new experiences until new market conditions are encountered
