# AI Intake Metrics Dashboard

An interactive dashboard for viewing AI intake metrics from Redshift, including volume, cycle time, productivity, and accuracy metrics.

> **This is a template!** Use this dashboard as-is, or create your own custom dashboard from this template. See [Creating Your Own Dashboard](#-creating-your-own-dashboard) below.

## 🚀 Quick Start for Team Members

**New to this dashboard?** Get started in 5 minutes:

```bash
# 1. Clone and enter the project
git clone https://github.com/dawaymouth/dash-setup.git ai-intake-dashboard
cd ai-intake-dashboard

# 2. Run automated setup
./setup.sh

# 3. Connect to VPN, then start!
./start.sh
```

The dashboard will open automatically in your browser! 

**Need help?** See the comprehensive [Team Setup Guide](TEAM_SETUP.md) for troubleshooting and detailed instructions.

### Daily Usage

```bash
./start.sh  # Start dashboard (opens browser automatically)
./stop.sh   # Stop dashboard when done
```

### Updating

The dashboard automatically notifies you when updates are available:

```bash
./update.sh  # Update to latest version
```

---

## Features

- **Volume Metrics** (Green)
  - Total faxes received by day/week/month
  - Total pages/documents
  - Category distribution

- **Cycle Time Metrics** (Red)
  - Received to Open time (excluding non-business hours)
  - Processing time (open to accept/send)

- **Productivity Metrics** (Purple/Fuchsia)
  - Faxes processed by individual
  - Average faxes per day per individual
  - Category breakdown by individual

- **Accuracy Metrics** (Blue) - Placeholder
  - Per field AI accuracy
  - Document-level accuracy
  - Identification/extraction precision

## Filters

- **Date Range**: Default last 30 days, customizable
- **AI Intake Only**: Toggle to filter suppliers with AI intake enabled
- **Supplier**: Filter by specific supplier

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   React App     │────▶│  FastAPI Server │────▶│    Redshift     │
│   (Vite + TS)   │     │   (Python 3.13) │     │    Database     │
└─────────────────┘     └─────────────────┘     └─────────────────┘
```

## Project Structure

```
ai-intake-dashboard/
├── backend/
│   ├── app/
│   │   ├── main.py           # FastAPI entry point
│   │   ├── database.py       # Redshift connection
│   │   ├── models.py         # Pydantic models
│   │   └── routers/
│   │       ├── volume.py     # Volume metrics endpoints
│   │       ├── cycle_time.py # Cycle time endpoints
│   │       ├── productivity.py # Productivity endpoints
│   │       └── suppliers.py  # Supplier endpoints
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── components/       # React components
│   │   ├── hooks/            # Custom React Query hooks
│   │   ├── api.ts            # API client
│   │   └── types.ts          # TypeScript types
│   ├── package.json
│   └── vite.config.ts
└── README.md
```

## 📖 Documentation

- **[Team Setup Guide](TEAM_SETUP.md)** - Complete guide for team members (troubleshooting, tips, FAQ)
- **[Customization Guide](CUSTOMIZATION_GUIDE.md)** - How to create your own dashboard from this template
- **[Changelog](CHANGELOG.md)** - What's new in each version
- **[API Documentation](http://localhost:8000/docs)** - Interactive API docs (when running)

---

## 🎨 Creating Your Own Dashboard

Want to build a dashboard for different metrics? Use this repository as a template!

### Step 1: Create from Template

1. Click **"Use this template"** button on GitHub (or visit the repo and click it)
2. Name your new repository (e.g., `supplier-dashboard`, `orders-dashboard`)
3. Clone your new repository

```bash
git clone https://github.com/YOUR_USERNAME/YOUR_REPO.git
cd YOUR_REPO
./setup.sh
```

### Step 2: Customize

See the **[Customization Guide](CUSTOMIZATION_GUIDE.md)** for detailed instructions on:
- Adding new metrics and SQL queries
- Creating new chart components
- Modifying filters
- Changing the color scheme

### Step 3: Share

Once your dashboard is ready:
- Push to GitHub for your team to use
- Add to the Dashboard Hub for central discovery (if your team uses it)

### Quick Customization Checklist

- [ ] Rename dashboard in `README.md` and `backend/app/main.py`
- [ ] Update/replace routers in `backend/app/routers/`
- [ ] Update/replace components in `frontend/src/components/`
- [ ] Update types in `frontend/src/types.ts`
- [ ] Update hooks in `frontend/src/hooks/useMetrics.ts`
- [ ] Test with `./start.sh`
- [ ] Update documentation

---

## 🔧 Manual Setup (Advanced)

**Note:** Most users should use `./setup.sh` instead. This section is for those who prefer manual setup or are troubleshooting.

### Backend

1. Navigate to the backend directory:
   ```bash
   cd backend
   ```

2. Create a virtual environment and activate it:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Create a `.env` file with your Redshift credentials:
   ```bash
   cp .env.example .env
   # Edit .env with your Redshift connection details
   ```

5. Start the server:
   ```bash
   uvicorn app.main:app --reload --port 8000
   ```

### Frontend

1. Navigate to the frontend directory:
   ```bash
   cd frontend
   ```

2. Install dependencies:
   ```bash
   npm install
   ```

3. Start the development server:
   ```bash
   npm run dev
   ```

4. Open http://localhost:5173 in your browser

## API Endpoints

### Volume
- `GET /api/volume/faxes` - Fax volume by time period
- `GET /api/volume/pages` - Pages statistics
- `GET /api/volume/categories` - Category distribution

### Cycle Time
- `GET /api/cycle-time/received-to-open` - Time from received to opened
- `GET /api/cycle-time/processing` - Processing time

### Productivity
- `GET /api/productivity/by-individual` - Total by individual
- `GET /api/productivity/daily-average` - Daily average by individual
- `GET /api/productivity/category-breakdown` - Category breakdown

### Suppliers
- `GET /api/suppliers/` - List suppliers
- `GET /api/suppliers/ai-enabled-count` - Count of AI-enabled suppliers

## Query Parameters

All metrics endpoints support:
- `start_date` - Start date (YYYY-MM-DD)
- `end_date` - End date (YYYY-MM-DD)
- `ai_intake_only` - Boolean to filter AI-enabled suppliers
- `supplier_id` - Filter by specific supplier

## Database Tables Used

- `analytics.intake_documents` - Primary fax/document data
- `analytics.orders` - Order data
- `analytics.order_skus` - Category data
- `interim.suppliers` - Supplier information

## Technology Stack

- **Frontend**: React, TypeScript, Vite, Tailwind CSS, Recharts, React Query
- **Backend**: Python 3.13, FastAPI, redshift-connector
- **Database**: Amazon Redshift

## Development

### API Documentation
When the backend is running, visit http://localhost:8000/docs for interactive API documentation (Swagger UI).

### Building for Production

Frontend:
```bash
cd frontend
npm run build
```

Backend:
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```
