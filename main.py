"""
AI Lead Scoring Engine - Full 100-Feature Build
CLI entry point with subcommands for all operations.

Usage:
    python main.py                              # Score sample_leads.csv (default ICP)
    python main.py score leads.csv              # Score a specific CSV
    python main.py score leads.csv --icp smb    # Score against SMB ICP
    python main.py score leads.csv --all-icps   # Score against all ICPs
    python main.py rescore                      # Re-score all without re-enriching
    python main.py rescore --domain stripe.com  # Re-score one company
    python main.py dashboard                    # Start web dashboard
    python main.py export --csv                 # Export latest scores to CSV
    python main.py export --json                # Export as JSON
    python main.py report stripe.com            # Generate explainability report
    python main.py quality                      # Run bias/quality checks
    python main.py watchlist create "hot-leads" # Create a watchlist
    python main.py watchlist add "hot-leads" stripe.com,notion.so
    python main.py similar stripe.com           # Find look-alike companies
    python main.py tam                          # Estimate TAM
    python main.py icp-learn                    # Auto-learn ICP weights
    python main.py contacts stripe.com          # Find decision makers
    python main.py backup                       # Backup database
    python main.py stats                        # Show database stats
    python main.py demo                         # Export demo-safe data
    python main.py case-study stripe.com        # Generate case study
"""
import sys
import time
import json
from pathlib import Path
from datetime import datetime

from config import ICPS, OUTPUT_FILE, OUTPUT_CSV, RATE_LIMIT
from database import (
    init_db, create_run, complete_run, upsert_company, save_score,
    log_error, get_latest_scores, get_company, get_all_companies,
    record_score_history, get_db_stats, backup_db, create_watchlist,
    add_to_watchlist, get_watchlists,
)
from ingestion import prepare_leads
from enrichment import enrich_lead
from scoring import score_lead, score_lead_multi_icp
from signals import gather_signals, check_score_changes, analyze_news_sentiment
from llm_engine import run_advanced_llm
from output import write_results, export_csv
from reports import (
    build_audit_trail, generate_explainability_report, check_bias_quality,
    sanitize_for_demo, generate_case_study,
)
from notifications import notify_run_complete, notify_score_change


