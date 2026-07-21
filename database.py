"""
Features 31, 33, 38, 51, 67, 80, 89, 90: Database backend with run history,
error logging, caching, watchlists, audit trail, cross-run dedup, Postgres support, auth.
"""
import json
import sqlite3
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from config import DB_FILE, CACHE_TTL_HOURS, ADMIN_USERNAME, ADMIN_PASSWORD


def get_db_path() -> str:
    return str(Path(__file__).parent / DB_FILE)


def get_connection():
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """Create all tables if they don't exist."""
    conn = get_connection()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS companies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_name TEXT NOT NULL,
            domain TEXT UNIQUE NOT NULL,
            website_status INTEGER,
            site_text TEXT,
            site_text_hash TEXT,
            tech_stack TEXT DEFAULT '[]',
            founding_year INTEGER,
            hq_country TEXT,
            industry TEXT,
            industry_classified TEXT,
            employee_estimate TEXT,
            description TEXT,
            social_linkedin TEXT,
            social_twitter TEXT,
            favicon_url TEXT,
            email_pattern TEXT,
            careers_jobs_count INTEGER,
            careers_signal TEXT,
            event_mentions TEXT DEFAULT '[]',
            intent_signals TEXT DEFAULT '[]',
            competitor_tech TEXT DEFAULT '[]',
            enriched_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER REFERENCES companies(id),
            run_id INTEGER REFERENCES runs(id),
            icp_name TEXT DEFAULT 'default',
            total_score INTEGER,
            tier TEXT,
            rule_score INTEGER,
            soft_score INTEGER,
            confidence REAL DEFAULT 1.0,
            rule_breakdown TEXT DEFAULT '{}',
            reasoning TEXT,
            key_signal TEXT,
            synthesis TEXT,
            outreach_line TEXT,
            next_action TEXT,
            objections TEXT,
            target_persona TEXT,
            sources TEXT DEFAULT '{}',
            -- Tri-dimensional scores (Features 1-3)
            fit_score INTEGER DEFAULT 0,
            fit_score_pct INTEGER DEFAULT 0,
            engagement_score INTEGER DEFAULT 0,
            engagement_score_pct INTEGER DEFAULT 0,
            intent_score INTEGER DEFAULT 0,
            intent_score_pct INTEGER DEFAULT 0,
            -- Buying stage (Feature 88)
            buying_stage TEXT DEFAULT 'Target',
            -- Matrix cell (Feature 36)
            fit_grade TEXT DEFAULT 'C',
            engagement_grade TEXT DEFAULT '3',
            matrix_cell TEXT DEFAULT 'C3',
            -- Explainability (Feature 12)
            top_positive_factors TEXT DEFAULT '[]',
            top_negative_factors TEXT DEFAULT '[]',
            -- Feedback (Feature 17)
            feedback TEXT,
            feedback_by TEXT,
            feedback_at TIMESTAMP,
            scored_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            started_at TIMESTAMP,
            completed_at TIMESTAMP,
            status TEXT DEFAULT 'running',
            total_leads INTEGER DEFAULT 0,
            hot_count INTEGER DEFAULT 0,
            warm_count INTEGER DEFAULT 0,
            cold_count INTEGER DEFAULT 0,
            error_count INTEGER DEFAULT 0,
            icp_name TEXT DEFAULT 'default',
            config_snapshot TEXT DEFAULT '{}',
            source_file TEXT
        );

        CREATE TABLE IF NOT EXISTS errors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER REFERENCES runs(id),
            company_name TEXT,
            domain TEXT,
            stage TEXT,
            error_message TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS watchlists (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            description TEXT DEFAULT '',
            domains TEXT DEFAULT '[]',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS contacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER REFERENCES companies(id),
            name TEXT,
            title TEXT,
            role_category TEXT,
            email TEXT,
            email_verified INTEGER DEFAULT 0,
            linkedin_url TEXT,
            source TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS cache (
            cache_key TEXT PRIMARY KEY,
            value TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS score_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            domain TEXT,
            total_score INTEGER,
            tier TEXT,
            icp_name TEXT DEFAULT 'default',
            fit_score_pct INTEGER DEFAULT 0,
            engagement_score_pct INTEGER DEFAULT 0,
            intent_score_pct INTEGER DEFAULT 0,
            buying_stage TEXT DEFAULT 'Target',
            matrix_cell TEXT DEFAULT 'C3',
            recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            domain TEXT NOT NULL,
            username TEXT,
            feedback_type TEXT NOT NULL,
            original_score INTEGER,
            adjusted_score INTEGER,
            comment TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS score_settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            setting_key TEXT UNIQUE NOT NULL,
            setting_value TEXT NOT NULL,
            updated_by TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            action TEXT NOT NULL,
            entity_type TEXT,
            entity_id TEXT,
            details TEXT DEFAULT '{}',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT DEFAULT 'viewer',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_scores_company ON scores(company_id);
        CREATE INDEX IF NOT EXISTS idx_scores_run ON scores(run_id);
        CREATE INDEX IF NOT EXISTS idx_errors_run ON errors(run_id);
        CREATE INDEX IF NOT EXISTS idx_score_history_domain ON score_history(domain);
        CREATE INDEX IF NOT EXISTS idx_contacts_company ON contacts(company_id);
        CREATE INDEX IF NOT EXISTS idx_cache_expires ON cache(expires_at);
    """)
    conn.commit()

    # Create default admin user if no users exist
    existing = conn.execute("SELECT COUNT(*) as cnt FROM users").fetchone()
    if existing["cnt"] == 0:
        pw_hash = hashlib.sha256(ADMIN_PASSWORD.encode()).hexdigest()
        conn.execute(
            "INSERT INTO users (username, password_hash, role) VALUES (?, ?, 'admin')",
            (ADMIN_USERNAME, pw_hash),
        )
        conn.commit()

    conn.close()


# --- Run management (Feature 31) ---

def create_run(icp_name: str = "default", total_leads: int = 0, source_file: str = "") -> int:
    conn = get_connection()
    cur = conn.execute(
        "INSERT INTO runs (started_at, status, total_leads, icp_name, source_file) VALUES (?, 'running', ?, ?, ?)",
        (datetime.now().isoformat(), total_leads, icp_name, source_file),
    )
    run_id = cur.lastrowid
    conn.commit()
    conn.close()
    return run_id


def complete_run(run_id: int, hot: int, warm: int, cold: int, errors: int):
    conn = get_connection()
    conn.execute(
        "UPDATE runs SET completed_at=?, status='completed', hot_count=?, warm_count=?, cold_count=?, error_count=? WHERE id=?",
        (datetime.now().isoformat(), hot, warm, cold, errors, run_id),
    )
    conn.commit()
    conn.close()


def get_runs(limit: int = 50) -> list[dict]:
    conn = get_connection()
    rows = conn.execute("SELECT * FROM runs ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_run(run_id: int) -> dict | None:
    conn = get_connection()
    row = conn.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


# --- Company management (Feature 30, 80) ---

def upsert_company(data: dict) -> int:
    """Insert or update a company. Returns company ID. Feature 30: dedup by domain."""
    conn = get_connection()
    existing = conn.execute("SELECT id FROM companies WHERE domain=?", (data["domain"],)).fetchone()

    fields = [
        "company_name", "domain", "website_status", "site_text", "site_text_hash",
        "tech_stack", "founding_year", "hq_country", "industry", "industry_classified",
        "employee_estimate", "description", "social_linkedin", "social_twitter",
        "favicon_url", "email_pattern", "careers_jobs_count", "careers_signal",
        "event_mentions", "intent_signals", "competitor_tech", "enriched_at",
    ]

    if existing:
        sets = ", ".join(f"{f}=?" for f in fields if f in data)
        vals = [_serialize(data[f]) for f in fields if f in data]
        vals.append(datetime.now().isoformat())
        vals.append(existing["id"])
        conn.execute(f"UPDATE companies SET {sets}, updated_at=? WHERE id=?", vals)
        company_id = existing["id"]
    else:
        present = [f for f in fields if f in data]
        placeholders = ", ".join("?" for _ in present)
        cols = ", ".join(present)
        vals = [_serialize(data[f]) for f in present]
        cur = conn.execute(f"INSERT INTO companies ({cols}) VALUES ({placeholders})", vals)
        company_id = cur.lastrowid

    conn.commit()
    conn.close()
    return company_id


def get_company(domain: str) -> dict | None:
    conn = get_connection()
    row = conn.execute("SELECT * FROM companies WHERE domain=?", (domain,)).fetchone()
    conn.close()
    if not row:
        return None
    d = dict(row)
    for key in ("tech_stack", "event_mentions", "intent_signals", "competitor_tech"):
        if d.get(key) and isinstance(d[key], str):
            try:
                d[key] = json.loads(d[key])
            except json.JSONDecodeError:
                d[key] = []
    return d


def get_all_companies() -> list[dict]:
    conn = get_connection()
    rows = conn.execute("SELECT * FROM companies ORDER BY company_name").fetchall()
    conn.close()
    results = []
    for row in rows:
        d = dict(row)
        for key in ("tech_stack", "event_mentions", "intent_signals", "competitor_tech"):
            if d.get(key) and isinstance(d[key], str):
                try:
                    d[key] = json.loads(d[key])
                except json.JSONDecodeError:
                    d[key] = []
        results.append(d)
    return results


# --- Score management (Features 28, 67) ---

def save_score(company_id: int, run_id: int, score_data: dict):
    conn = get_connection()
    conn.execute(
        """INSERT INTO scores (company_id, run_id, icp_name, total_score, tier,
           rule_score, soft_score, confidence, rule_breakdown, reasoning, key_signal,
           synthesis, outreach_line, next_action, objections, target_persona, sources,
           fit_score, fit_score_pct, engagement_score, engagement_score_pct,
           intent_score, intent_score_pct, buying_stage, fit_grade, engagement_grade,
           matrix_cell, top_positive_factors, top_negative_factors)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            company_id, run_id,
            score_data.get("icp_name", "default"),
            score_data.get("total_score", 0),
            score_data.get("tier", "Cold"),
            score_data.get("rule_score", 0),
            score_data.get("soft_score", 0),
            score_data.get("confidence", 1.0),
            _serialize(score_data.get("rule_breakdown", {})),
            score_data.get("reasoning", ""),
            score_data.get("key_signal", ""),
            score_data.get("synthesis", ""),
            score_data.get("outreach_line", ""),
            score_data.get("next_action", ""),
            score_data.get("objections", ""),
            score_data.get("target_persona", ""),
            _serialize(score_data.get("sources", {})),
            score_data.get("fit_score", score_data.get("rule_score", 0)),
            score_data.get("fit_score_pct", 0),
            score_data.get("engagement_score", 0),
            score_data.get("engagement_score_pct", 0),
            score_data.get("intent_score", 0),
            score_data.get("intent_score_pct", 0),
            score_data.get("buying_stage", "Target"),
            score_data.get("fit_grade", "C"),
            score_data.get("engagement_grade", "3"),
            score_data.get("matrix_cell", "C3"),
            _serialize(score_data.get("top_positive_factors", [])),
            _serialize(score_data.get("top_negative_factors", [])),
        ),
    )
    conn.commit()
    conn.close()


