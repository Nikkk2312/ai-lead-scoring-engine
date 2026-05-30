"""
Features 5-9, 16-23, 36-38, 43, 45, 52, 60: Full enrichment pipeline with
website fetch, text extract, Wikidata, tech detection, careers scraping,
social discovery, favicon, email pattern, LLM description/industry/employee,
rate limiting, retry, caching, tech change detection, website change monitor,
incremental enrichment, competitor detection.
"""
import re
import json
import time
import hashlib
import requests
from bs4 import BeautifulSoup
from config import RATE_LIMIT, COMPETITORS, LLM_CONFIG
from database import cache_get, cache_set, cache_key_for, get_company


TECH_PATTERNS = {
    "Google Analytics": [r"google-analytics\.com", r"gtag\(", r"ga\("],
    "Google Tag Manager": [r"googletagmanager\.com", r"gtm\.js"],
    "HubSpot": [r"hubspot\.com", r"hs-scripts\.com", r"hbspt\."],
    "Segment": [r"segment\.com/analytics", r"analytics\.js"],
    "Intercom": [r"intercom\.io", r"widget\.intercom"],
    "Drift": [r"drift\.com", r"js\.driftt\.com"],
    "Mixpanel": [r"mixpanel\.com"],
    "Amplitude": [r"amplitude\.com", r"cdn\.amplitude"],
    "Hotjar": [r"hotjar\.com", r"static\.hotjar"],
    "Salesforce": [r"salesforce\.com", r"pardot\.com", r"force\.com"],
    "Marketo": [r"marketo\.com", r"munchkin\.marketo"],
    "WordPress": [r"wp-content", r"wp-includes"],
    "Shopify": [r"cdn\.shopify", r"shopify\.com"],
    "React/Next.js": [r"__NEXT_DATA__", r"_next/static"],
    "Cloudflare": [r"cloudflare", r"cf-ray"],
    "Stripe": [r"js\.stripe\.com", r"stripe\.js"],
    "Zendesk": [r"zendesk\.com", r"zdassets\.com"],
    "Clearbit": [r"clearbit\.com", r"clearbit\.js"],
    "6sense": [r"6sense\.com", r"6sc\.co"],
    "Gong": [r"gong\.io"],
    "Outreach": [r"outreach\.io"],
    "ZoomInfo": [r"zoominfo\.com"],
    "Heap": [r"heap\.io", r"heapanalytics"],
    "FullStory": [r"fullstory\.com"],
    "Pendo": [r"pendo\.io"],
    "LaunchDarkly": [r"launchdarkly\.com"],
    "Datadog": [r"datadoghq\.com", r"datadog"],
    "Sentry": [r"sentry\.io", r"sentry-cdn"],
}

REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

_last_request_time = 0


def _rate_limit():
    """Feature 36: Polite delay between requests."""
    global _last_request_time
    elapsed = time.time() - _last_request_time
    min_interval = 1.0 / RATE_LIMIT["requests_per_second"]
    if elapsed < min_interval:
        time.sleep(min_interval - elapsed)
    _last_request_time = time.time()


def _fetch_with_retry(url: str, max_retries: int = 2, timeout: int = 15) -> requests.Response | None:
    """Feature 37: Retry on transient failure."""
    for attempt in range(max_retries + 1):
        _rate_limit()
        try:
            resp = requests.get(url, headers=REQUEST_HEADERS, timeout=timeout, allow_redirects=True)
            if resp.status_code < 500:
                return resp
        except requests.RequestException:
            if attempt == max_retries:
                return None
        time.sleep(1 * (attempt + 1))
    return None


