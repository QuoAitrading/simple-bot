# Azure Deployment Checklist - QuoTrading Platform

## ✅ Fix Applied - Server Crash Issue

**Root Cause**: Missing `eventlet` dependency in requirements.txt while startup command tried to use eventlet worker.

**Solution**:
- ✅ Added eventlet to requirements.txt
- ✅ Updated Flask-SocketIO async_mode to 'eventlet'
- ✅ Created proper startup.sh script
- ✅ Added comprehensive documentation

## Deployment Steps

### 1. Flask API (quotrading-flask-api)

```bash
cd cloud-api/flask-api

# Option A: Use PowerShell script
.\deploy.ps1

# Option B: Manual deployment
az webapp deployment source config-zip \
    --resource-group quotrading-rg \
    --name quotrading-flask-api \
    --src deploy_package.zip
```

**Required Environment Variables** (Set in Azure Portal):
- [ ] `DB_PASSWORD` - PostgreSQL password
- [ ] `ADMIN_API_KEY` - Admin dashboard key (CHANGE FROM DEFAULT!)
- [ ] `SENDGRID_API_KEY` - Email service key
- [ ] `WHOP_API_KEY` - Whop integration key
- [ ] `WHOP_WEBHOOK_SECRET` - Webhook secret

**Startup Command**: `startup.sh`

**Verify**:
- [ ] Health: https://quotrading-flask-api.azurewebsites.net/health
- [ ] API: https://quotrading-flask-api.azurewebsites.net/api/hello
- [ ] Admin: https://quotrading-flask-api.azurewebsites.net/admin-dashboard-full.html

### 2. Discord Bot (quotrading-discord-bot)

```bash
cd discord-bot

# Deploy
.\deploy-azure.ps1
```

**Required Environment Variables**:
- [ ] `DISCORD_BOT_TOKEN` - Discord bot token
- [ ] `API_URL` - Flask API URL (default is correct)

**Startup Command**: `python ticket_bot.py`

**Verify**:
- [ ] Health: https://quotrading-discord-bot.azurewebsites.net/health
- [ ] Bot online in Discord server
- [ ] Ticket buttons working

### 3. Database Configuration

**PostgreSQL Firewall Rules**:
- [ ] Allow Azure services
- [ ] Add your IP for management
- [ ] Verify SSL is required

**Database Tables**:
The Flask API will auto-create required tables on first run.

### 4. Post-Deployment Checks

**Flask API**:
- [ ] Server responds to /health
- [ ] Database connection works
- [ ] WebSocket connections work (for zone delivery)
- [ ] Admin dashboard accessible
- [ ] Email service configured
- [ ] Trade copier endpoints responding

**Discord Bot**:
- [ ] Bot shows online in Discord
- [ ] Create ticket button works
- [ ] Close ticket button works
- [ ] Heartbeat reporting to API
- [ ] HTTP health check responds

**Integration**:
- [ ] Discord bot can reach Flask API
- [ ] Whop webhooks configured (if using)
- [ ] Email notifications working

## Common Issues & Solutions

### Issue: "Application Error" on Flask API

**Solution**:
1. Check logs: `az webapp log tail --name quotrading-flask-api --resource-group quotrading-rg`
2. Verify DB_PASSWORD is set correctly
3. Ensure startup command is `startup.sh`
4. Check Python runtime is 3.12

### Issue: Discord bot offline

**Solution**:
1. Check logs: `az webapp log tail --name quotrading-discord-bot --resource-group quotrading-rg`
2. Verify DISCORD_BOT_TOKEN is correct
3. Check bot has required Discord intents enabled
4. Ensure startup command is `python ticket_bot.py`

### Issue: WebSocket not working

**Solution**:
1. Verify eventlet is in requirements.txt
2. Check async_mode is 'eventlet' in app.py
3. Ensure gunicorn uses eventlet worker
4. Test with WebSocket client

### Issue: Admin dashboard 403/401

**Solution**:
1. Use correct ADMIN_API_KEY
2. Check CORS_ORIGINS includes your domain
3. Verify API endpoints are responding

## Monitoring Setup

### Enable Application Insights

```bash
# For Flask API
az monitor app-insights component create \
    --app quotrading-api-insights \
    --location westus2 \
    --resource-group quotrading-rg \
    --application-type web

# Connect to app
az webapp config appsettings set \
    --name quotrading-flask-api \
    --resource-group quotrading-rg \
    --settings APPINSIGHTS_INSTRUMENTATIONKEY="<key>"
```

### Set Up Alerts

Create alerts for:
- [ ] HTTP 5xx errors
- [ ] Response time > 5s
- [ ] App restarts
- [ ] Database connection failures

## Security Hardening

- [ ] Change ADMIN_API_KEY from default
- [ ] Configure CORS_ORIGINS for production
- [ ] Enable HTTPS only (disable HTTP)
- [ ] Set up custom domain with SSL certificate
- [ ] Configure database firewall rules
- [ ] Enable Azure AD authentication (optional)
- [ ] Set up API rate limiting
- [ ] Review and rotate secrets regularly

## Rollback Procedure

If deployment fails:

```bash
# Flask API - restore previous version
az webapp deployment source config-zip \
    --resource-group quotrading-rg \
    --name quotrading-flask-api \
    --src previous_deploy_package.zip

# Discord Bot - redeploy previous version
cd discord-bot
git checkout <previous-commit>
.\deploy-azure.ps1
```

## Documentation

- Flask API: See `cloud-api/flask-api/AZURE_DEPLOYMENT.md`
- Discord Bot: See `discord-bot/AZURE_DEPLOYMENT.md`
- Environment Variables: See `.env.example`

## Support Contacts

- **Azure Issues**: Azure Support Portal
- **Application Issues**: support@quotrading.com
- **Database Issues**: Check PostgreSQL logs in Azure Portal
- **Discord Bot Issues**: Discord Developer Portal

## Deployment Verification Script

```bash
#!/bin/bash
echo "Testing QuoTrading Platform Deployment..."

# Test Flask API
echo "1. Testing Flask API health..."
curl -f https://quotrading-flask-api.azurewebsites.net/health || echo "❌ Flask API health check failed"

echo "2. Testing Flask API endpoints..."
curl -f https://quotrading-flask-api.azurewebsites.net/api/hello || echo "❌ Flask API hello failed"

# Test Discord Bot
echo "3. Testing Discord bot health..."
curl -f https://quotrading-discord-bot.azurewebsites.net/health || echo "❌ Discord bot health check failed"

echo "✅ Deployment verification complete!"
```

Save as `verify-deployment.sh` and run after deployment.

## Next Steps After Deployment

1. **Test all critical paths**:
   - User registration flow
   - License validation
   - Trade copier signal flow
   - Admin dashboard functions
   - Email notifications

2. **Monitor for 24 hours**:
   - Check error rates
   - Review performance metrics
   - Monitor database connections
   - Watch WebSocket connections

3. **Update DNS** (if using custom domain):
   - Point domain to Azure App Service
   - Configure SSL certificate
   - Update CORS settings

4. **Communicate with users**:
   - Announce maintenance window
   - Share new URLs if changed
   - Update documentation
   - Test with beta users

## Rollout Strategy (Recommended)

1. Deploy to staging first
2. Run integration tests
3. Monitor for issues (2-4 hours)
4. Deploy to production
5. Monitor closely (24 hours)
6. Gradual rollout if possible

---

**Last Updated**: December 2024
**Status**: ✅ Fixed and Ready for Deployment
