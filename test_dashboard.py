"""Comprehensive test suite for AI Lead Scoring Engine Dashboard."""
import json
import os
import sys

# Fresh DB
if os.path.exists('lead_scorer.db'):
    os.remove('lead_scorer.db')
    print('[SETUP] Removed old database for clean test')

from dashboard import create_app
from database import init_db, get_runs
init_db()
app = create_app()
client = app.test_client()

errors = []
passes = []


def test(name, response, expected_status=200, check_content=None):
    ok = response.status_code == expected_status
    if check_content and ok:
        data = response.data.decode('utf-8', errors='replace')
        if check_content not in data:
            errors.append(f'FAIL {name}: missing content "{check_content[:50]}"')
            return
    if ok:
        passes.append(name)
    else:
        errors.append(f'FAIL {name}: got {response.status_code}, expected {expected_status}')


print('=' * 60)
print('  COMPREHENSIVE DASHBOARD TEST')
print('=' * 60)

# ===== 1. AUTH =====
print('\n--- 1. Auth Tests ---')

r = client.get('/login')
test('Login page loads', r, 200, 'Sign in')

r = client.post('/login', data={'username': 'wrong', 'password': 'wrong'}, follow_redirects=True)
test('Bad login shows error', r, 200, 'Invalid username or password')

r = client.get('/', follow_redirects=False)
test('Redirect to login when not authed', r, 302)

r = client.post('/login', data={'username': 'admin', 'password': 'changeme'}, follow_redirects=True)
test('Successful login', r, 200, 'Dashboard')

# ===== 2. EMPTY STATE =====
print('\n--- 2. Empty State Pages ---')

r = client.get('/')
test('Dashboard empty state', r, 200, 'No leads scored yet')

r = client.get('/leads')
test('Leads page empty', r, 200)

r = client.get('/analytics')
test('Analytics page empty', r, 200)

r = client.get('/runs')
test('Runs page empty', r, 200, 'No pipeline runs yet')

r = client.get('/quality')
test('Quality page empty', r, 200)

r = client.get('/integrations')
test('Integrations page', r, 200, 'Google Sheets')

r = client.get('/api-docs')
test('API docs page', r, 200, '/api/leads')

r = client.get('/admin/users')
test('Admin users page', r, 200, 'admin')

# ===== 3. API EMPTY =====
print('\n--- 3. API Endpoints (Empty) ---')

r = client.get('/api/leads')
data = r.get_json()
test('API leads returns list', r, 200)
if not isinstance(data, list):
    errors.append('FAIL API leads: not a list')
else:
    passes.append('API leads is empty list')

r = client.get('/api/runs')
test('API runs', r, 200)

r = client.get('/api/health')
data = r.get_json()
test('API health', r, 200)
if data.get('status') != 'healthy':
    errors.append(f'FAIL API health: {data}')
else:
    passes.append('API health is healthy')

r = client.get('/api/stats')
test('API stats', r, 200)

r = client.get('/api/demo')
test('API demo', r, 200)

r = client.get('/api/leads/nonexistent.com')
test('API lead 404', r, 404)

# ===== 4. SAMPLE DATA =====
print('\n--- 4. Load Sample Data ---')

r = client.post('/api/load-sample-data')
data = r.get_json()
test('Load sample data', r, 200)
if data.get('status') != 'ok':
    errors.append(f'FAIL Sample data: {data}')
else:
    passes.append(f'Sample data loaded: {data.get("companies")} companies')

# ===== 5. DASHBOARD WITH DATA =====
print('\n--- 5. Dashboard With Data ---')

r = client.get('/')
page = r.data.decode('utf-8', errors='replace')
test('Dashboard with data loads', r, 200, 'tierChart')

for kw in ['Total Leads', 'Hot Leads', 'Warm Leads', 'Cold Leads', 'Avg Score']:
    if kw in page:
        passes.append(f'Dashboard has "{kw}"')
    else:
        errors.append(f'FAIL Dashboard missing "{kw}"')

# Check charts exist
for chart in ['tierChart', 'scoreChart']:
    if chart in page:
        passes.append(f'Dashboard has {chart}')
    else:
        errors.append(f'FAIL Dashboard missing {chart}')

# ===== 6. LEADS TABLE =====
print('\n--- 6. Leads Table ---')

