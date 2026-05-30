"""
Features 71-77: CRM push (HubSpot), Apollo provider toggle,
sequencer hand-off, calendar link, Zapier/Make export, Google Sheets two-way sync.
"""
import json
import csv
import requests
from io import StringIO
from pathlib import Path
from config import HUBSPOT_API_KEY, APOLLO_API_KEY, GOOGLE_SERVICE_ACCOUNT_FILE, GOOGLE_OAUTH_CLIENT_FILE, GOOGLE_SHEET_ID


# ---------------------------------------------------------------------------
# Feature 71: HubSpot CRM Push
# ---------------------------------------------------------------------------

def push_to_hubspot(leads: list[dict]) -> dict:
    """Push scored leads to HubSpot as contacts/companies."""
    if not HUBSPOT_API_KEY:
        return {"status": "skipped", "reason": "HUBSPOT_API_KEY not configured"}

    results = {"created": 0, "updated": 0, "errors": []}
    headers = {
        "Authorization": f"Bearer {HUBSPOT_API_KEY}",
        "Content-Type": "application/json",
    }

    for lead in leads:
        payload = {
            "properties": {
                "domain": lead.get("domain", ""),
                "name": lead.get("company_name", ""),
                "industry": lead.get("industry_classified") or lead.get("industry") or "",
                "country": lead.get("hq_country") or "",
                "description": (lead.get("description") or "")[:1000],
                "founded_year": str(lead.get("founding_year") or ""),
                "numberofemployees": _parse_employee_count(lead.get("employee_estimate")),
                # Custom properties (must be created in HubSpot first)
                # "lead_score": lead.get("total_score", 0),
                # "lead_tier": lead.get("tier", "Cold"),
            }
        }

        try:
            # Search for existing company by domain
            search_resp = requests.post(
                "https://api.hubapi.com/crm/v3/objects/companies/search",
                headers=headers,
                json={"filterGroups": [{"filters": [
                    {"propertyName": "domain", "operator": "EQ", "value": lead["domain"]}
                ]}]},
                timeout=15,
            )
            existing = search_resp.json().get("results", [])

            if existing:
                # Update
                company_id = existing[0]["id"]
                requests.patch(
                    f"https://api.hubapi.com/crm/v3/objects/companies/{company_id}",
                    headers=headers, json=payload, timeout=15,
                )
                results["updated"] += 1
            else:
                # Create
                requests.post(
                    "https://api.hubapi.com/crm/v3/objects/companies",
                    headers=headers, json=payload, timeout=15,
                )
                results["created"] += 1
        except Exception as e:
            results["errors"].append({"domain": lead.get("domain"), "error": str(e)[:200]})

    results["status"] = "completed"
    return results


# ---------------------------------------------------------------------------
# Feature 72: Apollo Provider Toggle
# ---------------------------------------------------------------------------

def enrich_via_apollo(domain: str) -> dict:
    """Enrich a company via Apollo API when available."""
    if not APOLLO_API_KEY:
        return {"status": "skipped", "reason": "APOLLO_API_KEY not configured"}

    try:
        resp = requests.post(
            "https://api.apollo.io/v1/organizations/enrich",
            headers={"Content-Type": "application/json"},
            json={"api_key": APOLLO_API_KEY, "domain": domain},
            timeout=15,
        )
        data = resp.json().get("organization", {})
        return {
            "status": "ok",
            "name": data.get("name"),
            "industry": data.get("industry"),
            "employee_count": data.get("estimated_num_employees"),
            "founded_year": data.get("founded_year"),
            "city": data.get("city"),
            "country": data.get("country"),
            "description": data.get("short_description"),
            "linkedin_url": data.get("linkedin_url"),
            "technologies": data.get("current_technologies", []),
        }
    except Exception as e:
        return {"status": "error", "error": str(e)[:200]}


# ---------------------------------------------------------------------------
# Feature 74: Sequencer Hand-off
# ---------------------------------------------------------------------------

def handoff_to_sequencer(lead: dict, sequencer: str = "generic") -> dict:
    """Push Hot leads into an outreach sequencer."""
    handoff = {
        "company": lead.get("company_name"),
        "domain": lead.get("domain"),
        "score": lead.get("total_score"),
        "tier": lead.get("tier"),
        "email_pattern": lead.get("email_pattern"),
        "outreach_line": lead.get("outreach_line", ""),
        "target_persona": lead.get("target_persona", ""),
        "next_action": lead.get("next_action", ""),
    }

    if sequencer == "webhook":
        # Generic webhook for any sequencer
        return {"status": "ready", "payload": handoff,
                "instruction": "POST this payload to your sequencer's webhook URL"}

    return {"status": "ready", "payload": handoff}


