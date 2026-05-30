"""
Features 85-88: Decision-maker finder, contact enrichment,
org-chart inference, email verification.
"""
import re
import json
import socket
import smtplib
import requests
from config import LLM_CONFIG


def find_decision_makers(company_name: str, industry: str = "", employee_estimate: str = "") -> list[dict]:
    """Feature 85: Identify likely buyers by role using LLM inference."""
    prompt = f"""For a B2B sale to {company_name} (industry: {industry or 'technology'}, ~{employee_estimate or 'unknown'} employees),
list the 3-5 most likely decision makers and their typical titles.

Respond with ONLY valid JSON:
{{"contacts": [{{"title": "<job title>", "role_category": "<one of: economic_buyer, technical_buyer, champion, influencer, end_user>", "department": "<department>", "seniority": "<C-level/VP/Director/Manager>"}}]}}"""

    try:
        resp = requests.post(
            f"{LLM_CONFIG['base_url']}/api/generate",
            json={"model": LLM_CONFIG["model"], "prompt": prompt, "stream": False,
                  "options": {"temperature": 0.3, "num_predict": 400}},
            timeout=LLM_CONFIG["timeout"],
        )
        raw = resp.json().get("response", "")
        # Find the JSON with array
        match = re.search(r'\{.*"contacts"\s*:\s*\[.*?\]\s*\}', raw, re.DOTALL)
        if match:
            parsed = json.loads(match.group())
            contacts = parsed.get("contacts", [])
            return [
                {
                    "name": None,  # We don't have actual names from LLM
                    "title": c.get("title", "Unknown"),
                    "role_category": c.get("role_category", "unknown"),
                    "department": c.get("department", ""),
                    "seniority": c.get("seniority", ""),
                    "source": "llm_inference",
                }
                for c in contacts[:5]
            ]
    except Exception:
        pass

    return [
        {"name": None, "title": "VP of Sales", "role_category": "economic_buyer", "source": "default"},
        {"name": None, "title": "Head of Marketing", "role_category": "champion", "source": "default"},
        {"name": None, "title": "CTO", "role_category": "technical_buyer", "source": "default"},
    ]


def enrich_contact(contact: dict, company_name: str, domain: str) -> dict:
    """Feature 86: Add public professional context per contact."""
    enriched = {**contact}
    # Generate probable email if we have a name
    if contact.get("name") and domain:
        parts = contact["name"].lower().split()
        if len(parts) >= 2:
            enriched["email"] = f"{parts[0]}.{parts[-1]}@{domain}"
        elif len(parts) == 1:
            enriched["email"] = f"{parts[0]}@{domain}"
    enriched["company"] = company_name
    enriched["domain"] = domain
    return enriched


def infer_org_chart(company_name: str, industry: str = "", employee_estimate: str = "") -> dict:
    """Feature 87: Sketch the buying committee."""
    prompt = f"""Sketch a simplified buying committee org chart for {company_name} (industry: {industry or 'tech'}, ~{employee_estimate or 'unknown'} employees).
Focus on who would be involved in a B2B software purchase decision.

Respond with ONLY valid JSON:
{{"org_chart": {{"decision_maker": "<title>", "budget_holder": "<title>", "technical_evaluator": "<title>", "end_users": "<department/role>", "procurement": "<title or N/A>"}}, "buying_process": "<one sentence about their likely buying process>"}}"""

    try:
        resp = requests.post(
            f"{LLM_CONFIG['base_url']}/api/generate",
            json={"model": LLM_CONFIG["model"], "prompt": prompt, "stream": False,
                  "options": {"temperature": 0.3, "num_predict": 300}},
            timeout=LLM_CONFIG["timeout"],
        )
        raw = resp.json().get("response", "")
        match = re.search(r'\{.*\}', raw, re.DOTALL)
        if match:
            return json.loads(match.group())
    except Exception:
        pass

    return {
        "org_chart": {
            "decision_maker": "VP/Director",
            "budget_holder": "CFO/VP Finance",
            "technical_evaluator": "Engineering Lead",
            "end_users": "Team members",
            "procurement": "N/A for SMB",
        },
        "buying_process": "Likely a champion-led evaluation with VP sign-off.",
    }


def verify_email_domain(domain: str) -> dict:
    """Feature 88: Verify domain has MX records (can receive email)."""
    result = {"has_mx": False, "mx_records": [], "smtp_check": None}
    try:
        import dns.resolver
        answers = dns.resolver.resolve(domain, "MX")
        result["mx_records"] = [str(r.exchange).rstrip(".") for r in answers]
        result["has_mx"] = len(result["mx_records"]) > 0
    except ImportError:
        # Fallback: try socket
        try:
            socket.getaddrinfo(f"mail.{domain}", 25)
            result["has_mx"] = True
            result["mx_records"] = [f"mail.{domain} (inferred)"]
        except socket.gaierror:
            try:
                socket.getaddrinfo(domain, 25)
                result["has_mx"] = True
                result["mx_records"] = [f"{domain} (inferred)"]
            except socket.gaierror:
                pass
    except Exception:
        pass
    return result


def verify_email_address(email: str) -> dict:
    """Feature 88: Basic email verification (format + domain MX)."""
    result = {"email": email, "valid_format": False, "domain_accepts_mail": False}

    # Format check
    if re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
        result["valid_format"] = True

    # Domain MX check
    if result["valid_format"]:
        domain = email.split("@")[1]
        mx = verify_email_domain(domain)
        result["domain_accepts_mail"] = mx["has_mx"]

    return result
