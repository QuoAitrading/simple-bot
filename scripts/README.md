# QuoTrading Live Trading Validation Scripts

This directory contains validation and testing scripts to ensure the trading bot and RL system work correctly before going live.

## Scripts Overview

### 1. JSON File Validation
**Script:** `validate_json_files.py`

Validates all JSON configuration files for structural integrity and correct data types.

**Usage:**
```bash
python scripts/validate_json_files.py
```

**What it checks:**
- `data/config.json` - Trading configuration (required fields, valid ranges)
- `data/signal_experience.json` - RL training data structure
- `data/trade_summary.json` - Trade record format
- `daily_summary.json` - Daily summary format

**Exit codes:**
- 0: All JSON files are valid
- 1: One or more files have errors

---

### 2. Cloud RL Connection Test
**Script:** `test_cloud_rl_connection.py`

Tests connectivity to the Azure-hosted RL API and validates the reinforcement learning system.

**Usage:**
```bash
python scripts/test_cloud_rl_connection.py
```

**What it tests:**
- API health endpoint
- License key validation
- RL signal analysis functionality
- Trade outcome reporting

**Prerequisites:**
- `cloud_api_url` configured in `data/config.json`
- Valid license key in `data/config.json` (`quotrading_api_key`)

**Exit codes:**
- 0: Cloud RL is accessible and working
- 1: Connection or authentication failed

---

### 3. Azure Deployment Validation
**Script:** `validate_azure_deployment.sh`

Uses Azure CLI to validate all Azure resources are deployed and configured correctly.

**Usage:**
```bash
# First, login to Azure
az login

# Then run the validation
./scripts/validate_azure_deployment.sh
```

**What it checks:**
- Azure CLI installation and login status
- Resource Group existence
- Container App (Flask API) status and health
- Storage Account and RL data container
- PostgreSQL database server
- Environment variables configuration

**Prerequisites:**
- Azure CLI installed (`az` command)
- Logged in to Azure account
- Proper permissions to read resources

**Configuration:**
Set these environment variables to customize (optional):
```bash
export AZURE_RESOURCE_GROUP="quotrading-rg"
export CONTAINER_APP_NAME="quotrading-signals"
export STORAGE_ACCOUNT_NAME="quotradingdata"
export POSTGRES_SERVER="quotrading-db"
```

---

### 4. Pre-Flight Check (All-in-One)
**Script:** `preflight_check.py`

Comprehensive check that runs all validations before starting live trading.

**Usage:**
```bash
python scripts/preflight_check.py
```

**What it checks:**
1. JSON file validation
2. Cloud RL connection
3. Environment variables
4. Risk management settings
5. Trading hours configuration
6. Broker configuration

**Recommended Workflow:**
```bash
# 1. Run pre-flight check
python scripts/preflight_check.py

# 2. If errors, fix them and re-run
python scripts/preflight_check.py

# 3. Start live trading only after all checks pass
python src/main.py
```

**Exit codes:**
- 0: All checks passed (safe to trade)
- 1: One or more critical checks failed

---

## Common Issues and Solutions

### Issue: "Cloud API timeout"
**Solution:** Check your internet connection and verify the `cloud_api_url` in `data/config.json`

### Issue: "License key is INVALID"
**Solution:** 
1. Check if your subscription is active
2. Verify the `quotrading_api_key` in `data/config.json` matches your license
3. Contact support if issue persists

### Issue: "Azure CLI not found"
**Solution:** Install Azure CLI from https://docs.microsoft.com/en-us/cli/azure/install-azure-cli

### Issue: "JSON validation failed"
**Solution:** Review the specific errors and fix the JSON files. Common issues:
- Missing required fields
- Wrong data types
- Invalid value ranges

### Issue: "Resource Group not found"
**Solution:** 
1. Verify you're logged into the correct Azure subscription
2. Check the resource group name in the script configuration
3. Create the resource group if needed: `az group create --name quotrading-rg --location eastus`

---

## Integration with CI/CD

These scripts can be integrated into your CI/CD pipeline:

```yaml
# Example GitHub Actions workflow
- name: Validate JSON Files
  run: python scripts/validate_json_files.py

- name: Test Cloud RL Connection
  run: python scripts/test_cloud_rl_connection.py

- name: Pre-Flight Check
  run: python scripts/preflight_check.py
```

---

## Azure CLI Quick Reference

### Common Commands

**Login to Azure:**
```bash
az login
```

**Check Container App status:**
```bash
az containerapp show --name quotrading-signals --resource-group quotrading-rg
```

**View Container App logs:**
```bash
az containerapp logs show --name quotrading-signals --resource-group quotrading-rg --follow
```

**Test Container App health:**
```bash
curl https://$(az containerapp show --name quotrading-signals --resource-group quotrading-rg --query properties.configuration.ingress.fqdn -o tsv)/health
```

**Check PostgreSQL status:**
```bash
az postgres flexible-server show --name quotrading-db --resource-group quotrading-rg
```

**List all resources in group:**
```bash
az resource list --resource-group quotrading-rg --output table
```

---

## Automated Daily Checks

For production environments, set up automated checks:

**Linux/Mac (crontab):**
```bash
# Run pre-flight check every day at 5:30 PM ET (before market open)
30 17 * * * cd /path/to/simple-bot && python scripts/preflight_check.py >> logs/preflight.log 2>&1
```

**Windows (Task Scheduler):**
1. Open Task Scheduler
2. Create new task
3. Set trigger: Daily at 5:30 PM
4. Set action: Run `python scripts/preflight_check.py`
5. Configure to send email on failure

---

## Support

If you encounter issues with these scripts:
1. Check the logs in `logs/` directory
2. Review the error messages carefully
3. Consult this README for common solutions
4. Contact QuoTrading support with log files

---

## Script Maintenance

These scripts are designed to be self-contained and require minimal maintenance. Update the configuration variables at the top of each script if your Azure resource names change.

**Last Updated:** 2024-11-23
**Version:** 1.0.0
