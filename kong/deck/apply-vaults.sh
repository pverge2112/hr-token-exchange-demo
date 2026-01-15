#!/bin/bash
#
# Script to apply ENV vault configuration to Kong Konnect
# This script configures Kong Gateway to read secrets from environment variables
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "=================================================="
echo "Kong ENV Vault Configuration - Apply Script"
echo "=================================================="
echo ""

# Check required environment variables
echo "Checking required environment variables..."
MISSING_VARS=()

if [ -z "$KONNECT_TOKEN" ]; then
    MISSING_VARS+=("KONNECT_TOKEN")
fi

# Check if main .env file exists
if [ -f "../../.env" ]; then
    echo -e "${GREEN}✓${NC} Found .env file, sourcing it..."
    source ../../.env
else
    echo -e "${YELLOW}⚠${NC} No .env file found at ../../.env"
fi

# Check Kong Konnect credentials
if [ -z "$KONG_CLUSTER_CONTROL_PLANE" ]; then
    MISSING_VARS+=("KONG_CLUSTER_CONTROL_PLANE")
fi

# Check Okta credentials
if [ -z "$OKTA_HR_AGENT_CLIENT_ID" ]; then
    MISSING_VARS+=("OKTA_HR_AGENT_CLIENT_ID")
fi
if [ -z "$OKTA_HR_AGENT_CLIENT_SECRET" ]; then
    MISSING_VARS+=("OKTA_HR_AGENT_CLIENT_SECRET")
fi
if [ -z "$OKTA_HR_MCP_CLIENT_ID" ]; then
    MISSING_VARS+=("OKTA_HR_MCP_CLIENT_ID")
fi
if [ -z "$OKTA_HR_MCP_CLIENT_SECRET" ]; then
    MISSING_VARS+=("OKTA_HR_MCP_CLIENT_SECRET")
fi
if [ -z "$OKTA_STREAMLIT_UI_CLIENT_ID" ]; then
    MISSING_VARS+=("OKTA_STREAMLIT_UI_CLIENT_ID")
fi

# Check AI provider credentials
if [ -z "$OPENAI_API_KEY" ]; then
    MISSING_VARS+=("OPENAI_API_KEY")
fi

if [ ${#MISSING_VARS[@]} -gt 0 ]; then
    echo -e "${RED}✗${NC} Missing required environment variables:"
    for var in "${MISSING_VARS[@]}"; do
        echo "  - $var"
    done
    echo ""
    echo "Please set these variables in your .env file or export them."
    echo "See .env.example for reference."
    exit 1
else
    echo -e "${GREEN}✓${NC} All required environment variables are set"
fi

echo ""
echo "Environment variables summary:"
echo "  OKTA_HR_AGENT_CLIENT_ID: ${OKTA_HR_AGENT_CLIENT_ID:0:20}..."
echo "  OKTA_HR_MCP_CLIENT_ID: ${OKTA_HR_MCP_CLIENT_ID:0:20}..."
echo "  OKTA_STREAMLIT_UI_CLIENT_ID: ${OKTA_STREAMLIT_UI_CLIENT_ID:0:20}..."
echo "  OPENAI_API_KEY: ${OPENAI_API_KEY:0:20}..."
echo ""

# Set decK environment variables
export DECK_KONNECT_TOKEN=$KONNECT_TOKEN
export DECK_KONNECT_CONTROL_PLANE_NAME=${DECK_KONNECT_CONTROL_PLANE_NAME:-kong-token-exchange-prototype}

echo "Applying vault configuration to Konnect..."
echo "  Control Plane: $DECK_KONNECT_CONTROL_PLANE_NAME"
echo ""

# Apply the vault configuration
if deck gateway sync -s vaults.yaml --select-tag hr-demo; then
    echo ""
    echo -e "${GREEN}✓${NC} Vault configuration applied successfully!"
    echo ""
    echo "Next steps:"
    echo "  1. Verify vault configuration:"
    echo "     deck gateway dump --select-tag hr-demo | grep -A 10 'vaults:'"
    echo ""
    echo "  2. Apply main Kong configuration:"
    echo "     deck gateway sync -s kong.yaml --select-tag hr-demo"
    echo ""
    echo "  3. Test vault resolution by calling your APIs"
    echo ""
else
    echo ""
    echo -e "${RED}✗${NC} Failed to apply vault configuration"
    exit 1
fi