def fetch_website(domain: str) -> dict:
    """Feature 5: Pull the company homepage HTML with caching."""
    # Feature 38: Check cache
    ck = cache_key_for("website", domain)
    cached = cache_get(ck)
    if cached:
        data = json.loads(cached)
        data["from_cache"] = True
        return data

    result = {"html": None, "status": None, "error": None, "from_cache": False}
    url = f"https://{domain}"
    resp = _fetch_with_retry(url)
    if resp:
        result["status"] = resp.status_code
        if resp.status_code == 200:
            result["html"] = resp.text
        else:
            result["error"] = f"HTTP {resp.status_code}"
    else:
        result["error"] = "Request failed after retries"

    # Cache (without HTML to save space, store a flag)
    cache_data = {**result}
    if cache_data.get("html") and len(cache_data["html"]) > 100000:
        cache_data["html"] = cache_data["html"][:100000]
    cache_set(ck, json.dumps(cache_data))
    return result


def extract_text(html: str, max_chars: int = 3000) -> str:
    """Feature 6: Strip text from the site for LLM to read positioning & product focus."""
    if not html:
        return ""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header", "noscript", "svg", "iframe"]):
        tag.decompose()
    text = soup.get_text(separator=" ", strip=True)
    text = re.sub(r'\s+', ' ', text)
    return text[:max_chars]


def get_wikidata(company_name: str) -> dict:
    """Feature 7: Pull founding year, HQ country, industry from Wikidata API."""
    result = {"founding_year": None, "hq_country": None, "industry": None}

    ck = cache_key_for("wikidata", company_name)
    cached = cache_get(ck)
    if cached:
        return json.loads(cached)

    wiki_headers = {"User-Agent": "LeadScorer/1.0 (lead-scoring project)"}
    search_terms = [
        company_name,
        f"{company_name}, Inc.",
        f"{company_name} (company)",
        f"{company_name} software",
    ]

    try:
        search_url = "https://www.wikidata.org/w/api.php"
        candidates = []

        for term in search_terms:
            _rate_limit()
            params = {
                "action": "wbsearchentities", "search": term,
                "language": "en", "format": "json", "limit": 3, "type": "item",
            }
            resp = requests.get(search_url, params=params, timeout=10, headers=wiki_headers)
            data = resp.json()
            for item in data.get("search", []):
                desc = (item.get("description") or "").lower()
                if any(kw in desc for kw in ["company", "software", "platform", "corporation", "technology", "startup"]):
                    candidates.insert(0, item)
                else:
                    candidates.append(item)
            if candidates:
                break

        seen_ids = set()
        unique = []
        for c in candidates:
            if c["id"] not in seen_ids:
                seen_ids.add(c["id"])
                unique.append(c)

        for candidate in unique[:3]:
            entity_id = candidate["id"]
            _rate_limit()
            entity_url = f"https://www.wikidata.org/wiki/Special:EntityData/{entity_id}.json"
            eresp = requests.get(entity_url, timeout=10, headers=wiki_headers)
            entity = eresp.json().get("entities", {}).get(entity_id, {})
            claims = entity.get("claims", {})

            if "P571" in claims:
                try:
                    time_val = claims["P571"][0]["mainsnak"]["datavalue"]["value"]["time"]
                    result["founding_year"] = int(time_val[1:5])
                except (KeyError, ValueError, IndexError):
                    pass
            if "P17" in claims:
                try:
                    country_id = claims["P17"][0]["mainsnak"]["datavalue"]["value"]["id"]
                    result["hq_country"] = _resolve_wikidata_label(country_id)
                except (KeyError, IndexError):
                    pass
            if "P452" in claims:
                try:
                    industry_id = claims["P452"][0]["mainsnak"]["datavalue"]["value"]["id"]
                    result["industry"] = _resolve_wikidata_label(industry_id)
                except (KeyError, IndexError):
                    pass
            if any(v is not None for v in result.values()):
                break

    except requests.RequestException:
        pass

    cache_set(ck, json.dumps(result))
    return result


def _resolve_wikidata_label(entity_id: str) -> str | None:
    try:
        _rate_limit()
        url = f"https://www.wikidata.org/wiki/Special:EntityData/{entity_id}.json"
        resp = requests.get(url, timeout=8, headers={"User-Agent": "LeadScorer/1.0"})
        entity = resp.json().get("entities", {}).get(entity_id, {})
        return entity.get("labels", {}).get("en", {}).get("value")
    except Exception:
        return None


