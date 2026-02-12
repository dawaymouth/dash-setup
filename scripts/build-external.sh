#!/bin/bash
set -e  # Exit on error

# Color codes for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# EXPORT_DIR: where metadata.json and dashboard-data.json live (per-org under external-exports/ or custom path)
EXPORT_DIR=""
if [ -n "$1" ]; then
    if [[ "$1" != */* ]]; then
        # No path separator: treat as org slug → external-exports/<slug>/
        CANDIDATE="external-exports/$1"
        if [ -d "$CANDIDATE" ] && [ -f "$CANDIDATE/metadata.json" ] && [ -f "$CANDIDATE/dashboard-data.json" ]; then
            EXPORT_DIR="$CANDIDATE"
        else
            echo -e "${RED}❌ Error: No export found at $CANDIDATE (need metadata.json and dashboard-data.json)${NC}"
            exit 1
        fi
    else
        # Path: use as export directory
        if [ -d "$1" ] && [ -f "$1/metadata.json" ] && [ -f "$1/dashboard-data.json" ]; then
            EXPORT_DIR="$1"
        else
            echo -e "${RED}❌ Error: Directory $1 must contain metadata.json and dashboard-data.json${NC}"
            exit 1
        fi
    fi
fi

echo "================================================================"
echo "🚀 External Dashboard Builder"
echo "================================================================"
echo ""
if [ -n "$EXPORT_DIR" ]; then
    echo "Building from existing export: $EXPORT_DIR"
    echo "  1. Copy data from export directory"
    echo "  2. Build the frontend in static data mode"
    echo "  3. Create a deployment-ready package"
else
    echo "This script will:"
    echo "  1. Export data for a specific supplier organization"
    echo "  2. Build the frontend in static data mode"
    echo "  3. Create a deployment-ready package"
fi
echo ""

# Check if we're in the right directory
if [ ! -f "backend/export_external_dashboard.py" ]; then
    echo -e "${RED}❌ Error: Must be run from project root directory${NC}"
    exit 1
fi

# Check if backend virtual environment exists
if [ ! -d "backend/venv" ]; then
    echo -e "${YELLOW}⚠️  Backend virtual environment not found${NC}"
    echo "Setting up backend..."
    cd backend
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    cd ..
    echo -e "${GREEN}✅ Backend setup complete${NC}"
    echo ""
fi

# Check if frontend dependencies are installed
if [ ! -d "frontend/node_modules" ]; then
    echo -e "${YELLOW}⚠️  Frontend dependencies not found${NC}"
    echo "Installing frontend dependencies..."
    cd frontend
    npm install
    cd ..
    echo -e "${GREEN}✅ Frontend dependencies installed${NC}"
    echo ""
fi

# Step 1: Export data (or use provided export directory / slug)
if [ -z "$EXPORT_DIR" ]; then
    echo -e "${BLUE}📥 Step 1: Export Data${NC}"
    echo "================================================================"
    cd backend
    source venv/bin/activate
    python3 export_external_dashboard.py

    EXPORT_STATUS=$?

    if [ $EXPORT_STATUS -ne 0 ]; then
        echo -e "${RED}❌ Data export failed${NC}"
        deactivate
        exit 1
    fi

    deactivate
    cd ..

    # Export writes to external-exports/<slug>/; use newest dir with both JSON files
    EXPORT_DIR=$(ls -td external-exports/*/ 2>/dev/null | while read d; do
        dir="${d%/}"
        if [ -f "$dir/metadata.json" ] && [ -f "$dir/dashboard-data.json" ]; then
            echo "$dir"
            break
        fi
    done)
    if [ -z "$EXPORT_DIR" ]; then
        echo -e "${RED}❌ No export found under external-exports/; run export first or pass org slug.${NC}"
        exit 1
    fi
    echo -e "${GREEN}✅ Using export: $EXPORT_DIR${NC}"
fi

# Always copy from EXPORT_DIR into frontend/public/data (export no longer writes there by default)
echo -e "${BLUE}📂 Copying data into frontend/public/data${NC}"
mkdir -p frontend/public/data
rm -f frontend/public/data/dashboard-data.json.gz
cp "$EXPORT_DIR/metadata.json" "$EXPORT_DIR/dashboard-data.json" frontend/public/data/
echo -e "${GREEN}✅ Copied metadata.json and dashboard-data.json from $EXPORT_DIR${NC}"
echo ""

# Step 2: Build frontend in static mode (external sharing: hide Accuracy card)
echo -e "${BLUE}🔨 Step 2: Build Frontend (Static Mode)${NC}"
echo "================================================================"
cd frontend

# Remove any full-export .gz so deploy only serves single-org JSON (avoids wrong data)
rm -f public/data/dashboard-data.json.gz

# Build with static data and external-sharing flag (hides Accuracy card)
VITE_STATIC_DATA=true VITE_EXTERNAL_SHARING=true npm run build

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Frontend build failed${NC}"
    exit 1
fi

cd ..
echo -e "${GREEN}✅ Frontend build complete${NC}"
echo ""

# Step 3: Create deployment package
echo -e "${BLUE}📦 Step 3: Create Deployment Package${NC}"
echo "================================================================"

DIST_DIR="frontend/dist"

if [ ! -d "$DIST_DIR" ]; then
    echo -e "${RED}❌ Build directory not found${NC}"
    exit 1
fi

# Check if data directory exists and has files
if [ ! -d "$DIST_DIR/data" ] || [ -z "$(ls -A $DIST_DIR/data)" ]; then
    echo -e "${YELLOW}⚠️  Data files not found in build output${NC}"
    echo "Copying data files to dist..."
    mkdir -p "$DIST_DIR/data"
    cp frontend/public/data/*.json "$DIST_DIR/data/"
    echo -e "${GREEN}✅ Data files copied${NC}"
fi

# Get supplier organization name from metadata (we always have EXPORT_DIR at this point)
METADATA_FILE="$EXPORT_DIR/metadata.json"
ORG_NAME=$(cat "$METADATA_FILE" | grep -A 2 '"supplier_organization"' | grep '"name"' | cut -d'"' -f4 | tr ' ' '-' | tr '[:upper:]' '[:lower:]')
BUILD_DATE=$(date +%Y%m%d)
PACKAGE_NAME="${ORG_NAME}-dashboard-${BUILD_DATE}"
PACKAGE_DIR="external-builds/${PACKAGE_NAME}"

# Create package directory
mkdir -p "$PACKAGE_DIR"

# Copy build files
echo "Copying build files to $PACKAGE_DIR..."
cp -r "$DIST_DIR"/* "$PACKAGE_DIR/"

# Vercel: serve /data/* as static files (don't rewrite to index.html); disable cache for data
echo '{"rewrites":[{"source":"/((?!data/).*)","destination":"/index.html"}],"headers":[{"source":"/data/(.*)","headers":[{"key":"Cache-Control","value":"no-cache, no-store, must-revalidate"}]}]}' > "$PACKAGE_DIR/vercel.json"

# Ask about password protection
echo ""
echo -e "${YELLOW}🔒 Password Protection${NC}"
echo "Would you like to password-protect this dashboard?"
read -p "Add password protection? (y/n): " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]; then
    # Check if staticrypt is installed
    if ! command -v staticrypt &> /dev/null; then
        echo "Installing StaticCrypt..."
        npm install -g staticrypt
        
        if [ $? -ne 0 ]; then
            echo -e "${RED}❌ Failed to install staticrypt${NC}"
            echo "You can install it manually later: npm install -g staticrypt"
            echo "Then run: staticrypt index.html -p YOUR_PASSWORD -r (from inside $PACKAGE_DIR)"
        fi
    fi
    
    if command -v staticrypt &> /dev/null; then
        echo ""
        echo "Enter a strong password for the dashboard:"
        read -s -p "Password: " PASSWORD
        echo ""
        read -s -p "Confirm password: " PASSWORD_CONFIRM
        echo ""
        
        if [ "$PASSWORD" = "$PASSWORD_CONFIRM" ]; then
            echo "Encrypting dashboard..."
            cd "$PACKAGE_DIR"
            staticrypt index.html -p "$PASSWORD" -r --short
            
            if [ $? -eq 0 ]; then
                echo -e "${GREEN}✅ Dashboard encrypted with password${NC}"
                echo ""
                echo -e "${YELLOW}⚠️  IMPORTANT: Save this password securely!${NC}"
                echo "Password: $PASSWORD"
                echo ""
            else
                echo -e "${RED}❌ Encryption failed${NC}"
            fi
            cd - > /dev/null
        else
            echo -e "${RED}❌ Passwords don't match. Skipping encryption.${NC}"
            echo "You can encrypt manually later:"
            echo "  cd $PACKAGE_DIR"
            echo "  staticrypt index.html -p YOUR_PASSWORD -r"
        fi
    fi
else
    echo "Skipping password protection."
    echo "You can add it later with:"
    echo "  npm install -g staticrypt"
    echo "  cd $PACKAGE_DIR"
    echo "  staticrypt index.html -p YOUR_PASSWORD -r"
fi
echo ""

# Create deployment README
cat > "$PACKAGE_DIR/DEPLOY.md" << 'EOF'
# Deployment Instructions

## Quick Deploy to Vercel (Recommended)

### 1. Install Vercel CLI (if not already installed)
```bash
npm install -g vercel
```

### 2. Deploy
```bash
vercel --prod
```

When prompted:
- Set up and deploy: **Y**
- Which scope: Select your account
- Link to existing project: **N**
- Project name: Accept default or customize
- Directory: **.**
- Override settings: **N**

### 3. Enable Password Protection

1. Go to your Vercel dashboard: https://vercel.com/dashboard
2. Select your project
3. Go to **Settings** → **Deployment Protection**
4. Enable **Password Protection**
5. Set a strong password
6. Save changes

### 4. Share with Customer

Share these items separately for security:
- Dashboard URL (from Vercel deployment)
- Password (via secure channel - not email!)

## Alternative: Deploy to Netlify

### 1. Manual Deployment
1. Go to https://app.netlify.com/drop
2. Drag and drop this entire folder
3. Your site will be live in seconds

### 2. Password Protection (Paid Plan)
- Netlify password protection requires paid plan ($19/month)
- Or use the free tier without password protection

### 3. Alternative: StaticCrypt (Free)
For free password protection on any host:

```bash
# Install StaticCrypt
npm install -g staticrypt

# Encrypt the site
staticrypt index.html -p YOUR_PASSWORD -r

# Deploy the encrypted version
```

## Updating Data

To refresh the dashboard with new data:
1. Run `./scripts/build-external.sh` again from the project root
2. Select the same organization and new date range
3. Redeploy using `vercel --prod`

The password will remain the same unless you change it in Vercel settings.

## Support

For issues or questions, contact your dashboard administrator.
EOF

echo -e "${GREEN}✅ Deployment package created${NC}"
echo ""

# Final summary
echo "================================================================"
echo -e "${GREEN}✅ Build Complete!${NC}"
echo "================================================================"
echo ""
echo "📦 Deployment Package: $PACKAGE_DIR"
echo ""
echo "Next steps:"
echo "  1. cd $PACKAGE_DIR"
echo "  2. vercel --prod"
echo "  3. Enable password protection in Vercel dashboard"
echo "  4. Share URL + password with customer"
echo ""
echo "See $PACKAGE_DIR/DEPLOY.md for detailed instructions"
echo ""
