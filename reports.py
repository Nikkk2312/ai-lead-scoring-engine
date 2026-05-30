"""
Features 67-70, 96, 99: Full audit trail, source attribution, explainability report,
bias/quality checks, public demo mode, case-study generation.
"""
import json
from datetime import datetime
from database import get_scores_for_run, get_errors_for_run, get_run


def build_audit_trail(score_data: dict) -> dict:
    """Feature 67: Every input + rule that produced a score is logged."""
    return {
        "timestamp": datetime.now().isoformat(),
        "company": score_data.get("company_name"),
        "domain": score_data.get("domain"),
        "inputs": {
            "website_status": score_data.get("website_status"),
            "site_text_length": len(score_data.get("site_text") or ""),
            "founding_year": score_data.get("founding_year"),
            "hq_country": score_data.get("hq_country"),
            "industry": score_data.get("industry"),
            "industry_classified": score_data.get("industry_classified"),
            "tech_stack": score_data.get("tech_stack"),
            "employee_estimate": score_data.get("employee_estimate"),
            "careers_jobs_count": score_data.get("careers_jobs_count"),
            "competitor_tech": score_data.get("competitor_tech"),
        },
        "scoring": {
            "rule_score": score_data.get("rule_score"),
            "rule_breakdown": score_data.get("rule_breakdown"),
            "soft_score": score_data.get("soft_score"),
            "total_score": score_data.get("total_score"),
            "tier": score_data.get("tier"),
            "confidence": score_data.get("confidence"),
            "icp_name": score_data.get("icp_name"),
        },
        "llm_output": {
            "reasoning": score_data.get("reasoning"),
            "key_signal": score_data.get("key_signal"),
            "synthesis": score_data.get("synthesis"),
        },
        "sources": score_data.get("sources", {}),
    }


def get_source_attribution(score_data: dict) -> list[dict]:
    """Feature 68: Cite where each enriched fact came from."""
    attributions = []

    sources = score_data.get("sources", {})
    if isinstance(sources, str):
        try:
            sources = json.loads(sources)
        except json.JSONDecodeError:
            sources = {}

    field_source_map = {
        "website_status": ("Website", "Direct HTTPS fetch"),
        "site_text": ("Website Content", "HTML text extraction via BeautifulSoup"),
        "tech_stack": ("Tech Stack", "HTML regex pattern matching"),
        "founding_year": ("Founding Year", "Wikidata API (P571)"),
        "hq_country": ("HQ Country", "Wikidata API (P17)"),
        "industry": ("Industry", "Wikidata API (P452)"),
        "industry_classified": ("Industry (AI)", "Ollama LLM classification"),
        "employee_estimate": ("Employee Estimate", "Ollama LLM inference from website signals"),
        "description": ("Company Description", "Ollama LLM summarization"),
        "social_linkedin": ("LinkedIn", "HTML link extraction"),
        "social_twitter": ("Twitter/X", "HTML link extraction"),
        "careers_jobs_count": ("Hiring Signal", "Careers page scrape"),
        "competitor_tech": ("Competitor Usage", "Tech stack + HTML keyword matching"),
    }

    for field, (label, method) in field_source_map.items():
        value = score_data.get(field)
        if value is not None and value != "" and value != [] and value != 0:
            attributions.append({
                "field": label,
                "value": str(value)[:100] if not isinstance(value, (int, float)) else value,
                "source_method": method,
                "confidence": "high" if field in ("website_status", "founding_year", "hq_country") else "medium",
            })

    return attributions


def generate_explainability_report(score_data: dict) -> str:
    """Feature 69: Per-lead text report explaining the score."""
    company = score_data.get("company_name", "Unknown")
    domain = score_data.get("domain", "")
    score = score_data.get("total_score", 0)
    tier = score_data.get("tier", "Cold")

    lines = [
        f"{'=' * 60}",
        f"LEAD SCORE EXPLAINABILITY REPORT",
        f"{'=' * 60}",
        f"Company: {company}",
        f"Domain:  {domain}",
        f"Date:    {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"",
        f"OVERALL SCORE: {score}/100 ({tier})",
        f"Confidence:    {score_data.get('confidence', 'N/A')}",
        f"ICP Profile:   {score_data.get('icp_name', 'default')}",
        f"",
        f"--- RULE-BASED SCORE ({score_data.get('rule_score', 0)}/60) ---",
    ]

    breakdown = score_data.get("rule_breakdown", {})
    if isinstance(breakdown, str):
        try:
            breakdown = json.loads(breakdown)
        except json.JSONDecodeError:
            breakdown = {}
    for signal, points in breakdown.items():
        lines.append(f"  {signal:<20} {points:>3} pts")

    lines.extend([
        f"",
        f"--- LLM SOFT SCORE ({score_data.get('soft_score', 0)}/40) ---",
        f"  Key Signal: {score_data.get('key_signal', 'N/A')}",
        f"  Reasoning:  {score_data.get('reasoning', 'N/A')}",
    ])

    if score_data.get("synthesis"):
        lines.extend([f"", f"--- SIGNAL SYNTHESIS ---", f"  {score_data['synthesis']}"])
    if score_data.get("outreach_line"):
        lines.extend([f"", f"--- SUGGESTED OUTREACH ---", f"  {score_data['outreach_line']}"])
    if score_data.get("next_action"):
        lines.extend([f"", f"--- RECOMMENDED ACTION ---", f"  {score_data['next_action']}"])
    if score_data.get("objections"):
        lines.extend([f"", f"--- OBJECTIONS/RISKS ---", f"  {score_data['objections']}"])
    if score_data.get("target_persona"):
        lines.extend([f"", f"--- TARGET PERSONA ---", f"  {score_data['target_persona']}"])

    # Source attribution
    attributions = get_source_attribution(score_data)
    if attributions:
        lines.extend([f"", f"--- DATA SOURCES ---"])
        for a in attributions:
            lines.append(f"  {a['field']}: {a['source_method']} (confidence: {a['confidence']})")

    lines.append(f"\n{'=' * 60}")
    return "\n".join(lines)


