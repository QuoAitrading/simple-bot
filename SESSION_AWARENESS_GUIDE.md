# Session Awareness & Smart Guidance - Implementation Summary

## Overview
Comprehensive session awareness system that remembers bot performance across restarts and provides intelligent guidance to prevent account failure.

## Problem Solved
Users were:
1. Losing track of bot performance when GUI closed
2. Not aware they were approaching account failure
3. Having to manually calculate risk settings
4. Getting locked out when close to limits
5. Not getting prop firm-specific guidance

## Solution Implemented

### 1. Session State Manager (`src/session_state.py`)

**What It Does:**
- Tracks all trading activity across sessions
- Persists to `data/session_state.json` (survives restarts)
- Auto-detects account type (prop firm vs live broker)
- Calculates severity levels (how close to failure)

**Data Tracked:**
```python
{
  "trading_date": "2025-11-06",
  "starting_equity": 50000.00,
  "current_equity": 48400.00,
  "peak_equity": 51200.00,
  "daily_pnl": -1600.00,
  "daily_trades": 8,
  "current_drawdown_percent": 3.2,
  "daily_loss_percent": 3.2,
  "approaching_failure": true,
  "in_recovery_mode": false,
  "account_type": "prop_firm",
  "broker": "TopStep"
}
```

### 2. Smart Warnings on GUI Launch

**When Warnings Show:**
- **Critical (95%+)**: Red alert with auto-apply settings
- **Warning (80-95%)**: Orange warning with recommendations
- **Info (<80%)**: Green - all good

**Example Warning (Critical):**
```
⚠️ CRITICAL: At 95% of account limits! Account failure imminent!

📋 RECOMMENDATIONS:
• 🔄 RECOMMEND: Enable Recovery Mode to attempt recovery
• 📊 RECOMMEND: Increase confidence threshold to 85% (currently 65%)
• 📉 RECOMMEND: Reduce contracts to 1 (currently 3)

⚙️ Would you like to apply recommended settings automatically?
[Yes] [No]
```

**Example Warning (Approaching):**
```
📊 Session Status:

⚠️ WARNING: Approaching limits (82% of max). Consider enabling Recovery Mode.

💡 RECOMMENDATIONS:
• 📊 RECOMMEND: Increase confidence threshold to 75% (currently 65%)
• 📉 RECOMMEND: Reduce contracts to 2 (currently 3)
• 💡 SUGGEST: Set daily loss limit to $1000 (2% rule for TopStep)

⚙️ Apply recommended settings?
[Yes] [No]
```

### 3. Auto-Calculated Recommendations

**Confidence Scaling:**
- 80-90% severity → 75% confidence (selective)
- 90-95% severity → 85% confidence (very selective)
- 95%+ severity → 90% confidence (only best signals)

**Contract Reduction:**
- 80-90% severity → 75% of normal size
- 90-95% severity → 50% of normal size
- 95%+ severity → 33% of normal size

**Prop Firm Specifics:**
- Auto-calculates 2% daily loss rule
- Recommends trailing drawdown
- Stricter guidance overall

### 4. Smart Position Management

**When Severity Hits 95%+:**
```python
# Bot checks if current position is losing
if severity >= 0.95 and has_active_position:
    if position_is_losing:
        # Flag for aggressive exit management
        bot_status["aggressive_exit_mode"] = True
        logger.warning("Critical severity with losing position")
        logger.warning("Considering early exit to prevent account failure")
```

**Key Feature:** Bot NEVER hard-locks user out. Recovery mode is always available.

### 5. One-Click Apply Settings

**User Experience:**
1. User launches GUI
2. Warning appears: "At 85% of limits"
3. Recommendations shown:
   - Confidence: 65% → 75%
   - Contracts: 3 → 2
   - Daily loss: $2000 → $1000
4. User clicks "Yes"
5. All settings applied instantly
6. User can trade with safer settings

### 6. Account Type Detection

**Auto-Detects Prop Firms:**
- TopStep
- Apex
- Earn2Trade
- FTMO
- The5ers

**Prop Firm Benefits:**
- 2% daily loss auto-calculated
- Stricter warnings
- Trailing drawdown recommended
- Account failure prevention prioritized

**Live Broker:**
- More flexible recommendations
- User has more control
- Still gets warnings but less strict

## Technical Implementation

### GUI Integration (`customer/QuoTrading_Launcher.py`)

```python
def __init__(self):
    # ... existing code ...
    
    # Initialize session state manager
    from session_state import SessionStateManager
    self.session_manager = SessionStateManager()

def setup_trading_screen(self):
    # Check session and show warnings
    if self.session_manager:
        self._show_session_warnings()

def _show_session_warnings(self):
    # Get warnings and recommendations
    warnings, recommendations, smart_settings = \
        self.session_manager.check_warnings_and_recommendations(...)
    
    # Show dialog with one-click apply
    if warnings and smart_settings:
        result = messagebox.askyesno("Warning", warning_text)
        if result:
            self._apply_smart_settings(smart_settings)
```