def get_scores_for_run(run_id: int) -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        """SELECT s.*, c.company_name, c.domain, c.hq_country, c.industry,
           c.founding_year, c.tech_stack, c.employee_estimate, c.description,
           c.social_linkedin, c.social_twitter, c.favicon_url, c.email_pattern,
           c.careers_jobs_count
           FROM scores s JOIN companies c ON s.company_id = c.id
           WHERE s.run_id=? ORDER BY s.total_score DESC""",
        (run_id,),
    ).fetchall()
    conn.close()
    return [_parse_score_row(r) for r in rows]


def get_latest_scores(icp_name: str = "default") -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        """SELECT s.*, c.company_name, c.domain, c.hq_country, c.industry,
           c.founding_year, c.tech_stack, c.employee_estimate, c.description,
           c.social_linkedin, c.social_twitter, c.favicon_url, c.email_pattern,
           c.careers_jobs_count
           FROM scores s JOIN companies c ON s.company_id = c.id
           WHERE s.icp_name=? AND s.id IN (
               SELECT MAX(id) FROM scores WHERE icp_name=? GROUP BY company_id
           )
           ORDER BY s.total_score DESC""",
        (icp_name, icp_name),
    ).fetchall()
    conn.close()
    return [_parse_score_row(r) for r in rows]


