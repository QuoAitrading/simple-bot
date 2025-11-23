# QuoTrading Bot - Live Trading Setup with Azure CLI

## Quick Start for Live Trading

Before starting live trading, ensure your JSON files and RL system are working correctly.

### Prerequisites

1. **Azure CLI installed**
   ```bash
   # Check if installed
   az --version
   
   # If not installed, get it from:
   # https://docs.microsoft.com/en-us/cli/azure/install-azure-cli
   ```

2. **Python 3.8+**
   ```bash
   python --version
   ```

3. **Dependencies installed**
   ```bash
   pip install -r requirements.txt
   ```

### Step-by-Step Live Trading Validation

#### Step 1: Validate JSON Configuration Files
```bash
python scripts/validate_json_files.py
```

This validates:
- `data/config.json` - Main trading configuration
- `data/signal_experience.json` - RL training data
- `data/trade_summary.json` - Trade records
- `daily_summary.json` - Daily performance summary

**Expected Output:**
```
✅ data/config.json: VALID
✅ data/signal_experience.json: VALID
✅ data/trade_summary.json: VALID
✅ daily_summary.json: VALID
✅ ALL JSON FILES ARE VALID - READY FOR LIVE TRADING
```

#### Step 2: Test Cloud RL Connection
```bash
python scripts/test_cloud_rl_connection.py
```

This tests:
- API health endpoint
- License key validation
- RL signal analysis
- Trade outcome reporting

**Expected Output:**
```
[1/4] Testing API Health...
   ✅ API is healthy: https://quotrading-signals...

[2/4] Testing License Validation...
   ✅ License key is valid

[3/4] Testing RL Signal Analysis...
   ✅ RL Analysis successful

[4/4] Testing Trade Outcome Reporting...
   ✅ Outcome reported successfully

✅ ALL TESTS PASSED (4/4) - READY FOR LIVE TRADING
```

#### Step 3: Validate Azure Deployment (Optional but Recommended)
```bash
# Login to Azure
az login

# Run Azure validation
./scripts/validate_azure_deployment.sh
```

This checks:
- Azure resources are deployed
- Container App is running
- Storage Account is accessible
- PostgreSQL database is healthy
- Environment variables are configured

#### Step 4: Run Comprehensive Pre-Flight Check
```bash
python scripts/preflight_check.py
```

This runs all checks in one command:
- JSON validation
- Cloud RL connection
- Environment variables
- Risk settings
- Trading configuration
- Broker setup

**Expected Output:**
```
PRE-FLIGHT CHECK SUMMARY
Checks Passed: 6/6
✅ ALL CHECKS PASSED - READY FOR LIVE TRADING
```

#### Step 5: Start Live Trading
```bash
# Set environment variables
export BOT_ENVIRONMENT=production
export CONFIRM_LIVE_TRADING=1

# Start the bot
python src/main.py
```

### Important Configuration in data/config.json

Ensure these fields are correctly set:

```json
{
  "cloud_api_url": "https://quotrading-signals.icymeadow-86b2969e.eastus.azurecontainerapps.io",
  "quotrading_api_key": "YOUR_LICENSE_KEY_HERE",
  "rl_confidence_threshold": 0.70,
  "rl_exploration_rate": 0.0,
  "max_contracts": 2,
  "daily_loss_limit": 1000.0,
  "shadow_mode": false
}
```

**Critical Settings for Live Trading:**
- `rl_exploration_rate` should be `0.0` (no random trades in live mode)
- `shadow_mode` should be `false` (enables real trading)
- `cloud_api_url` must point to your Azure Container App
- `quotrading_api_key` must be your valid license key

### Troubleshooting

#### Cloud RL Connection Failed
1. Check internet connectivity
2. Verify `cloud_api_url` is correct
3. Ensure license key is valid and not expired
4. Check Azure Container App is running:
   ```bash
   az containerapp show --name quotrading-signals --resource-group quotrading-rg --query properties.runningStatus
   ```

#### JSON Validation Failed
1. Review the specific error messages
2. Check for syntax errors (missing commas, brackets)
3. Verify field types match expectations
4. Ensure required fields are present

#### Azure CLI Not Found
Install from: https://docs.microsoft.com/en-us/cli/azure/install-azure-cli

**Ubuntu/Debian:**
```bash
curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash
```

**macOS:**
```bash
brew install azure-cli
```

**Windows:**
Download from: https://aka.ms/installazurecliwindows

### Safety Checklist

Before going live, confirm:
- [ ] All validation scripts pass
- [ ] License key is valid
- [ ] Cloud RL connection is working
- [ ] Risk limits are appropriate for account size
- [ ] Broker credentials are validated
- [ ] `rl_exploration_rate` is set to `0.0`
- [ ] `shadow_mode` is `false`
- [ ] `CONFIRM_LIVE_TRADING=1` environment variable is set
- [ ] You understand the risks of live trading

### Monitoring During Live Trading

**Check bot status:**
```bash
# View live logs
tail -f logs/vwap_bot.log
```

**Monitor Cloud RL:**
```bash
# Test connection periodically
python scripts/test_cloud_rl_connection.py
```

**Check Azure resources:**
```bash
# View Container App logs
az containerapp logs show --name quotrading-signals --resource-group quotrading-rg --follow

# Check Container App health
curl https://$(az containerapp show --name quotrading-signals --resource-group quotrading-rg --query properties.configuration.ingress.fqdn -o tsv)/health
```

### Daily Pre-Trading Routine

Run this before each trading session:
```bash
# 1. Validate everything is working
python scripts/preflight_check.py

# 2. If all checks pass, start trading
python src/main.py
```

### Getting Help

**Documentation:**
- Scripts documentation: `scripts/README.md`
- Main README: `README.md`
- Environment variables: `.env.example`

**Support:**
- Email: support@quotrading.com
- Discord: [Your Discord link]
- Documentation: [Your docs site]

---

**⚠️ IMPORTANT:** Never trade live without running the validation scripts first. These checks ensure your configuration is correct and the RL system is operational.

**Last Updated:** 2024-11-23
