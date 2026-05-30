# AI Lead Scoring Engine

[![CI](https://github.com/Nikkk2312/ai-lead-scoring-engine/actions/workflows/ci.yml/badge.svg)](https://github.com/Nikkk2312/ai-lead-scoring-engine/actions)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Docker](https://img.shields.io/badge/docker-ready-blue.svg)](Dockerfile)

A self-hosted, AI-powered B2B lead scoring pipeline with **136 features** across 4 tiers. Enriches company data from free public sources and scores leads against your Ideal Customer Profile using deterministic rules + local LLM reasoning.

**Zero API costs. Fully local. Privacy-first.**

## How It Works

```
CSV Input -> Domain Cleanup -> Website Fetch -> Wikidata Lookup -> Tech Detection
  -> Careers Scrape -> LLM Analysis -> Tri-Dimensional Scoring (Fit/Engagement/Intent)
  -> Signal Synthesis -> Buying Stage Classification -> Outreach Generation
  -> Excel/CSV/Dashboard Output
```

### Scoring Architecture

```
                    +-------------------+
                    |   Total Score     |
                    |    (0-100)        |
                    +-------------------+
                   /         |          \
          +--------+   +-----------+   +--------+
          |  Fit   |   |Engagement |   | Intent |
          | (40%)  |   |  (35%)    |   | (25%)  |
          +--------+   +-----------+   +--------+
          |            |               |
     Firmographic  Behavioral     Buying Signals
     - Geography   - Job posts    - Intent keywords
     - Industry    - Tech stack   - Competitor usage
     - Size        - Web changes  - Funding news
     - Age         - Social       - Event mentions
```

## Quick Start

```bash
pip install -r requirements.txt
ollama pull llama3.1:8b

# Score sample companies
python main.py

# Score your own leads
python main.py score your_leads.csv

# Score against a specific ICP
python main.py score leads.csv --icp enterprise

# Fast mode (skip advanced signals)
python main.py score leads.csv --fast

# Start web dashboard
python main.py dashboard
```

### Docker

```bash
docker compose up -d
docker exec lead-scorer-ollama ollama pull llama3.1:8b
# Dashboard at http://localhost:5000
```

### CSV Format
```csv
company_name,domain
Stripe,stripe.com
Shopify,shopify.com
```

## Dashboard

The web dashboard provides a full-featured UI for managing and analyzing scored leads:

- **KPI overview** with tier distribution and score histograms
- **Buying stage funnel** (Target > Awareness > Consideration > Decision > Purchase)
- **Fit-Engagement matrix** (A1-C3 HubSpot-inspired grid)
- **Lead comparison** view for side-by-side analysis
- **Tri-dimensional score breakdown** (Fit / Engagement / Intent bars)
- **Glass-box explainability** with radar charts and factor attribution
- **Sales feedback loop** (accept/reject/too_high/too_low)
- **Score history** with trend charts per lead
- **Dark/light mode** with localStorage persistence
- **Command palette** (Ctrl+K) for quick navigation
- **Keyboard shortcuts** (g+d=Dashboard, g+l=Leads, g+a=Analytics, etc.)
- **Printable PDF reports** for sharing with stakeholders
- **Data quality dashboard** with enrichment coverage tracking
- **Scoring settings UI** with template application
- **User management** with role-based access (admin/editor/viewer)
- **Audit log** for compliance tracking
- **Kanban pipeline board** with drag-and-drop between stages
- **Pipeline velocity metrics** with conversion rates and win/loss analysis
- **Geographic heatmap** view with country-level breakdowns
- **Integration marketplace** with 12 connector cards
- **Workflow automation builder** with visual trigger/condition/action rules
- **Champion/Challenger A/B testing** with model versioning
- **Account-based scoring (ABM)** view with aggregate account scores
- **Leaderboard & achievement badges** for gamification
- **Import templates** for HubSpot, Salesforce, Apollo, LinkedIn
- **Natural language score explanations** on every lead detail page
- **Webhook event log** for debugging and transparency
- **Lead routing** with automatic queue assignments

## Features (136 total)

### Tier 1 - Day-1 MVP Core (15 features)
| # | Feature | Status |
|---|---------|--------|
| 1 | CSV upload input | Done |
| 2 | Manual trigger run | Done |
| 3 | Domain normalizer | Done |
| 4 | Row-by-row loop | Done |
| 5 | Website fetch | Done |
| 6 | About/messaging extract | Done |
| 7 | Wikidata firmographics | Done |
| 8 | Basic tech detection (28 tools) | Done |
| 9 | Graceful missing-data handling | Done |
| 10 | Rule-based scorer (/60) | Done |
| 11 | Local LLM soft scorer (/40) | Done |
| 12 | JSON parse + validate | Done |
| 13 | Combine + tier (Hot/Warm/Cold) | Done |
| 14 | Excel writer | Done |
| 15 | Tier color-coding | Done |

### Tier 2 - V1 Solid Product (25 features)
| # | Feature | Status |
|---|---------|--------|
| 16 | Careers-page job-signal scraper | Done |
| 17 | Job-board RSS signals | Done |
| 18 | Social/handle discovery (LinkedIn, X) | Done |
| 19 | Favicon + logo capture | Done |
| 20 | Email pattern guesser | Done |
| 21 | Company description summarizer (LLM) | Done |
| 22 | Industry classifier (LLM) | Done |
| 23 | Employee-range estimator (LLM) | Done |
| 24 | Configurable scoring weights | Done |
| 25 | Multiple ICP profiles (default, enterprise, smb) | Done |
| 26 | Negative/disqualifier rules | Done |
| 27 | Confidence score | Done |
| 28 | Score breakdown per signal | Done |
| 29 | Re-score on demand | Done |
| 30 | De-duplication | Done |
| 31 | Run history log (SQLite) | Done |
| 32 | Summary stats row | Done |
| 33 | Error/skip log | Done |
| 34 | CSV export of results | Done |
| 35 | Slack/email run notification | Done |
| 36 | Rate-limit / polite delays | Done |
| 37 | Retry on transient failure | Done |
| 38 | Caching layer (SQLite) | Done |
| 39 | Input validation | Done |
| 40 | Secrets/config separation (.env) | Done |

### Tier 3 - V2 Differentiation (30 features)
| # | Feature | Status |
|---|---------|--------|
| 41 | Funding-news detector | Done |
| 42 | Headcount-growth trend | Done |
| 43 | Tech-stack change detection | Done |
| 44 | News sentiment tagging (LLM) | Done |
| 45 | Website-change monitor | Done |
| 46 | Event/webinar mentions | Done |
| 47 | Intent keyword scanner | Done |
| 48 | Cron scheduler | Done |
| 49 | Score-freshness decay | Done |
| 50 | Score-change alerts | Done |
| 51 | Watchlist / saved segments | Done |
| 52 | Incremental enrichment | Done |
| 53 | Webhook trigger | Done |
| 54 | Queue / batch manager | Done |
| 55 | Multi-signal LLM synthesis | Done |
| 56 | Personalized outreach line | Done |
| 57 | Recommended next action | Done |
| 58 | Objection/risk flagging | Done |
| 59 | Persona/role targeting | Done |
| 60 | Competitor-usage detection | Done |
| 61 | Web dashboard (Flask) | Done |
| 62 | Filter/sort by tier & score | Done |
| 63 | Per-company detail view | Done |
| 64 | Visual score breakdown (Chart.js) | Done |
| 65 | Pipeline run dashboard | Done |
| 66 | One-click re-score button | Done |
| 67 | Full audit trail per score | Done |
| 68 | Source attribution | Done |
| 69 | Explainability report export | Done |
| 70 | Bias/quality checks | Done |

### Tier 4 - V3 Full Platform (46 features)
| # | Feature | Status |
|---|---------|--------|
| 71 | HubSpot CRM push | Done |
| 72 | Apollo provider toggle | Done |
| 73 | Clay provider toggle | Done |
| 74 | Sequencer hand-off | Done |
| 75 | Calendar/booking link inject | Done |
| 76 | Zapier/Make webhook export | Done |
| 77 | Google Sheets two-way sync | Done |
| 78 | Look-alike discovery | Done |
| 79 | Auto-ICP learning | Done |
| 80 | Lead deduping across runs | Done |
| 81 | Account hierarchy mapping (LLM) | Done |
| 82 | Total addressable market sizing | Done |
| 83 | Embeddings-based similarity | Done |
| 84 | Predictive conversion score | Done |
| 85 | Decision-maker finder (LLM) | Done |
| 86 | Contact enrichment | Done |
| 87 | Org-chart inference (LLM) | Done |
| 88 | Email verification (MX check) | Done |
| 89 | Database backend (SQLite, Postgres-ready) | Done |
| 90 | Multi-user auth (admin/editor/viewer) | Done |
| 91 | API endpoint (REST) | Done |
| 92 | Containerized deploy (Docker Compose) | Done |
| 93 | Monitoring & health checks | Done |
| 94 | Cost/usage dashboard | Done |
| 95 | Backup & restore | Done |
| 96 | Public demo mode | Done |
| 97 | Sample dataset + walkthrough | Done |
| 98 | Benchmark/metrics page | Done |
| 99 | Case-study write-up | Done |
| 100 | Architecture decision records | Done |
| 101 | Tri-dimensional scoring (Fit/Engagement/Intent) | Done |
| 102 | Buying stage pipeline (6sense-inspired) | Done |
| 103 | Fit-Engagement matrix (A1-C3 grid) | Done |
| 104 | Sales feedback loop | Done |
| 105 | Scoring model templates | Done |
| 106 | Negative scoring rules | Done |
| 107 | Dark/light mode | Done |
| 108 | Command palette (Ctrl+K) | Done |
| 109 | Keyboard shortcuts | Done |
| 110 | Printable PDF reports | Done |
| 111 | Lead comparison view | Done |
| 112 | Security headers (CSP, HSTS) | Done |
| 113 | OpenAPI/Swagger spec | Done |
| 114 | GitHub Actions CI/CD | Done |
| 115 | API key authentication | Done |
| 116 | Scoring settings UI | Done |
| 117 | Kanban pipeline board | Done |
| 118 | Pipeline velocity metrics | Done |
| 119 | Integration marketplace | Done |
| 120 | Workflow automation builder | Done |
| 121 | Lead nurture triggers | Done |
| 122 | Champion/Challenger A/B testing | Done |
| 123 | Scoring model versioning | Done |
| 124 | Webhook event log | Done |
| 125 | Account-based scoring (ABM) | Done |
| 126 | Leaderboard & gamification | Done |
| 127 | Achievement badges | Done |
| 128 | Geographic heatmap view | Done |
| 129 | Import templates (HubSpot/SF/Apollo) | Done |
| 130 | Custom field mapping | Done |
| 131 | Natural language score explanations | Done |
| 132 | API rate limiting | Done |
| 133 | Lead routing page | Done |
| 134 | GDPR data export/deletion | Done |
| 135 | SLA monitoring | Done |
| 136 | Duplicate detection | Done |

## CLI Commands

```bash
# Scoring
python main.py                              # Score sample data
python main.py score leads.csv              # Score custom CSV
python main.py score leads.csv --icp smb    # Score with SMB ICP
python main.py score leads.csv --all-icps   # Score against all ICPs
python main.py score leads.csv --fast       # Skip advanced signals/LLM

# Re-scoring
python main.py rescore                      # Re-score all (no re-enrichment)
python main.py rescore --domain stripe.com  # Re-score one company

# Dashboard
python main.py dashboard                    # Start web UI on port 5000

# Reports & Analysis
python main.py report stripe.com            # Explainability report
python main.py quality                      # Bias/quality checks
python main.py similar stripe.com           # Find look-alikes
python main.py tam                          # Estimate TAM
python main.py icp-learn                    # Auto-learn ICP weights
python main.py contacts stripe.com          # Find decision makers
python main.py case-study stripe.com        # Generate case study

# Export
python main.py export --csv                 # CSV export
python main.py export --json                # JSON export
python main.py demo                         # Export demo-safe data

# Watchlists
python main.py watchlist                    # List watchlists
python main.py watchlist create "my-list"   # Create watchlist
python main.py watchlist add "my-list" a.com,b.com

# System
python main.py stats                        # Database stats
python main.py backup                       # Backup database
```

## REST API

Start with `python main.py dashboard`, then:

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/leads` | All scored leads |
| GET | `/api/leads?tier=Hot` | Filter by tier |
| GET | `/api/leads/<domain>` | Single lead detail |
| POST | `/api/leads/bulk` | Bulk lookup by domains |
| GET | `/api/routing-rules` | Lead routing assignments |
| GET | `/api/runs` | Pipeline run history |
| GET | `/api/runs/<id>` | Run details + scores |
| POST | `/api/webhook` | Trigger via webhook |
| POST | `/api/feedback` | Submit lead feedback |
| GET | `/api/export/csv` | CSV download |
| GET | `/api/health` | Health check |
| GET | `/api/stats` | Database statistics |
| GET | `/api/activity` | Activity feed |
| GET | `/api/demo` | Public demo data |
| GET | `/api/openapi.yaml` | OpenAPI spec |
| GET | `/api/gdpr/export/<domain>` | GDPR data export |
| POST | `/api/gdpr/delete/<domain>` | GDPR deletion request |
| GET | `/api/sla` | SLA monitoring metrics |
| GET | `/api/duplicates` | Duplicate detection |

API key auth is optional - configure via the Settings page, then pass via `X-API-Key` header. Rate limited to 30 req/min per IP.

## Architecture

```
main.py          - CLI orchestrator with subcommands
config.py        - ICP profiles, scoring weights, secrets (.env)
database.py      - SQLite backend (runs, scores, cache, watchlists, contacts, audit)
ingestion.py     - CSV loading, validation, domain normalization, dedup
enrichment.py    - Website fetch, Wikidata, tech detect, careers, social, LLM analysis
scoring.py       - Tri-dimensional scorer, LLM scorer, confidence, tiers, multi-ICP
signals.py       - Funding news, headcount trends, tech changes, intent, events
llm_engine.py    - Synthesis, outreach, next action, objections, persona targeting
contacts.py      - Decision-maker finder, org chart, email verification
intelligence.py  - Look-alikes, auto-ICP, embeddings, TAM, predictive scoring
integrations.py  - HubSpot, Apollo, Clay, Google Sheets, Zapier/webhook
notifications.py - Slack webhook, email (SMTP) notifications
scheduler.py     - Cron scheduling, webhook handler, batch manager
output.py        - Excel + CSV export with tier color-coding
reports.py       - Audit trail, source attribution, explainability, quality checks
dashboard.py     - Flask web app with Chart.js, dark mode, command palette
```

## Stack

- **Python 3.11** - Core pipeline
- **Ollama + llama3.1:8b** - Local LLM (scoring, synthesis, classification)
- **SQLite** - Persistence, caching, run history
- **Flask** - Web dashboard + REST API
- **Chart.js** - Score visualizations
- **Wikidata API** - Free firmographic enrichment
- **BeautifulSoup** - HTML parsing
- **openpyxl** - Excel output
- **Docker** - Containerized deployment

## Security

- Security headers (CSP, HSTS, X-Frame-Options, X-Content-Type-Options)
- Session-based auth with role-based access control
- Optional API key authentication
- Secrets separated via .env file
- Input validation and sanitization

## Documentation

- [ADR 001: Local-First Architecture](docs/adr-001-local-first.md)
- [ADR 002: Hybrid Scoring Model](docs/adr-002-hybrid-scoring.md)
- [ADR 003: SQLite Default Database](docs/adr-003-sqlite-default.md)
- [Benchmarks & Metrics](docs/benchmarks.md)
- [OpenAPI Spec](openapi.yaml)
- [Changelog](CHANGELOG.md)
- [Contributing](CONTRIBUTING.md)

## License

MIT - see [LICENSE](LICENSE)
