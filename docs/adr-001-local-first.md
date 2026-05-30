# ADR 001: Local-First Architecture

## Status
Accepted

## Context
We needed to build a lead scoring engine that could be demonstrated as a portfolio project
without requiring paid API subscriptions or cloud infrastructure.

## Decision
Build everything to run locally first:
- **Ollama** for LLM inference instead of OpenAI/Claude API
- **SQLite** for persistence instead of cloud databases
- **Free APIs** (Wikidata, direct website scraping) instead of paid enrichment (Clearbit, Apollo)
- **Flask** for the dashboard instead of a SaaS frontend

## Consequences
- Zero ongoing costs - entire stack runs on a laptop
- No API key management for core functionality
- Slower LLM inference (~30-40s per company with 8B model)
- Less enrichment data than paid sources (mitigated by LLM inference)
- Easy to extend with paid providers (Apollo, Clay, HubSpot) when available