def get_company_score_history(domain: str) -> list[dict]:
    """Feature 50: Score history for change detection."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM score_history WHERE domain=? ORDER BY recorded_at DESC LIMIT 50",
        (domain,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def record_score_history(domain: str, total_score: int, tier: str, icp_name: str = "default"):
    conn = get_connection()
    conn.execute(
        "INSERT INTO score_history (domain, total_score, tier, icp_name) VALUES (?, ?, ?, ?)",
        (domain, total_score, tier, icp_name),
    )
    conn.commit()
    conn.close()


# --- Error logging (Feature 33) ---

def log_error(run_id: int, company_name: str, domain: str, stage: str, message: str):
    conn = get_connection()
    conn.execute(
        "INSERT INTO errors (run_id, company_name, domain, stage, error_message) VALUES (?, ?, ?, ?, ?)",
        (run_id, company_name, domain, stage, message[:2000]),
    )
    conn.commit()
    conn.close()


def get_errors_for_run(run_id: int) -> list[dict]:
    conn = get_connection()
    rows = conn.execute("SELECT * FROM errors WHERE run_id=? ORDER BY id", (run_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# --- Caching (Feature 38) ---

def cache_get(key: str) -> str | None:
    conn = get_connection()
    row = conn.execute(
        "SELECT value FROM cache WHERE cache_key=? AND expires_at > ?",
        (key, datetime.now().isoformat()),
    ).fetchone()
    conn.close()
    return row["value"] if row else None


def cache_set(key: str, value: str, ttl_hours: int = CACHE_TTL_HOURS):
    conn = get_connection()
    expires = (datetime.now() + timedelta(hours=ttl_hours)).isoformat()
    conn.execute(
        "INSERT OR REPLACE INTO cache (cache_key, value, created_at, expires_at) VALUES (?, ?, ?, ?)",
        (key, value, datetime.now().isoformat(), expires),
    )
    conn.commit()
    conn.close()


def cache_key_for(prefix: str, identifier: str) -> str:
    return f"{prefix}:{hashlib.md5(identifier.encode()).hexdigest()}"


def cleanup_cache():
    conn = get_connection()
    conn.execute("DELETE FROM cache WHERE expires_at < ?", (datetime.now().isoformat(),))
    conn.commit()
    conn.close()


# --- Watchlists (Feature 51) ---

def create_watchlist(name: str, description: str = "", domains: list[str] = None) -> int:
    conn = get_connection()
    cur = conn.execute(
        "INSERT INTO watchlists (name, description, domains) VALUES (?, ?, ?)",
        (name, description, json.dumps(domains or [])),
    )
    wid = cur.lastrowid
    conn.commit()
    conn.close()
    return wid


def get_watchlists() -> list[dict]:
    conn = get_connection()
    rows = conn.execute("SELECT * FROM watchlists ORDER BY name").fetchall()
    conn.close()
    results = []
    for r in rows:
        d = dict(r)
        d["domains"] = json.loads(d["domains"]) if d["domains"] else []
        results.append(d)
    return results


def add_to_watchlist(name: str, domains: list[str]):
    conn = get_connection()
    row = conn.execute("SELECT domains FROM watchlists WHERE name=?", (name,)).fetchone()
    if row:
        existing = json.loads(row["domains"]) if row["domains"] else []
        updated = list(set(existing + domains))
        conn.execute("UPDATE watchlists SET domains=? WHERE name=?", (json.dumps(updated), name))
        conn.commit()
    conn.close()


# --- Contacts (Feature 85-88) ---

def save_contact(company_id: int, contact: dict):
    conn = get_connection()
    conn.execute(
        """INSERT INTO contacts (company_id, name, title, role_category, email,
           email_verified, linkedin_url, source) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            company_id, contact.get("name"), contact.get("title"),
            contact.get("role_category"), contact.get("email"),
            1 if contact.get("email_verified") else 0,
            contact.get("linkedin_url"), contact.get("source"),
        ),
    )
    conn.commit()
    conn.close()


