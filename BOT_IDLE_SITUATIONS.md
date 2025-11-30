# Bot Idle Situations - Complete Coverage

This document lists ALL situations where the bot goes IDLE and how they're handled.

## Idle Situations Covered

### 1. ✅ Maintenance Window (Mon-Thu 4:45-6:00 PM ET)
**When:** Monday through Thursday, 4:45 PM - 6:00 PM ET
**Behavior:**
- Bot flattens all positions at 4:45 PM
- Disconnects broker/websocket
- Shows: "[IDLE MODE] MAINTENANCE - GOING IDLE"
- Periodic message: "[IDLE] MAINTENANCE IN PROGRESS" (every 5 min)
- Auto-reconnects at 6:00 PM ET
- Daily limits reset at 6:00 PM ET
**Code:** Lines 740-790 in `quotrading_engine.py`

### 2. ✅ Weekend (Fri 4:45 PM - Sun 6:00 PM ET)
**When:** Friday 4:45 PM through Sunday 6:00 PM ET
**Behavior:**
- Bot flattens all positions Friday at 4:45 PM
- Disconnects broker/websocket
- Shows: "[IDLE MODE] WEEKEND - GOING IDLE"
- Periodic message: "[IDLE] WEEKEND IN PROGRESS" (every 5 min)
- Auto-reconnects Sunday at 6:00 PM ET
**Code:** Lines 740-790 in `quotrading_engine.py`

### 3. ✅ License Expired (During Trading)
**When:** License expires while bot is running
**Behavior:**
- Bot flattens any open positions (grace period)
- Disconnects broker/websocket completely
- Shows: "LICENSE EXPIRED - Stopping all trading and market data"
- Shows: "Websocket disconnected - No data streaming"
- Shows: "LICENSE EXPIRED - Please renew your license"
- Bot stays ON but IDLE (no exit)
**Code:** Lines 6074-6089, 7836-7848 in `quotrading_engine.py`

### 4. ✅ Expired License on Startup
**When:** User tries to start bot with expired license
**Behavior:**
- Shows clear error: "INVALID OR EXPIRED LICENSE - Bot will not start"
- Shows: "Your license has expired. Please renew to continue trading."
- Exits immediately (before any trading starts)
- User CANNOT start bot with expired license
**Code:** Lines 449-462 in `quotrading_engine.py`

### 5. ✅ Session Conflict (License in use on another device)
**When:** License key is active on another device
**Behavior:**
- Shows: "LICENSE ALREADY IN USE"
- Disconnects broker/websocket
- Bot stays ON but IDLE
- Shows: "Press Ctrl+C to stop bot"
**Code:** Lines 7934-7965, 7970-8010 in `quotrading_engine.py`

### 6. ✅ License Conflict (403 response)
**When:** Server detects license conflict
**Behavior:**
- Shows: "LICENSE ALREADY IN USE"
- Disconnects broker/websocket
- Bot stays ON but IDLE
- Shows: "Press Ctrl+C to stop bot"
**Code:** Lines 7970-8010 in `quotrading_engine.py`

### 7. ✅ Daily Loss Limit Hit
**When:** Daily P&L reaches user's configured loss limit
**Behavior:**
- Stops new trades (existing positions can close)
- Bot stays running (does NOT disconnect)
- Shows: "Daily loss limit hit"
- Auto-resumes next day at 6:00 PM ET
**Code:** Lines 2413-2429, 6377-6404 in `quotrading_engine.py`

### 8. ✅ Max Trades Per Day Reached
**When:** Daily trade count reaches user's limit
**Behavior:**
- Stops new trades
- Bot stays running
- Shows: "Daily trade limit reached"
- Auto-resumes next day at 6:00 PM ET
**Code:** Lines 2377-2392 in `quotrading_engine.py`

### 9. ✅ Emergency Stop (Overnight Position Detected)
**When:** Position detected past 4:45 PM ET (shouldn't happen)
**Behavior:**
- Emergency flatten at market
- Sets emergency_stop flag
- Bot stays running but stops trading
**Code:** Lines 6674-6697 in `quotrading_engine.py`

### 10. ✅ Data Feed Timeout
**When:** No tick data received for extended period
**Behavior:**
- Sets stop_reason = "data_feed_timeout"
- Bot stays running
- Stops new trades
**Code:** Lines 6460-6476 in `quotrading_engine.py`

### 11. ✅ Stop Order Placement Failed
**When:** Critical stop order can't be placed
**Behavior:**
- Sets emergency_stop flag
- Prevents new trades
- Bot stays running
**Code:** Lines 3960-3963 in `quotrading_engine.py`

## What Bot Does in IDLE Mode

**All Idle Modes:**
1. Bot process stays running (never exits unless Ctrl+C)
2. Shows clear status message
3. Checks periodically for resume condition
4. Shows "Press Ctrl+C to stop bot"

**License/Session Issues:**
- Disconnects websocket/broker completely
- Stops all data streaming
- Shows clear error message with reason

**Time-Based (Maintenance/Weekend):**
- Disconnects to save resources
- Auto-reconnects when market reopens
- Resets daily limits at 6:00 PM ET

**Limit-Based (Daily Loss/Trade Count):**
- Keeps connection active
- Just blocks new trades
- Auto-resumes next trading day

## Summary

✅ **11 Different Idle Situations Covered**
✅ **All Have Clear Messages**
✅ **Bot Never Exits (Except Startup License Validation)**
✅ **All Auto-Resume When Appropriate**
✅ **Websocket Disconnects When Needed**
✅ **No Kill Switch (Removed)**

## Missing Situations?

If there are any other situations not covered here, they should be implemented with:
1. Clear logging message explaining why idle
2. Proper bot_status flags set
3. Either disconnect broker (time-based) or keep connection (limit-based)
4. Auto-resume condition when applicable
5. "Press Ctrl+C to stop bot" message
