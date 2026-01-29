#!/bin/bash

# Odoo.sh Submodule Update Script (Local Approach)
# This script clones the parent repo locally, updates the submodule pointer, and pushes

PARENT_REPO="https://github.com/tbriceno65/AnimalCenter.git"
BRANCH="Prueba"
SUBMODULE_PATH="nerdop44/LocVe18v2"
SUBMODULE_BRANCH="Dep3"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${YELLOW}--- Odoo.sh Submodule Update (Local) ---${NC}"
echo -e "Parent Repo: $PARENT_REPO"
echo -e "Branch:      $BRANCH"
echo -e "Submodule:   $SUBMODULE_PATH"

TEMP_DIR=$(mktemp -d)
echo -e "\nWorking Dir: $TEMP_DIR"

# 1. Clone Parent Repo
echo -e "\n${YELLOW}[1/5] Cloning parent repository...${NC}"
git clone "$PARENT_REPO" "$TEMP_DIR" || {
    echo -e "${RED}ERROR: Failed to clone parent repository${NC}"
    exit 1
}

cd "$TEMP_DIR" || exit

# 2. Switch to Target Branch
echo -e "\n${YELLOW}[2/5] Switching to branch $BRANCH...${NC}"
git checkout "$BRANCH" || {
    echo -e "${RED}ERROR: Failed to checkout branch $BRANCH${NC}"
    exit 1
}

# 3. Initialize and Update Submodule
echo -e "\n${YELLOW}[3/5] Initializing submodule...${NC}"
git submodule update --init "$SUBMODULE_PATH" || {
    echo -e "${RED}ERROR: Failed to initialize submodule${NC}"
    exit 1
}

# 4. Update Submodule to Latest Commit
echo -e "\n${YELLOW}[4/5] Updating submodule to latest $SUBMODULE_BRANCH...${NC}"
cd "$SUBMODULE_PATH" || exit
git fetch origin
git checkout "$SUBMODULE_BRANCH"
git pull origin "$SUBMODULE_BRANCH"
LATEST_COMMIT=$(git rev-parse HEAD)
echo -e "${GREEN}Latest commit: $LATEST_COMMIT${NC}"

cd "$TEMP_DIR" || exit

# 5. Commit and Push Update
echo -e "\n${YELLOW}[5/5] Committing and pushing submodule update...${NC}"
git add "$SUBMODULE_PATH"
git commit -m "🔧 Update: Sync $SUBMODULE_PATH to latest $SUBMODULE_BRANCH ($LATEST_COMMIT)" || {
    echo -e "${YELLOW}No changes to commit (submodule already up to date)${NC}"
    rm -rf "$TEMP_DIR"
    exit 0
}

git push origin "$BRANCH" || {
    echo -e "${RED}ERROR: Failed to push changes${NC}"
    exit 1
}

# Cleanup
rm -rf "$TEMP_DIR"

echo -e "\n${GREEN}SUCCESS! Submodule updated and pushed to $BRANCH${NC}"
echo -e "${GREEN}Odoo.sh should automatically rebuild now.${NC}"
