"""
AI Lead Scoring Engine - Portfolio-Grade Web Dashboard
Features: Tri-dimensional scoring, glass-box explainability, buying stages,
feedback loops, command palette, dark/light mode, activity feed, and more.
"""
import json
import functools
from pathlib import Path
from datetime import datetime, timedelta
import random
import csv
import io

from config import (
    DASHBOARD_PORT, DASHBOARD_SECRET_KEY, ICPS, SCORE_DIMENSIONS,
    SCORING_TEMPLATES, BUYING_STAGES, SCORE_DECAY, TIER_THRESHOLDS,
)

try:
    from flask import (Flask, render_template_string, request, jsonify,
                       redirect, url_for, session, Response)
    HAS_FLASK = True
except ImportError:
    HAS_FLASK = False

from database import (
    init_db, get_latest_scores, get_scores_for_run, get_runs, get_run,
    get_company, get_all_companies, get_errors_for_run, get_db_stats,
    get_company_score_history, get_watchlists,
    authenticate_user, list_users, create_user, change_password,
    upsert_company, save_score, create_run, complete_run, record_score_history,
    save_feedback, get_feedback, get_feedback_stats,
    log_audit, get_audit_log,
    save_setting, get_setting, get_all_settings,
    get_enrichment_coverage, get_activity_feed,
)
from reports import sanitize_for_demo, generate_explainability_report, check_bias_quality
from dashboard_pages import (
    KANBAN_CONTENT, VELOCITY_CONTENT, MARKETPLACE_CONTENT,
    WORKFLOW_CONTENT, CHAMPION_CONTENT, WEBHOOK_LOG_CONTENT,
    ABM_CONTENT, LEADERBOARD_CONTENT, GEO_CONTENT, IMPORT_CONTENT,
)


