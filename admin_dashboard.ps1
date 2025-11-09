# QuoTrading Admin Dashboard
# Manage users, view stats, and monitor your Azure bot system

$ADMIN_KEY = "QT-0149-EA27-38BB-C7A0"
$API_URL = "https://quotrading-signals.icymeadow-86b2969e.eastus.azurecontainerapps.io"

function Show-Menu {
    Clear-Host
    Write-Host "============================================" -ForegroundColor Cyan
    Write-Host "   QuoTrading Admin Dashboard" -ForegroundColor Green
    Write-Host "============================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "1. View All Users" -ForegroundColor Yellow
    Write-Host "2. View System Stats" -ForegroundColor Yellow
    Write-Host "3. Create New User" -ForegroundColor Yellow
    Write-Host "4. Get User Details" -ForegroundColor Yellow
    Write-Host "5. Extend User License" -ForegroundColor Yellow
    Write-Host "6. Suspend User" -ForegroundColor Yellow
    Write-Host "7. Activate User" -ForegroundColor Yellow
    Write-Host "8. Test License Key" -ForegroundColor Yellow
    Write-Host "9. Check Calendar (FOMC/NFP/CPI)" -ForegroundColor Yellow
    Write-Host "10. Health Check" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Q. Quit" -ForegroundColor Red
    Write-Host ""
}

function View-AllUsers {
    Write-Host "`nFetching all users..." -ForegroundColor Cyan
    
    $url = "$API_URL/api/admin/users?license_key=$ADMIN_KEY"
    
    try {
        $result = Invoke-RestMethod -Uri $url -Method GET
        
        Write-Host "`n========================================" -ForegroundColor Cyan
        Write-Host "TOTAL USERS: $($result.users.Count)" -ForegroundColor Green
        Write-Host "========================================" -ForegroundColor Cyan
        
        foreach ($user in $result.users) {
            Write-Host "`nAccount ID: $($user.account_id)" -ForegroundColor White
            Write-Host "  Email: $($user.email)"
            Write-Host "  License Key: $($user.license_key)" -ForegroundColor Yellow
            Write-Host "  Type: $($user.license_type)"
            Write-Host "  Status: $($user.license_status)" -ForegroundColor $(if($user.license_status -eq "ACTIVE"){"Green"}else{"Red"})
            Write-Host "  Expires: $($user.license_expiration)"
            Write-Host "  Created: $($user.created_at)"
            Write-Host "  Last Active: $($user.last_active)"
            if ($user.notes) {
                Write-Host "  Notes: $($user.notes)" -ForegroundColor Gray
            }
        }
        
    } catch {
        Write-Host "Error: $($_.Exception.Message)" -ForegroundColor Red
    }
    
    Write-Host "`nPress any key to continue..."
    $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
}

function View-SystemStats {
    Write-Host "`nFetching system statistics..." -ForegroundColor Cyan
    
    $url = "$API_URL/api/admin/stats?license_key=$ADMIN_KEY"
    
    try {
        $stats = Invoke-RestMethod -Uri $url -Method GET
        
        Write-Host "`n========================================" -ForegroundColor Cyan
        Write-Host "SYSTEM STATISTICS" -ForegroundColor Green
        Write-Host "========================================" -ForegroundColor Cyan
        Write-Host "Total Users: $($stats.total_users)" -ForegroundColor White
        Write-Host "Active Users: $($stats.active_users)" -ForegroundColor Green
        Write-Host "Suspended Users: $($stats.suspended_users)" -ForegroundColor Red
        Write-Host ""
        Write-Host "Users by Type:" -ForegroundColor Yellow
        foreach ($type in $stats.users_by_type.PSObject.Properties) {
            Write-Host "  $($type.Name): $($type.Value)"
        }
        Write-Host ""
        Write-Host "API Calls (24h): $($stats.api_calls_24h)" -ForegroundColor Magenta
        Write-Host "Total Trades: $($stats.total_trades)" -ForegroundColor Cyan
        Write-Host "Total P&L: `$$($stats.total_pnl)" -ForegroundColor $(if($stats.total_pnl -gt 0){"Green"}else{"Red"})
        
    } catch {
        Write-Host "Error: $($_.Exception.Message)" -ForegroundColor Red
    }
    
    Write-Host "`nPress any key to continue..."
    $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
}

