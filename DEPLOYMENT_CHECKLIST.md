# Deployment Checklist - Profile Endpoint & Bot Optimizations

## Summary
This PR contains changes to both the Flask API and the trading bot that need to be deployed to Azure.

---

## Files to Deploy

### 1. Flask API (Azure App Service)
**File:** `cloud-api/flask-api/app.py`

**Changes:**
- ✅ New `/api/profile` endpoint for user self-service (GET)
- ✅ `minutes_valid` parameter support in `/api/admin/create-license` endpoint
- ✅ Email masking and security features
- ✅ Rate limiting (100 req/min)

**Deployment Method:**
```bash
cd cloud-api/flask-api
zip deploy_update.zip app.py requirements.txt
az webapp deployment source config-zip \
    --resource-group quotrading-rg \
    --name quotrading-flask-api \
    --src deploy_update.zip
az webapp restart --resource-group quotrading-rg --name quotrading-flask-api
```

### 2. Trading Bot
**File:** `src/quotrading_engine.py`

**Changes:**
- ✅ VWAP reset disabled at maintenance open (6:00 PM ET)
- ✅ VWAP calculation logging removed (silent per-bar calculation)
- ✅ Maintenance reconnection logging reduced

**Deployment:** 
- Copy updated `quotrading_engine.py` to bot deployment location
- Restart bot instances

### 3. Test Script (Optional - Not for Production)
**File:** `cloud-api/flask-api/test_profile_endpoint.py`
- Automated testing script for the new profile endpoint
- Not needed in production deployment

---

## Pre-Deployment Verification

### Syntax Check
```bash
python3 -m py_compile cloud-api/flask-api/app.py
python3 -m py_compile src/quotrading_engine.py
```
✅ All files pass syntax check

### Security Check
✅ CodeQL scan passed with 0 alerts

---

## Post-Deployment Testing

### 1. Test Flask API Profile Endpoint
```bash
# Test with valid license key
curl "https://quotrading-flask-api.azurewebsites.net/api/profile?license_key=YOUR-KEY"

# Expected: 200 OK with JSON response containing profile, trading_stats, recent_activity
```

### 2. Test License Creation with Minutes
```bash
# Create 5-minute test license
curl -X POST https://quotrading-flask-api.azurewebsites.net/api/admin/create-license \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "minutes_valid": 5,
    "admin_key": "YOUR-ADMIN-KEY"
  }'

# Expected: License created with 5-minute expiration
```

### 3. Verify Bot Changes
- ✅ VWAP calculates silently (no logs)
- ✅ No VWAP reset at 6:00 PM maintenance window
- ✅ Reduced maintenance reconnection logging

---

## Changes Summary

### Flask API Changes (`cloud-api/flask-api/app.py`)
- **Lines added:** ~260
- **New endpoint:** `/api/profile` (GET)
- **Enhanced endpoint:** `/api/admin/create-license` (supports `minutes_valid`)
- **Database queries:** 5 optimized queries for profile data
- **Security:** Email masking, rate limiting, proper error handling

### Trading Bot Changes (`src/quotrading_engine.py`)
- **Lines removed:** ~50 (logging and reset logic)
- **Lines modified:** ~10
- **Functions changed:**
  - `calculate_vwap()` - Removed all logging
  - `perform_vwap_reset()` - Disabled (now just `pass`)
  - `handle_vwap_reset_event()` - Disabled with comment
  - Maintenance reconnection - Reduced from CRITICAL to INFO level

---

## Environment Variables
**No new environment variables required** ✅

All existing environment variables remain unchanged:
- `DB_HOST`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_PORT`
- `ADMIN_API_KEY`
- `CORS_ORIGINS`

---

## Database Migrations
**No database migrations required** ✅

All endpoints use existing database schema:
- `users` table (already exists)
- `rl_experiences` table (already exists)
- `api_logs` table (already exists)

---

## Rollback Plan

If issues occur after deployment:

### Flask API Rollback
```bash
# Use Azure Portal to rollback to previous deployment
# OR redeploy previous version of app.py
```

### Trading Bot Rollback
- Restore previous version of `quotrading_engine.py`
- Restart bot instances

---

## Testing Endpoints

### New Profile Endpoint
```
GET https://quotrading-flask-api.azurewebsites.net/api/profile?license_key=KEY
GET https://quotrading-flask-api.azurewebsites.net/api/profile
  Headers: Authorization: ******
```

### Updated License Creation
```
POST https://quotrading-flask-api.azurewebsites.net/api/admin/create-license
  Body: {"email": "test@test.com", "minutes_valid": 5, "admin_key": "KEY"}
  
POST https://quotrading-flask-api.azurewebsites.net/api/admin/add-user
  Body: {"email": "test@test.com", "minutes_valid": 5, "admin_key": "KEY"}
```

---

## Deployment Status

- [x] Code changes completed
- [x] Syntax verified
- [x] Security scan passed
- [ ] Flask API deployed to Azure
- [ ] Trading bot deployed
- [ ] Post-deployment testing completed

---

*Generated: 2025-12-05*
