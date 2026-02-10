# Scripts Directory

This directory contains automation scripts for the AI Intake Dashboard.

## Available Scripts

### Full AI Intake Dashboard Export (Vercel)

**Purpose:** Export the full dashboard (all AI intake–enabled supplier orgs) for static deployment (e.g. Vercel).

**Script:** `backend/export_full_ai_dashboard.py`

**Usage:**
```bash
cd backend && source venv/bin/activate && python export_full_ai_dashboard.py [--start YYYY-MM-DD] [--end YYYY-MM-DD] [--workers N] [--limit N]
```

**Options:**
- `--start`, `--end` — date range (default: last 90 days).
- `--output-dir PATH` — where to write files (default: `frontend/public/data`).
- `--workers N` — parallel org workers (default: 6). Use `--no-parallel` to run sequentially.
- `--limit N` — process only the first N orgs (for testing).
- `--check-backend` — require backend API to be running (optional; export uses direct DB by default).

**Quick test (1 org, no parallel):**
```bash
cd backend && source venv/bin/activate && python export_full_ai_dashboard.py --limit 1 --no-parallel
```

**Output:** Writes to `frontend/public/data/`: `metadata.json`, `dashboard-data.json` (minified), `dashboard-data.json.gz`. Build the frontend with `VITE_STATIC_DATA=true` and deploy `frontend/dist` to Vercel. Export uses direct Redshift (no backend API required unless `--check-backend` is set).

**Docs:** [../VERCEL_DEPLOY.md](../VERCEL_DEPLOY.md)

---

### `build-external.sh`

**Purpose:** Export data and build external dashboard for sharing with customers (single org).

**Usage:**
```bash
./scripts/build-external.sh
```

**What it does:**
1. Runs the interactive data export tool
2. Prompts you to select supplier organization
3. Prompts you to select date range
4. Exports all metrics data to JSON files
5. Builds frontend in static mode
6. Creates deployment-ready package in `external-builds/`

**Requirements:**
- Backend virtual environment set up
- Frontend dependencies installed  
- Connected to VPN
- Valid Redshift credentials in `backend/.env`

**Output:**
- Deployment package in `external-builds/[org-name]-dashboard-[date]/`
- Contains built frontend + static data files
- Includes deployment instructions in `DEPLOY.md`

**Documentation:**
- Full guide: [../EXTERNAL_SHARING.md](../EXTERNAL_SHARING.md)
- Quick reference: [QUICK_REFERENCE.md](QUICK_REFERENCE.md)

## Adding New Scripts

When adding new scripts:
1. Add to this directory (`scripts/`)
2. Make executable: `chmod +x scripts/your-script.sh`
3. Add shebang: `#!/bin/bash` or `#!/usr/bin/env python3`
4. Document in this README
5. Add error handling: `set -e` for bash scripts

## Script Development Guidelines

**Bash Scripts:**
- Use `set -e` to exit on errors
- Add colored output for better UX
- Validate prerequisites before running
- Provide clear success/failure messages
- Include usage instructions in comments

**Python Scripts:**
- Add shebang: `#!/usr/bin/env python3`
- Use argparse for CLI arguments
- Validate environment and credentials
- Provide interactive prompts with defaults
- Handle errors gracefully with helpful messages

## Testing Scripts

Before committing:
1. Test on clean environment
2. Verify error handling works
3. Check output formatting
4. Ensure documentation is up to date
5. Test edge cases (missing deps, no VPN, etc.)
