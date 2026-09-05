// ==============================================================================
// Nevis Agentic Onboarding Platform — Dashboard Client Application
// ==============================================================================

let currentTab = 'canonical';
let currentEntity = 'households';
let canonicalData = {};
let clarificationsData = { pending: [], resolved: [] };
let advisorsList = [];
let searchQuery = '';

document.addEventListener('DOMContentLoaded', () => {
  initDashboard();
});

async function initDashboard() {
  await fetchStatus();
  await fetchCanonicalData();
  await fetchClarifications();
  await fetchRules();
  await fetchAuditReport();
  await fetchSlackMessage();
}

// ------------------------------------------------------------------------------
// Navigation & Tab Switching
// ------------------------------------------------------------------------------
function switchTab(tabId) {
  currentTab = tabId;
  document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
  document.querySelectorAll('.tab-content').forEach(content => content.classList.remove('active'));

  const activeBtn = Array.from(document.querySelectorAll('.tab-btn')).find(b => 
    b.getAttribute('onclick').includes(tabId)
  );
  if (activeBtn) activeBtn.classList.add('active');

  const contentEl = document.getElementById(`tab-${tabId}`);
  if (contentEl) contentEl.classList.add('active');

  if (tabId === 'slack') {
    fetchSlackMessage();
  }
}

function filterEntityType(entityType) {
  currentEntity = entityType;
  document.querySelectorAll('.sub-filter-btn').forEach(btn => btn.classList.remove('active'));
  const activeBtn = Array.from(document.querySelectorAll('.sub-filter-btn')).find(b => 
    b.getAttribute('onclick').includes(entityType)
  );
  if (activeBtn) activeBtn.classList.add('active');
  renderCanonicalTable();
}

function handleCanonicalSearch() {
  searchQuery = document.getElementById('canonicalSearch').value.toLowerCase();
  renderCanonicalTable();
}

// ------------------------------------------------------------------------------
// API Data Fetchers
// ------------------------------------------------------------------------------
async function fetchStatus() {
  try {
    const res = await fetch('/api/pipeline/status');
    const data = await res.json();
    document.getElementById('kpiAum').textContent = `$${data.total_aum_usd.toLocaleString(undefined, {minimumFractionDigits: 0, maximumFractionDigits: 0})}`;
    document.getElementById('kpiHouseholds').textContent = data.total_households;
    document.getElementById('kpiAccounts').textContent = data.total_accounts;
    document.getElementById('kpiClients').textContent = data.total_clients;
    document.getElementById('kpiClarif').textContent = data.total_clarifications;
    document.getElementById('kpiClarifBadge').textContent = `${data.total_clarifications} ITEMS`;
    document.getElementById('triageCounter').textContent = data.total_clarifications;
  } catch (err) {
    console.error('Failed to fetch status:', err);
  }
}

async function fetchCanonicalData() {
  try {
    const res = await fetch('/api/canonical');
    canonicalData = await res.json();
    advisorsList = canonicalData.advisors || [];

    document.getElementById('countHh').textContent = (canonicalData.households || []).length;
    document.getElementById('countCli').textContent = (canonicalData.clients || []).length;
    document.getElementById('countAcc').textContent = (canonicalData.accounts || []).length;
    document.getElementById('countAdv').textContent = (canonicalData.advisors || []).length;
    document.getElementById('countInt').textContent = (canonicalData.interactions || []).length;

    renderCanonicalTable();
  } catch (err) {
    console.error('Failed to fetch canonical book:', err);
  }
}

async function fetchClarifications() {
  try {
    const res = await fetch('/api/clarifications');
    clarificationsData = await res.json();
    renderTriageList();
  } catch (err) {
    console.error('Failed to fetch clarifications:', err);
  }
}

async function fetchRules() {
  try {
    const res = await fetch('/api/rules');
    const data = await res.json();
    renderRulesGrid(data.rules || []);
  } catch (err) {
    console.error('Failed to fetch rules:', err);
  }
}

async function fetchAuditReport() {
  try {
    const res = await fetch('/api/audit');
    const data = await res.json();
    renderAuditReport(data);
  } catch (err) {
    console.error('Failed to fetch audit report:', err);
  }
}

async function fetchSlackMessage() {
  try {
    const res = await fetch('/api/export/slack');
    const text = await res.text();
    document.getElementById('slackMarkdownContent').textContent = text;
  } catch (err) {
    console.error('Failed to fetch Slack markdown:', err);
  }
}