def detect_tech(html: str) -> list[str]:
    """Feature 8: Regex-match site HTML for common tech tags."""
    if not html:
        return []
    detected = []
    html_lower = html.lower()
    for tech_name, patterns in TECH_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, html_lower):
                detected.append(tech_name)
                break
    return sorted(set(detected))


def scrape_careers(domain: str) -> dict:
    """Feature 16: Detect hiring intent from careers page."""
    result = {"jobs_count": 0, "signal": "none", "roles": []}
    for path in ["/careers", "/jobs", "/about/careers", "/company/careers"]:
        url = f"https://{domain}{path}"
        resp = _fetch_with_retry(url, max_retries=1, timeout=10)
        if resp and resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            text = soup.get_text(" ", strip=True).lower()
            # Count job-like headings
            job_patterns = re.findall(r'(engineer|developer|designer|manager|analyst|sales|marketing|product|data|ops)\b', text)
            result["jobs_count"] = len(set(job_patterns))
            result["roles"] = list(set(job_patterns))[:10]
            if result["jobs_count"] >= 5:
                result["signal"] = "high_hiring"
            elif result["jobs_count"] >= 2:
                result["signal"] = "moderate_hiring"
            elif result["jobs_count"] >= 1:
                result["signal"] = "some_hiring"
            break
    return result


def discover_social(html: str) -> dict:
    """Feature 18: Find LinkedIn/X handles from site HTML."""
    result = {"linkedin": None, "twitter": None}
    if not html:
        return result
    # LinkedIn
    li_match = re.search(r'https?://(?:www\.)?linkedin\.com/company/([a-zA-Z0-9_-]+)', html)
    if li_match:
        result["linkedin"] = f"https://linkedin.com/company/{li_match.group(1)}"
    # Twitter/X
    tw_match = re.search(r'https?://(?:www\.)?(?:twitter|x)\.com/([a-zA-Z0-9_]+)', html)
    if tw_match and tw_match.group(1).lower() not in ("share", "intent", "home"):
        result["twitter"] = f"https://x.com/{tw_match.group(1)}"
    return result


def get_favicon(domain: str, html: str) -> str | None:
    """Feature 19: Extract favicon URL."""
    if html:
        soup = BeautifulSoup(html, "html.parser")
        icon = soup.find("link", rel=lambda x: x and "icon" in " ".join(x).lower())
        if icon and icon.get("href"):
            href = icon["href"]
            if href.startswith("//"):
                return f"https:{href}"
            if href.startswith("/"):
                return f"https://{domain}{href}"
            if href.startswith("http"):
                return href
    return f"https://{domain}/favicon.ico"


def guess_email_pattern(domain: str) -> str:
    """Feature 20: Infer likely email format."""
    return f"first.last@{domain}"


def detect_competitors(html: str, tech_stack: list[str]) -> list[str]:
    """Feature 60: Flag if they use a competitor's product."""
    detected = []
    if not html:
        return detected
    html_lower = html.lower()
    for comp in COMPETITORS:
        if comp.lower() in [t.lower() for t in tech_stack]:
            detected.append(comp)
        elif re.search(r'\b' + re.escape(comp) + r'\b', html_lower):
            detected.append(comp)
    return sorted(set(detected))


def compute_site_hash(text: str) -> str:
    """Feature 45: Hash for website change detection."""
    return hashlib.md5(text.encode()).hexdigest() if text else ""