# ---------------------------------------------------------------------------
# Feature 75: Calendar/Booking Link Inject
# ---------------------------------------------------------------------------

def inject_booking_link(lead: dict, booking_link: str = "") -> str:
    """Attach a booking link to outreach drafts."""
    outreach = lead.get("outreach_line", "")
    if booking_link and outreach:
        return f"{outreach}\n\nBook a time: {booking_link}"
    return outreach


# ---------------------------------------------------------------------------
# Feature 76: Zapier/Make Export (Webhook)
# ---------------------------------------------------------------------------

def export_to_webhook(leads: list[dict], webhook_url: str) -> dict:
    """Send results to Zapier/Make/n8n via webhook."""
    if not webhook_url:
        return {"status": "skipped", "reason": "No webhook URL provided"}

    try:
        payload = {
            "event": "lead_scoring_complete",
            "total_leads": len(leads),
            "leads": [
                {
                    "company_name": l.get("company_name"),
                    "domain": l.get("domain"),
                    "score": l.get("total_score"),
                    "tier": l.get("tier"),
                    "industry": l.get("industry_classified") or l.get("industry"),
                    "hq_country": l.get("hq_country"),
                    "key_signal": l.get("key_signal"),
                    "outreach_line": l.get("outreach_line", ""),
                }
                for l in leads
            ],
        }
        resp = requests.post(webhook_url, json=payload, timeout=15)
        return {"status": "sent", "http_status": resp.status_code}
    except Exception as e:
        return {"status": "error", "error": str(e)[:200]}


# ---------------------------------------------------------------------------
# Feature 77: Google Sheets Two-Way Sync (OAuth2 user flow)
# ---------------------------------------------------------------------------

SHEETS_COLUMNS = [
    "Company", "Domain", "Score", "Tier", "Confidence", "Rule (/60)", "LLM (/40)",
    "Industry", "HQ Country", "Founded", "Employees", "Tech Stack",
    "Hiring Signal", "Key Signal", "Reasoning", "Outreach Line", "Next Action",
    "LinkedIn", "Email Pattern",
]

SHEETS_KEYS = [
    "company_name", "domain", "total_score", "tier", "confidence", "rule_score", "soft_score",
    "industry_classified", "hq_country", "founding_year", "employee_estimate", "tech_stack",
    "careers_jobs_count", "key_signal", "reasoning", "outreach_line", "next_action",
    "social_linkedin", "email_pattern",
]

_ENV_FILE = Path(__file__).parent / ".env"
_TOKEN_FILE = Path(__file__).parent / "google_token.json"
_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
]


def _get_user_creds():
    """Get OAuth2 user credentials. Opens browser on first run for consent."""
    from google.oauth2.credentials import Credentials as UserCredentials
    from google.auth.transport.requests import Request

    creds = None

    # Load saved token if it exists
    if _TOKEN_FILE.exists():
        try:
            creds = UserCredentials.from_authorized_user_file(str(_TOKEN_FILE), _SCOPES)
        except Exception:
            pass

    # Refresh or get new token
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
        except Exception:
            creds = None

    if not creds or not creds.valid:
        if not GOOGLE_OAUTH_CLIENT_FILE:
            print("[SHEETS] No GOOGLE_OAUTH_CLIENT_FILE configured in .env")
            return None
        try:
            from google_auth_oauthlib.flow import InstalledAppFlow
            flow = InstalledAppFlow.from_client_secrets_file(GOOGLE_OAUTH_CLIENT_FILE, _SCOPES)
            creds = flow.run_local_server(port=8090, prompt="consent",
                                          success_message="Google Sheets connected! You can close this tab.")
            # Save token for next time
            _TOKEN_FILE.write_text(creds.to_json())
            print("[SHEETS] Authorized successfully. Token saved for future runs.")
        except Exception as e:
            print("[SHEETS] OAuth error: {}".format(e))
            return None

    return creds


def _get_gspread_client():
    """Get authenticated gspread client using OAuth2 user credentials."""
    creds = _get_user_creds()
    if not creds:
        return None
    try:
        import gspread
        return gspread.authorize(creds)
    except Exception as e:
        print("[SHEETS] gspread auth error: {}".format(e))
        return None


