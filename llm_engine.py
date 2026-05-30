"""
Features 55-59: Advanced LLM operations - Multi-signal synthesis, personalized
outreach lines, recommended next actions, objection/risk flagging, persona targeting.
"""
import re
import json
import requests
from config import LLM_CONFIG


def _call_llm(prompt: str, max_tokens: int = 400) -> str:
    """Shared LLM call helper."""
    try:
        resp = requests.post(
            f"{LLM_CONFIG['base_url']}/api/generate",
            json={
                "model": LLM_CONFIG["model"],
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.4, "num_predict": max_tokens},
            },
            timeout=LLM_CONFIG["timeout"],
        )
        resp.raise_for_status()
        return resp.json().get("response", "")
    except Exception as e:
        return f'{{"error": "{str(e)[:100]}"}}'


def _extract_json(raw: str) -> dict:
    match = re.search(r'\{[^{}]*\}', raw, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    return {}


def multi_signal_synthesis(lead: dict, signals: dict) -> str:
    """Feature 55: LLM weighs several signals into one narrative."""
    prompt = f"""You are a sales intelligence analyst. Synthesize all available signals about this company into a brief narrative (3-4 sentences) for a sales rep.

Company: {lead.get('company_name')}
Domain: {lead.get('domain')}
Industry: {lead.get('industry_classified') or lead.get('industry') or 'Unknown'}
HQ: {lead.get('hq_country') or 'Unknown'}
Founded: {lead.get('founding_year') or 'Unknown'}
Employees: {lead.get('employee_estimate') or 'Unknown'}
Tech Stack: {', '.join(lead.get('tech_stack') or []) or 'None detected'}
Description: {(lead.get('description') or '')[:300]}
Careers Signal: {lead.get('careers_signal') or 'None'}
Competitor Usage: {', '.join(lead.get('competitor_tech') or []) or 'None'}
Funding Signal: {signals.get('funding', {}).get('detail') or 'None'}
Headcount Trend: {signals.get('headcount_trend', {}).get('trend', 'unknown')}
Intent Keywords: {', '.join(signals.get('intent_keywords', [])) or 'None'}
Events: {', '.join(signals.get('events', [])) or 'None'}

Write a concise synthesis paragraph. No JSON needed, just plain text."""

    raw = _call_llm(prompt, 300)
    # Strip any JSON artifacts
    if raw.startswith("{"):
        raw = _extract_json(raw).get("synthesis", raw)
    return raw.strip()[:600]


def generate_outreach_line(lead: dict) -> str:
    """Feature 56: Generate a one-line opener per Hot lead."""
    prompt = f"""Write a single personalized cold outreach opening line for a sales email to {lead.get('company_name')}.

Context:
- They are a {lead.get('industry_classified') or lead.get('industry') or 'technology'} company
- Based in {lead.get('hq_country') or 'unknown location'}
- Key signal: {lead.get('key_signal', 'N/A')}
- Their tech stack includes: {', '.join((lead.get('tech_stack') or [])[:5]) or 'various tools'}

Write ONLY the one-line opener. Be specific, not generic. Do not use "I hope this email finds you well." """

    raw = _call_llm(prompt, 100)
    # Clean up
    line = raw.strip().split("\n")[0].strip('"').strip("'")
    return line[:300]


def recommend_next_action(lead: dict) -> str:
    """Feature 57: LLM suggests the play (demo, nurture, ignore)."""
    prompt = f"""Based on this lead's profile, recommend ONE specific next action for the sales team.

Company: {lead.get('company_name')}
Score: {lead.get('total_score')}/100 (Tier: {lead.get('tier')})
Confidence: {lead.get('confidence', 'N/A')}
Industry: {lead.get('industry_classified') or lead.get('industry') or 'Unknown'}
Key Signal: {lead.get('key_signal', 'N/A')}
Reasoning: {(lead.get('reasoning') or '')[:200]}

Respond with ONLY valid JSON:
{{"action": "<one of: book_demo, send_case_study, nurture_sequence, research_more, disqualify, partner_intro>", "reason": "<one sentence why>", "urgency": "<high/medium/low>"}}"""

    raw = _call_llm(prompt, 150)
    parsed = _extract_json(raw)
    if parsed:
        return json.dumps(parsed)
    return json.dumps({"action": "research_more", "reason": "Insufficient data", "urgency": "low"})


def flag_objections(lead: dict) -> str:
    """Feature 58: Surface likely deal blockers from public info."""
    prompt = f"""Identify potential deal blockers or objections for selling to {lead.get('company_name')}.

Industry: {lead.get('industry_classified') or lead.get('industry') or 'Unknown'}
HQ: {lead.get('hq_country') or 'Unknown'}
Employees: {lead.get('employee_estimate') or 'Unknown'}
Competitor Usage: {', '.join(lead.get('competitor_tech') or []) or 'None detected'}
Description: {(lead.get('description') or '')[:300]}

Respond with ONLY valid JSON:
{{"objections": ["<objection 1>", "<objection 2>"], "risk_level": "<low/medium/high>"}}"""

    raw = _call_llm(prompt, 200)
    parsed = _extract_json(raw)
    if parsed:
        return json.dumps(parsed)
    return json.dumps({"objections": [], "risk_level": "unknown"})


def suggest_persona(lead: dict) -> str:
    """Feature 59: Suggest which job title to approach."""
    prompt = f"""For a B2B sale to {lead.get('company_name')} ({lead.get('industry_classified') or lead.get('industry') or 'tech company'}), which job title should the sales team contact first?

Company size: {lead.get('employee_estimate') or 'Unknown'}
Their tech stack: {', '.join((lead.get('tech_stack') or [])[:5]) or 'Unknown'}

Respond with ONLY valid JSON:
{{"primary_title": "<job title>", "department": "<department>", "secondary_title": "<backup title>", "approach": "<one sentence on how to approach>"}}"""

    raw = _call_llm(prompt, 150)
    parsed = _extract_json(raw)
    if parsed:
        return json.dumps(parsed)
    return json.dumps({"primary_title": "VP of Sales", "department": "Sales", "secondary_title": "Head of Revenue", "approach": "Lead with ROI data"})


def run_advanced_llm(lead: dict, signals: dict = None) -> dict:
    """Run all advanced LLM features for a scored lead."""
    result = {}

    print(f"    [LLM+] Synthesizing signals: {lead['company_name']}")
    result["synthesis"] = multi_signal_synthesis(lead, signals or {})

    # Only generate outreach for Hot/Warm leads
    if lead.get("tier") in ("Hot", "Warm"):
        print(f"    [LLM+] Generating outreach: {lead['company_name']}")
        result["outreach_line"] = generate_outreach_line(lead)

        print(f"    [LLM+] Recommending action: {lead['company_name']}")
        result["next_action"] = recommend_next_action(lead)

        print(f"    [LLM+] Identifying objections: {lead['company_name']}")
        result["objections"] = flag_objections(lead)

        print(f"    [LLM+] Suggesting persona: {lead['company_name']}")
        result["target_persona"] = suggest_persona(lead)
    else:
        result["outreach_line"] = ""
        result["next_action"] = json.dumps({"action": "nurture_sequence", "reason": "Low score", "urgency": "low"})
        result["objections"] = json.dumps({"objections": [], "risk_level": "low"})
        result["target_persona"] = ""

    return result