def run_pipeline(csv_path: str, icp_name: str = "default", all_icps: bool = False,
                 skip_signals: bool = False, skip_llm_advanced: bool = False) -> list[dict]:
    """Execute the full lead scoring pipeline end-to-end."""
    start = time.time()
    init_db()

    print("=" * 60)
    print("  AI Lead Scoring Engine")
    print("=" * 60)

    # Ingest
    leads = prepare_leads(csv_path)
    if not leads:
        print("[ERROR] No valid leads found.")
        return []

    # Create run record
    run_id = create_run(icp_name=icp_name, total_leads=len(leads), source_file=csv_path)
    print(f"[RUN] #{run_id} started with {len(leads)} leads (ICP: {icp_name})")

    scored = []
    errors = 0
    score_changes = []
    total = len(leads)

    for i, lead in enumerate(leads, 1):
        print(f"\n[{i}/{total}] Processing: {lead['company_name']} ({lead['domain']})")

        try:
            # Enrichment (Features 5-9, 16-23)
            enriched = enrich_lead(lead)

            # Save to DB
            company_id = upsert_company(enriched)

            # Advanced signals (Tier 3)
            signals = {}
            if not skip_signals:
                print(f"  [SIGNALS] Gathering: {lead['company_name']}")
                signals = gather_signals(enriched)
                enriched["event_mentions"] = signals.get("events", [])
                enriched["intent_signals"] = signals.get("intent_keywords", [])

            # Scoring (Features 10-13, 25-29)
            if all_icps:
                results = score_lead_multi_icp(enriched)
                for result in results:
                    _process_score(result, company_id, run_id, enriched, signals,
                                   skip_llm_advanced, score_changes)
                    scored.append(result)
            else:
                result = score_lead(enriched, icp_name)
                _process_score(result, company_id, run_id, enriched, signals,
                               skip_llm_advanced, score_changes)
                scored.append(result)

            tier = scored[-1]["tier"]
            score = scored[-1]["total_score"]
            conf = scored[-1].get("confidence", 0)
            print(f"  [RESULT] {lead['company_name']}: {score}/100 ({tier}) [conf: {conf:.0%}]")

            # Rate limiting between companies
            time.sleep(RATE_LIMIT["delay_between_companies"])

        except Exception as e:
            errors += 1
            print(f"  [ERROR] {lead['company_name']}: {e}")
            log_error(run_id, lead["company_name"], lead["domain"], "pipeline", str(e))
            scored.append({
                **lead,
                "total_score": 0, "tier": "Cold", "rule_score": 0, "soft_score": 0,
                "confidence": 0, "reasoning": f"Error: {e}", "key_signal": "Processing failed",
                "rule_breakdown": {}, "icp_name": icp_name,
            })

    # Complete run
    hot = sum(1 for s in scored if s.get("tier") == "Hot")
    warm = sum(1 for s in scored if s.get("tier") == "Warm")
    cold = sum(1 for s in scored if s.get("tier") == "Cold")
    complete_run(run_id, hot, warm, cold, errors)

    # Output
    output_dir = Path(csv_path).resolve().parent
    xlsx_path = write_results(scored, str(output_dir / OUTPUT_FILE))
    csv_path_out = export_csv(scored, str(output_dir / OUTPUT_CSV))

    elapsed = time.time() - start

    # Notifications (Feature 35)
    new_hot = [s for s in scored if s.get("tier") == "Hot"]
    notify_run_complete({
        "run_id": run_id, "total": len(scored), "hot": hot, "warm": warm,
        "cold": cold, "errors": errors, "duration": f"{elapsed:.1f}s", "new_hot": new_hot,
    })

    # Score change alerts (Feature 50)
    if score_changes:
        notify_score_change(score_changes)

    # Quality check summary
    quality = check_bias_quality(scored)

    print(f"\n{'=' * 60}")
    print(f"  Pipeline complete! Run #{run_id}")
    print(f"  {len(scored)} leads scored in {elapsed:.1f}s")
    print(f"  Hot: {hot}  |  Warm: {warm}  |  Cold: {cold}  |  Errors: {errors}")
    print(f"  Data quality: {quality['quality_score']}")
    print(f"  Excel: file:///{xlsx_path.replace(chr(92), '/')}")
    print(f"  CSV:   file:///{csv_path_out.replace(chr(92), '/')}")
    print(f"  Dashboard: python main.py dashboard")
    print("=" * 60)

    return scored


def _process_score(result, company_id, run_id, enriched, signals, skip_llm_advanced, score_changes):
    """Save score, run advanced LLM, check for changes."""
    icp_name = result.get("icp_name", "default")

    # Advanced LLM (Features 55-59) - only for Hot/Warm
    if not skip_llm_advanced and result.get("tier") in ("Hot", "Warm"):
        advanced = run_advanced_llm(result, signals)
        result.update(advanced)

    # Audit trail (Feature 67)
    result["sources"] = enriched.get("sources", {})

    # Save score to DB
    save_score(company_id, run_id, result)

    # Score history (Feature 49, 50)
    record_score_history(result["domain"], result["total_score"], result["tier"], icp_name)

    # Check for tier changes (Feature 50)
    changes = check_score_changes(result["domain"], result["total_score"], result["tier"])
    if changes.get("became_hot"):
        score_changes.append({
            **changes, "company_name": result["company_name"],
            "domain": result["domain"], "score": result["total_score"],
        })


