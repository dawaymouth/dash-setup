#!/bin/bash
# AI Intake Dashboard - Start Script
# Starts both backend and frontend with health checks and update notifications

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
NC='\033[0m' # No Color

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

print_header() {
    echo ""
    echo -e "${MAGENTA}═══════════════════════════════════════════════════${NC}"
    echo -e "${MAGENTA}  $1${NC}"
    echo -e "${MAGENTA}═══════════════════════════════════════════════════${NC}"
    echo ""
}

# Cleanup function
cleanup() {
    if [ -n "$BACKEND_PID" ]; then
        kill $BACKEND_PID 2>/dev/null || true
    fi
    if [ -n "$FRONTEND_PID" ]; then
        kill $FRONTEND_PID 2>/dev/null || true
    fi
}

trap cleanup EXIT INT TERM

# Get current version
CURRENT_VERSION=$(cat VERSION 2>/dev/null || echo "unknown")

print_header "AI Intake Dashboard v${CURRENT_VERSION}"

# Check for updates (once per day)
LAST_UPDATE_CHECK=".last_update"
SHOULD_CHECK_UPDATE=false

if [ ! -f "$LAST_UPDATE_CHECK" ]; then
    SHOULD_CHECK_UPDATE=true
else
    # Check if last update check was more than 24 hours ago
    if [[ "$OSTYPE" == "darwin"* ]]; then
        LAST_CHECK=$(stat -f %m "$LAST_UPDATE_CHECK" 2>/dev/null || echo 0)
    else
        LAST_CHECK=$(stat -c %Y "$LAST_UPDATE_CHECK" 2>/dev/null || echo 0)
    fi
    NOW=$(date +%s)
    HOURS_SINCE=$(( ($NOW - $LAST_CHECK) / 3600 ))
    
    if [ $HOURS_SINCE -gt 24 ]; then
        SHOULD_CHECK_UPDATE=true
    fi
fi

if [ "$SHOULD_CHECK_UPDATE" = true ]; then
    # Run git operations in subshell with set +e - never let failures exit main script
    TMP_UPDATE=$(mktemp 2>/dev/null || echo "/tmp/dash-update-$$")
    (
        set +e
        git rev-parse --is-inside-work-tree >/dev/null 2>&1 || exit 0
        git fetch origin main --quiet 2>/dev/null || git fetch origin master --quiet 2>/dev/null || true
        LOCAL=$(git rev-parse HEAD 2>/dev/null) || true
        REMOTE=$(git rev-parse @{u} 2>/dev/null || echo "")
        [ -z "$REMOTE" ] || [ "$LOCAL" = "$REMOTE" ] && exit 0
        REMOTE_VERSION=$(git show origin/HEAD:VERSION 2>/dev/null || echo "unknown")
        echo "$REMOTE_VERSION" > "$TMP_UPDATE"
    ) 2>/dev/null || true
    
    if [ -s "$TMP_UPDATE" ]; then
        REMOTE_VERSION=$(cat "$TMP_UPDATE")
        rm -f "$TMP_UPDATE"
        print_info "Checking for updates..."
        echo ""
        echo -e "${CYAN}╔══════════════════════════════════════════════════════╗${NC}"
        echo -e "${CYAN}║  📦 Update Available: v${CURRENT_VERSION} → v${REMOTE_VERSION}${NC}"
        echo -e "${CYAN}╟──────────────────────────────────────────────────────╢${NC}"
        CHANGES=$(git log --oneline --decorate HEAD..@{u} 2>/dev/null | head -3 | sed 's/^/║  • /') || true
        [ -n "$CHANGES" ] && echo -e "${CYAN}${CHANGES}${NC}"
        echo -e "${CYAN}╟──────────────────────────────────────────────────────╢${NC}"
        echo -e "${CYAN}║  To update: ./update.sh                              ║${NC}"
        echo -e "${CYAN}╚══════════════════════════════════════════════════════╝${NC}"
        echo ""
        read -p "Continue with current version? [y/N] " -n 1 -r || REPLY="y"
        echo ""
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            print_info "Run './update.sh' to update, then restart"
            exit 0
        fi
    fi
    rm -f "$TMP_UPDATE"
    touch "$LAST_UPDATE_CHECK"
fi

# Check if backend .env exists
if [ ! -f "backend/.env" ]; then
    print_error "Backend .env file not found"
    print_info "Please run './setup.sh' first"
    exit 1