def llm_describe_and_classify(company_name: str, domain: str, site_text: str) -> dict:
    """Features 21, 22, 23: LLM-powered description, industry classification, employee estimate."""
    result = {"description": None, "industry_classified": None, "employee_estimate": None}
    if not site_text:
        return result

    prompt = f"""Analyze this company based on their website text. Respond ONLY with valid JSON.

Company: {company_name}
Domain: {domain}
Website text (excerpt): {site_text[:2000]}

Return JSON:
{{"description": "<one paragraph summary of what the company does>", "industry": "<specific industry vertical, e.g. 'B2B SaaS - Project Management'>", "employee_estimate": "<estimated range like '50-200' or '1000-5000' based on product complexity and market signals>"}}"""

    try:
        resp = requests.post(
            f"{LLM_CONFIG['base_url']}/api/generate",
            json={"model": LLM_CONFIG["model"], "prompt": prompt, "stream": False,
                  "options": {"temperature": 0.2, "num_predict": 400}},
            timeout=LLM_CONFIG["timeout"],
        )
        raw = resp.json().get("response", "")
        json_match = re.search(r'\{[^{}]*\}', raw, re.DOTALL)
        if json_match:
            parsed = json.loads(json_match.group())
            result["description"] = str(parsed.get("description", ""))[:500]
            result["industry_classified"] = str(parsed.get("industry", ""))[:100]
            result["employee_estimate"] = str(parsed.get("employee_estimate", ""))[:50]
    except Exception:
        pass
    return result


def enrich_lead(lead: dict, incremental: bool = False) -> dict:
    """
    Feature 9, 52: Full enrichment with graceful missing-data handling.
    If incremental=True (Feature 52), skip fields that already exist.
    """
    domain = lead["domain"]
    company = lead["company_name"]
    enriched = {**lead}
    sources = {}

    # Feature 52: Check existing data for incremental enrichment
    existing = get_company(domain) if incremental else None
    if existing and existing.get("enriched_at"):
        enriched.update({k: v for k, v in existing.items() if v is not None and k != "id"})
        print(f"  [ENRICH] Using cached data for {domain} (incremental)")
        return enriched

    # Feature 5-6: Website fetch + text extract
    print(f"  [ENRICH] Fetching website: {domain}")
    site = fetch_website(domain)
    enriched["website_status"] = site["status"]
    enriched["website_error"] = site.get("error")
    html = site.get("html") or ""
    enriched["site_text"] = extract_text(html)
    enriched["site_text_hash"] = compute_site_hash(enriched["site_text"])
    sources["website"] = "direct_fetch"

    # Feature 8: Tech detection
    enriched["tech_stack"] = detect_tech(html)
    sources["tech_stack"] = "html_regex"

    # Feature 7: Wikidata
    print(f"  [ENRICH] Querying Wikidata: {company}")
    wiki = get_wikidata(company)
    enriched["founding_year"] = wiki["founding_year"]
    enriched["hq_country"] = wiki["hq_country"]
    enriched["industry"] = wiki["industry"]
    if any(v for v in wiki.values()):
        sources["firmographics"] = "wikidata"

    # Feature 16: Careers scraping
    print(f"  [ENRICH] Checking careers page: {domain}")
    careers = scrape_careers(domain)
    enriched["careers_jobs_count"] = careers["jobs_count"]
    enriched["careers_signal"] = json.dumps(careers)
    if careers["jobs_count"] > 0:
        sources["careers"] = "careers_page_scrape"

    # Feature 18: Social discovery
    social = discover_social(html)
    enriched["social_linkedin"] = social["linkedin"]
    enriched["social_twitter"] = social["twitter"]

    # Feature 19: Favicon
    enriched["favicon_url"] = get_favicon(domain, html)

    # Feature 20: Email pattern
    enriched["email_pattern"] = guess_email_pattern(domain)

    # Feature 60: Competitor detection
    enriched["competitor_tech"] = detect_competitors(html, enriched["tech_stack"])

    # Features 21-23: LLM description, industry classification, employee estimate
    print(f"  [ENRICH] LLM analysis: {company}")
    llm_info = llm_describe_and_classify(company, domain, enriched["site_text"])
    enriched["description"] = llm_info["description"]
    enriched["industry_classified"] = llm_info["industry_classified"]
    enriched["employee_estimate"] = llm_info["employee_estimate"]
    if llm_info["description"]:
        sources["llm_analysis"] = "ollama"

    enriched["sources"] = sources
    enriched["enriched_at"] = __import__("datetime").datetime.now().isoformat()

    return enriched
