# Session Locking Fix - Implementation Summary

## Problem Statement

The user reported issues with API key session management:

1. **Session conflicts appearing at runtime instead of login** - Users would start the bot successfully, but then get session conflict errors 30+ seconds later during runtime
2. **Stale sessions not clearing** - When a device crashed or was turned off, the session would remain "active" on the server, preventing the same device from logging back in
3. **Inconsistent behavior** - Sometimes the bot would allow login, other times it would reject with "session already in use"
4. **Poor user experience** - Errors appeared during trading (runtime) instead of at the login screen where users expect them

## Root Causes Identified

### 1. Launcher Didn't Send Device Fingerprint
**Problem**: The GUI launcher (`QuoTrading_Launcher.py`) validated the license key but didn't send a device fingerprint to the server. This meant:
- Server couldn't detect if another device was using the license during launcher validation
- Session conflicts only detected later when the bot engine started (which does send device fingerprint)
- Users saw "validation successful" in launcher, then session conflict error 30 seconds later

**Fix**: Added `get_device_fingerprint()` function to launcher and included it in all license validation requests.

### 2. Inconsistent Session Timeout Thresholds
**Problem**: Different endpoints used different thresholds to determine if a session was "active":
- `/api/main`: 120 seconds (2 minutes)
- `/api/validate-license`: 30 seconds
- `/api/heartbeat`: 30 seconds
- `/api/session/clear`: 30 seconds

This caused confusing behavior where a session would be considered "active" in one place but "stale" in another.

**Fix**: Introduced `SESSION_TIMEOUT_SECONDS = 90` constant (3 missed heartbeats) and used it consistently across all endpoints.

### 3. No Automatic Stale Session Cleanup
**Problem**: When a device crashed, lost internet, or was force-closed, its session would remain in the database. The next login attempt would fail with "session already in use" even though no device was actually active.

**Fix**: All validation endpoints (`/api/main`, `/api/validate-license`) now automatically clear stale sessions (>90 seconds old) BEFORE checking for conflicts. This prevents false positives.

### 4. SQL Injection Vulnerability
**Problem**: The INTERVAL clause used string formatting which could be vulnerable to SQL injection:
```sql
-- Vulnerable
WHERE last_heartbeat < NOW() - INTERVAL '%s seconds'
```

**Fix**: Used PostgreSQL's `make_interval()` function with proper parameterization:
```sql
-- Safe
WHERE last_heartbeat < NOW() - make_interval(secs => %s)
```

## Implementation Details

### Server-Side Changes (cloud-api/flask-api/app.py)

1. **Added SESSION_TIMEOUT_SECONDS constant** (line 54):
```python
SESSION_TIMEOUT_SECONDS = 90  # 3 missed heartbeats
```

2. **Auto-clear stale sessions in /api/validate-license** (lines 1162-1174):
```python
# First, automatically clear stale sessions
cursor.execute("""
    UPDATE users 
    SET device_fingerprint = NULL, last_heartbeat = NULL
    WHERE license_key = %s 
    AND last_heartbeat < NOW() - make_interval(secs => %s)
""", (license_key, SESSION_TIMEOUT_SECONDS))
```

3. **Auto-clear stale sessions in /api/main** (lines 1467-1478):
Same logic as /api/validate-license - clears stale sessions before checking for conflicts.

4. **Consistent timeout in /api/heartbeat** (line 1281):
```python
if time_since_last < timedelta(seconds=SESSION_TIMEOUT_SECONDS):
```

5. **Fixed /api/session/clear** to use 90-second threshold (line 1417).

### Client-Side Changes (launcher/QuoTrading_Launcher.py)

1. **Added device fingerprint function** (lines 45-80):
```python
def get_device_fingerprint() -> str:
    # Uses MAC address, username, and platform
    # Returns SHA256 hash for privacy
    ...
```

2. **Updated license validation** (lines 442-444):
```python
response = requests.post(
    f"{api_url}/api/main",
    json={
        "license_key": api_key,
        "device_fingerprint": get_device_fingerprint()
    },
    timeout=10
)
```

3. **Added session conflict handling** (lines 485-495):
```python
if error_data.get("session_conflict"):
    error_msg = (
        "LICENSE ALREADY IN USE\n\n"
        "Your license key is currently active on another device.\n"
        "..."
        "wait 90 seconds and try again."
    )
```

### Bot Engine (src/quotrading_engine.py)

No changes needed - already properly implements:
- Device fingerprint generation and sending
- Session conflict detection at startup
- Session conflict detection during runtime (heartbeat)
- Graceful handling (emergency stop, not exit)

## How It Works Now

### Scenario 1: Normal Login (Single Device)
1. User opens launcher and enters license key
2. Launcher calls `/api/main` with device_fingerprint
3. Server auto-clears any stale sessions (>90s old)
4. Server checks for active sessions (<90s old) - finds none
5. Server updates device_fingerprint and last_heartbeat
6. **✅ Login succeeds**
7. Bot starts and sends heartbeats every 30 seconds