fi

# Load environment variables to check connection
source backend/.env 2>/dev/null || true

# Check VPN connection (by trying to reach Redshift host)
if [ -n "$REDSHIFT_HOST" ]; then
    print_info "Checking VPN/database connectivity..."
    
    if nc -z -w 2 "$REDSHIFT_HOST" "${REDSHIFT_PORT:-5439}" 2>/dev/null; then
        print_success "Database reachable"
    else
        print_error "Cannot reach database at $REDSHIFT_HOST"
        print_warning "Please ensure you are connected to VPN"
        read -p "Try starting anyway? [y/N] " -n 1 -r
        echo ""
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
fi

# Check if ports are already in use
if lsof -Pi :8000 -sTCP:LISTEN -t >/dev/null 2>&1; then
    print_warning "Port 8000 already in use"
    read -p "Stop existing process and continue? [y/N] " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        lsof -ti:8000 | xargs kill -9 2>/dev/null || true
        sleep 1
    else
        exit 1
    fi
fi

if lsof -Pi :5173 -sTCP:LISTEN -t >/dev/null 2>&1; then
    print_warning "Port 5173 already in use"
    read -p "Stop existing process and continue? [y/N] " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        lsof -ti:5173 | xargs kill -9 2>/dev/null || true
        sleep 1
    else
        exit 1
    fi
fi

# Start Backend
print_info "Starting backend..."

cd backend
source venv/bin/activate

# Start uvicorn in background
nohup uvicorn app.main:app --host 127.0.0.1 --port 8000 > ../backend.log 2>&1 &
BACKEND_PID=$!

cd ..

# Wait for backend to be ready
print_info "Waiting for backend to be ready..."
for i in {1..30}; do
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        print_success "Backend started (PID: $BACKEND_PID)"
        break
    fi
    sleep 1
    if [ $i -eq 30 ]; then
        print_error "Backend failed to start"
        print_info "Check backend.log for details"
        exit 1
    fi
done

# Verify database connectivity
HEALTH_RESPONSE=$(curl -s http://localhost:8000/health)
if echo "$HEALTH_RESPONSE" | grep -q '"database":"connected"'; then
    print_success "Database connected"
elif echo "$HEALTH_RESPONSE" | grep -q '"database":"disconnected"'; then
    print_error "Database connection failed"
    print_warning "Backend is running but cannot connect to database"
    print_info "Please check your VPN connection and credentials"
    read -p "Continue anyway? [y/N] " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Start Frontend
print_info "Starting frontend..."

cd frontend

# Start Vite dev server in background
nohup npm run dev > ../frontend.log 2>&1 &
FRONTEND_PID=$!

cd ..

# Wait for frontend to be ready
print_info "Waiting for frontend to be ready..."
for i in {1..30}; do
    if curl -s http://localhost:5173 > /dev/null 2>&1; then
        print_success "Frontend started (PID: $FRONTEND_PID)"
        break
    fi
    sleep 1
    if [ $i -eq 30 ]; then
        print_error "Frontend failed to start"
        print_info "Check frontend.log for details"
        exit 1
    fi
done

# Success!
echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  ✓ Dashboard Running!                                ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "  ${BLUE}Version:${NC}  v${CURRENT_VERSION}"
echo -e "  ${BLUE}Frontend:${NC} http://localhost:5173"
echo -e "  ${BLUE}Backend:${NC}  http://localhost:8000"
echo -e "  ${BLUE}API Docs:${NC} http://localhost:8000/docs"
echo ""
echo -e "  ${YELLOW}Logs:${NC}"
echo -e "    Backend:  ${CYAN}tail -f backend.log${NC}"
echo -e "    Frontend: ${CYAN}tail -f frontend.log${NC}"
echo ""
echo -e "  ${YELLOW}To stop:${NC} ${CYAN}./stop.sh${NC} or press ${CYAN}Ctrl+C${NC}"
echo ""

# Open browser
print_info "Opening dashboard in browser..."
sleep 2
if command -v open &> /dev/null; then
    open http://localhost:5173
else
    print_info "Please open http://localhost:5173 in your browser"
fi

# Keep script running
echo ""
print_info "Press Ctrl+C to stop the dashboard"
echo ""

# Wait for user interrupt
trap cleanup INT TERM
wait