r = client.get('/leads')
page = r.data.decode('utf-8', errors='replace')
test('Leads table loads', r, 200)

companies = ['Stripe', 'Notion', 'Datadog', 'Figma', 'Vercel', 'Zapier', 'Calendly',
             'Airtable', 'Miro', 'Linear', 'Mailchimp', 'Squarespace', 'Freshworks', 'GitLab', 'Webflow',
             'Wise', 'Atlassian', 'Razorpay', 'UiPath', 'Canva', 'Checkout.com',
             'Personio', 'Deel', 'Postman', 'Grab', 'Contentful', 'Rappi', 'Wiz',
             'Mercado Libre', 'N26', 'Loom', 'Sage Group', 'Naver', 'Xero', 'Baidu',
             'Flipkart', 'Booking Holdings', 'Zalando']
for c in companies:
    if c in page:
        passes.append(f'Leads has {c}')
    else:
        errors.append(f'FAIL Leads missing {c}')

# Check filter/search elements
for el in ['searchF', 'tierF', 'leadsTable']:
    if el in page:
        passes.append(f'Leads has element: {el}')
    else:
        errors.append(f'FAIL Leads missing element: {el}')

# ===== 7. LEAD DETAILS =====
print('\n--- 7. Lead Detail Pages ---')

detail_domains = ['stripe.com', 'notion.so', 'datadoghq.com', 'figma.com', 'zapier.com',
                  'mailchimp.com', 'linear.app', 'gitlab.com']
for domain in detail_domains:
    r = client.get(f'/leads/{domain}')
    page = r.data.decode('utf-8', errors='replace')
    test(f'Detail: {domain}', r, 200)

    checks = {
        'radarChart': 'radar chart',
        'Score Breakdown': 'score breakdown',
        'Score Components': 'score components',
        'Tech Stack': 'tech stack section',
        'AI Insights': 'AI insights',
    }
    for key, label in checks.items():
        if key in page:
            passes.append(f'  {domain}: has {label}')
        else:
            errors.append(f'FAIL {domain}: missing {label}')

r = client.get('/leads/nonexistent.com')
test('Detail 404', r, 404)

# ===== 8. REPORTS =====
print('\n--- 8. Explainability Reports ---')

r = client.get('/leads/stripe.com/report')
test('Stripe report', r, 200)

r = client.get('/leads/notion.so/report')
test('Notion report', r, 200)

r = client.get('/leads/nonexistent.com/report')
test('Report 404', r, 404)

# ===== 9. ANALYTICS =====
print('\n--- 9. Analytics Page ---')

r = client.get('/analytics')
page = r.data.decode('utf-8', errors='replace')
test('Analytics loads', r, 200)

for chart in ['indChart', 'geoChart', 'confChart', 'scatterChart']:
    if chart in page:
        passes.append(f'Analytics: {chart}')
    else:
        errors.append(f'FAIL Analytics missing {chart}')

# Check analytics JSON data is valid
if 'analytics_json' not in page and 'industries' in page:
    passes.append('Analytics has data in template')

# ===== 10. RUNS =====
print('\n--- 10. Pipeline Runs ---')

r = client.get('/runs')
page = r.data.decode('utf-8', errors='replace')
test('Runs page with data', r, 200)

runs = get_runs(5)
if runs:
    passes.append(f'Database has {len(runs)} run(s)')
    run_id = runs[0]['id']
    r = client.get(f'/runs/{run_id}')
    test(f'Run detail #{run_id}', r, 200)
else:
    errors.append('FAIL No runs in database')

r = client.get('/runs/99999')
test('Run detail 404', r, 404)

# ===== 11. QUALITY =====
print('\n--- 11. Data Quality ---')

r = client.get('/quality')
page = r.data.decode('utf-8', errors='replace')
test('Quality page', r, 200, 'Quality Rating')
if 'Total Scored' in page:
    passes.append('Quality has total scored')
else:
    errors.append('FAIL Quality missing total scored')

# ===== 12. API WITH DATA =====
print('\n--- 12. API Endpoints (With Data) ---')

r = client.get('/api/leads')
data = r.get_json()
test('API leads has data', r, 200)
if len(data) < 40:
    errors.append(f'FAIL API leads: expected >=40, got {len(data)}')
else:
    passes.append(f'API leads returns {len(data)} companies')

