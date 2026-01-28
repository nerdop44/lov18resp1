#!/bin/bash

# Odoo.sh Submodule Update Automation Script
# This script updates the localization submodule in a parent Odoo.sh repository
# and pushes the change to trigger a formal rebuild.

# Usage: ./tools/update_odoosh.sh <parent_repo_url> <branch> <ssh_key_path> [submodule_path]

PARENT_REPO=$1
BRANCH=$2
SSH_KEY=$3
SUBMODULE_PATH=${4:-"nerdop44/LocVe18v2"} # Default path

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

if [[ -z "$PARENT_REPO" || -z "$BRANCH" || -z "$SSH_KEY" ]]; then
    echo -e "${RED}Usage:${NC} $0 <parent_repo_url> <branch> <ssh_key_path> [submodule_path]"
    echo -e "Example: $0 git@github.com:tbriceno65/AnimalCenter.git Prueba ~/.ssh/id_odoosh_clean"
    exit 1
fi

TEMP_DIR=$(mktemp -d)
echo -e "${YELLOW}--- Updating Odoo.sh Instance ---${NC}"
echo -e "Parent Repo: $PARENT_REPO"
echo -e "Branch:      $BRANCH"
echo -e "Working Dir: $TEMP_DIR"

# 1. Clone Parent Repo
echo -e "\n${YELLOW}[1/4] Cloning parent repository...${NC}"
GIT_SSH_COMMAND="ssh -i $SSH_KEY -o IdentitiesOnly=yes -o StrictHostKeyChecking=no" \
git clone "$PARENT_REPO" "$TEMP_DIR"
cd "$TEMP_DIR" || exit

# 2. Switch to Target Branch
echo -e "\n${YELLOW}[2/4] Switching to branch $BRANCH...${NC}"
git checkout "$BRANCH"

# 3. Update Submodule
echo -e "\n${YELLOW}[3/4] Updating submodule $SUBMODULE_PATH...${NC}"
git submodule update --init --recursive
cd "$SUBMODULE_PATH" || exit
git fetch origin
git checkout Dep3 # Always target the production/staging branch for localization
git pull origin Dep3
cd "$TEMP_DIR" || exit

# 4. Commit and Push
echo -e "\n${YELLOW}[4/4] Committing and pushing update...${NC}"
git config user.email "nerdop@gmail.com"
git config user.name "Nerdo Pulido"
git add "$SUBMODULE_PATH"
git commit -m "🔧 Build: Update localization submodule to trigger Odoo.sh rebuild"

GIT_SSH_COMMAND="ssh -i $SSH_KEY -o IdentitiesOnly=yes -o StrictHostKeyChecking=no" \
git push origin "$BRANCH"

if [ $? -eq 0 ]; then
    echo -e "\n${GREEN}SUCCESS!${NC} Odoo.sh rebuild triggered for $PARENT_REPO [$BRANCH]"
else
    echo -e "\n${RED}FAILURE!${NC} Could not push to $PARENT_REPO"
fi

# Cleanup
rm -rf "$TEMP_DIR"
