# Dashboard Display Feature

## Overview

The bot now features a **fixed dashboard display** that updates in place without scrolling. This provides a clean, professional view of the bot's status and trading activity.

## Features

### Header Section
- **Bot Version**: Shows "QuoTrading AI Bot v2.0"
- **Server Status**: Connection status and latency (✓ 45ms)
- **Account Balance**: Real-time account balance display

### Active Settings Section
- Max Contracts per symbol
- Daily Loss Limit
- Confidence Mode (Standard or Confidence Trading with threshold)
- Recovery Mode status (Enabled/Disabled)

### Symbol Sections (Dynamic)
Each selected symbol gets its own section showing:

#### Market Information
- **Market Status**: OPEN, CLOSED, or FLATTEN
- **Maintenance Countdown**: Time until next maintenance window (e.g., "4h 23m")

#### Live Quotes
- **Bid**: Bid price and size (e.g., "$6785.25 x 50")
- **Ask**: Ask price and size (e.g., "$6785.50 x 48")
- **Spread**: Current bid-ask spread

#### Market Condition
- **Condition Assessment**: 
  - "NORMAL - Tight spread, good liquidity" (spread ≤ $0.50)
  - "NORMAL - Good liquidity" (spread ≤ $1.00)
  - "CAUTION - Wider spread" (spread ≤ $2.00)
  - "WARNING - Wide spread, low liquidity" (spread > $2.00)

#### Position Status
- **Position**: Current position (FLAT, LONG X, SHORT X)
- **P&L Today**: Today's profit/loss for this symbol

#### Trading Activity
- **Last Signal**: Most recent trading signal
- **Status**: Current bot activity (e.g., "Monitoring...", "In trade", "Trade closed")

## Display Behavior

### Updates In Place
- The dashboard updates in place using ANSI escape codes
- **No scrolling** - the display refreshes at the same screen position
- Updates occur every 100 ticks (approximately 1-2 seconds in active markets)

### Multi-Symbol Support
- Shows only the symbols selected in settings
- If user selects MES only → shows only MES section
- If user selects MES + NQ → shows both sections
- Supports up to 12 symbols simultaneously

### Cross-Platform Compatibility
- **Windows**: Works with PowerShell (Windows 10+)
- **Linux**: Works with standard terminals
- **macOS**: Works with Terminal.app

## Technical Implementation

### Dashboard Module (`src/dashboard.py`)
- Self-contained dashboard display class
- Platform detection for Windows/Linux/macOS
- ANSI escape code support for cursor control
- Singleton pattern for global access

### Integration Points
1. **Bot Startup**: Dashboard initialized with selected symbols
2. **Tick Handler**: Dashboard refreshed every 100 ticks
3. **Position Changes**: Dashboard updated when positions open/close
4. **Exit Handler**: Dashboard updated when trades exit
5. **Shutdown**: Dashboard cleanup on bot shutdown

### Update Frequency
- **Quote Data**: Every 100 ticks (~1-2 seconds)
- **Position Data**: Immediately on position changes
- **P&L Data**: Real-time with position updates
- **Market Status**: Every time check event

## Example Display

```
============================================================
QuoTrading AI Bot v2.0 | Server: ✓ 45ms | Account: $50,092
============================================================

Active Settings:
  Max Contracts: 3 per symbol
  Daily Loss Limit: $1,000
  Confidence Mode: Standard (65%)
  Recovery Mode: Enabled

============================================================
MES | Micro E-mini S&P 500
============================================================
Market: OPEN | Maintenance in: 3h 45m
Bid: $6785.23 x 50 | Ask: $6785.48 x 48 | Spread: $0.25
Condition: NORMAL - Tight spread, good liquidity
Position: LONG 3 | P&L Today: $62.50
Last Signal: LONG @ $6785.25
Status: In trade - Target: $6795.25
============================================================

============================================================
NQ | E-mini Nasdaq
============================================================
Market: OPEN | Maintenance in: 3h 45m
Bid: $21450.17 x 30 | Ask: $21450.42 x 28 | Spread: $0.25
Condition: NORMAL - Good liquidity
Position: FLAT | P&L Today: $30.00
Last Signal: LONG @ $21450.25
Status: Monitoring...
============================================================
```

## Benefits

1. **Professional Appearance**: Clean, organized display
2. **No Log Spam**: Updates in place instead of scrolling
3. **Real-Time Monitoring**: Always see current status at a glance
4. **Multi-Symbol Tracking**: Monitor multiple symbols simultaneously
5. **Quick Reference**: All key metrics in one view

## Future Enhancements

Potential improvements for future versions:
- Color coding for profit/loss
- Historical P&L chart
- Win rate statistics
- Trade count for the day
- Signal strength indicators
