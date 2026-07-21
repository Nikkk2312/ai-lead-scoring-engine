"""
Additional dashboard page templates for advanced features.
Kanban board, pipeline velocity, workflow builder, champion/challenger,
webhook log, ABM view, marketplace, leaderboard.
"""

KANBAN_CONTENT = """
<div class="kanban" id="kanbanBoard">
  {% for stage in ['Target','Awareness','Consideration','Decision','Purchase'] %}
  <div class="kanban-col" data-stage="{{ stage }}" ondragover="event.preventDefault()" ondrop="kanbanDrop(event,'{{ stage }}')">
    <h4>{{ stage }} <span class="cnt">{{ stage_counts[stage] }}</span></h4>
    {% for l in kanban_leads if (l.buying_stage or 'Target') == stage %}
    <div class="kanban-card" draggable="true" ondragstart="kanbanDrag(event,'{{ l.domain }}')" id="kc-{{ l.domain|replace('.','_') }}">
      <div class="kc-name"><a href="/leads/{{ l.domain }}">{{ l.company_name }}</a></div>
      <div class="kc-score">
        <span style="color:{{ l._color }};font-weight:700">{{ l.total_score }}</span>
        <span class="badge badge-{{ l.tier|lower }}" style="font-size:.7em;padding:2px 6px;margin-left:4px">{{ l.tier }}</span>
      </div>
      <div class="kc-meta">{{ l.industry_classified or l.industry or '' }} | {{ l.hq_country or '?' }}</div>
    </div>
    {% endfor %}
  </div>
  {% endfor %}
</div>
<script>
function kanbanDrag(e,domain){e.dataTransfer.setData('text/plain',domain);e.target.classList.add('dragging');}
function kanbanDrop(e,stage){
  e.preventDefault();
  const domain=e.dataTransfer.getData('text/plain');
  document.querySelectorAll('.kanban-card').forEach(c=>c.classList.remove('dragging'));
  const col=e.currentTarget.querySelector('h4 .cnt')?e.currentTarget:e.target.closest('.kanban-col');
  const card=document.getElementById('kc-'+domain.replace(/\\./g,'_'));
  if(card&&col){col.appendChild(card);}
  fetch('/api/lead/'+encodeURIComponent(domain)+'/stage',{method:'POST',
    headers:{'Content-Type':'application/json'},body:JSON.stringify({stage:stage})})
    .then(r=>r.json()).then(d=>{showToast(d.status==='ok'?'Moved '+domain+' to '+stage:'Move failed');})
    .catch(()=>showToast('Move failed'));
}
</script>
"""

VELOCITY_CONTENT = """
<div class="kpis">
  <div class="kpi total"><div class="value val-accent">{{ velocity.avg_days_to_hot }}</div><div class="label">Avg Days to Hot</div></div>
  <div class="kpi hot"><div class="value val-hot">{{ velocity.hot_conversion }}%</div><div class="label">Hot Conversion Rate</div></div>
  <div class="kpi warm"><div class="value val-warm">{{ velocity.warm_to_hot }}%</div><div class="label">Warm-to-Hot Rate</div></div>
  <div class="kpi score"><div class="value">{{ velocity.avg_score_change }}</div><div class="label">Avg Score Change</div></div>
</div>
<div class="grid-2">
  <div class="card">
    <h3>Stage Conversion Funnel</h3>
    <div class="funnel">
      {% for stage, pct in velocity.funnel %}
      <div class="funnel-step">
        <span style="width:120px;font-size:.82em;color:var(--text2)">{{ stage }}</span>
        <div class="funnel-bar" style="width:{{ pct }}%;background:{{ stage_colors[loop.index0 % 5] }}">{{ pct }}%</div>
      </div>
      {% endfor %}
    </div>
  </div>
  <div class="card">
    <h3>Win/Loss Analysis</h3>
    <div class="chart-box"><canvas id="winLossChart"></canvas></div>
  </div>
</div>
<div class="card">
  <h3>Pipeline Velocity by Stage</h3>
  <div class="tbl-wrap"><table>
    <thead><tr><th>Stage</th><th>Leads</th><th>Avg Score</th><th>Avg Days in Stage</th><th>Conversion to Next</th></tr></thead>
    <tbody>
    {% for s in velocity.stage_details %}
    <tr><td><span class="badge badge-{{ s.stage|lower }}">{{ s.stage }}</span></td>
        <td>{{ s.count }}</td><td>{{ s.avg_score }}</td><td>{{ s.avg_days }}</td>
        <td>{{ s.conversion_pct }}%</td></tr>
    {% endfor %}
    </tbody>
  </table></div>
</div>
<script>
const wl={{ winloss_json|safe }};
new Chart(document.getElementById('winLossChart'),{type:'doughnut',data:{
  labels:['Accepted','Rejected','Too High','Too Low','Pending'],
  datasets:[{data:[wl.accept||0,wl.reject||0,wl.too_high||0,wl.too_low||0,wl.pending||0],
    backgroundColor:['#22c55e','#ef4444','#f59e0b','#3b82f6','#64748b'],borderWidth:0}]},
  options:{cutout:'60%',plugins:{legend:{position:'bottom',labels:{color:'#94a3b8',padding:12,usePointStyle:true}}}}});
</script>
"""

