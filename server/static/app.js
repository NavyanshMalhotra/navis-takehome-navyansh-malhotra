// ==============================================================================
// Nevis Canonical Data Platform — Tufte Analytical Client
// ==============================================================================

let currentTab = 'canonical';
let currentEntity = 'households';
let canonicalData = {};
let clarificationsData = { pending: [], resolved: [] };
let advisorsList = [];
let searchQuery = '';

document.addEventListener('DOMContentLoaded', () => {
  initPlatform();
});

async function initPlatform() {
  await Promise.all([
    fetchStatus(),
    fetchCanonicalData(),
    fetchClarifications(),
    fetchAuditReport(),
    fetchSlackMessage()
  ]);
}

// ------------------------------------------------------------------------------
// Navigation & Views
// ------------------------------------------------------------------------------
function switchTab(tabId) {
  currentTab = tabId;
  document.querySelectorAll('.view-tab').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.view-pane').forEach(p => p.classList.remove('active'));

  const clickedBtn = Array.from(document.querySelectorAll('.view-tab')).find(b =>
    b.getAttribute('onclick')?.includes(tabId)
  );
  if (clickedBtn) clickedBtn.classList.add('active');

  const pane = document.getElementById(`view-${tabId}`);
  if (pane) pane.classList.add('active');

  if (tabId === 'slack') {
    fetchSlackMessage();
  }
}

function filterEntityType(entityType) {
  currentEntity = entityType;
  document.querySelectorAll('.entity-btn').forEach(b => b.classList.remove('active'));
  const clickedBtn = Array.from(document.querySelectorAll('.entity-btn')).find(b =>
    b.getAttribute('onclick')?.includes(entityType)
  );
  if (clickedBtn) clickedBtn.classList.add('active');
  renderCanonicalTable();
}

function handleCanonicalSearch() {
  searchQuery = document.getElementById('canonicalSearch').value.toLowerCase().trim();
  renderCanonicalTable();
}

// ------------------------------------------------------------------------------
// API Fetchers
// ------------------------------------------------------------------------------
async function fetchStatus() {
  try {
    const res = await fetch('/api/pipeline/status');
    const data = await res.json();
    
    const fmtUsd = (val) => '$' + Number(val || 0).toLocaleString(undefined, {
      minimumFractionDigits: 0,
      maximumFractionDigits: 0
    });

    const activeAumEl = document.getElementById('kpiActiveAum');
    if (activeAumEl) activeAumEl.textContent = fmtUsd(data.active_aum_usd);

    const totalMvEl = document.getElementById('kpiTotalMv');
    if (totalMvEl) totalMvEl.textContent = fmtUsd(data.total_market_value_usd);

    const hhEl = document.getElementById('kpiHouseholds');
    if (hhEl) hhEl.textContent = data.total_households;

    const accEl = document.getElementById('kpiAccounts');
    if (accEl) accEl.textContent = data.total_accounts;

    const cliEl = document.getElementById('kpiClients');
    if (cliEl) cliEl.textContent = data.total_clients;

    const clarifEl = document.getElementById('kpiClarif');
    if (clarifEl) clarifEl.textContent = data.total_clarifications;

    const badgeEl = document.getElementById('triageBadge');
    if (badgeEl) badgeEl.textContent = data.total_clarifications;

    const mastheadEl = document.getElementById('mastheadStatus');
    if (mastheadEl) {
      mastheadEl.textContent = data.audit_passed ? '8/8 Invariant Rules Passed' : 'Audit Exception Detected';
    }
  } catch (err) {
    console.error('Failed to fetch system status:', err);
  }
}

async function fetchCanonicalData() {
  try {
    const res = await fetch('/api/canonical');
    canonicalData = await res.json();
    advisorsList = canonicalData.advisors || [];

    const setVal = (id, val) => {
      const el = document.getElementById(id);
      if (el) el.textContent = val;
    };

    setVal('countHh', (canonicalData.households || []).length);
    setVal('countCli', (canonicalData.clients || []).length);
    setVal('countAcc', (canonicalData.accounts || []).length);
    setVal('countAdv', (canonicalData.advisors || []).length);
    setVal('countInt', (canonicalData.interactions || []).length);

    renderCanonicalTable();
  } catch (err) {
    console.error('Failed to fetch canonical store:', err);
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
    const el = document.getElementById('slackMarkdownContent');
    if (el) el.textContent = text;
  } catch (err) {
    console.error('Failed to fetch Slack markdown:', err);
  }
}