def check_bias_quality(scores: list[dict]) -> dict:
    """Feature 70: Flag scores driven by thin or stale data."""
    issues = []
    stats = {"total": len(scores), "low_confidence": 0, "missing_geo": 0,
             "missing_industry": 0, "no_website": 0, "stale_data": 0}

    for s in scores:
        confidence = s.get("confidence", 1.0)
        if confidence < 0.5:
            stats["low_confidence"] += 1
            issues.append({"domain": s.get("domain"), "issue": "low_confidence",
                          "detail": f"Confidence {confidence}"})

        if not s.get("hq_country"):
            stats["missing_geo"] += 1
        if not s.get("industry") and not s.get("industry_classified"):
            stats["missing_industry"] += 1
        if s.get("website_status") != 200:
            stats["no_website"] += 1

    # Check for geo bias
    geos = [s.get("hq_country") for s in scores if s.get("hq_country")]
    if geos:
        from collections import Counter
        geo_dist = Counter(geos)
        total_with_geo = len(geos)
        for geo, count in geo_dist.items():
            if count / total_with_geo > 0.7:
                issues.append({"domain": "ALL", "issue": "geo_concentration",
                              "detail": f"{count}/{total_with_geo} leads from {geo}"})

    # Check tier distribution
    tiers = [s.get("tier") for s in scores]
    if tiers:
        from collections import Counter
        tier_dist = Counter(tiers)
        if tier_dist.get("Hot", 0) > len(scores) * 0.5:
            issues.append({"domain": "ALL", "issue": "scoring_too_generous",
                          "detail": f">{50}% of leads are Hot"})
        if tier_dist.get("Cold", 0) > len(scores) * 0.8:
            issues.append({"domain": "ALL", "issue": "scoring_too_strict",
                          "detail": f">{80}% of leads are Cold"})

    return {"stats": stats, "issues": issues, "quality_score": _compute_quality(stats)}


def _compute_quality(stats: dict) -> str:
    total = stats.get("total", 1)
    problems = stats["low_confidence"] + stats["no_website"]
    rate = problems / max(total, 1)
    if rate < 0.1:
        return "good"
    elif rate < 0.3:
        return "fair"
    else:
        return "poor"


def sanitize_for_demo(scores: list[dict]) -> list[dict]:
    """Feature 96: Public demo mode - sanitize sensitive data."""
    sanitized = []
    for s in scores:
        sanitized.append({
            "company_name": s.get("company_name"),
            "domain": s.get("domain"),
            "total_score": s.get("total_score"),
            "tier": s.get("tier"),
            "rule_score": s.get("rule_score"),
            "soft_score": s.get("soft_score"),
            "confidence": s.get("confidence"),
            "industry": s.get("industry_classified") or s.get("industry"),
            "hq_country": s.get("hq_country"),
            "key_signal": s.get("key_signal"),
            # Exclude: reasoning, outreach lines, contact info, emails
        })
    return sanitized


def generate_case_study(lead: dict, signals: dict = None) -> str:
    """Feature 99: A real example lead scored end to end."""
    lines = [
        f"# Case Study: Scoring {lead.get('company_name', 'Unknown')}",
        f"",
        f"## Company Profile",
        f"- **Domain:** {lead.get('domain')}",
        f"- **Industry:** {lead.get('industry_classified') or lead.get('industry') or 'Unknown'}",
        f"- **HQ:** {lead.get('hq_country') or 'Unknown'}",
        f"- **Founded:** {lead.get('founding_year') or 'Unknown'}",
        f"- **Employees:** {lead.get('employee_estimate') or 'Unknown'}",
        f"",
        f"## Enrichment Sources",
        f"Data was gathered from: website scraping, Wikidata API, HTML tech detection, ",
        f"careers page analysis, and local LLM (Ollama) analysis.",
        f"",
        f"## Scoring Result",
        f"- **Total Score:** {lead.get('total_score', 0)}/100",
        f"- **Tier:** {lead.get('tier', 'Cold')}",
        f"- **Rule Score:** {lead.get('rule_score', 0)}/60",
        f"- **LLM Score:** {lead.get('soft_score', 0)}/40",
        f"- **Confidence:** {lead.get('confidence', 'N/A')}",
        f"",
        f"## Rule Breakdown",
    ]

    breakdown = lead.get("rule_breakdown", {})
    if isinstance(breakdown, str):
        try:
            breakdown = json.loads(breakdown)
        except json.JSONDecodeError:
            breakdown = {}
    for signal, pts in breakdown.items():
        lines.append(f"- {signal}: {pts} pts")

    lines.extend([
        f"",
        f"## LLM Reasoning",
        f"{lead.get('reasoning', 'N/A')}",
        f"",
        f"## Key Signal",
        f"{lead.get('key_signal', 'N/A')}",
    ])

    if lead.get("synthesis"):
        lines.extend([f"", f"## Signal Synthesis", f"{lead['synthesis']}"])

    lines.extend([f"", f"---", f"*Generated by AI Lead Scoring Engine on {datetime.now().strftime('%Y-%m-%d')}*"])
    return "\n".join(lines)
