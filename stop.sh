#!/bin/bash
# AI Intake Dashboard - Stop Script
# Gracefully stops both backend and frontend processes

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

print_info "Stopping AI Intake Dashboard..."

# Function to kill process on a port
kill_port() {
    local port=$1
    local name=$2
    
    pid=$(lsof -ti:$port 2>/dev/null)
    if [ -n "$pid" ]; then
        kill $pid 2>/dev/null
        sleep 1
        # Force kill if still running
        if kill -0 $pid 2>/dev/null; then
            kill -9 $pid 2>/dev/null
        fi
        print_success "$name stopped (port $port)"
    fi
}

# Stop backend (port 8000)
kill_port 8000 "Backend"

# Stop frontend (port 5173)
kill_port 5173 "Frontend"

print_success "Dashboard stopped"
echo ""