# Check data structure
if data:
    lead = data[0]
    for f in ['company_name', 'domain', 'total_score', 'tier']:
        if f in lead:
            passes.append(f'API lead field: {f}')
        else:
            errors.append(f'FAIL API lead missing: {f}')

# Tier filter
r = client.get('/api/leads?tier=Hot')
data = r.get_json()
test('API filter Hot', r, 200)
all_hot = all(l.get('tier') == 'Hot' for l in data)
if all_hot and len(data) > 0:
    passes.append(f'API Hot filter correct ({len(data)} leads)')
else:
    errors.append(f'FAIL API Hot filter: {len(data)} leads, all_hot={all_hot}')

r = client.get('/api/leads?tier=Warm')
data = r.get_json()
test('API filter Warm', r, 200)
if all(l.get('tier') == 'Warm' for l in data) and len(data) > 0:
    passes.append(f'API Warm filter correct ({len(data)} leads)')

r = client.get('/api/leads?tier=Cold')
data = r.get_json()
test('API filter Cold', r, 200)
if all(l.get('tier') == 'Cold' for l in data) and len(data) > 0:
    passes.append(f'API Cold filter correct ({len(data)} leads)')

# Single lead API
r = client.get('/api/leads/stripe.com')
data = r.get_json()
test('API lead detail stripe', r, 200)
if 'company' in data and 'score' in data:
    passes.append('API lead detail structure OK')
    if data['score'].get('total_score') == 88:
        passes.append('API stripe score = 88')
    else:
        errors.append(f'FAIL stripe score: {data["score"].get("total_score")}')
else:
    errors.append(f'FAIL API lead detail keys: {list(data.keys())}')

# Webhook
r = client.post('/api/webhook', json={'leads': [{'domain': 'test.com'}]},
                content_type='application/json')
test('API webhook valid', r, 200)

r = client.post('/api/webhook', json={'bad': 'data'}, content_type='application/json')
test('API webhook invalid', r, 400)

# ===== 13. ADMIN =====
print('\n--- 13. User Management ---')

r = client.post('/admin/users',
                data={'action': 'create', 'username': 'testviewer', 'password': 'test123', 'role': 'viewer'},
                follow_redirects=True)
test('Create viewer user', r, 200, 'User created')

r = client.post('/admin/users',
                data={'action': 'create', 'username': 'testeditor', 'password': 'test123', 'role': 'editor'},
                follow_redirects=True)
test('Create editor user', r, 200, 'User created')

r = client.post('/admin/users',
                data={'action': 'create', 'username': 'testviewer', 'password': 'test123', 'role': 'viewer'},
                follow_redirects=True)
test('Duplicate user rejected', r, 200, 'already exists')

r = client.post('/admin/users',
                data={'action': 'change_pw', 'username': 'testviewer', 'new_password': 'newpass'},
                follow_redirects=True)
test('Change password', r, 200, 'Password updated')

# Test viewer login
client.get('/logout')
r = client.post('/login', data={'username': 'testviewer', 'password': 'newpass'}, follow_redirects=True)
test('Viewer login', r, 200, 'Dashboard')

# Viewer can see pages
r = client.get('/leads')
test('Viewer sees leads', r, 200)

r = client.get('/analytics')
test('Viewer sees analytics', r, 200)

# Viewer blocked from admin
r = client.get('/admin/users')
test('Viewer blocked from admin', r, 403)

# Login back as admin
client.get('/logout')
client.post('/login', data={'username': 'admin', 'password': 'changeme'})

# ===== 14. INTEGRATIONS =====
print('\n--- 14. Integrations ---')

r = client.get('/integrations')
page = r.data.decode('utf-8', errors='replace')
test('Integrations page', r, 200)
for item in ['Google Sheets', 'HubSpot', 'Webhooks']:
    if item in page:
        passes.append(f'Integrations: {item}')
    else:
        errors.append(f'FAIL Integrations missing {item}')

# Sync sheets button exists
if 'sync-sheets' in page:
    passes.append('Integrations: sync button present')
else:
    errors.append('FAIL Integrations missing sync button')

# ===== 15. DOUBLE LOAD =====
print('\n--- 15. Idempotency Test ---')

r = client.post('/api/load-sample-data')
test('Second sample load', r, 200)

r = client.get('/api/leads')
data = r.get_json()
count = len(data)
if count == 40:
    passes.append(f'No duplicates: {count} leads')
