#!/bin/bash
# AI Intake Dashboard - Automated Setup Script
# This script sets up the development environment for the dashboard

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
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
    echo -e "${BLUE}═══════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════${NC}"
    echo ""
}

# Check if running on macOS
if [[ "$OSTYPE" != "darwin"* ]]; then
    print_error "This script is designed for macOS"
    exit 1
fi

print_header "AI Intake Dashboard Setup"

# Check prerequisites
print_info "Checking prerequisites..."

# Check for Homebrew
if ! command -v brew &> /dev/null; then
    print_warning "Homebrew not found. Installing Homebrew..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    print_success "Homebrew installed"
else
    print_success "Homebrew found"
fi

# Check for Python 3
if ! command -v python3 &> /dev/null; then
    print_warning "Python 3 not found. Installing Python..."
    brew install python@3.13
    print_success "Python installed"
else
    PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
    print_success "Python found (version $PYTHON_VERSION)"
fi

# Check for Node.js
if ! command -v node &> /dev/null; then
    print_warning "Node.js not found. Installing Node.js..."
    brew install node@20
    print_success "Node.js installed"
else
    NODE_VERSION=$(node --version)
    print_success "Node.js found (version $NODE_VERSION)"
fi

# Setup Backend
print_header "Setting up Backend"

cd backend

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    print_info "Creating Python virtual environment..."
    python3 -m venv venv
    print_success "Virtual environment created"
else
    print_success "Virtual environment already exists"
fi

# Activate virtual environment
print_info "Activating virtual environment..."
source venv/bin/activate

# Install Python dependencies
print_info "Installing Python dependencies..."
pip install --upgrade pip --quiet
pip install -r requirements.txt --quiet
print_success "Python dependencies installed"

# Setup .env file
if [ ! -f ".env" ]; then
    print_info "Setting up environment variables..."
    echo ""
    echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${YELLOW}  Redshift Database Configuration${NC}"
    echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    echo "Please provide YOUR Redshift connection details:"
    echo "(Use your personal Redshift credentials)"
    echo ""
    
    read -p "Redshift Host: " REDSHIFT_HOST
    read -p "Redshift Port [5439]: " REDSHIFT_PORT
    REDSHIFT_PORT=${REDSHIFT_PORT:-5439}
    read -p "Redshift Database [dev]: " REDSHIFT_DATABASE
    REDSHIFT_DATABASE=${REDSHIFT_DATABASE:-dev}
    read -p "Redshift User: " REDSHIFT_USER
    read -sp "Redshift Password: " REDSHIFT_PASSWORD
    echo ""
    
    # Create .env file
    cat > .env << EOF
# Redshift Connection Settings
REDSHIFT_HOST=$REDSHIFT_HOST
REDSHIFT_PORT=$REDSHIFT_PORT
REDSHIFT_DATABASE=$REDSHIFT_DATABASE
REDSHIFT_USER=$REDSHIFT_USER
REDSHIFT_PASSWORD=$REDSHIFT_PASSWORD
EOF
    
    print_success ".env file created"
else
    print_success ".env file already exists"
fi

# Validate database connection
print_info "Validating database connection..."
python3 << 'PYTHON_EOF'
import sys
from app.database import execute_query

try:
    result = execute_query("SELECT 1")
    print("✓ Database connection successful!")
    sys.exit(0)
except Exception as e:
    print(f"✗ Database connection failed: {e}")
    print("Please check your credentials in backend/.env")
    sys.exit(1)
PYTHON_EOF

if [ $? -eq 0 ]; then
    print_success "Database connection validated"
else
    print_error "Database connection failed"
    print_warning "Please verify your credentials and VPN connection"
fi

cd ..

# Setup Frontend
print_header "Setting up Frontend"

cd frontend

# Install Node dependencies
print_info "Installing Node.js dependencies..."
npm install --silent
print_success "Node.js dependencies installed"

cd ..

# Setup Git hooks
print_header "Setting up Git Hooks"

mkdir -p .git/hooks

# Create pre-commit hook to prevent committing .env
cat > .git/hooks/pre-commit << 'EOF'
#!/bin/sh
# Prevent committing sensitive files

if git diff --cached --name-only | grep -q "backend/.env$"; then
  echo "❌ Error: Attempting to commit backend/.env with credentials!"
  echo "This file contains sensitive information and should not be committed."
  exit 1
fi
EOF

chmod +x .git/hooks/pre-commit
print_success "Git pre-commit hook installed"

# Final summary
print_header "Setup Complete!"

echo ""
echo -e "${GREEN}✓ Backend: Python environment configured${NC}"
echo -e "${GREEN}✓ Frontend: Node packages installed${NC}"
echo -e "${GREEN}✓ Database: Connection validated${NC}"
echo -e "${GREEN}✓ Git: Pre-commit hooks installed${NC}"
echo ""
echo -e "${BLUE}═══════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  Next Steps${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════${NC}"
echo ""
echo "1. Connect to your VPN"
echo "2. Run: ${GREEN}./start.sh${NC}"
echo "3. Dashboard will open automatically in your browser"
echo ""
echo "For help, see: ${BLUE}TEAM_SETUP.md${NC}"
echo ""
