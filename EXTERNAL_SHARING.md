# External Dashboard Sharing Guide

This guide explains how to share the AI Intake Dashboard with external customers (suppliers, partners, etc.) in a secure, isolated way.

## Overview

The external sharing system allows you to:
- Export a snapshot of dashboard data for any supplier organization
- Create a standalone, password-protected dashboard
- Deploy to free hosting (Vercel/Netlify)
- Update data periodically without changing the URL or password

## Quick Start

```bash
# 1. Export data and build dashboard
./scripts/build-external.sh

# 2. Deploy to Vercel
cd external-builds/[organization-name]-dashboard-[date]
vercel --prod

# 3. Enable password protection in Vercel dashboard
# 4. Share URL + password with customer (via separate channels)
```

## How It Works

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│ Internal Setup (Your Environment)                           │
│                                                              │
│  Redshift DB → Export Script → Static JSON Files            │
│                                      ↓                       │
│                          Build Frontend (Static Mode)        │
│                                      ↓                       │
│                          Deployment Package                  │
└─────────────────────────────────────────────────────────────┘
                                ↓
┌─────────────────────────────────────────────────────────────┐
│ External Setup (Customer Access)                            │
│                                                              │
│  Vercel/Netlify (Password Protected)                        │
│       ↓                                                      │
│  Static Dashboard → Loads JSON Data → Interactive UI        │
│                                                              │
│  ✅ No Redshift access needed                               │
│  ✅ No VPN required                                          │
│  ✅ Password protected                                       │
└─────────────────────────────────────────────────────────────┘
```

### What Gets Exported

The export script creates static JSON files with:
- **Volume metrics**: Fax counts, pages, categories, time-of-day distribution
- **Cycle time metrics**: Received-to-open and processing times
- **Productivity metrics**: Individual performance, daily averages
- **Accuracy metrics**: Per-field accuracy, document-level, trends
- **Metadata**: Organization info, date range, export timestamp

**Important Security Notes:**
- Only data for the selected supplier organization
- Aggregated metrics only (no individual document details)
- No PII or sensitive customer information
- Redshift credentials never exported
- Other suppliers' data excluded

## Step-by-Step Guide

### Step 1: Export Data

Run the interactive export tool:

```bash
./scripts/build-external.sh
```

The script will:
1. Show list of all supplier organizations from your database
2. Prompt you to select one
3. Ask for date range (last 30/90/180 days, YTD, or custom)
4. Export all metrics data to JSON files
5. Build the frontend in static mode
6. Create a deployment-ready package

Example interaction:
```
================================================================
🚀 External Dashboard Data Export Tool
================================================================

📋 Fetching supplier organizations...

✅ Found 45 supplier organizations:

  1. Cardinal Health                     (3 suppliers, 15,234 faxes) ✓ AI Enabled
  2. McKesson Corporation                (5 suppliers, 22,109 faxes) ✓ AI Enabled
  3. AmerisourceBergen                   (2 suppliers, 8,456 faxes)   No AI
  ...

Select organization (1-45): 1

✅ Selected: Cardinal Health (ID: 123)

📅 Date Range Options:
1. Last 30 days
2. Last 90 days (quarter)
3. Last 6 months
4. Year to date (2026)
5. Custom range

Select option (1-5): 2

✅ Date range: 2025-11-01 to 2026-02-05
```

#### Exporting multiple dashboards (no interference)

External exports go **by default** to `external-exports/<org-slug>/` (e.g. "Cardinal Health" → `external-exports/cardinal-health/`). Each org has its own directory; re-exporting the same org overwrites only that org's data.

- **Export then build (no argument):** Run `./scripts/build-external.sh`. The script runs the export (which writes to `external-exports/<slug>/`), then builds from that export and creates a package.
- **Build from an existing export:** Run `./scripts/build-external.sh <org-slug>` (e.g. `./scripts/build-external.sh cardinal-health`) to build from `external-exports/<slug>/` without re-exporting. You can also pass a full path: `./scripts/build-external.sh external-exports/cardinal-health` or a custom directory that contains `metadata.json` and `dashboard-data.json`.

Each build produces a separate package under `external-builds/`. To override the default output location for a one-off export, use `--output-dir` when running the export script directly.

### Step 2: Deploy to Vercel

Navigate to the generated package:

```bash
cd external-builds/cardinal-health-dashboard-20260205
```

#### Option A: Vercel CLI (Recommended)

```bash
# Install Vercel CLI (one-time)
npm install -g vercel