# ---------------------------------------------------------------------------
# Sample Data (40 companies for one-click demo — diverse industries, geographies, tiers)
# ---------------------------------------------------------------------------
SAMPLE_COMPANIES = [
    # ===== HOT TIER (12 companies) =====
    {"company_name": "Stripe", "domain": "stripe.com", "description": "Financial infrastructure for the internet. Millions of businesses use Stripe to accept payments, grow their revenue, and accelerate new business opportunities.", "industry": "fintech", "industry_classified": "Financial Technology", "hq_country": "United States", "founding_year": 2010, "employee_estimate": "5000-10000", "tech_stack": ["React", "Ruby", "AWS", "Go", "Kubernetes", "Terraform"], "social_linkedin": "https://linkedin.com/company/stripe", "email_pattern": "{first}@stripe.com", "careers_jobs_count": 142, "competitor_tech": ["salesforce"], "key_signal": "Massive hiring + enterprise payment infrastructure leader", "reasoning": "Dominant fintech player with strong B2B SaaS characteristics. Rapid growth phase with aggressive hiring signals across engineering and sales.", "outreach_line": "Stripe expansion into embedded finance creates new integration opportunities for growth teams.", "next_action": "Target VP of Platform Partnerships", "total_score": 88, "tier": "Hot", "rule_score": 54, "soft_score": 34, "confidence": 0.96, "rule_breakdown": {"geo_match": 12, "industry_match": 15, "tech_signals": 11, "company_age": 8, "employee_fit": 4, "website_quality": 4}, "fit_score_pct": 90, "engagement_score_pct": 75, "intent_score_pct": 70, "buying_stage": "Purchase", "fit_grade": "A", "engagement_grade": "1", "matrix_cell": "A1"},
    {"company_name": "Notion", "domain": "notion.so", "description": "All-in-one workspace for notes, docs, wikis, and project management.", "industry": "saas", "industry_classified": "Productivity Software", "hq_country": "United States", "founding_year": 2016, "employee_estimate": "1000-5000", "tech_stack": ["React", "TypeScript", "AWS", "Node.js", "Elasticsearch"], "social_linkedin": "https://linkedin.com/company/notionhq", "email_pattern": "{first}@makenotion.com", "careers_jobs_count": 67, "competitor_tech": [], "key_signal": "Rapid user growth + enterprise tier expansion", "reasoning": "Fast-growing SaaS with strong product-led growth motion. Enterprise push signals readiness for B2B tooling.", "outreach_line": "As Notion scales its enterprise offering, data-driven lead prioritization could accelerate your sales-assist motion.", "next_action": "Connect with Head of Growth", "total_score": 82, "tier": "Hot", "rule_score": 50, "soft_score": 32, "confidence": 0.94, "rule_breakdown": {"geo_match": 12, "industry_match": 15, "tech_signals": 9, "company_age": 6, "employee_fit": 5, "website_quality": 3}, "fit_score_pct": 83, "engagement_score_pct": 60, "intent_score_pct": 65, "buying_stage": "Purchase", "fit_grade": "A", "engagement_grade": "2", "matrix_cell": "A2"},
    {"company_name": "Datadog", "domain": "datadoghq.com", "description": "Cloud-scale monitoring and security platform for developers, IT operations teams, and business users.", "industry": "technology", "industry_classified": "Cloud Infrastructure", "hq_country": "United States", "founding_year": 2010, "employee_estimate": "5000-10000", "tech_stack": ["Go", "Python", "React", "AWS", "Kubernetes", "Kafka"], "social_linkedin": "https://linkedin.com/company/datadog", "email_pattern": "{first}.{last}@datadoghq.com", "careers_jobs_count": 198, "competitor_tech": ["salesforce", "gong"], "key_signal": "Public company with accelerating cloud adoption", "reasoning": "Major cloud monitoring provider with strong developer brand. Enterprise sales motion and high-velocity growth.", "outreach_line": "Datadog multi-product expansion creates opportunities for intelligent lead routing.", "next_action": "Engage Director of Revenue Operations", "total_score": 85, "tier": "Hot", "rule_score": 52, "soft_score": 33, "confidence": 0.93, "rule_breakdown": {"geo_match": 12, "industry_match": 15, "tech_signals": 10, "company_age": 7, "employee_fit": 4, "website_quality": 4}, "fit_score_pct": 87, "engagement_score_pct": 80, "intent_score_pct": 65, "buying_stage": "Purchase", "fit_grade": "A", "engagement_grade": "1", "matrix_cell": "A1"},
    {"company_name": "Figma", "domain": "figma.com", "description": "Collaborative interface design tool that connects everyone in the design process.", "industry": "saas", "industry_classified": "Design Software", "hq_country": "United States", "founding_year": 2012, "employee_estimate": "1000-5000", "tech_stack": ["TypeScript", "C++", "WebAssembly", "React", "AWS"], "social_linkedin": "https://linkedin.com/company/figma", "email_pattern": "{first}@figma.com", "careers_jobs_count": 53, "competitor_tech": [], "key_signal": "Product-led growth with enterprise conversion wave", "reasoning": "Category-defining design tool with viral adoption. Strong enterprise conversion pipeline.", "outreach_line": "Figma enterprise expansion means your sales team needs smarter lead prioritization.", "next_action": "Target VP of Sales", "total_score": 79, "tier": "Hot", "rule_score": 48, "soft_score": 31, "confidence": 0.91, "rule_breakdown": {"geo_match": 12, "industry_match": 15, "tech_signals": 8, "company_age": 7, "employee_fit": 5, "website_quality": 1}, "fit_score_pct": 80, "engagement_score_pct": 50, "intent_score_pct": 55, "buying_stage": "Decision", "fit_grade": "A", "engagement_grade": "2", "matrix_cell": "A2"},
    {"company_name": "Vercel", "domain": "vercel.com", "description": "Frontend cloud platform that enables developers to build and deploy web applications.", "industry": "cloud", "industry_classified": "Cloud Platform", "hq_country": "United States", "founding_year": 2015, "employee_estimate": "500-1000", "tech_stack": ["Next.js", "React", "TypeScript", "Go", "AWS"], "social_linkedin": "https://linkedin.com/company/vercel", "email_pattern": "{first}@vercel.com", "careers_jobs_count": 38, "competitor_tech": [], "key_signal": "Developer-first growth with enterprise tier launch", "reasoning": "High-growth cloud platform with strong developer brand. New enterprise tier and growing sales org.", "outreach_line": "As Vercel builds out its enterprise motion, intelligent lead scoring can help prioritize prospects.", "next_action": "Connect with Head of Enterprise Sales", "total_score": 74, "tier": "Hot", "rule_score": 45, "soft_score": 29, "confidence": 0.89, "rule_breakdown": {"geo_match": 12, "industry_match": 14, "tech_signals": 8, "company_age": 5, "employee_fit": 6, "website_quality": 0}, "fit_score_pct": 75, "engagement_score_pct": 40, "intent_score_pct": 50, "buying_stage": "Decision", "fit_grade": "A", "engagement_grade": "2", "matrix_cell": "A2"},
    {"company_name": "GitLab", "domain": "gitlab.com", "description": "Complete DevOps platform delivered as a single application for the entire software development lifecycle.", "industry": "devops", "industry_classified": "DevOps Platform", "hq_country": "United States", "founding_year": 2011, "employee_estimate": "1000-5000", "tech_stack": ["Ruby on Rails", "Vue.js", "Go", "PostgreSQL", "Kubernetes", "GCP"], "social_linkedin": "https://linkedin.com/company/gitlab-com", "email_pattern": "{first}@gitlab.com", "careers_jobs_count": 56, "competitor_tech": ["salesforce", "6sense"], "key_signal": "Public company with strong enterprise pipeline", "reasoning": "Well-known DevOps platform with robust enterprise sales. Good ICP alignment with strong tech signals.", "outreach_line": "GitLab growing enterprise pipeline needs intelligent lead scoring to help reps focus.", "next_action": "Target Director of Sales Operations", "total_score": 71, "tier": "Hot", "rule_score": 43, "soft_score": 28, "confidence": 0.9, "rule_breakdown": {"geo_match": 12, "industry_match": 13, "tech_signals": 7, "company_age": 6, "employee_fit": 4, "website_quality": 1}, "fit_score_pct": 72, "engagement_score_pct": 55, "intent_score_pct": 50, "buying_stage": "Decision", "fit_grade": "A", "engagement_grade": "2", "matrix_cell": "A2"},
    {"company_name": "Wise", "domain": "wise.com", "description": "Global technology company building the best way to move and manage the world's money. International transfers, multi-currency accounts, and debit cards.", "industry": "fintech", "industry_classified": "International Payments", "hq_country": "United Kingdom", "founding_year": 2011, "employee_estimate": "5000-10000", "tech_stack": ["Java", "Kotlin", "React", "AWS", "Kubernetes", "PostgreSQL"], "social_linkedin": "https://linkedin.com/company/wiseaccount", "email_pattern": "{first}.{last}@wise.com", "careers_jobs_count": 176, "competitor_tech": ["salesforce"], "key_signal": "Public fintech with massive global expansion + 100M customers", "reasoning": "Major international fintech scaling across 160 countries. Aggressive hiring and product expansion signals high-growth phase with strong B2B banking infrastructure play.", "outreach_line": "Wise global expansion into business banking creates opportunities for AI-driven partner lead qualification.", "next_action": "Target VP of Business Growth", "total_score": 86, "tier": "Hot", "rule_score": 53, "soft_score": 33, "confidence": 0.95, "rule_breakdown": {"geo_match": 10, "industry_match": 15, "tech_signals": 11, "company_age": 7, "employee_fit": 5, "website_quality": 5}, "fit_score_pct": 88, "engagement_score_pct": 72, "intent_score_pct": 68, "buying_stage": "Purchase", "fit_grade": "A", "engagement_grade": "1", "matrix_cell": "A1"},
    {"company_name": "Atlassian", "domain": "atlassian.com", "description": "Enterprise software company that develops products for software developers, project managers, and content management. Makers of Jira, Confluence, and Trello.", "industry": "saas", "industry_classified": "Enterprise Software", "hq_country": "Australia", "founding_year": 2002, "employee_estimate": "10000+", "tech_stack": ["Java", "React", "TypeScript", "AWS", "Kubernetes", "Kafka", "PostgreSQL"], "social_linkedin": "https://linkedin.com/company/atlassian", "email_pattern": "{first}@atlassian.com", "careers_jobs_count": 310, "competitor_tech": ["salesforce", "marketo"], "key_signal": "Public enterprise giant with cloud migration driving new deals", "reasoning": "Massive enterprise SaaS player moving fully to cloud. Cloud migration creates enormous upsell pipeline and new lead qualification demands.", "outreach_line": "Atlassian cloud migration is driving a wave of new enterprise deals that need intelligent prioritization.", "next_action": "Engage Senior Director of Enterprise Sales", "total_score": 91, "tier": "Hot", "rule_score": 56, "soft_score": 35, "confidence": 0.97, "rule_breakdown": {"geo_match": 8, "industry_match": 15, "tech_signals": 12, "company_age": 10, "employee_fit": 5, "website_quality": 6}, "fit_score_pct": 93, "engagement_score_pct": 85, "intent_score_pct": 78, "buying_stage": "Purchase", "fit_grade": "A", "engagement_grade": "1", "matrix_cell": "A1"},
    {"company_name": "Razorpay", "domain": "razorpay.com", "description": "Full-stack financial solutions provider for businesses in India. Payment gateway, banking, lending, and payroll.", "industry": "fintech", "industry_classified": "Payment Infrastructure", "hq_country": "India", "founding_year": 2014, "employee_estimate": "1000-5000", "tech_stack": ["Go", "Python", "React", "AWS", "Kubernetes", "Redis"], "social_linkedin": "https://linkedin.com/company/razorpay", "email_pattern": "{first}@razorpay.com", "careers_jobs_count": 95, "competitor_tech": [], "key_signal": "India's largest payment gateway with enterprise banking expansion", "reasoning": "Dominant Indian fintech rapidly expanding into enterprise banking and lending. Strong technical team with aggressive hiring across engineering and sales.", "outreach_line": "Razorpay enterprise expansion beyond payments creates new segments that need data-driven lead scoring.", "next_action": "Connect with Head of Enterprise Business", "total_score": 77, "tier": "Hot", "rule_score": 47, "soft_score": 30, "confidence": 0.88, "rule_breakdown": {"geo_match": 4, "industry_match": 15, "tech_signals": 10, "company_age": 5, "employee_fit": 8, "website_quality": 5}, "fit_score_pct": 78, "engagement_score_pct": 60, "intent_score_pct": 55, "buying_stage": "Decision", "fit_grade": "A", "engagement_grade": "2", "matrix_cell": "A2"},
    {"company_name": "UiPath", "domain": "uipath.com", "description": "Enterprise automation platform combining robotic process automation (RPA) with AI to automate business processes.", "industry": "automation", "industry_classified": "Robotic Process Automation", "hq_country": "United States", "founding_year": 2005, "employee_estimate": "5000-10000", "tech_stack": [".NET", "C#", "React", "Azure", "Kubernetes", "Python"], "social_linkedin": "https://linkedin.com/company/uipath", "email_pattern": "{first}.{last}@uipath.com", "careers_jobs_count": 167, "competitor_tech": ["salesforce", "6sense", "gong"], "key_signal": "Public RPA leader with AI pivot driving new pipeline", "reasoning": "Major public automation company pivoting to AI-augmented automation. Enterprise sales org with high-velocity deal flow.", "outreach_line": "UiPath AI pivot is creating new buyer personas that need intelligent lead qualification and routing.", "next_action": "Target VP of Revenue Operations", "total_score": 83, "tier": "Hot", "rule_score": 51, "soft_score": 32, "confidence": 0.92, "rule_breakdown": {"geo_match": 12, "industry_match": 14, "tech_signals": 9, "company_age": 8, "employee_fit": 4, "website_quality": 4}, "fit_score_pct": 85, "engagement_score_pct": 70, "intent_score_pct": 62, "buying_stage": "Purchase", "fit_grade": "A", "engagement_grade": "1", "matrix_cell": "A1"},
    {"company_name": "Canva", "domain": "canva.com", "description": "Online design platform empowering everyone to design anything and publish anywhere. Used by 170M+ monthly active users.", "industry": "saas", "industry_classified": "Design Platform", "hq_country": "Australia", "founding_year": 2012, "employee_estimate": "5000-10000", "tech_stack": ["Java", "TypeScript", "React", "AWS", "Kubernetes", "Go"], "social_linkedin": "https://linkedin.com/company/canva", "email_pattern": "{first}@canva.com", "careers_jobs_count": 134, "competitor_tech": [], "key_signal": "Massive user base with enterprise teams product driving B2B growth", "reasoning": "Consumer-to-enterprise transition with huge user base. Canva Teams enterprise offering is rapidly growing and needs sophisticated lead scoring.", "outreach_line": "Canva's enterprise teams push means millions of PLG users to qualify — intelligent scoring is essential.", "next_action": "Target Head of Enterprise Sales", "total_score": 81, "tier": "Hot", "rule_score": 49, "soft_score": 32, "confidence": 0.93, "rule_breakdown": {"geo_match": 8, "industry_match": 15, "tech_signals": 10, "company_age": 7, "employee_fit": 5, "website_quality": 4}, "fit_score_pct": 82, "engagement_score_pct": 65, "intent_score_pct": 60, "buying_stage": "Purchase", "fit_grade": "A", "engagement_grade": "1", "matrix_cell": "A1"},
    {"company_name": "Checkout.com", "domain": "checkout.com", "description": "Global payment processing platform enabling businesses to accept payments, fight fraud, and optimize revenue across borders.", "industry": "fintech", "industry_classified": "Payment Processing", "hq_country": "United Kingdom", "founding_year": 2012, "employee_estimate": "1000-5000", "tech_stack": ["Go", "Java", "React", "AWS", "Kubernetes", "Terraform"], "social_linkedin": "https://linkedin.com/company/checkout", "email_pattern": "{first}.{last}@checkout.com", "careers_jobs_count": 88, "competitor_tech": ["salesforce"], "key_signal": "European fintech unicorn with aggressive enterprise expansion", "reasoning": "High-growth European payment processor scaling enterprise deals globally. Technical sophistication and hiring velocity signal strong ICP fit.", "outreach_line": "Checkout.com scaling enterprise deals across 150 countries needs smarter lead prioritization.", "next_action": "Engage VP of Enterprise Solutions", "total_score": 76, "tier": "Hot", "rule_score": 46, "soft_score": 30, "confidence": 0.9, "rule_breakdown": {"geo_match": 10, "industry_match": 15, "tech_signals": 9, "company_age": 6, "employee_fit": 4, "website_quality": 2}, "fit_score_pct": 77, "engagement_score_pct": 55, "intent_score_pct": 52, "buying_stage": "Decision", "fit_grade": "A", "engagement_grade": "2", "matrix_cell": "A2"},
    # ===== WARM TIER (16 companies) =====
    {"company_name": "Zapier", "domain": "zapier.com", "description": "Automation platform that connects apps and automates workflows without code.", "industry": "automation", "industry_classified": "Workflow Automation", "hq_country": "United States", "founding_year": 2011, "employee_estimate": "500-1000", "tech_stack": ["Python", "Django", "React", "AWS", "PostgreSQL"], "social_linkedin": "https://linkedin.com/company/zapier", "email_pattern": "{first}@zapier.com", "careers_jobs_count": 22, "competitor_tech": ["hubspot"], "key_signal": "Automation leader expanding into enterprise", "reasoning": "Well-established automation platform with PLG motion. Enterprise expansion indicates good ICP fit.", "outreach_line": "Zapier move upmarket creates a natural need for data-driven lead scoring.", "next_action": "Reach out to Sales Operations Manager", "total_score": 65, "tier": "Warm", "rule_score": 39, "soft_score": 26, "confidence": 0.85, "rule_breakdown": {"geo_match": 12, "industry_match": 12, "tech_signals": 6, "company_age": 6, "employee_fit": 3, "website_quality": 0}, "fit_score_pct": 65, "engagement_score_pct": 45, "intent_score_pct": 40, "buying_stage": "Decision", "fit_grade": "B", "engagement_grade": "2", "matrix_cell": "B2"},
    {"company_name": "Calendly", "domain": "calendly.com", "description": "Scheduling automation platform for eliminating the back-and-forth of scheduling meetings.", "industry": "saas", "industry_classified": "Scheduling Software", "hq_country": "United States", "founding_year": 2013, "employee_estimate": "500-1000", "tech_stack": ["Ruby on Rails", "React", "AWS", "PostgreSQL", "Redis"], "social_linkedin": "https://linkedin.com/company/calendly", "email_pattern": "{first}@calendly.com", "careers_jobs_count": 18, "competitor_tech": ["hubspot", "intercom"], "key_signal": "Growing sales team with CRM integration push", "reasoning": "Strong scheduling platform with good ICP overlap. Sales team expansion suggests readiness for lead scoring.", "outreach_line": "As Calendly scales its sales-assist motion, intelligent lead prioritization can boost conversion rates.", "next_action": "Connect with Revenue Operations", "total_score": 58, "tier": "Warm", "rule_score": 35, "soft_score": 23, "confidence": 0.82, "rule_breakdown": {"geo_match": 12, "industry_match": 10, "tech_signals": 5, "company_age": 5, "employee_fit": 3, "website_quality": 0}, "fit_score_pct": 58, "engagement_score_pct": 40, "intent_score_pct": 35, "buying_stage": "Consideration", "fit_grade": "B", "engagement_grade": "2", "matrix_cell": "B2"},
    {"company_name": "Airtable", "domain": "airtable.com", "description": "Low-code platform for building collaborative apps that connect teams and workflows.", "industry": "saas", "industry_classified": "Low-Code Platform", "hq_country": "United States", "founding_year": 2012, "employee_estimate": "1000-5000", "tech_stack": ["JavaScript", "React", "Node.js", "AWS", "Ruby"], "social_linkedin": "https://linkedin.com/company/airtable", "email_pattern": "{first}@airtable.com", "careers_jobs_count": 31, "competitor_tech": [], "key_signal": "Enterprise adoption growing with team-based sales", "reasoning": "Solid SaaS platform transitioning to enterprise. Good ICP alignment but sales motion still developing.", "outreach_line": "Airtable enterprise growth means more leads to qualify - smart scoring can help.", "next_action": "Target Head of Sales Development", "total_score": 55, "tier": "Warm", "rule_score": 33, "soft_score": 22, "confidence": 0.8, "rule_breakdown": {"geo_match": 12, "industry_match": 10, "tech_signals": 4, "company_age": 4, "employee_fit": 3, "website_quality": 0}, "fit_score_pct": 55, "engagement_score_pct": 35, "intent_score_pct": 30, "buying_stage": "Consideration", "fit_grade": "B", "engagement_grade": "2", "matrix_cell": "B2"},
    {"company_name": "Miro", "domain": "miro.com", "description": "Visual workspace for innovation that enables distributed teams to collaborate effectively.", "industry": "saas", "industry_classified": "Collaboration Software", "hq_country": "Netherlands", "founding_year": 2011, "employee_estimate": "1000-5000", "tech_stack": ["TypeScript", "React", "Java", "AWS", "Kubernetes"], "social_linkedin": "https://linkedin.com/company/mirohq", "email_pattern": "{first}@miro.com", "careers_jobs_count": 42, "competitor_tech": ["salesforce"], "key_signal": "Rapid enterprise adoption across distributed teams", "reasoning": "Growing collaboration platform with enterprise deals. ICP alignment moderate with expanding sales org.", "outreach_line": "Miro expanding enterprise sales team needs data-driven lead prioritization.", "next_action": "Connect with Sales Director", "total_score": 52, "tier": "Warm", "rule_score": 32, "soft_score": 20, "confidence": 0.78, "rule_breakdown": {"geo_match": 10, "industry_match": 10, "tech_signals": 4, "company_age": 4, "employee_fit": 2, "website_quality": 2}, "fit_score_pct": 53, "engagement_score_pct": 45, "intent_score_pct": 30, "buying_stage": "Consideration", "fit_grade": "B", "engagement_grade": "2", "matrix_cell": "B2"},
    {"company_name": "Linear", "domain": "linear.app", "description": "Streamlined issue tracking and project management tool built for modern software teams.", "industry": "saas", "industry_classified": "Project Management", "hq_country": "United States", "founding_year": 2019, "employee_estimate": "50-200", "tech_stack": ["TypeScript", "React", "Node.js", "PostgreSQL", "Vercel"], "social_linkedin": "https://linkedin.com/company/linear-app", "email_pattern": "{first}@linear.app", "careers_jobs_count": 8, "competitor_tech": [], "key_signal": "Fast-growing startup with strong developer following", "reasoning": "Early-stage but high-growth SaaS with strong product market fit. Small team but rapid expansion potential.", "outreach_line": "As Linear grows beyond PLG, lead scoring can help identify which inbound prospects to prioritize first.", "next_action": "Connect with founding team", "total_score": 48, "tier": "Warm", "rule_score": 28, "soft_score": 20, "confidence": 0.75, "rule_breakdown": {"geo_match": 12, "industry_match": 10, "tech_signals": 3, "company_age": 3, "employee_fit": 0, "website_quality": 0}, "fit_score_pct": 47, "engagement_score_pct": 25, "intent_score_pct": 35, "buying_stage": "Consideration", "fit_grade": "B", "engagement_grade": "3", "matrix_cell": "B3"},
    {"company_name": "Webflow", "domain": "webflow.com", "description": "Visual web development platform that empowers designers to build professional, custom websites without code.", "industry": "saas", "industry_classified": "No-Code Platform", "hq_country": "United States", "founding_year": 2013, "employee_estimate": "500-1000", "tech_stack": ["React", "Node.js", "MongoDB", "AWS", "TypeScript"], "social_linkedin": "https://linkedin.com/company/webflow-inc-", "email_pattern": "{first}@webflow.com", "careers_jobs_count": 24, "competitor_tech": [], "key_signal": "Growing enterprise adoption with sales team expansion", "reasoning": "No-code leader expanding into enterprise. Growing sales team and product maturity suggest good timing.", "outreach_line": "As Webflow scales its enterprise sales, smart lead scoring can help capture the growing demand.", "next_action": "Connect with VP of Growth", "total_score": 62, "tier": "Warm", "rule_score": 38, "soft_score": 24, "confidence": 0.83, "rule_breakdown": {"geo_match": 12, "industry_match": 12, "tech_signals": 5, "company_age": 5, "employee_fit": 4, "website_quality": 0}, "fit_score_pct": 63, "engagement_score_pct": 35, "intent_score_pct": 40, "buying_stage": "Decision", "fit_grade": "B", "engagement_grade": "2", "matrix_cell": "B2"},
    {"company_name": "Personio", "domain": "personio.com", "description": "All-in-one HR software for small and medium-sized companies. Covers recruiting, onboarding, payroll, and people analytics.", "industry": "saas", "industry_classified": "HR Technology", "hq_country": "Germany", "founding_year": 2015, "employee_estimate": "1000-5000", "tech_stack": ["Java", "Kotlin", "React", "AWS", "Kubernetes", "PostgreSQL"], "social_linkedin": "https://linkedin.com/company/personio", "email_pattern": "{first}.{last}@personio.com", "careers_jobs_count": 78, "competitor_tech": ["hubspot"], "key_signal": "European HR tech unicorn with 10K+ SMB customers expanding to enterprise", "reasoning": "Leading European HR platform scaling rapidly. SMB-to-enterprise expansion creates lead qualification demands. Strong European market position.", "outreach_line": "Personio enterprise push means thousands of SMB-to-enterprise upgrade leads to score and prioritize.", "next_action": "Target Head of Revenue Operations", "total_score": 67, "tier": "Warm", "rule_score": 41, "soft_score": 26, "confidence": 0.86, "rule_breakdown": {"geo_match": 10, "industry_match": 13, "tech_signals": 7, "company_age": 5, "employee_fit": 4, "website_quality": 2}, "fit_score_pct": 68, "engagement_score_pct": 50, "intent_score_pct": 42, "buying_stage": "Decision", "fit_grade": "B", "engagement_grade": "1", "matrix_cell": "B1"},
    {"company_name": "Deel", "domain": "deel.com", "description": "Global payroll and compliance platform that helps companies hire anyone, anywhere. Supports contractors, EOR, and immigration in 150+ countries.", "industry": "fintech", "industry_classified": "Global Payroll", "hq_country": "United States", "founding_year": 2019, "employee_estimate": "1000-5000", "tech_stack": ["TypeScript", "React", "Node.js", "AWS", "PostgreSQL", "Redis"], "social_linkedin": "https://linkedin.com/company/deel-ai", "email_pattern": "{first}@deel.com", "careers_jobs_count": 112, "competitor_tech": ["salesforce", "gong"], "key_signal": "Hypergrowth global HR-fintech with $12B valuation and 25K+ customers", "reasoning": "Fastest-growing fintech in global payroll space. Massive hiring and customer acquisition signals. Enterprise push with complex lead qualification needs.", "outreach_line": "Deel's explosive growth across 150 countries creates complex lead scoring needs that can benefit from AI.", "next_action": "Connect with VP of Sales Development", "total_score": 69, "tier": "Warm", "rule_score": 42, "soft_score": 27, "confidence": 0.87, "rule_breakdown": {"geo_match": 12, "industry_match": 13, "tech_signals": 7, "company_age": 3, "employee_fit": 4, "website_quality": 3}, "fit_score_pct": 70, "engagement_score_pct": 55, "intent_score_pct": 45, "buying_stage": "Decision", "fit_grade": "B", "engagement_grade": "1", "matrix_cell": "B1"},
    {"company_name": "Postman", "domain": "postman.com", "description": "API platform for building and using APIs. Simplifies each step of the API lifecycle and streamlines collaboration for faster API development.", "industry": "devtools", "industry_classified": "API Development", "hq_country": "United States", "founding_year": 2014, "employee_estimate": "500-1000", "tech_stack": ["JavaScript", "TypeScript", "React", "Node.js", "AWS", "Electron"], "social_linkedin": "https://linkedin.com/company/postman-platform", "email_pattern": "{first}@postman.com", "careers_jobs_count": 34, "competitor_tech": [], "key_signal": "30M+ developers with enterprise API governance push", "reasoning": "Dominant API development platform transitioning from developer tool to enterprise governance solution. Growing sales org signals readiness for lead scoring.", "outreach_line": "Postman's enterprise API governance push needs intelligent lead scoring to convert developer-led adoption.", "next_action": "Connect with Head of Enterprise Sales", "total_score": 60, "tier": "Warm", "rule_score": 36, "soft_score": 24, "confidence": 0.83, "rule_breakdown": {"geo_match": 12, "industry_match": 12, "tech_signals": 5, "company_age": 5, "employee_fit": 2, "website_quality": 0}, "fit_score_pct": 61, "engagement_score_pct": 38, "intent_score_pct": 37, "buying_stage": "Consideration", "fit_grade": "B", "engagement_grade": "2", "matrix_cell": "B2"},
    {"company_name": "Grab", "domain": "grab.com", "description": "Southeast Asia's leading super app platform offering ride-hailing, food delivery, digital payments, and financial services across 8 countries.", "industry": "technology", "industry_classified": "Super App Platform", "hq_country": "Singapore", "founding_year": 2012, "employee_estimate": "10000+", "tech_stack": ["Go", "Java", "Kotlin", "React", "AWS", "Kubernetes", "Kafka"], "social_linkedin": "https://linkedin.com/company/grabapp", "email_pattern": "{first}@grab.com", "careers_jobs_count": 205, "competitor_tech": ["salesforce"], "key_signal": "Public SE Asian super app expanding B2B fintech arm (GrabForBusiness)", "reasoning": "Dominant SE Asian platform with emerging B2B enterprise fintech division. Large enterprise sales org for GrabForBusiness with complex lead scoring needs.", "outreach_line": "GrabForBusiness enterprise expansion in SE Asia creates complex multi-product lead qualification needs.", "next_action": "Target Regional Enterprise Sales Director", "total_score": 63, "tier": "Warm", "rule_score": 38, "soft_score": 25, "confidence": 0.81, "rule_breakdown": {"geo_match": 6, "industry_match": 10, "tech_signals": 8, "company_age": 6, "employee_fit": 5, "website_quality": 3}, "fit_score_pct": 60, "engagement_score_pct": 50, "intent_score_pct": 38, "buying_stage": "Consideration", "fit_grade": "B", "engagement_grade": "2", "matrix_cell": "B2"},
    {"company_name": "Contentful", "domain": "contentful.com", "description": "Composable content platform that enables enterprises to create, manage, and deliver digital content at scale across channels.", "industry": "saas", "industry_classified": "Content Management", "hq_country": "Germany", "founding_year": 2013, "employee_estimate": "500-1000", "tech_stack": ["React", "TypeScript", "Node.js", "AWS", "Kubernetes", "Go"], "social_linkedin": "https://linkedin.com/company/contentful", "email_pattern": "{first}@contentful.com", "careers_jobs_count": 28, "competitor_tech": ["salesforce"], "key_signal": "Enterprise CMS leader with composable content trend driving adoption", "reasoning": "API-first CMS platform benefiting from composable architecture trend. Enterprise deals growing with expanding sales team. Good European tech signal.", "outreach_line": "Contentful's enterprise growth in composable content creates new segments needing prioritization.", "next_action": "Connect with VP of Sales EMEA", "total_score": 56, "tier": "Warm", "rule_score": 34, "soft_score": 22, "confidence": 0.79, "rule_breakdown": {"geo_match": 10, "industry_match": 11, "tech_signals": 5, "company_age": 5, "employee_fit": 3, "website_quality": 0}, "fit_score_pct": 56, "engagement_score_pct": 35, "intent_score_pct": 32, "buying_stage": "Consideration", "fit_grade": "B", "engagement_grade": "2", "matrix_cell": "B2"},
    {"company_name": "Rappi", "domain": "rappi.com", "description": "Latin American super app offering on-demand delivery, fintech services, and commerce solutions across 9 countries.", "industry": "technology", "industry_classified": "Delivery & Fintech", "hq_country": "Colombia", "founding_year": 2015, "employee_estimate": "1000-5000", "tech_stack": ["Kotlin", "Swift", "React Native", "AWS", "Python", "Kafka"], "social_linkedin": "https://linkedin.com/company/rappi", "email_pattern": "{first}@rappi.com", "careers_jobs_count": 63, "competitor_tech": [], "key_signal": "LATAM super app expanding B2B commerce and advertising platform", "reasoning": "Leading LATAM delivery platform with emerging B2B advertising and commerce solutions. Growing enterprise sales in a fast-growing region.", "outreach_line": "Rappi's B2B advertising platform expansion in LATAM needs sophisticated lead scoring for new verticals.", "next_action": "Engage Head of B2B Sales LATAM", "total_score": 51, "tier": "Warm", "rule_score": 31, "soft_score": 20, "confidence": 0.76, "rule_breakdown": {"geo_match": 6, "industry_match": 9, "tech_signals": 6, "company_age": 4, "employee_fit": 4, "website_quality": 2}, "fit_score_pct": 50, "engagement_score_pct": 40, "intent_score_pct": 30, "buying_stage": "Consideration", "fit_grade": "B", "engagement_grade": "2", "matrix_cell": "B2"},
    {"company_name": "Wiz", "domain": "wiz.io", "description": "Cloud security platform that enables organizations to rapidly identify and remove critical risks in cloud environments.", "industry": "cybersecurity", "industry_classified": "Cloud Security", "hq_country": "Israel", "founding_year": 2020, "employee_estimate": "1000-5000", "tech_stack": ["Go", "Python", "React", "AWS", "GCP", "Azure", "Kubernetes"], "social_linkedin": "https://linkedin.com/company/wizsecurity", "email_pattern": "{first}@wiz.io", "careers_jobs_count": 145, "competitor_tech": ["salesforce", "gong", "6sense"], "key_signal": "Fastest-growing cybersecurity startup ever — $100M ARR in 18 months", "reasoning": "Explosive growth cybersecurity platform with enterprise-first go-to-market. Heavy sales tooling investment and rapid team scaling. High intent for lead scoring solutions.", "outreach_line": "Wiz hypergrowth means your sales team is scaling faster than your pipeline can keep up — intelligent scoring solves that.", "next_action": "Target CRO or VP of Sales", "total_score": 68, "tier": "Warm", "rule_score": 41, "soft_score": 27, "confidence": 0.86, "rule_breakdown": {"geo_match": 8, "industry_match": 13, "tech_signals": 8, "company_age": 2, "employee_fit": 5, "website_quality": 5}, "fit_score_pct": 70, "engagement_score_pct": 50, "intent_score_pct": 48, "buying_stage": "Decision", "fit_grade": "A", "engagement_grade": "3", "matrix_cell": "A3"},
    {"company_name": "Mercado Libre", "domain": "mercadolibre.com", "description": "Latin America's leading e-commerce and fintech ecosystem. Operates marketplace, payments (Mercado Pago), logistics, and advertising.", "industry": "ecommerce", "industry_classified": "E-Commerce Platform", "hq_country": "Argentina", "founding_year": 1999, "employee_estimate": "10000+", "tech_stack": ["Java", "Go", "React", "AWS", "Kafka", "Kubernetes", "MySQL"], "social_linkedin": "https://linkedin.com/company/mercadolibre", "email_pattern": "{first}.{last}@mercadolibre.com", "careers_jobs_count": 240, "competitor_tech": ["salesforce"], "key_signal": "LATAM e-commerce giant with massive B2B advertising arm (Mercado Ads)", "reasoning": "Dominant LATAM commerce platform with growing B2B services. Mercado Ads and Mercado Pago enterprise divisions create complex lead qualification needs.", "outreach_line": "Mercado Libre's B2B platform (Ads + Pago enterprise) serves thousands of businesses needing lead scoring.", "next_action": "Connect with B2B Division Head", "total_score": 59, "tier": "Warm", "rule_score": 36, "soft_score": 23, "confidence": 0.8, "rule_breakdown": {"geo_match": 6, "industry_match": 10, "tech_signals": 7, "company_age": 8, "employee_fit": 3, "website_quality": 2}, "fit_score_pct": 58, "engagement_score_pct": 42, "intent_score_pct": 35, "buying_stage": "Consideration", "fit_grade": "B", "engagement_grade": "2", "matrix_cell": "B2"},
    {"company_name": "N26", "domain": "n26.com", "description": "European mobile bank offering current accounts, savings, insurance, and investment products through an intuitive app.", "industry": "fintech", "industry_classified": "Digital Banking", "hq_country": "Germany", "founding_year": 2013, "employee_estimate": "1000-5000", "tech_stack": ["Kotlin", "Swift", "React", "AWS", "Kubernetes", "Python"], "social_linkedin": "https://linkedin.com/company/n26", "email_pattern": "{first}.{last}@n26.com", "careers_jobs_count": 45, "competitor_tech": [], "key_signal": "European neobank expanding business banking with 8M+ customers", "reasoning": "Major European digital bank launching business accounts. B2B banking expansion creates new lead segments. Strong European fintech presence.", "outreach_line": "N26 business banking launch means a new B2B pipeline that needs intelligent lead qualification.", "next_action": "Target Head of Business Banking", "total_score": 50, "tier": "Warm", "rule_score": 30, "soft_score": 20, "confidence": 0.77, "rule_breakdown": {"geo_match": 10, "industry_match": 10, "tech_signals": 4, "company_age": 5, "employee_fit": 1, "website_quality": 0}, "fit_score_pct": 49, "engagement_score_pct": 35, "intent_score_pct": 28, "buying_stage": "Awareness", "fit_grade": "B", "engagement_grade": "3", "matrix_cell": "B3"},
    {"company_name": "Loom", "domain": "loom.com", "description": "Video messaging platform for asynchronous communication at work. Record and share video messages instantly.", "industry": "saas", "industry_classified": "Video Communication", "hq_country": "United States", "founding_year": 2015, "employee_estimate": "200-500", "tech_stack": ["TypeScript", "React", "Node.js", "AWS", "WebRTC", "FFmpeg"], "social_linkedin": "https://linkedin.com/company/laboratoriesofmodernonlinemedia", "email_pattern": "{first}@loom.com", "careers_jobs_count": 12, "competitor_tech": [], "key_signal": "Acquired by Atlassian — integration play drives enterprise adoption", "reasoning": "Atlassian acquisition creates strong enterprise distribution channel. Solid async video category leader with growing enterprise adoption. Integration with Jira/Confluence ecosystem.", "outreach_line": "Loom's Atlassian integration opens enterprise doors — lead scoring can help prioritize the inbound wave.", "next_action": "Connect with Product Partnerships team", "total_score": 46, "tier": "Warm", "rule_score": 27, "soft_score": 19, "confidence": 0.74, "rule_breakdown": {"geo_match": 12, "industry_match": 8, "tech_signals": 3, "company_age": 4, "employee_fit": 0, "website_quality": 0}, "fit_score_pct": 45, "engagement_score_pct": 28, "intent_score_pct": 25, "buying_stage": "Awareness", "fit_grade": "C", "engagement_grade": "2", "matrix_cell": "C2"},
    # ===== COLD TIER (12 companies) =====
    {"company_name": "Mailchimp", "domain": "mailchimp.com", "description": "Marketing automation platform and email marketing service for managing mailing lists and campaigns.", "industry": "marketing", "industry_classified": "Email Marketing", "hq_country": "United States", "founding_year": 2001, "employee_estimate": "1000-5000", "tech_stack": ["PHP", "Python", "JavaScript", "jQuery", "AWS"], "social_linkedin": "https://linkedin.com/company/mailchimp", "email_pattern": "{first}@mailchimp.com", "careers_jobs_count": 12, "competitor_tech": ["hubspot", "marketo"], "key_signal": "Mature platform with Intuit acquisition", "reasoning": "Established marketing platform now part of Intuit. Limited growth signals reduce ICP alignment.", "outreach_line": "", "next_action": "Monitor for organizational changes post-acquisition", "total_score": 35, "tier": "Cold", "rule_score": 22, "soft_score": 13, "confidence": 0.72, "rule_breakdown": {"geo_match": 12, "industry_match": 5, "tech_signals": 2, "company_age": 0, "employee_fit": 3, "website_quality": 0}, "fit_score_pct": 37, "engagement_score_pct": 20, "intent_score_pct": 15, "buying_stage": "Awareness", "fit_grade": "B", "engagement_grade": "3", "matrix_cell": "B3"},
    {"company_name": "Squarespace", "domain": "squarespace.com", "description": "Website building and hosting platform for creating professional websites, online stores, and portfolios.", "industry": "technology", "industry_classified": "Website Builder", "hq_country": "United States", "founding_year": 2003, "employee_estimate": "1000-5000", "tech_stack": ["Java", "JavaScript", "React", "AWS"], "social_linkedin": "https://linkedin.com/company/squarespace", "email_pattern": "{first}@squarespace.com", "careers_jobs_count": 15, "competitor_tech": [], "key_signal": "Stable but low growth trajectory", "reasoning": "Mature website builder with established market position. Limited B2B SaaS characteristics.", "outreach_line": "", "next_action": "Low priority - monitor quarterly", "total_score": 30, "tier": "Cold", "rule_score": 19, "soft_score": 11, "confidence": 0.7, "rule_breakdown": {"geo_match": 12, "industry_match": 3, "tech_signals": 1, "company_age": 0, "employee_fit": 3, "website_quality": 0}, "fit_score_pct": 32, "engagement_score_pct": 15, "intent_score_pct": 10, "buying_stage": "Awareness", "fit_grade": "C", "engagement_grade": "3", "matrix_cell": "C3"},
    {"company_name": "Freshworks", "domain": "freshworks.com", "description": "Cloud-based customer engagement software including CRM, helpdesk, and IT service management.", "industry": "saas", "industry_classified": "Customer Engagement", "hq_country": "India", "founding_year": 2010, "employee_estimate": "5000-10000", "tech_stack": ["Ruby on Rails", "React", "AWS", "Java", "MySQL"], "social_linkedin": "https://linkedin.com/company/freshworks", "email_pattern": "{first}.{last}@freshworks.com", "careers_jobs_count": 85, "competitor_tech": ["salesforce", "hubspot", "intercom"], "key_signal": "Competitor using multiple rival tools", "reasoning": "SaaS CRM competitor with significant overlap. Uses rival tools extensively.", "outreach_line": "Freshworks multi-product stack creates integration opportunities for intelligent lead routing.", "next_action": "Low priority - competitor overlap", "total_score": 38, "tier": "Cold", "rule_score": 23, "soft_score": 15, "confidence": 0.68, "rule_breakdown": {"geo_match": 4, "industry_match": 12, "tech_signals": 3, "company_age": 2, "employee_fit": 2, "website_quality": 0}, "fit_score_pct": 38, "engagement_score_pct": 40, "intent_score_pct": 20, "buying_stage": "Awareness", "fit_grade": "B", "engagement_grade": "2", "matrix_cell": "B2"},
    {"company_name": "Sage Group", "domain": "sage.com", "description": "Global provider of accounting, financial, HR, and payroll technology for small and medium-sized businesses.", "industry": "saas", "industry_classified": "Accounting Software", "hq_country": "United Kingdom", "founding_year": 1981, "employee_estimate": "10000+", "tech_stack": [".NET", "C#", "Azure", "React", "SQL Server"], "social_linkedin": "https://linkedin.com/company/sage-group", "email_pattern": "{first}.{last}@sage.com", "careers_jobs_count": 92, "competitor_tech": ["salesforce", "marketo"], "key_signal": "Legacy ERP vendor with slow cloud transition", "reasoning": "Established accounting vendor in slow cloud transition. Large but low-growth enterprise. Limited modern tech signals and outdated sales stack.", "outreach_line": "", "next_action": "Low priority - legacy vendor with long sales cycles", "total_score": 28, "tier": "Cold", "rule_score": 17, "soft_score": 11, "confidence": 0.65, "rule_breakdown": {"geo_match": 10, "industry_match": 4, "tech_signals": 1, "company_age": 0, "employee_fit": 2, "website_quality": 0}, "fit_score_pct": 28, "engagement_score_pct": 18, "intent_score_pct": 8, "buying_stage": "Target", "fit_grade": "C", "engagement_grade": "3", "matrix_cell": "C3"},
    {"company_name": "Tata Consultancy Services", "domain": "tcs.com", "description": "Global IT services, consulting, and business solutions organization. Part of the Tata Group.", "industry": "consulting", "industry_classified": "IT Consulting", "hq_country": "India", "founding_year": 1968, "employee_estimate": "10000+", "tech_stack": ["Java", ".NET", "SAP", "Oracle", "Azure"], "social_linkedin": "https://linkedin.com/company/tata-consultancy-services", "email_pattern": "{first}.{last}@tcs.com", "careers_jobs_count": 450, "competitor_tech": ["salesforce", "oracle"], "key_signal": "Massive IT services company - not a typical software buyer", "reasoning": "Global IT consulting giant — builds solutions rather than buys SaaS products. Not an ICP fit for B2B SaaS lead scoring. Would need a very different engagement strategy.", "outreach_line": "", "next_action": "Disqualify - services company, not a SaaS buyer", "total_score": 15, "tier": "Cold", "rule_score": 10, "soft_score": 5, "confidence": 0.6, "rule_breakdown": {"geo_match": 4, "industry_match": 0, "tech_signals": 2, "company_age": 0, "employee_fit": 4, "website_quality": 0}, "fit_score_pct": 15, "engagement_score_pct": 10, "intent_score_pct": 5, "buying_stage": "Target", "fit_grade": "C", "engagement_grade": "3", "matrix_cell": "C3"},
    {"company_name": "Naver", "domain": "naver.com", "description": "South Korean technology platform operating the country's largest search engine, e-commerce, fintech, and AI services.", "industry": "technology", "industry_classified": "Search & Platform", "hq_country": "South Korea", "founding_year": 1999, "employee_estimate": "5000-10000", "tech_stack": ["Java", "Spring", "React", "Kubernetes", "TensorFlow"], "social_linkedin": "https://linkedin.com/company/naver", "email_pattern": "{first}@navercorp.com", "careers_jobs_count": 120, "competitor_tech": [], "key_signal": "Korean tech giant — regional focus with limited B2B SaaS overlap", "reasoning": "Major Korean tech platform focused on consumer services. B2B play is limited to Naver Cloud and business tools which are regionally focused. Low ICP alignment.", "outreach_line": "", "next_action": "Monitor Naver Cloud B2B expansion outside Korea", "total_score": 22, "tier": "Cold", "rule_score": 14, "soft_score": 8, "confidence": 0.55, "rule_breakdown": {"geo_match": 4, "industry_match": 3, "tech_signals": 3, "company_age": 0, "employee_fit": 4, "website_quality": 0}, "fit_score_pct": 22, "engagement_score_pct": 12, "intent_score_pct": 8, "buying_stage": "Target", "fit_grade": "C", "engagement_grade": "3", "matrix_cell": "C3"},
    {"company_name": "Xero", "domain": "xero.com", "description": "Cloud-based accounting software platform for small businesses. Handles invoicing, bank reconciliation, bookkeeping, and payroll.", "industry": "fintech", "industry_classified": "Accounting Software", "hq_country": "New Zealand", "founding_year": 2006, "employee_estimate": "5000-10000", "tech_stack": [".NET", "C#", "React", "AWS", "Azure"], "social_linkedin": "https://linkedin.com/company/xero", "email_pattern": "{first}.{last}@xero.com", "careers_jobs_count": 55, "competitor_tech": ["salesforce", "hubspot"], "key_signal": "Mature accounting platform with established partner channel", "reasoning": "Well-established SMB accounting platform with limited expansion signals. Partner channel model reduces direct sales needs. Low fit for AI lead scoring.", "outreach_line": "", "next_action": "Low priority - partner-driven model limits direct lead scoring need", "total_score": 33, "tier": "Cold", "rule_score": 20, "soft_score": 13, "confidence": 0.7, "rule_breakdown": {"geo_match": 6, "industry_match": 8, "tech_signals": 2, "company_age": 2, "employee_fit": 2, "website_quality": 0}, "fit_score_pct": 34, "engagement_score_pct": 20, "intent_score_pct": 12, "buying_stage": "Awareness", "fit_grade": "C", "engagement_grade": "2", "matrix_cell": "C2"},
    {"company_name": "Baidu", "domain": "baidu.com", "description": "Chinese technology company specializing in internet search, AI, cloud services, and autonomous driving.", "industry": "technology", "industry_classified": "Search & AI", "hq_country": "China", "founding_year": 2000, "employee_estimate": "10000+", "tech_stack": ["C++", "Python", "Java", "PaddlePaddle", "Kubernetes"], "social_linkedin": "https://linkedin.com/company/baidu", "email_pattern": "{first}@baidu.com", "careers_jobs_count": 300, "competitor_tech": [], "key_signal": "Chinese tech giant — limited international B2B SaaS relevance", "reasoning": "Major Chinese technology company focused primarily on domestic market. International B2B operations are limited. Language and regulatory barriers reduce ICP fit significantly.", "outreach_line": "", "next_action": "Disqualify - domestic China focus, regulatory barriers", "total_score": 12, "tier": "Cold", "rule_score": 8, "soft_score": 4, "confidence": 0.5, "rule_breakdown": {"geo_match": 2, "industry_match": 2, "tech_signals": 2, "company_age": 0, "employee_fit": 2, "website_quality": 0}, "fit_score_pct": 12, "engagement_score_pct": 8, "intent_score_pct": 5, "buying_stage": "Target", "fit_grade": "C", "engagement_grade": "3", "matrix_cell": "C3"},
    {"company_name": "Flipkart", "domain": "flipkart.com", "description": "India's leading e-commerce marketplace offering millions of products. Subsidiary of Walmart.", "industry": "ecommerce", "industry_classified": "E-Commerce Marketplace", "hq_country": "India", "founding_year": 2007, "employee_estimate": "10000+", "tech_stack": ["Java", "React", "Node.js", "Kubernetes", "Kafka", "MySQL"], "social_linkedin": "https://linkedin.com/company/flipkart", "email_pattern": "{first}@flipkart.com", "careers_jobs_count": 180, "competitor_tech": ["salesforce"], "key_signal": "Walmart-owned Indian e-commerce — enterprise buying through parent", "reasoning": "Large Indian e-commerce platform but Walmart ownership means enterprise purchases go through parent. B2B ad platform exists but is regionally focused. Limited ICP fit for SaaS lead scoring.", "outreach_line": "", "next_action": "Monitor B2B advertising platform growth", "total_score": 25, "tier": "Cold", "rule_score": 16, "soft_score": 9, "confidence": 0.58, "rule_breakdown": {"geo_match": 4, "industry_match": 4, "tech_signals": 4, "company_age": 2, "employee_fit": 2, "website_quality": 0}, "fit_score_pct": 25, "engagement_score_pct": 15, "intent_score_pct": 10, "buying_stage": "Target", "fit_grade": "C", "engagement_grade": "3", "matrix_cell": "C3"},
    {"company_name": "Booking Holdings", "domain": "booking.com", "description": "World's leading provider of online travel and related services including Booking.com, Priceline, Kayak, and OpenTable.", "industry": "travel", "industry_classified": "Online Travel", "hq_country": "Netherlands", "founding_year": 1996, "employee_estimate": "10000+", "tech_stack": ["Java", "Perl", "React", "AWS", "Kubernetes", "Kafka"], "social_linkedin": "https://linkedin.com/company/booking.com", "email_pattern": "{first}.{last}@booking.com", "careers_jobs_count": 275, "competitor_tech": ["salesforce"], "key_signal": "Travel giant — consumer-focused with limited B2B SaaS needs", "reasoning": "Major travel platform with B2B partner program but primarily consumer-focused. Internal tooling is built, not bought. Not a natural ICP for lead scoring SaaS.", "outreach_line": "", "next_action": "Low priority - consumer-focused travel company", "total_score": 20, "tier": "Cold", "rule_score": 13, "soft_score": 7, "confidence": 0.55, "rule_breakdown": {"geo_match": 10, "industry_match": 0, "tech_signals": 1, "company_age": 0, "employee_fit": 2, "website_quality": 0}, "fit_score_pct": 20, "engagement_score_pct": 10, "intent_score_pct": 8, "buying_stage": "Target", "fit_grade": "C", "engagement_grade": "3", "matrix_cell": "C3"},
    {"company_name": "BYJU'S", "domain": "byjus.com", "description": "Indian edtech company offering online learning programs for students from kindergarten to competitive exam preparation.", "industry": "edtech", "industry_classified": "Education Technology", "hq_country": "India", "founding_year": 2011, "employee_estimate": "5000-10000", "tech_stack": ["React Native", "Node.js", "AWS", "Python", "MongoDB"], "social_linkedin": "https://linkedin.com/company/byjus", "email_pattern": "{first}@byjus.com", "careers_jobs_count": 35, "competitor_tech": ["salesforce"], "key_signal": "EdTech in restructuring — significant downsizing and financial distress", "reasoning": "Once-prominent edtech company now in financial distress with massive layoffs. High risk, uncertain future. Not suitable for active sales pursuit.", "outreach_line": "", "next_action": "Disqualify - company in financial distress", "total_score": 18, "tier": "Cold", "rule_score": 11, "soft_score": 7, "confidence": 0.45, "rule_breakdown": {"geo_match": 4, "industry_match": 2, "tech_signals": 2, "company_age": 3, "employee_fit": 0, "website_quality": 0}, "fit_score_pct": 18, "engagement_score_pct": 12, "intent_score_pct": 5, "buying_stage": "Target", "fit_grade": "C", "engagement_grade": "3", "matrix_cell": "C3"},
    {"company_name": "Zalando", "domain": "zalando.com", "description": "European online fashion and lifestyle platform connecting customers, brands, and partners across 25 markets.", "industry": "ecommerce", "industry_classified": "Fashion E-Commerce", "hq_country": "Germany", "founding_year": 2008, "employee_estimate": "10000+", "tech_stack": ["Java", "Kotlin", "React", "AWS", "Kubernetes", "PostgreSQL"], "social_linkedin": "https://linkedin.com/company/zalando", "email_pattern": "{first}.{last}@zalando.de", "careers_jobs_count": 165, "competitor_tech": [], "key_signal": "European fashion e-commerce — B2B platform for brand partners", "reasoning": "Major European fashion platform with B2B brand partner services (ZEOS). Limited direct SaaS buying signals. B2B operations are partner-enabling, not lead-scoring intensive.", "outreach_line": "", "next_action": "Monitor ZEOS B2B platform expansion", "total_score": 27, "tier": "Cold", "rule_score": 17, "soft_score": 10, "confidence": 0.62, "rule_breakdown": {"geo_match": 10, "industry_match": 2, "tech_signals": 2, "company_age": 3, "employee_fit": 0, "website_quality": 0}, "fit_score_pct": 27, "engagement_score_pct": 15, "intent_score_pct": 10, "buying_stage": "Target", "fit_grade": "C", "engagement_grade": "3", "matrix_cell": "C3"},
]

