# Changelog

All notable changes to the AI Intake Dashboard will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-02-05

### Added
- Initial release of AI Intake Dashboard
- Volume metrics dashboard (faxes, pages, categories)
- Cycle time metrics (received to open, processing time)
- Productivity metrics (by individual, daily average, category breakdown)
- Accuracy metrics (field-level, document-level)
- Date range filtering (default last 30 days)
- AI intake only toggle filter
- Supplier filtering
- Automated setup script for easy installation
- Smart startup script with auto-update checking
- Update script with dependency detection
- Comprehensive team documentation (TEAM_SETUP.md)
- Version tracking and health check endpoints

### Technical Details
- React 18.2.0 with TypeScript
- FastAPI 0.109.0 backend
- Redshift database integration
- Vite 5.0.11 build tool
- Tailwind CSS for styling
- Recharts for data visualization

### Update Instructions
- First time setup: Run `./setup.sh` and follow prompts
- For updates: Run `./update.sh` when notified

---

## Future Releases

Check this file for updates when the dashboard notifies you of new versions available.