else:
    errors.append(f'WARN Duplicates: expected 40, got {count}')

# ===== 16. NAVIGATION =====
print('\n--- 16. Navigation & UI Elements ---')

r = client.get('/')
page = r.data.decode('utf-8', errors='replace')
nav_items = ['Dashboard', 'Leads', 'Analytics', 'Pipeline Runs', 'Data Quality', 'Integrations', 'API', 'Settings']
for item in nav_items:
    if item in page:
        passes.append(f'Nav: {item}')
    else:
        errors.append(f'FAIL Nav missing: {item}')

# Sample data button
if 'Load Sample Data' in page:
    passes.append('Sample Data button present')
else:
    errors.append('FAIL Sample Data button missing')

# User info in sidebar
if 'admin' in page.lower() and 'Sign out' in page:
    passes.append('Sidebar shows user + signout')
else:
    errors.append('FAIL Sidebar missing user info')

# ===== 17. SCORE VALIDATION =====
print('\n--- 17. Score Validation ---')

r = client.get('/api/leads')
leads = r.get_json()
for lead in leads:
    score = lead.get('total_score', 0)
    tier = lead.get('tier', '')
    name = lead.get('company_name', '?')

    # Check tier matches score
    if score >= 70 and tier != 'Hot':
        errors.append(f'FAIL {name}: score {score} should be Hot, got {tier}')
    elif 40 <= score < 70 and tier != 'Warm':
        errors.append(f'FAIL {name}: score {score} should be Warm, got {tier}')
    elif score < 40 and tier != 'Cold':
        errors.append(f'FAIL {name}: score {score} should be Cold, got {tier}')

    # Check rule + soft = total
    rule = lead.get('rule_score', 0)
    soft = lead.get('soft_score', 0)
    if rule + soft != score:
        errors.append(f'FAIL {name}: rule({rule}) + soft({soft}) != total({score})')

passes.append('Score/tier validation complete')

# ===== 18. NEW FEATURES =====
print('\n--- 18. New Features ---')

# Compare page
r = client.get('/compare?domains=stripe.com,notion.so')
page = r.data.decode('utf-8', errors='replace')
test('Compare page loads', r, 200)
if 'compareChart' in page:
    passes.append('Compare: has chart')
else:
    errors.append('FAIL Compare missing chart')
if 'Stripe' in page and 'Notion' in page:
    passes.append('Compare: has both companies')
else:
    errors.append('FAIL Compare missing companies')

# Compare with no domains
r = client.get('/compare')
test('Compare empty state', r, 200, 'Select 2+ leads')

# Settings page (admin)
r = client.get('/admin/settings')
test('Settings page loads', r, 200)
page = r.data.decode('utf-8', errors='replace')
if 'Scoring Weights' in page:
    passes.append('Settings: has scoring weights')
else:
    errors.append('FAIL Settings missing scoring weights')
if 'Scoring Templates' in page:
    passes.append('Settings: has templates')
else:
    errors.append('FAIL Settings missing templates')

# Settings: apply template
r = client.post('/admin/settings', data={'action': 'template', 'template': 'enterprise_abm'}, follow_redirects=True)
test('Settings apply template', r, 200)

# Settings: update tiers
r = client.post('/admin/settings', data={'action': 'tiers', 'hot_min': '70', 'warm_min': '40'}, follow_redirects=True)
test('Settings update tiers', r, 200)

# Bulk API
r = client.post('/api/leads/bulk', json={'domains': ['stripe.com', 'notion.so', 'nonexistent.com']},
                content_type='application/json')
data = r.get_json()
test('API bulk leads', r, 200)
if data.get('found') == 2:
    passes.append('API bulk: found 2')
else:
    errors.append(f'FAIL API bulk: expected found=2, got {data.get("found")}')

# Routing rules API
r = client.get('/api/routing-rules')
data = r.get_json()
test('API routing rules', r, 200)
if 'hot_enterprise' in data and 'warm_nurture' in data:
    passes.append('API routing: has categories')
else:
    errors.append(f'FAIL API routing missing categories')

# OpenAPI spec
r = client.get('/api/openapi.yaml')
test('API OpenAPI spec', r, 200)
if b'openapi' in r.data:
    passes.append('OpenAPI spec is valid YAML')