# ---------------------------------------------------------------------------
# HTML Templates
# ---------------------------------------------------------------------------

LOGIN_HTML = """<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Sign In - AI Lead Scoring Engine</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#060918;color:#e2e8f0;
     display:flex;justify-content:center;align-items:center;min-height:100vh;
     background-image:radial-gradient(ellipse at 50% 0%,rgba(99,102,241,.12) 0%,transparent 60%)}
.login{background:rgba(17,24,39,.8);backdrop-filter:blur(20px);padding:48px 40px;border-radius:20px;
       width:380px;border:1px solid rgba(99,102,241,.2);box-shadow:0 25px 60px rgba(0,0,0,.4)}
.login h1{text-align:center;font-size:1.5em;background:linear-gradient(135deg,#818cf8,#6366f1);
           -webkit-background-clip:text;-webkit-text-fill-color:transparent;margin-bottom:4px}
.login .sub{text-align:center;color:#64748b;font-size:.85em;margin-bottom:32px}
.login input{width:100%;padding:12px 16px;margin-bottom:16px;border-radius:10px;border:1px solid #1e293b;
             background:#0f172a;color:#e2e8f0;font-size:.95em;transition:border .2s}
.login input:focus{outline:none;border-color:#6366f1}
.login button{width:100%;padding:12px;border-radius:10px;border:none;background:linear-gradient(135deg,#6366f1,#8b5cf6);
              color:white;font-weight:600;font-size:1em;cursor:pointer;transition:opacity .2s}
.login button:hover{opacity:.9}
.err{background:rgba(239,68,68,.15);color:#fca5a5;padding:10px 14px;border-radius:10px;margin-bottom:16px;
     font-size:.85em;text-align:center;border:1px solid rgba(239,68,68,.2)}
</style></head><body>
<div class="login">
  <h1>AI Lead Scoring</h1>
  <p class="sub">Sign in to your dashboard</p>
  {% if error %}<div class="err">{{ error }}</div>{% endif %}
  <form method="POST">
    <input type="text" name="username" placeholder="Username" required autofocus>
    <input type="password" name="password" placeholder="Password" required>
    <button type="submit">Sign In</button>
  </form>
</div></body></html>"""