MARKETPLACE_CONTENT = """
<h3 class="mb-4">Integration Marketplace</h3>
<p class="text-muted mb-4">Connect your lead scoring engine with your favorite tools.</p>
<div class="mkt-grid">
  {% for i in integrations_list %}
  <div class="mkt-card">
    <div class="mkt-icon">{{ i.icon }}</div>
    <div class="mkt-name">{{ i.name }}</div>
    <div class="mkt-desc">{{ i.description }}</div>
    <div class="mkt-status {{ 'mkt-on' if i.connected else 'mkt-off' }}">{{ 'Connected' if i.connected else 'Available' }}</div>
  </div>
  {% endfor %}
</div>
"""

WORKFLOW_CONTENT = """
<div class="grid-2">
  <div class="card">
    <h3>Active Workflow Rules</h3>
    <p class="text-muted mb-4">Automate actions based on lead scoring events.</p>
    <div class="wf-canvas">
      {% for rule in rules %}
      <div style="display:flex;align-items:center;flex-wrap:wrap;margin-bottom:12px;gap:4px">
        <div class="wf-node wf-trigger"><div class="wf-type">Trigger</div><div class="wf-label">{{ rule.trigger }}</div></div>
        <span class="wf-arrow">&rarr;</span>
        <div class="wf-node wf-condition"><div class="wf-type">Condition</div><div class="wf-label">{{ rule.condition }}</div></div>
        <span class="wf-arrow">&rarr;</span>
        <div class="wf-node wf-action"><div class="wf-type">Action</div><div class="wf-label">{{ rule.action }}</div></div>
        <span style="margin-left:auto"><span class="badge {{ 'mkt-on' if rule.enabled else 'mkt-off' }}">{{ 'Active' if rule.enabled else 'Paused' }}</span></span>
      </div>
      {% endfor %}
    </div>
  </div>
  <div>
    <div class="card">
      <h3>Create Rule</h3>
      <form method="POST" action="/workflows">
        <div class="form-row" style="flex-direction:column;gap:10px">
          <select name="trigger" style="background:var(--surface);color:var(--text);border:1px solid var(--border);padding:8px 14px;border-radius:8px;font-size:.85em">
            <option value="score_change">Score Changes</option>
            <option value="tier_change">Tier Changes</option>
            <option value="new_lead">New Lead Scored</option>
            <option value="stage_change">Stage Changes</option>
          </select>
          <select name="condition" style="background:var(--surface);color:var(--text);border:1px solid var(--border);padding:8px 14px;border-radius:8px;font-size:.85em">
            <option value="score_above_70">Score &gt; 70</option>
            <option value="score_above_40">Score &gt; 40</option>
            <option value="tier_is_hot">Tier = Hot</option>
            <option value="stage_is_purchase">Stage = Purchase</option>
            <option value="fit_grade_a">Fit Grade = A</option>
          </select>
          <select name="action" style="background:var(--surface);color:var(--text);border:1px solid var(--border);padding:8px 14px;border-radius:8px;font-size:.85em">
            <option value="send_slack">Send Slack Alert</option>
            <option value="send_email">Send Email</option>
            <option value="push_crm">Push to CRM</option>
            <option value="add_watchlist">Add to Watchlist</option>
            <option value="assign_rep">Assign to Rep</option>
          </select>
          <button class="btn btn-primary btn-sm">Add Rule</button>
        </div>
      </form>
    </div>
    <div class="card">
      <h3>Nurture Triggers</h3>
      <p class="text-muted">Automated sequences based on lead behavior.</p>
      <div style="margin-top:12px">
        {% for trigger in nurture_triggers %}
        <div style="display:flex;align-items:center;gap:8px;padding:8px 0;border-bottom:1px solid rgba(30,41,59,.3);font-size:.85em">
          <span class="badge" style="background:rgba(99,102,241,.1);color:#a5b4fc">{{ trigger.event }}</span>
          <span>&rarr;</span>
          <span>{{ trigger.action }}</span>
          <span style="margin-left:auto" class="text-muted">{{ trigger.delay }}</span>
        </div>
        {% endfor %}
      </div>
    </div>
  </div>
</div>
"""

