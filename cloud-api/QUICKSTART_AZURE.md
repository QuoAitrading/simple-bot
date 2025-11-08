# Azure Deployment - Quick Start Guide

Get your QuoTrading Cloud API running on Azure in 10 minutes!

## Prerequisites

✅ Azure account ([sign up free](https://azure.microsoft.com/free/) - $200 credit)  
✅ Azure CLI installed  
✅ 10 minutes of your time  

## Install Azure CLI

**Windows:**
```powershell
winget install Microsoft.AzureCLI
```

**macOS:**
```bash
brew install azure-cli
```

**Linux:**
```bash
curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash
```

## Deploy in 3 Steps

### Step 1: Login to Azure
```bash
az login
```
Your browser will open - login with your Azure account.

### Step 2: Run Deployment Script
```bash
cd cloud-api
chmod +x deploy-azure.sh
./deploy-azure.sh
```

**What it does:**
- Creates resource group
- Creates PostgreSQL database
- Creates App Service
- Configures environment variables
- Sets up HTTPS

**You'll be prompted for:**
- Database password (create a strong one!)
- Stripe keys (optional - can set later)

### Step 3: Deploy Your Code
```bash
# Get your app name from deployment output
APP_NAME="quotrading-api-xxxxxxxx"

# Deploy
az webapp up --resource-group quotrading-rg --name $APP_NAME --runtime PYTHON:3.11
```

## Verify It Works

```bash
# Use the URL from deployment output
./verify-azure-deployment.sh https://quotrading-api-xxxxxxxx.azurewebsites.net
```

You should see:
```
[PASS] Health check successful
[PASS] User registration successful
[PASS] Admin key validation successful
[PASS] User license validation successful
[PASS] Get user info successful
[PASS] Signal health check successful
```

## Update Your Bot

In `customer/QuoTrading_Launcher.py`, change:
```python
CLOUD_API_BASE_URL = "https://quotrading-api-xxxxxxxx.azurewebsites.net"
```

## What's Next?

### Configure Stripe (for production)
```bash
# Get production keys from https://dashboard.stripe.com/apikeys
az webapp config appsettings set \
  --resource-group quotrading-rg \
  --name quotrading-api-xxxxxxxx \
  --settings STRIPE_SECRET_KEY="sk_live_YOUR_KEY"
```

### Set Up Stripe Webhook
1. Go to https://dashboard.stripe.com/webhooks
2. Add endpoint: `https://quotrading-api-xxxxxxxx.azurewebsites.net/api/v1/webhooks/stripe`
3. Select events: `customer.subscription.*`, `invoice.payment_failed`
4. Update webhook secret:
```bash
az webapp config appsettings set \
  --resource-group quotrading-rg \
  --name quotrading-api-xxxxxxxx \
  --settings STRIPE_WEBHOOK_SECRET="whsec_YOUR_SECRET"
```

### Monitor Your API
```bash
# Stream logs
az webapp log tail --resource-group quotrading-rg --name quotrading-api-xxxxxxxx

# Check app status
az webapp show --resource-group quotrading-rg --name quotrading-api-xxxxxxxx --query state
```

### Scale Up (when needed)
```bash
# Upgrade to Standard tier for better performance
az appservice plan update \
  --resource-group quotrading-rg \
  --name quotrading-plan \
  --sku S1
```

## Common Issues

### "az: command not found"
→ Azure CLI not installed. See installation instructions above.

### "Please run 'az login'"
→ Run `az login` and authenticate.

### "Database connection failed"
→ Check firewall rules allow Azure services (deployment script does this automatically).

### "App won't start"
→ Check logs: `az webapp log tail --resource-group quotrading-rg --name $APP_NAME`

## Cost Breakdown

### Development (Free Tier)
- **PostgreSQL**: ~$12/month (Burstable B1ms)
- **App Service**: Free tier available
- **Total**: ~$12/month (or free with $200 Azure credit)

### Production
- **PostgreSQL**: ~$12/month
- **App Service**: ~$13/month (Basic B1)
- **Total**: ~$25/month

## Stop Services (Save Money)

When not in use:
```bash
# Stop web app
az webapp stop --resource-group quotrading-rg --name quotrading-api-xxxxxxxx

# Stop database
az postgres flexible-server stop --resource-group quotrading-rg --name quotrading-db-xxxxxxxx
```

Start again:
```bash
az webapp start --resource-group quotrading-rg --name quotrading-api-xxxxxxxx
az postgres flexible-server start --resource-group quotrading-rg --name quotrading-db-xxxxxxxx
```

## Delete Everything

To remove all resources and stop all charges:
```bash
az group delete --name quotrading-rg --yes
```
⚠️ This deletes EVERYTHING - database, app, all data!

## Need Help?

- 📖 **Full Guide**: See `AZURE_DEPLOYMENT.md`
- 🔧 **CLI Reference**: See `AZURE_CLI_REFERENCE.md`
- 📝 **Summary**: See `AZURE_SUPPORT_SUMMARY.md`
- 📧 **Support**: support@quotrading.com

## Success! 🎉

Your QuoTrading Cloud API is now running on Azure!

**Your API**: `https://quotrading-api-xxxxxxxx.azurewebsites.net`

Test it:
```bash
curl https://quotrading-api-xxxxxxxx.azurewebsites.net/
```

---

**Time to deploy**: ~10 minutes  
**Monthly cost**: ~$25 (production) or ~$12 (dev)  
**Uptime**: 99.95% SLA  
**Support**: 24/7 Azure support available  

Ready to scale! 🚀