function Create-NewUser {
    Write-Host "`n========================================" -ForegroundColor Cyan
    Write-Host "CREATE NEW USER" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Cyan
    
    $accountId = Read-Host "Account ID (e.g., BETA002)"
    $email = Read-Host "Email"
    
    Write-Host "`nLicense Type:"
    Write-Host "1. TRIAL (7 days)"
    Write-Host "2. BETA (90 days)"
    Write-Host "3. MONTHLY (30 days)"
    Write-Host "4. ANNUAL (365 days)"
    $typeChoice = Read-Host "Choose (1-4)"
    
    $licenseType = switch ($typeChoice) {
        "1" { "TRIAL"; $days = 7 }
        "2" { "BETA"; $days = 90 }
        "3" { "MONTHLY"; $days = 30 }
        "4" { "ANNUAL"; $days = 365 }
        default { "BETA"; $days = 90 }
    }
    
    $customDays = Read-Host "Days valid (press Enter for default: $days)"
    if ($customDays) { $days = $customDays }
    
    $notes = Read-Host "Notes (optional)"
    
    $url = "$API_URL/api/admin/add-user?license_key=$ADMIN_KEY&account_id=$accountId&email=$email&license_type=$licenseType&license_duration_days=$days"
    if ($notes) {
        $url += "&notes=$([System.Web.HttpUtility]::UrlEncode($notes))"
    }
    
    try {
        Write-Host "`nCreating user..." -ForegroundColor Cyan
        $result = Invoke-RestMethod -Uri $url -Method POST
        
        Write-Host "`n========================================" -ForegroundColor Cyan
        Write-Host "✅ USER CREATED SUCCESSFULLY!" -ForegroundColor Green
        Write-Host "========================================" -ForegroundColor Cyan
        Write-Host "Account ID: $($result.user.account_id)"
        Write-Host "Email: $($result.user.email)"
        Write-Host ""
        Write-Host "LICENSE KEY (GIVE TO USER):" -ForegroundColor Yellow
        Write-Host "  $($result.user.license_key)" -ForegroundColor Yellow
        Write-Host ""
        Write-Host "Type: $($result.user.license_type)"
        Write-Host "Expires: $($result.user.license_expiration)"
        Write-Host "Status: $($result.user.license_status)" -ForegroundColor Green
        
    } catch {
        Write-Host "Error: $($_.Exception.Message)" -ForegroundColor Red
    }
    
    Write-Host "`nPress any key to continue..."
    $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
}

function Get-UserDetails {
    $accountId = Read-Host "`nEnter Account ID"
    
    $url = "$API_URL/api/admin/user/${accountId}?license_key=$ADMIN_KEY"
    
    try {
        Write-Host "Fetching user details..." -ForegroundColor Cyan
        $result = Invoke-RestMethod -Uri $url -Method GET
        
        Write-Host "`n========================================" -ForegroundColor Cyan
        Write-Host "USER DETAILS: $accountId" -ForegroundColor Green
        Write-Host "========================================" -ForegroundColor Cyan
        Write-Host "Email: $($result.user.email)"
        Write-Host "License Key: $($result.user.license_key)" -ForegroundColor Yellow
        Write-Host "Type: $($result.user.license_type)"
        Write-Host "Status: $($result.user.license_status)"
        Write-Host "Expires: $($result.user.license_expiration)"
        Write-Host "Created: $($result.user.created_at)"
        Write-Host "Last Active: $($result.user.last_active)"
        Write-Host ""
        Write-Host "Recent API Calls: $($result.recent_api_calls)"
        Write-Host ""
        Write-Host "TRADE STATS:" -ForegroundColor Cyan
        Write-Host "  Total Trades: $($result.trade_stats.total_trades)"
        Write-Host "  Total P&L: `$$($result.trade_stats.total_pnl)"
        Write-Host "  Avg P&L: `$$($result.trade_stats.avg_pnl)"
        
    } catch {
        Write-Host "Error: $($_.Exception.Message)" -ForegroundColor Red
    }
    
    Write-Host "`nPress any key to continue..."
    $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
}

function Extend-UserLicense {
    $accountId = Read-Host "`nEnter Account ID"
    $days = Read-Host "Add how many days?"
    
    $url = "$API_URL/api/admin/extend-license/${accountId}?license_key=$ADMIN_KEY&days=$days"
    
    try {
        Write-Host "Extending license..." -ForegroundColor Cyan
        $result = Invoke-RestMethod -Uri $url -Method PUT
        
        Write-Host "`n✅ License extended!" -ForegroundColor Green
        Write-Host "New expiration: $($result.license_expiration)"
        
    } catch {
        Write-Host "Error: $($_.Exception.Message)" -ForegroundColor Red
    }
    
    Write-Host "`nPress any key to continue..."
    $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
}

function Suspend-User {
    $accountId = Read-Host "`nEnter Account ID to SUSPEND"
    
    $confirm = Read-Host "Are you sure? This will disable their bot immediately. (yes/no)"
    if ($confirm -ne "yes") {
        Write-Host "Cancelled" -ForegroundColor Yellow
        return
    }
    
    $url = "$API_URL/api/admin/suspend-user/${accountId}?license_key=$ADMIN_KEY"
    
    try {
        Write-Host "Suspending user..." -ForegroundColor Cyan
        $result = Invoke-RestMethod -Uri $url -Method PUT
        
        Write-Host "`n🚫 User suspended!" -ForegroundColor Red
        Write-Host "Status: $($result.license_status)"
        
    } catch {
        Write-Host "Error: $($_.Exception.Message)" -ForegroundColor Red
    }
    
    Write-Host "`nPress any key to continue..."
    $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
}

