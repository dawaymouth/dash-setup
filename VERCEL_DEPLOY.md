# Deploy Full AI Intake Dashboard to Vercel

This describes how to build and deploy the **full AI Intake dashboard** (all AI intake–enabled supplier organizations) as a static site on Vercel. The app loads one gzipped data file and optional metadata; no backend runs on Vercel.

## Prerequisites

- Backend can reach Redshift (VPN + `backend/.env` with Redshift credentials).
- Node.js and npm for the frontend build.

The export script uses **direct Redshift** (no backend API required). To require the backend to be up during export, pass `--check-backend`.

## 1. Export the data

From the project root:

```bash
cd backend
source venv/bin/activate   # or your venv path
python export_full_ai_dashboard.py
```

Optional arguments:

- `--start YYYY-MM-DD` — start date (default: 90 days ago).
- `--end YYYY-MM-DD` — end date (default: today).
- `--output-dir PATH` — where to write files (default: `frontend/public/data`).
- `--workers N` — parallel org workers (default: 6). Use `--no-parallel` for sequential.
- `--limit N` — process only the first N orgs (for quick testing).
- `--check-backend` — require backend API to be running (optional).

The script will:

- Fetch all AI intake–enabled supplier organizations.
- Run bulk DB queries for volume, categories, and time-of-day; then per-org DB queries (cycle time, productivity, accuracy, pages, per-supplier data) in parallel.
- Round numbers and minify JSON, then write:
  - `frontend/public/data/metadata.json`
  - `frontend/public/data/dashboard-data.json` (minified; optional for local dev)
  - `frontend/public/data/dashboard-data.json.gz` (used in production)

**Quick test:** `python export_full_ai_dashboard.py --limit 1 --no-parallel`

## 2. Build the frontend with static data

Set `VITE_STATIC_DATA=true` so the app loads from the static files instead of the API:

```bash
cd frontend
VITE_STATIC_DATA=true npm run build
```

Or add to `frontend/.env.production`:

```
VITE_STATIC_DATA=true
```

Then:

```bash
cd frontend
npm run build
```

The build output is in `frontend/dist/`. The `public/data/` folder (with `metadata.json` and `dashboard-data.json.gz`) is copied into `dist` at `dist/data/`.

## 3. Deploy to Vercel

1. Connect your repo to Vercel (or use the Vercel CLI).
2. Set the **Root Directory** to the project root (or where `frontend/` and `backend/` live).
3. **Build and Output Settings:**
   - **Build Command:** Run the export then build, e.g.  
     `cd backend && python export_full_ai_dashboard.py && cd ../frontend && VITE_STATIC_DATA=true npm run build`  
     Or, if you commit the exported `frontend/public/data/` after running the export locally, you can use:  
     `cd frontend && VITE_STATIC_DATA=true npm run build`
   - **Output Directory:** `frontend/dist`
   - **Install Command:** `cd frontend && npm install` (if root is repo root).

4. **Environment variables:** Add `VITE_STATIC_DATA=true` as an environment variable for the build if you don’t commit it in `.env.production`.

5. Deploy. The site will serve the static assets; the dashboard will fetch `/data/metadata.json` and `/data/dashboard-data.json.gz` and decompress the latter in the browser.

## Summary

| Step | Action |
|------|--------|
| 1 | Run `backend/export_full_ai_dashboard.py` (direct DB; no backend required). |
| 2 | Build frontend with `VITE_STATIC_DATA=true` so `dist/data/` contains `metadata.json` and `dashboard-data.json.gz`. |
| 3 | Deploy `frontend/dist` to Vercel (output directory: `frontend/dist`). |

No backend or API is required on Vercel; the dashboard runs entirely from the static files.