CHAMPION_CONTENT = """
<div class="kpis">
  <div class="kpi total"><div class="value val-accent">{{ models|length }}</div><div class="label">Model Versions</div></div>
  <div class="kpi hot"><div class="value" style="font-size:1.2em">{{ champion.name }}</div><div class="label">Champion</div></div>
  <div class="kpi warm"><div class="value" style="font-size:1.2em">{{ challenger.name if challenger else 'None' }}</div><div class="label">Challenger</div></div>
  <div class="kpi score"><div class="value">{{ champion.accuracy }}%</div><div class="label">Champion Accuracy</div></div>
</div>
<div class="grid-2">
  <div class="card">
    <h3>Champion Model</h3>
    <p><strong>{{ champion.name }}</strong> (v{{ champion.version }})</p>
    <p class="text-muted mt-2">Fit: {{ champion.fit_w }}% | Engagement: {{ champion.eng_w }}% | Intent: {{ champion.int_w }}%</p>
    <p class="mt-2">Leads scored: {{ champion.leads_scored }} | Accuracy: {{ champion.accuracy }}%</p>
    <div class="dim-bars mt-4">
      <div class="dim-bar"><span class="lbl">Fit</span>
        <div class="track"><div class="fill fill-fit" style="width:{{ champion.fit_w }}%"></div></div>
        <span class="pct" style="color:#818cf8">{{ champion.fit_w }}%</span></div>
      <div class="dim-bar"><span class="lbl">Engagement</span>
        <div class="track"><div class="fill fill-eng" style="width:{{ champion.eng_w }}%"></div></div>
        <span class="pct" style="color:#fbbf24">{{ champion.eng_w }}%</span></div>
      <div class="dim-bar"><span class="lbl">Intent</span>
        <div class="track"><div class="fill fill-int" style="width:{{ champion.int_w }}%"></div></div>
        <span class="pct" style="color:#4ade80">{{ champion.int_w }}%</span></div>
    </div>
  </div>
  {% if challenger %}
  <div class="card">
    <h3>Challenger Model</h3>
    <p><strong>{{ challenger.name }}</strong> (v{{ challenger.version }})</p>
    <p class="text-muted mt-2">Fit: {{ challenger.fit_w }}% | Engagement: {{ challenger.eng_w }}% | Intent: {{ challenger.int_w }}%</p>
    <p class="mt-2">Leads scored: {{ challenger.leads_scored }} | Accuracy: {{ challenger.accuracy }}%</p>
    {% if challenger.accuracy > champion.accuracy %}
    <form method="POST" action="/champion-challenger" class="mt-4">
      <input type="hidden" name="action" value="promote">
      <button class="btn btn-primary btn-sm">Promote Challenger</button>
    </form>
    {% endif %}
  </div>
  {% else %}
  <div class="card">
    <h3>No Challenger</h3>
    <p class="text-muted">Configure a challenger model to A/B test scoring weights.</p>
  </div>
  {% endif %}
</div>
<div class="card">
  <h3>Model Version History</h3>
  <div class="tbl-wrap"><table>
    <thead><tr><th>Version</th><th>Name</th><th>Weights</th><th>Leads</th><th>Accuracy</th><th>Status</th><th>Created</th></tr></thead>
    <tbody>{% for m in models %}
    <tr><td>v{{ m.version }}</td><td>{{ m.name }}</td>
        <td style="font-size:.82em">F:{{ m.fit_w }}% E:{{ m.eng_w }}% I:{{ m.int_w }}%</td>
        <td>{{ m.leads_scored }}</td><td>{{ m.accuracy }}%</td>
        <td><span class="badge {{ 'badge-hot' if m.status=='champion' else 'badge-warm' if m.status=='challenger' else '' }}">{{ m.status }}</span></td>
        <td class="text-muted">{{ m.created }}</td></tr>
    {% endfor %}</tbody>
  </table></div>
</div>
"""

