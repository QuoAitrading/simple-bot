#!/bin/bash
# =============================================================================
# Complete Live Trading Validation Pipeline
# =============================================================================
# Runs all validation checks in sequence to ensure system is ready for live trading
# =============================================================================

# Note: Not using 'set -e' to allow graceful handling of non-critical failures

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Project root
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"

echo "================================================================================"
echo "COMPLETE LIVE TRADING VALIDATION PIPELINE"
echo "================================================================================"
echo ""
echo "Project: $PROJECT_ROOT"
echo "Date: $(date)"
echo ""

# Step 1: Auto-fix JSON files
echo "================================================================================"
echo "[1/4] Auto-fixing JSON files..."
echo "================================================================================"
python3 "$PROJECT_ROOT/scripts/fix_json_files.py"
RESULT=$?
if [ $RESULT -ne 0 ]; then
    echo -e "${RED}❌ JSON auto-fix failed${NC}"
    exit 1
fi
echo ""

# Step 2: Validate JSON files
echo "================================================================================"
echo "[2/4] Validating JSON files..."
echo "================================================================================"
python3 "$PROJECT_ROOT/scripts/validate_json_files.py"
RESULT=$?
if [ $RESULT -ne 0 ]; then
    echo -e "${RED}❌ JSON validation failed${NC}"
    exit 1
fi
echo ""

# Step 3: Test Cloud RL connection
echo "================================================================================"
echo "[3/4] Testing Cloud RL connection..."
echo "================================================================================"
python3 "$PROJECT_ROOT/scripts/test_cloud_rl_connection.py"
RESULT=$?
if [ $RESULT -ne 0 ]; then
    echo -e "${YELLOW}⚠️  Cloud RL connection test had issues (see above)${NC}"
    echo -e "${YELLOW}    This may be expected if running offline or license not configured${NC}"
    # Don't exit - allow continuation with warning
fi
echo ""

# Step 4: Run comprehensive pre-flight check
echo "================================================================================"
echo "[4/4] Running comprehensive pre-flight check..."
echo "================================================================================"
python3 "$PROJECT_ROOT/scripts/preflight_check.py"
RESULT=$?
if [ $RESULT -ne 0 ]; then
    echo -e "${RED}❌ Pre-flight check failed${NC}"
    exit 1
fi
echo ""

# Optional: Azure deployment validation (if Azure CLI is available)
if command -v az &> /dev/null; then
    echo "================================================================================"
    echo "[BONUS] Azure deployment validation (Azure CLI detected)..."
    echo "================================================================================"
    
    # Check if logged in
    if az account show &> /dev/null; then
        bash "$PROJECT_ROOT/scripts/validate_azure_deployment.sh" || echo -e "${YELLOW}⚠️  Azure validation had warnings${NC}"
    else
        echo -e "${YELLOW}⚠️  Not logged in to Azure - skipping Azure validation${NC}"
        echo "    Run 'az login' to enable Azure validation"
    fi
    echo ""
else
    echo "ℹ️  Azure CLI not found - skipping Azure deployment validation"
    echo ""
fi

# Final summary
echo "================================================================================"
echo "VALIDATION PIPELINE COMPLETE"
echo "================================================================================"
echo ""
echo -e "${GREEN}✅ All critical checks passed!${NC}"
echo ""
echo "Next steps:"
echo "  1. Review any warnings above"
echo "  2. Ensure environment variables are set:"
echo "     export BOT_ENVIRONMENT=production"
echo "     export CONFIRM_LIVE_TRADING=1"
echo "  3. Start live trading:"
echo "     python src/main.py"
echo ""
echo "================================================================================"
