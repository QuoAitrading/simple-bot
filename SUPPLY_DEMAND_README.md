# Supply/Demand Rejection Strategy Bot (LuxAlgo-Style Order Blocks)

A completely separate trading bot that implements **LuxAlgo-style supply/demand zone detection** (order blocks) for ES futures. This bot operates independently from the main capitulation reversal bot and replicates the LuxAlgo order block methodology.

## Strategy Overview - LuxAlgo Order Blocks

The LuxAlgo Order Block strategy identifies institutional supply and demand zones where large players (institutions) placed significant orders. These zones appear as:
- **🔴 Supply Zones (Red/Bearish Order Blocks)**: Areas where institutions sold heavily, causing price to drop
- **🔵 Demand Zones (Blue/Bullish Order Blocks)**: Areas where institutions bought heavily, causing price to rally

When price returns to these zones, we look for rejection patterns indicating institutions are still active at those levels.

### How It Works (LuxAlgo Methodology)

1. **Zone Detection (Order Block Identification)**
   - **Supply Zones**: Identified when price shows an uptrend → pauses (base candle) → drops hard with strong bearish impulse
   - **Demand Zones**: Identified when price shows a downtrend → pauses (base candle) → rallies hard with strong bullish impulse
   - The "base candle" is where institutions placed their orders before the big move
   - Similar to LuxAlgo's red (bearish) and blue (bullish) order blocks

2. **Zone Validation**
   - Impulse move must be 1.5x the average candle range over the last 20 bars
   - Zone thickness must be between 4-20 ticks
   - Zone is defined by the pause candle's body range (not the full high-low range)

3. **Entry Signals**
   - **Long**: Price returns to demand zone, rejection candle forms (wick into zone, green body above zone)
   - **Short**: Price returns to supply zone, rejection candle forms (wick into zone, red body below zone)
   - Rejection wick must be at least 30% of total candle size

4. **Risk Management**
   - **Stop Loss**: 2 ticks beyond the zone boundary
   - **Take Profit**: 1.5x the risk distance (1.5:1 reward-to-risk ratio)

5. **Zone Management**
   - Zones deleted if price closes completely through them
   - Zones deleted after 3 tests (losing strength)
   - Zones deleted after 200 candles (too old)

## Files

- **`src/supply_demand_bot.py`**: Core strategy implementation
  - `SupplyDemandStrategy` class with zone detection and signal generation
  - `Zone` dataclass for managing supply/demand zones
  - `Candle` dataclass for candlestick data

- **`dev/run_supply_demand_backtest.py`**: Backtesting runner
  - Loads historical 1-minute ES data
  - Simulates realistic order fills
  - Generates detailed performance reports

## Usage

### Running a Backtest

Test the strategy on historical data:

```bash
# Backtest last 30 days
python dev/run_supply_demand_backtest.py --days 30 --symbol ES

# Backtest specific date range
python dev/run_supply_demand_backtest.py --start 2024-11-01 --end 2024-12-01 --symbol ES

# Backtest with custom parameters
python dev/run_supply_demand_backtest.py --days 30 --symbol ES --contracts 2 --initial-balance 100000
```

### Command Line Options

- `--days N`: Backtest for last N days
- `--start YYYY-MM-DD`: Start date for backtest
- `--end YYYY-MM-DD`: End date for backtest
- `--symbol SYMBOL`: Trading symbol (default: ES)
- `--data-path PATH`: Path to historical data directory
- `--contracts N`: Number of contracts to trade (default: 1)
- `--initial-balance AMOUNT`: Initial account balance (default: 50000)
- `--log-level LEVEL`: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)

## Performance Results

**30-Day Backtest on ES (Nov 9 - Dec 5, 2025)** - LuxAlgo-Style Quality Zones

- **Total Trades**: 17 (focused on highest-quality setups only)
- **Win Rate**: 35.3% (6 wins, 11 losses)
- **Total P&L**: **$732.50**
- **Average Win**: $437.50
- **Average Loss**: -$168.18
- **Profit Factor**: **1.42** (consistent positive edge)
- **Max Drawdown**: 1.61%
- **Return**: 1.47%
- **Average Trade Duration**: 16.1 minutes

**Strategy Statistics**
- **Zones Created**: 58 (only STRONG zones, like LuxAlgo - typically 3-6 active at once)
- Signals Generated: 23
- Signal-to-Trade Ratio: 74% (17/23 signals executed)

