#!/bin/bash

# Configuration
REPO_NAME="LocVe18v2"
REMOTE_EXPECTED="git@github.com:nerdop44/LocVe18v2.git"
EE_MARKER="account_reports"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}--- Odoo Localization Version Check ---${NC}"

# 1. Check Directory
CURRENT_DIR=$(basename "$PWD")
if [ "$CURRENT_DIR" != "$REPO_NAME" ]; then
    echo -e "${RED}[ERROR]${NC} You are NOT in the $REPO_NAME directory (Current: $CURRENT_DIR)"
    exit 1
else
    echo -e "${GREEN}[OK]${NC} Directory is $REPO_NAME"
fi

# 2. Check Remote
REMOTE_URL=$(git remote get-url origin 2>/dev/null)
if [[ "$REMOTE_URL" != *"$REMOTE_EXPECTED"* ]]; then
    echo -e "${RED}[ERROR]${NC} Remote URL mismatch!"
    echo -e "Expected: $REMOTE_EXPECTED"
    echo -e "Found:    $REMOTE_URL"
    exit 1
else
    echo -e "${GREEN}[OK]${NC} Remote URL is correct"
fi

# 3. Check for EE markers
if [ -d "$EE_MARKER" ] || [ -d "account_dual_currency" ]; then
    # Verify account_reports dependency in account_dual_currency
    if grep -q "account_reports" account_dual_currency/__manifest__.py; then
        echo -e "${GREEN}[OK]${NC} Version identified as Odoo 18 ENTERPRISE (EE)"
    else
        echo -e "${RED}[ERROR]${NC} account_reports NOT found in manifest. Is this Community (CC)?"
        exit 1
    fi
else
    echo -e "${RED}[ERROR]${NC} Critical modules not found. Check repository integrity."
    exit 1
fi

echo -e "${GREEN}Environment verified. Safe to proceed.${NC}"
