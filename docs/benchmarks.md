# Benchmarks & Metrics

## Throughput

| Metric | Value | Notes |
|--------|-------|-------|
| Enrichment per company | ~5-8s | Website fetch + Wikidata + careers page |
| LLM scoring per company | ~30-40s | Ollama llama3.1:8b on CPU |
| Advanced LLM (synthesis etc.) | ~60-90s | 5 additional LLM calls for Hot/Warm |
| Full pipeline per company | ~45-60s | Enrichment + base scoring |
| Full pipeline (10 leads) | ~6-8 min | With rate limiting |
| Full pipeline (100 leads) | ~60-90 min | Batch processing |

## Accuracy

Accuracy is relative to ICP configuration. With proper ICP tuning:
- **Precision (Hot tier):** Varies - tune thresholds based on your conversion data
- **Recall:** High for companies with good web presence
- **Confidence correlation:** Lower confidence scores strongly correlate with less reliable results

## Data Coverage

| Source | Coverage | Reliability |
|--------|----------|-------------|
| Website fetch | ~95% | High (direct) |
| Wikidata firmographics | ~40-60% | High (structured) |
| Tech stack detection | ~70% | Medium (regex-based) |
| Careers page | ~50% | Medium (page structure varies) |
| LLM description | ~90% | Medium (inference-based) |
| LLM industry classification | ~90% | Medium (inference-based) |

## Resource Usage

| Resource | Usage |
|----------|-------|
| RAM (Ollama 8B) | ~5-6 GB |
| Disk (SQLite, 1000 leads) | ~5-10 MB |
| Disk (Ollama model) | ~4.9 GB |
| Network | ~1-2 MB per company |
