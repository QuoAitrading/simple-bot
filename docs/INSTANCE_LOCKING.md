# Instance Locking System

## Overview
Prevents duplicate trading on the same account by implementing a file-based locking mechanism. Multiple GUI instances can run simultaneously, but each trading account can only be used by one bot at a time.

## How It Works

### Lock Mechanism
- **Lock Location**: `locks/account_{account_id}.lock`
- **Lock Created**: When "Start Bot" button is clicked
- **Lock Removed**: When GUI window is closed
- **Stale Detection**: Automatically removes locks from crashed processes

### Lock File Structure
```json
{
  "account_id": "123456",
  "pid": 12345,
  "created_at": "2025-11-09T14:30:00",
  "broker_username": "john_topstep"
}
```

## User Scenarios

### ✅ Allowed: Multiple Accounts, Same Credentials
User has 2 TopStep accounts under same login:
- **GUI Instance 1**: Trading Account A (ES strategy)
- **GUI Instance 2**: Trading Account B (NQ strategy)
- **Result**: ✅ Both run simultaneously, no conflict

### ✅ Allowed: Different Users, Different Credentials
Two users on same computer:
- **User A GUI**: Trading their Account 1
- **User B GUI**: Trading their Account 2
- **Result**: ✅ Both run simultaneously, separate lock files

### ❌ Prevented: Same Account, Duplicate Launch
User accidentally launches bot twice:
- **GUI Instance 1**: Trading Account A
- **GUI Instance 2**: Tries to trade Account A again
- **Result**: ❌ Error message, second instance blocked

## Error Messages

### Duplicate Account Error
```
❌ Account 'Combine 50K - $50,000.00' is already being traded!

Broker: john_topstep
Started: 2025-11-09T14:30:00

You cannot run multiple bots on the same trading account.
This prevents duplicate orders and position conflicts.

To trade this account:
1. Stop the other bot instance
2. Or select a different account from the dropdown
```

## Technical Implementation

### Dependencies
- **psutil**: Process checking for stale lock detection
- Added to `requirements.txt`: `psutil>=5.9.0`

### Key Functions

#### `check_account_lock(account_id)`
- Checks if account is locked
- Validates PID still exists (removes stale locks)
- Returns: `(is_locked: bool, lock_info: dict)`

#### `create_account_lock(account_id)`
- Creates lock file with current PID
- Stores broker username and timestamp
- Returns: `True` if successful

#### `remove_account_lock(account_id)`
- Removes lock file when GUI closes
- Called automatically via `WM_DELETE_WINDOW` protocol
- Prevents lock leakage

### Stale Lock Detection
If a bot crashes without cleanup:
1. Lock file remains on disk
2. Next launch checks if PID exists
3. If process dead → Auto-remove lock
4. User can launch bot again

## File Structure
```
simple-bot-1/
├── locks/                    # Instance lock files (gitignored)
│   ├── account_123456.lock
│   └── account_789012.lock
├── customer/
│   └── QuoTrading_Launcher.py  # Lock implementation
└── .gitignore                # Excludes /locks/ directory
```

## Benefits
- ✅ Multi-user support (different accounts)
- ✅ Multi-strategy support (one account per strategy)
- ✅ Prevents duplicate orders on same account
- ✅ Automatic cleanup on normal exit
- ✅ Stale lock recovery on crash
- ✅ Clear error messages for users
- ✅ Zero cloud dependency (local file-based)

## Limitations
- Lock only prevents duplicate launches from **same computer**
- If user has 2 computers, they could theoretically launch same account twice
- **Mitigation**: TopStep API will reject duplicate orders/positions from same account
- Future enhancement: Cloud-based lock via Azure API

## Testing Checklist
- [ ] Launch GUI, start bot → Lock created
- [ ] Try launching second GUI with same account → Blocked
- [ ] Close first GUI → Lock removed
- [ ] Launch second GUI again → Allowed
- [ ] Kill GUI process forcefully → Stale lock detected and removed on next launch
- [ ] Launch 2 GUIs with different accounts → Both allowed

## Production Notes
- Lock files are **local only** (not synced across machines)
- `.gitignore` excludes `/locks/` to prevent commit accidents
- No personal data stored in lock files (only account ID and PID)
- Compatible with Windows, macOS, Linux (Path library cross-platform)