def cmd_rescore(domain: str = None, icp_name: str = "default"):
    """Feature 29: Re-score without re-enriching."""
    init_db()
    from scoring import score_lead

    if domain:
        company = get_company(domain)
        if not company:
            print(f"[ERROR] Company not found: {domain}")
            return
        print(f"Re-scoring: {company['company_name']}")
        result = score_lead(company, icp_name)
        company_id = company["id"]
        run_id = create_run(icp_name, 1, "rescore")
        save_score(company_id, run_id, result)
        record_score_history(domain, result["total_score"], result["tier"], icp_name)
        complete_run(run_id, int(result["tier"] == "Hot"), int(result["tier"] == "Warm"),
                     int(result["tier"] == "Cold"), 0)
        print(f"  Result: {result['total_score']}/100 ({result['tier']})")
    else:
        companies = get_all_companies()
        print(f"Re-scoring {len(companies)} companies...")
        run_id = create_run(icp_name, len(companies), "rescore-all")
        hot = warm = cold = 0
        for c in companies:
            result = score_lead(c, icp_name)
            save_score(c["id"], run_id, result)
            record_score_history(c["domain"], result["total_score"], result["tier"], icp_name)
            if result["tier"] == "Hot": hot += 1
            elif result["tier"] == "Warm": warm += 1
            else: cold += 1
            print(f"  {c['company_name']}: {result['total_score']}/100 ({result['tier']})")
        complete_run(run_id, hot, warm, cold, 0)
        print(f"\nDone. Hot: {hot} | Warm: {warm} | Cold: {cold}")


