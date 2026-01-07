# Azure Deployment Guide - QuoTrading Flask API

## Quick Fix for Current Issue

The server was crashing because `eventlet` was missing from requirements.txt while the startup command tried to use it.

**Fix Applied:**
1. ✅ Added `eventlet>=0.33.0,<1.0.0` to requirements.txt
2. ✅ Updated Flask-SocketIO async_mode to 'eventlet'
3. ✅ Created startup.sh with proper configuration

## Deployment to Azure App Service

### Prerequisites
- Azure CLI installed
- Access to Azure subscription (quotrading-rg resource group)
- PostgreSQL database configured

### Deploy Using Azure CLI

```bash
cd cloud-api/flask-api

# Login to Azure
az login

# Deploy the app
az webapp deployment source config-zip \
    --resource-group quotrading-rg \
    --name quotrading-flask-api \
    --src deploy_package.zip
```

Or use the PowerShell script:
```powershell
.\deploy.ps1
```

### Required Environment Variables

Configure these in Azure Portal > App Service > Configuration > Application Settings:

#### Critical (Required)
- `DB_PASSWORD` - PostgreSQL database password
- `PORT` - Auto-set by Azure (usually 8000)

#### Important (Recommended)
- `ADMIN_API_KEY` - Admin dashboard access key (change from default!)
- `SENDGRID_API_KEY` - Email service API key
- `WHOP_API_KEY` - Whop integration API key
- `WHOP_WEBHOOK_SECRET` - Webhook verification secret

#### Optional
- `DB_HOST` - Default: quotrading-db.postgres.database.azure.com
- `DB_NAME` - Default: quotrading
- `DB_USER` - Default: quotradingadmin
- `DB_PORT` - Default: 5432
- `CORS_ORIGINS` - Comma-separated allowed origins
- `SMTP_SERVER`, `SMTP_USERNAME`, `SMTP_PASSWORD` - SMTP fallback
- `FROM_EMAIL` - Email sender address

### Startup Command

The app uses `startup.sh` for proper configuration. In Azure Portal:
1. Go to Configuration > General Settings
2. Set **Startup Command** to: `startup.sh`
3. Save changes and restart app

Alternatively, Azure will auto-detect and use gunicorn if startup command is empty.

### Verify Deployment

After deployment, check:
1. **Health Check**: https://quotrading-flask-api.azurewebsites.net/health
2. **API Status**: https://quotrading-flask-api.azurewebsites.net/api/hello
3. **Admin Dashboard**: https://quotrading-flask-api.azurewebsites.net/admin-dashboard-full.html

### Troubleshooting

#### App won't start
- Check Azure Portal > Diagnose and solve problems
- View logs: `az webapp log tail --name quotrading-flask-api --resource-group quotrading-rg`
- Verify environment variables are set correctly

#### Database connection errors
- Verify DB_PASSWORD is set
- Check PostgreSQL firewall allows Azure services
- Test connection from Azure Cloud Shell

#### WebSocket issues
- Ensure eventlet is in requirements.txt
- Verify startup command uses eventlet worker
- Check WebSocket protocol is allowed (wss://)

## Architecture

### Stack
- **Runtime**: Python 3.12
- **Framework**: Flask 3.x with Flask-SocketIO
- **WSGI Server**: Gunicorn with eventlet workers
- **Database**: Azure PostgreSQL Flexible Server
- **Storage**: Azure Blob Storage (for bot downloads)

### Key Features
- WebSocket support for real-time updates
- Trade copier relay server
- User license management
- Admin dashboard
- Email notifications (SendGrid/SMTP)
- Whop integration for subscriptions

## Discord Bot Deployment

The Discord bot is deployed separately:

```bash
cd discord-bot

# Deploy to Azure Container Instances or App Service
az webapp up \
    --resource-group quotrading-rg \
    --name quotrading-discord-bot \
    --runtime "PYTHON:3.12" \
    --sku B1
```

Required environment variables for Discord bot:
- `DISCORD_BOT_TOKEN` - Discord bot authentication token
- `API_URL` - Flask API URL (default: https://quotrading-flask-api.azurewebsites.net)

## Monitoring

### Application Insights
Enable Application Insights in Azure Portal for:
- Request tracking
- Performance monitoring
- Error logging
- Custom metrics

### Log Streaming
```bash
# Stream live logs
az webapp log tail --name quotrading-flask-api --resource-group quotrading-rg

# Download logs
az webapp log download --name quotrading-flask-api --resource-group quotrading-rg
```

## Security Checklist

- [ ] Change ADMIN_API_KEY from default value
- [ ] Configure allowed CORS origins
- [ ] Enable HTTPS only
- [ ] Set up custom domain with SSL
- [ ] Configure database firewall rules
- [ ] Enable Application Insights
- [ ] Set up alerts for errors/downtime
- [ ] Regular dependency updates
- [ ] Database backups configured

## Support

For issues:
1. Check Azure Portal diagnostics
2. Review application logs
3. Test health endpoints
4. Contact: support@quotrading.com
