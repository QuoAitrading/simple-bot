#!/bin/bash
# =============================================================================
# Azure Deployment Validation Script
# =============================================================================
# Uses Azure CLI to validate the deployment of QuoTrading cloud API
# and ensure all required Azure resources are properly configured.
#
# Prerequisites:
# - Azure CLI installed (az command)
# - Logged in to Azure (az login)
# - Proper permissions to read resources
# =============================================================================

set -e  # Exit on error

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration - Update these values for your deployment
RESOURCE_GROUP="${AZURE_RESOURCE_GROUP:-quotrading-rg}"
CONTAINER_APP_NAME="${CONTAINER_APP_NAME:-quotrading-signals}"
STORAGE_ACCOUNT_NAME="${STORAGE_ACCOUNT_NAME:-quotradingdata}"
POSTGRES_SERVER="${POSTGRES_SERVER:-quotrading-db}"
SUBSCRIPTION_ID="${AZURE_SUBSCRIPTION_ID:-}"

echo "================================================================================"
echo "AZURE DEPLOYMENT VALIDATION FOR QUOTRADING"
echo "================================================================================"
echo ""

# Function to print status
print_status() {
    local status=$1
    local message=$2
    
    if [ "$status" = "OK" ]; then
        echo -e "${GREEN}✅ $message${NC}"
    elif [ "$status" = "WARN" ]; then
        echo -e "${YELLOW}⚠️  $message${NC}"
    else
        echo -e "${RED}❌ $message${NC}"
    fi
}

# Check if Azure CLI is installed
echo "[1/7] Checking Azure CLI installation..."
if ! command -v az &> /dev/null; then
    print_status "FAIL" "Azure CLI is not installed. Install from: https://docs.microsoft.com/en-us/cli/azure/install-azure-cli"
    exit 1
fi

AZ_VERSION=$(az version --output tsv 2>/dev/null | head -n 1 | awk '{print $2}')
print_status "OK" "Azure CLI version: $AZ_VERSION"
echo ""

# Check if logged in
echo "[2/7] Checking Azure login status..."
if ! az account show &> /dev/null; then
    print_status "FAIL" "Not logged in to Azure. Run 'az login' first."
    exit 1
fi

CURRENT_USER=$(az account show --query user.name -o tsv 2>/dev/null)
CURRENT_SUBSCRIPTION=$(az account show --query name -o tsv 2>/dev/null)
print_status "OK" "Logged in as: $CURRENT_USER"
print_status "OK" "Subscription: $CURRENT_SUBSCRIPTION"
echo ""

# Check Resource Group
echo "[3/7] Checking Resource Group..."
if az group show --name "$RESOURCE_GROUP" &> /dev/null; then
    LOCATION=$(az group show --name "$RESOURCE_GROUP" --query location -o tsv)
    print_status "OK" "Resource Group: $RESOURCE_GROUP (Location: $LOCATION)"
else
    print_status "WARN" "Resource Group '$RESOURCE_GROUP' not found"
    echo "       You may need to create it: az group create --name $RESOURCE_GROUP --location eastus"
fi
echo ""

# Check Container App
echo "[4/7] Checking Container App (Flask API)..."
if az containerapp show --name "$CONTAINER_APP_NAME" --resource-group "$RESOURCE_GROUP" &> /dev/null 2>&1; then
    APP_URL=$(az containerapp show --name "$CONTAINER_APP_NAME" --resource-group "$RESOURCE_GROUP" --query properties.configuration.ingress.fqdn -o tsv 2>/dev/null)
    APP_STATUS=$(az containerapp show --name "$CONTAINER_APP_NAME" --resource-group "$RESOURCE_GROUP" --query properties.runningStatus -o tsv 2>/dev/null)
    
    print_status "OK" "Container App: $CONTAINER_APP_NAME"
    print_status "OK" "Status: $APP_STATUS"
    print_status "OK" "URL: https://$APP_URL"
    
    # Test health endpoint
    echo "       Testing health endpoint..."
    if curl -s -f "https://$APP_URL/health" &> /dev/null; then
        print_status "OK" "Health endpoint responsive"
    else
        print_status "WARN" "Health endpoint not responding"
    fi