### Scenario 2: Device Crash and Restart (Same Device)
1. Bot crashes on Device A at T=0 (no cleanup, session not released)
2. User restarts bot immediately at T=10 seconds
3. Launcher calls `/api/main` with same device_fingerprint
4. Server checks last_heartbeat (10 seconds ago) < 90 seconds
5. Server sees same device_fingerprint, allows it
6. **✅ Login succeeds** (same device can always reconnect)

### Scenario 3: Stale Session (Device Offline)
1. Bot crashes on Device A at T=0
2. User waits 100 seconds
3. User tries to login from Device A (or Device B)
4. Launcher calls `/api/main` with device_fingerprint
5. Server auto-clears session (100s > 90s threshold)
6. Server checks for active sessions - finds none after clearing
7. **✅ Login succeeds** (stale session auto-cleared)

### Scenario 4: Active Conflict (Two Devices)
1. Bot running on Device A, sent heartbeat 20 seconds ago
2. User tries to login from Device B
3. Launcher calls `/api/main` with different device_fingerprint
4. Server auto-clears sessions >90s old (none found)
5. Server checks for active sessions (<90s old) - finds Device A (20s ago)
6. Server sees different device_fingerprint
7. **❌ Login blocked at launcher with clear error message**
8. User sees: "LICENSE ALREADY IN USE - Please stop the bot on the other device first"
9. Bot never starts, error appears immediately

### Scenario 5: Runtime Conflict (Session Stolen)
1. Bot running on Device A
2. Device A loses internet for 95 seconds (no heartbeats)
3. User starts bot on Device B (session is stale, login succeeds)
4. Device A internet returns, tries to send heartbeat
5. Server receives heartbeat from Device A with old device_fingerprint
6. Server sees Device B has active session (different fingerprint, <90s)
7. **❌ Server returns 403 with session_conflict=true**
8. Bot on Device A detects conflict, disconnects broker, enters emergency stop
9. Bot shows: "LICENSE ALREADY IN USE - Bot will remain ON but IDLE"

## Testing

### Automated Tests
- `test_session_locking.py` - Verifies implementation correctness
- All 5 tests passing:
  1. Device Fingerprint Generation
  2. Session Conflict Detection in Heartbeat
  3. Heartbeat Scheduling (30s)
  4. Symbol-Specific RL Folders
  5. Server-Side Session Locking

### Manual Test Scenarios
See `SESSION_LOCKING_TEST_SCENARIOS.md` for 8 comprehensive test scenarios.

## Security Improvements

1. **SQL Injection Prevention**: All INTERVAL clauses now use `make_interval(secs => %s)` instead of string formatting
2. **Session Hijacking Prevention**: Device fingerprint ensures sessions can't be stolen
3. **Privacy**: Device fingerprints are hashed (SHA256) before sending to server

## Benefits

### For Users
✅ **Session conflicts detected at LOGIN SCREEN** - No more surprises during trading
✅ **Automatic stale session cleanup** - No manual intervention needed
✅ **Clear error messages** - Users know exactly what's wrong and how to fix it
✅ **Fast recovery** - Can restart after 90 seconds instead of waiting indefinitely

### For Support Team
✅ **Fewer support tickets** - Users understand the error and can self-resolve
✅ **Better logging** - Server logs show exactly what device tried to connect when
✅ **Consistent behavior** - Same timeout threshold everywhere

### For System Integrity
✅ **No license sharing** - Only one device can use a license at a time
✅ **No false positives** - Stale sessions don't block legitimate users
✅ **Graceful degradation** - Runtime conflicts handled without crashing

## Configuration

All endpoints now use `SESSION_TIMEOUT_SECONDS = 90` seconds:
- **Heartbeat interval**: 30 seconds (sent by bot)
- **Session timeout**: 90 seconds (3 missed heartbeats)
- **This means**: If a device goes offline, after 90 seconds it's considered "stale"

## Migration Notes

**No database migration needed** - Uses existing columns:
- `users.device_fingerprint` (already exists)
- `users.last_heartbeat` (already exists)

**No breaking changes** - All changes are backward compatible.

## Monitoring

Server logs now include:
- `🧹 Auto-cleared N stale session(s)` - When stale sessions are cleared
- `⚠️ Session conflict for {license_key}` - When login blocked due to active session
- `⚠️ Runtime session conflict` - When heartbeat blocked due to active session
- `✅ License validated for device {fingerprint}` - Successful validations

## Future Enhancements

Potential improvements (not implemented):
1. Admin dashboard to view active sessions and force-disconnect
2. Email notifications when session conflict detected
3. Configurable timeout per license type (e.g., premium gets 60s, standard gets 90s)
4. Session history tracking in database