# Deploy
vercel --prod
```

Follow the prompts:
- **Set up and deploy**: Y
- **Which scope**: Select your account
- **Link to existing project**: N (first time) or Y (updating)
- **Project name**: Accept default or customize
- **Directory**: . (current directory)
- **Override settings**: N

You'll receive a deployment URL like: `https://cardinal-dashboard.vercel.app`

#### Option B: Vercel Dashboard (Drag & Drop)

1. Go to https://vercel.com/new
2. Drag and drop the entire package folder
3. Click Deploy

### Step 3: Enable Password Protection

#### Vercel Password Protection (Recommended)

1. Go to https://vercel.com/dashboard
2. Select your project
3. Navigate to **Settings** → **Deployment Protection**
4. Enable **Password Protection**
5. Set a strong password (e.g., generate with 1Password/LastPass)
6. Click **Save**

**Benefits:**
- Server-side protection (can't be bypassed)
- Free on all Vercel plans
- Easy to change password
- Works immediately

#### Alternative: StaticCrypt (for other hosts)

For GitHub Pages, basic Netlify, or other static hosts:

```bash
# Install StaticCrypt
npm install -g staticrypt

# Encrypt the site
staticrypt index.html YOUR_PASSWORD -r

# Deploy the encrypted version
```

**Note:** StaticCrypt is client-side encryption, less secure than Vercel's server-side protection.

### Step 4: Share with Customer

**Security Best Practices:**

1. **Separate Communication Channels:**
   - Share URL via email/Slack
   - Share password via different channel (phone, SMS, password manager)
   - Never put both in the same message

2. **Password Management:**
   - Use a strong, unique password per customer
   - Store in your team's password manager
   - Document who has access

3. **Example Communication:**

Email to customer:
```
Subject: Cardinal Health - AI Intake Metrics Dashboard

Hi [Name],

I've created a custom dashboard for you to view your AI intake 
performance metrics. You can access it here:

https://cardinal-dashboard.vercel.app

The password has been sent separately via [SMS/phone/secure channel].

This dashboard shows your metrics from Nov 1, 2025 to Feb 5, 2026.
Let me know if you have any questions!

Best,
[Your Name]
```

Separate message (via phone/SMS):
```
Dashboard password: [generated-password]

Please change this after first login if prompted, or contact 
me if you'd like it changed.
```

## Updating Data

To refresh the dashboard with new data:

```bash
# 1. Run the build script again
./scripts/build-external.sh

# 2. Select the same organization
# 3. Choose new date range

# 4. Deploy the update
cd external-builds/[new-package-name]
vercel --prod

# If you previously linked to a project:
# The URL stays the same
# The password stays the same
# Only the data updates
```

**Note:** If you used a custom domain or specific project name, make sure to link to the same project during deployment to keep the same URL.

## Password Rotation

To change the password:

### Vercel
1. Go to your project in Vercel dashboard
2. Settings → Deployment Protection
3. Update the password
4. Save changes
5. Notify the customer of the new password

### StaticCrypt
1. Re-encrypt the site with new password
2. Redeploy
3. Notify the customer

**Recommendation:** Rotate passwords periodically (every 3-6 months) or when team members with access leave.

## Monitoring Access

### Vercel Analytics (Optional)

Enable analytics to see:
- Page views
- Unique visitors
- Performance metrics

Go to: Project → Analytics (available on Pro plan)

### Alternative: Google Analytics

Add Google Analytics to track usage:
1. Get tracking ID from Google Analytics
2. Add to `frontend/index.html` before deploying
3. Rebuild and redeploy

## Multiple Customers

To share with multiple customers:

1. **Run build script for each customer separately**
   - Each gets their own deployment package
   - Each has their own static data

2. **Deploy each to separate Vercel project**
   - Different URLs
   - Different passwords
   - Independent updates

3. **Organization:**
   ```
   external-builds/
   ├── cardinal-health-dashboard-20260205/
   ├── mckesson-dashboard-20260205/
   └── amerisource-dashboard-20260205/
   ```

## Troubleshooting

### Export Script Fails

**Problem:** Script can't connect to Redshift

**Solution:**
- Make sure you're connected to VPN
- Check backend/.env has correct credentials
- Test with: `cd backend && source venv/bin/activate && python -c "from app.database import execute_query; print(execute_query('SELECT 1'))"`

### Build Fails

**Problem:** Frontend build errors

**Solution:**
```bash
cd frontend
rm -rf node_modules package-lock.json
npm install
npm run build
```

### Data Not Showing

**Problem:** Dashboard loads but shows no data

**Solution:**
- Check that `dist/data/` directory has JSON files
- Verify JSON files are valid: `cat dist/data/metadata.json`
- Check browser console for errors
- Ensure environment variable was set: `VITE_STATIC_DATA=true`

### Password Not Working

**Problem:** Password doesn't work after enabling in Vercel

**Solution:**
- Wait 1-2 minutes for deployment to propagate
- Try in incognito/private browsing mode
- Clear browser cache
- Verify password protection is enabled in Vercel dashboard

## Cost

- **Vercel Free Tier:**
  - 100GB bandwidth/month
  - Unlimited projects
  - Password protection included
  - Custom domains (1 per project)

- **Netlify Free Tier:**
  - 100GB bandwidth/month
  - Password protection requires paid plan ($19/month)

- **GitHub Pages:**
  - Free, unlimited bandwidth
  - No built-in password protection (use StaticCrypt)

**Recommendation:** Vercel free tier is perfect for most use cases.

## Security Checklist

Before sharing a dashboard:

- [ ] Verified only correct organization's data is included
- [ ] Checked no PII or sensitive info in exported data
- [ ] Enabled password protection
- [ ] Used strong, unique password
- [ ] Shared URL and password via separate channels
- [ ] Documented who has access
- [ ] Tested dashboard loads correctly
- [ ] Confirmed date range is correct
- [ ] Set calendar reminder to rotate password

## Support

For issues or questions:
- Check this guide first
- Review [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
- Contact your dashboard administrator
- Open issue on GitHub (if applicable)

## Advanced Topics

### Custom Domains

To use a custom domain (e.g., `cardinal.yourdomain.com`):

1. Vercel Dashboard → Project → Settings → Domains
2. Add your domain
3. Configure DNS records as instructed
4. Vercel automatically provisions SSL certificate

### Automated Updates

To automate periodic updates:

```bash
# Create a cron job or GitHub Action
# Example: Update every Monday at 9 AM

0 9 * * 1 cd /path/to/project && ./scripts/build-external.sh --auto --org-id=123 --days=90 && cd external-builds/* && vercel --prod
```

### Whitelabel

To customize branding:

1. Update `frontend/index.html` title and favicon
2. Modify `frontend/src/App.tsx` header
3. Change color scheme in `frontend/tailwind.config.js`
4. Rebuild and redeploy

### API Keys (Alternative Approach)

If you need real-time data instead of snapshots, consider:
1. Add API key authentication to backend
2. Deploy backend to cloud (AWS, GCP, Cloud Run)
3. Give customer read-only API key
4. Deploy frontend pointing to hosted backend

**Trade-offs:**
- ✅ Real-time data
- ✅ No manual updates needed
- ❌ Exposes Redshift connection (via backend)
- ❌ Ongoing infrastructure costs
- ❌ More complex security management

---

## Summary

The external sharing system provides a secure, cost-effective way to share dashboard insights with customers:

1. **One-time setup** (~5 minutes per customer)
2. **Free hosting** with password protection
3. **No infrastructure** to maintain
4. **Easy updates** (re-run script, redeploy)
5. **Complete data isolation** per customer

This approach is ideal for periodic reporting (weekly, monthly, quarterly) where real-time data is not required.