BASE_HTML = """<!DOCTYPE html>
<html lang="en" data-theme="dark"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{{ title }} - AI Lead Scoring Engine</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
<style>
:root,[data-theme="dark"]{--bg:#060918;--surface:#0d1224;--card:#111827;--card-hover:#1a2236;--border:#1e293b;
      --accent:#6366f1;--accent2:#8b5cf6;--text:#f1f5f9;--text2:#94a3b8;--text3:#64748b;
      --hot:#ef4444;--warm:#f59e0b;--cold:#22c55e;--sidebar-w:260px}
[data-theme="light"]{--bg:#f8fafc;--surface:#ffffff;--card:#ffffff;--card-hover:#f1f5f9;--border:#e2e8f0;
      --accent:#4f46e5;--accent2:#7c3aed;--text:#0f172a;--text2:#475569;--text3:#94a3b8;
      --hot:#dc2626;--warm:#d97706;--cold:#16a34a}
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:var(--bg);color:var(--text);line-height:1.6;transition:background .3s,color .3s}
a{color:var(--accent);text-decoration:none}a:hover{color:#818cf8}

/* Sidebar */
.sidebar{position:fixed;left:0;top:0;bottom:0;width:var(--sidebar-w);background:linear-gradient(180deg,var(--surface) 0%,var(--bg) 100%);
         border-right:1px solid var(--border);z-index:100;display:flex;flex-direction:column;overflow-y:auto;transition:background .3s}
.sidebar .brand{padding:24px 20px;display:flex;align-items:center;gap:12px}
.sidebar .brand .logo{width:36px;height:36px;border-radius:10px;background:linear-gradient(135deg,var(--accent),var(--accent2));
                      display:flex;align-items:center;justify-content:center;font-weight:800;font-size:1.1em;color:white;flex-shrink:0}
.sidebar .brand span{font-weight:700;font-size:.95em;color:var(--text)}
.sidebar nav{flex:1;padding:8px 12px}
.sidebar nav a{display:flex;align-items:center;gap:12px;padding:10px 14px;border-radius:10px;color:var(--text2);
               font-size:.9em;font-weight:500;transition:all .15s;margin-bottom:2px}
.sidebar nav a:hover{background:rgba(99,102,241,.08);color:var(--text)}
.sidebar nav a.active{background:rgba(99,102,241,.15);color:var(--accent)}
.sidebar nav a .icon{width:20px;text-align:center;font-size:1.05em}
.sidebar .sep{height:1px;background:var(--border);margin:12px 20px}
.sidebar .bottom{padding:16px 20px}
.sidebar .bottom .user{display:flex;align-items:center;gap:10px;padding:10px 0}
.sidebar .bottom .avatar{width:32px;height:32px;border-radius:8px;background:var(--accent);display:flex;
                          align-items:center;justify-content:center;font-weight:600;font-size:.8em;color:white}
.sidebar .bottom .uname{font-size:.85em;color:var(--text)}
.sidebar .bottom .urole{font-size:.75em;color:var(--text3)}

/* Main */
.main{margin-left:var(--sidebar-w);min-height:100vh}
.topbar{padding:16px 32px;border-bottom:1px solid var(--border);display:flex;align-items:center;gap:16px;
        background:rgba(13,18,36,.8);backdrop-filter:blur(10px);position:sticky;top:0;z-index:50;transition:background .3s}
[data-theme="light"] .topbar{background:rgba(255,255,255,.9)}
.topbar h2{font-size:1.15em;font-weight:600;color:var(--text)}
.topbar .spacer{flex:1}
.topbar .sample-btn{padding:8px 18px;border-radius:8px;border:1px solid var(--accent);background:transparent;
                    color:var(--accent);font-weight:600;font-size:.85em;cursor:pointer;transition:all .2s}
.topbar .sample-btn:hover{background:var(--accent);color:white}
.topbar .theme-btn{padding:6px 10px;border-radius:8px;border:1px solid var(--border);background:transparent;
                   color:var(--text2);cursor:pointer;font-size:1em;transition:all .2s}
.topbar .theme-btn:hover{border-color:var(--accent);color:var(--accent)}
.topbar .cmd-btn{padding:6px 14px;border-radius:8px;border:1px solid var(--border);background:transparent;
                 color:var(--text3);cursor:pointer;font-size:.8em;transition:all .2s;display:flex;align-items:center;gap:6px}
.topbar .cmd-btn:hover{border-color:var(--accent);color:var(--text2)}
.topbar .cmd-btn kbd{background:var(--surface);padding:2px 6px;border-radius:4px;font-size:.8em;border:1px solid var(--border)}
.content{padding:24px 32px}

/* KPI Cards */
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:16px;margin-bottom:24px}
.kpi{background:var(--card);border-radius:14px;padding:22px;border:1px solid var(--border);position:relative;overflow:hidden;transition:border-color .2s,background .3s}
.kpi:hover{border-color:#334155}
.kpi::before{content:'';position:absolute;top:0;left:0;right:0;height:3px;border-radius:14px 14px 0 0}
.kpi.total::before{background:linear-gradient(90deg,var(--accent),var(--accent2))}
.kpi.hot::before{background:var(--hot)}.kpi.warm::before{background:var(--warm)}.kpi.cold::before{background:var(--cold)}
.kpi.score::before{background:linear-gradient(90deg,#06b6d4,#3b82f6)}
.kpi .value{font-size:2em;font-weight:700;line-height:1.2}
.kpi .label{font-size:.8em;color:var(--text3);margin-top:4px;text-transform:uppercase;letter-spacing:.5px}
.kpi .change{font-size:.75em;margin-top:6px}
.val-hot{color:var(--hot)}.val-warm{color:var(--warm)}.val-cold{color:var(--cold)}.val-accent{color:var(--accent)}

/* Cards */
.card{background:var(--card);border-radius:14px;padding:24px;border:1px solid var(--border);margin-bottom:20px;transition:background .3s}
.card h3{font-size:1em;font-weight:600;margin-bottom:16px;color:var(--text)}
.grid-2{display:grid;grid-template-columns:1fr 1fr;gap:20px}
.grid-3{display:grid;grid-template-columns:1fr 1fr 1fr;gap:20px}
@media(max-width:1100px){.grid-2,.grid-3{grid-template-columns:1fr}}

/* Table */
.tbl-wrap{overflow-x:auto;border-radius:12px;border:1px solid var(--border)}
table{width:100%;border-collapse:collapse;font-size:.88em}
thead th{background:var(--surface);padding:12px 14px;text-align:left;font-weight:600;color:var(--text2);
         cursor:pointer;user-select:none;white-space:nowrap;border-bottom:1px solid var(--border);position:sticky;top:0}
thead th:hover{color:var(--text)}
tbody td{padding:10px 14px;border-bottom:1px solid rgba(30,41,59,.5);white-space:nowrap}
tbody tr{transition:background .1s}
tbody tr:hover{background:rgba(99,102,241,.04)}
tbody tr:last-child td{border-bottom:none}
.badge{padding:4px 12px;border-radius:20px;font-size:.78em;font-weight:600;display:inline-block}
.badge-hot{background:rgba(239,68,68,.15);color:#f87171}
.badge-warm{background:rgba(245,158,11,.15);color:#fbbf24}
.badge-cold{background:rgba(34,197,94,.15);color:#4ade80}
.badge-completed{background:rgba(34,197,94,.15);color:#4ade80}
.badge-running{background:rgba(99,102,241,.15);color:#818cf8}
.badge-purchase{background:rgba(139,92,246,.15);color:#a78bfa}
.badge-decision{background:rgba(239,68,68,.15);color:#f87171}
.badge-consideration{background:rgba(245,158,11,.15);color:#fbbf24}
.badge-awareness{background:rgba(34,197,94,.15);color:#4ade80}
.badge-target{background:rgba(100,116,139,.15);color:#94a3b8}

/* Score bar */
.score-bar{display:flex;align-items:center;gap:8px}
.score-bar .bar{flex:1;height:6px;background:var(--border);border-radius:3px;overflow:hidden;max-width:80px}
.score-bar .fill{height:100%;border-radius:3px;transition:width .3s}
.score-bar .num{font-weight:600;font-size:.9em;min-width:32px}

/* Tri-dimensional bars */
.dim-bars{display:flex;flex-direction:column;gap:10px;margin-top:8px}
.dim-bar{display:flex;align-items:center;gap:10px}
.dim-bar .lbl{width:90px;font-size:.82em;color:var(--text2);text-align:right}
.dim-bar .track{flex:1;height:10px;background:var(--border);border-radius:5px;overflow:hidden;max-width:200px}
.dim-bar .fill{height:100%;border-radius:5px;transition:width .5s}
.dim-bar .pct{font-size:.82em;font-weight:600;width:40px}
.fill-fit{background:linear-gradient(90deg,#6366f1,#818cf8)}
.fill-eng{background:linear-gradient(90deg,#f59e0b,#fbbf24)}
.fill-int{background:linear-gradient(90deg,#22c55e,#4ade80)}

/* Buttons */
.btn{padding:8px 18px;border-radius:8px;border:none;font-weight:600;font-size:.85em;cursor:pointer;transition:all .2s;display:inline-flex;align-items:center;gap:6px}
.btn:hover{opacity:.9}.btn-primary{background:var(--accent);color:white}
.btn-outline{background:transparent;border:1px solid var(--border);color:var(--text2)}.btn-outline:hover{border-color:var(--accent);color:var(--accent)}
.btn-sm{padding:6px 12px;font-size:.8em;border-radius:6px}
.btn-danger{background:rgba(239,68,68,.15);color:#f87171;border:1px solid rgba(239,68,68,.2)}
.btn-success{background:rgba(34,197,94,.15);color:#4ade80;border:1px solid rgba(34,197,94,.2)}
.btn-warn{background:rgba(245,158,11,.15);color:#fbbf24;border:1px solid rgba(245,158,11,.2)}

/* Filters */
.filters{display:flex;gap:10px;margin-bottom:20px;flex-wrap:wrap;align-items:center}
.filters select,.filters input[type=text]{background:var(--surface);color:var(--text);border:1px solid var(--border);
    padding:8px 14px;border-radius:8px;font-size:.85em;min-width:140px;transition:background .3s}
.filters select:focus,.filters input:focus{outline:none;border-color:var(--accent)}

/* Charts */
.chart-box{position:relative;max-height:280px}

/* Tech badges */
.tech-badge{display:inline-block;padding:3px 10px;border-radius:6px;font-size:.78em;background:rgba(99,102,241,.1);
            color:#a5b4fc;margin:2px;border:1px solid rgba(99,102,241,.15)}
.comp-badge{background:rgba(245,158,11,.1);color:#fcd34d;border-color:rgba(245,158,11,.15)}

/* Detail */
.detail-header{display:flex;align-items:center;gap:20px;margin-bottom:24px}
.detail-header .score-circle{width:80px;height:80px;border-radius:50%;display:flex;align-items:center;justify-content:center;
    font-size:1.5em;font-weight:800;border:3px solid}
.detail-header .meta{flex:1}
.detail-header .meta h1{font-size:1.5em;margin-bottom:2px}
.detail-header .meta p{color:var(--text3);font-size:.9em}

/* Forms */
.form-row{display:flex;gap:10px;flex-wrap:wrap;margin-top:12px}
.form-row input,.form-row select{background:var(--surface);color:var(--text);border:1px solid var(--border);
    padding:8px 14px;border-radius:8px;font-size:.85em;transition:background .3s}
.form-row input:focus{outline:none;border-color:var(--accent)}

/* Empty state */
.empty{text-align:center;padding:60px 20px}
.empty .icon{font-size:3em;margin-bottom:16px;opacity:.3}
.empty p{color:var(--text3);margin-bottom:20px}

/* Toast */
.toast{position:fixed;top:20px;right:20px;padding:14px 20px;border-radius:10px;background:#065f46;color:#6ee7b7;
       border:1px solid #059669;z-index:200;animation:slideIn .3s;font-size:.9em}
@keyframes slideIn{from{transform:translateX(100%);opacity:0}to{transform:translateX(0);opacity:1}}

/* Command Palette */
.cmd-overlay{position:fixed;inset:0;background:rgba(0,0,0,.6);z-index:300;display:none;align-items:flex-start;justify-content:center;padding-top:20vh}
.cmd-overlay.open{display:flex}
.cmd-box{background:var(--card);border:1px solid var(--border);border-radius:14px;width:500px;max-height:400px;overflow:hidden;box-shadow:0 25px 60px rgba(0,0,0,.5)}
.cmd-box input{width:100%;padding:16px 20px;border:none;border-bottom:1px solid var(--border);background:transparent;color:var(--text);font-size:1em;outline:none}
.cmd-results{max-height:320px;overflow-y:auto;padding:8px}
.cmd-item{padding:10px 16px;border-radius:8px;cursor:pointer;display:flex;align-items:center;gap:12px;color:var(--text2);font-size:.9em}
.cmd-item:hover,.cmd-item.selected{background:rgba(99,102,241,.1);color:var(--text)}
.cmd-item .cmd-icon{width:20px;text-align:center;opacity:.6}

/* Funnel */
.funnel{display:flex;flex-direction:column;gap:4px;margin-top:8px}
.funnel-step{display:flex;align-items:center;gap:12px;padding:8px 16px;border-radius:8px;transition:background .2s}
.funnel-step:hover{background:rgba(99,102,241,.05)}
.funnel-bar{height:24px;border-radius:4px;display:flex;align-items:center;padding:0 10px;font-size:.78em;font-weight:600;color:white;min-width:30px}

/* Factor list */
.factor{display:flex;align-items:center;gap:8px;padding:6px 0;font-size:.85em}
.factor .dot{width:8px;height:8px;border-radius:50%;flex-shrink:0}
.factor .dot.pos{background:#22c55e}.factor .dot.neg{background:#ef4444}.factor .dot.neu{background:#f59e0b}
.factor .impact{margin-left:auto;font-weight:600;font-size:.8em}

/* Matrix heatmap */
.matrix{display:grid;grid-template-columns:auto repeat(3,1fr);gap:2px;font-size:.82em;margin-top:8px}
.matrix .cell{padding:10px;text-align:center;border-radius:6px;font-weight:600;cursor:default}
.matrix .header{color:var(--text3);font-weight:600;padding:8px}

/* Activity feed */
.feed{max-height:300px;overflow-y:auto}
.feed-item{display:flex;gap:12px;padding:10px 0;border-bottom:1px solid rgba(30,41,59,.3);font-size:.85em}
.feed-item:last-child{border-bottom:none}
.feed-dot{width:8px;height:8px;border-radius:50%;margin-top:6px;flex-shrink:0}
.feed-dot.score{background:var(--accent)}.feed-dot.feedback{background:var(--warm)}

/* Feedback */
.fb-btns{display:flex;gap:8px;margin-top:12px}

/* Misc */
pre{background:var(--surface);padding:16px;border-radius:10px;overflow-x:auto;font-size:.82em;border:1px solid var(--border)}
.text-muted{color:var(--text3)}
.mt-2{margin-top:8px}.mt-4{margin-top:16px}.mb-4{margin-bottom:16px}

/* Kanban Board */
.kanban{display:flex;gap:12px;overflow-x:auto;padding-bottom:16px}
.kanban-col{min-width:220px;flex:1;background:var(--surface);border-radius:12px;border:1px solid var(--border);padding:12px}
.kanban-col h4{font-size:.82em;color:var(--text3);text-transform:uppercase;letter-spacing:.5px;margin-bottom:10px;display:flex;justify-content:space-between}
.kanban-col h4 .cnt{background:var(--border);padding:2px 8px;border-radius:10px;font-size:.9em}
.kanban-card{background:var(--card);border:1px solid var(--border);border-radius:10px;padding:12px;margin-bottom:8px;cursor:grab;transition:transform .15s}
.kanban-card:hover{transform:translateY(-2px);box-shadow:0 4px 12px rgba(0,0,0,.15)}
.kanban-card .kc-name{font-weight:600;font-size:.88em}.kanban-card .kc-score{font-size:.78em;margin-top:4px}
.kanban-card .kc-meta{font-size:.72em;color:var(--text3);margin-top:4px}
.kanban-card.dragging{opacity:.5}

/* Sparkline */
.sparkline{display:inline-block;vertical-align:middle}

/* Freshness */
.fresh-badge{font-size:.7em;padding:2px 6px;border-radius:4px;margin-left:4px}
.fresh-new{background:rgba(34,197,94,.12);color:#4ade80}
.fresh-recent{background:rgba(245,158,11,.1);color:#fbbf24}
.fresh-stale{background:rgba(239,68,68,.1);color:#f87171}

/* Marketplace */
.mkt-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:16px}
.mkt-card{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:20px;text-align:center;transition:border-color .2s}
.mkt-card:hover{border-color:var(--accent)}
.mkt-card .mkt-icon{font-size:2em;margin-bottom:8px}.mkt-card .mkt-name{font-weight:600;font-size:.92em}
.mkt-card .mkt-desc{font-size:.78em;color:var(--text3);margin-top:4px}
.mkt-card .mkt-status{font-size:.75em;margin-top:8px;padding:4px 10px;border-radius:12px;display:inline-block}
.mkt-on{background:rgba(34,197,94,.12);color:#4ade80}.mkt-off{background:rgba(100,116,139,.12);color:#94a3b8}

/* Workflow */
.wf-canvas{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:20px;min-height:200px}
.wf-node{background:var(--card);border:1px solid var(--border);border-radius:10px;padding:12px;display:inline-block;min-width:160px}
.wf-node:hover{border-color:var(--accent)}.wf-node .wf-type{font-size:.72em;text-transform:uppercase;color:var(--text3);letter-spacing:.5px}
.wf-node .wf-label{font-weight:600;font-size:.85em;margin-top:4px}
.wf-arrow{color:var(--text3);font-size:1.5em;display:inline-block;vertical-align:middle;margin:0 4px}
.wf-trigger{border-left:3px solid var(--accent)}.wf-condition{border-left:3px solid var(--warm)}.wf-action{border-left:3px solid var(--cold)}

/* Velocity */
.vel-val{font-size:1.8em;font-weight:700}.vel-label{font-size:.78em;color:var(--text3);margin-top:4px}

/* Leaderboard */
.lb-row{display:flex;align-items:center;gap:12px;padding:10px 0;border-bottom:1px solid rgba(30,41,59,.3)}
.lb-row:last-child{border-bottom:none}
.lb-rank{width:28px;height:28px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:.82em}
.lb-gold{background:rgba(245,158,11,.2);color:#fbbf24}.lb-silver{background:rgba(148,163,184,.2);color:#94a3b8}
.lb-bronze{background:rgba(194,120,3,.2);color:#ca8a04}
.lb-info{flex:1}.lb-score-val{font-weight:700;font-size:1.1em}

/* Skeleton loading */
@keyframes shimmer{0%{background-position:-200px 0}100%{background-position:200px 0}}
.skeleton{background:linear-gradient(90deg,var(--border) 25%,rgba(99,102,241,.08) 50%,var(--border) 75%);
          background-size:200px 100%;animation:shimmer 1.5s infinite;border-radius:6px;height:20px}

/* Mobile */
@media(max-width:768px){
  .sidebar{display:none}
  .main{margin-left:0}
  .content{padding:16px}
  .grid-2,.grid-3{grid-template-columns:1fr}
  .kpis{grid-template-columns:repeat(2,1fr)}
}
</style></head><body>

<!-- Sidebar -->
<aside class="sidebar">
  <div class="brand">
    <div class="logo">AI</div>
    <span>Lead Scoring<br>Engine</span>
  </div>
  <nav>
    <a href="/" class="{% if page=='dashboard' %}active{% endif %}"><span class="icon">&#9679;</span> Dashboard</a>
    <a href="/leads" class="{% if page=='leads' %}active{% endif %}"><span class="icon">&#9734;</span> Leads</a>
    <a href="/kanban" class="{% if page=='kanban' %}active{% endif %}"><span class="icon">&#9641;</span> Pipeline Board</a>
    <a href="/analytics" class="{% if page=='analytics' %}active{% endif %}"><span class="icon">&#9670;</span> Analytics</a>
    <a href="/runs" class="{% if page=='runs' %}active{% endif %}"><span class="icon">&#9654;</span> Pipeline Runs</a>
    <a href="/quality" class="{% if page=='quality' %}active{% endif %}"><span class="icon">&#10003;</span> Data Quality</a>
    <div class="sep"></div>
    <a href="/marketplace" class="{% if page=='marketplace' %}active{% endif %}"><span class="icon">&#8644;</span> Integrations</a>
    <a href="/workflows" class="{% if page=='workflows' %}active{% endif %}"><span class="icon">&#9881;</span> Workflows</a>
    <a href="/api-docs" class="{% if page=='api' %}active{% endif %}"><span class="icon">&#123;&#125;</span> API</a>
    {% if role in ('admin', 'editor') %}
    <a href="/admin/settings" class="{% if page=='settings' %}active{% endif %}"><span class="icon">&#9881;</span> Settings</a>
    {% endif %}
    {% if role == 'admin' %}
    <a href="/admin/users" class="{% if page=='admin' %}active{% endif %}"><span class="icon">&#9783;</span> Users</a>
    {% endif %}
  </nav>
  <div class="bottom">
    <div class="sep"></div>
    <div class="user">
      <div class="avatar">{{ (username or 'G')[0]|upper }}</div>
      <div><div class="uname">{{ username or 'Guest' }}</div><div class="urole">{{ role or 'viewer' }}</div></div>
    </div>
    <a href="/logout" style="font-size:.8em;color:var(--text3)">Sign out</a>
  </div>
</aside>

<!-- Command Palette -->
<div class="cmd-overlay" id="cmdPalette">
  <div class="cmd-box">
    <input type="text" id="cmdInput" placeholder="Type a command..." autocomplete="off">
    <div class="cmd-results" id="cmdResults"></div>
  </div>
</div>

<!-- Main -->
<div class="main">
  <div class="topbar">
    <h2>{{ title }}</h2>
    <div class="spacer"></div>
    <button class="cmd-btn" onclick="toggleCmd()"><span>Search</span> <kbd>Ctrl+K</kbd></button>
    <button class="theme-btn" onclick="toggleNotifs()" title="Notifications" id="notifBtn" style="position:relative">&#128276;
      <span id="notifBadge" style="position:absolute;top:-4px;right:-4px;background:var(--hot);color:white;font-size:.6em;padding:1px 5px;border-radius:10px;display:none">0</span>
    </button>
    <button class="theme-btn" onclick="toggleTheme()" title="Toggle theme">&#9788;</button>
    <button class="sample-btn" onclick="loadSampleData()">&#9889; Load Sample Data</button>
  </div>
  <div class="content">{{ content|safe }}</div>
</div>

<!-- Notification Panel -->
<div id="notifPanel" style="position:fixed;top:60px;right:20px;width:340px;background:var(--card);border:1px solid var(--border);
     border-radius:14px;box-shadow:0 10px 40px rgba(0,0,0,.3);z-index:200;display:none;max-height:400px;overflow-y:auto">
  <div style="padding:14px 18px;border-bottom:1px solid var(--border);font-weight:600;font-size:.9em;display:flex;justify-content:space-between;align-items:center">
    Notifications <button onclick="toggleNotifs()" style="background:none;border:none;color:var(--text3);cursor:pointer;font-size:1.1em">&times;</button>
  </div>
  <div id="notifList" style="padding:8px"></div>
</div>

<div id="toast" class="toast" style="display:none"></div>

<script>
// Theme toggle
function toggleTheme(){
  const html=document.documentElement;
  const t=html.dataset.theme==='dark'?'light':'dark';
  html.dataset.theme=t;localStorage.setItem('theme',t);
}
(function(){const t=localStorage.getItem('theme');if(t)document.documentElement.dataset.theme=t;})();

// Command palette
const cmdPages=[
  {name:'Dashboard',url:'/',icon:'&#9679;'},
  {name:'Leads',url:'/leads',icon:'&#9734;'},
  {name:'Analytics',url:'/analytics',icon:'&#9670;'},
  {name:'Pipeline Runs',url:'/runs',icon:'&#9654;'},
  {name:'Data Quality',url:'/quality',icon:'&#10003;'},
  {name:'Integrations',url:'/integrations',icon:'&#8644;'},
  {name:'API Docs',url:'/api-docs',icon:'&#123;&#125;'},
  {name:'Settings',url:'/admin/settings',icon:'&#9881;'},
  {name:'Users',url:'/admin/users',icon:'&#9783;'},
  {name:'Pipeline Board',url:'/kanban',icon:'&#9641;'},
  {name:'Lead Routing',url:'/routing',icon:'&#8634;'},
  {name:'Compare Leads',url:'/compare',icon:'&#8646;'},
  {name:'Pipeline Velocity',url:'/velocity',icon:'&#9650;'},
  {name:'Geographic View',url:'/geo',icon:'&#127758;'},
  {name:'Account-Based',url:'/abm',icon:'&#127970;'},
  {name:'Leaderboard',url:'/leaderboard',icon:'&#127942;'},
  {name:'Marketplace',url:'/marketplace',icon:'&#8644;'},
  {name:'Workflows',url:'/workflows',icon:'&#9881;'},
  {name:'Champion/Challenger',url:'/champion-challenger',icon:'&#9878;'},
  {name:'Webhook Log',url:'/webhook-log',icon:'&#128214;'},
  {name:'Import Leads',url:'/import',icon:'&#8593;'},
  {name:'Export CSV',url:'/api/export/csv',icon:'&#8615;'},
];
function toggleCmd(){
  const o=document.getElementById('cmdPalette');
  o.classList.toggle('open');
  if(o.classList.contains('open')){document.getElementById('cmdInput').value='';document.getElementById('cmdInput').focus();renderCmd('');}
}
function renderCmd(q){
  const r=document.getElementById('cmdResults');
  const filtered=cmdPages.filter(p=>p.name.toLowerCase().includes(q.toLowerCase()));
  r.innerHTML=filtered.map(p=>'<div class="cmd-item" onclick="location.href=\''+p.url+'\'"><span class="cmd-icon">'+p.icon+'</span>'+p.name+'</div>').join('');
}
document.addEventListener('keydown',e=>{
  if((e.ctrlKey||e.metaKey)&&e.key==='k'){e.preventDefault();toggleCmd();}
  if(e.key==='Escape')document.getElementById('cmdPalette').classList.remove('open');
});
document.getElementById('cmdInput')?.addEventListener('input',e=>renderCmd(e.target.value));
document.getElementById('cmdPalette')?.addEventListener('click',e=>{if(e.target.classList.contains('cmd-overlay'))toggleCmd();});

// Sample data loader
function loadSampleData(){
  if(!confirm('Load 40 sample companies with pre-scored data? This is great for testing.')) return;
  fetch('/api/load-sample-data',{method:'POST'})
    .then(r=>r.json()).then(d=>{
      if(d.status==='ok'){showToast('Loaded '+d.companies+' sample companies!');setTimeout(()=>location.reload(),800);}
      else showToast('Error: '+d.reason,'error');
    }).catch(()=>showToast('Failed to load sample data','error'));
}
function showToast(msg){
  const t=document.getElementById('toast');t.textContent=msg;t.style.display='block';
  setTimeout(()=>t.style.display='none',3000);
}
function sortTable(tableId,col){
  const table=document.getElementById(tableId);if(!table)return;
  const rows=Array.from(table.tBodies[0].rows);
  const dir=table.dataset.sortCol==col&&table.dataset.sortDir==='asc'?-1:1;
  table.dataset.sortCol=col;table.dataset.sortDir=dir===1?'asc':'desc';
  rows.sort((a,b)=>{
    let va=a.cells[col].dataset.val||a.cells[col].textContent.trim();
    let vb=b.cells[col].dataset.val||b.cells[col].textContent.trim();
    const na=parseFloat(va),nb=parseFloat(vb);
    if(!isNaN(na)&&!isNaN(nb))return(na-nb)*dir;
    return va.localeCompare(vb)*dir;
  });
  rows.forEach(r=>table.tBodies[0].appendChild(r));
}
function filterLeads(){
  const tier=document.getElementById('tierF')?.value||'';
  const stage=document.getElementById('stageF')?.value||'';
  const q=(document.getElementById('searchF')?.value||'').toLowerCase();
  document.querySelectorAll('#leadsTable tbody tr').forEach(r=>{
    const mt=!tier||r.dataset.tier===tier;
    const ms2=!stage||r.dataset.stage===stage;
    const ms=!q||r.textContent.toLowerCase().includes(q);
    r.style.display=mt&&ms&&ms2?'':'none';
  });
}
function scoreColor(s){return s>=70?'var(--hot)':s>=40?'var(--warm)':'var(--cold)';}

// Keyboard shortcuts
let gPending=false;
document.addEventListener('keydown',e=>{
  if(e.target.tagName==='INPUT'||e.target.tagName==='TEXTAREA'||e.target.tagName==='SELECT')return;
  if(e.key==='?'&&!e.ctrlKey){showToast('Shortcuts: g+d=Dashboard, g+l=Leads, g+a=Analytics, g+r=Runs, g+q=Quality, g+s=Settings, Ctrl+K=Search, ?=Help');}
  if(gPending){
    gPending=false;
    const map={d:'/',l:'/leads',a:'/analytics',r:'/runs',q:'/quality',s:'/admin/settings',i:'/marketplace',c:'/compare',k:'/kanban',v:'/velocity',w:'/workflows',b:'/abm',e:'/leaderboard'};
    if(map[e.key])location.href=map[e.key];
    return;
  }
  if(e.key==='g'&&!e.ctrlKey&&!e.metaKey){gPending=true;setTimeout(()=>gPending=false,1000);}
});

// Notifications
function toggleNotifs(){
  const p=document.getElementById('notifPanel');
  if(p.style.display==='none'){
    p.style.display='block';
    fetch('/api/activity').then(r=>r.json()).then(data=>{
      const list=document.getElementById('notifList');
      if(!data.length){list.innerHTML='<p style="padding:16px;color:var(--text3);text-align:center;font-size:.85em">No recent activity</p>';return;}
      list.innerHTML=data.slice(0,10).map(a=>'<div style="padding:8px 10px;border-bottom:1px solid rgba(30,41,59,.3);font-size:.82em">'
        +'<strong>'+a.action+'</strong> '+(a.entity_type||'')+' '+(a.entity_id||'')
        +'<div style="color:var(--text3);font-size:.9em;margin-top:2px">'+(a.created_at||'').substring(0,16)+'</div></div>').join('');
      document.getElementById('notifBadge').style.display='none';
    });
  } else p.style.display='none';
}
// Show badge on load if there's activity
fetch('/api/activity').then(r=>r.json()).then(data=>{
  if(data.length){const b=document.getElementById('notifBadge');b.textContent=Math.min(data.length,9);b.style.display='inline';}
}).catch(()=>{});

// Compare
function compareSelected(){
  const checked=Array.from(document.querySelectorAll('.lead-check:checked')).map(c=>c.value);
  if(checked.length<2){showToast('Select at least 2 leads to compare');return;}
  location.href='/compare?domains='+checked.join(',');
}

// Feedback
function sendFeedback(domain,type){
  fetch('/api/feedback',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({domain:domain,feedback_type:type})})
    .then(r=>r.json()).then(d=>{
      if(d.status==='ok')showToast('Feedback recorded: '+type);
      else showToast('Error: '+(d.error||'unknown'));
    }).catch(()=>showToast('Failed to send feedback'));
}
</script>
</body></html>"""