else
    print_status "WARN" "Container App '$CONTAINER_APP_NAME' not found in resource group '$RESOURCE_GROUP'"
fi
echo ""

# Check Storage Account
echo "[5/7] Checking Storage Account..."
if az storage account show --name "$STORAGE_ACCOUNT_NAME" --resource-group "$RESOURCE_GROUP" &> /dev/null 2>&1; then
    STORAGE_STATUS=$(az storage account show --name "$STORAGE_ACCOUNT_NAME" --resource-group "$RESOURCE_GROUP" --query provisioningState -o tsv 2>/dev/null)
    print_status "OK" "Storage Account: $STORAGE_ACCOUNT_NAME"
    print_status "OK" "Status: $STORAGE_STATUS"
    
    # Check for rl-data container (requires connection string or key)
    echo "       Checking for 'rl-data' container..."
    CONNECTION_STRING=$(az storage account show-connection-string --name "$STORAGE_ACCOUNT_NAME" --resource-group "$RESOURCE_GROUP" --query connectionString -o tsv 2>/dev/null)
    if [ -n "$CONNECTION_STRING" ]; then
        if az storage container show --name "rl-data" --connection-string "$CONNECTION_STRING" &> /dev/null 2>&1; then
            print_status "OK" "RL data container exists"
        else
            print_status "WARN" "RL data container 'rl-data' not found"
        fi
    fi
else
    print_status "WARN" "Storage Account '$STORAGE_ACCOUNT_NAME' not found"
fi
echo ""

# Check PostgreSQL Server
echo "[6/7] Checking PostgreSQL Server..."
if az postgres flexible-server show --name "$POSTGRES_SERVER" --resource-group "$RESOURCE_GROUP" &> /dev/null 2>&1; then
    PG_STATUS=$(az postgres flexible-server show --name "$POSTGRES_SERVER" --resource-group "$RESOURCE_GROUP" --query state -o tsv 2>/dev/null)
    PG_VERSION=$(az postgres flexible-server show --name "$POSTGRES_SERVER" --resource-group "$RESOURCE_GROUP" --query version -o tsv 2>/dev/null)
    print_status "OK" "PostgreSQL Server: $POSTGRES_SERVER"
    print_status "OK" "Status: $PG_STATUS"
    print_status "OK" "Version: $PG_VERSION"
else
    print_status "WARN" "PostgreSQL Server '$POSTGRES_SERVER' not found"
fi
echo ""

# Check Environment Variables in Container App
echo "[7/7] Checking Container App Environment Variables..."
if az containerapp show --name "$CONTAINER_APP_NAME" --resource-group "$RESOURCE_GROUP" &> /dev/null 2>&1; then
    echo "       Checking required environment variables..."
    
    SECRETS_JSON=$(az containerapp show --name "$CONTAINER_APP_NAME" --resource-group "$RESOURCE_GROUP" --query "properties.template.containers[0].env" -o json 2>/dev/null)
    
    # Check for critical environment variables
    REQUIRED_VARS=("DB_HOST" "DB_NAME" "DB_USER" "DB_PASSWORD" "AZURE_STORAGE_CONNECTION_STRING")
    
    for var in "${REQUIRED_VARS[@]}"; do
        if echo "$SECRETS_JSON" | grep -q "\"name\": \"$var\""; then
            print_status "OK" "$var is configured"
        else
            print_status "WARN" "$var is not configured"
        fi
    done
else
    print_status "WARN" "Cannot check environment variables (Container App not found)"
fi
echo ""

# Summary
echo "================================================================================"
echo "VALIDATION SUMMARY"
echo "================================================================================"
echo ""
echo "Next Steps:"
echo "1. If warnings were found, review the Azure portal to ensure all resources are deployed"
echo "2. Run 'python scripts/test_cloud_rl_connection.py' to test API connectivity"
echo "3. Run 'python scripts/validate_json_files.py' to validate local JSON files"
echo "4. Check logs: az containerapp logs show --name $CONTAINER_APP_NAME --resource-group $RESOURCE_GROUP"
echo ""
echo "================================================================================"
