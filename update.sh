#!/bin/bash
# AI Intake Dashboard - Update Script
# Intelligently updates the dashboard and handles dependency changes

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Parse arguments
CHECK_ONLY=false
FORCE=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --check)
            CHECK_ONLY=true
            shift
            ;;
        --force)
            FORCE=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: ./update.sh [--check] [--force]"
            exit 1
            ;;
    esac
done

# Helper functions
print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

# Check for updates
print_info "Checking for updates..."

# Fetch latest from remote
git fetch origin main --quiet 2>/dev/null || git fetch origin master --quiet 2>/dev/null || true

# Get current and remote commit
LOCAL=$(git rev-parse HEAD 2>/dev/null)
REMOTE=$(git rev-parse @{u} 2>/dev/null || echo "")

if [ -z "$REMOTE" ]; then
    print_warning "Unable to check remote repository"
    exit 1
fi

if [ "$LOCAL" = "$REMOTE" ]; then
    print_success "Already up to date!"
    exit 0
fi

# Get version info
CURRENT_VERSION=$(cat VERSION 2>/dev/null || echo "unknown")
REMOTE_VERSION=$(git show origin/HEAD:VERSION 2>/dev/null || echo "unknown")

# Show update notification
echo ""
echo -e "${CYAN}╔══════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║  📦 Update Available                                 ║${NC}"
echo -e "${CYAN}╟──────────────────────────────────────────────────────╢${NC}"
echo -e "${CYAN}║  Current: v${CURRENT_VERSION}  →  Latest: v${REMOTE_VERSION}${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════════════════╝${NC}"
echo ""

# Show what's changed
print_info "Changes since your version:"
echo ""
git log --oneline --decorate --color HEAD..@{u} | head -10
echo ""

# Show relevant CHANGELOG section if it exists
if git show @{u}:CHANGELOG.md &>/dev/null; then
    echo -e "${BLUE}Recent updates:${NC}"
    # Extract the most recent version section from CHANGELOG
    git show @{u}:CHANGELOG.md | awk '/^## \[/{if(p)exit;p=1} p' | head -20
    echo ""
fi

# Check only mode
if [ "$CHECK_ONLY" = true ]; then
    echo "Run './update.sh' to install the update"
    exit 0
fi

# Ask for confirmation unless forced
if [ "$FORCE" = false ]; then
    read -p "Update now? [Y/n] " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]] && [[ ! -z $REPLY ]]; then
        print_info "Update cancelled"
        exit 0
    fi
fi

# Check for local modifications
if [ -n "$(git status --porcelain)" ]; then
    print_warning "You have local modifications"
    print_info "Stashing local changes..."
    git stash push -m "Auto-stash before update at $(date)"
    STASHED=true
else
    STASHED=false
fi

# Store file hashes before update to detect dependency changes
REQUIREMENTS_BEFORE=$(git show HEAD:backend/requirements.txt 2>/dev/null | md5 || echo "")
PACKAGE_JSON_BEFORE=$(git show HEAD:frontend/package.json 2>/dev/null | md5 || echo "")

# Pull updates
print_info "Pulling updates..."
git pull --quiet

REQUIREMENTS_AFTER=$(cat backend/requirements.txt 2>/dev/null | md5 || echo "")
PACKAGE_JSON_AFTER=$(cat frontend/package.json 2>/dev/null | md5 || echo "")

# Restore stashed changes if any
if [ "$STASHED" = true ]; then
    print_info "Restoring your local changes..."
    git stash pop --quiet || print_warning "Could not automatically restore changes. Run 'git stash list' to see stashed changes."
fi

print_success "Code updated"

# Check if dependencies changed and update them
NEEDS_RESTART=false

if [ "$REQUIREMENTS_AFTER" != "$REQUIREMENTS_BEFORE" ]; then
    print_info "Python dependencies changed, updating..."
    cd backend
    source venv/bin/activate
    pip install -r requirements.txt --quiet
    cd ..
    print_success "Python dependencies updated"
    NEEDS_RESTART=true
fi

if [ "$PACKAGE_JSON_AFTER" != "$PACKAGE_JSON_BEFORE" ]; then
    print_info "Node.js dependencies changed, updating..."
    cd frontend
    npm install --silent
    cd ..
    print_success "Node.js dependencies updated"
    NEEDS_RESTART=true
fi

# Final summary
NEW_VERSION=$(cat VERSION 2>/dev/null || echo "unknown")

echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  ✓ Update Complete!                                  ║${NC}"
echo -e "${GREEN}╟──────────────────────────────────────────────────────╢${NC}"
echo -e "${GREEN}║  Updated to v${NEW_VERSION}${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════╝${NC}"
echo ""

if [ "$NEEDS_RESTART" = true ]; then
    print_warning "Dependencies were updated. Please restart the dashboard:"
    echo "  ${BLUE}./stop.sh${NC}"
    echo "  ${BLUE}./start.sh${NC}"
else
    print_info "Restart the dashboard to use the new version:"
    echo "  ${BLUE}./stop.sh${NC}"
    echo "  ${BLUE}./start.sh${NC}"
fi

echo ""