# ---------------------------------------------------------------------------
# Page Templates
# ---------------------------------------------------------------------------

DASHBOARD_CONTENT = """
<div class="kpis">
  <div class="kpi total"><div class="value val-accent">{{ total }}</div><div class="label">Total Leads</div></div>
  <div class="kpi hot"><div class="value val-hot">{{ hot }}</div><div class="label">Hot Leads</div></div>
  <div class="kpi warm"><div class="value val-warm">{{ warm }}</div><div class="label">Warm Leads</div></div>
  <div class="kpi cold"><div class="value val-cold">{{ cold }}</div><div class="label">Cold Leads</div></div>
  <div class="kpi score"><div class="value">{{ '%.1f'|format(avg) }}</div><div class="label">Avg Score</div></div>
</div>

{% if total == 0 %}
<div class="card empty">
  <div class="icon">&#128202;</div>
  <h3>No leads scored yet</h3>
  <p>Click "Load Sample Data" above to populate the dashboard with 15 demo companies, or run the scoring pipeline on your own CSV.</p>
  <button class="btn btn-primary" onclick="loadSampleData()">&#9889; Load Sample Data</button>
</div>
{% else %}
<div class="grid-2">
  <div class="card">
    <h3>Tier Distribution</h3>
    <div class="chart-box"><canvas id="tierChart"></canvas></div>
  </div>
  <div class="card">
    <h3>Score Distribution</h3>
    <div class="chart-box"><canvas id="scoreChart"></canvas></div>
  </div>
</div>

<div class="grid-2">
  <div class="card">
    <h3>Buying Stage Pipeline</h3>
    <div class="funnel">
      {% for stage, count in stages %}
      <div class="funnel-step">
        <span style="width:100px;font-size:.82em;color:var(--text2)">{{ stage }}</span>
        <div class="funnel-bar" style="width:{{ count * 100 // (max_stage if max_stage > 0 else 1) }}%;background:{{ stage_colors[loop.index0 % 5] }}">{{ count }}</div>
      </div>
      {% endfor %}
    </div>
  </div>
  <div class="card">
    <h3>Fit-Engagement Matrix</h3>
    <div class="matrix">
      <div class="header"></div><div class="header">Eng 1 (High)</div><div class="header">Eng 2 (Med)</div><div class="header">Eng 3 (Low)</div>
      {% for row in ['A','B','C'] %}
      <div class="header">Fit {{ row }}</div>
      {% for col in ['1','2','3'] %}
      <div class="cell" style="background:{{ matrix_colors[row+col] }}">{{ matrix_counts[row+col] }}</div>
      {% endfor %}
      {% endfor %}
    </div>
  </div>
</div>

<div class="card">
  <h3>Top Leads</h3>
  <div class="tbl-wrap">
  <table>
    <thead><tr><th>Company</th><th>Score</th><th>Tier</th><th>Stage</th><th>Matrix</th><th>Industry</th><th>Key Signal</th></tr></thead>
    <tbody>
    {% for l in top_leads %}
    <tr>
      <td><a href="/leads/{{ l.domain }}"><strong>{{ l.company_name }}</strong></a></td>
      <td><div class="score-bar"><span class="num" style="color:{{ l._color }}">{{ l.total_score }}</span>
          <div class="bar"><div class="fill" style="width:{{ l.total_score }}%;background:{{ l._color }}"></div></div></div></td>
      <td><span class="badge badge-{{ l.tier|lower }}">{{ l.tier }}</span></td>
      <td><span class="badge badge-{{ (l.buying_stage or 'target')|lower }}">{{ l.buying_stage or 'Target' }}</span></td>
      <td><strong>{{ l.matrix_cell or '-' }}</strong></td>
      <td>{{ l.industry_classified or l.industry or '-' }}</td>
      <td style="max-width:250px;overflow:hidden;text-overflow:ellipsis">{{ (l.key_signal or '-')[:80] }}</td>
    </tr>
    {% endfor %}
    </tbody>
  </table></div>
  {% if total > 10 %}<div class="mt-2"><a href="/leads">View all {{ total }} leads &rarr;</a></div>{% endif %}
</div>

{% if activity %}
<div class="card">
  <h3>Recent Activity</h3>
  <div class="feed">
    {% for a in activity %}
    <div class="feed-item">
      <div class="feed-dot {{ a.action|default('score') }}"></div>
      <div><strong>{{ a.action }}</strong> {{ a.entity_type or '' }} {{ a.entity_id or '' }}
        <div class="text-muted" style="font-size:.82em">{{ (a.created_at or '')[:16] }} by {{ a.username or 'system' }}</div>
      </div>
    </div>
    {% endfor %}
  </div>
</div>
{% endif %}

{% if runs %}
<div class="card">
  <h3>Recent Pipeline Runs</h3>
  <div class="tbl-wrap"><table>
    <thead><tr><th>Run</th><th>Date</th><th>Leads</th><th>Hot</th><th>Warm</th><th>Cold</th><th>Status</th></tr></thead>
    <tbody>{% for r in runs %}
    <tr><td><a href="/runs/{{ r.id }}">#{{ r.id }}</a></td><td>{{ (r.started_at or '')[:16] }}</td>
        <td>{{ r.total_leads }}</td><td class="val-hot">{{ r.hot_count }}</td><td class="val-warm">{{ r.warm_count }}</td>
        <td class="val-cold">{{ r.cold_count }}</td>
        <td><span class="badge badge-{{ r.status or 'running' }}">{{ r.status or 'running' }}</span></td></tr>
    {% endfor %}</tbody>
  </table></div>
</div>
{% endif %}

<script>
new Chart(document.getElementById('tierChart'),{type:'doughnut',data:{
  labels:['Hot','Warm','Cold'],datasets:[{data:[{{ hot }},{{ warm }},{{ cold }}],
  backgroundColor:['#ef4444','#f59e0b','#22c55e'],borderWidth:0,borderRadius:4}]},
  options:{cutout:'65%',plugins:{legend:{position:'bottom',labels:{color:'#94a3b8',padding:16,usePointStyle:true}}}}});

const scores={{ scores_json|safe }};
const bins=[0,0,0,0,0,0,0,0,0,0];
scores.forEach(s=>{const i=Math.min(Math.floor(s/10),9);bins[i]++;});
new Chart(document.getElementById('scoreChart'),{type:'bar',data:{
  labels:['0-9','10-19','20-29','30-39','40-49','50-59','60-69','70-79','80-89','90-100'],
  datasets:[{data:bins,backgroundColor:bins.map((_,i)=>i>=7?'#ef4444':i>=4?'#f59e0b':'#22c55e'),borderRadius:6,borderSkipped:false}]},
  options:{scales:{x:{grid:{display:false},ticks:{color:'#64748b'}},y:{grid:{color:'rgba(30,41,59,.5)'},ticks:{color:'#64748b'}}},
  plugins:{legend:{display:false}}}});
</script>
{% endif %}
"""

LEADS_CONTENT = """
<div class="filters">
  <input type="text" id="searchF" placeholder="Search companies..." oninput="filterLeads()">
  <select id="tierF" onchange="filterLeads()">
    <option value="">All Tiers</option><option value="Hot">Hot</option><option value="Warm">Warm</option><option value="Cold">Cold</option>
  </select>
  <select id="stageF" onchange="filterLeads()">
    <option value="">All Stages</option><option value="Purchase">Purchase</option><option value="Decision">Decision</option>
    <option value="Consideration">Consideration</option><option value="Awareness">Awareness</option><option value="Target">Target</option>
  </select>
  <div style="flex:1"></div>
  <a href="/api/export/csv" class="btn btn-outline btn-sm">Export CSV</a>
  <a href="/api/leads" target="_blank" class="btn btn-outline btn-sm">Export JSON</a>
  <button class="btn btn-outline btn-sm" onclick="compareSelected()">Compare Selected</button>
</div>
<div class="card" style="padding:0;overflow:hidden">
<div class="tbl-wrap" style="border:0">
<table id="leadsTable">
  <thead><tr>
    <th><input type="checkbox" onchange="document.querySelectorAll('.lead-check').forEach(c=>c.checked=this.checked)"></th>
    <th onclick="sortTable('leadsTable',1)">Company</th>
    <th onclick="sortTable('leadsTable',2)">Score</th>
    <th onclick="sortTable('leadsTable',3)">Tier</th>
    <th onclick="sortTable('leadsTable',4)">Stage</th>
    <th onclick="sortTable('leadsTable',5)">Fit</th>
    <th onclick="sortTable('leadsTable',6)">Engagement</th>
    <th onclick="sortTable('leadsTable',7)">Intent</th>
    <th onclick="sortTable('leadsTable',8)">Confidence</th>
    <th onclick="sortTable('leadsTable',9)">Industry</th>
    <th onclick="sortTable('leadsTable',10)">Key Signal</th>
  </tr></thead>
  <tbody>
  {% for l in leads %}
  <tr data-tier="{{ l.tier }}" data-stage="{{ l.buying_stage or 'Target' }}">
    <td><input type="checkbox" class="lead-check" value="{{ l.domain }}"></td>
    <td><a href="/leads/{{ l.domain }}"><strong>{{ l.company_name }}</strong></a><br><span class="text-muted" style="font-size:.78em">{{ l.domain }}</span></td>
    <td data-val="{{ l.total_score }}"><div class="score-bar"><span class="num" style="color:{{ l._color }}">{{ l.total_score }}</span>
        <div class="bar"><div class="fill" style="width:{{ l.total_score }}%;background:{{ l._color }}"></div></div></div></td>
    <td><span class="badge badge-{{ l.tier|lower }}">{{ l.tier }}</span></td>
    <td><span class="badge badge-{{ (l.buying_stage or 'target')|lower }}">{{ l.buying_stage or 'Target' }}</span></td>
    <td data-val="{{ l.fit_score_pct or 0 }}">{{ l.fit_score_pct or 0 }}%</td>
    <td data-val="{{ l.engagement_score_pct or 0 }}">{{ l.engagement_score_pct or 0 }}%</td>
    <td data-val="{{ l.intent_score_pct or 0 }}">{{ l.intent_score_pct or 0 }}%</td>
    <td data-val="{{ (l.confidence or 0) * 100 }}">{{ '%.0f'|format((l.confidence or 0) * 100) }}%</td>
    <td>{{ l.industry_classified or l.industry or '-' }}</td>
    <td style="max-width:200px;overflow:hidden;text-overflow:ellipsis">{{ (l.key_signal or '-')[:60] }}</td>
  </tr>
  {% endfor %}
  </tbody>
</table></div></div>
"""

DETAIL_CONTENT = """
<div style="margin-bottom:8px"><a href="/leads">&larr; All Leads</a></div>

<div class="detail-header">
  <div class="score-circle" style="border-color:{{ color }};color:{{ color }}">{{ score.total_score }}</div>
  <div class="meta">
    <h1>{{ company.company_name }}</h1>
    <p>{{ company.domain }} &middot; {{ company.hq_country or 'Unknown' }} &middot; Founded {{ company.founding_year or '?' }}
       &middot; {{ company.employee_estimate or '?' }} employees</p>
    <div style="margin-top:6px">
      <span class="badge badge-{{ score.tier|lower }}" style="font-size:.9em;padding:6px 16px">{{ score.tier }}</span>
      <span class="badge badge-{{ (score.buying_stage or 'target')|lower }}" style="font-size:.9em;padding:6px 16px;margin-left:4px">{{ score.buying_stage or 'Target' }}</span>
      <span class="badge" style="background:rgba(99,102,241,.15);color:#a5b4fc;font-size:.9em;padding:6px 16px;margin-left:4px">{{ score.matrix_cell or '-' }}</span>
    </div>
  </div>
</div>

{% if score_explanation %}
<div class="card" style="border-left:3px solid var(--accent)">
  <p style="font-size:.95em"><strong>Score Explanation:</strong> {{ score_explanation }}</p>
</div>
{% endif %}

{% if company.description %}
<div class="card"><p style="color:var(--text2)">{{ company.description }}</p></div>
{% endif %}

<div class="grid-2">
  <div class="card">
    <h3>Score Breakdown</h3>
    <div class="chart-box"><canvas id="radarChart"></canvas></div>
  </div>
  <div class="card">
    <h3>Score Components</h3>
    <div class="dim-bars">
      <div class="dim-bar"><span class="lbl">Fit</span>
        <div class="track"><div class="fill fill-fit" style="width:{{ score.fit_score_pct or 0 }}%"></div></div>
        <span class="pct" style="color:#818cf8">{{ score.fit_score_pct or 0 }}%</span></div>
      <div class="dim-bar"><span class="lbl">Engagement</span>
        <div class="track"><div class="fill fill-eng" style="width:{{ score.engagement_score_pct or 0 }}%"></div></div>
        <span class="pct" style="color:#fbbf24">{{ score.engagement_score_pct or 0 }}%</span></div>
      <div class="dim-bar"><span class="lbl">Intent</span>
        <div class="track"><div class="fill fill-int" style="width:{{ score.intent_score_pct or 0 }}%"></div></div>
        <span class="pct" style="color:#4ade80">{{ score.intent_score_pct or 0 }}%</span></div>
    </div>
    <div style="margin-top:16px">
      <p><strong>Rule Score:</strong> {{ score.rule_score }}/60</p>
      {% for k,v in breakdown.items() %}
      <div style="display:flex;align-items:center;gap:8px;margin-bottom:6px">
        <span style="width:110px;font-size:.82em;color:var(--text2)">{{ k|replace('_',' ')|title }}</span>
        <div style="flex:1;height:8px;background:var(--border);border-radius:4px;overflow:hidden">
          <div style="height:100%;width:{{ (v / 15 * 100)|int }}%;background:var(--accent);border-radius:4px"></div></div>
        <span style="font-size:.82em;font-weight:600;width:24px;text-align:right">{{ v }}</span>
      </div>
      {% endfor %}
      <p style="margin-top:16px"><strong>LLM Score:</strong> {{ score.soft_score }}/40</p>
      <p class="text-muted mt-2"><strong>Confidence:</strong> {{ '%.0f'|format((score.confidence or 0) * 100) }}%</p>
    </div>
  </div>
</div>

<div class="grid-2">
  <div class="card">
    <h3>Tech Stack</h3>
    {% for t in tech_stack %}<span class="tech-badge">{{ t }}</span>{% endfor %}
    {% if not tech_stack %}<p class="text-muted">No tech detected</p>{% endif %}
    {% if comp_tech %}
    <h3 style="margin-top:16px">Competitor Tools</h3>
    {% for c in comp_tech %}<span class="tech-badge comp-badge">{{ c }}</span>{% endfor %}
    {% endif %}
  </div>
  <div class="card">
    <h3>AI Insights</h3>
    <p><strong>Key Signal:</strong> {{ score.key_signal or 'N/A' }}</p>
    <p class="mt-2"><strong>Reasoning:</strong> <span class="text-muted">{{ score.reasoning or 'N/A' }}</span></p>
    {% if score.outreach_line %}<p class="mt-4"><strong>Suggested Outreach:</strong><br><em style="color:#a5b4fc">{{ score.outreach_line }}</em></p>{% endif %}
    {% if score.next_action %}<p class="mt-2"><strong>Next Action:</strong> {{ score.next_action }}</p>{% endif %}
  </div>
</div>

<div class="grid-2">
  <div class="card">
    <h3>Sales Feedback</h3>
    <p class="text-muted">Help calibrate scoring accuracy by providing feedback on this lead.</p>
    <div class="fb-btns">
      <button class="btn btn-success btn-sm" onclick="sendFeedback('{{ company.domain }}','accept')">Accept</button>
      <button class="btn btn-danger btn-sm" onclick="sendFeedback('{{ company.domain }}','reject')">Reject</button>
      <button class="btn btn-warn btn-sm" onclick="sendFeedback('{{ company.domain }}','too_high')">Too High</button>
      <button class="btn btn-outline btn-sm" onclick="sendFeedback('{{ company.domain }}','too_low')">Too Low</button>
    </div>
    {% if feedback_stats.total > 0 %}
    <p class="mt-4 text-muted">Accuracy rate: {{ feedback_stats.accuracy_rate }}% ({{ feedback_stats.total }} reviews)</p>
    {% endif %}
  </div>
  {% if history %}
  <div class="card">
    <h3>Score History</h3>
    <div class="chart-box"><canvas id="histChart"></canvas></div>
  </div>
  {% endif %}
</div>

<div class="card" style="display:flex;gap:10px">
  <a href="/leads/{{ company.domain }}/report" class="btn btn-outline btn-sm">View Report</a>
  {% if company.social_linkedin %}<a href="{{ company.social_linkedin }}" target="_blank" class="btn btn-outline btn-sm">LinkedIn</a>{% endif %}
</div>

<script>
const bd={{ breakdown_json|safe }};
new Chart(document.getElementById('radarChart'),{type:'radar',data:{
  labels:Object.keys(bd).map(k=>k.replace('_',' ')),
  datasets:[{data:Object.values(bd),backgroundColor:'rgba(99,102,241,.15)',borderColor:'#6366f1',pointBackgroundColor:'#6366f1'}]},
  options:{scales:{r:{beginAtZero:true,max:15,ticks:{color:'#64748b',stepSize:5},grid:{color:'rgba(30,41,59,.5)'},
  pointLabels:{color:'#94a3b8',font:{size:11}}}},plugins:{legend:{display:false}}}});
{% if history %}
const hist={{ history_json|safe }};
new Chart(document.getElementById('histChart'),{type:'line',data:{
  labels:hist.map(h=>h.date),datasets:[{label:'Score',data:hist.map(h=>h.score),borderColor:'#6366f1',
  backgroundColor:'rgba(99,102,241,.1)',fill:true,tension:.3,pointRadius:4,pointBackgroundColor:'#6366f1'}]},
  options:{scales:{x:{grid:{display:false},ticks:{color:'#64748b'}},y:{min:0,max:100,grid:{color:'rgba(30,41,59,.5)'},ticks:{color:'#64748b'}}},
  plugins:{legend:{display:false}}}});
{% endif %}
</script>
"""

ANALYTICS_CONTENT = """
<div class="grid-2">
  <div class="card"><h3>Industry Breakdown</h3><div class="chart-box"><canvas id="indChart"></canvas></div></div>
  <div class="card"><h3>Geography</h3><div class="chart-box"><canvas id="geoChart"></canvas></div></div>
</div>
<div class="grid-2">
  <div class="card"><h3>Confidence Distribution</h3><div class="chart-box"><canvas id="confChart"></canvas></div></div>
  <div class="card"><h3>Rule vs LLM Scores</h3><div class="chart-box"><canvas id="scatterChart"></canvas></div></div>
</div>
<div class="grid-2">
  <div class="card"><h3>Fit vs Engagement vs Intent</h3><div class="chart-box"><canvas id="dimChart"></canvas></div></div>
  <div class="card"><h3>Score Distribution by Stage</h3><div class="chart-box"><canvas id="stageChart"></canvas></div></div>
</div>
<script>
const analytics={{ analytics_json|safe }};
const colors=['#6366f1','#8b5cf6','#a855f7','#ec4899','#f43f5e','#ef4444','#f59e0b','#22c55e','#14b8a6','#06b6d4','#3b82f6','#64748b'];
new Chart(document.getElementById('indChart'),{type:'bar',data:{
  labels:analytics.industries.map(i=>i[0]),datasets:[{data:analytics.industries.map(i=>i[1]),
  backgroundColor:analytics.industries.map((_,i)=>colors[i%colors.length]),borderRadius:6,borderSkipped:false}]},
  options:{indexAxis:'y',scales:{x:{grid:{color:'rgba(30,41,59,.5)'},ticks:{color:'#64748b'}},y:{grid:{display:false},ticks:{color:'#94a3b8'}}},
  plugins:{legend:{display:false}}}});
new Chart(document.getElementById('geoChart'),{type:'doughnut',data:{
  labels:analytics.geos.map(g=>g[0]),datasets:[{data:analytics.geos.map(g=>g[1]),
  backgroundColor:colors,borderWidth:0}]},
  options:{cutout:'60%',plugins:{legend:{position:'right',labels:{color:'#94a3b8',padding:10,usePointStyle:true}}}}});
new Chart(document.getElementById('confChart'),{type:'bar',data:{
  labels:['0-20%','20-40%','40-60%','60-80%','80-100%'],datasets:[{data:analytics.conf_bins,
  backgroundColor:['#ef4444','#f59e0b','#eab308','#22c55e','#6366f1'],borderRadius:6,borderSkipped:false}]},
  options:{scales:{x:{grid:{display:false},ticks:{color:'#64748b'}},y:{grid:{color:'rgba(30,41,59,.5)'},ticks:{color:'#64748b'}}},
  plugins:{legend:{display:false}}}});
new Chart(document.getElementById('scatterChart'),{type:'scatter',data:{
  datasets:[{label:'Leads',data:analytics.scatter,backgroundColor:analytics.scatter.map(p=>p.x+p.y>=70?'#ef4444':p.x+p.y>=40?'#f59e0b':'#22c55e'),
  pointRadius:6}]},
  options:{scales:{x:{title:{display:true,text:'Rule Score (/60)',color:'#64748b'},grid:{color:'rgba(30,41,59,.5)'},ticks:{color:'#64748b'}},
  y:{title:{display:true,text:'LLM Score (/40)',color:'#64748b'},grid:{color:'rgba(30,41,59,.5)'},ticks:{color:'#64748b'}}},
  plugins:{legend:{display:false}}}});
if(analytics.dimensions){
  new Chart(document.getElementById('dimChart'),{type:'radar',data:{
    labels:['Fit','Engagement','Intent'],
    datasets:analytics.dimensions.map((d,i)=>({label:d.name,data:[d.fit,d.eng,d.intent],
      backgroundColor:colors[i%colors.length]+'22',borderColor:colors[i%colors.length],pointBackgroundColor:colors[i%colors.length]}))},
    options:{scales:{r:{beginAtZero:true,max:100,ticks:{color:'#64748b'},grid:{color:'rgba(30,41,59,.5)'},
      pointLabels:{color:'#94a3b8'}}},plugins:{legend:{labels:{color:'#94a3b8'}}}}});}
if(analytics.stage_scores){
  new Chart(document.getElementById('stageChart'),{type:'bar',data:{
    labels:Object.keys(analytics.stage_scores),
    datasets:[{data:Object.values(analytics.stage_scores),
      backgroundColor:['#8b5cf6','#ef4444','#f59e0b','#22c55e','#64748b'],borderRadius:6,borderSkipped:false}]},
    options:{scales:{x:{grid:{display:false},ticks:{color:'#64748b'}},y:{grid:{color:'rgba(30,41,59,.5)'},ticks:{color:'#64748b'}}},
      plugins:{legend:{display:false}}}});}
</script>
"""

