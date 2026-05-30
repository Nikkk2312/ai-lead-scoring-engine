# ADR 002: Hybrid Scoring Model (Rules + LLM)

## Status
Accepted

## Context
Lead scoring can be done purely with rules or purely with AI. Each has trade-offs:
- Rules: fast, deterministic, explainable, but rigid
- LLM: flexible, handles nuance, but slow and sometimes unpredictable

## Decision
Split scoring into two components:
- **Rule-based scorer (/60 points):** Deterministic checks against ICP criteria.
  Fast, auditable, consistent across runs.
- **LLM soft scorer (/40 points):** Ollama analyzes enriched data holistically.
  Catches signals that rules miss (positioning, messaging quality, product-market fit).

Combined score /100, bucketed into Hot (70+), Warm (40-69), Cold (0-39).

## Consequences
- Best of both worlds: speed + nuance
- Fully explainable: rule breakdown + LLM reasoning are both stored
- LLM failures degrade gracefully (0/40 soft score, still get rule score)
- Confidence score reflects data completeness, not just the score itself
- Multiple ICP profiles can share the same rule weights but get different LLM prompts
