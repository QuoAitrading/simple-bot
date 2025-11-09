# QuoTrading Admin Commands - Azure User Management

## Your Admin License Key
```
QT-0149-EA27-38BB-C7A0
```

---

## 1️⃣ CREATE NEW BETA USER

```powershell
# Create a new beta user with 90-day license
$body = @{
    account_id = "USER001"
    email = "john@example.com"
    license_type = "BETA"
    days_valid = 90
    notes = "Beta tester - referred by Kevin"
} | ConvertTo-Json

Invoke-RestMethod -Uri "https://quotrading-signals.azurecontainerapps.io/api/admin/add-user" `
    -Method POST `
    -Headers @{"X-License-Key" = "QT-0149-EA27-38BB-C7A0"} `
    -Body $body `
    -ContentType "application/json"
```

**Response:**
```json
{
    "success": true,
    "message": "User created successfully",
    "user": {
        "account_id": "USER001",
        "email": "john@example.com",
        "license_key": "QT-XXXX-XXXX-XXXX-XXXX",  // ⬅️ GIVE THIS TO USER
        "license_type": "BETA",
        "license_expiration": "2026-02-07T12:00:00"
    }
}
```

---

## 2️⃣ VIEW ALL USERS

```powershell
# Get list of all users in database
Invoke-RestMethod -Uri "https://quotrading-signals.azurecontainerapps.io/api/admin/users" `
    -Headers @{"X-License-Key" = "QT-0149-EA27-38BB-C7A0"}
```

**Response:**
```json
{
    "users": [
        {
            "account_id": "ADMIN",
            "email": "admin@quotrading.com",
            "license_key": "QT-0149-EA27-38BB-C7A0",
            "license_type": "ADMIN",
            "license_status": "active",
            "created_at": "2025-11-09T12:00:00",
            "last_active": "2025-11-09T13:00:00"
        },
        {
            "account_id": "USER001",
            "email": "john@example.com",
            "license_key": "QT-XXXX-XXXX-XXXX-XXXX",
            "license_type": "BETA",
            "license_status": "active",
            "license_expiration": "2026-02-07T12:00:00"
        }
    ]
}
```

---

## 3️⃣ GET SPECIFIC USER DETAILS

```powershell
# Check a specific user's info and usage
Invoke-RestMethod -Uri "https://quotrading-signals.azurecontainerapps.io/api/admin/user/USER001" `
    -Headers @{"X-License-Key" = "QT-0149-EA27-38BB-C7A0"}
```

**Response:**
```json
{
    "user": {
        "account_id": "USER001",
        "email": "john@example.com",
        "license_key": "QT-XXXX-XXXX-XXXX-XXXX",
        "license_status": "active",
        "license_expiration": "2026-02-07T12:00:00",
        "created_at": "2025-11-09T12:00:00",
        "last_active": "2025-11-09T13:30:00"
    },
    "api_usage": {
        "last_24h": 143,
        "last_7d": 1250,
        "last_30d": 4821
    },
    "trades": {
        "total_trades": 23,
        "winning_trades": 15,
        "total_pnl": 1250.50
    }
}
```

---

## 4️⃣ EXTEND USER LICENSE

```powershell
# Add 30 more days to a user's license
$body = @{
    days = 30
} | ConvertTo-Json

Invoke-RestMethod -Uri "https://quotrading-signals.azurecontainerapps.io/api/admin/extend-license/USER001" `
    -Method PUT `
    -Headers @{"X-License-Key" = "QT-0149-EA27-38BB-C7A0"} `
    -Body $body `
    -ContentType "application/json"
```

---

## 5️⃣ SUSPEND USER (Ban)

```powershell
# Suspend a user (license becomes invalid immediately)
Invoke-RestMethod -Uri "https://quotrading-signals.azurecontainerapps.io/api/admin/suspend-user/USER001" `
    -Method PUT `
    -Headers @{"X-License-Key" = "QT-0149-EA27-38BB-C7A0"}
```

---

## 6️⃣ ACTIVATE USER (Unsuspend)

```powershell
# Reactivate a suspended user
Invoke-RestMethod -Uri "https://quotrading-signals.azurecontainerapps.io/api/admin/activate-user/USER001" `
    -Method PUT `
    -Headers @{"X-License-Key" = "QT-0149-EA27-38BB-C7A0"}
```

---

## 7️⃣ GET SYSTEM STATISTICS

```powershell
# View system-wide stats
Invoke-RestMethod -Uri "https://quotrading-signals.azurecontainerapps.io/api/admin/stats" `
    -Headers @{"X-License-Key" = "QT-0149-EA27-38BB-C7A0"}
