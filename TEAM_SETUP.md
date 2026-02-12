# AI Intake Dashboard - Team Setup Guide

Welcome! This guide will help you get the AI Intake Dashboard running on your Mac in about 5 minutes.

## Quick Start

```bash
# 1. Clone the repository
git clone https://github.com/dawaymouth/dash-setup.git ai-intake-dashboard
cd ai-intake-dashboard

# 2. Run setup (one time only)
./setup.sh

# 3. Connect to VPN and start!
./start.sh
```

That's it! The dashboard will open automatically in your browser.

---

## Prerequisites

Before you begin, make sure you have:

- [ ] Mac with macOS 12 or later
- [ ] VPN access configured (ask your team lead if you don't have this)
- [ ] Git installed (check with `git --version`)
- [ ] 5 minutes of your time

**Note:** The setup script will automatically install Python and Node.js if needed. Python 3.10–3.13 is required; Python 3.14+ is not yet supported by pydantic.

---

## First-Time Setup

### Step 1: Get the Code

```bash
git clone https://github.com/dawaymouth/dash-setup.git new-dash
cd new-dash
```

### Step 2: Run Setup Script

```bash
./setup.sh
```

The setup script will:
- Check for and install prerequisites (Python, Node.js)
- Create Python virtual environment
- Install all dependencies
- Prompt you for Redshift credentials
- Validate database connection
- Set up Git hooks

**Redshift Credentials**: When prompted during setup:
- **Host, Port, Database**: Same for everyone (ask team lead or check with a colleague)
- **Username & Password**: Your personal credentials (unique to you)

Ask your team lead if you don't have Redshift credentials yet.

### Step 3: Connect to VPN

Before starting the dashboard, **connect to your VPN**. The dashboard needs VPN access to reach the Redshift database.

### Step 4: Start the Dashboard

```bash
./start.sh
```

The dashboard will:
- Check for updates
- Validate VPN connection
- Start the backend and frontend
- Open automatically in your browser at http://localhost:5173

---

## Daily Usage

Every time you want to use the dashboard:

1. **Connect to VPN** (critical!)
2. Run `./start.sh`
3. Dashboard opens in browser automatically
4. When done, run `./stop.sh` or press `Ctrl+C`

```bash
# Start
./start.sh

# Stop
./stop.sh
```

---

## Updating the Dashboard

The dashboard automatically checks for updates when you start it.

### Automatic Update Notification

When you run `./start.sh`, you'll see:

```
╔══════════════════════════════════════════════════════╗
║  📦 Update Available: v1.0.0 → v1.1.0                ║
╟──────────────────────────────────────────────────────╢
║  • Added supplier performance trends                 ║
║  • Fixed date picker bug                             ║
╟──────────────────────────────────────────────────────╢
║  To update: ./update.sh                              ║
╚══════════════════════════════════════════════════════╝

Continue with current version? [y/N]
```

You can:
- Press `N` to update first, or
- Press `Y` to continue with current version

### Updating Manually

To update at any time:

```bash
./update.sh
```

The update script will:
- Show you what changed
- Ask for confirmation
- Pull latest code
- Automatically detect and update dependencies
- Tell you if you need to restart

**After updating:**
```bash
./stop.sh
./start.sh
```

### Check for Updates Without Installing

```bash
./update.sh --check
```

---

## Troubleshooting

### Cannot Connect to Redshift

**Symptom:** Error message about database connection failed

**Solutions:**

1. **Check VPN connection:**
   - Look for VPN icon in menu bar
   - Try disconnecting and reconnecting
   - Verify you can access other internal resources

2. **Verify credentials:**
   - Check `backend/.env` file has correct values
   - Host, port, database should match team's (same for everyone)
   - Username and password should be YOUR personal credentials
   - Look for typos in hostname, username, or password

3. **Test connection:**
   ```bash
   cd backend
   source venv/bin/activate
   python -c "from app.database import execute_query; print(execute_query('SELECT 1'))"
   ```

### Port Already in Use

**Symptom:** "Port 8000 already in use" or "Port 5173 already in use"

**Solution:**

```bash
# Stop any running instances
./stop.sh

# Or manually kill processes
lsof -ti:8000 | xargs kill -9
lsof -ti:5173 | xargs kill -9

# Then start again
./start.sh
```

### Module Not Found Errors

**Symptom:** Python or Node module errors

**Solution:** Dependencies may have changed. Reinstall:

```bash
./setup.sh
```

This is safe to run multiple times and will reinstall all dependencies.

### Update Failed / Git Conflicts

**Symptom:** `git pull` fails with merge conflicts

**Cause:** You modified files locally

**Solution:**

```bash
# Save your changes temporarily
git stash

# Update
./update.sh

# Restore your changes (optional)
git stash pop
```

**Better solution:** Don't modify code locally. If you need a feature, request it from the team.

### Dashboard Slow or Unresponsive

**Solutions:**

1. **Restart the dashboard:**
   ```bash
   ./stop.sh
   ./start.sh
   ```

2. **Check Redshift load:** Ask team if database is under heavy load

3. **Clear browser cache:** 
   - Chrome: Cmd+Shift+Delete
   - Clear cached images and files

4. **Check system resources:** Activity Monitor → Look for CPU/memory issues

### Update Notification Won't Go Away

**Symptom:** Start script keeps showing update available even after updating

**Solutions:**

1. **Verify you're up to date:**
   ```bash
   git status
   # Should say "Your branch is up to date"
   ```

2. **If behind, update:**
   ```bash
   ./update.sh
   ```

3. **Reset update check:**
   ```bash
   rm .last_update
   ./start.sh
   ```

### Setup Script Fails

**Symptom:** Error during `./setup.sh`

**Solutions:**

1. **Check internet connection:** Setup needs to download packages

2. **Check Homebrew:**
   ```bash
   brew doctor
   # Fix any issues it reports
   ```

3. **Start fresh:**
   ```bash
   rm -rf backend/venv frontend/node_modules
   ./setup.sh
   ```

### SSL Certificate / pip Install Fails

**Symptom:** `CERTIFICATE_VERIFY_FAILED` during setup, or errors involving `puccinialin`/`pydantic-core` build

**Cause:** Python 3.13 has no pre-built wheels for pydantic-core on macOS, so pip builds from source. The build downloads Rust, which can fail due to SSL certificate issues on python.org's Python.

**Solutions:**

1. **Re-run setup** (the script now installs Rust via Homebrew to avoid the download):
   ```bash
   rm -rf backend/venv
   ./setup.sh
   ```
   If Rust is already installed, the script will detect it and skip installation.

2. **Pre-install Rust manually** (if Homebrew install fails):
   ```bash
   brew install rust
   rm -rf backend/venv
   ./setup.sh
   ```

3. **Manual certificate fix** (alternative—fixes system Python SSL):
   ```bash
   open "/Applications/Python 3.13/Install Certificates.command"
   ```
   (Adjust the version in the path if you use a different Python version.) Then retry `./setup.sh`.

4. **Use Homebrew Python** (handles certificates better):
   ```bash
   brew install python@3.13
   # Ensure python3 points to Homebrew: brew link python@3.13
   rm -rf backend/venv
   ./setup.sh
   ```

### pydantic-core Build Fails (ForwardRef / Python 3.13)

**Symptom:** `ForwardRef._evaluate() missing 1 required keyword-only argument: 'recursive_guard'` or build errors with pydantic-core

**Cause:** Old pydantic versions (2.5.x) use pydantic-core that doesn't support Python 3.13's API changes. The project requires pydantic>=2.9.2 for Python 3.13.

**Solution:** Ensure you've pulled the latest code—requirements.txt now specifies pydantic>=2.9.2. If you still see this, delete venv and re-run:
   ```bash
   rm -rf backend/venv
   ./setup.sh
   ```

### Python 3.14 Not Supported

**Symptom:** Same ForwardRef error when using Python 3.14

**Solution:** Install Python 3.13 and let the setup script use it:
   ```bash
   brew install python@3.13
   rm -rf backend/venv
   ./setup.sh
   ```
   The setup script will prefer python3.13 over python3.14 if both are installed.

---

## Scripts Reference

| Script | Purpose | When to Use |
|--------|---------|-------------|
| `./setup.sh` | Install everything | First time setup, after dependency changes, if things are broken |
| `./start.sh` | Start dashboard | Every time you want to use the dashboard |
| `./stop.sh` | Stop dashboard | When you're done, or to restart |
| `./update.sh` | Get latest version | When updates are available |
| `./update.sh --check` | Check for updates | Manually check without installing |
| `./update.sh --force` | Force update | Skip confirmation prompt |

---

## Useful Commands

### View Logs

```bash
# Backend logs (Python/FastAPI)
tail -f backend.log

# Frontend logs (React/Vite)
tail -f frontend.log

# Follow both
tail -f backend.log frontend.log
```

### Check Version

```bash
cat VERSION
# Or visit http://localhost:8000/version while running
```

### Check What's Running

```bash
# Check if backend is running
curl http://localhost:8000/health

# Check if frontend is running
curl http://localhost:5173
```

### Clean Start

If things are really broken, start completely fresh:

```bash
./stop.sh
rm -rf backend/venv frontend/node_modules
./setup.sh
./start.sh
```

---

## Understanding the Dashboard

### URLs

- **Frontend:** http://localhost:5173
  - The main dashboard interface you'll use
  
- **Backend API:** http://localhost:8000
  - The API that fetches data from Redshift
  
- **API Documentation:** http://localhost:8000/docs
  - Interactive API documentation (Swagger UI)
  - Useful if you want to test API endpoints directly

### Metrics

The dashboard shows four main metric types:

1. **Volume** (Green) - How many faxes, pages, documents
2. **Cycle Time** (Red) - How long things take to process
3. **Productivity** (Purple) - Who processed what
4. **Accuracy** (Blue) - AI accuracy metrics

### Filters

Use the filter bar at the top to:
- Select date range (default: last 30 days)
- Filter by supplier
- Toggle AI intake only

---

## Getting Help

### First Steps

1. Check this troubleshooting guide above
2. Look at recent changes in `CHANGELOG.md`
3. Check if your issue is in the repository issues

### Still Stuck?

- **Slack:** Post in #dashboard-support
- **Email:** Contact your team lead
- **In Person:** Ask a colleague who's already using it

### Reporting Issues

When reporting a problem, include:

1. What you were trying to do
2. What happened instead
3. Error messages (exact text)
4. Your version: `cat VERSION`
5. Relevant logs: `tail -50 backend.log` or `tail -50 frontend.log`

---

## Tips & Tricks

### Keyboard Shortcuts

While dashboard is running in terminal:
- `Ctrl+C` - Stop the dashboard
- `Cmd+T` - New terminal tab (to run other commands)

### Multiple Sessions

You can't run multiple instances on the same machine (ports will conflict). But you can:
- Run backend and frontend in separate terminals for better visibility
- Check logs in separate terminal windows

### VPN Best Practices

- Keep VPN connected while using dashboard
- If VPN disconnects, you'll see database errors
- Simply reconnect VPN and refresh browser
- No need to restart dashboard for VPN reconnections

### Quick Restart

```bash
./stop.sh && ./start.sh
```

### Check for Updates Daily

The dashboard checks once per 24 hours. To check more frequently:

```bash
./update.sh --check
```

---

## What's Next?

- Explore the dashboard and different metrics
- Try different date ranges and filters
- Check out the API docs at http://localhost:8000/docs
- Share feedback with the team

---

## FAQ

**Q: Do I need to keep the terminal open?**  
A: Yes, the dashboard runs in that terminal. Closing it will stop the dashboard.

**Q: Can I run this on Windows or Linux?**  
A: The scripts are designed for Mac. For other OS, you'll need to modify the scripts or run commands manually.

**Q: How much data can I query?**  
A: The dashboard is optimized for up to 90 days of data. Longer ranges may be slow.

**Q: Can I modify the code?**  
A: Yes, for local testing. But updates will overwrite your changes. Better to request features from the team.

**Q: Is my data secure?**  
A: Yes. Your credentials are in `.env` (not committed to Git). Data stays on your machine and Redshift.

**Q: Can I use this offline?**  
A: No, you need VPN to access Redshift. The dashboard requires database connectivity.

**Q: How do I uninstall?**  
A: Just delete the project folder. Optionally uninstall Python/Node if you installed them just for this.

---

**Last Updated:** 2026-02-05  
**Version:** 1.0.0  
**Questions?** Ask in #dashboard-support on Slack