else:
    errors.append('FAIL OpenAPI spec not valid')

# Print report
r = client.get('/leads/stripe.com/report?format=print')
page = r.data.decode('utf-8', errors='replace')
test('Print report loads', r, 200)
if 'Confidential' in page:
    passes.append('Print report: has footer')
else:
    errors.append('FAIL Print report missing footer')

# Security headers
r = client.get('/api/health')
if r.headers.get('X-Content-Type-Options') == 'nosniff':
    passes.append('Security: X-Content-Type-Options')
else:
    errors.append('FAIL Security: missing X-Content-Type-Options')
if r.headers.get('X-Frame-Options') == 'DENY':
    passes.append('Security: X-Frame-Options')
else:
    errors.append('FAIL Security: missing X-Frame-Options')
if 'Content-Security-Policy' in r.headers:
    passes.append('Security: CSP header present')
else:
    errors.append('FAIL Security: missing CSP')

# Notification bell in nav
r = client.get('/')
page = r.data.decode('utf-8', errors='replace')
if 'notifBtn' in page:
    passes.append('UI: notification bell present')
else:
    errors.append('FAIL UI missing notification bell')

# Keyboard shortcuts
if 'gPending' in page:
    passes.append('UI: keyboard shortcuts active')
else:
    errors.append('FAIL UI missing keyboard shortcuts')

# Command palette has new entries
if 'Compare Leads' in page:
    passes.append('Command palette: has Compare Leads')
else:
    errors.append('FAIL Command palette missing Compare Leads')

# Lead checkboxes for comparison
r = client.get('/leads')
page = r.data.decode('utf-8', errors='replace')
if 'lead-check' in page:
    passes.append('Leads: has comparison checkboxes')
else:
    errors.append('FAIL Leads missing comparison checkboxes')

if 'compareSelected' in page:
    passes.append('Leads: has compare button JS')
else:
    errors.append('FAIL Leads missing compare JS')

# Viewer blocked from settings
client.get('/logout')
client.post('/login', data={'username': 'testviewer', 'password': 'newpass'})
r = client.get('/admin/settings')
test('Viewer blocked from settings', r, 403)

# Editor can access settings
client.get('/logout')
client.post('/login', data={'username': 'admin', 'password': 'changeme'})
client.post('/admin/users',
            data={'action': 'create', 'username': 'testeditor2', 'password': 'test123', 'role': 'editor'},
            follow_redirects=True)
client.get('/logout')
client.post('/login', data={'username': 'testeditor2', 'password': 'test123'})
r = client.get('/admin/settings')
test('Editor can access settings', r, 200)

# Login back as admin for remaining tests
client.get('/logout')
client.post('/login', data={'username': 'admin', 'password': 'changeme'})

# ===== 19. ROUTING & ADVANCED FEATURES =====
print('\n--- 19. Routing & Advanced Features ---')

# Routing page
r = client.get('/routing')
page = r.data.decode('utf-8', errors='replace')
test('Routing page loads', r, 200)
if 'routeChart' in page:
    passes.append('Routing: has chart')
else:
    errors.append('FAIL Routing missing chart')
if 'Hot Enterprise' in page:
    passes.append('Routing: has queue labels')
else:
    errors.append('FAIL Routing missing queue labels')

# API bulk with empty
r = client.post('/api/leads/bulk', json={'bad': 'data'}, content_type='application/json')
test('API bulk bad request', r, 400)

# Settings weights update
r = client.post('/admin/settings', data={
    'action': 'weights', 'fit_weight': '50', 'engagement_weight': '30', 'intent_weight': '20'
}, follow_redirects=True)
test('Settings update weights', r, 200)
page = r.data.decode('utf-8', errors='replace')
if 'Scoring weights updated' in page:
    passes.append('Settings: weight update confirmed')
else:
    errors.append('FAIL Settings weight update not confirmed')

# Dashboard has activity feed
r = client.get('/')
page = r.data.decode('utf-8', errors='replace')
if 'Recent Activity' in page or 'feed-item' in page or 'activity' in page.lower():
    passes.append('Dashboard: has activity section')

# Verify compare chart data structure
r = client.get('/compare?domains=stripe.com,datadoghq.com,figma.com')
page = r.data.decode('utf-8', errors='replace')
test('Compare 3 leads', r, 200)
if 'Datadog' in page:
    passes.append('Compare: 3-way comparison works')