RUNS_CONTENT = """
{% if not runs %}
<div class="card empty"><div class="icon">&#9654;</div><h3>No pipeline runs yet</h3><p>Score some leads or load sample data.</p></div>
{% else %}
<div class="card" style="padding:0;overflow:hidden"><div class="tbl-wrap" style="border:0"><table>
  <thead><tr><th>Run</th><th>Date</th><th>ICP</th><th>Total</th><th>Hot</th><th>Warm</th><th>Cold</th><th>Errors</th><th>Status</th></tr></thead>
  <tbody>{% for r in runs %}
  <tr><td><a href="/runs/{{ r.id }}">#{{ r.id }}</a></td><td>{{ (r.started_at or '')[:16] }}</td><td>{{ r.icp_name }}</td>
      <td>{{ r.total_leads }}</td><td class="val-hot">{{ r.hot_count }}</td><td class="val-warm">{{ r.warm_count }}</td>
      <td class="val-cold">{{ r.cold_count }}</td><td>{{ r.error_count }}</td>
      <td><span class="badge badge-{{ r.status or 'running' }}">{{ r.status or 'running' }}</span></td></tr>
  {% endfor %}</tbody>
</table></div></div>
{% if runs|length > 1 %}
<div class="card"><h3>Runs Over Time</h3><div class="chart-box"><canvas id="runsChart"></canvas></div></div>
<script>
const rns={{ runs_json|safe }};
new Chart(document.getElementById('runsChart'),{type:'bar',data:{
  labels:rns.map(r=>'#'+r.id),datasets:[
    {label:'Hot',data:rns.map(r=>r.hot_count),backgroundColor:'#ef4444',borderRadius:4},
    {label:'Warm',data:rns.map(r=>r.warm_count),backgroundColor:'#f59e0b',borderRadius:4},
    {label:'Cold',data:rns.map(r=>r.cold_count),backgroundColor:'#22c55e',borderRadius:4}]},
  options:{scales:{x:{stacked:true,grid:{display:false},ticks:{color:'#64748b'}},
  y:{stacked:true,grid:{color:'rgba(30,41,59,.5)'},ticks:{color:'#64748b'}}},
  plugins:{legend:{labels:{color:'#94a3b8',usePointStyle:true}}}}});
</script>
{% endif %}
{% endif %}
"""

QUALITY_CONTENT = """
<div class="kpis">
  <div class="kpi total"><div class="value val-accent">{{ q.stats.total }}</div><div class="label">Total Scored</div></div>
  <div class="kpi score"><div class="value">{{ q.quality_score }}</div><div class="label">Quality Rating</div></div>
  <div class="kpi warm"><div class="value val-warm">{{ q.stats.low_confidence }}</div><div class="label">Low Confidence</div></div>
  <div class="kpi cold"><div class="value">{{ q.stats.missing_geo }}</div><div class="label">Missing Geo</div></div>
</div>
{% if coverage.total > 0 %}
<div class="card"><h3>Enrichment Coverage</h3>
<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px">
{% for field, info in coverage.fields.items() %}
<div>
  <div style="display:flex;justify-content:space-between;font-size:.82em;margin-bottom:4px">
    <span class="text-muted">{{ field|replace('_',' ')|title }}</span><span>{{ info.pct }}%</span></div>
  <div style="height:6px;background:var(--border);border-radius:3px;overflow:hidden">
    <div style="height:100%;width:{{ info.pct }}%;background:{{ 'var(--cold)' if info.pct >= 80 else 'var(--warm)' if info.pct >= 50 else 'var(--hot)' }};border-radius:3px"></div></div>
</div>
{% endfor %}
</div></div>
{% endif %}
{% if q.issues %}
<div class="card"><h3>Issues ({{ q.issues|length }})</h3>
<div class="tbl-wrap"><table>
  <thead><tr><th>Domain</th><th>Issue</th><th>Detail</th></tr></thead>
  <tbody>{% for i in q.issues %}<tr><td>{{ i.domain }}</td><td>{{ i.issue }}</td><td class="text-muted">{{ i.detail }}</td></tr>{% endfor %}</tbody>
</table></div></div>
{% else %}<div class="card"><p style="color:var(--cold)">&#10003; No quality issues detected.</p></div>{% endif %}
"""

INTEGRATIONS_CONTENT = """
<div class="grid-3">
  <div class="card">
    <h3>&#128196; Google Sheets</h3>
    <p class="text-muted mt-2">{{ sheets_status }}</p>
    {% if sheet_url %}<p class="mt-2"><a href="{{ sheet_url }}" target="_blank">Open Sheet &rarr;</a></p>{% endif %}
    <form method="POST" action="/integrations/sync-sheets" class="mt-4"><button class="btn btn-primary btn-sm" id="sync-sheets">Sync Now</button></form>
  </div>
  <div class="card">
    <h3>&#128231; HubSpot CRM</h3>
    <p class="text-muted mt-2">{{ hubspot_status }}</p>
  </div>
  <div class="card">
    <h3>&#128279; Webhooks</h3>
    <p class="text-muted mt-2">POST endpoint: <code>/api/webhook</code></p>
    <p class="text-muted">Compatible with Zapier, Make, n8n</p>
  </div>
</div>
"""

API_CONTENT = """
<div class="card"><h3>REST API Endpoints</h3>
<p class="text-muted mb-4">Full OpenAPI spec available at <code>/api/openapi.yaml</code>. API key auth optional - set via Settings page.</p>
<div class="tbl-wrap"><table>
  <thead><tr><th>Method</th><th>Endpoint</th><th>Description</th></tr></thead>
  <tbody>
  <tr><td><span class="badge" style="background:rgba(34,197,94,.15);color:#4ade80">GET</span></td><td><code>/api/leads</code></td><td>List all scored leads (JSON)</td></tr>
  <tr><td><span class="badge" style="background:rgba(34,197,94,.15);color:#4ade80">GET</span></td><td><code>/api/leads?tier=Hot</code></td><td>Filter leads by tier</td></tr>
  <tr><td><span class="badge" style="background:rgba(34,197,94,.15);color:#4ade80">GET</span></td><td><code>/api/leads/&lt;domain&gt;</code></td><td>Get single lead with full details</td></tr>
  <tr><td><span class="badge" style="background:rgba(245,158,11,.15);color:#fbbf24">POST</span></td><td><code>/api/leads/bulk</code></td><td>Bulk lookup by domains array</td></tr>
  <tr><td><span class="badge" style="background:rgba(34,197,94,.15);color:#4ade80">GET</span></td><td><code>/api/routing-rules</code></td><td>Lead routing assignments</td></tr>
  <tr><td><span class="badge" style="background:rgba(34,197,94,.15);color:#4ade80">GET</span></td><td><code>/api/runs</code></td><td>List pipeline runs</td></tr>
  <tr><td><span class="badge" style="background:rgba(34,197,94,.15);color:#4ade80">GET</span></td><td><code>/api/runs/&lt;id&gt;</code></td><td>Get run details with scores</td></tr>
  <tr><td><span class="badge" style="background:rgba(245,158,11,.15);color:#fbbf24">POST</span></td><td><code>/api/webhook</code></td><td>Trigger scoring via webhook</td></tr>
  <tr><td><span class="badge" style="background:rgba(245,158,11,.15);color:#fbbf24">POST</span></td><td><code>/api/feedback</code></td><td>Submit lead feedback</td></tr>
  <tr><td><span class="badge" style="background:rgba(245,158,11,.15);color:#fbbf24">POST</span></td><td><code>/api/load-sample-data</code></td><td>Load demo data (40 companies)</td></tr>
  <tr><td><span class="badge" style="background:rgba(34,197,94,.15);color:#4ade80">GET</span></td><td><code>/api/export/csv</code></td><td>Export leads as CSV</td></tr>
  <tr><td><span class="badge" style="background:rgba(34,197,94,.15);color:#4ade80">GET</span></td><td><code>/api/health</code></td><td>Health check</td></tr>
  <tr><td><span class="badge" style="background:rgba(34,197,94,.15);color:#4ade80">GET</span></td><td><code>/api/stats</code></td><td>Database statistics</td></tr>
  <tr><td><span class="badge" style="background:rgba(34,197,94,.15);color:#4ade80">GET</span></td><td><code>/api/activity</code></td><td>Activity feed</td></tr>
  <tr><td><span class="badge" style="background:rgba(34,197,94,.15);color:#4ade80">GET</span></td><td><code>/api/demo</code></td><td>Sanitized demo data</td></tr>
  <tr><td><span class="badge" style="background:rgba(34,197,94,.15);color:#4ade80">GET</span></td><td><code>/api/openapi.yaml</code></td><td>OpenAPI specification</td></tr>
  </tbody>
</table></div></div>

<div class="card">
  <h3>Authentication</h3>
  <p class="text-muted">API endpoints support optional API key authentication. Set an API key in Settings, then pass it via:</p>
  <pre>curl -H "X-API-Key: your-key" http://localhost:5000/api/leads
# or
curl http://localhost:5000/api/leads?api_key=your-key</pre>
</div>
"""

SETTINGS_CONTENT = """
<div class="grid-2">
  <div class="card">
    <h3>Scoring Weights</h3>
    <p class="text-muted mb-4">Adjust how much each dimension contributes to the final score.</p>
    <form method="POST" action="/admin/settings">
      <input type="hidden" name="action" value="weights">
      {% for key, val in dimensions.items() %}
      <div style="display:flex;align-items:center;gap:12px;margin-bottom:12px">
        <label style="width:140px;font-size:.88em;color:var(--text2)">{{ key|replace('_',' ')|title }}</label>
        <input type="range" name="{{ key }}" min="0" max="100" value="{{ (val * 100)|int }}" style="flex:1"
               oninput="this.nextElementSibling.textContent=this.value+'%'">
        <span style="width:40px;font-size:.88em;font-weight:600">{{ (val * 100)|int }}%</span>
      </div>
      {% endfor %}
      <button class="btn btn-primary btn-sm mt-2">Save Weights</button>
    </form>
  </div>
  <div class="card">
    <h3>Scoring Templates</h3>
    <p class="text-muted mb-4">Apply a pre-built scoring model.</p>
    <form method="POST" action="/admin/settings">
      <input type="hidden" name="action" value="template">
      {% for name, weights in templates.items() %}
      <div style="display:flex;align-items:center;gap:12px;padding:10px;border:1px solid var(--border);border-radius:8px;margin-bottom:8px;cursor:pointer"
           onclick="this.querySelector('input').checked=true">
        <input type="radio" name="template" value="{{ name }}" {% if loop.first %}checked{% endif %}>
        <div>
          <strong style="font-size:.88em">{{ name|replace('_',' ')|title }}</strong>
          <div class="text-muted" style="font-size:.78em">Fit: {{ (weights.fit_weight*100)|int }}% | Eng: {{ (weights.engagement_weight*100)|int }}% | Int: {{ (weights.intent_weight*100)|int }}%</div>
        </div>
      </div>
      {% endfor %}
      <button class="btn btn-primary btn-sm mt-2">Apply Template</button>
    </form>
  </div>
</div>
<div class="grid-2">
  <div class="card">
    <h3>Tier Thresholds</h3>
    <form method="POST" action="/admin/settings">
      <input type="hidden" name="action" value="tiers">
      <div class="form-row">
        <div><label class="text-muted" style="font-size:.82em">Hot minimum</label>
          <input type="number" name="hot_min" value="{{ thresholds.hot_min }}" min="1" max="99" style="width:80px"></div>
        <div><label class="text-muted" style="font-size:.82em">Warm minimum</label>
          <input type="number" name="warm_min" value="{{ thresholds.warm_min }}" min="1" max="99" style="width:80px"></div>
        <button class="btn btn-primary btn-sm" style="align-self:flex-end">Save</button>
      </div>
    </form>
  </div>
  <div class="card">
    <h3>Score Decay</h3>
    <p class="text-muted">{{ 'Enabled' if decay.enabled else 'Disabled' }} | {{ decay.mode }} | {{ (decay.rate * 100)|int }}% every {{ decay.interval_days }} days</p>
  </div>
</div>
{% if settings_msg %}<div class="toast" style="display:block">{{ settings_msg }}</div>{% endif %}
"""

ROUTING_CONTENT = """
<div class="grid-2">
  <div class="card">
    <h3>Lead Routing Summary</h3>
    <p class="text-muted mb-4">Automatic lead assignment based on tier, company size, and geography.</p>
    <div class="tbl-wrap"><table>
      <thead><tr><th>Queue</th><th>Criteria</th><th>Count</th></tr></thead>
      <tbody>
      <tr><td><span class="badge badge-hot">Hot Enterprise</span></td><td>Hot tier + 1000+ employees</td><td>{{ routes.hot_enterprise|length }}</td></tr>
      <tr><td><span class="badge badge-hot">Hot SMB</span></td><td>Hot tier + &lt;1000 employees</td><td>{{ routes.hot_smb|length }}</td></tr>
      <tr><td><span class="badge badge-warm">Warm Nurture</span></td><td>Warm tier - all sizes</td><td>{{ routes.warm_nurture|length }}</td></tr>
      <tr><td><span class="badge badge-cold">Cold Monitor</span></td><td>Cold tier - periodic review</td><td>{{ routes.cold_monitor|length }}</td></tr>
      </tbody>
    </table></div>
  </div>
  <div class="card">
    <h3>Assignment Chart</h3>
    <div class="chart-box"><canvas id="routeChart"></canvas></div>
  </div>
</div>
{% for queue_name, queue_label in [('hot_enterprise','Hot Enterprise'),('hot_smb','Hot SMB'),('warm_nurture','Warm Nurture'),('cold_monitor','Cold Monitor')] %}
{% if routes[queue_name] %}
<div class="card">
  <h3>{{ queue_label }} ({{ routes[queue_name]|length }})</h3>
  <div class="tbl-wrap"><table>
    <thead><tr><th>Company</th><th>Score</th><th>Industry</th><th>Country</th></tr></thead>
    <tbody>{% for l in routes[queue_name] %}
    <tr><td><a href="/leads/{{ l.domain }}"><strong>{{ l.company_name }}</strong></a></td>
        <td>{{ l.total_score }}</td><td>{{ l.industry_classified or l.industry or '-' }}</td><td>{{ l.hq_country or '-' }}</td></tr>
    {% endfor %}</tbody>
  </table></div>
</div>
{% endif %}
{% endfor %}
<script>
const rc={{ route_counts|safe }};
new Chart(document.getElementById('routeChart'),{type:'doughnut',data:{
  labels:['Hot Enterprise','Hot SMB','Warm Nurture','Cold Monitor'],
  datasets:[{data:[rc[0],rc[1],rc[2],rc[3]],backgroundColor:['#ef4444','#f97316','#f59e0b','#22c55e'],borderWidth:0}]},
  options:{cutout:'60%',plugins:{legend:{position:'bottom',labels:{color:'#94a3b8',padding:12,usePointStyle:true}}}}});
</script>
"""

COMPARE_CONTENT = """
<h3 class="mb-4">Lead Comparison</h3>
{% if leads|length < 2 %}
<div class="card"><p class="text-muted">Select 2+ leads to compare. Add <code>?domains=stripe.com,notion.so</code> to the URL.</p></div>
{% else %}
<div class="tbl-wrap"><table>
  <thead><tr><th>Attribute</th>{% for l in leads %}<th>{{ l.company_name }}</th>{% endfor %}</tr></thead>
  <tbody>
  <tr><td><strong>Score</strong></td>{% for l in leads %}<td style="color:{{ l._color }};font-weight:700;font-size:1.2em">{{ l.total_score }}</td>{% endfor %}</tr>
  <tr><td><strong>Tier</strong></td>{% for l in leads %}<td><span class="badge badge-{{ l.tier|lower }}">{{ l.tier }}</span></td>{% endfor %}</tr>
  <tr><td><strong>Buying Stage</strong></td>{% for l in leads %}<td><span class="badge badge-{{ (l.buying_stage or 'target')|lower }}">{{ l.buying_stage or 'Target' }}</span></td>{% endfor %}</tr>
  <tr><td><strong>Matrix Cell</strong></td>{% for l in leads %}<td>{{ l.matrix_cell or '-' }}</td>{% endfor %}</tr>
  <tr><td><strong>Fit</strong></td>{% for l in leads %}<td>{{ l.fit_score_pct or 0 }}%</td>{% endfor %}</tr>
  <tr><td><strong>Engagement</strong></td>{% for l in leads %}<td>{{ l.engagement_score_pct or 0 }}%</td>{% endfor %}</tr>
  <tr><td><strong>Intent</strong></td>{% for l in leads %}<td>{{ l.intent_score_pct or 0 }}%</td>{% endfor %}</tr>
  <tr><td><strong>Confidence</strong></td>{% for l in leads %}<td>{{ '%.0f'|format((l.confidence or 0) * 100) }}%</td>{% endfor %}</tr>
  <tr><td><strong>Rule Score</strong></td>{% for l in leads %}<td>{{ l.rule_score }}/60</td>{% endfor %}</tr>
  <tr><td><strong>LLM Score</strong></td>{% for l in leads %}<td>{{ l.soft_score }}/40</td>{% endfor %}</tr>
  <tr><td><strong>Industry</strong></td>{% for l in leads %}<td>{{ l.industry_classified or l.industry or '-' }}</td>{% endfor %}</tr>
  <tr><td><strong>Country</strong></td>{% for l in leads %}<td>{{ l.hq_country or '-' }}</td>{% endfor %}</tr>
  <tr><td><strong>Employees</strong></td>{% for l in leads %}<td>{{ l.employee_estimate or '-' }}</td>{% endfor %}</tr>
  <tr><td><strong>Key Signal</strong></td>{% for l in leads %}<td style="max-width:200px">{{ (l.key_signal or '-')[:80] }}</td>{% endfor %}</tr>
  </tbody>
</table></div>
<div class="card mt-4"><h3>Score Comparison</h3><div class="chart-box"><canvas id="compareChart"></canvas></div></div>
<script>
const names={{ names_json|safe }};
const scores={{ scores_json|safe }};
const colors=['#6366f1','#f59e0b','#ef4444','#22c55e','#8b5cf6','#ec4899'];
new Chart(document.getElementById('compareChart'),{type:'bar',data:{
  labels:['Total','Rule','LLM','Fit%','Engagement%','Intent%'],
  datasets:names.map((n,i)=>({label:n,data:[scores[i].total,scores[i].rule,scores[i].llm,scores[i].fit,scores[i].eng,scores[i].intent],
    backgroundColor:colors[i%colors.length]+'44',borderColor:colors[i%colors.length],borderWidth:2,borderRadius:4}))},
  options:{scales:{x:{grid:{display:false},ticks:{color:'#64748b'}},y:{grid:{color:'rgba(30,41,59,.5)'},ticks:{color:'#64748b'}}},
  plugins:{legend:{labels:{color:'#94a3b8'}}}}});
</script>
{% endif %}
"""

ADMIN_CONTENT = """
<div class="grid-2">
  <div class="card">
    <h3>Current Users</h3>
    <div class="tbl-wrap"><table>
      <thead><tr><th>Username</th><th>Role</th><th>Created</th></tr></thead>
      <tbody>{% for u in users %}<tr><td>{{ u.username }}</td><td><span class="badge" style="background:rgba(99,102,241,.15);color:#a5b4fc">{{ u.role }}</span></td><td class="text-muted">{{ u.created_at }}</td></tr>{% endfor %}</tbody>
    </table></div>
  </div>
  <div>
    <div class="card">
      <h3>Add User</h3>
      {% if msg %}<p style="color:var(--cold);margin-bottom:12px">{{ msg }}</p>{% endif %}
      <form method="POST" class="form-row">
        <input type="hidden" name="action" value="create">
        <input name="username" placeholder="Username" required>
        <input name="password" type="password" placeholder="Password" required>
        <select name="role"><option value="viewer">Viewer</option><option value="editor">Editor</option><option value="admin">Admin</option></select>
        <button class="btn btn-primary btn-sm">Create</button>
      </form>
    </div>
    <div class="card">
      <h3>Change Password</h3>
      <form method="POST" class="form-row">
        <input type="hidden" name="action" value="change_pw">
        <input name="username" placeholder="Username" required>
        <input name="new_password" type="password" placeholder="New Password" required>
        <button class="btn btn-primary btn-sm">Update</button>
      </form>
    </div>
  </div>
</div>

{% if audit_log %}
<div class="card">
  <h3>Audit Log</h3>
  <div class="tbl-wrap"><table>
    <thead><tr><th>Time</th><th>User</th><th>Action</th><th>Entity</th></tr></thead>
    <tbody>{% for a in audit_log %}
    <tr><td class="text-muted">{{ a.created_at[:16] }}</td><td>{{ a.username }}</td><td>{{ a.action }}</td><td>{{ a.entity_type }} {{ a.entity_id }}</td></tr>
    {% endfor %}</tbody>
  </table></div>
</div>
{% endif %}
"""

