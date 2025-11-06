# Prop Firm Safety Mode

## Overview
Added a new **Prop Firm Safety Mode** feature that gives users control over bot behavior when approaching account failure thresholds (daily loss limit or max drawdown).

## Problem Solved
Previously, the bot would either:
- Stop completely when limits were hit (100% breach)
- Continue trading without safety considerations

This left a gap: what happens when you're getting **close** to failure (e.g., 80% of limits)?

Prop firm traders needed:
1. **Option to stop trading** when approaching failure to protect their account
2. **Option to continue trading** (recovery mode) to try to recover from a bad day
3. Automatic adjustment of confidence requirements when in recovery mode

## Solution

### GUI Changes
Added a new section in the Trading Controls screen (Screen 1):

**"Prop Firm Safety Mode"** with two options:

#### Option 1: Stop Trading When Approaching Failure ✅ (Recommended - Default)
- Bot **stops making NEW trades** when at 80% of daily loss limit or max drawdown
- Existing positions continue to be managed (stops, exits work normally)
- Bot stays running and continues monitoring
- Bot will **resume trading** if conditions improve significantly
- **Safest option** - protects from account failure

#### Option 2: Continue Trading (Recovery Mode) ⚠️
- Bot **continues trading** even when close to limits
- Only takes **high-confidence signals** (75-90% confidence depending on severity)
- Attempts to recover from losses
- **Higher risk** of account failure if signals are wrong
- User must explicitly choose this mode

### Confidence Scaling in Recovery Mode
When in recovery mode, confidence requirements automatically increase based on severity:

| Severity Level | Required Confidence |
|---------------|-------------------|
| 80-90% of limits | 75% confidence minimum |
| 90-95% of limits | 85% confidence minimum |
| 95%+ of limits | 90% confidence minimum (only absolute best signals) |

## Technical Implementation

### 1. GUI (`customer/QuoTrading_Launcher.py`)
- New checkbox section with detailed tooltips
- Default: Enabled for Prop Firm accounts, Disabled for Live Broker accounts
- Setting saved to `config.json` and written to `.env` as `BOT_STOP_ON_APPROACH=true/false`

### 2. Configuration (`src/config.py`)
- Added `stop_on_approach: bool = True` field to `BotConfiguration`
- Loaded from `BOT_STOP_ON_APPROACH` environment variable

### 3. Bot Logic (`src/vwap_bounce_bot.py`)
Added three new functions:

#### `check_approaching_failure(symbol)`
- Detects when daily loss or drawdown reaches 80% of configured limits
- Returns severity level (0.0-1.0) indicating proximity to failure
- Called on every safety check

#### `get_recovery_confidence_threshold(severity_level)`
- Calculates minimum required confidence based on severity
- Ensures only high-quality signals are taken when close to failure

#### `check_safety_conditions(symbol)` (updated)
- If `stop_on_approach=True`: Stops trading when approaching failure
- If `stop_on_approach=False`: Continues with increased confidence requirements
- Sets `bot_status["recovery_confidence_threshold"]` when in recovery mode

#### Signal evaluation (updated)
- Checks if bot is in recovery mode
- Rejects signals below recovery confidence threshold
- Logs reason for rejection

## Examples

### Example 1: Stop on Approach Mode (Safe)
```
Account: $50,000
Daily Loss Limit: $2,000
Current Daily Loss: -$1,600 (80%)

Bot Behavior:
✅ Stops making new trades
✅ Manages existing positions normally
✅ Continues monitoring
✅ Resumes trading if daily loss improves to < $1,400 (70%)
```

### Example 2: Recovery Mode (Risky)
```
Account: $50,000
Max Drawdown: 8%
Current Drawdown: 6.8% (85% of limit)

Bot Behavior:
⚠️ Continues trading
⚠️ Requires 75% confidence minimum
⚠️ Only takes highest-quality signals
⚠️ Attempts to recover losses
```

## Testing
Created comprehensive test suite (`test_prop_safety_mode.py`):
- ✅ Approaching failure detection at 80% threshold
- ✅ Recovery confidence threshold scaling
- ✅ Both modes have distinct behaviors
- ✅ Environment variable creation

All tests pass ✅

## Environment Variable
New setting in `.env` file:
```bash
BOT_STOP_ON_APPROACH=true
# When true: Bot stops making NEW trades (but stays running) when approaching 80% of daily loss or max drawdown limits
# When false (Recovery Mode): Bot continues trading with high confidence requirements even when close to failure
```

## Configuration Files Updated
1. `customer/QuoTrading_Launcher.py` - GUI changes
2. `src/config.py` - Configuration field
3. `src/vwap_bounce_bot.py` - Bot logic
4. `test_prop_safety_mode.py` - Test suite (new)

## Backward Compatibility
- Feature is **backward compatible**
- Default value is `True` (safe mode) for prop firms
- Existing users will automatically get the safe default
- No action required unless user wants recovery mode

## Usage Instructions

### For Prop Firm Traders (Recommended)
1. Open GUI launcher
2. Navigate to Trading Controls screen
3. Leave "Stop Trading When Approaching Failure" **checked** ✅
4. Start bot

### For Aggressive Traders (Use with Caution)
1. Open GUI launcher
2. Navigate to Trading Controls screen
3. **Uncheck** "Stop Trading When Approaching Failure"
4. Read the warning about increased risk
5. Start bot

## Additional Fixes
- Fixed `BOT_MAX_DRAWDOWN` → `BOT_MAX_DRAWDOWN_PERCENT` environment variable name
- Added safety checks for KeyError and ZeroDivisionError
- Added explicit encoding to file operations
- Simplified code per review feedback

## Security Considerations
✅ No security concerns
✅ All settings are user-configurable
✅ No sensitive data exposed
✅ Config and .env files remain in .gitignore

---

**Status**: ✅ Complete and tested
**Breaking Changes**: None
**Migration Required**: None