def _save_sheet_id_to_env(sheet_id: str):
    """Persist GOOGLE_SHEET_ID into .env so future runs reuse the same sheet."""
    import os
    os.environ["GOOGLE_SHEET_ID"] = sheet_id
    if _ENV_FILE.exists():
        lines = _ENV_FILE.read_text().splitlines()
        new_lines = []
        found = False
        for line in lines:
            if line.strip().startswith("GOOGLE_SHEET_ID"):
                new_lines.append("GOOGLE_SHEET_ID={}".format(sheet_id))
                found = True
            else:
                new_lines.append(line)
        if not found:
            new_lines.append("GOOGLE_SHEET_ID={}".format(sheet_id))
        _ENV_FILE.write_text("\n".join(new_lines) + "\n")
    else:
        _ENV_FILE.write_text("GOOGLE_SHEET_ID={}\n".format(sheet_id))
    print("[SHEETS] Saved GOOGLE_SHEET_ID={} to .env".format(sheet_id))


def _get_or_create_sheet() -> str | None:
    """Get existing sheet ID from .env, or auto-create a new one in user's Drive."""
    sheet_id = GOOGLE_SHEET_ID
    if sheet_id:
        return sheet_id

    print("[SHEETS] No GOOGLE_SHEET_ID found. Creating a new spreadsheet in your Drive...")
    gc = _get_gspread_client()
    if not gc:
        return None

    try:
        sh = gc.create("AI Lead Scoring Engine")
        sheet_id = sh.id
        # Add a "Scored Leads" worksheet
        sh.sheet1.update_title("Scored Leads")
        print("[SHEETS] Created: https://docs.google.com/spreadsheets/d/{}".format(sheet_id))
        _save_sheet_id_to_env(sheet_id)
        return sheet_id
    except Exception as e:
        print("[SHEETS] Failed to create spreadsheet: {}".format(e))
        return None


def sync_to_sheets(leads: list[dict], spreadsheet_id: str = "") -> dict:
    """Write scored leads to Google Sheets. Auto-creates sheet if needed."""
    if not GOOGLE_OAUTH_CLIENT_FILE:
        return {"status": "skipped", "reason": "No GOOGLE_OAUTH_CLIENT_FILE configured in .env"}

    sheet_id = spreadsheet_id or _get_or_create_sheet()
    if not sheet_id:
        return {"status": "error", "reason": "Could not create or access Google Sheet."}

    gc = _get_gspread_client()
    if not gc:
        return {"status": "error", "reason": "Failed to authenticate with Google"}

    try:
        sh = gc.open_by_key(sheet_id)

        # Get or create "Scored Leads" worksheet
        try:
            ws = sh.worksheet("Scored Leads")
            ws.clear()
        except Exception:
            ws = sh.add_worksheet(title="Scored Leads", rows=len(leads) + 10, cols=len(SHEETS_COLUMNS) + 1)

        # Sort leads: Hot first, then Warm, then Cold
        tier_order = {"Hot": 0, "Warm": 1, "Cold": 2}
        sorted_leads = sorted(leads, key=lambda x: (tier_order.get(x.get("tier", "Cold"), 3), -x.get("total_score", 0)))

        # Build data grid
        rows = [SHEETS_COLUMNS]
        for lead in sorted_leads:
            row = []
            for key in SHEETS_KEYS:
                val = lead.get(key)
                if isinstance(val, list):
                    val = ", ".join(str(v) for v in val)
                elif isinstance(val, dict):
                    val = json.dumps(val)
                elif val is None:
                    val = ""
                else:
                    val = str(val)
                row.append(val)
            rows.append(row)

        ws.update(rows, value_input_option="RAW")

        # Apply basic formatting: bold header, freeze row 1
        ws.format("1:1", {"textFormat": {"bold": True}})
        ws.freeze(rows=1)

        # Color tier cells
        for i, lead in enumerate(sorted_leads, 2):
            tier = lead.get("tier", "Cold")
            color = {"Hot": (1, 0.27, 0.27), "Warm": (1, 0.66, 0), "Cold": (0.27, 0.73, 0.27)}.get(tier, (0.5, 0.5, 0.5))
            text_color = {"Hot": (1, 1, 1), "Warm": (0, 0, 0), "Cold": (1, 1, 1)}.get(tier, (1, 1, 1))
            ws.format("D{}".format(i), {
                "backgroundColor": {"red": color[0], "green": color[1], "blue": color[2]},
                "textFormat": {"bold": True, "foregroundColor": {"red": text_color[0], "green": text_color[1], "blue": text_color[2]}},
            })

        url = "https://docs.google.com/spreadsheets/d/{}".format(sheet_id)
        print("[SHEETS] Wrote {} leads to 'Scored Leads' worksheet".format(len(sorted_leads)))
        print("[SHEETS] Open your sheet: {}".format(url))
        return {"status": "ok", "rows_written": len(sorted_leads), "sheet": url}

    except Exception as e:
        return {"status": "error", "reason": str(e)[:300]}