```

**Response:**
```json
{
    "total_users": 25,
    "active_users": 23,
    "suspended_users": 2,
    "users_by_type": {
        "ADMIN": 1,
        "BETA": 20,
        "TRIAL": 3,
        "MONTHLY": 1
    },
    "api_calls_24h": 3421,
    "total_trades": 156,
    "total_pnl": 8450.25
}
```

---

## 8️⃣ TEST USER'S LICENSE

```powershell
# Verify a license key is valid (what bot does)
Invoke-RestMethod -Uri "https://quotrading-signals.azurecontainerapps.io/api/validate-license/QT-XXXX-XXXX-XXXX-XXXX"
```

**Valid Response:**
```json
{
    "valid": true,
    "account_id": "USER001",
    "license_type": "BETA",
    "expires_at": "2026-02-07T12:00:00",
    "days_remaining": 90
}
```

**Invalid Response (suspended/expired):**
```json
{
    "valid": false,
    "reason": "License suspended by admin"
}
```

---

## 9️⃣ CHECK ECONOMIC CALENDAR

```powershell
# See if there are any FOMC/NFP/CPI events today
Invoke-RestMethod -Uri "https://quotrading-signals.azurecontainerapps.io/api/calendar/today"
```

**Response:**
```json
{
    "date": "2025-11-09",
    "events": {},
    "count": 0,
    "has_fomc": false,
    "has_nfp": false,
    "has_cpi": false,
    "trading_recommended": true
}
```

---

## 🔟 HOW USERS USE THEIR LICENSE

When you create a user and get their license key (e.g., `QT-F926-99EE-EDBE-E4F6`), they:

### **Option 1: Put it in config.json**
```json
{
    "license_key": "QT-F926-99EE-EDBE-E4F6",
    "api_url": "https://quotrading-signals.azurecontainerapps.io"
}
```

### **Option 2: Enter in GUI**
When they launch `QuoTrading_Launcher.py`:
1. GUI asks: "Enter your license key"
2. They paste: `QT-F926-99EE-EDBE-E4F6`
3. Bot validates with Azure
4. ✅ Trading enabled if valid
5. ❌ "Invalid license" if expired/suspended

---

## 📊 MONITOR USERS IN REAL-TIME

You can run this script to monitor active users:

```powershell
# Check who's actively trading
while ($true) {
    Clear-Host
    Write-Host "=== QuoTrading Live Users ===" -ForegroundColor Cyan
    $stats = Invoke-RestMethod -Uri "https://quotrading-signals.azurecontainerapps.io/api/admin/stats" `
        -Headers @{"X-License-Key" = "QT-0149-EA27-38BB-C7A0"}
    
    Write-Host "Total Users: $($stats.total_users)" -ForegroundColor Green
    Write-Host "Active Today: $($stats.active_users)" -ForegroundColor Yellow
    Write-Host "API Calls (24h): $($stats.api_calls_24h)" -ForegroundColor Magenta
    Write-Host "`nPress Ctrl+C to exit"
    
    Start-Sleep -Seconds 30
}
```

---

## 💰 PRICING TIERS (For Future Paid Users)

When you're ready to charge:

```powershell
# Create TRIAL user (7 days free)
$body = @{
    account_id = "TRIAL001"
    email = "prospect@example.com"
    license_type = "TRIAL"
    days_valid = 7
} | ConvertTo-Json

# Create MONTHLY user ($99/month)
$body = @{
    account_id = "PAID001"
    email = "customer@example.com"
    license_type = "MONTHLY"
    days_valid = 30
} | ConvertTo-Json

# Create ANNUAL user ($990/year, 2 months free)
$body = @{
    account_id = "ANNUAL001"
    email = "vip@example.com"
    license_type = "ANNUAL"
    days_valid = 365
} | ConvertTo-Json
```

---

## 🚨 EMERGENCY KILL SWITCH

If you need to disable ALL users immediately:

```powershell
# Get all users
$users = Invoke-RestMethod -Uri "https://quotrading-signals.azurecontainerapps.io/api/admin/users" `
    -Headers @{"X-License-Key" = "QT-0149-EA27-38BB-C7A0"}

# Suspend everyone (except you)
foreach ($user in $users.users) {
    if ($user.account_id -ne "ADMIN") {
        Invoke-RestMethod -Uri "https://quotrading-signals.azurecontainerapps.io/api/admin/suspend-user/$($user.account_id)" `
            -Method PUT `
            -Headers @{"X-License-Key" = "QT-0149-EA27-38BB-C7A0"}
        Write-Host "Suspended: $($user.account_id)"
    }
}
```

---

## 📝 QUICK START FOR BETA LAUNCH

1. **Create 5 beta testers:**
```powershell
# Run this to create 5 users quickly
1..5 | ForEach-Object {
    $body = @{
        account_id = "BETA00$_"
        email = "beta$_@quotrading.com"
        license_type = "BETA"
        days_valid = 90
    } | ConvertTo-Json
    
    $result = Invoke-RestMethod -Uri "https://quotrading-signals.azurecontainerapps.io/api/admin/add-user" `
        -Method POST `
        -Headers @{"X-License-Key" = "QT-0149-EA27-38BB-C7A0"} `
        -Body $body `
        -ContentType "application/json"
    
    Write-Host "Created: $($result.user.account_id) - License: $($result.user.license_key)"
}
```

2. **Give them their license keys**

3. **Monitor them:**
```powershell
Invoke-RestMethod -Uri "https://quotrading-signals.azurecontainerapps.io/api/admin/stats" `
    -Headers @{"X-License-Key" = "QT-0149-EA27-38BB-C7A0"}
```

---

## 🛠️ DATABASE ACCESS (Advanced)

If you need direct database access:

**Connection String:**
```
postgresql://quotadmin:QuoTrading2025!Secure@quotrading-db.postgres.database.azure.com/quotrading?sslmode=require
```

**Connect with pgAdmin/DBeaver:**
- Host: `quotrading-db.postgres.database.azure.com`
- Port: `5432`
- Database: `quotrading`
- User: `quotadmin`
- Password: `QuoTrading2025!Secure`
- SSL Mode: Require

**Tables:**
- `users` - User accounts and licenses
- `api_logs` - Every API call tracked
- `trade_history` - Every trade logged

---

## ✅ SYSTEM HEALTH CHECK

```powershell
# Verify everything is working
Invoke-RestMethod -Uri "https://quotrading-signals.azurecontainerapps.io/health"
```

**Response:**
```json
{
    "status": "healthy",
    "database": "connected",
    "redis": "connected",
    "version": "v11-database"
}
```
