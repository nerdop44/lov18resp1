#!/bin/bash

# Odoo.sh Rebuild Script for Prueba2
# This script triggers a rebuild by syncing files and updating the submodule pointer

ODOOSH_HOST="28010585@tbriceno65-animalcenter-prueba2-28010585.dev.odoo.com"
SUBMODULE_PATH="nerdop44/LocVe18v2"
LOCAL_REPO="/home/nerdop/laboratorio/LocVe18v2"
BRANCH="Prueba2"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${YELLOW}=== Odoo.sh Rebuild Script (Prueba2) ===${NC}"
echo -e "Local Repo:  $LOCAL_REPO"
echo -e "Remote Host: $ODOOSH_HOST"
echo -e "Branch:      $BRANCH"

# Step 1: Push local changes to GitHub
echo -e "\n${YELLOW}[1/4] Pushing local changes to GitHub...${NC}"
cd "$LOCAL_REPO" || exit 1
git push origin Dep3 || {
    echo -e "${RED}ERROR: Failed to push to GitHub${NC}"
    exit 1
}

LATEST_COMMIT=$(git log -1 --format="%h - %s")
echo -e "${GREEN}✓ Pushed: $LATEST_COMMIT${NC}"

# Step 2: Sync files to Odoo.sh (backup method)
echo -e "\n${YELLOW}[2/4] Syncing files to Odoo.sh server...${NC}"
rsync -avz --exclude='.git' "$LOCAL_REPO/" "$ODOOSH_HOST:~/src/user/$SUBMODULE_PATH/" 2>&1 | tail -5

# Step 3: Update submodule on Odoo.sh server
echo -e "\n${YELLOW}[3/4] Updating submodule on Odoo.sh...${NC}"
ssh "$ODOOSH_HOST" bash << 'ENDSSH'
cd ~/src/user/nerdop44/LocVe18v2
git fetch origin
git checkout Dep3
git pull origin Dep3 || {
    # If pull fails, just update to latest local state
    git add .
    git commit -m "Sync: Local changes" || true
}
git log --oneline -3
ENDSSH

# Step 4: Update parent repository pointer
echo -e "\n${YELLOW}[4/4] Triggering Odoo.sh rebuild...${NC}"
ssh "$ODOOSH_HOST" bash << 'ENDSSH'
cd ~/src/user
git checkout Prueba2 2>/dev/null || true
git add nerdop44/LocVe18v2
git commit -m "🔧 Build: Update localization submodule ($(date +%Y-%m-%d\ %H:%M))" || {
    echo "No changes to commit - submodule already up to date"
    exit 0
}
echo "Commit created successfully!"
GIT_SSH_COMMAND="ssh -i ~/.ssh/id_pajarolandia -o IdentitiesOnly=yes -o StrictHostKeyChecking=no" git push origin Prueba2
git log --oneline -2
ENDSSH

if [ $? -eq 0 ]; then
    echo -e "\n${GREEN}✓ SUCCESS!${NC} Rebuild triggered on Odoo.sh"
    echo -e "${YELLOW}→ Check build status at: https://www.odoo.sh/${NC}"
else
    echo -e "\n${RED}✗ FAILED${NC} Could not trigger rebuild"
    exit 1
fi