def get_contacts_for_company(company_id: int) -> list[dict]:
    conn = get_connection()
    rows = conn.execute("SELECT * FROM contacts WHERE company_id=? ORDER BY role_category", (company_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# --- Helpers ---

def _serialize(val):
    if isinstance(val, (list, dict)):
        return json.dumps(val)
    return val


def _parse_score_row(row) -> dict:
    d = dict(row)
    for key in ("rule_breakdown", "sources"):
        if d.get(key) and isinstance(d[key], str):
            try:
                d[key] = json.loads(d[key])
            except json.JSONDecodeError:
                d[key] = {}
    for key in ("tech_stack",):
        if d.get(key) and isinstance(d[key], str):
            try:
                d[key] = json.loads(d[key])
            except json.JSONDecodeError:
                d[key] = []
    return d


# --- Feature 95: Backup & restore ---

def backup_db(backup_path: str = None):
    import shutil
    src = get_db_path()
    dst = backup_path or f"{src}.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    shutil.copy2(src, dst)
    return dst


def get_db_stats() -> dict:
    """Feature 94: Usage stats."""
    conn = get_connection()
    stats = {}
    for table in ["companies", "scores", "runs", "errors", "contacts", "cache", "users"]:
        row = conn.execute(f"SELECT COUNT(*) as cnt FROM {table}").fetchone()
        stats[table] = row["cnt"]
    db_path = Path(get_db_path())
    stats["db_size_mb"] = round(db_path.stat().st_size / 1024 / 1024, 2) if db_path.exists() else 0
    conn.close()
    return stats


def update_lead_stage(domain: str, stage: str) -> bool:
    """Persist a Kanban stage change to the lead's most recent score row."""
    valid = {"Target", "Awareness", "Consideration", "Decision", "Purchase"}
    if stage not in valid:
        return False
    conn = get_connection()
    row = conn.execute("SELECT id FROM companies WHERE domain=?", (domain,)).fetchone()
    if not row:
        conn.close()
        return False
    cid = row["id"]
    conn.execute(
        """UPDATE scores SET buying_stage=? WHERE id=(
               SELECT id FROM scores WHERE company_id=? ORDER BY scored_at DESC, id DESC LIMIT 1)""",
        (stage, cid),
    )
    conn.commit()
    conn.close()
    return True


# --- Feature 90: Multi-user auth ---

def authenticate_user(username: str, password: str) -> dict | None:
    """Verify username/password. Returns user dict or None."""
    pw_hash = hashlib.sha256(password.encode()).hexdigest()
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM users WHERE username=? AND password_hash=?",
        (username, pw_hash),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def create_user(username: str, password: str, role: str = "viewer") -> bool:
    """Create a new user. Returns True on success."""
    pw_hash = hashlib.sha256(password.encode()).hexdigest()
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
            (username, pw_hash, role),
        )
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        conn.close()
        return False


def get_user(username: str) -> dict | None:
    conn = get_connection()
    row = conn.execute("SELECT id, username, role, created_at FROM users WHERE username=?", (username,)).fetchone()
    conn.close()
    return dict(row) if row else None


def list_users() -> list[dict]:
    conn = get_connection()
    rows = conn.execute("SELECT id, username, role, created_at FROM users ORDER BY id").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def change_password(username: str, new_password: str) -> bool:
    pw_hash = hashlib.sha256(new_password.encode()).hexdigest()
    conn = get_connection()
    conn.execute("UPDATE users SET password_hash=? WHERE username=?", (pw_hash, username))
    conn.commit()
    affected = conn.total_changes
    conn.close()
    return affected > 0


# --- Feature 17: Feedback ---

def save_feedback(domain: str, username: str, feedback_type: str,
                  original_score: int, adjusted_score: int, comment: str = ""):
    conn = get_connection()
    conn.execute(
        """INSERT INTO feedback (domain, username, feedback_type, original_score,
           adjusted_score, comment) VALUES (?, ?, ?, ?, ?, ?)""",
        (domain, username, feedback_type, original_score, adjusted_score, comment),
    )
    conn.commit()
    conn.close()


def get_feedback(domain: str = None, limit: int = 50) -> list[dict]:
    conn = get_connection()
    if domain:
        rows = conn.execute(
            "SELECT * FROM feedback WHERE domain=? ORDER BY created_at DESC LIMIT ?",
            (domain, limit)).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM feedback ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_feedback_stats() -> dict:
    conn = get_connection()
    total = conn.execute("SELECT COUNT(*) as cnt FROM feedback").fetchone()["cnt"]
    accepts = conn.execute("SELECT COUNT(*) as cnt FROM feedback WHERE feedback_type='accept'").fetchone()["cnt"]
    rejects = conn.execute("SELECT COUNT(*) as cnt FROM feedback WHERE feedback_type='reject'").fetchone()["cnt"]
    conn.close()
    return {"total": total, "accepts": accepts, "rejects": rejects,
            "accuracy_rate": round(accepts / max(total, 1) * 100, 1)}


# --- Feature 96: Audit log ---

def log_audit(username: str, action: str, entity_type: str = "",
              entity_id: str = "", details: dict = None):
    conn = get_connection()
    conn.execute(
        "INSERT INTO audit_log (username, action, entity_type, entity_id, details) VALUES (?, ?, ?, ?, ?)",
        (username, action, entity_type, entity_id, json.dumps(details or {})),
    )
    conn.commit()
    conn.close()


def get_audit_log(limit: int = 100) -> list[dict]:
    conn = get_connection()
    rows = conn.execute("SELECT * FROM audit_log ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# --- Score settings ---

def save_setting(key: str, value: str, username: str = "system"):
    conn = get_connection()
    conn.execute(
        "INSERT OR REPLACE INTO score_settings (setting_key, setting_value, updated_by, updated_at) VALUES (?, ?, ?, ?)",
        (key, value, username, datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()


def get_setting(key: str, default: str = "") -> str:
    conn = get_connection()
    row = conn.execute("SELECT setting_value FROM score_settings WHERE setting_key=?", (key,)).fetchone()
    conn.close()
    return row["setting_value"] if row else default


def get_all_settings() -> dict:
    conn = get_connection()
    rows = conn.execute("SELECT setting_key, setting_value FROM score_settings").fetchall()
    conn.close()
    return {r["setting_key"]: r["setting_value"] for r in rows}


# --- Enrichment coverage (Feature 93) ---

def get_enrichment_coverage() -> dict:
    conn = get_connection()
    total = conn.execute("SELECT COUNT(*) as cnt FROM companies").fetchone()["cnt"]
    if total == 0:
        conn.close()
        return {"total": 0, "fields": {}}
    fields = {}
    for col in ["hq_country", "industry", "founding_year", "employee_estimate",
                 "description", "social_linkedin", "tech_stack", "email_pattern"]:
        filled = conn.execute(
            f"SELECT COUNT(*) as cnt FROM companies WHERE {col} IS NOT NULL AND {col} != '' AND {col} != '[]'"
        ).fetchone()["cnt"]
        fields[col] = {"filled": filled, "total": total, "pct": round(filled / total * 100, 1)}
    conn.close()
    return {"total": total, "fields": fields}


# --- Activity feed (Feature 115) ---

def get_activity_feed(limit: int = 30) -> list[dict]:
    """Get recent activity across scoring, feedback, and runs."""
    conn = get_connection()
    activities = []
    # Recent scores
    rows = conn.execute(
        """SELECT s.scored_at as ts, c.company_name, c.domain, s.total_score, s.tier, s.buying_stage
           FROM scores s JOIN companies c ON s.company_id = c.id
           ORDER BY s.scored_at DESC LIMIT ?""", (limit,)).fetchall()
    for r in rows:
        activities.append({
            "type": "score", "timestamp": r["ts"],
            "message": f"{r['company_name']} scored {r['total_score']} ({r['tier']})",
            "domain": r["domain"], "detail": r["buying_stage"] or ""
        })
    # Recent feedback
    rows = conn.execute(
        "SELECT * FROM feedback ORDER BY created_at DESC LIMIT ?", (min(limit, 10),)).fetchall()
    for r in rows:
        activities.append({
            "type": "feedback", "timestamp": r["created_at"],
            "message": f"Feedback on {r['domain']}: {r['feedback_type']}",
            "domain": r["domain"], "detail": r["comment"] or ""
        })
    # Sort all by timestamp
    activities.sort(key=lambda a: a.get("timestamp", ""), reverse=True)
    conn.close()
    return activities[:limit]
