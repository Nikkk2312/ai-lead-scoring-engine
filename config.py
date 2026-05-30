"""
Features 24, 25, 26, 40: Configurable scoring weights, multiple ICP profiles,
negative/disqualifier rules, secrets/config separation.
"""
import os
from pathlib import Path

# Load .env if present
_env_path = Path(__file__).parent / ".env"
if _env_path.exists():
    for line in _env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, val = line.partition("=")
            os.environ.setdefault(key.strip(), val.strip())

# --- Feature 40: Secrets/config separation ---
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///lead_scorer.db")
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", "")
SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
NOTIFY_EMAIL_TO = os.getenv("NOTIFY_EMAIL_TO", "")
HUBSPOT_API_KEY = os.getenv("HUBSPOT_API_KEY", "")
APOLLO_API_KEY = os.getenv("APOLLO_API_KEY", "")
GOOGLE_SERVICE_ACCOUNT_FILE = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "")
GOOGLE_OAUTH_CLIENT_FILE = os.getenv("GOOGLE_OAUTH_CLIENT_FILE", "")
GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID", "")
DASHBOARD_PORT = int(os.getenv("DASHBOARD_PORT", "5000"))
DASHBOARD_SECRET_KEY = os.getenv("DASHBOARD_SECRET_KEY", "dev-secret-key")
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "changeme")
CRON_EXPRESSION = os.getenv("CRON_EXPRESSION", "0 6 * * 1")

# --- Feature 25: Multiple ICP Profiles ---
ICPS = {
    "default": {
        "name": "Mid-Market B2B SaaS",
        "target_geos": ["United States", "Canada", "United Kingdom", "Germany", "Australia"],
        "target_industries": [
            "software", "saas", "technology", "cloud", "fintech",
            "artificial intelligence", "machine learning", "data",
            "e-commerce", "digital", "internet", "automation",
        ],
        "positive_tech_signals": [
            "segment", "hubspot", "marketo", "intercom", "drift",
            "salesforce", "google tag manager", "gtm.js", "mixpanel",
            "amplitude", "hotjar", "clearbit", "6sense", "gong",
        ],
        "negative_tech_signals": [],
        "ideal_age_min": 2,
        "ideal_age_max": 20,
        "ideal_employee_min": 50,
        "ideal_employee_max": 5000,
        # Feature 26: Negative/disqualifier rules
        "disqualifiers": {
            "blocked_geos": ["North Korea", "Iran", "Syria"],
            "blocked_industries": ["gambling", "tobacco", "weapons"],
            "blocked_domains": [],
            "max_employee_count": 50000,
        },
        # Feature 75: Calendar/booking link
        "booking_link": "",
    },
    "enterprise": {
        "name": "Enterprise Tech",
        "target_geos": ["United States", "United Kingdom", "Germany", "Japan"],
        "target_industries": [
            "enterprise software", "cloud computing", "cybersecurity",
            "infrastructure", "devops", "platform",
        ],
        "positive_tech_signals": [
            "salesforce", "marketo", "6sense", "gong", "outreach",
            "zoominfo", "snowflake", "datadog",
        ],
        "negative_tech_signals": [],
        "ideal_age_min": 5,
        "ideal_age_max": 30,
        "ideal_employee_min": 500,
        "ideal_employee_max": 50000,
        "disqualifiers": {
            "blocked_geos": [],
            "blocked_industries": [],
            "blocked_domains": [],
            "max_employee_count": 100000,
        },
        "booking_link": "",
    },
    "smb": {
        "name": "SMB / Startup",
        "target_geos": ["United States", "Canada", "United Kingdom", "Australia", "India"],
        "target_industries": [
            "software", "saas", "e-commerce", "marketplace", "fintech",
            "healthtech", "edtech", "proptech",
        ],
        "positive_tech_signals": [
            "hubspot", "intercom", "segment", "mixpanel", "stripe",
            "google tag manager",
        ],
        "negative_tech_signals": [],
        "ideal_age_min": 0,
        "ideal_age_max": 8,
        "ideal_employee_min": 5,
        "ideal_employee_max": 200,
        "disqualifiers": {
            "blocked_geos": [],
            "blocked_industries": [],
            "blocked_domains": [],
            "max_employee_count": 500,
        },
        "booking_link": "",
    },
}

# Convenience: default ICP
ICP = ICPS["default"]