WEBHOOK_LOG_CONTENT = """
<div class="card">
  <h3>Webhook Event Log</h3>
  <p class="text-muted mb-4">Recent webhook deliveries and API calls.</p>
  {% if events %}
  <div class="tbl-wrap"><table>
    <thead><tr><th>Time</th><th>Type</th><th>Endpoint</th><th>Status</th><th>Duration</th><th>Payload</th></tr></thead>
    <tbody>{% for e in events %}
    <tr><td class="text-muted">{{ e.time }}</td><td>{{ e.type }}</td><td><code>{{ e.endpoint }}</code></td>
        <td><span class="badge {{ 'badge-completed' if e.status == 200 else 'badge-hot' }}">{{ e.status }}</span></td>
        <td>{{ e.duration_ms }}ms</td>
        <td style="max-width:200px;overflow:hidden;text-overflow:ellipsis;font-size:.78em">{{ e.payload_preview }}</td></tr>
    {% endfor %}</tbody>
  </table></div>
  {% else %}
  <div class="empty"><p>No webhook events recorded yet. Events appear here when webhooks are triggered.</p></div>
  {% endif %}
</div>
"""

ABM_CONTENT = """
<div class="kpis">
  <div class="kpi total"><div class="value val-accent">{{ accounts|length }}</div><div class="label">Accounts</div></div>
  <div class="kpi hot"><div class="value val-hot">{{ hot_accounts }}</div><div class="label">Hot Accounts</div></div>
  <div class="kpi score"><div class="value">{{ '%.1f'|format(avg_account_score) }}</div><div class="label">Avg Account Score</div></div>
</div>
<div class="card">
  <h3>Account-Based Scoring</h3>
  <p class="text-muted mb-4">Leads grouped by parent account with aggregate scoring.</p>
  <div class="tbl-wrap"><table>
    <thead><tr><th>Account</th><th>Leads</th><th>Avg Score</th><th>Top Tier</th><th>Industry</th><th>Stage</th></tr></thead>
    <tbody>{% for a in accounts %}
    <tr><td><a href="/leads/{{ a.domain }}"><strong>{{ a.name }}</strong></a></td>
        <td>{{ a.lead_count }}</td>
        <td><span style="color:{{ a.color }};font-weight:700">{{ a.avg_score }}</span></td>
        <td><span class="badge badge-{{ a.top_tier|lower }}">{{ a.top_tier }}</span></td>
        <td>{{ a.industry }}</td>
        <td><span class="badge badge-{{ a.stage|lower }}">{{ a.stage }}</span></td></tr>
    {% endfor %}</tbody>
  </table></div>
</div>
"""

LEADERBOARD_CONTENT = """
<div class="grid-2">
  <div class="card">
    <h3>Scoring Leaderboard</h3>
    <p class="text-muted mb-4">Top performing leads by composite score.</p>
    {% for i, l in enumerate(leaders) %}
    <div class="lb-row">
      <div class="lb-rank {{ 'lb-gold' if i==0 else 'lb-silver' if i==1 else 'lb-bronze' if i==2 else '' }}">{{ i+1 }}</div>
      <div class="lb-info">
        <div><a href="/leads/{{ l.domain }}"><strong>{{ l.company_name }}</strong></a></div>
        <div class="text-muted" style="font-size:.78em">{{ l.industry_classified or l.industry or '' }} | {{ l.hq_country or '' }}</div>
      </div>
      <div class="lb-score-val" style="color:{{ l._color }}">{{ l.total_score }}</div>
    </div>
    {% endfor %}
  </div>
  <div class="card">
    <h3>Score Achievements</h3>
    <p class="text-muted mb-4">Milestones and badges earned.</p>
    {% for badge in badges %}
    <div style="display:flex;align-items:center;gap:12px;padding:8px 0;border-bottom:1px solid rgba(30,41,59,.3)">
      <span style="font-size:1.5em">{{ badge.icon }}</span>
      <div>
        <div style="font-weight:600;font-size:.88em">{{ badge.name }}</div>
        <div class="text-muted" style="font-size:.78em">{{ badge.description }}</div>
      </div>
      {% if badge.earned %}<span class="badge mkt-on" style="margin-left:auto">Earned</span>{% endif %}
    </div>
    {% endfor %}
  </div>
</div>
"""