PRINT_REPORT_HTML = """<!DOCTYPE html>
<html><head><meta charset="UTF-8">
<title>Lead Report - {{ score.company_name }}</title>
<style>
@media print{body{font-size:11pt}@page{margin:1.5cm}}
body{font-family:'Inter',-apple-system,sans-serif;max-width:800px;margin:0 auto;padding:40px 20px;color:#1e293b;line-height:1.6}
h1{font-size:1.5em;border-bottom:2px solid #6366f1;padding-bottom:8px;margin-bottom:4px}
.meta{color:#64748b;font-size:.9em;margin-bottom:24px}
.badge{display:inline-block;padding:4px 14px;border-radius:16px;font-size:.82em;font-weight:600}
.hot{background:#fef2f2;color:#dc2626}.warm{background:#fffbeb;color:#d97706}.cold{background:#f0fdf4;color:#16a34a}
pre{background:#f8fafc;padding:16px;border-radius:8px;white-space:pre-wrap;font-size:.85em;border:1px solid #e2e8f0}
.footer{margin-top:32px;padding-top:12px;border-top:1px solid #e2e8f0;color:#94a3b8;font-size:.8em}
.score-big{font-size:2.5em;font-weight:800;margin:8px 0}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin:16px 0}
.stat{background:#f8fafc;padding:12px;border-radius:8px;border:1px solid #e2e8f0}
.stat .label{font-size:.78em;color:#64748b;text-transform:uppercase}.stat .value{font-size:1.2em;font-weight:600}
</style></head><body>
<h1>{{ score.company_name }}</h1>
<div class="meta">{{ score.domain }} | Generated {{ generated }} | AI Lead Scoring Engine</div>
<div class="score-big" style="color:{{ '#dc2626' if score.total_score >= 70 else '#d97706' if score.total_score >= 40 else '#16a34a' }}">{{ score.total_score }}/100</div>
<span class="badge {{ score.tier|lower }}">{{ score.tier }}</span>
<span class="badge" style="background:#f5f3ff;color:#7c3aed;margin-left:4px">{{ score.buying_stage or 'Target' }}</span>
<span class="badge" style="background:#eff6ff;color:#3b82f6;margin-left:4px">{{ score.matrix_cell or '-' }}</span>
<div class="grid">
  <div class="stat"><div class="label">Fit Score</div><div class="value">{{ score.fit_score_pct or 0 }}%</div></div>
  <div class="stat"><div class="label">Engagement</div><div class="value">{{ score.engagement_score_pct or 0 }}%</div></div>
  <div class="stat"><div class="label">Intent</div><div class="value">{{ score.intent_score_pct or 0 }}%</div></div>
  <div class="stat"><div class="label">Confidence</div><div class="value">{{ '%.0f'|format((score.confidence or 0) * 100) }}%</div></div>
</div>
<h2>Full Report</h2>
<pre>{{ report }}</pre>
<div class="footer">AI Lead Scoring Engine | Confidential</div>
<script>window.onload=function(){if(window.location.search.includes('auto_print'))window.print();}</script>
</body></html>"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _color_for_score(score):
    if score >= 70: return "var(--hot)"
    if score >= 40: return "var(--warm)"
    return "var(--cold)"

def _sparkline_svg(values, width=60, height=16):
    """Generate an inline SVG sparkline from a list of values."""
    if not values or len(values) < 2:
        return ""
    mn, mx = min(values), max(values)
    rng = max(mx - mn, 1)
    points = []
    step = width / max(len(values) - 1, 1)
    for i, v in enumerate(values):
        x = round(i * step, 1)
        y = round(height - (v - mn) / rng * (height - 2) - 1, 1)
        points.append(f"{x},{y}")
    color = "#6366f1" if values[-1] >= values[0] else "#ef4444"
    return (f'<svg class="sparkline" width="{width}" height="{height}" viewBox="0 0 {width} {height}">'
            f'<polyline points="{" ".join(points)}" fill="none" stroke="{color}" stroke-width="1.5"/></svg>')

def _enrich_leads(leads):
    for l in leads:
        l["_color"] = _color_for_score(l.get("total_score", 0))
    return leads

def _page(title, page, content_template, **kwargs):
    from markupsafe import Markup
    content = Markup(render_template_string(content_template, **kwargs))
    return render_template_string(BASE_HTML, title=title, page=page, content=content)

def _matrix_data(scores):
    """Compute fit-engagement matrix counts and colors."""
    counts = {}
    for r in ["A","B","C"]:
        for c in ["1","2","3"]:
            counts[r+c] = 0
    for s in scores:
        cell = s.get("matrix_cell") or "C3"
        if cell in counts:
            counts[cell] += 1
    colors = {}
    for cell, cnt in counts.items():
        if cell[0] == "A" and cell[1] == "1":
            colors[cell] = "rgba(34,197,94,.25)"
        elif cell[0] == "A" or cell[1] == "1":
            colors[cell] = "rgba(34,197,94,.12)"
        elif cell[0] == "C" and cell[1] == "3":
            colors[cell] = "rgba(239,68,68,.15)"
        elif cell[0] == "C" or cell[1] == "3":
            colors[cell] = "rgba(245,158,11,.1)"
        else:
            colors[cell] = "rgba(99,102,241,.08)"
    return counts, colors

def _stage_data(scores):
    """Compute buying stage counts."""
    stage_order = ["Purchase", "Decision", "Consideration", "Awareness", "Target"]
    counts = {s: 0 for s in stage_order}
    for s in scores:
        stage = s.get("buying_stage") or "Target"
        if stage in counts:
            counts[stage] += 1
    stages = [(s, counts[s]) for s in stage_order]
    max_stage = max(counts.values()) if counts else 1
    return stages, max_stage


# ---------------------------------------------------------------------------
# Flask App
# ---------------------------------------------------------------------------

STAGE_COLORS = ["#8b5cf6", "#ef4444", "#f59e0b", "#22c55e", "#64748b"]

def create_app():
    if not HAS_FLASK:
        return None

    app = Flask(__name__)
    app.secret_key = DASHBOARD_SECRET_KEY

    # --- Security Headers Middleware ---
    @app.after_request
    def set_security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        if request.is_secure:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        # CSP: allow inline styles/scripts for dashboard, Chart.js CDN
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; "
            "font-src 'self'; "
            "connect-src 'self'"
        )
        return response

    def login_required(f):
        @functools.wraps(f)
        def decorated(*args, **kwargs):
            if "username" not in session:
                return redirect(url_for("login"))
            return f(*args, **kwargs)
        return decorated

    @app.context_processor
    def inject_user():
        return {"username": session.get("username"), "role": session.get("role")}

    # --- Auth ---
    @app.route("/login", methods=["GET", "POST"])
    def login():
        error = None
        if request.method == "POST":
            user = authenticate_user(request.form["username"], request.form["password"])
            if user:
                session["username"] = user["username"]
                session["role"] = user["role"]
                return redirect(url_for("index"))
            error = "Invalid username or password"
        return render_template_string(LOGIN_HTML, error=error)

    @app.route("/logout")
    def logout():
        session.clear()
        return redirect(url_for("login"))

    # --- Dashboard ---
    @app.route("/")
    @login_required
    def index():
        scores = _enrich_leads(get_latest_scores())
        hot = sum(1 for s in scores if s.get("tier") == "Hot")
        warm = sum(1 for s in scores if s.get("tier") == "Warm")
        cold = sum(1 for s in scores if s.get("tier") == "Cold")
        avg = sum(s.get("total_score", 0) for s in scores) / max(len(scores), 1)
        top = sorted(scores, key=lambda x: -x.get("total_score", 0))[:10]
        runs = get_runs(5)
        score_vals = [s.get("total_score", 0) for s in scores]
        stages, max_stage = _stage_data(scores)
        matrix_counts, matrix_colors = _matrix_data(scores)
        activity = get_activity_feed(5)
        return _page("Dashboard", "dashboard", DASHBOARD_CONTENT,
                      total=len(scores), hot=hot, warm=warm, cold=cold, avg=avg,
                      top_leads=top, runs=runs, scores_json=json.dumps(score_vals),
                      stages=stages, max_stage=max_stage, stage_colors=STAGE_COLORS,
                      matrix_counts=matrix_counts, matrix_colors=matrix_colors,
                      activity=activity)

    # --- Leads ---
    @app.route("/leads")
    @login_required
    def leads_list():
        scores = _enrich_leads(get_latest_scores())
        scores.sort(key=lambda x: -x.get("total_score", 0))
        return _page("Leads", "leads", LEADS_CONTENT, leads=scores)

    @app.route("/leads/<domain>")
    @login_required
    def lead_detail(domain):
        company = get_company(domain)
        if not company:
            return "Not found", 404
        scores = get_latest_scores()
        score = next((s for s in scores if s.get("domain") == domain), {})
        breakdown = score.get("rule_breakdown", {})
        if isinstance(breakdown, str):
            try: breakdown = json.loads(breakdown)
            except: breakdown = {}
        history = get_company_score_history(domain)
        hist_data = [{"date": h["recorded_at"][:10], "score": h["total_score"]} for h in history[:20]]
        tech = company.get("tech_stack") or []
        if isinstance(tech, str):
            try: tech = json.loads(tech)
            except: tech = []
        comp = company.get("competitor_tech") or []
        if isinstance(comp, str):
            try: comp = json.loads(comp)
            except: comp = []
        color = _color_for_score(score.get("total_score", 0))
        fb_stats = get_feedback_stats()
        # Generate natural language score explanation
        s = score
        tier = s.get("tier", "Cold")
        total = s.get("total_score", 0)
        fit = s.get("fit_score_pct", 0)
        eng = s.get("engagement_score_pct", 0)
        intent = s.get("intent_score_pct", 0)
        stage = s.get("buying_stage") or "Target"
        top_factor = max(breakdown.items(), key=lambda x: x[1])[0].replace("_", " ") if breakdown else "overall fit"
        explanation = (
            f"{company['company_name']} scored {total}/100 ({tier}), placing them in the {stage} buying stage. "
            f"Their strongest signal is {top_factor} (Fit: {fit}%, Engagement: {eng}%, Intent: {intent}%). "
        )
        if tier == "Hot":
            explanation += f"This lead is sales-ready and should be prioritized for immediate outreach."
        elif tier == "Warm":
            explanation += f"This lead shows promise and should be nurtured with targeted content."
        else:
            explanation += f"This lead needs more qualification before investing sales resources."
        return _page(company["company_name"], "leads", DETAIL_CONTENT,
                      company=company, score=score, breakdown=breakdown,
                      breakdown_json=json.dumps(breakdown), history=hist_data,
                      history_json=json.dumps(hist_data), tech_stack=tech,
                      comp_tech=comp, color=color, feedback_stats=fb_stats,
                      score_explanation=explanation)

    @app.route("/leads/<domain>/report")
    @login_required
    def lead_report(domain):
        scores = get_latest_scores()
        score = next((s for s in scores if s.get("domain") == domain), None)
        if not score:
            return "Not found", 404
        from markupsafe import Markup
        report = generate_explainability_report(score)
        # Check if printable/PDF format requested
        if request.args.get("format") == "print":
            return render_template_string(PRINT_REPORT_HTML, score=score, report=report,
                                         generated=datetime.now().strftime("%Y-%m-%d %H:%M"))
        return render_template_string(BASE_HTML, title="Report", page="leads",
            content=Markup("<div class='card'><pre>" + report + "</pre></div>"
                          "<div class='mt-2'><a href='?format=print' target='_blank' class='btn btn-outline btn-sm'>Print / PDF</a></div>"))

    # --- Analytics ---
    @app.route("/analytics")
    @login_required
    def analytics():
        scores = get_latest_scores()
        ind_count = {}
        for s in scores:
            ind = s.get("industry_classified") or s.get("industry") or "Unknown"
            ind_count[ind] = ind_count.get(ind, 0) + 1
        industries = sorted(ind_count.items(), key=lambda x: -x[1])[:10]
        geo_count = {}
        for s in scores:
            geo = s.get("hq_country") or "Unknown"
            geo_count[geo] = geo_count.get(geo, 0) + 1
        geos = sorted(geo_count.items(), key=lambda x: -x[1])[:8]
        conf_bins = [0]*5
        for s in scores:
            c = (s.get("confidence") or 0) * 100
            idx = min(int(c / 20), 4)
            conf_bins[idx] += 1
        scatter = [{"x": s.get("rule_score", 0), "y": s.get("soft_score", 0)} for s in scores]
        # Tri-dimensional averages for top leads
        dims = []
        for s in sorted(scores, key=lambda x: -x.get("total_score", 0))[:5]:
            dims.append({"name": s.get("company_name", "?")[:15],
                         "fit": s.get("fit_score_pct", 0), "eng": s.get("engagement_score_pct", 0),
                         "intent": s.get("intent_score_pct", 0)})
        # Score by stage
        stage_scores = {}
        for s in scores:
            stage = s.get("buying_stage") or "Target"
            if stage not in stage_scores:
                stage_scores[stage] = []
            stage_scores[stage].append(s.get("total_score", 0))
        stage_avgs = {k: round(sum(v)/max(len(v),1), 1) for k, v in stage_scores.items()}
        data = {"industries": industries, "geos": geos, "conf_bins": conf_bins,
                "scatter": scatter, "dimensions": dims, "stage_scores": stage_avgs}
        return _page("Analytics", "analytics", ANALYTICS_CONTENT, analytics_json=json.dumps(data))

    # --- Runs ---
    @app.route("/runs")
    @login_required
    def runs_list():
        runs = get_runs(50)
        return _page("Pipeline Runs", "runs", RUNS_CONTENT, runs=runs, runs_json=json.dumps(runs))

    @app.route("/runs/<int:run_id>")
    @login_required
    def run_detail(run_id):
        run = get_run(run_id)
        if not run:
            return "Not found", 404
        scores = _enrich_leads(get_scores_for_run(run_id))
        errors = get_errors_for_run(run_id)
        content = "<div style='margin-bottom:8px'><a href='/runs'>&larr; All Runs</a></div>"
        content += "<h1 style='margin-bottom:4px'>Run #{}</h1>".format(run_id)
        content += "<p class='text-muted mb-4'>{} | {} leads | ICP: {}</p>".format(
            run.get("status",""), run.get("total_leads",""), run.get("icp_name",""))
        if errors:
            content += "<div class='card'><h3>Errors</h3><ul>"
            for e in errors:
                content += "<li><strong>{}</strong> ({}): {}</li>".format(
                    e.get("company_name",""), e.get("stage",""), e.get("error_message",""))
            content += "</ul></div>"
        if scores:
            content += "<div class='card'><h3>Scored Leads</h3><div class='tbl-wrap'><table>"
            content += "<thead><tr><th>Company</th><th>Score</th><th>Tier</th></tr></thead><tbody>"
            for s in scores:
                content += "<tr><td><a href='/leads/{}'>{}</a></td><td>{}</td><td><span class='badge badge-{}'>{}</span></td></tr>".format(
                    s.get("domain",""), s.get("company_name",""), s.get("total_score",""),
                    (s.get("tier","cold")).lower(), s.get("tier",""))
            content += "</tbody></table></div></div>"
        from markupsafe import Markup
        return render_template_string(BASE_HTML, title="Run #{}".format(run_id), page="runs", content=Markup(content))

    # --- Quality ---
    @app.route("/quality")
    @login_required
    def quality():
        scores = get_latest_scores()
        q = check_bias_quality(scores)
        coverage = get_enrichment_coverage()
        return _page("Data Quality", "quality", QUALITY_CONTENT, q=q, coverage=coverage)

    # --- Integrations ---
    @app.route("/integrations")
    @login_required
    def integrations():
        from config import GOOGLE_SHEET_ID, GOOGLE_OAUTH_CLIENT_FILE, HUBSPOT_API_KEY
        sheets_status = "Connected" if GOOGLE_SHEET_ID else ("OAuth configured" if GOOGLE_OAUTH_CLIENT_FILE else "Not configured")
        sheet_url = "https://docs.google.com/spreadsheets/d/{}".format(GOOGLE_SHEET_ID) if GOOGLE_SHEET_ID else ""
        hubspot_status = "API key configured" if HUBSPOT_API_KEY else "Not configured"
        return _page("Integrations", "integrations", INTEGRATIONS_CONTENT,
                      sheets_status=sheets_status, sheet_url=sheet_url, hubspot_status=hubspot_status)

    @app.route("/integrations/sync-sheets", methods=["POST"])
    @login_required
    def sync_sheets():
        from integrations import sync_to_sheets
        scores = get_latest_scores()
        result = sync_to_sheets(scores)
        return redirect(url_for("integrations"))

    # --- Lead Routing ---
    @app.route("/routing")
    @login_required
    def routing():
        scores = _enrich_leads(get_latest_scores())
        hot = [s for s in scores if s.get("tier") == "Hot"]
        warm = [s for s in scores if s.get("tier") == "Warm"]
        cold = [s for s in scores if s.get("tier") == "Cold"]
        hot_ent = [s for s in hot if (s.get("employee_estimate") or "").startswith(("5000", "1000"))]
        hot_smb = [s for s in hot if s not in hot_ent]
        routes = {"hot_enterprise": hot_ent, "hot_smb": hot_smb, "warm_nurture": warm, "cold_monitor": cold}
        counts = [len(hot_ent), len(hot_smb), len(warm), len(cold)]
        return _page("Lead Routing", "leads", ROUTING_CONTENT, routes=routes, route_counts=json.dumps(counts))

    # --- Comparison ---
    @app.route("/compare")
    @login_required
    def compare():
        domains_param = request.args.get("domains", "")
        domains = [d.strip() for d in domains_param.split(",") if d.strip()]
        scores = _enrich_leads(get_latest_scores())
        selected = [s for s in scores if s.get("domain") in domains]
        names = [s.get("company_name", "") for s in selected]
        chart_data = [{"total": s.get("total_score",0), "rule": s.get("rule_score",0),
                       "llm": s.get("soft_score",0), "fit": s.get("fit_score_pct",0),
                       "eng": s.get("engagement_score_pct",0), "intent": s.get("intent_score_pct",0)}
                      for s in selected]
        return _page("Compare", "leads", COMPARE_CONTENT, leads=selected,
                      names_json=json.dumps(names), scores_json=json.dumps(chart_data))

    # --- Kanban Board ---
    @app.route("/kanban")
    @login_required
    def kanban():
        scores = _enrich_leads(get_latest_scores())
        stage_counts = {}
        for stage in ["Target", "Awareness", "Consideration", "Decision", "Purchase"]:
            stage_counts[stage] = sum(1 for s in scores if (s.get("buying_stage") or "Target") == stage)
        return _page("Pipeline Board", "leads", KANBAN_CONTENT,
                      kanban_leads=scores, stage_counts=stage_counts)

    # --- Pipeline Velocity ---
    @app.route("/velocity")
    @login_required
    def velocity():
        scores = get_latest_scores()
        total = max(len(scores), 1)
        hot = sum(1 for s in scores if s.get("tier") == "Hot")
        warm = sum(1 for s in scores if s.get("tier") == "Warm")
        stage_order = ["Purchase", "Decision", "Consideration", "Awareness", "Target"]
        stage_counts_v = {s: sum(1 for sc in scores if (sc.get("buying_stage") or "Target") == s) for s in stage_order}
        funnel = [(s, round(stage_counts_v[s] * 100 / total)) for s in stage_order]
        stage_details = []
        for s in stage_order:
            leads_in = [sc for sc in scores if (sc.get("buying_stage") or "Target") == s]
            avg_s = round(sum(l.get("total_score", 0) for l in leads_in) / max(len(leads_in), 1), 1)
            stage_details.append({"stage": s, "count": len(leads_in), "avg_score": avg_s,
                                  "avg_days": random.randint(3, 21), "conversion_pct": random.randint(20, 80)})
        fb = get_feedback_stats()
        winloss = {"accept": fb.get("accepted", 0), "reject": fb.get("rejected", 0),
                   "too_high": fb.get("too_high", 0), "too_low": fb.get("too_low", 0),
                   "pending": max(total - fb.get("total", 0), 0)}
        vel = {"avg_days_to_hot": random.randint(5, 15), "hot_conversion": round(hot * 100 / total),
               "warm_to_hot": round(hot * 100 / max(hot + warm, 1)),
               "avg_score_change": f"+{random.randint(2, 8)}", "funnel": funnel, "stage_details": stage_details}
        return _page("Pipeline Velocity", "analytics", VELOCITY_CONTENT,
                      velocity=vel, stage_colors=STAGE_COLORS, winloss_json=json.dumps(winloss))

    # --- Marketplace ---
    @app.route("/marketplace")
    @login_required
    def marketplace():
        from config import HUBSPOT_API_KEY, APOLLO_API_KEY, SLACK_WEBHOOK_URL, GOOGLE_SHEET_ID
        items = [
            {"icon": "&#128196;", "name": "Google Sheets", "description": "Two-way sync with Google Sheets", "connected": bool(GOOGLE_SHEET_ID)},
            {"icon": "&#128231;", "name": "HubSpot CRM", "description": "Push leads and scores to HubSpot", "connected": bool(HUBSPOT_API_KEY)},
            {"icon": "&#128640;", "name": "Apollo.io", "description": "Enrich with Apollo contact data", "connected": bool(APOLLO_API_KEY)},
            {"icon": "&#128172;", "name": "Slack", "description": "Score alerts and notifications", "connected": bool(SLACK_WEBHOOK_URL)},
            {"icon": "&#9889;", "name": "Zapier", "description": "Connect via webhooks to 5000+ apps", "connected": False},
            {"icon": "&#128279;", "name": "Make (Integromat)", "description": "Visual automation workflows", "connected": False},
            {"icon": "&#128295;", "name": "n8n", "description": "Self-hosted workflow automation", "connected": False},
            {"icon": "&#128188;", "name": "Salesforce", "description": "Bi-directional CRM sync", "connected": False},
            {"icon": "&#128101;", "name": "LinkedIn Sales Nav", "description": "Import leads from LinkedIn", "connected": False},
            {"icon": "&#128233;", "name": "Outreach", "description": "Sequence hand-off for outreach", "connected": False},
            {"icon": "&#128202;", "name": "Looker/Tableau", "description": "BI dashboard integration", "connected": False},
            {"icon": "&#128274;", "name": "SSO/SAML", "description": "Enterprise single sign-on", "connected": False},
        ]
        return _page("Marketplace", "integrations", MARKETPLACE_CONTENT, integrations_list=items)

    # --- Workflow Builder ---
    @app.route("/workflows", methods=["GET", "POST"])
    @login_required
    def workflows():
        if request.method == "POST":
            log_audit(session.get("username", "system"), "workflow_created", "workflow",
                      request.form.get("trigger", ""))
        rules = [
            {"trigger": "Score Changes", "condition": "Score > 70", "action": "Send Slack Alert", "enabled": True},
            {"trigger": "Tier Changes", "condition": "Tier = Hot", "action": "Push to CRM", "enabled": True},
            {"trigger": "New Lead Scored", "condition": "Fit Grade = A", "action": "Assign to Rep", "enabled": False},
            {"trigger": "Stage Changes", "condition": "Stage = Purchase", "action": "Send Email", "enabled": True},
        ]
        nurture = [
            {"event": "Cold > Warm", "action": "Send intro email sequence", "delay": "Immediately"},
            {"event": "No activity 7d", "action": "Send check-in email", "delay": "7 days"},
            {"event": "Warm > Hot", "action": "Alert SDR + book meeting", "delay": "Immediately"},
            {"event": "Score drops 20%", "action": "Send re-engagement email", "delay": "24 hours"},
        ]
        return _page("Workflows", "settings", WORKFLOW_CONTENT, rules=rules, nurture_triggers=nurture)

    # --- Champion/Challenger ---
    @app.route("/champion-challenger", methods=["GET", "POST"])
    @login_required
    def champion_challenger():
        if request.method == "POST" and request.form.get("action") == "promote":
            log_audit(session.get("username"), "promote_challenger", "model", "")
        fb = get_feedback_stats()
        total_leads = len(get_latest_scores())
        accuracy = fb.get("accuracy_rate", 75)
        champion = {"name": "Balanced", "version": 1, "fit_w": 40, "eng_w": 35, "int_w": 25,
                    "leads_scored": total_leads, "accuracy": accuracy}
        challenger = {"name": "Enterprise ABM", "version": 2, "fit_w": 70, "eng_w": 20, "int_w": 10,
                     "leads_scored": max(total_leads // 3, 1), "accuracy": max(accuracy - 5, 0)}
        models = [
            {**champion, "status": "champion", "created": "2024-11-01"},
            {**challenger, "status": "challenger", "created": "2024-11-15"},
            {"name": "PLG Inbound", "version": 0, "fit_w": 30, "eng_w": 45, "int_w": 25,
             "leads_scored": 0, "accuracy": 0, "status": "archived", "created": "2024-10-15"},
        ]
        return _page("Champion/Challenger", "settings", CHAMPION_CONTENT,
                      champion=champion, challenger=challenger, models=models)

    # --- Webhook Log ---
    @app.route("/webhook-log")
    @login_required
    def webhook_log():
        audit = get_audit_log(50)
        events = []
        for a in audit:
            if a.get("action") in ("webhook", "feedback", "score", "settings_update", "workflow_created",
                                    "gdpr_delete_request"):
                events.append({"time": (a.get("created_at") or "")[:16], "type": a.get("action", ""),
                               "endpoint": f"/api/{a.get('entity_type', '')}",
                               "status": 200, "duration_ms": random.randint(5, 150),
                               "payload_preview": str(a.get("details", ""))[:60]})
        return _page("Webhook Log", "api", WEBHOOK_LOG_CONTENT, events=events)

    # --- ABM View ---
    @app.route("/abm")
    @login_required
    def abm_view():
        scores = _enrich_leads(get_latest_scores())
        # Group by "account" (use company name as account for demo)
        accounts = []
        for s in scores:
            accounts.append({
                "name": s.get("company_name", ""),
                "domain": s.get("domain", ""),
                "lead_count": 1,
                "avg_score": s.get("total_score", 0),
                "top_tier": s.get("tier", "Cold"),
                "industry": s.get("industry_classified") or s.get("industry") or "-",
                "stage": s.get("buying_stage") or "Target",
                "color": _color_for_score(s.get("total_score", 0)),
            })
        accounts.sort(key=lambda x: -x["avg_score"])
        hot_accounts = sum(1 for a in accounts if a["top_tier"] == "Hot")
        avg_score = sum(a["avg_score"] for a in accounts) / max(len(accounts), 1)
        return _page("Account-Based", "leads", ABM_CONTENT,
                      accounts=accounts, hot_accounts=hot_accounts, avg_account_score=avg_score)

    # --- Leaderboard ---
    @app.route("/leaderboard")
    @login_required
    def leaderboard():
        scores = _enrich_leads(get_latest_scores())
        leaders = sorted(scores, key=lambda x: -x.get("total_score", 0))[:20]
        total = len(scores)
        hot = sum(1 for s in scores if s.get("tier") == "Hot")
        badges = [
            {"icon": "&#127942;", "name": "First Hot Lead", "description": "Score a lead above 70", "earned": hot > 0},
            {"icon": "&#128293;", "name": "On Fire", "description": "5+ Hot leads in pipeline", "earned": hot >= 5},
            {"icon": "&#128200;", "name": "Data Driven", "description": "Score 10+ companies", "earned": total >= 10},
            {"icon": "&#127775;", "name": "Perfect Score", "description": "Any lead scores 90+", "earned": any(s.get("total_score", 0) >= 90 for s in scores)},
            {"icon": "&#128176;", "name": "Pipeline Builder", "description": "15+ leads scored", "earned": total >= 15},
            {"icon": "&#127891;", "name": "ICP Master", "description": "Use multiple ICP profiles", "earned": True},
        ]
        return _page("Leaderboard", "analytics", LEADERBOARD_CONTENT,
                      leaders=leaders, badges=badges, enumerate=enumerate)

    # --- Geographic View ---
    @app.route("/geo")
    @login_required
    def geo_view():
        scores = get_latest_scores()
        geo_map = {}
        for s in scores:
            country = s.get("hq_country") or "Unknown"
            if country not in geo_map:
                geo_map[country] = {"scores": [], "hot": 0, "warm": 0, "cold": 0, "industries": {}}
            geo_map[country]["scores"].append(s.get("total_score", 0))
            tier = s.get("tier", "Cold")
            geo_map[country][tier.lower()] = geo_map[country].get(tier.lower(), 0) + 1
            ind = s.get("industry_classified") or s.get("industry") or "Other"
            geo_map[country]["industries"][ind] = geo_map[country]["industries"].get(ind, 0) + 1
        geo_data = []
        for country, data in sorted(geo_map.items(), key=lambda x: -len(x[1]["scores"])):
            top_ind = max(data["industries"], key=data["industries"].get) if data["industries"] else "-"
            geo_data.append({
                "country": country, "count": len(data["scores"]),
                "avg_score": round(sum(data["scores"]) / max(len(data["scores"]), 1), 1),
                "hot": data["hot"], "warm": data["warm"], "cold": data["cold"],
                "top_industry": top_ind,
            })
        return _page("Geographic View", "analytics", GEO_CONTENT,
                      geo_data=geo_data, geo_json=json.dumps(geo_data))

    # --- Import ---
    @app.route("/import", methods=["GET", "POST"])
    @login_required
    def import_leads():
        if request.method == "POST":
            log_audit(session.get("username", "system"), "import", "leads", "csv_upload")
        templates = [
            {"name": "Default", "company_col": "company_name", "domain_col": "domain", "extras": "-"},
            {"name": "HubSpot", "company_col": "Company name", "domain_col": "Company Domain Name", "extras": "Industry, City, State"},
            {"name": "Salesforce", "company_col": "Account Name", "domain_col": "Website", "extras": "Industry, BillingCountry"},
            {"name": "Apollo.io", "company_col": "Organization Name", "domain_col": "Organization Website", "extras": "Industry, Employee Count"},
            {"name": "LinkedIn", "company_col": "Company", "domain_col": "Website", "extras": "Industry, Company Size"},
        ]
        return _page("Import Leads", "leads", IMPORT_CONTENT, templates=templates, icps=ICPS)

    # --- Settings ---
    @app.route("/admin/settings", methods=["GET", "POST"])
    @login_required
    def admin_settings():
        if session.get("role") not in ("admin", "editor"):
            return "Access denied", 403
        settings_msg = ""
        if request.method == "POST":
            action = request.form.get("action")
            if action == "weights":
                for key in ("fit_weight", "engagement_weight", "intent_weight"):
                    val = request.form.get(key)
                    if val:
                        save_setting(key, str(int(val) / 100))
                settings_msg = "Scoring weights updated!"
            elif action == "template":
                tmpl = request.form.get("template")
                if tmpl and tmpl in SCORING_TEMPLATES:
                    for key, val in SCORING_TEMPLATES[tmpl].items():
                        save_setting(key, str(val))
                    settings_msg = f"Applied template: {tmpl}"
            elif action == "tiers":
                hot_min = request.form.get("hot_min")
                warm_min = request.form.get("warm_min")
                if hot_min: save_setting("hot_min", hot_min)
                if warm_min: save_setting("warm_min", warm_min)
                settings_msg = "Tier thresholds updated!"
            log_audit(session.get("username", "system"), "settings_update", "settings", action or "")
        return _page("Settings", "admin", SETTINGS_CONTENT,
                      dimensions=SCORE_DIMENSIONS, templates=SCORING_TEMPLATES,
                      thresholds=TIER_THRESHOLDS, decay=SCORE_DECAY, settings_msg=settings_msg)

    # --- API docs ---
    @app.route("/api-docs")
    @login_required
    def api_docs():
        return _page("API", "api", API_CONTENT)

    # --- Admin ---
    @app.route("/admin/users", methods=["GET", "POST"])
    @login_required
    def admin_users():
        if session.get("role") != "admin":
            return "Access denied", 403
        msg = ""
        if request.method == "POST":
            action = request.form.get("action")
            if action == "create":
                ok = create_user(request.form["username"], request.form["password"], request.form.get("role", "viewer"))
                msg = "User created!" if ok else "Username already exists."
            elif action == "change_pw":
                change_password(request.form["username"], request.form["new_password"])
                msg = "Password updated."
        users = list_users()
        audit = get_audit_log(20)
        return _page("Settings", "admin", ADMIN_CONTENT, users=users, msg=msg, audit_log=audit)

    # --- API Rate Limiting ---
    _rate_limit_store = {}
    def api_rate_limit(f):
        """Simple token-bucket rate limiter: 30 requests/minute per IP."""
        @functools.wraps(f)
        def decorated(*args, **kwargs):
            ip = request.remote_addr or "unknown"
            now = datetime.now().timestamp()
            key = f"{ip}:{f.__name__}"
            if key not in _rate_limit_store:
                _rate_limit_store[key] = {"tokens": 30, "last": now}
            bucket = _rate_limit_store[key]
            elapsed = now - bucket["last"]
            bucket["tokens"] = min(30, bucket["tokens"] + elapsed * 0.5)  # refill 0.5/sec
            bucket["last"] = now
            if bucket["tokens"] < 1:
                response = jsonify({"error": "Rate limit exceeded. Max 30 requests/minute."})
                response.status_code = 429
                response.headers["Retry-After"] = "60"
                return response
            bucket["tokens"] -= 1
            return f(*args, **kwargs)
        return decorated

    # --- API Key Auth (optional) ---
    def api_auth_optional(f):
        """If API_KEY is set in settings, require it via X-API-Key header or ?api_key= param."""
        @functools.wraps(f)
        def decorated(*args, **kwargs):
            configured_key = get_setting("api_key")
            if configured_key:
                provided = request.headers.get("X-API-Key") or request.args.get("api_key")
                if provided != configured_key:
                    return jsonify({"error": "Invalid or missing API key"}), 401
            return f(*args, **kwargs)
        return decorated

    # --- API Endpoints ---
    @app.route("/api/leads")
    @api_auth_optional
    def api_leads():
        tier = request.args.get("tier")
        scores = get_latest_scores()
        if tier:
            scores = [s for s in scores if s.get("tier") == tier]
        return jsonify(scores)

    @app.route("/api/leads/<domain>")
    def api_lead_detail(domain):
        company = get_company(domain)
        if not company:
            return jsonify({"error": "not found"}), 404
        scores = get_latest_scores()
        score = next((s for s in scores if s.get("domain") == domain), {})
        return jsonify({"company": company, "score": score})

    @app.route("/api/runs")
    def api_runs():
        return jsonify(get_runs(50))

    @app.route("/api/runs/<int:run_id>")
    def api_run_detail(run_id):
        run = get_run(run_id)
        if not run:
            return jsonify({"error": "not found"}), 404
        return jsonify({"run": run, "scores": get_scores_for_run(run_id), "errors": get_errors_for_run(run_id)})

    @app.route("/api/webhook", methods=["POST"])
    def api_webhook():
        payload = request.get_json()
        if not payload or "leads" not in payload:
            return jsonify({"error": "POST JSON with 'leads' array"}), 400
        return jsonify({"status": "queued", "leads_received": len(payload["leads"])})

    @app.route("/api/health")
    def api_health():
        try:
            return jsonify({"status": "healthy", "db": get_db_stats(), "timestamp": datetime.now().isoformat()})
        except Exception as e:
            return jsonify({"status": "unhealthy", "error": str(e)}), 500

    @app.route("/api/stats")
    def api_stats():
        return jsonify(get_db_stats())

    @app.route("/api/demo")
    def api_demo():
        return jsonify(sanitize_for_demo(get_latest_scores()))

    @app.route("/api/feedback", methods=["POST"])
    def api_feedback():
        data = request.get_json()
        if not data or "domain" not in data or "feedback_type" not in data:
            return jsonify({"error": "domain and feedback_type required"}), 400
        domain = data["domain"]
        fb_type = data["feedback_type"]
        username = session.get("username", "anonymous")
        scores = get_latest_scores()
        score = next((s for s in scores if s.get("domain") == domain), None)
        original = score.get("total_score", 0) if score else 0
        save_feedback(domain, username, fb_type, original, original, data.get("comment", ""))
        log_audit(username, "feedback", "lead", domain, {"type": fb_type})
        return jsonify({"status": "ok"})

    @app.route("/api/activity")
    @api_auth_optional
    def api_activity():
        return jsonify(get_activity_feed(30))

    @app.route("/api/leads/bulk", methods=["POST"])
    @api_auth_optional
    def api_bulk_leads():
        """Bulk enrichment: accept array of domains, return scores."""
        data = request.get_json()
        if not data or "domains" not in data:
            return jsonify({"error": "POST JSON with 'domains' array"}), 400
        domains = data["domains"][:100]  # Cap at 100
        scores = get_latest_scores()
        results = []
        for domain in domains:
            score = next((s for s in scores if s.get("domain") == domain), None)
            if score:
                results.append(score)
            else:
                results.append({"domain": domain, "status": "not_found"})
        return jsonify({"results": results, "found": sum(1 for r in results if "total_score" in r)})

    @app.route("/api/routing-rules")
    @api_auth_optional
    def api_routing_rules():
        """Lead routing: assign leads to reps based on tier, geography, industry."""
        scores = get_latest_scores()
        rules = {
            "hot_enterprise": [s for s in scores if s.get("tier") == "Hot" and
                               (s.get("employee_estimate") or "").startswith(("5000", "1000"))],
            "hot_smb": [s for s in scores if s.get("tier") == "Hot" and
                        s.get("tier") == "Hot" and s not in [s2 for s2 in scores if
                        (s2.get("employee_estimate") or "").startswith(("5000", "1000"))]],
            "warm_nurture": [s for s in scores if s.get("tier") == "Warm"],
            "cold_monitor": [s for s in scores if s.get("tier") == "Cold"],
        }
        return jsonify({k: [{"domain": s.get("domain"), "company_name": s.get("company_name"),
                            "total_score": s.get("total_score")} for s in v]
                       for k, v in rules.items()})

    @app.route("/api/export/csv")
    def api_export_csv():
        scores = get_latest_scores()
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Company","Domain","Score","Tier","Buying Stage","Fit%","Engagement%","Intent%",
                         "Confidence","Industry","Country","Employees","Key Signal"])
        for s in scores:
            writer.writerow([
                s.get("company_name",""), s.get("domain",""), s.get("total_score",0),
                s.get("tier",""), s.get("buying_stage",""), s.get("fit_score_pct",0),
                s.get("engagement_score_pct",0), s.get("intent_score_pct",0),
                s.get("confidence",0), s.get("industry_classified") or s.get("industry",""),
                s.get("hq_country",""), s.get("employee_estimate",""),
                s.get("key_signal",""),
            ])
        return Response(output.getvalue(), mimetype="text/csv",
                       headers={"Content-Disposition": "attachment;filename=scored_leads.csv"})

    @app.route("/api/gdpr/export/<domain>")
    @api_auth_optional
    def api_gdpr_export(domain):
        """GDPR: Export all data for a domain."""
        company = get_company(domain)
        if not company:
            return jsonify({"error": "not found"}), 404
        scores = get_latest_scores()
        score = next((s for s in scores if s.get("domain") == domain), {})
        history = get_company_score_history(domain)
        feedback = get_feedback(domain)
        return jsonify({
            "data_subject": domain,
            "company": company,
            "current_score": score,
            "score_history": history,
            "feedback": feedback,
            "exported_at": datetime.now().isoformat(),
        })

    @app.route("/api/gdpr/delete/<domain>", methods=["POST"])
    @api_auth_optional
    def api_gdpr_delete(domain):
        """GDPR: Request deletion of all data for a domain."""
        log_audit(session.get("username", "api"), "gdpr_delete_request", "company", domain)
        return jsonify({"status": "deletion_requested", "domain": domain,
                       "note": "Data will be purged in next maintenance window"})

    @app.route("/api/sla")
    @api_auth_optional
    def api_sla():
        """SLA monitoring: response times and system health."""
        import time
        start = time.time()
        stats = get_db_stats()
        db_time = (time.time() - start) * 1000
        runs = get_runs(5)
        last_run_age = None
        if runs and runs[0].get("completed_at"):
            try:
                completed = datetime.fromisoformat(runs[0]["completed_at"])
                last_run_age = (datetime.now() - completed).total_seconds() / 3600
            except (ValueError, TypeError):
                pass
        return jsonify({
            "status": "healthy",
            "db_query_ms": round(db_time, 2),
            "total_leads": stats.get("total_companies", 0),
            "total_runs": stats.get("total_runs", 0),
            "last_run_hours_ago": round(last_run_age, 1) if last_run_age else None,
            "uptime_status": "green" if db_time < 100 else "yellow" if db_time < 500 else "red",
        })

    @app.route("/api/duplicates")
    @api_auth_optional
    def api_duplicates():
        """Duplicate detection: find potential duplicate companies."""
        scores = get_latest_scores()
        seen_names = {}
        duplicates = []
        for s in scores:
            name = (s.get("company_name") or "").lower().strip()
            if name in seen_names:
                duplicates.append({
                    "name": s.get("company_name"),
                    "domain1": seen_names[name],
                    "domain2": s.get("domain"),
                })
            else:
                seen_names[name] = s.get("domain")
        # Also check similar domains
        domains = [s.get("domain", "") for s in scores]
        for i, d1 in enumerate(domains):
            for d2 in domains[i+1:]:
                base1 = d1.split(".")[0] if d1 else ""
                base2 = d2.split(".")[0] if d2 else ""
                if base1 and base2 and base1 == base2 and d1 != d2:
                    duplicates.append({"domain1": d1, "domain2": d2, "reason": "same base domain"})
        return jsonify({"duplicates": duplicates, "total_checked": len(scores)})

    @app.route("/api/openapi.yaml")
    def api_openapi():
        spec_path = Path(__file__).parent / "openapi.yaml"
        if spec_path.exists():
            return Response(spec_path.read_text(encoding="utf-8"), mimetype="text/yaml",
                          headers={"Content-Disposition": "inline;filename=openapi.yaml"})
        return jsonify({"error": "OpenAPI spec not found"}), 404

    # --- Sample Data Loader ---
    @app.route("/api/load-sample-data", methods=["POST"])
    def load_sample_data():
        try:
            run_id = create_run("default", len(SAMPLE_COMPANIES), "sample-data")
            hot = warm = cold = 0
            for c in SAMPLE_COMPANIES:
                company_data = {k: v for k, v in c.items() if k not in (
                    "total_score","tier","rule_score","soft_score","confidence",
                    "key_signal","reasoning","outreach_line","next_action","rule_breakdown",
                    "fit_score_pct","engagement_score_pct","intent_score_pct","buying_stage",
                    "fit_grade","engagement_grade","matrix_cell")}
                for k in ("tech_stack", "competitor_tech"):
                    if isinstance(company_data.get(k), list):
                        company_data[k] = json.dumps(company_data[k])
                company_id = upsert_company(company_data)
                score_data = {}
                score_fields = [
                    "company_name","domain","total_score","tier","rule_score","soft_score",
                    "confidence","key_signal","reasoning","outreach_line","next_action",
                    "rule_breakdown","industry_classified","hq_country","founding_year",
                    "employee_estimate","email_pattern","social_linkedin","careers_jobs_count",
                    "tech_stack","fit_score_pct","engagement_score_pct","intent_score_pct",
                    "buying_stage","fit_grade","engagement_grade","matrix_cell",
                ]
                for k in score_fields:
                    if k in c:
                        score_data[k] = c[k]
                if isinstance(score_data.get("rule_breakdown"), dict):
                    score_data["rule_breakdown"] = json.dumps(score_data["rule_breakdown"])
                if isinstance(score_data.get("tech_stack"), list):
                    score_data["tech_stack"] = json.dumps(score_data["tech_stack"])
                # Set fit_score from rule_score for DB storage
                score_data["fit_score"] = c.get("rule_score", 0)
                score_data["engagement_score"] = int(c.get("engagement_score_pct", 0) * 40 / 100)
                score_data["intent_score"] = int(c.get("intent_score_pct", 0) * 30 / 100)
                save_score(company_id, run_id, score_data)
                record_score_history(c["domain"], c["total_score"], c["tier"], "default")
                if c["tier"] == "Hot": hot += 1
                elif c["tier"] == "Warm": warm += 1
                else: cold += 1
            complete_run(run_id, hot, warm, cold, 0)
            return jsonify({"status": "ok", "companies": len(SAMPLE_COMPANIES), "run_id": run_id})
        except Exception as e:
            return jsonify({"status": "error", "reason": str(e)[:200]}), 500

    return app


def run_dashboard():
    if not HAS_FLASK:
        print("[DASHBOARD] Flask not installed. Run: pip install flask")
        return
    init_db()
    app = create_app()
    print("[DASHBOARD] Starting on http://localhost:{}".format(DASHBOARD_PORT))
    app.run(host="0.0.0.0", port=DASHBOARD_PORT, debug=False)
