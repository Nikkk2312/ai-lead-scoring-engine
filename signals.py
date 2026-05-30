"""
Features 17, 41-47, 50: Advanced signal detection - job board RSS, funding news,
headcount growth, tech-stack change, news sentiment, website-change monitor,
event/webinar mentions, intent keyword scanning, score-change alerts.
"""
import re
import json
import requests
from datetime import datetime
from config import INTENT_KEYWORDS, LLM_CONFIG
from database import get_company_score_history, get_company


def scan_job_rss(company_name: str, domain: str) -> dict:
    """Feature 17: Pull job postings from free RSS/API sources."""
    result = {"job_count": 0, "source": None, "roles": []}
    # Try a simple web search proxy via DuckDuckGo instant answer
    try:
        search_query = f"{company_name} jobs hiring"
        resp = requests.get(
            "https://api.duckduckgo.com/",
            params={"q": search_query, "format": "json", "no_html": 1},
            timeout=10,
            headers={"User-Agent": "LeadScorer/1.0"},
        )
        data = resp.json()
        abstract = (data.get("AbstractText") or "").lower()
        if "hiring" in abstract or "career" in abstract or "job" in abstract:
            result["job_count"] = 1
            result["source"] = "duckduckgo"
    except Exception:
        pass
    return result


def detect_funding_news(company_name: str, domain: str) -> dict:
    """Feature 41: Detect recent funding/raises as timing signals."""
    result = {"has_funding_signal": False, "detail": None}
    try:
        resp = requests.get(
            "https://api.duckduckgo.com/",
            params={"q": f"{company_name} funding raised series", "format": "json", "no_html": 1},
            timeout=10,
            headers={"User-Agent": "LeadScorer/1.0"},
        )
        data = resp.json()
        text = (data.get("AbstractText") or "") + " " + (data.get("Abstract") or "")
        funding_keywords = ["raised", "funding", "series a", "series b", "series c",
                           "seed round", "million", "valuation", "investment"]
        if any(kw in text.lower() for kw in funding_keywords):
            result["has_funding_signal"] = True
            result["detail"] = text[:300]
    except Exception:
        pass
    return result


def track_headcount_trend(domain: str, current_jobs: int) -> dict:
    """Feature 42: Compare current job count to historical."""
    result = {"trend": "stable", "previous_count": None}
    existing = get_company(domain)
    if existing and existing.get("careers_jobs_count") is not None:
        prev = existing["careers_jobs_count"]
        result["previous_count"] = prev
        if current_jobs > prev + 2:
            result["trend"] = "growing"
        elif current_jobs < prev - 2:
            result["trend"] = "shrinking"
    return result


def detect_tech_changes(domain: str, current_tech: list[str]) -> dict:
    """Feature 43: Flag when a company adopts/drops a relevant tool."""
    result = {"added": [], "removed": [], "changed": False}
    existing = get_company(domain)
    if existing and existing.get("tech_stack"):
        prev_tech = existing["tech_stack"]
        if isinstance(prev_tech, str):
            try:
                prev_tech = json.loads(prev_tech)
            except json.JSONDecodeError:
                prev_tech = []
        prev_set = set(prev_tech)
        curr_set = set(current_tech)
        result["added"] = sorted(curr_set - prev_set)
        result["removed"] = sorted(prev_set - curr_set)
        result["changed"] = bool(result["added"] or result["removed"])
    return result


def analyze_news_sentiment(company_name: str) -> dict:
    """Feature 44: Positive/negative news classification via LLM."""
    result = {"sentiment": "neutral", "summary": None}
    try:
        resp = requests.get(
            "https://api.duckduckgo.com/",
            params={"q": f"{company_name} news recent", "format": "json", "no_html": 1},
            timeout=10,
            headers={"User-Agent": "LeadScorer/1.0"},
        )
        data = resp.json()
        text = data.get("AbstractText") or data.get("Abstract") or ""
        if not text:
            return result

        # Quick LLM sentiment check
        llm_resp = requests.post(
            f"{LLM_CONFIG['base_url']}/api/generate",
            json={
                "model": LLM_CONFIG["model"],
                "prompt": f'Classify the sentiment of this news about {company_name} as "positive", "negative", or "neutral". Respond with ONLY one word.\n\nText: {text[:500]}',
                "stream": False,
                "options": {"temperature": 0.1, "num_predict": 10},
            },
            timeout=60,
        )
        sentiment = llm_resp.json().get("response", "").strip().lower()
        if "positive" in sentiment:
            result["sentiment"] = "positive"
        elif "negative" in sentiment:
            result["sentiment"] = "negative"
        result["summary"] = text[:300]
    except Exception:
        pass
    return result


def detect_website_changes(domain: str, current_hash: str) -> dict:
    """Feature 45: Detect website content changes between runs."""
    result = {"changed": False, "previous_hash": None}
    existing = get_company(domain)
    if existing and existing.get("site_text_hash"):
        result["previous_hash"] = existing["site_text_hash"]
        if existing["site_text_hash"] != current_hash:
            result["changed"] = True
    return result


def scan_events(site_text: str) -> list[str]:
    """Feature 46: Surface conference or webinar activity."""
    if not site_text:
        return []
    patterns = [
        r'\b(webinar|conference|summit|meetup|workshop|event|demo day|hackathon)\b',
        r'\b(aws re:invent|dreamforce|saastr|web summit|google next|microsoft ignite)\b',
    ]
    mentions = []
    text_lower = site_text.lower()
    for pattern in patterns:
        matches = re.findall(pattern, text_lower)
        mentions.extend(matches)
    return sorted(set(mentions))


def scan_intent_keywords(site_text: str) -> list[str]:
    """Feature 47: Scan site for buying-intent language."""
    if not site_text:
        return []
    found = []
    text_lower = site_text.lower()
    for kw in INTENT_KEYWORDS:
        if kw.lower() in text_lower:
            found.append(kw)
    return found


def check_score_changes(domain: str, new_score: int, new_tier: str) -> dict:
    """Feature 50: Notify when a company crosses into Hot."""
    result = {"tier_changed": False, "score_delta": 0, "prev_tier": None, "became_hot": False}
    history = get_company_score_history(domain)
    if history:
        prev = history[0]
        result["prev_tier"] = prev["tier"]
        result["score_delta"] = new_score - prev["total_score"]
        if prev["tier"] != new_tier:
            result["tier_changed"] = True
        if prev["tier"] != "Hot" and new_tier == "Hot":
            result["became_hot"] = True
    return result


def gather_signals(lead: dict) -> dict:
    """Gather all advanced signals for a lead. Called during enrichment."""
    domain = lead.get("domain", "")
    company = lead.get("company_name", "")
    site_text = lead.get("site_text", "")
    current_hash = lead.get("site_text_hash", "")
    tech = lead.get("tech_stack") or []

    signals = {}

    # Feature 17: Job board
    signals["job_rss"] = scan_job_rss(company, domain)

    # Feature 41: Funding
    signals["funding"] = detect_funding_news(company, domain)

    # Feature 42: Headcount trend
    jobs_count = lead.get("careers_jobs_count", 0)
    signals["headcount_trend"] = track_headcount_trend(domain, jobs_count)

    # Feature 43: Tech changes
    signals["tech_changes"] = detect_tech_changes(domain, tech)

    # Feature 45: Website changes
    signals["website_changes"] = detect_website_changes(domain, current_hash)

    # Feature 46: Events
    signals["events"] = scan_events(site_text)

    # Feature 47: Intent keywords
    signals["intent_keywords"] = scan_intent_keywords(site_text)

    return signals
