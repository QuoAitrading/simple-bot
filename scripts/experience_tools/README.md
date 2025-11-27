# Experience Management Tools

Scripts for managing and analyzing your bot's experience database.

## 📊 Analysis Scripts

### `check_duplicates.py`
Check for duplicate experiences in your database.
```bash
python scripts/experience_tools/check_duplicates.py
```
**When to use:** Verify data quality, check for duplicates after backtesting.

### `check_experience_fields.py`
Verify all 26 fields are present and complete in experiences.
```bash
python scripts/experience_tools/check_experience_fields.py
```
**When to use:** Validate data integrity, ensure no missing fields.

### `check_confidence_stats.py`
Analyze confidence distribution and performance by confidence level.
```bash
python scripts/experience_tools/check_confidence_stats.py
```
**When to use:** Understand confidence patterns, optimize threshold settings.

### `test_duplicate_prevention.py`
Test that duplicate prevention system is working correctly.
```bash
python scripts/experience_tools/test_duplicate_prevention.py
```
**When to use:** Verify duplicate prevention allows different outcomes at same timestamp.

## 🧹 Maintenance Scripts

### `cleanup_duplicates.py`
Remove all duplicate experiences from the database file.
```bash
python scripts/experience_tools/cleanup_duplicates.py
```
**When to use:** 
- After running multiple backtests on same data range
- If you suspect duplicates have accumulated
- **NOT needed for live trading** (auto-prevention works)

**Note:** Creates backup before cleaning (`signal_experience.json.before_cleanup`)

## 📝 Notes

- **Duplicate Key:** `(timestamp, symbol, pnl, exit_reason)`
- **Pattern Matching:** Uses 17 market state fields (RSI, VWAP, ATR, etc.)
- **Automatic Prevention:** Built-in during live trading - these are diagnostic tools only
- **Clean Database:** Currently 244 unique experiences from 82-day backtest

## ⚙️ Current Configuration

- **Confidence Threshold:** 40% (configurable in `data/config.json`)
- **Exploration Rate:** 30%
- **Max Stop Loss:** $300 (configurable from GUI)
- **Experience File:** `experiences/ES/signal_experience.json`
