# Trade Copier System Architecture

## Before Refactoring (Old)

```
┌─────────────────────────────────────────────────────────────┐
│                    OLD ARCHITECTURE                          │
└─────────────────────────────────────────────────────────────┘

Main AI Bot (src/main.py)
│
├─> Connected to Broker
├─> Executed Trades Directly
├─> Complex Health Checks
├─> Metrics Collection
└─> Multi-symbol orchestration

Admin Dashboard
│
└─> Showed data from main AI bot
    └─> Limited real-time info
```

## After Refactoring (New)

```
┌─────────────────────────────────────────────────────────────┐
│                    NEW ARCHITECTURE                          │
└─────────────────────────────────────────────────────────────┘

                     ┌──────────────────┐
                     │  Main AI Bot     │
                     │  (Signal Only)   │
                     │                  │
                     │ • Analyzes       │
                     │ • Generates      │
                     │ • NO Trading     │
                     └────────┬─────────┘
                              │
                              │ Discord Webhook
                              │ (Signals)
                              ▼
                     ┌──────────────────┐
                     │    Discord       │
                     │  Signal Channel  │
                     └────────┬─────────┘
                              │
                              │ Signals
                              ▼
        ┌────────────────────────────────────────┐
        │                                        │
        │    Follower Trade Copiers              │
        │    (MAIN TRADING ENGINE)               │
        │                                        │
        │  User 1 ─> Executes trades            │
        │  User 2 ─> Executes trades            │
        │  User 3 ─> Executes trades            │
        │  User N ─> Executes trades            │
        │                                        │
        │  Each Follower:                        │
        │  • Validates license                   │
        │  • Receives signals                    │
        │  • Executes on broker                 │
        │  • Sends heartbeats                   │
        │  • Reports P&L                        │
        │                                        │
        └────────────────┬───────────────────────┘
                         │
                         │ Heartbeats + Status
                         │ (Every 20 seconds)
                         │
                         ▼
        ┌────────────────────────────────────────┐
        │          Flask API Server              │
        │        (Relay & Management)            │
        │                                        │
        │  /copier/register                     │
        │  /copier/heartbeat                    │
        │  /copier/poll                         │
        │  /api/admin/copier-users ← NEW!       │
        │  /api/heartbeat                       │
        │  /copier/validate-license             │
        │                                        │
        │  Tracks:                               │
        │  • Connected followers                 │
        │  • Live positions                      │
        │  • Session P&L                        │
        │  • Online status                       │
        │                                        │
        └────────────────┬───────────────────────┘
                         │
                         │ GET /api/admin/copier-users
                         │ (Combined user + follower data)
                         │
                         ▼
        ┌────────────────────────────────────────┐
        │        Admin Dashboard                 │
        │      (admin-dashboard-full.html)       │
        │                                        │
        │  Shows for each user:                  │
        │  ✅ Online/Offline (from heartbeats)  │
        │  ✅ Current Position (live)           │
        │  ✅ Session P&L (live)                │
        │  ✅ Trades Executed (live)            │
        │  ✅ Signals Received/Executed         │
        │  ✅ License Status                     │
        │  ✅ Last Active Time                   │
        │                                        │
        └────────────────────────────────────────┘
```

## Data Flow Examples

### Example 1: Signal Generation & Execution

```
1. Main AI Bot analyzes market
   └─> Generates OPEN signal for MES BUY

2. Signal posted to Discord
   └─> Webhook: "🤖 AI SIGNAL: BUY 1 MES @ 6000"

3. Follower Trade Copiers receive signal
   └─> User A's copier: Validates license ✅
   └─> User B's copier: Validates license ✅
   └─> User C's copier: Validates license ✅

4. Each follower executes trade
   └─> User A: BUY 1 MES @ 6000 ✅
   └─> User B: BUY 1 MES @ 6000 ✅
   └─> User C: BUY 1 MES @ 6000 ✅

5. Followers send status updates
   └─> Heartbeat to Flask API with position data
   └─> {position: "LONG 1 MES", entry: 6000}

6. Admin dashboard updates
   └─> Shows all users with LONG position
   └─> Real-time P&L as price moves
```

### Example 2: Admin Dashboard Update

```
1. Admin opens dashboard
   └─> Calls: GET /api/admin/copier-users

2. Flask API processes request
   ├─> Queries users from database
   ├─> Checks _connected_followers for live status
   └─> Combines data

3. For each user:
   ├─> If follower connected (heartbeat < 60s ago):
   │   ├─> Status: ONLINE 🟢
   │   ├─> Position: From follower.current_position
   │   ├─> P&L: From follower.metadata.session_pnl
   │   └─> Trades: From follower.metadata.trades_executed
   │
   └─> If no follower connected:
       ├─> Status: OFFLINE ⚪
       ├─> Position: -
       ├─> P&L: -
       └─> Trades: From database (historical)

4. Dashboard renders data
   └─> Live updates every few seconds
```

## Key Benefits

### ✅ Scalability
- Each user runs their own follower copier
- No bottleneck on main AI bot
- Can support unlimited users

### ✅ Reliability
- Follower crashes don't affect others
- Main AI bot is simple and stable
- Each user has independent execution

### ✅ Transparency
- All trades visible in Discord
- Real-time P&L tracking
- Complete audit trail

### ✅ Security
- API keys validated per follower
- Session locking prevents duplicates
- License expiration enforced

### ✅ Performance
- Signals pushed via WebSocket (instant)
- Heartbeats keep admin dashboard live
- Minimal database queries

## Component Responsibilities

| Component | Role | Trading | Signals | Status |
|-----------|------|---------|---------|--------|
| **Main AI Bot** | Generate signals | ❌ No | ✅ Creates | - |
| **Discord** | Broadcast signals | ❌ No | ✅ Relays | - |
| **Follower Copier** | Execute trades | ✅ YES | ✅ Receives | ✅ Reports |
| **Flask API** | Manage & relay | ❌ No | ✅ Relays | ✅ Tracks |
| **Admin Dashboard** | Monitor users | ❌ No | ❌ No | ✅ Displays |

## Security & Validation

```
Follower Login Flow:
1. Follower starts
2. Calls /copier/validate-license
   └─> Checks license_key in database
   └─> Validates expiration
   └─> Returns expiration_date
3. If valid, registers
   └─> /copier/register with follower_key
   └─> Creates session in _connected_followers
4. Sends heartbeats every 20s
   └─> /copier/heartbeat with position data
   └─> Updates last_heartbeat timestamp
5. If heartbeat > 60s old
   └─> Marked offline in admin dashboard
```

## File Organization

```
simple-bot/
├── src/
│   ├── main.py                    ← NEW: Discord signal generator
│   └── main_legacy_backup.py      ← OLD: Backed up trading bot
│
├── trade-copier/
│   ├── follower/
│   │   ├── main.py                ← MAIN TRADING ENGINE
│   │   ├── signal_receiver.py     ← Receives signals
│   │   └── config.json            ← User's license key
│   │
│   ├── master/
│   │   └── main.py                ← Master broadcaster (optional)
│   │
│   └── shared/
│       ├── signal_protocol.py     ← Signal format
│       └── copier_broker.py       ← Broker integration
│
├── cloud-api/flask-api/
│   ├── app.py                     ← Flask API (NEW endpoint)
│   └── admin-dashboard-full.html  ← Dashboard (UPDATED)
│
└── REFACTORING_SUMMARY.md         ← This documentation
```