def read_from_sheets(spreadsheet_id: str = "") -> list[dict]:
    """Feature 77: Read leads back from Google Sheets (two-way sync)."""
    sheet_id = spreadsheet_id or GOOGLE_SHEET_ID
    if not sheet_id or not GOOGLE_OAUTH_CLIENT_FILE:
        return []

    gc = _get_gspread_client()
    if not gc:
        return []

    try:
        sh = gc.open_by_key(sheet_id)
        ws = sh.worksheet("Scored Leads")
        records = ws.get_all_records()
        col_to_key = dict(zip(SHEETS_COLUMNS, SHEETS_KEYS))
        leads = []
        for record in records:
            lead = {}
            for col_name, value in record.items():
                key = col_to_key.get(col_name)
                if key:
                    lead[key] = value if value != "" else None
            if lead.get("domain"):
                leads.append(lead)
        print("[SHEETS] Read {} leads from Google Sheets".format(len(leads)))
        return leads
    except Exception as e:
        print("[SHEETS] Read error: {}".format(e))
        return []


def setup_sheets() -> dict:
    """One-command setup: authenticates user, creates sheet, saves config."""
    if not GOOGLE_OAUTH_CLIENT_FILE:
        return {"status": "error", "reason": "Set GOOGLE_OAUTH_CLIENT_FILE in .env first"}

    print("[SETUP] Authenticating with Google (browser will open)...")
    gc = _get_gspread_client()
    if not gc:
        return {"status": "error", "reason": "Authentication failed"}

    # If sheet already exists, just verify access
    if GOOGLE_SHEET_ID:
        try:
            sh = gc.open_by_key(GOOGLE_SHEET_ID)
            url = "https://docs.google.com/spreadsheets/d/{}".format(GOOGLE_SHEET_ID)
            print("[SETUP] Already configured: {}".format(sh.title))
            return {"status": "ok", "sheet_id": GOOGLE_SHEET_ID, "sheet_url": url}
        except Exception:
            print("[SETUP] Existing sheet ID invalid, creating new one...")

    # Create new sheet in user's Drive
    sheet_id = _get_or_create_sheet()
    if not sheet_id:
        return {"status": "error", "reason": "Failed to create spreadsheet"}

    url = "https://docs.google.com/spreadsheets/d/{}".format(sheet_id)
    print("[SETUP] Google Sheets is ready!")
    print("[SETUP] Sheet: {}".format(url))
    return {"status": "ok", "sheet_id": sheet_id, "sheet_url": url}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_employee_count(estimate: str) -> int | None:
    if not estimate:
        return None
    import re
    match = re.search(r'(\d+)', str(estimate).replace(",", ""))
    return int(match.group(1)) if match else None


def export_leads_json(leads: list[dict]) -> str:
    """Export leads as JSON string for API/webhook consumption."""
    export = []
    for l in leads:
        export.append({
            "company_name": l.get("company_name"),
            "domain": l.get("domain"),
            "total_score": l.get("total_score"),
            "tier": l.get("tier"),
            "rule_score": l.get("rule_score"),
            "soft_score": l.get("soft_score"),
            "confidence": l.get("confidence"),
            "industry": l.get("industry_classified") or l.get("industry"),
            "hq_country": l.get("hq_country"),
            "founding_year": l.get("founding_year"),
            "employee_estimate": l.get("employee_estimate"),
            "tech_stack": l.get("tech_stack"),
            "key_signal": l.get("key_signal"),
            "reasoning": l.get("reasoning"),
            "outreach_line": l.get("outreach_line"),
            "next_action": l.get("next_action"),
        })
    return json.dumps(export, indent=2)