async function triggerPipelineRun() {
  const btn = document.getElementById('runPipelineBtn');
  btn.disabled = true;
  btn.textContent = 'Executing Pipeline...';

  try {
    const res = await fetch('/api/pipeline/run', { method: 'POST' });
    const data = await res.json();
    showToast(data.message || 'Pipeline executed successfully.');
    await initPlatform();
  } catch (err) {
    showToast('Pipeline execution failed.');
  } finally {
    btn.disabled = false;
    btn.textContent = 'Execute Sync Pipeline';
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
    tbody.innerHTML = `<tr><td colspan="7" style="text-align:center; color:var(--text-muted); padding:32px;">No matching records found.</td></tr>`;
    return;
  }

  const fmtUsd = (val) => val !== null && val !== undefined
    ? '$' + Number(val).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
    : '<span style="color:var(--text-muted);">null</span>';

  if (currentEntity === 'households') {
    thead.innerHTML = `
      <tr>
        <th style="width: 140px;">Household ID</th>
        <th>Household Name</th>
        <th style="width: 120px;">Primary Advisor</th>
        <th style="width: 90px;">Status</th>
        <th class="num-col" style="width: 150px;">Market Value (USD)</th>
        <th class="num-col" style="width: 150px;">Active AUM (USD)</th>
        <th>Source Tags</th>
      </tr>
    `;
    tbody.innerHTML = items.map(h => `
      <tr onclick="openProvenanceDrawer('Household', '${h.household_id}')">
        <td><code>${h.household_id}</code></td>
        <td style="font-weight:600;">${h.household_name}</td>
        <td><code>${h.primary_advisor_id || 'unassigned'}</code></td>
        <td><span class="tag tag-${(h.status || 'active').toLowerCase()}">${h.status}</span></td>
        <td class="num-col">${fmtUsd(h.market_value_usd)}</td>
        <td class="num-col" style="font-weight:600; color:${h.is_active ? 'var(--text-primary)' : 'var(--ink-amber)'};">${fmtUsd(h.active_aum_usd)}</td>
        <td>${(h.source_tags || []).map(t => `<span class="tag tag-meta">${t}</span>`).join('')}</td>
      </tr>
    `).join('');
  } else if (currentEntity === 'clients') {
    thead.innerHTML = `
      <tr>
        <th style="width: 140px;">Client ID</th>
        <th>Full Legal Name</th>
        <th style="width: 140px;">Household ID</th>
        <th style="width: 100px;">Role</th>
        <th style="width: 100px;">Status</th>
        <th>Source Tags</th>
      </tr>
    `;
    tbody.innerHTML = items.map(c => `
      <tr onclick="openProvenanceDrawer('Client', '${c.client_id}')">
        <td><code>${c.client_id}</code></td>
        <td style="font-weight:600;">${c.first_name} ${c.last_name}</td>
        <td><code>${c.household_id}</code></td>
        <td><span class="tag tag-meta">${c.role}</span></td>
        <td><span class="tag tag-${(c.status || 'active').toLowerCase()}">${c.status}</span></td>
        <td>${(c.source_tags || []).map(t => `<span class="tag tag-meta">${t}</span>`).join('')}</td>
      </tr>
    `).join('');
  } else if (currentEntity === 'accounts') {
    thead.innerHTML = `
      <tr>
        <th style="width: 140px;">Account ID</th>
        <th>Account Title / Holder</th>
        <th style="width: 140px;">Household ID</th>
        <th style="width: 100px;">Type</th>
        <th class="num-col" style="width: 150px;">Market Value (USD)</th>
        <th style="width: 90px;">Currency</th>
        <th style="width: 120px;">Custodian</th>
      </tr>
    `;
    tbody.innerHTML = items.map(a => `
      <tr onclick="openProvenanceDrawer('Account', '${a.account_id}')">
        <td><code>${a.account_id}</code></td>
        <td style="font-weight:600;">${a.account_holder_raw}</td>
        <td><code>${a.household_id}</code></td>
        <td><span class="tag tag-meta">${a.account_type}</span></td>
        <td class="num-col" style="font-weight:600;">${fmtUsd(a.market_value_usd)}</td>
        <td><code>${a.currency_original}</code> ${a.currency_original !== 'USD' ? '<span class="tag tag-prospect">FX</span>' : ''}</td>
        <td>${a.custodian}</td>
      </tr>
    `).join('');
  } else if (currentEntity === 'advisors') {
    thead.innerHTML = `
      <tr>
        <th style="width: 140px;">Advisor ID</th>
        <th>Full Name</th>
        <th style="width: 180px;">Role</th>
        <th>Office Location</th>
      </tr>
    `;
    tbody.innerHTML = items.map(adv => `
      <tr onclick="openProvenanceDrawer('Advisor', '${adv.advisor_id}')">
        <td><code>${adv.advisor_id}</code></td>
        <td style="font-weight:600;">${adv.full_name}</td>
        <td>${adv.role}</td>
        <td>${adv.office}</td>
      </tr>
    `).join('');
  } else if (currentEntity === 'interactions') {
    thead.innerHTML = `
      <tr>
        <th style="width: 140px;">Interaction ID</th>
        <th style="width: 140px;">Household ID</th>
        <th style="width: 100px;">Date</th>
        <th style="width: 100px;">Type</th>
        <th style="width: 120px;">Advisor</th>
        <th>Summary / Context</th>
      </tr>
    `;
    tbody.innerHTML = items.map(i => `
      <tr onclick="openProvenanceDrawer('Interaction', '${i.interaction_id}')">
        <td><code>${i.interaction_id}</code></td>
        <td><code>${i.household_id}</code></td>
        <td>${i.interaction_date}</td>
        <td><span class="tag tag-meta">${i.interaction_type}</span></td>
        <td><code>${i.advisor_id || 'unassigned'}</code></td>
        <td>${i.summary || 'N/A'}</td>
      </tr>
    `).join('');
  }
}

