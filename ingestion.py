"""
Features 1-4, 30, 39: CSV Upload, Manual Trigger, Domain Normalizer,
Row-by-Row Loop, De-duplication, Input Validation.
"""
import csv
import re
import sys
from pathlib import Path


def validate_csv(file_path: str) -> list[str]:
    """Feature 39: Validate CSV structure and return list of issues."""
    issues = []
    path = Path(file_path)

    if not path.exists():
        issues.append(f"File not found: {file_path}")
        return issues
    if path.suffix.lower() != ".csv":
        issues.append(f"Expected .csv file, got: {path.suffix}")
        return issues
    if path.stat().st_size == 0:
        issues.append("File is empty")
        return issues
    if path.stat().st_size > 50 * 1024 * 1024:
        issues.append("File exceeds 50MB limit")
        return issues

    try:
        with open(path, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            headers = reader.fieldnames or []
            normalized_headers = {h.strip().lower() for h in headers}

            if "company_name" not in normalized_headers:
                issues.append("Missing required column: company_name")
            if "domain" not in normalized_headers:
                issues.append("Missing required column: domain")

            row_count = 0
            for i, row in enumerate(reader, 2):
                row_count += 1
                if row_count > 10000:
                    issues.append("File exceeds 10,000 row limit")
                    break
                vals = {k.strip().lower(): v.strip() for k, v in row.items()}
                if not vals.get("company_name"):
                    issues.append(f"Row {i}: empty company_name")
                if not vals.get("domain"):
                    issues.append(f"Row {i}: empty domain")

            if row_count == 0:
                issues.append("No data rows found")

    except UnicodeDecodeError:
        issues.append("File encoding error - please use UTF-8")
    except csv.Error as e:
        issues.append(f"CSV parsing error: {e}")

    return issues


def load_csv(file_path: str) -> list[dict]:
    """Feature 1: Load a CSV of company names + domains."""
    path = Path(file_path)

    # Feature 39: Input validation
    issues = validate_csv(file_path)
    if issues:
        for issue in issues:
            print(f"  [VALIDATION] {issue}")
        if any("required column" in i or "not found" in i or "empty" == i for i in issues):
            sys.exit(1)

    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = []
        for row in reader:
            normalized = {k.strip().lower(): v.strip() for k, v in row.items()}
            if normalized.get("company_name") and normalized.get("domain"):
                rows.append(normalized)

    print(f"[INGEST] Loaded {len(rows)} companies from {path.name}")
    return rows


def normalize_domain(domain: str) -> str:
    """Feature 3: Clean and standardize a domain string."""
    d = domain.strip().lower()
    d = re.sub(r'^https?://', '', d)
    d = re.sub(r'^www\.', '', d)
    d = d.split('/')[0]
    d = d.split(':')[0]
    d = d.split('?')[0]
    return d


def deduplicate(leads: list[dict]) -> list[dict]:
    """Feature 30: Detect and merge duplicate company rows."""
    seen = {}
    unique = []
    dupes = 0
    for lead in leads:
        domain = lead["domain"]
        if domain in seen:
            dupes += 1
            continue
        seen[domain] = True
        unique.append(lead)
    if dupes:
        print(f"  [DEDUP] Removed {dupes} duplicate domains")
    return unique


def prepare_leads(file_path: str) -> list[dict]:
    """Load CSV, normalize domains, deduplicate. Returns list of lead dicts."""
    rows = load_csv(file_path)
    leads = []

    for row in rows:
        domain = normalize_domain(row["domain"])
        if not domain:
            print(f"  [SKIP] Empty domain for {row.get('company_name', '?')}")
            continue
        leads.append({
            "company_name": row["company_name"],
            "domain": domain,
        })

    leads = deduplicate(leads)
    print(f"[INGEST] {len(leads)} unique leads ready for enrichment")
    return leads
