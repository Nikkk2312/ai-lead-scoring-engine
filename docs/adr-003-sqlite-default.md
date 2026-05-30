# ADR 003: SQLite as Default Database

## Status
Accepted

## Context
The system needs persistence for: companies, scores, run history, cache, watchlists,
contacts, and audit trails. Options considered:
1. JSON files - simple but no querying
2. SQLite - zero config, powerful, portable
3. PostgreSQL - production-grade but requires setup

## Decision
Use SQLite as the default database with a migration path to PostgreSQL:
- All DB operations go through `database.py` abstraction layer
- SQLite file lives alongside the project (`lead_scorer.db`)
- Docker Compose includes an optional PostgreSQL service
- Connection string configurable via `DATABASE_URL` env var

## Consequences
- Zero setup: `pip install` and go
- Single-file backup: just copy the `.db` file
- Handles thousands of leads easily
- WAL mode enabled for concurrent dashboard reads
- PostgreSQL upgrade path when scaling to multi-user/production