### Bot Integration (`src/vwap_bounce_bot.py`)

```python
def main():
    # Initialize session manager
    from session_state import SessionStateManager
    session_manager = SessionStateManager()

def on_position_close():
    # Update session after every trade
    if session_manager:
        session_manager.update_trading_state(
            starting_equity=...,
            current_equity=...,
            daily_pnl=...,
            daily_trades=...,
            broker=CONFIG["broker"]
        )

def check_safety_conditions():
    # Smart position management at critical severity
    if severity >= 0.95 and position_is_losing:
        bot_status["aggressive_exit_mode"] = True
```

## User Benefits

### For Prop Firm Traders
1. **Never Fail Account**: Warnings before it's too late
2. **Auto-Calculated Limits**: Bot knows the 2% rule
3. **Smart Guidance**: Prop firm-specific recommendations
4. **One-Click Safety**: Apply all recommendations instantly
5. **Session Memory**: Bot remembers yesterday's performance

### For Live Broker Traders
1. **Flexible Control**: Less strict but still safe
2. **Performance Tracking**: Know your daily P&L across restarts
3. **Smart Recommendations**: Still get guidance when needed
4. **Never Locked Out**: Can always trade (your money, your choice)

### For All Users
1. **Session Awareness**: Bot remembers everything
2. **Smart Warnings**: Know when you're in danger
3. **Auto-Recommendations**: No math required
4. **One-Click Apply**: Easy to use
5. **Account Protection**: Prevent failures

## Configuration Examples

### Safe Mode (Recovery Disabled) - Default
```
Daily Loss: -$1600 / $2000 (80%)
→ Bot STOPS making new trades
→ Existing positions managed normally
→ Resumes after daily reset
→ User gets warning on next launch
```

### Recovery Mode (Enabled) at 85% Severity
```
Daily Loss: -$1700 / $2000 (85%)
→ Bot CONTINUES trading
→ Confidence: 65% → 75% (auto)
→ Contracts: 3 → 2 (auto)
→ Only takes best signals
→ Attempts recovery
```

### Critical Severity (95%+) with Losing Position
```
Daily Loss: -$1900 / $2000 (95%)
Current Position: LONG, down $200
→ Bot flags for aggressive exit
→ Position managed aggressively
→ Early exit likely
→ Prevents account failure
```

## Files Modified

1. **`src/session_state.py`** (NEW - 330 lines)
   - SessionStateManager class
   - JSON persistence
   - Warning/recommendation generation
   - Account type detection

2. **`customer/QuoTrading_Launcher.py`** (+100 lines)
   - Session manager initialization
   - `_show_session_warnings()` method
   - `_apply_smart_settings()` helper
   - Warning dialogs

3. **`src/vwap_bounce_bot.py`** (+40 lines)
   - Session manager integration
   - State updates after trades
   - Smart position management
   - Aggressive exit mode flag

## Testing Checklist

- ✅ Session state persists across restarts
- ✅ Warnings show on GUI launch
- ✅ Recommendations are accurate
- ✅ One-click apply works
- ✅ Account type detection correct
- ✅ Prop firm rules applied
- ✅ Smart position management works
- ✅ Never locks out user
- ✅ No syntax errors
- ✅ No security vulnerabilities (CodeQL clean)

## Constants Defined

```python
# Prop firm detection
PROP_FIRM_NAMES = ["topstep", "apex", "earn2trade", "ftmo", "the5ers"]
PROP_FIRM_DAILY_LOSS_PERCENT = 0.02

# Severity thresholds
SEVERITY_HIGH = 0.90
SEVERITY_MODERATE = 0.80

# Confidence recommendations
CONFIDENCE_THRESHOLD_HIGH = 85.0
CONFIDENCE_THRESHOLD_MODERATE = 75.0

# Contract reductions
CONTRACT_MULTIPLIER_CRITICAL = 0.33
CONTRACT_MULTIPLIER_HIGH = 0.50
CONTRACT_MULTIPLIER_MODERATE = 0.75
```

## Future Enhancements

Potential improvements:
1. Email/SMS alerts when approaching failure
2. Historical performance charts in GUI
3. ML-based recommendation tuning
4. Multi-timeframe analysis
5. Broker-specific rule templates

## Conclusion

This implementation provides comprehensive session awareness and intelligent guidance that:
- Prevents account failures
- Provides smart recommendations
- Works across sessions
- Is account-type aware
- Never locks users out
- Applies settings with one click

Users now have a "smart assistant" that helps them navigate risky situations and make better decisions.