async function triggerPipelineRun() {
  const btn = document.getElementById('runPipelineBtn');
  btn.disabled = true;
  btn.innerHTML = '<span>Executing Pipeline...</span>';

  try {
    const res = await fetch('/api/pipeline/run', { method: 'POST' });
    const data = await res.json();
    showToast(data.message || 'Pipeline executed successfully.');
    await initDashboard();
  } catch (err) {
    showToast('Pipeline execution error.');
  } finally {
    btn.disabled = false;
    btn.innerHTML = `
      <svg class="btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <polygon points="5 3 19 12 5 21 5 3"></polygon>
      </svg>
      <span>Execute Sync Pipeline</span>
    `;
  }
}

// ------------------------------------------------------------------------------
// Renderers
// ------------------------------------------------------------------------------
function renderCanonicalTable() {
  const thead = document.getElementById('canonicalThead');
  const tbody = document.getElementById('canonicalTbody');
  thead.innerHTML = '';
  tbody.innerHTML = '';

  let items = canonicalData[currentEntity] || [];

  if (searchQuery) {
    items = items.filter(item => JSON.stringify(item).toLowerCase().includes(searchQuery));
  }

  if (items.length === 0) {
    tbody.innerHTML = `<tr><td colspan="6" style="text-align:center; color:#6b7280; padding:32px;">No matching records found.</td></tr>`;
    return;
  }

  if (currentEntity === 'households') {
    thead.innerHTML = `
      <tr>
        <th>Household ID</th>
        <th>Household Name</th>
        <th>Primary Advisor</th>
        <th>Status</th>
        <th>Total AUM (USD)</th>
        <th>Source Tags / Lineage</th>
      </tr>
    `;
    tbody.innerHTML = items.map(h => `
      <tr onclick="openProvenanceDrawer('Household', '${h.household_id}')">
        <td><code>${h.household_id}</code></td>
        <td style="font-weight:600; color:#fff;">${h.household_name}</td>
        <td><code>${h.primary_advisor_id || 'N/A'}</code></td>
        <td><span class="badge badge-${(h.status || 'active').toLowerCase()}">${h.status}</span></td>
        <td style="font-family:var(--font-mono); font-weight:600;">${h.market_value_usd !== null ? '$' + h.market_value_usd.toLocaleString(undefined, {minimumFractionDigits: 2}) : '<span style="color:#6b7280;">null (Rule 3)</span>'}</td>
        <td>${(h.source_tags || []).slice(0, 3).map(t => `<span class="badge badge-tag">${t}</span>`).join('')}</td>
      </tr>
    `).join('');
  } else if (currentEntity === 'clients') {
    thead.innerHTML = `
      <tr>
        <th>Client ID</th>
        <th>Full Name</th>
        <th>Household ID</th>
        <th>Role</th>
        <th>Source Tags</th>
      </tr>
    `;
    tbody.innerHTML = items.map(c => `
      <tr onclick="openProvenanceDrawer('Client', '${c.client_id}')">
        <td><code>${c.client_id}</code></td>
        <td style="font-weight:600; color:#fff;">${c.first_name} ${c.last_name}</td>
        <td><code>${c.household_id}</code></td>
        <td><span class="badge badge-tag">${c.role}</span></td>
        <td>${(c.source_tags || []).slice(0, 3).map(t => `<span class="badge badge-tag">${t}</span>`).join('')}</td>
      </tr>
    `).join('');
  } else if (currentEntity === 'accounts') {
    thead.innerHTML = `
      <tr>
        <th>Account ID</th>
        <th>Holder Name</th>
        <th>Household ID</th>
        <th>Type</th>
        <th>Market Value (USD)</th>
        <th>Original Currency</th>
        <th>Custodian</th>
      </tr>
    `;
    tbody.innerHTML = items.map(a => `
      <tr onclick="openProvenanceDrawer('Account', '${a.account_id}')">
        <td><code>${a.account_id}</code></td>
        <td style="font-weight:600; color:#fff;">${a.account_holder_raw}</td>
        <td><code>${a.household_id}</code></td>
        <td><span class="badge badge-tag">${a.account_type}</span></td>
        <td style="font-family:var(--font-mono); font-weight:600; color:#34d399;">$${(a.market_value_usd || 0).toLocaleString(undefined, {minimumFractionDigits: 2})}</td>
        <td><code>${a.currency_original}</code> ${a.currency_original !== 'USD' ? '<span class="badge badge-prospect">Converted</span>' : ''}</td>
        <td>${a.custodian}</td>
      </tr>
    `).join('');
  } else if (currentEntity === 'advisors') {
    thead.innerHTML = `
      <tr>
        <th>Advisor ID</th>
        <th>Full Name</th>
        <th>Role</th>
        <th>Office</th>
      </tr>
    `;
    tbody.innerHTML = items.map(adv => `
      <tr onclick="openProvenanceDrawer('Advisor', '${adv.advisor_id}')">
        <td><code>${adv.advisor_id}</code></td>
        <td style="font-weight:600; color:#fff;">${adv.full_name}</td>
        <td>${adv.role}</td>
        <td>${adv.office}</td>
      </tr>
    `).join('');
  } else if (currentEntity === 'interactions') {
    thead.innerHTML = `
      <tr>
        <th>Interaction ID</th>
        <th>Household ID</th>
        <th>Type</th>
        <th>Date</th>
        <th>Advisor ID</th>
        <th>Summary</th>
      </tr>
    `;
    tbody.innerHTML = items.map(i => `
      <tr onclick="openProvenanceDrawer('Interaction', '${i.interaction_id}')">
        <td><code>${i.interaction_id}</code></td>
        <td><code>${i.household_id}</code></td>
        <td><span class="badge badge-tag">${i.interaction_type}</span></td>
        <td>${i.interaction_date}</td>
        <td><code>${i.advisor_id || 'N/A'}</code></td>
        <td style="max-width:300px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">${i.summary || 'N/A'}</td>
      </tr>
    `).join('');
  }
}