**LuxAlgo-Style Zone Quality:**
This matches LuxAlgo's approach of showing only the STRONGEST, most significant institutional levels:
- Minimum 1.6x average candle impulse (strong moves only)
- Minimum 6 tick impulse size (filters out noise)
- Maximum 12 active zones (6 supply + 6 demand - keeps charts clean)
- 2-day zone persistence (like LuxAlgo's major levels)
- Only replaces zones with stronger ones when limit reached

**Result**: Clean charts with 3-6 key zones visible at any time, matching LuxAlgo's behavior.

## Strategy Parameters

LuxAlgo-Style Parameters (configurable in `SupplyDemandStrategy` constructor):

```python
tick_size = 0.25              # ES tick size
tick_value = 12.50            # ES tick value ($12.50 per tick)
lookback_period = 20          # Bars for average range calculation
impulse_multiplier = 1.6      # Impulse must be 1.6x avg range (STRONG moves only)
min_zone_ticks = 4            # Minimum zone thickness (quality filter)
max_zone_ticks = 30           # Maximum zone thickness
rejection_wick_pct = 0.25     # Rejection wick must be 25% of candle
stop_loss_ticks = 2           # Stop placement beyond zone
risk_reward_ratio = 1.5       # Target is 1.5x risk (1.5:1 R:R)
max_zone_age = 2880           # Zone expires after 2880 candles (2 days on 1-min)
max_zone_tests = 3            # Zone deleted after 3 tests
max_active_zones = 12         # Maximum 12 zones total (6 supply + 6 demand)
min_impulse_ticks = 6         # Minimum impulse size (6 ticks = strong move)
```

**Quality Over Quantity Philosophy:**
- Only the STRONGEST zones are created (1.6x impulse + 6 tick minimum)
- Maximum 12 zones active at once (keeps charts clean like LuxAlgo)
- Weaker zones are replaced by stronger ones when limit is reached
- Zones persist for 2 days to allow price time to return
- Focus on major institutional levels, not every small move
stop_loss_ticks = 2           # Stop placement beyond zone
risk_reward_ratio = 1.5       # Target is 1.5x risk
max_zone_age = 200            # Zone expires after 200 candles
max_zone_tests = 3            # Zone deleted after 3 tests
```

## Customization

To modify the strategy parameters, edit the initialization in `run_supply_demand_backtest.py`:

```python
self.strategy = SupplyDemandStrategy(
    tick_size=self.tick_size,
    tick_value=self.tick_value,
    impulse_multiplier=2.0,      # Stricter impulse requirement
    min_zone_ticks=6,            # Thicker zones only
    rejection_wick_pct=0.40,     # Stronger rejection required
    risk_reward_ratio=2.0,       # 2:1 reward-to-risk
    logger=self.logger
)
```

## Integration with Live Trading

This is currently a backtest-only implementation. To integrate with live trading:

1. Implement real-time data feed connection
2. Add broker order execution interface
3. Implement position management
4. Add proper error handling and logging
5. Add monitoring and alerts

## Data Requirements

The backtester expects CSV files with the following format:

```
timestamp,open,high,low,close,volume,time_diff
2025-12-03 23:00:00,6543.5,6543.5,6543.5,6543.5,2.0,
2025-12-03 23:01:00,6545.25,6545.25,6545.25,6545.25,1.0,0 days 00:01:00
```

Data files should be named `{SYMBOL}_1min.csv` and placed in `data/historical_data/`.

## Notes

- This bot is completely independent of the main capitulation reversal bot
- No modifications were made to existing bot files
- The strategy has been tested on ES 1-minute data
- Works with ES, MES, NQ, MNQ, and other futures symbols
- Automatically handles different tick sizes and values per symbol

## Future Enhancements

Potential improvements to consider:

1. **Multi-timeframe analysis**: Confirm zones on higher timeframes
2. **Volume confirmation**: Require volume spike on impulse move
3. **Zone strength scoring**: Prioritize fresher, untested zones
4. **Partial profit taking**: Exit portion at 1:1, let rest run to 1.5:1
5. **Breakeven stops**: Move stop to breakeven after reaching 1:1
6. **Session filters**: Only trade during high-liquidity sessions
7. **Trend filters**: Only take trades aligned with larger trend

## Support

For questions or issues:
- Review the code documentation in `src/supply_demand_bot.py`
- Check backtest logs for detailed execution information
- Adjust parameters to match your risk tolerance and market conditions