GEO_CONTENT = """
<div class="card">
  <h3>Geographic Distribution</h3>
  <p class="text-muted mb-4">Lead scores by country and region.</p>
  <div class="tbl-wrap"><table>
    <thead><tr><th>Country</th><th>Leads</th><th>Avg Score</th><th>Hot</th><th>Warm</th><th>Cold</th><th>Top Industry</th></tr></thead>
    <tbody>{% for g in geo_data %}
    <tr><td><strong>{{ g.country }}</strong></td>
        <td>{{ g.count }}</td>
        <td><span style="font-weight:700">{{ g.avg_score }}</span></td>
        <td class="val-hot">{{ g.hot }}</td>
        <td class="val-warm">{{ g.warm }}</td>
        <td class="val-cold">{{ g.cold }}</td>
        <td>{{ g.top_industry }}</td></tr>
    {% endfor %}</tbody>
  </table></div>
</div>
<div class="card">
  <h3>Region Heatmap</h3>
  <div class="chart-box"><canvas id="geoBarChart"></canvas></div>
</div>
<script>
const gd={{ geo_json|safe }};
new Chart(document.getElementById('geoBarChart'),{type:'bar',data:{
  labels:gd.map(g=>g.country),
  datasets:[
    {label:'Hot',data:gd.map(g=>g.hot),backgroundColor:'#ef4444',borderRadius:4},
    {label:'Warm',data:gd.map(g=>g.warm),backgroundColor:'#f59e0b',borderRadius:4},
    {label:'Cold',data:gd.map(g=>g.cold),backgroundColor:'#22c55e',borderRadius:4}]},
  options:{scales:{x:{stacked:true,grid:{display:false},ticks:{color:'#64748b'}},
    y:{stacked:true,grid:{color:'rgba(30,41,59,.5)'},ticks:{color:'#64748b'}}},
    plugins:{legend:{labels:{color:'#94a3b8',usePointStyle:true}}}}});
</script>
"""

IMPORT_CONTENT = """
<div class="grid-2">
  <div class="card">
    <h3>Import Leads</h3>
    <p class="text-muted mb-4">Upload a CSV file to score new leads.</p>
    <form method="POST" action="/import" enctype="multipart/form-data">
      <div class="form-row" style="flex-direction:column;gap:12px">
        <div>
          <label class="text-muted" style="font-size:.82em">CSV File</label>
          <input type="file" name="csv_file" accept=".csv" style="margin-top:4px;width:100%">
        </div>
        <div>
          <label class="text-muted" style="font-size:.82em">Field Mapping Template</label>
          <select name="template" style="background:var(--surface);color:var(--text);border:1px solid var(--border);padding:8px 14px;border-radius:8px;font-size:.85em;width:100%">
            <option value="default">Default (company_name, domain)</option>
            <option value="hubspot">HubSpot Export</option>
            <option value="salesforce">Salesforce Export</option>
            <option value="apollo">Apollo.io Export</option>
            <option value="linkedin">LinkedIn Sales Nav</option>
            <option value="custom">Custom Mapping</option>
          </select>
        </div>
        <div>
          <label class="text-muted" style="font-size:.82em">ICP Profile</label>
          <select name="icp" style="background:var(--surface);color:var(--text);border:1px solid var(--border);padding:8px 14px;border-radius:8px;font-size:.85em;width:100%">
            {% for key, icp in icps.items() %}
            <option value="{{ key }}">{{ icp.name }}</option>
            {% endfor %}
          </select>
        </div>
        <button class="btn btn-primary">Upload &amp; Score</button>
      </div>
    </form>
  </div>
  <div class="card">
    <h3>Field Mapping Templates</h3>
    <p class="text-muted mb-4">Map columns from different export formats.</p>
    <div class="tbl-wrap"><table>
      <thead><tr><th>Template</th><th>Company Name Column</th><th>Domain Column</th><th>Extra Fields</th></tr></thead>
      <tbody>
      {% for t in templates %}
      <tr><td><strong>{{ t.name }}</strong></td><td><code>{{ t.company_col }}</code></td>
          <td><code>{{ t.domain_col }}</code></td><td class="text-muted">{{ t.extras }}</td></tr>
      {% endfor %}
      </tbody>
    </table></div>
  </div>
</div>
"""
