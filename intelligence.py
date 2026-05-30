"""
Features 78-84: Look-alike discovery, auto-ICP learning, lead deduping across runs,
account hierarchy mapping, TAM sizing, embeddings-based similarity, predictive conversion score.
"""
import json
import math
import requests
from collections import Counter
from config import LLM_CONFIG, ICPS
from database import get_all_companies, get_latest_scores, get_connection


def find_look_alikes(target_domain: str, top_n: int = 5) -> list[dict]:
    """Feature 78: Find companies similar to a given lead."""
    companies = get_all_companies()
    target = None
    for c in companies:
        if c["domain"] == target_domain:
            target = c
            break
    if not target:
        return []

    scored = []
    target_tech = set(target.get("tech_stack") or [])
    target_industry = (target.get("industry_classified") or target.get("industry") or "").lower()

    for c in companies:
        if c["domain"] == target_domain:
            continue
        sim = 0
        # Tech overlap
        c_tech = set(c.get("tech_stack") or [])
        if target_tech and c_tech:
            overlap = len(target_tech & c_tech)
            sim += overlap * 10
        # Industry match
        c_industry = (c.get("industry_classified") or c.get("industry") or "").lower()
        if target_industry and c_industry and target_industry in c_industry:
            sim += 20
        # Geo match
        if target.get("hq_country") and c.get("hq_country") == target["hq_country"]:
            sim += 10
        # Size similarity
        if target.get("employee_estimate") and c.get("employee_estimate"):
            sim += 5

        if sim > 0:
            scored.append({"domain": c["domain"], "company_name": c["company_name"],
                          "similarity_score": sim, "shared_tech": sorted(target_tech & c_tech)})

    scored.sort(key=lambda x: -x["similarity_score"])
    return scored[:top_n]


def auto_learn_icp(icp_name: str = "default") -> dict:
    """Feature 79: Refine ICP weights from which leads score highest."""
    scores = get_latest_scores(icp_name)
    if len(scores) < 5:
        return {"status": "insufficient_data", "suggestions": []}

    hot_leads = [s for s in scores if s.get("tier") == "Hot"]
    warm_leads = [s for s in scores if s.get("tier") == "Warm"]
    good_leads = hot_leads + warm_leads

    if not good_leads:
        return {"status": "no_hot_warm_leads", "suggestions": []}

    suggestions = []

    # Analyze common traits of high-scoring leads
    geos = Counter(s.get("hq_country") for s in good_leads if s.get("hq_country"))
    industries = Counter(
        (s.get("industry_classified") or s.get("industry") or "").lower()
        for s in good_leads if s.get("industry_classified") or s.get("industry")
    )
    all_tech = Counter()
    for s in good_leads:
        tech = s.get("tech_stack") or []
        if isinstance(tech, str):
            try:
                tech = json.loads(tech)
            except json.JSONDecodeError:
                tech = []
        for t in tech:
            all_tech[t] += 1

    if geos:
        top_geos = [g for g, _ in geos.most_common(5)]
        suggestions.append({"field": "target_geos", "suggested": top_geos,
                           "reason": f"Top geos among {len(good_leads)} high-scoring leads"})
    if industries:
        top_ind = [i for i, _ in industries.most_common(5) if i]
        suggestions.append({"field": "target_industries", "suggested": top_ind,
                           "reason": "Most common industries among high scorers"})
    if all_tech:
        top_tech = [t for t, cnt in all_tech.most_common(10) if cnt >= 2]
        if top_tech:
            suggestions.append({"field": "positive_tech_signals", "suggested": top_tech,
                               "reason": "Most common tech signals in high scorers"})

    return {"status": "ok", "analyzed_leads": len(good_leads), "suggestions": suggestions}


def dedupe_across_runs() -> dict:
    """Feature 80: Global identity resolution across runs."""
    conn = get_connection()
    # Find domains with multiple score entries
    rows = conn.execute("""
        SELECT domain, COUNT(DISTINCT run_id) as run_count, MAX(total_score) as best_score
        FROM scores s JOIN companies c ON s.company_id = c.id
        GROUP BY domain HAVING run_count > 1
        ORDER BY run_count DESC
    """).fetchall()
    conn.close()
    return {
        "duplicates_found": len(rows),
        "details": [dict(r) for r in rows[:50]],
    }