else:
    errors.append('FAIL Compare 3-way missing Datadog')

# Print report with auto_print
r = client.get('/leads/notion.so/report?format=print')
test('Print report Notion', r, 200)
page = r.data.decode('utf-8', errors='replace')
if 'auto_print' in page:
    passes.append('Print report: has auto_print JS')
else:
    errors.append('FAIL Print report missing auto_print')

# API key auth - no key configured, should pass
r = client.get('/api/leads')
test('API no key configured passes', r, 200)

# ===== 20. GDPR, SLA, DUPLICATES =====
print('\n--- 20. GDPR, SLA, Duplicates ---')

# GDPR export
r = client.get('/api/gdpr/export/stripe.com')
data = r.get_json()
test('GDPR export stripe', r, 200)
if 'company' in data and 'current_score' in data:
    passes.append('GDPR export: has company + score')
else:
    errors.append(f'FAIL GDPR export missing data: {list(data.keys())}')

r = client.get('/api/gdpr/export/nonexistent.com')
test('GDPR export 404', r, 404)

# GDPR delete request
r = client.post('/api/gdpr/delete/stripe.com')
data = r.get_json()
test('GDPR delete request', r, 200)
if data.get('status') == 'deletion_requested':
    passes.append('GDPR delete: correct status')
else:
    errors.append(f'FAIL GDPR delete status: {data}')

# SLA monitoring
r = client.get('/api/sla')
data = r.get_json()
test('SLA endpoint', r, 200)
if data.get('status') == 'healthy':
    passes.append('SLA: healthy status')
else:
    errors.append(f'FAIL SLA not healthy: {data}')
if 'db_query_ms' in data:
    passes.append(f'SLA: db_query_ms={data["db_query_ms"]}ms')
else:
    errors.append('FAIL SLA missing db_query_ms')

# Duplicate detection
r = client.get('/api/duplicates')
data = r.get_json()
test('Duplicates endpoint', r, 200)
if 'duplicates' in data and 'total_checked' in data:
    passes.append(f'Duplicates: checked {data["total_checked"]} leads')
else:
    errors.append(f'FAIL Duplicates response: {data}')

# ===== 21. ANALYTICS ENHANCEMENTS =====
print('\n--- 21. Analytics & Routing Extras ---')

# Analytics has new charts
r = client.get('/analytics')
page = r.data.decode('utf-8', errors='replace')
for chart in ['dimChart', 'stageChart']:
    if chart in page:
        passes.append(f'Analytics: {chart}')
    else:
        errors.append(f'FAIL Analytics missing {chart}')

# Routing has chart
r = client.get('/routing')
page = r.data.decode('utf-8', errors='replace')
if 'Warm Nurture' in page:
    passes.append('Routing: has Warm Nurture queue')
else:
    errors.append('FAIL Routing missing queues')

# API docs has new endpoints
r = client.get('/api-docs')
page = r.data.decode('utf-8', errors='replace')
for ep in ['/api/leads/bulk', '/api/routing-rules', '/api/openapi.yaml']:
    if ep in page:
        passes.append(f'API docs: {ep}')
    else:
        errors.append(f'FAIL API docs missing {ep}')

# Settings has decay info
r = client.get('/admin/settings')
page = r.data.decode('utf-8', errors='replace')
if 'Score Decay' in page:
    passes.append('Settings: has decay section')
else:
    errors.append('FAIL Settings missing decay')

if 'Tier Thresholds' in page:
    passes.append('Settings: has tier thresholds')
else:
    errors.append('FAIL Settings missing tier thresholds')

# ===== 22. ALL REMAINING FEATURES =====
print('\n--- 22. All Remaining Features ---')

# Kanban Board
r = client.get('/kanban')
page = r.data.decode('utf-8', errors='replace')
test('Kanban board loads', r, 200)
if 'kanbanBoard' in page:
    passes.append('Kanban: has board container')
else:
    errors.append('FAIL Kanban missing board')
if 'kanbanDrag' in page:
    passes.append('Kanban: has drag JS')
else:
    errors.append('FAIL Kanban missing drag JS')
for stage in ['Target', 'Awareness', 'Consideration', 'Decision', 'Purchase']:
    if stage in page:
        passes.append(f'Kanban: has {stage} column')