function renderTriageList() {
  const container = document.getElementById('triageList');
  const items = clarificationsData.pending || [];

  if (items.length === 0) {
    container.innerHTML = `
      <div class="clarif-entry" style="text-align:center; padding:32px;">
        <h3 style="color:var(--ink-green); margin-bottom:6px;">Clarification Queue Clear</h3>
        <p style="color:var(--text-secondary); font-size:13px;">All 8 items have been reviewed and canonical invariants are 100% satisfied.</p>
      </div>
    `;
    return;
  }

  container.innerHTML = items.map((c) => {
    let chipClass = 'chip-advisor';
    if (c.category === 'ORPHAN_ACCOUNT') chipClass = 'chip-account';
    if (c.category === 'ORPHAN_INTERACTION') chipClass = 'chip-interaction';

    let actionControls = '';
    if (c.category === 'UNASSIGNED_ADVISOR') {
      actionControls = `
        <div class="clarif-controls">
          <select id="advSelect_${c.id}" class="select-control">
            ${advisorsList.map(a => `<option value="${a.advisor_id}">${a.full_name} (${a.office})</option>`).join('')}
          </select>
          <button class="btn btn-primary" onclick="submitAdvisorAssignment('${c.id}')">Assign Advisor</button>
        </div>
      `;
    } else {
      actionControls = `
        <div class="clarif-controls">
          <button class="btn btn-primary" onclick="submitDefaultResolution('${c.id}')">Confirm Proposed Default</button>
        </div>
      `;
    }

    const optionsText = Array.isArray(c.candidate_options)
      ? c.candidate_options.join(' | ')
      : (c.candidate_options || 'N/A');

    return `
      <div class="clarif-entry">
        <div class="clarif-topline">
          <div class="clarif-title-group">
            <span class="clarif-category-chip ${chipClass}">${c.category.replace(/_/g, ' ')}</span>
            <span class="clarif-title-text">${c.title}</span>
          </div>
          <span class="clarif-id-label">Item ID: ${c.id}</span>
        </div>

        <div class="schema-grid">
          <div class="schema-key">Trigger</div>
          <div class="schema-val">${c.trigger}</div>

          <div class="schema-key">Evidence</div>
          <div class="schema-val"><span class="schema-val evidence">${c.evidence}</span></div>

          <div class="schema-key">Candidate Options</div>
          <div class="schema-val">${optionsText}</div>

          <div class="schema-key">Proposed Default</div>
          <div class="schema-val default">${c.proposed_default}</div>
        </div>

        <div class="clarif-actions-strip">
          <span class="clarif-meta-note">Target: Dana Ruiz (Head of Operations) &bull; Confidence: <b>${c.confidence.toFixed(2)}</b></span>
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
        notes: `Assigned advisor ${advId} via Tufte HITL triage`
      })
    });
    const data = await res.json();
    showToast(`Assigned ${advId} to ${itemId}`);
    await initPlatform();
  } catch (err) {
    showToast('Failed to resolve advisor assignment.');
  }
}

async function submitDefaultResolution(itemId) {
  try {
    const res = await fetch('/api/clarifications/resolve', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        item_id: itemId,
        notes: 'Approved proposed default via Tufte HITL triage'
      })
    });
    const data = await res.json();
    showToast(`Approved default for ${itemId}`);
    await initPlatform();
  } catch (err) {
    showToast('Failed to confirm default.');
  }
}

function renderAuditReport(audit) {
  const tbody = document.getElementById('auditRulesList');
  if (!tbody) return;

  tbody.innerHTML = (audit.rule_results || []).map(r => `
    <tr>
      <td><span class="audit-pass-icon">${r.passed ? '✓' : '✗'}</span></td>
      <td><span class="audit-rule-code">${r.rule_id}</span></td>
      <td style="font-weight:600;">${r.rule_name}</td>
      <td style="color:var(--text-secondary);">${r.details}</td>
    </tr>
  `).join('');
}

// ------------------------------------------------------------------------------
// Provenance Drawer
// ------------------------------------------------------------------------------
function openProvenanceDrawer(entityType, entityId) {
  const collectionKey = entityType.toLowerCase() + 's';
  const items = canonicalData[collectionKey] || [];
  
  const pkField = `${entityType.toLowerCase()}_id`;
  const entity = items.find(item => item[pkField] === entityId);
  if (!entity) return;

  document.getElementById('drawerTitle').textContent = `${entityType} Provenance Lineage`;
  document.getElementById('drawerSubtitle').textContent = `${pkField}: ${entityId}`;

  const body = document.getElementById('drawerBody');
  const provDict = entity._provenance || {};

  if (Object.keys(provDict).length === 0) {
    body.innerHTML = `<p style="color:var(--text-muted);">No field-level provenance recorded for this record.</p>`;
  } else {
    body.innerHTML = Object.entries(provDict).map(([fieldName, prov]) => {
      const conf = prov.confidence || 1.0;
      return `
        <div class="citation-card">
          <div class="citation-head">
            <span class="citation-field">${fieldName}</span>
            <span class="citation-conf">Conf: ${conf.toFixed(2)}</span>
          </div>
          <div class="citation-details">
            <div><b>Source File:</b> <code>${prov.source_file}</code></div>
            <div><b>Source Location:</b> ${prov.source_location}</div>
            <div><b>Method / Agent:</b> ${prov.method} &bull; ${prov.rule_or_agent}</div>
            <div><b>Raw Value:</b> <code>${JSON.stringify(prov.source_raw_value)}</code></div>
            ${prov.reasoning ? `<div class="citation-evidence-quote">${prov.reasoning}</div>` : ''}
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
  const el = document.getElementById('slackMarkdownContent');
  if (!el) return;
  navigator.clipboard.writeText(el.textContent).then(() => {
    showToast('Slack message copied to clipboard');
  }).catch(() => {
    showToast('Clipboard copy failed');
  });
}

function showToast(message) {
  const toast = document.getElementById('toast');
  if (!toast) return;
  toast.textContent = message;
  toast.classList.add('show');
  setTimeout(() => {
    toast.classList.remove('show');
  }, 2500);
}