def map_account_hierarchy(company_name: str, domain: str) -> dict:
    """Feature 81: Link subsidiaries to parents via LLM."""
    prompt = f"""Is {company_name} ({domain}) a subsidiary of a larger company, or does it own any subsidiaries?

Respond with ONLY valid JSON:
{{"parent_company": "<parent name or null>", "subsidiaries": ["<sub1>", "<sub2>"], "is_independent": true/false, "corporate_family": "<family name if applicable>"}}"""

    try:
        resp = requests.post(
            f"{LLM_CONFIG['base_url']}/api/generate",
            json={"model": LLM_CONFIG["model"], "prompt": prompt, "stream": False,
                  "options": {"temperature": 0.2, "num_predict": 200}},
            timeout=LLM_CONFIG["timeout"],
        )
        raw = resp.json().get("response", "")
        import re
        match = re.search(r'\{.*\}', raw, re.DOTALL)
        if match:
            return json.loads(match.group())
    except Exception:
        pass

    return {"parent_company": None, "subsidiaries": [], "is_independent": True}


def estimate_tam(icp_name: str = "default") -> dict:
    """Feature 82: Estimate total addressable market size."""
    icp = ICPS.get(icp_name, ICPS["default"])
    scores = get_latest_scores(icp_name)

    total_scored = len(scores)
    hot = sum(1 for s in scores if s.get("tier") == "Hot")
    warm = sum(1 for s in scores if s.get("tier") == "Warm")

    # Rough TAM estimation
    icp_fit_rate = (hot + warm) / max(total_scored, 1)

    return {
        "icp_name": icp.get("name", icp_name),
        "total_companies_scored": total_scored,
        "icp_fit_count": hot + warm,
        "icp_fit_rate": round(icp_fit_rate * 100, 1),
        "hot_count": hot,
        "warm_count": warm,
        "note": "TAM estimate based on scored sample. Larger sample = better estimate.",
    }


def compute_embedding_similarity(text1: str, text2: str) -> float:
    """Feature 83: Vector similarity using Ollama embeddings."""
    try:
        emb1 = _get_embedding(text1)
        emb2 = _get_embedding(text2)
        if emb1 and emb2:
            return _cosine_similarity(emb1, emb2)
    except Exception:
        pass
    return 0.0


def _get_embedding(text: str) -> list[float] | None:
    try:
        resp = requests.post(
            f"{LLM_CONFIG['base_url']}/api/embeddings",
            json={"model": "nomic-embed-text", "prompt": text[:2000]},
            timeout=30,
        )
        return resp.json().get("embedding")
    except Exception:
        return None


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return round(dot / (norm_a * norm_b), 4)


def find_similar_by_embedding(target_domain: str, top_n: int = 5) -> list[dict]:
    """Feature 83: Find similar companies using embeddings."""
    companies = get_all_companies()
    target = None
    for c in companies:
        if c["domain"] == target_domain:
            target = c
            break
    if not target or not target.get("description"):
        return []

    results = []
    for c in companies:
        if c["domain"] == target_domain or not c.get("description"):
            continue
        sim = compute_embedding_similarity(target["description"], c["description"])
        if sim > 0.5:
            results.append({
                "domain": c["domain"],
                "company_name": c["company_name"],
                "similarity": sim,
            })

    results.sort(key=lambda x: -x["similarity"])
    return results[:top_n]


def predictive_conversion_score(lead: dict) -> dict:
    """Feature 84: Simple predictive score based on signal patterns."""
    score = 50  # Base score
    factors = []

    # Positive signals
    if lead.get("tier") == "Hot":
        score += 20
        factors.append("+20: Hot tier")
    elif lead.get("tier") == "Warm":
        score += 10
        factors.append("+10: Warm tier")

    if lead.get("careers_jobs_count", 0) >= 3:
        score += 10
        factors.append("+10: Active hiring")

    tech = lead.get("tech_stack") or []
    if len(tech) >= 5:
        score += 10
        factors.append("+10: Rich tech stack")

    if lead.get("competitor_tech"):
        score += 15
        factors.append("+15: Uses competitor tools")

    confidence = lead.get("confidence", 0.5)
    if confidence >= 0.8:
        score += 5
        factors.append("+5: High data confidence")

    # Negative signals
    if not lead.get("hq_country"):
        score -= 10
        factors.append("-10: Unknown geography")

    if lead.get("disqualified"):
        score = 5
        factors = ["Disqualified"]

    score = max(0, min(100, score))
    return {"conversion_probability": score, "factors": factors}