function renderTriageList() {
  const container = document.getElementById('triageList');
  const items = clarificationsData.pending || [];

  if (items.length === 0) {
    container.innerHTML = `
      <div class="glassmorphism" style="padding:40px; text-align:center;">
        <h4 style="color:#34d399; margin-bottom:8px;">All Clarifications Resolved!</h4>
        <p style="color:#9ca3af; font-size:13px;">The client book has achieved 100% full canonical alignment with no outstanding flags.</p>
      </div>
    `;
    return;
  }

  container.innerHTML = items.map((c, idx) => {
    let catClass = 'cat-advisor';
    if (c.category === 'ORPHAN_ACCOUNT') catClass = 'cat-account';
    if (c.category === 'ORPHAN_INTERACTION') catClass = 'cat-interaction';

    // Build interactive action controls
    let actionControls = '';
    if (c.category === 'UNASSIGNED_ADVISOR') {
      actionControls = `
        <div style="display:flex; align-items:center; gap:12px;">
          <label style="font-size:12px; color:#9ca3af;">Assign Advisor:</label>
          <select id="advSelect_${c.id}" class="advisor-select">
            ${advisorsList.map(a => `<option value="${a.advisor_id}">${a.full_name} (${a.office})</option>`).join('')}
          </select>
          <button class="btn btn-primary" onclick="submitAdvisorAssignment('${c.id}')">Approve Assignment</button>
        </div>
      `;
    } else {
      actionControls = `
        <div style="display:flex; align-items:center; gap:12px;">
          <button class="btn btn-primary" onclick="submitDefaultResolution('${c.id}')">Approve Proposed Default</button>
        </div>
      `;
    }

    return `
      <div class="clarif-card glassmorphism">
        <div class="clarif-card-header">
          <span class="clarif-category-tag ${catClass}">${c.category.replace('_', ' ')}</span>
          <span style="font-size:12px; color:#9ca3af; font-family:var(--font-mono);">ID: ${c.id}</span>
        </div>
        <h4 class="clarif-title">${c.title}</h4>
        <div class="clarif-body">
          <div class="clarif-row">
            <span class="clarif-label">Trigger:</span>
            <span class="clarif-text">${c.trigger}</span>
          </div>
          <div class="clarif-row">
            <span class="clarif-label">Evidence:</span>
            <span class="clarif-text" style="color:#93c5fd;">${c.evidence}</span>
          </div>
          <div class="clarif-row">
            <span class="clarif-label">Proposed Default:</span>
            <span class="clarif-text" style="color:#34d399; font-weight:600;">${c.proposed_default}</span>
          </div>
        </div>
        <div class="clarif-action-bar">
          <span style="font-size:12px; color:#6b7280;">Confidence Score: <b>${c.confidence.toFixed(2)}</b> (Routing: Dana Ruiz)</span>
          ${actionControls}
        </div>
      </div>
    `;
  }).join('');
}

async function submitAdvisorAssignment(itemId) {
  const select = document.getElementById(`advSelect_${itemId}`);
  const advId = select ? select.value : 'ADV-001';
  try {
    const res = await fetch('/api/clarifications/resolve', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        item_id: itemId,
        selected_advisor_id: advId,
        notes: `Assigned advisor ${advId} via dashboard triage`
      })
    });
    const data = await res.json();
    showToast(`Clarification ${itemId} resolved!`);
    await initDashboard();
  } catch (err) {
    showToast('Failed to resolve clarification.');
  }
}

