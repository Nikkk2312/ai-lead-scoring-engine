# Changelog

All notable changes to this project will be documented in this file.

## [3.0.0] - 2024-12-01

### Added
- Tri-dimensional scoring (Fit / Engagement / Intent) with configurable weights
- Buying stage pipeline (Target > Awareness > Consideration > Decision > Purchase)
- Fit-Engagement matrix (A1-C3 HubSpot-inspired grid)
- Sales feedback loop with accept/reject/too_high/too_low
- Score decay with linear and exponential modes
- Scoring model templates (Enterprise ABM, Outbound SDR, PLG Inbound, Balanced)
- Negative scoring rules for competitor domains, unsubscribes
- Command palette (Ctrl+K) for quick navigation
- Dark/light mode with localStorage persistence
- CSV export from dashboard
- Activity feed API
- Enrichment coverage tracking on Data Quality page
- Security headers middleware (CSP, HSTS, X-Frame-Options)
- OpenAPI/Swagger specification
- GitHub Actions CI/CD pipeline
- Docker health checks

### Changed
- Dashboard fully rebuilt with glass-box explainability
- Score breakdown now shows tri-dimensional bars
- Lead detail pages include feedback buttons and score history
- Analytics page adds confidence distribution chart

## [2.0.0] - 2024-11-15

### Added
- Tier 3 features: Advanced signals (funding, headcount, tech changes)
- Tier 4 features: HubSpot CRM push, Apollo integration, Google Sheets sync
- Web dashboard with Flask + Chart.js
- Pipeline run history and audit trail
- Watchlists, cron scheduling, webhooks
- Look-alike discovery, TAM estimation, auto-ICP learning
- Contact enrichment, decision-maker finder, org-chart inference
- Case study generator, architecture decision records

## [1.0.0] - 2024-11-01

### Added
- Initial release with 40 core features
- CSV input, domain normalization, website fetch
- Wikidata enrichment, tech detection, careers scraping
- Rule-based scorer (/60) + LLM soft scorer (/40)
- Hot/Warm/Cold tier classification
- Excel + CSV output with color coding
- Multiple ICP profiles (default, enterprise, SMB)
- Slack/email notifications
- SQLite persistence with caching