def main():
    args = sys.argv[1:]

    if not args or args[0] == "score":
        # Default: run the scoring pipeline
        csv_path = args[1] if len(args) > 1 and not args[1].startswith("--") else str(Path(__file__).parent / "sample_leads.csv")
        icp_name = "default"
        all_icps = False
        skip_signals = False
        skip_llm_adv = False

        for i, arg in enumerate(args):
            if arg == "--icp" and i + 1 < len(args):
                icp_name = args[i + 1]
            elif arg == "--all-icps":
                all_icps = True
            elif arg == "--fast":
                skip_signals = True
                skip_llm_adv = True

        if not Path(csv_path).exists():
            print(f"[ERROR] File not found: {csv_path}")
            sys.exit(1)
        run_pipeline(csv_path, icp_name, all_icps, skip_signals, skip_llm_adv)

    elif args[0] == "rescore":
        domain = None
        icp_name = "default"
        for i, arg in enumerate(args):
            if arg == "--domain" and i + 1 < len(args):
                domain = args[i + 1]
            if arg == "--icp" and i + 1 < len(args):
                icp_name = args[i + 1]
        cmd_rescore(domain, icp_name)

    elif args[0] == "dashboard":
        from dashboard import run_dashboard
        run_dashboard()

    elif args[0] == "export":
        init_db()
        scores = get_latest_scores()
        if "--json" in args:
            from integrations import export_leads_json
            out = export_leads_json(scores)
            path = Path(__file__).parent / "scored_leads.json"
            path.write_text(out, encoding="utf-8")
            print(f"[EXPORT] JSON: file:///{str(path.resolve()).replace(chr(92), '/')}")
        else:
            export_csv(scores)

    elif args[0] == "report":
        init_db()
        domain = args[1] if len(args) > 1 else None
        if not domain:
            print("Usage: python main.py report <domain>")
            return
        scores = get_latest_scores()
        score = next((s for s in scores if s.get("domain") == domain), None)
        if not score:
            print(f"No scores found for {domain}")
            return
        report = generate_explainability_report(score)
        path = Path(__file__).parent / f"report_{domain.replace('.', '_')}.txt"
        path.write_text(report, encoding="utf-8")
        print(report)
        print(f"\nSaved to: file:///{str(path.resolve()).replace(chr(92), '/')}")

    elif args[0] == "quality":
        init_db()
        scores = get_latest_scores()
        quality = check_bias_quality(scores)
        print(json.dumps(quality, indent=2))

    elif args[0] == "watchlist":
        init_db()
        if len(args) < 2:
            for wl in get_watchlists():
                print(f"  {wl['name']}: {len(wl['domains'])} domains")
            return
        if args[1] == "create" and len(args) > 2:
            name = args[2]
            desc = args[3] if len(args) > 3 else ""
            create_watchlist(name, desc)
            print(f"Created watchlist: {name}")
        elif args[1] == "add" and len(args) > 3:
            name = args[2]
            domains = args[3].split(",")
            add_to_watchlist(name, domains)
            print(f"Added {len(domains)} domains to {name}")

    elif args[0] == "similar":
        init_db()
        domain = args[1] if len(args) > 1 else None
        if not domain:
            print("Usage: python main.py similar <domain>")
            return
        from intelligence import find_look_alikes
        results = find_look_alikes(domain)
        if results:
            print(f"\nCompanies similar to {domain}:")
            for r in results:
                print(f"  {r['company_name']} ({r['domain']}) - similarity: {r['similarity_score']}")
                if r.get("shared_tech"):
                    print(f"    Shared tech: {', '.join(r['shared_tech'])}")
        else:
            print("No similar companies found. Score more leads first.")

    elif args[0] == "tam":
        init_db()
        from intelligence import estimate_tam
        icp_name = args[1] if len(args) > 1 else "default"
        result = estimate_tam(icp_name)
        print(json.dumps(result, indent=2))

    elif args[0] == "icp-learn":
        init_db()
        from intelligence import auto_learn_icp
        icp_name = args[1] if len(args) > 1 else "default"
        result = auto_learn_icp(icp_name)
        print(json.dumps(result, indent=2))

    elif args[0] == "contacts":
        init_db()
        domain = args[1] if len(args) > 1 else None
        if not domain:
            print("Usage: python main.py contacts <domain>")
            return
        company = get_company(domain)
        if not company:
            print(f"Company not found: {domain}. Score it first.")
            return
        from contacts import find_decision_makers, infer_org_chart
        print(f"\nDecision makers for {company['company_name']}:")
        makers = find_decision_makers(
            company["company_name"],
            company.get("industry_classified") or company.get("industry") or "",
            company.get("employee_estimate") or "",
        )
        for m in makers:
            print(f"  {m['title']} ({m['role_category']})")

        print(f"\nOrg chart:")
        org = infer_org_chart(
            company["company_name"],
            company.get("industry_classified") or "",
            company.get("employee_estimate") or "",
        )
        print(json.dumps(org, indent=2))

    elif args[0] == "sheets":
        init_db()
        from integrations import sync_to_sheets, read_from_sheets
        if len(args) > 1 and args[1] == "read":
            leads = read_from_sheets()
            print(f"Read {len(leads)} leads from Google Sheets")
            for l in leads[:5]:
                print(f"  {l.get('company_name')} ({l.get('domain')}): {l.get('total_score')}")
        else:
            scores = get_latest_scores()
            if not scores:
                print("No scores to sync. Run scoring first.")
                return
            result = sync_to_sheets(scores)
            print(json.dumps(result, indent=2))

    elif args[0] == "setup-sheets":
        from integrations import setup_sheets
        result = setup_sheets()
        print(json.dumps(result, indent=2))

    elif args[0] == "backup":
        init_db()
        path = backup_db()
        print(f"Backup saved to: {path}")

    elif args[0] == "stats":
        init_db()
        stats = get_db_stats()
        print(json.dumps(stats, indent=2))

    elif args[0] == "demo":
        init_db()
        scores = get_latest_scores()
        demo = sanitize_for_demo(scores)
        path = Path(__file__).parent / "demo_data.json"
        path.write_text(json.dumps(demo, indent=2), encoding="utf-8")
        print(f"Demo data exported to: file:///{str(path.resolve()).replace(chr(92), '/')}")

    elif args[0] == "case-study":
        init_db()
        domain = args[1] if len(args) > 1 else None
        if not domain:
            print("Usage: python main.py case-study <domain>")
            return
        scores = get_latest_scores()
        score = next((s for s in scores if s.get("domain") == domain), None)
        if not score:
            print(f"No scores found for {domain}")
            return
        study = generate_case_study(score)
        path = Path(__file__).parent / f"docs/case_study_{domain.replace('.', '_')}.md"
        path.parent.mkdir(exist_ok=True)
        path.write_text(study, encoding="utf-8")
        print(study)
        print(f"\nSaved to: file:///{str(path.resolve()).replace(chr(92), '/')}")

    else:
        print(__doc__)


if __name__ == "__main__":
    main()