async function submitDefaultResolution(itemId) {
  try {
    const res = await fetch('/api/clarifications/resolve', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        item_id: itemId,
        notes: 'Approved proposed default via dashboard triage'
      })
    });
    const data = await res.json();
    showToast(`Approved default for ${itemId}!`);
    await initDashboard();
  } catch (err) {
    showToast('Failed to resolve clarification.');
  }
}

function renderRulesGrid(rules) {
  const container = document.getElementById('rulesGrid');
  container.innerHTML = rules.map(r => `
    <div class="rule-card glassmorphism">
      <div class="rule-header">
        <span class="rule-id">${r.rule_id}</span>
        <span class="rule-scope">${r.scope}</span>
      </div>
      <p class="rule-desc">${r.description}</p>
      <div class="rule-meta">
        <div><b>Stakeholder:</b> ${r.stakeholder}</div>
        <div><b>Source Citation:</b> <code>${r.source_reference}</code></div>
      </div>
    </div>
  `).join('');
}

function renderAuditReport(audit) {
  const list = document.getElementById('auditRulesList');
  list.innerHTML = (audit.rule_results || []).map(r => `
    <div class="audit-rule-item">
      <div class="audit-icon ${r.passed ? 'pass' : 'fail'}">${r.passed ? '✓' : '✗'}</div>
      <div>
        <div class="audit-rule-title">${r.rule_name}</div>
        <div class="audit-rule-detail">${r.details}</div>
      </div>
    </div>
  `).join('');
}

// ------------------------------------------------------------------------------
// Slide-Out Provenance Drawer
// ------------------------------------------------------------------------------
function openProvenanceDrawer(entityType, entityId) {
  const collectionKey = entityType.toLowerCase() + 's';
  const items = canonicalData[collectionKey] || [];
  
  // Find entity by PK
  const pkField = `${entityType.toLowerCase()}_id`;
  const entity = items.find(item => item[pkField] === entityId);
  if (!entity) return;

  document.getElementById('drawerTitle').textContent = `${entityType} Provenance Lineage`;
  document.getElementById('drawerSubtitle').textContent = `${pkField}: ${entityId}`;

  const body = document.getElementById('drawerBody');
  const provDict = entity._provenance || {};

  if (Object.keys(provDict).length === 0) {
    body.innerHTML = `<p style="color:#9ca3af;">No detailed field provenance recorded for this entity.</p>`;
  } else {
    body.innerHTML = Object.entries(provDict).map(([fieldName, prov]) => {
      const conf = prov.confidence || 1.0;
      let confClass = 'conf-high';
      if (conf < 0.85) confClass = 'conf-mid';
      if (conf < 0.50) confClass = 'conf-low';

      return `
        <div class="prov-field-card">
          <div class="prov-field-header">
            <span class="prov-field-name">${fieldName}</span>
            <span class="prov-confidence ${confClass}">Conf: ${conf.toFixed(2)}</span>
          </div>
          <div class="prov-field-body">
            <div><b>Source File:</b> <code>${prov.source_file.split('/').slice(-2).join('/')}</code> (${prov.source_location})</div>
            <div><b>Method / Agent:</b> <span style="color:#6366f1;">${prov.method}</span> (${prov.rule_or_agent})</div>
            <div><b>Raw Source Value:</b> <code style="color:#fcd34d;">${JSON.stringify(prov.source_raw_value)}</code></div>
            ${prov.reasoning ? `<div style="margin-top:4px; font-style:italic; color:#93c5fd;">"${prov.reasoning}"</div>` : ''}
          </div>
        </div>
      `;
    }).join('');
  }

  document.getElementById('provenanceBackdrop').classList.add('open');
  document.getElementById('provenanceDrawer').classList.add('open');
}

function closeProvenanceDrawer() {
  document.getElementById('provenanceBackdrop').classList.remove('open');
  document.getElementById('provenanceDrawer').classList.remove('open');
}

function copySlackMessage() {
  const text = document.getElementById('slackMarkdownContent').textContent;
  navigator.clipboard.writeText(text).then(() => {
    showToast('Slack message copied to clipboard!');
  }).catch(() => {
    showToast('Failed to copy to clipboard.');
  });
}

function showToast(message) {
  const toast = document.getElementById('toast');
  toast.textContent = message;
  toast.classList.add('show');
  setTimeout(() => {
    toast.classList.remove('show');
  }, 3000);
}