# Pipeline Velocity
r = client.get('/velocity')
page = r.data.decode('utf-8', errors='replace')
test('Velocity page loads', r, 200)
if 'winLossChart' in page:
    passes.append('Velocity: has win/loss chart')
else:
    errors.append('FAIL Velocity missing win/loss chart')
if 'Avg Days to Hot' in page:
    passes.append('Velocity: has KPIs')
else:
    errors.append('FAIL Velocity missing KPIs')
if 'Conversion to Next' in page:
    passes.append('Velocity: has conversion table')
else:
    errors.append('FAIL Velocity missing conversion table')

# Marketplace
r = client.get('/marketplace')
page = r.data.decode('utf-8', errors='replace')
test('Marketplace loads', r, 200)
for item in ['Google Sheets', 'HubSpot CRM', 'Apollo.io', 'Slack', 'Zapier', 'Salesforce', 'LinkedIn', 'SSO/SAML']:
    if item in page:
        passes.append(f'Marketplace: {item}')
    else:
        errors.append(f'FAIL Marketplace missing {item}')

# Workflows
r = client.get('/workflows')
page = r.data.decode('utf-8', errors='replace')
test('Workflows page loads', r, 200)
if 'wf-trigger' in page:
    passes.append('Workflows: has trigger nodes')
else:
    errors.append('FAIL Workflows missing trigger nodes')
if 'Nurture Triggers' in page:
    passes.append('Workflows: has nurture section')
else:
    errors.append('FAIL Workflows missing nurture')

# POST workflow rule
r = client.post('/workflows', data={'trigger': 'score_change', 'condition': 'score_above_70', 'action': 'send_slack'},
                follow_redirects=True)
test('Workflow create rule', r, 200)

# Champion/Challenger
r = client.get('/champion-challenger')
page = r.data.decode('utf-8', errors='replace')
test('Champion/Challenger loads', r, 200)
if 'Champion' in page and 'Challenger' in page:
    passes.append('Champion: has both models')
else:
    errors.append('FAIL Champion missing models')
if 'Model Version History' in page:
    passes.append('Champion: has version history')
else:
    errors.append('FAIL Champion missing version history')

# Webhook Log
r = client.get('/webhook-log')
test('Webhook log loads', r, 200)

# ABM View
r = client.get('/abm')
page = r.data.decode('utf-8', errors='replace')
test('ABM view loads', r, 200)
if 'Account-Based Scoring' in page:
    passes.append('ABM: has title')
else:
    errors.append('FAIL ABM missing title')
if 'Stripe' in page:
    passes.append('ABM: has lead data')
else:
    errors.append('FAIL ABM missing lead data')

# Leaderboard
r = client.get('/leaderboard')
page = r.data.decode('utf-8', errors='replace')
test('Leaderboard loads', r, 200)
if 'Score Achievements' in page:
    passes.append('Leaderboard: has achievements')
else:
    errors.append('FAIL Leaderboard missing achievements')
if 'lb-row' in page:
    passes.append('Leaderboard: has ranking rows')
else:
    errors.append('FAIL Leaderboard missing rows')

# Geographic View
r = client.get('/geo')
page = r.data.decode('utf-8', errors='replace')
test('Geo view loads', r, 200)
if 'geoBarChart' in page:
    passes.append('Geo: has bar chart')
else:
    errors.append('FAIL Geo missing chart')
if 'United States' in page:
    passes.append('Geo: has country data')
else:
    errors.append('FAIL Geo missing country data')

# Import page
r = client.get('/import')
page = r.data.decode('utf-8', errors='replace')
test('Import page loads', r, 200)
if 'Field Mapping Templates' in page:
    passes.append('Import: has templates')
else:
    errors.append('FAIL Import missing templates')
for tmpl in ['HubSpot', 'Salesforce', 'Apollo', 'LinkedIn']:
    if tmpl in page:
        passes.append(f'Import: has {tmpl} template')

# Score explanation on detail page
r = client.get('/leads/stripe.com')
page = r.data.decode('utf-8', errors='replace')
if 'Score Explanation' in page:
    passes.append('Detail: has NL score explanation')
else:
    errors.append('FAIL Detail missing score explanation')
if 'sales-ready' in page or 'nurtured' in page or 'qualification' in page:
    passes.append('Detail: explanation has actionable text')
