# Heartbeat Session Timer Fix

## Issue
Heartbeats sent every 20 seconds were not properly resetting the 60-second session timer, allowing multiple concurrent logins with the same API key after 60 seconds.

## Root Cause
The heartbeat endpoint (`/api/heartbeat`) had two critical issues:

1. **Missing table initialization**: The `ensure_active_sessions_table()` function was not called before attempting to use the `active_sessions` table.
   - If the table didn't exist (e.g., after server restart or database migration), the session update would fail silently
   - The error was caught and logged, but the heartbeat endpoint still returned HTTP 200 (success)

2. **No error propagation**: The return value of `create_or_update_symbol_session()` was not checked.
   - When the function returned `False` (indicating failure), the endpoint didn't detect it
   - This made debugging very difficult as the client thought the heartbeat succeeded

## Fix
Added two defensive programming improvements:

### 1. Table Existence Check (Line 1636-1637)
```python
if symbol and MULTI_SYMBOL_SESSIONS_ENABLED:
    # Ensure active_sessions table exists
    ensure_active_sessions_table(conn)
```

This ensures the `active_sessions` table is created before any operations that depend on it. While the table should already exist from the initial login (`/api/validate-license`), this adds defense-in-depth.

### 2. Error Checking (Line 1656-1666)
```python
session_updated = create_or_update_symbol_session(
    conn, license_key, symbol, device_fingerprint,
    metadata=data.get('metadata', {})
)

if not session_updated:
    logging.error(f"Failed to update session for {license_key}/{symbol}")
    return jsonify({
        "status": "error",
        "message": "Failed to update session"
    }), 500
```

Now the endpoint checks if the session update succeeded and returns HTTP 500 if it fails. This allows:
- The bot to detect failures and potentially retry
- Server admins to see errors in logs
- Monitoring systems to alert on failures

## How Heartbeat Session Reset Works

### Normal Flow (After Fix)
```
T=0s:   Bot calls /api/validate-license
        → Creates session with last_heartbeat = T0
        → Session expires at T60

T=20s:  Bot sends heartbeat
        → Updates last_heartbeat = T20  
        → Session now expires at T80

T=40s:  Bot sends heartbeat
        → Updates last_heartbeat = T40
        → Session now expires at T100

T=60s:  Bot sends heartbeat
        → Updates last_heartbeat = T60
        → Session now expires at T120

T=61s:  Another device tries to login
        → Checks last_heartbeat = T60 (1 second ago)
        → Since 1s < 60s, session is still active
        → Login BLOCKED ✅
```

### Expired Session (No Heartbeat)
```
T=0s:   Bot calls /api/validate-license
        → Creates session with last_heartbeat = T0
        → Session expires at T60

T=61s:  Another device tries to login
        → Checks last_heartbeat = T0 (61 seconds ago)
        → Since 61s > 60s, session has expired
        → Old session cleaned up
        → Login ALLOWED ✅
```

## Testing
To verify the fix:

1. **Start bot and monitor heartbeats**:
   ```bash
   # Watch server logs
   tail -f /var/log/quotrading-api.log | grep heartbeat
   ```
   You should see heartbeats every 20 seconds with no errors.

2. **Test concurrent login prevention**:
   - Start bot on Device A
   - After 61+ seconds of continuous heartbeats
   - Try to login on Device B with same license key
   - Expected: Session conflict error
   - If Device B is allowed to login, the fix didn't work

3. **Test session expiration**:
   - Start bot on Device A
   - Stop the bot (no more heartbeats)
   - Wait 61 seconds
   - Try to login on Device B with same license key
   - Expected: Login successful
   - If Device B gets session conflict, the timer isn't expiring

## Impact
- **Risk**: Very low - changes are defensive and don't modify core logic
- **Compatibility**: Fully backward compatible
- **Performance**: Negligible - adds one table check and one conditional
- **Debugging**: Greatly improved - failures are now visible

## Rollback Plan
If issues arise, revert to commit `7cbd883`:
```bash
git revert HEAD
git push origin copilot/fix-heartbeat-session-reset
```

## Related Code
- `/api/heartbeat`: Heartbeat endpoint (lines 1592-1781)
- `create_or_update_symbol_session()`: Session update function (lines 1265-1286)
- `check_symbol_session_conflict()`: Session conflict checker (lines 1202-1262)
- `ensure_active_sessions_table()`: Table creator (lines 1164-1200)
- `SESSION_TIMEOUT_SECONDS`: Session timeout constant (line 67)

## References
- Issue: "every 20 secs heartbeat is not resetting session timer"
- Fix PR: #XXX (to be filled in)
- Related: Multi-symbol session support (MULTI_SYMBOL_SESSIONS_ENABLED)