# --- Feature 24: Configurable scoring weights (must sum to 60) ---
RULE_WEIGHTS = {
    "geo_match": 12,
    "industry_match": 15,
    "tech_signals": 12,
    "company_age": 8,
    "employee_fit": 8,
    "website_quality": 5,
}
assert sum(RULE_WEIGHTS.values()) == 60

# --- LLM scorer config ---
LLM_CONFIG = {
    "model": OLLAMA_MODEL,
    "base_url": OLLAMA_BASE_URL,
    "max_score": 40,
    "timeout": 120,
}

# --- Tier thresholds (Feature 7: configurable) ---
TIER_THRESHOLDS = {
    "hot_min": int(os.getenv("TIER_HOT_MIN", "70")),
    "warm_min": int(os.getenv("TIER_WARM_MIN", "40")),
}
TIERS = {
    "Hot": (TIER_THRESHOLDS["hot_min"], 100),
    "Warm": (TIER_THRESHOLDS["warm_min"], TIER_THRESHOLDS["hot_min"] - 1),
    "Cold": (0, TIER_THRESHOLDS["warm_min"] - 1),
}

# --- Feature 1-4: Tri-dimensional scoring weights (Fit / Engagement / Intent) ---
SCORE_DIMENSIONS = {
    "fit_weight": float(os.getenv("SCORE_FIT_WEIGHT", "0.40")),
    "engagement_weight": float(os.getenv("SCORE_ENGAGEMENT_WEIGHT", "0.35")),
    "intent_weight": float(os.getenv("SCORE_INTENT_WEIGHT", "0.25")),
}

# --- Feature 5: Score decay config ---
SCORE_DECAY = {
    "enabled": os.getenv("SCORE_DECAY_ENABLED", "true").lower() == "true",
    "interval_days": int(os.getenv("SCORE_DECAY_INTERVAL_DAYS", "30")),
    "rate": float(os.getenv("SCORE_DECAY_RATE", "0.10")),  # 10% per interval
    "mode": os.getenv("SCORE_DECAY_MODE", "linear"),  # linear or exponential
}

# --- Feature 9: Scoring model templates ---
SCORING_TEMPLATES = {
    "enterprise_abm": {"fit_weight": 0.70, "engagement_weight": 0.20, "intent_weight": 0.10},
    "outbound_sdr": {"fit_weight": 0.50, "engagement_weight": 0.30, "intent_weight": 0.20},
    "plg_inbound": {"fit_weight": 0.30, "engagement_weight": 0.45, "intent_weight": 0.25},
    "balanced": {"fit_weight": 0.40, "engagement_weight": 0.35, "intent_weight": 0.25},
}

# --- Feature 6: Negative scoring rules ---
NEGATIVE_SCORE_RULES = {
    "competitor_email_domains": ["gmail.com", "yahoo.com", "hotmail.com"],
    "careers_page_visit": -5,
    "unsubscribe": -15,
    "competitor_domain": -20,
    "no_engagement_days": 90,
    "no_engagement_penalty": -10,
}

# --- Feature 88: Buying stages (6sense-inspired) ---
BUYING_STAGES = {
    "Target": {"min_score": 0, "max_score": 19, "description": "Not in-market"},
    "Awareness": {"min_score": 20, "max_score": 39, "description": "Top of funnel"},
    "Consideration": {"min_score": 40, "max_score": 59, "description": "Evaluating options"},
    "Decision": {"min_score": 60, "max_score": 79, "description": "Active buying signals"},
    "Purchase": {"min_score": 80, "max_score": 100, "description": "Ready to buy"},
}

# --- Feature 36: Rate limiting ---
RATE_LIMIT = {
    "requests_per_second": 2,
    "delay_between_companies": 1.0,
}

# --- Feature 38: Caching ---
CACHE_TTL_HOURS = 72

# --- Feature 47: Intent keywords ---
INTENT_KEYWORDS = [
    "request a demo", "book a demo", "get started", "free trial",
    "pricing", "compare", "alternative to", "migrate from",
    "looking for", "evaluate", "implement", "solution for",
    "roi calculator", "case study", "vs ",
]

# --- Feature 60: Competitors to detect ---
COMPETITORS = [
    "salesforce", "hubspot", "marketo", "outreach", "salesloft",
    "apollo", "zoominfo", "clearbit", "6sense", "gong",
    "drift", "intercom", "pardot",
]

# --- Output ---
OUTPUT_FILE = "scored_leads.xlsx"
OUTPUT_CSV = "scored_leads.csv"
DB_FILE = "lead_scorer.db"
