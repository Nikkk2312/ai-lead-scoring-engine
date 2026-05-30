"""
Scoring Engine — Tri-dimensional scoring (Fit + Engagement + Intent),
glass-box explainability, feedback loops, buying stages, champion/challenger,
configurable weights, negative scoring, score decay, multiple ICPs.

Features: 1-20 from competitor analysis + original features 10-13, 25-29, 49.
"""
import json
import re
import math
import requests
from datetime import datetime

from config import (
    ICPS, RULE_WEIGHTS, LLM_CONFIG, TIERS, SCORE_DIMENSIONS,
    SCORE_DECAY, NEGATIVE_SCORE_RULES, BUYING_STAGES, SCORING_TEMPLATES,
    TIER_THRESHOLDS,
)


# ---------------------------------------------------------------------------
# Feature 1: Fit Score — firmographic/demographic ICP match
# ---------------------------------------------------------------------------

def compute_fit_score(lead: dict, icp_name: str = "default") -> dict:
    """Score how well a lead matches the ICP on firmographic/demographic dimensions."""
    icp = ICPS.get(icp_name, ICPS["default"])
    breakdown = {}
    factors = []  # Glass-box explainability (Feature 12)

    # Feature 26: Negative/disqualifier rules - check first
    disq = icp.get("disqualifiers", {})
    domain = lead.get("domain", "")
    hq = (lead.get("hq_country") or "").lower()
    industry = (lead.get("industry") or "").lower()

    if domain in disq.get("blocked_domains", []):
        return {"fit_score": 0, "fit_breakdown": {"disqualified": "blocked_domain"},
                "disqualified": True, "fit_factors": [{"factor": "Blocked domain", "impact": -100, "direction": "negative"}]}
    if any(g.lower() in hq for g in disq.get("blocked_geos", []) if hq):
        return {"fit_score": 0, "fit_breakdown": {"disqualified": "blocked_geo"},
                "disqualified": True, "fit_factors": [{"factor": "Blocked geography", "impact": -100, "direction": "negative"}]}
    if any(i.lower() in industry for i in disq.get("blocked_industries", []) if industry):
        return {"fit_score": 0, "fit_breakdown": {"disqualified": "blocked_industry"},
                "disqualified": True, "fit_factors": [{"factor": "Blocked industry", "impact": -100, "direction": "negative"}]}

    # --- Geo match ---
    if hq and any(g.lower() in hq or hq in g.lower() for g in icp["target_geos"]):
        breakdown["geo_match"] = RULE_WEIGHTS["geo_match"]
        factors.append({"factor": f"HQ in target geo ({hq.title()})", "impact": RULE_WEIGHTS["geo_match"], "direction": "positive"})
    elif hq:
        breakdown["geo_match"] = RULE_WEIGHTS["geo_match"] // 3
        factors.append({"factor": f"HQ outside target geos ({hq.title()})", "impact": RULE_WEIGHTS["geo_match"] // 3, "direction": "neutral"})
    else:
        breakdown["geo_match"] = 0
        factors.append({"factor": "No geography data", "impact": 0, "direction": "negative"})

    # --- Industry match ---
    site_text = (lead.get("site_text") or "").lower()
    industry_classified = (lead.get("industry_classified") or "").lower()
    all_industry_text = f"{industry} {industry_classified} {site_text}"
    if any(ind in all_industry_text for ind in icp["target_industries"]):
        breakdown["industry_match"] = RULE_WEIGHTS["industry_match"]
        matched_ind = next((ind for ind in icp["target_industries"] if ind in all_industry_text), "")
        factors.append({"factor": f"Industry match: {matched_ind}", "impact": RULE_WEIGHTS["industry_match"], "direction": "positive"})
    elif any(ind in site_text for ind in icp["target_industries"]):
        breakdown["industry_match"] = RULE_WEIGHTS["industry_match"] * 2 // 3
        factors.append({"factor": "Partial industry match from website", "impact": RULE_WEIGHTS["industry_match"] * 2 // 3, "direction": "neutral"})
    else:
        breakdown["industry_match"] = 0
        factors.append({"factor": "No industry match", "impact": 0, "direction": "negative"})

    # --- Tech signals ---
    tech = lead.get("tech_stack") or []
    positive_hits = []
    for t in tech:
        for sig in icp["positive_tech_signals"]:
            if sig.lower() in t.lower():
                positive_hits.append(t)
                break
    breakdown["tech_signals"] = min(len(positive_hits) * 4, RULE_WEIGHTS["tech_signals"])
    if positive_hits:
        factors.append({"factor": f"Tech stack matches: {', '.join(positive_hits[:3])}", "impact": breakdown["tech_signals"], "direction": "positive"})
    else:
        factors.append({"factor": "No matching tech signals", "impact": 0, "direction": "negative"})

    # --- Company age ---
    founding = lead.get("founding_year")
    if founding:
        age = datetime.now().year - founding
        if icp["ideal_age_min"] <= age <= icp["ideal_age_max"]:
            breakdown["company_age"] = RULE_WEIGHTS["company_age"]
            factors.append({"factor": f"Company age {age}y (ideal range)", "impact": RULE_WEIGHTS["company_age"], "direction": "positive"})
        elif age > 0:
            breakdown["company_age"] = RULE_WEIGHTS["company_age"] // 2
            factors.append({"factor": f"Company age {age}y (outside ideal)", "impact": RULE_WEIGHTS["company_age"] // 2, "direction": "neutral"})
        else:
            breakdown["company_age"] = 0
    else:
        breakdown["company_age"] = 0
        factors.append({"factor": "No founding year data", "impact": 0, "direction": "negative"})

    # --- Employee fit ---
    emp_str = lead.get("employee_estimate") or ""
    tech_count = len(tech)
    emp_score = 0
    emp_match = re.search(r'(\d+)', emp_str.replace(",", ""))
    if emp_match:
        emp_low = int(emp_match.group(1))
        if icp["ideal_employee_min"] <= emp_low <= icp["ideal_employee_max"]:
            emp_score = RULE_WEIGHTS["employee_fit"]
            factors.append({"factor": f"Employee count {emp_str} (ideal range)", "impact": emp_score, "direction": "positive"})
        elif emp_low > 0:
            emp_score = RULE_WEIGHTS["employee_fit"] // 2
            factors.append({"factor": f"Employee count {emp_str} (outside ideal)", "impact": emp_score, "direction": "neutral"})
    elif tech_count >= 5:
        emp_score = RULE_WEIGHTS["employee_fit"]
        factors.append({"factor": "Large tech stack suggests good size", "impact": emp_score, "direction": "positive"})
    elif tech_count >= 2:
        emp_score = RULE_WEIGHTS["employee_fit"] * 2 // 3
    else:
        emp_score = RULE_WEIGHTS["employee_fit"] // 3
    breakdown["employee_fit"] = emp_score

    # --- Website quality ---
    site_text_len = len(lead.get("site_text") or "")
    if lead.get("website_status") == 200 and site_text_len > 500:
        breakdown["website_quality"] = RULE_WEIGHTS["website_quality"]
        factors.append({"factor": "Website live with rich content", "impact": RULE_WEIGHTS["website_quality"], "direction": "positive"})
    elif lead.get("website_status") == 200:
        breakdown["website_quality"] = RULE_WEIGHTS["website_quality"] // 2
        factors.append({"factor": "Website live but thin content", "impact": RULE_WEIGHTS["website_quality"] // 2, "direction": "neutral"})
    else:
        breakdown["website_quality"] = 0
        factors.append({"factor": "Website not accessible", "impact": 0, "direction": "negative"})

    total = sum(breakdown.values())

    # Normalize to 0-100 scale (fit dimension)
    fit_pct = round(total / 60 * 100)

    return {
        "fit_score": total,
        "fit_score_pct": fit_pct,
        "fit_breakdown": breakdown,
        "disqualified": False,
        "fit_factors": sorted(factors, key=lambda f: -abs(f["impact"])),
        # Legacy compatibility
        "rule_score": total,
        "rule_breakdown": breakdown,
    }


# ---------------------------------------------------------------------------
# Feature 2: Engagement Score — behavioral signals
# ---------------------------------------------------------------------------

def compute_engagement_score(lead: dict) -> dict:
    """Score based on behavioral/engagement signals."""
    score = 0
    factors = []

    # Careers/hiring signal (proxy for engagement in our enrichment-based model)
    jobs = lead.get("careers_jobs_count") or 0
    if jobs > 100:
        score += 15
        factors.append({"factor": f"Active hiring: {jobs} open positions", "impact": 15, "direction": "positive"})
    elif jobs > 30:
        score += 10
        factors.append({"factor": f"Moderate hiring: {jobs} open positions", "impact": 10, "direction": "positive"})
    elif jobs > 0:
        score += 5
        factors.append({"factor": f"Some hiring: {jobs} positions", "impact": 5, "direction": "neutral"})
    else:
        factors.append({"factor": "No hiring signal detected", "impact": 0, "direction": "negative"})

    # Website engagement signals
    site_text = lead.get("site_text") or ""
    if len(site_text) > 2000:
        score += 5
        factors.append({"factor": "Rich website content (engagement-ready)", "impact": 5, "direction": "positive"})

    # Social presence
    if lead.get("social_linkedin"):
        score += 5
        factors.append({"factor": "LinkedIn presence confirmed", "impact": 5, "direction": "positive"})
    if lead.get("social_twitter"):
        score += 3
        factors.append({"factor": "Twitter/X presence confirmed", "impact": 3, "direction": "positive"})

    # Competitor tool usage (shows they're in-market for solutions)
    comp_tech = lead.get("competitor_tech") or []
    if comp_tech:
        bonus = min(len(comp_tech) * 4, 12)
        score += bonus
        factors.append({"factor": f"Using competitor tools: {', '.join(comp_tech[:3])}", "impact": bonus, "direction": "positive"})

    # Cap at 40
    score = min(score, 40)
    engagement_pct = round(score / 40 * 100)

    return {
        "engagement_score": score,
        "engagement_score_pct": engagement_pct,
        "engagement_factors": sorted(factors, key=lambda f: -abs(f["impact"])),
    }


# ---------------------------------------------------------------------------
# Feature 2: Intent Score — buying intent signals
# ---------------------------------------------------------------------------

def compute_intent_score(lead: dict) -> dict:
    """Score based on intent signals (keywords, events, funding, tech changes)."""
    score = 0
    factors = []

    # Intent keywords found on website
    intent_signals = lead.get("intent_signals") or []
    if isinstance(intent_signals, str):
        try:
            intent_signals = json.loads(intent_signals)
        except (json.JSONDecodeError, TypeError):
            intent_signals = []
    if intent_signals:
        bonus = min(len(intent_signals) * 5, 15)
        score += bonus
        factors.append({"factor": f"Intent keywords: {', '.join(intent_signals[:3])}", "impact": bonus, "direction": "positive"})

    # Event mentions
    events = lead.get("event_mentions") or []
    if isinstance(events, str):
        try:
            events = json.loads(events)
        except (json.JSONDecodeError, TypeError):
            events = []
    if events:
        bonus = min(len(events) * 3, 10)
        score += bonus
        factors.append({"factor": f"Event activity: {', '.join(events[:3])}", "impact": bonus, "direction": "positive"})

    # Careers signal as intent proxy
    careers_signal = lead.get("careers_signal") or ""
    if "growing" in careers_signal.lower() or "hiring" in careers_signal.lower():
        score += 5
        factors.append({"factor": "Growth hiring signal detected", "impact": 5, "direction": "positive"})

    # Technology sophistication as intent signal
    tech = lead.get("tech_stack") or []
    if isinstance(tech, str):
        try:
            tech = json.loads(tech)
        except (json.JSONDecodeError, TypeError):
            tech = []
    if len(tech) >= 6:
        score += 5
        factors.append({"factor": f"High tech sophistication ({len(tech)} tools)", "impact": 5, "direction": "positive"})

    # Description-based intent signals
    desc = (lead.get("description") or "").lower()
    intent_phrases = ["enterprise", "scale", "growth", "expansion", "series", "platform"]
    matched_phrases = [p for p in intent_phrases if p in desc]
    if matched_phrases:
        bonus = min(len(matched_phrases) * 3, 10)
        score += bonus
        factors.append({"factor": f"Intent language: {', '.join(matched_phrases[:3])}", "impact": bonus, "direction": "positive"})

    if not factors:
        factors.append({"factor": "No intent signals detected", "impact": 0, "direction": "negative"})

    # Cap at 30
    score = min(score, 30)
    intent_pct = round(score / 30 * 100)

    return {
        "intent_score": score,
        "intent_score_pct": intent_pct,
        "intent_factors": sorted(factors, key=lambda f: -abs(f["impact"])),
    }


# ---------------------------------------------------------------------------
# Feature 27: Confidence score
# ---------------------------------------------------------------------------

def compute_confidence(lead: dict) -> float:
    """Rate confidence 0.0-1.0 based on data completeness."""
    checks = [
        bool(lead.get("website_status") == 200),
        bool(lead.get("site_text")),
        bool(lead.get("founding_year")),
        bool(lead.get("hq_country")),
        bool(lead.get("industry") or lead.get("industry_classified")),
        bool(lead.get("tech_stack")),
        bool(lead.get("employee_estimate")),
        bool(lead.get("description")),
    ]
    confidence = sum(checks) / len(checks)

    # Feature 49/5: Score-freshness decay
    enriched_at = lead.get("enriched_at")
    if enriched_at and SCORE_DECAY["enabled"]:
        try:
            age_days = (datetime.now() - datetime.fromisoformat(enriched_at)).days
            interval = SCORE_DECAY["interval_days"]
            if age_days > interval:
                periods = (age_days - interval) / interval
                if SCORE_DECAY["mode"] == "exponential":
                    decay_factor = (1 - SCORE_DECAY["rate"]) ** periods
                else:  # linear
                    decay_factor = max(0.5, 1.0 - SCORE_DECAY["rate"] * periods)
                confidence *= decay_factor
        except (ValueError, TypeError):
            pass

    return round(confidence, 2)


# ---------------------------------------------------------------------------
# Feature 11: Local LLM soft scorer (/40)
# ---------------------------------------------------------------------------

LLM_PROMPT = """You are a B2B lead scoring assistant. Score how well this company fits as a potential customer.

Company: {company_name}
Domain: {domain}
Industry: {industry}
HQ Country: {hq_country}
Founded: {founding_year}
Tech Stack: {tech_stack}
Employee Estimate: {employee_estimate}
Careers Signal: {careers_signal}
Competitor Usage: {competitor_tech}
Website Summary: {site_text}

ICP: {icp_name} - targeting {target_geos} in {target_industries}.

Respond ONLY with valid JSON:
{{"soft_score": <integer 0-{max_score}>, "reasoning": "<2-3 sentence explanation>", "key_signal": "<single most important signal>"}}"""


def llm_score(lead: dict, icp_name: str = "default") -> dict:
    """Feature 11: Call Ollama for a soft score with reasoning."""
    icp = ICPS.get(icp_name, ICPS["default"])
    prompt = LLM_PROMPT.format(
        max_score=LLM_CONFIG["max_score"],
        company_name=lead.get("company_name", "Unknown"),
        domain=lead.get("domain", ""),
        industry=lead.get("industry_classified") or lead.get("industry") or "Unknown",
        hq_country=lead.get("hq_country") or "Unknown",
        founding_year=lead.get("founding_year") or "Unknown",
        tech_stack=", ".join(lead.get("tech_stack") or []) or "None detected",
        employee_estimate=lead.get("employee_estimate") or "Unknown",
        careers_signal=lead.get("careers_signal") or "None",
        competitor_tech=", ".join(lead.get("competitor_tech") or []) or "None",
        site_text=(lead.get("site_text") or "")[:1500],
        icp_name=icp.get("name", icp_name),
        target_geos=", ".join(icp["target_geos"][:3]),
        target_industries=", ".join(icp["target_industries"][:5]),
    )

    try:
        resp = requests.post(
            f"{LLM_CONFIG['base_url']}/api/generate",
            json={"model": LLM_CONFIG["model"], "prompt": prompt, "stream": False,
                  "options": {"temperature": 0.3, "num_predict": 300}},
            timeout=LLM_CONFIG["timeout"],
        )
        resp.raise_for_status()
        return parse_llm_response(resp.json().get("response", ""))
    except requests.RequestException as e:
        print(f"    [LLM] Request failed: {e}")
        return {"soft_score": 0, "reasoning": "LLM unavailable", "key_signal": "N/A"}


# ---------------------------------------------------------------------------
# Feature 12: JSON parse + validate
# ---------------------------------------------------------------------------

def parse_llm_response(raw: str) -> dict:
    default = {"soft_score": 0, "reasoning": "Parse failed", "key_signal": "N/A"}
    json_match = re.search(r'\{[^{}]*\}', raw, re.DOTALL)
    if not json_match:
        return default
    try:
        parsed = json.loads(json_match.group())
    except json.JSONDecodeError:
        return default
    score = parsed.get("soft_score", 0)
    try:
        score = int(score)
    except (ValueError, TypeError):
        score = 0
    score = max(0, min(score, LLM_CONFIG["max_score"]))
    return {
        "soft_score": score,
        "reasoning": str(parsed.get("reasoning", ""))[:500],
        "key_signal": str(parsed.get("key_signal", "N/A"))[:200],
    }


# ---------------------------------------------------------------------------
# Feature 88: Buying stage classification
# ---------------------------------------------------------------------------

def classify_buying_stage(total_score: int) -> dict:
    """Classify lead into buying stage based on score (6sense-inspired 5-stage model)."""
    for stage_name, config in BUYING_STAGES.items():
        if config["min_score"] <= total_score <= config["max_score"]:
            return {
                "buying_stage": stage_name,
                "stage_description": config["description"],
            }
    return {"buying_stage": "Target", "stage_description": "Not in-market"}


# ---------------------------------------------------------------------------
# Feature 6: Negative scoring
# ---------------------------------------------------------------------------

def apply_negative_scoring(lead: dict, base_score: int) -> tuple[int, list]:
    """Apply negative scoring rules. Returns adjusted score and negative factors."""
    adjustments = 0
    factors = []

    # Check for competitor email domain
    email = lead.get("email_pattern") or ""
    for bad_domain in NEGATIVE_SCORE_RULES.get("competitor_email_domains", []):
        if bad_domain in email:
            adjustments += NEGATIVE_SCORE_RULES.get("competitor_domain", -20)
            factors.append({"factor": f"Free email domain ({bad_domain})", "impact": -20, "direction": "negative"})
            break

    return base_score + adjustments, factors


# ---------------------------------------------------------------------------
# Feature 13: Combine + tier (tri-dimensional)
# ---------------------------------------------------------------------------

def combine_and_tier(fit_result: dict, engagement_result: dict, intent_result: dict,
                     llm_result: dict, confidence: float,
                     weights: dict = None) -> dict:
    """Combine all score dimensions into final score with tier and buying stage."""

    # Use provided weights or defaults
    w = weights or SCORE_DIMENSIONS

    # Raw scores
    fit_raw = fit_result["fit_score"]  # /60
    engagement_raw = engagement_result["engagement_score"]  # /40
    intent_raw = intent_result["intent_score"]  # /30
    llm_raw = llm_result["soft_score"]  # /40

    # Normalize each to 0-100
    fit_pct = fit_raw / 60 * 100
    engagement_pct = engagement_raw / 40 * 100
    intent_pct = intent_raw / 30 * 100

    # Weighted composite (0-100)
    composite = (
        fit_pct * w["fit_weight"] +
        engagement_pct * w["engagement_weight"] +
        intent_pct * w["intent_weight"]
    )

    # Blend with LLM score (LLM is 0-40, so scale to 0-100)
    llm_pct = llm_raw / 40 * 100
    # Final: 70% weighted composite + 30% LLM judgment
    total = int(composite * 0.7 + llm_pct * 0.3)
    total = max(0, min(total, 100))

    # Feature 26: Hard disqualification override
    if fit_result.get("disqualified"):
        total = 0

    # Determine tier
    tier = "Cold"
    for tier_name, (low, high) in TIERS.items():
        if low <= total <= high:
            tier = tier_name
            break

    # Feature 88: Buying stage
    buying = classify_buying_stage(total)

    # Feature 12: Glass-box explainability — merge all factors
    all_factors = []
    all_factors.extend(fit_result.get("fit_factors", []))
    all_factors.extend(engagement_result.get("engagement_factors", []))
    all_factors.extend(intent_result.get("intent_factors", []))
    # Sort by impact
    top_positive = [f for f in all_factors if f["direction"] == "positive"]
    top_positive.sort(key=lambda f: -f["impact"])
    top_negative = [f for f in all_factors if f["direction"] == "negative"]

    # Fit grade (A/B/C) and Engagement grade (1/2/3) for matrix (Feature 36)
    fit_grade = "A" if fit_pct >= 66 else "B" if fit_pct >= 33 else "C"
    eng_grade = "1" if engagement_pct >= 66 else "2" if engagement_pct >= 33 else "3"
    matrix_cell = f"{fit_grade}{eng_grade}"

    return {
        "total_score": total,
        "tier": tier,
        # Tri-dimensional scores
        "fit_score": fit_raw,
        "fit_score_pct": round(fit_pct),
        "engagement_score": engagement_raw,
        "engagement_score_pct": round(engagement_pct),
        "intent_score": intent_raw,
        "intent_score_pct": round(intent_pct),
        # Legacy compatibility
        "rule_score": fit_raw,
        "rule_breakdown": fit_result.get("fit_breakdown", {}),
        "soft_score": llm_raw,
        "reasoning": llm_result["reasoning"],
        "key_signal": llm_result["key_signal"],
        "confidence": confidence,
        "disqualified": fit_result.get("disqualified", False),
        # Buying stage
        "buying_stage": buying["buying_stage"],
        "stage_description": buying["stage_description"],
        # Matrix cell (Feature 36)
        "fit_grade": fit_grade,
        "engagement_grade": eng_grade,
        "matrix_cell": matrix_cell,
        # Glass-box explainability (Feature 12/13)
        "top_positive_factors": top_positive[:5],
        "top_negative_factors": top_negative[:5],
        "all_factors": all_factors,
        # Score dimension weights used
        "weights_used": w,
    }


# ---------------------------------------------------------------------------
# Feature 25: Score against multiple ICPs
# ---------------------------------------------------------------------------

def score_lead(lead: dict, icp_name: str = "default", weights: dict = None) -> dict:
    """Full scoring pipeline for one lead against one ICP."""
    print(f"  [SCORE] Fit scoring: {lead['company_name']} (ICP: {icp_name})")
    fit_result = compute_fit_score(lead, icp_name)

    print(f"  [SCORE] Engagement scoring: {lead['company_name']}")
    engagement_result = compute_engagement_score(lead)

    print(f"  [SCORE] Intent scoring: {lead['company_name']}")
    intent_result = compute_intent_score(lead)

    print(f"  [SCORE] LLM scoring: {lead['company_name']}")
    llm_result = llm_score(lead, icp_name)

    confidence = compute_confidence(lead)
    combined = combine_and_tier(fit_result, engagement_result, intent_result,
                                 llm_result, confidence, weights)
    combined["icp_name"] = icp_name
    return {**lead, **combined}


def score_lead_multi_icp(lead: dict, icp_names: list[str] = None) -> list[dict]:
    """Feature 25: Score against multiple ICPs."""
    if not icp_names:
        icp_names = list(ICPS.keys())
    return [score_lead(lead, name) for name in icp_names]


# ---------------------------------------------------------------------------
# Feature 15: Champion/Challenger scoring
# ---------------------------------------------------------------------------

def champion_challenger_score(lead: dict, icp_name: str = "default",
                               champion_weights: dict = None,
                               challenger_weights: dict = None) -> dict:
    """Score a lead with both champion and challenger models for A/B comparison."""
    champion = score_lead(lead, icp_name, champion_weights or SCORE_DIMENSIONS)

    # Challenger uses different weights
    default_challenger = SCORING_TEMPLATES.get("outbound_sdr", {
        "fit_weight": 0.50, "engagement_weight": 0.30, "intent_weight": 0.20
    })
    challenger = score_lead(lead, icp_name, challenger_weights or default_challenger)

    return {
        "champion": {
            "total_score": champion["total_score"],
            "tier": champion["tier"],
            "weights": champion.get("weights_used", {}),
        },
        "challenger": {
            "total_score": challenger["total_score"],
            "tier": challenger["tier"],
            "weights": challenger.get("weights_used", {}),
        },
        "score_delta": challenger["total_score"] - champion["total_score"],
        "tier_changed": champion["tier"] != challenger["tier"],
    }


# ---------------------------------------------------------------------------
# Feature 17: Feedback loop
# ---------------------------------------------------------------------------

def apply_feedback(score_data: dict, feedback: str, feedback_score: int = None) -> dict:
    """Apply sales rep feedback to adjust scoring. Returns adjusted score data."""
    adjustment = 0
    if feedback == "accept":
        adjustment = 5  # Positive reinforcement
    elif feedback == "reject":
        adjustment = -10  # Strong negative signal
    elif feedback == "too_high":
        adjustment = -5
    elif feedback == "too_low":
        adjustment = 5

    if feedback_score is not None:
        # Direct score override from rep
        score_data["total_score"] = max(0, min(100, feedback_score))
    else:
        score_data["total_score"] = max(0, min(100, score_data["total_score"] + adjustment))

    # Reclassify tier
    for tier_name, (low, high) in TIERS.items():
        if low <= score_data["total_score"] <= high:
            score_data["tier"] = tier_name
            break

    score_data["feedback_applied"] = feedback
    score_data["buying_stage"] = classify_buying_stage(score_data["total_score"])["buying_stage"]
    return score_data
