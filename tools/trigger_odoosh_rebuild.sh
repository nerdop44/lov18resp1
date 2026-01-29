#!/bin/bash

# Odoo.sh Rebuild Trigger Script (Direct SSH Method)
# This script updates files directly on Odoo.sh server and creates a trigger commit

ODOOSH_HOST="27984180@tbriceno65-animalcenter-prueba-27984180.dev.odoo.com"
SUBMODULE_PATH="nerdop44/LocVe18v2"
LOCAL_PATH="/home/nerdop/laboratorio/LocVe18v2"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${YELLOW}--- Odoo.sh Direct Update Script ---${NC}"
echo -e "Local Path:  $LOCAL_PATH"
echo -e "Remote Host: $ODOOSH_HOST"
echo -e "Submodule:   $SUBMODULE_PATH"

# 1. Sync files to Odoo.sh
echo -e "\n${YELLOW}[1/3] Syncing files to Odoo.sh...${NC}"
rsync -avz --exclude='.git' "$LOCAL_PATH/" "$ODOOSH_HOST:~/src/user/$SUBMODULE_PATH/" || {
    echo -e "${RED}ERROR: Failed to sync files${NC}"
    exit 1
}

# 2. Commit changes in submodule
echo -e "\n${YELLOW}[2/3] Committing changes in submodule...${NC}"
LATEST_COMMIT=$(cd "$LOCAL_PATH" && git log -1 --format="%H %s")
ssh "$ODOOSH_HOST" "cd ~/src/user/$SUBMODULE_PATH && git add . && git commit -m 'Sync: $LATEST_COMMIT' || echo 'No changes to commit'"

# 3. Update submodule pointer and trigger rebuild
echo -e "\n${YELLOW}[3/3] Triggering Odoo.sh rebuild...${NC}"
ssh "$ODOOSH_HOST" << 'ENDSSH'
cd ~/src/user
git checkout Prueba 2>/dev/null || true
git add nerdop44/LocVe18v2
echo "# Rebuild trigger $(date)" >> .rebuild_trigger
git add .rebuild_trigger
git commit -m "🔧 Build: Update localization submodule ($(date +%Y-%m-%d\ %H:%M))"
git log --oneline -3
ENDSSH

if [ $? -eq 0 ]; then
    echo -e "\n${GREEN}SUCCESS!${NC} Files synced and rebuild triggered"
    echo -e "${YELLOW}Note: Odoo.sh will auto-detect the commit and start rebuild${NC}"
else
    echo -e "\n${RED}FAILURE!${NC} Could not trigger rebuild"
    exit 1
fi
