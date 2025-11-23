# License Expiration Handling

## Overview

The QuoTrading bot includes automatic license expiration detection with **intelligent grace period handling** for active positions. When a customer's API key (license) expires, the bot will:

1. **If position is active**: Enter grace period mode and allow the position to close naturally
2. **If no position**: Stop trading immediately

This ensures customers never have positions abandoned mid-trade, preventing unnecessary losses.

## How It Works

### Periodic License Validation

- The bot checks license validity **every 5 minutes** during trading hours
- Validates against the cloud API to ensure the license is still active
- Does not stop trading on temporary network errors (continues to retry)

### Grace Period for Active Positions

**The Problem**: Immediately stopping trading when a license expires could abandon active positions, causing losses.

**The Solution**: When a license expires during an active trade:

1. **Grace Period Activates**
   - Bot continues managing the current position
   - Uses normal exit rules (target/stop/time-based)
   - Blocks NEW trade entries
   - Shows message: "License expired. Closing position safely before stopping..."

2. **Position Closes Naturally**
   - Bot manages position until it hits target, stop, or time exit
   - Could be 5 minutes or 2 hours depending on trade
   - Safest approach for the customer

3. **Trading Stops After Position Closes**
   - Once position is flat, trading is disabled
   - Emergency stop flag is set
   - Customer receives notification with final P&L

### Graceful Shutdown Strategy

When a license expiration is detected, the bot chooses the best approach:

#### 1. **Grace Period** (Active Position)
- **When**: License expires while position is open
- **Action**: 
  - Continue managing position with normal exit rules
  - Block new trade entries
  - Send grace period notification
  - Wait for position to close naturally (target/stop/time)
  - After position closes: Disable trading and send final notification

#### 2. **Immediate Stop** (No Position)
- **When**: License expires with no active position
- **Action**:
  - Immediately disable new trade entries
  - Send notification alert
  - Log expiration reason

#### 3. **Friday Market Close** (Delayed)
- **When**: Expires on Friday before market close (before 5:00 PM ET)
- **Action**:
  - Continue trading until Friday market close (5:00 PM ET)
  - Close any positions at market close
  - Disable trading for the weekend

#### 4. **Maintenance Window** (Delayed)
- **When**: Expires during flatten mode (4:45-5:00 PM ET, Monday-Thursday)
- **Action**:
  - Wait until maintenance window starts (5:00 PM ET)
  - Close positions with other daily maintenance activities
  - Minimizes disruption during active trading

## Example Scenarios

**Scenario 1: Expires Wednesday 2 PM with Active Position (GRACE PERIOD)**
```
14:00 - License check detects expiration
14:00 - Position is ACTIVE (LONG 1 @ $5000)
14:00 - Enter GRACE PERIOD mode
14:00 - Block new trades
14:00 - Send grace period notification
14:00-14:30 - Continue managing position
14:30 - Position hits target at $5025
14:30 - Close position (+$25 profit)
14:30 - Grace period ends
14:30 - Disable trading
14:30 - Send final notification
```

**Scenario 2: Expires Wednesday 2 PM with No Position (IMMEDIATE STOP)**
```
14:00 - License check detects expiration
14:00 - No active position
14:00 - Disable trading immediately
14:00 - Send notification
```

**Scenario 3: Expires Friday 3 PM (DELAYED STOP)**
```
15:00 - License check detects expiration
15:00 - Flag set: stop_at_market_close
15:00-17:00 - Continue trading normally
17:00 - Market closes, close any positions
17:00 - Disable trading
17:00 - Send notification
```

## Customer Impact

### Benefits of Grace Period
- **No Abandoned Positions**: Position always closes via normal exit rules
- **No Forced Market Exits**: Uses target/stop/time-based exits (not panic market orders)
- **Protects Customer P&L**: Prevents losses from premature forced exits
- **Professional Handling**: Manages positions safely and intelligently

### Clear Communication
- **Grace Period Alert**: Explains position is being managed until close
- **Final Alert**: Shows final P&L and confirms trading stopped
- **Logging**: Clear messages about grace period status

## Testing

Run the test suites to validate expiration and grace period handling:

```bash
# Test grace period logic
python tests/test_grace_period.py

# Test expiration timing
python tests/test_expiration_simple.py
```

All scenarios are tested for correctness.