else:
    errors.append('FAIL Detail explanation missing actionable text')

# Sidebar has new items
r = client.get('/')
page = r.data.decode('utf-8', errors='replace')
if 'Pipeline Board' in page:
    passes.append('Sidebar: has Pipeline Board')
else:
    errors.append('FAIL Sidebar missing Pipeline Board')
if 'Workflows' in page:
    passes.append('Sidebar: has Workflows')
else:
    errors.append('FAIL Sidebar missing Workflows')

# Command palette has new entries
for cmd in ['Pipeline Board', 'Pipeline Velocity', 'Geographic View', 'Account-Based', 'Leaderboard', 'Marketplace', 'Workflows', 'Champion/Challenger', 'Webhook Log', 'Import Leads']:
    if cmd in page:
        passes.append(f'CmdPalette: {cmd}')

# Integrations page still works (now redirected to marketplace link)
r = client.get('/integrations')
test('Old integrations page still works', r, 200)

# ===== 23. DATA DIVERSITY VALIDATION =====
print('\n--- 23. Data Diversity Validation ---')

r = client.get('/api/leads')
leads = r.get_json()

# Tier distribution
tiers = {}
for l in leads:
    t = l.get('tier', 'Unknown')
    tiers[t] = tiers.get(t, 0) + 1
for tier_name in ['Hot', 'Warm', 'Cold']:
    count = tiers.get(tier_name, 0)
    if count >= 5:
        passes.append(f'Diversity: {tier_name} has {count} leads')
    else:
        errors.append(f'FAIL Diversity: {tier_name} has only {count} leads (need >= 5)')

# Geographic diversity
r = client.get('/geo')
page = r.data.decode('utf-8', errors='replace')
for country in ['United States', 'United Kingdom', 'Germany', 'India', 'Australia']:
    if country in page:
        passes.append(f'Geo diversity: {country} present')
    else:
        errors.append(f'FAIL Geo diversity: {country} missing')

# Buying stage diversity
stages = {}
for l in leads:
    s = l.get('buying_stage', 'Unknown')
    stages[s] = stages.get(s, 0) + 1
for stage_name in ['Target', 'Awareness', 'Consideration', 'Decision', 'Purchase']:
    if stages.get(stage_name, 0) >= 1:
        passes.append(f'Diversity: {stage_name} stage has {stages[stage_name]} leads')
    else:
        errors.append(f'FAIL Diversity: {stage_name} stage has 0 leads')

# Matrix cell diversity
matrix_cells = set()
for l in leads:
    mc = l.get('matrix_cell', '')
    if mc:
        matrix_cells.add(mc)
if len(matrix_cells) >= 6:
    passes.append(f'Diversity: {len(matrix_cells)} distinct matrix cells')
else:
    errors.append(f'FAIL Diversity: only {len(matrix_cells)} matrix cells (need >= 6)')

# Industry diversity
industries = set()
for l in leads:
    ind = l.get('industry', '')
    if ind:
        industries.add(ind)
if len(industries) >= 8:
    passes.append(f'Diversity: {len(industries)} distinct industries')
else:
    errors.append(f'FAIL Diversity: only {len(industries)} industries (need >= 8)')

# Score range coverage
scores = [l.get('total_score', 0) for l in leads]
if min(scores) <= 20:
    passes.append(f'Diversity: low score {min(scores)} present')
else:
    errors.append(f'FAIL Diversity: min score {min(scores)} too high')
if max(scores) >= 85:
    passes.append(f'Diversity: high score {max(scores)} present')
else:
    errors.append(f'FAIL Diversity: max score {max(scores)} too low')

# Detail pages for new companies
for domain in ['wise.com', 'razorpay.com', 'personio.com', 'wiz.io', 'atlassian.com']:
    r = client.get(f'/leads/{domain}')
    test(f'Detail: {domain}', r, 200)

# ===== RESULTS =====
print('\n' + '=' * 60)
print(f'  RESULTS: {len(passes)} PASSED, {len(errors)} FAILED')
print('=' * 60)

if errors:
    print('\nFAILURES:')
    for e in errors:
        print(f'  x {e}')

print(f'\nTotal: {len(passes)} passed, {len(errors)} failed')
if not errors:
    print('\nALL TESTS PASSED!')
    sys.exit(0)
else:
    sys.exit(1)
