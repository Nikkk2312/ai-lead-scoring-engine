# Contributing to AI Lead Scoring Engine

## Development Setup

```bash
git clone https://github.com/yourusername/ai-lead-scoring-engine.git
cd ai-lead-scoring-engine
pip install -r requirements.txt
ollama pull llama3.1:8b
```

## Running Tests

```bash
python test_dashboard.py
```

## Project Structure

```
main.py          - CLI orchestrator
config.py        - ICP profiles, weights, secrets
database.py      - SQLite backend
ingestion.py     - CSV loading, validation
enrichment.py    - Data enrichment pipeline
scoring.py       - Rule + LLM scoring engine
signals.py       - Advanced signal detection
llm_engine.py    - LLM synthesis and outreach
contacts.py      - Decision-maker finder
intelligence.py  - Look-alikes, TAM, predictive scoring
integrations.py  - CRM and webhook integrations
notifications.py - Slack/email notifications
scheduler.py     - Cron scheduling
output.py        - Excel/CSV export
reports.py       - Explainability reports
dashboard.py     - Flask web dashboard
```

## Code Style

- Python 3.10+ with type hints where helpful
- Follow existing patterns in the codebase
- Keep functions focused and under 50 lines where possible
- Use descriptive variable names

## Pull Request Process

1. Fork the repo and create a feature branch
2. Make your changes with clear commit messages
3. Add tests if introducing new functionality
4. Ensure `python test_dashboard.py` passes
5. Submit a PR with a description of what changed and why

## Reporting Issues

Open an issue with:
- Steps to reproduce
- Expected vs actual behavior
- Python version and OS