function Activate-User {
    $accountId = Read-Host "`nEnter Account ID to ACTIVATE"
    
    $url = "$API_URL/api/admin/activate-user/${accountId}?license_key=$ADMIN_KEY"
    
    try {
        Write-Host "Activating user..." -ForegroundColor Cyan
        $result = Invoke-RestMethod -Uri $url -Method PUT
        
        Write-Host "`n✅ User activated!" -ForegroundColor Green
        Write-Host "Status: $($result.license_status)"
        
    } catch {
        Write-Host "Error: $($_.Exception.Message)" -ForegroundColor Red
    }
    
    Write-Host "`nPress any key to continue..."
    $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
}

function Test-LicenseKey {
    $licenseKey = Read-Host "`nEnter License Key to test"
    
    $body = @{
        license_key = $licenseKey
    } | ConvertTo-Json
    
    try {
        Write-Host "Validating license..." -ForegroundColor Cyan
        $result = Invoke-RestMethod -Uri "$API_URL/api/license/validate" -Method POST -Body $body -ContentType "application/json"
        
        Write-Host "`n========================================" -ForegroundColor Cyan
        Write-Host "✅ LICENSE VALID" -ForegroundColor Green
        Write-Host "========================================" -ForegroundColor Cyan
        Write-Host "Account: $($result.account_id)"
        Write-Host "Email: $($result.email)"
        Write-Host "Type: $($result.license_type)"
        Write-Host "Expires: $($result.expires_at)"
        Write-Host "Message: $($result.message)"
        
    } catch {
        Write-Host "`n❌ LICENSE INVALID" -ForegroundColor Red
        Write-Host "Error: $($_.Exception.Message)"
    }
    
    Write-Host "`nPress any key to continue..."
    $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
}

function Check-Calendar {
    try {
        Write-Host "`nFetching economic calendar..." -ForegroundColor Cyan
        $result = Invoke-RestMethod -Uri "$API_URL/api/calendar/today"
        
        Write-Host "`n========================================" -ForegroundColor Cyan
        Write-Host "ECONOMIC CALENDAR: $($result.date)" -ForegroundColor Green
        Write-Host "========================================" -ForegroundColor Cyan
        Write-Host "Event Count: $($result.count)"
        Write-Host "Has FOMC: $($result.has_fomc)" -ForegroundColor $(if($result.has_fomc){"Red"}else{"Green"})
        Write-Host "Has NFP: $($result.has_nfp)" -ForegroundColor $(if($result.has_nfp){"Red"}else{"Green"})
        Write-Host "Has CPI: $($result.has_cpi)" -ForegroundColor $(if($result.has_cpi){"Red"}else{"Green"})
        Write-Host ""
        Write-Host "Trading Recommended: $($result.trading_recommended)" -ForegroundColor $(if($result.trading_recommended){"Green"}else{"Red"})
        
        if ($result.events.PSObject.Properties.Count -gt 0) {
            Write-Host "`nEvents Today:" -ForegroundColor Yellow
            foreach ($event in $result.events.PSObject.Properties) {
                Write-Host "  $($event.Name): $($event.Value)"
            }
        }
        
    } catch {
        Write-Host "Error: $($_.Exception.Message)" -ForegroundColor Red
    }
    
    Write-Host "`nPress any key to continue..."
    $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
}

function Check-Health {
    try {
        Write-Host "`nChecking system health..." -ForegroundColor Cyan
        $result = Invoke-RestMethod -Uri "$API_URL/health"
        
        Write-Host "`n========================================" -ForegroundColor Cyan
        Write-Host "SYSTEM HEALTH CHECK" -ForegroundColor Green
        Write-Host "========================================" -ForegroundColor Cyan
        Write-Host "Status: $($result.status)" -ForegroundColor Green
        Write-Host "Database: $($result.database)" -ForegroundColor $(if($result.database -eq "connected"){"Green"}else{"Red"})
        
        if ($result.redis) {
            Write-Host "Redis: $($result.redis)" -ForegroundColor $(if($result.redis -eq "connected"){"Green"}else{"Yellow"})
        }
        
        if ($result.version) {
            Write-Host "Version: $($result.version)"
        }
        
    } catch {
        Write-Host "❌ System is DOWN" -ForegroundColor Red
        Write-Host "Error: $($_.Exception.Message)"
    }
    
    Write-Host "`nPress any key to continue..."
    $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
}

# Main loop
do {
    Show-Menu
    $choice = Read-Host "Select option"
    
    switch ($choice) {
        "1" { View-AllUsers }
        "2" { View-SystemStats }
        "3" { Create-NewUser }
        "4" { Get-UserDetails }
        "5" { Extend-UserLicense }
        "6" { Suspend-User }
        "7" { Activate-User }
        "8" { Test-LicenseKey }
        "9" { Check-Calendar }
        "10" { Check-Health }
        "Q" { 
            Write-Host "`nGoodbye!" -ForegroundColor Cyan
            exit 
        }
        default {
            Write-Host "`nInvalid option. Press any key to continue..." -ForegroundColor Red
            $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
        }
    }
} while ($true)
