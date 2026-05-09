/* ── ClinIQ App Logic ── */

const API_URL = "https://api.anthropic.com/v1/messages";
const MODEL   = "claude-sonnet-4-20250514";

// ──────────────────────────────────────────────
// Tab navigation
// ──────────────────────────────────────────────
document.querySelectorAll('.tab').forEach(tab => {
  tab.addEventListener('click', () => {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.module').forEach(m => m.classList.remove('active'));
    tab.classList.add('active');
    document.getElementById('module-' + tab.dataset.module).classList.add('active');
  });
});

// Dark mode toggle
document.getElementById('darkToggle').addEventListener('click', () => {
  document.body.classList.toggle('dark');
  document.body.classList.toggle('light');
});

// ──────────────────────────────────────────────
// Helpers
// ──────────────────────────────────────────────
function showLoader(text = 'Analysing notes…') {
  document.getElementById('loaderText').textContent = text;
  document.getElementById('loaderOverlay').classList.add('active');
}
function hideLoader() {
  document.getElementById('loaderOverlay').classList.remove('active');
}

async function callClaude(systemPrompt, userContent) {
  const response = await fetch(API_URL, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      model: MODEL,
      max_tokens: 1000,
      system: systemPrompt,
      messages: [{ role: 'user', content: userContent }]
    })
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.error?.message || `HTTP ${response.status}`);
  }
  const data = await response.json();
  return data.content?.[0]?.text || '';
}

function parseJSON(text) {
  const clean = text.replace(/```json\s*/g, '').replace(/```\s*/g, '').trim();
  return JSON.parse(clean);
}

function feedbackRow() {
  const div = document.createElement('div');
  div.className = 'feedback-row';
  div.innerHTML = `
    <span class="feedback-label">Was this helpful?</span>
    <button class="feedback-btn" data-v="up" title="Thumbs up">👍</button>
    <button class="feedback-btn" data-v="down" title="Thumbs down">👎</button>
  `;
  div.querySelectorAll('.feedback-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      div.querySelectorAll('.feedback-btn').forEach(b => b.classList.remove('active-up','active-down'));
      btn.classList.add(btn.dataset.v === 'up' ? 'active-up' : 'active-down');
    });
  });
  return div;
}

// ──────────────────────────────────────────────
// MODULE 1 — HANDOVER
// ──────────────────────────────────────────────
const HANDOVER_SYSTEM = `You are a clinical AI assistant. Parse raw shift handover notes and return structured JSON.
Return ONLY valid JSON with this exact shape (no markdown, no preamble):
{
  "patients": [
    {
      "name": "Patient name / identifier",
      "age": "age if available",
      "bed": "bed/room if mentioned",
      "urgency": "critical | high | stable",
      "summary": "One-sentence status summary",
      "events": "Key events from previous shift",
      "medications": "Active medications mentioned",
      "watchFor": "What to monitor / flag"
    }
  ]
}
Sort patients by urgency: critical first, then high, then stable.`;

document.getElementById('handoverSample').addEventListener('click', () => {
  document.getElementById('handoverInput').value =
    `Bed 4 - Mr Patel, 68M, admitted chest pain, trop rising x2, on heparin infusion. Cardiology aware. Bed 7 - Mrs Chen, 45F, post lap chole day 1, doing well, obs stable, for d/c tomorrow if tolerating diet. Bed 2 - John D, 72M, COPD exac, sats 88% on 2L, nebs Q4H, ABG done - resp acidosis, worsening overnight, may need NIV. Bed 11 - Sarah M, 31F, migraine, obs fine, for d/c once pain controlled.`;
});

document.getElementById('runHandover').addEventListener('click', async () => {
  const raw = document.getElementById('handoverInput').value.trim();
  if (!raw) return alert('Please enter handover notes.');
  showLoader('Parsing handover notes…');
  try {
    const text = await callClaude(HANDOVER_SYSTEM, raw);
    const data  = parseJSON(text);
    renderHandover(data.patients || []);
    document.getElementById('handoverTimestamp').textContent = '· Generated ' + new Date().toLocaleTimeString();
    document.getElementById('handoverActions').style.display = 'flex';
  } catch (e) {
    document.getElementById('handoverOutput').innerHTML = `<div class="empty-state" style="color:var(--danger)">Error: ${e.message}</div>`;
  } finally {
    hideLoader();
  }
});

function renderHandover(patients) {
  const out = document.getElementById('handoverOutput');
  if (!patients.length) { out.innerHTML = '<div class="empty-state">No patients found.</div>'; return; }

  out.innerHTML = '';
  patients.forEach((p, i) => {
    const card = document.createElement('div');
    card.className = 'patient-card';
    card.style.animationDelay = (i * 0.07) + 's';

    const urgencyMap = { critical: 'urgency-critical', high: 'urgency-high', stable: 'urgency-stable' };
    const urgencyClass = urgencyMap[p.urgency?.toLowerCase()] || 'urgency-stable';

    card.innerHTML = `
      <div class="card-header">
        <span class="patient-name">${p.name || 'Unknown'}${p.bed ? ' · ' + p.bed : ''}${p.age ? ' · ' + p.age : ''}</span>
        <span class="urgency-badge ${urgencyClass}">${p.urgency || 'stable'}</span>
      </div>
      <div class="card-body">
        <div><strong>Status:</strong> ${p.summary || '—'}</div>
        <div><strong>Events:</strong> ${p.events || '—'}</div>
        <div><strong>Medications:</strong> ${p.medications || '—'}</div>
        ${p.watchFor ? `<div class="watch-flag">⚑ Watch for: ${p.watchFor}</div>` : ''}
      </div>
      <div class="card-footer">
        <button class="mark-reviewed-btn">Mark Reviewed</button>
      </div>
    `;

    card.querySelector('.mark-reviewed-btn').addEventListener('click', function() {
      this.textContent = this.classList.contains('reviewed') ? 'Mark Reviewed' : '✓ Reviewed';
      this.classList.toggle('reviewed');
    });

    out.appendChild(card);
  });
  out.appendChild(feedbackRow());
}

document.getElementById('exportHandoverPdf').addEventListener('click', () => {
  window.print();
});

// ──────────────────────────────────────────────
// MODULE 2 — SOAP NOTE
// ──────────────────────────────────────────────
const SOAP_SYSTEM = `You are a clinical AI assistant. Convert raw consultation notes into a structured SOAP note and identify red flags.
Return ONLY valid JSON with this exact shape (no markdown, no preamble):
{
  "soap": {
    "subjective": "What the patient reported",
    "objective": "Vitals and clinical findings",
    "assessment": "Clinical impression",
    "plan": "Next steps and prescriptions"
  },
  "redFlags": [
    {
      "title": "Short flag title",
      "detail": "Why this is a concern and what to do",
      "severity": "critical | warning | watch"
    }
  ]
}
Be concise and clinically precise. Return an empty array for redFlags if none exist.`;

document.getElementById('soapSample').addEventListener('click', () => {
  document.getElementById('soapInput').value =
    `58F c/o chest tightness x2d, worse on exertion, some SOB, no fever. Ex-smoker 20py. HTN on amlodipine. HR 92 irregular, BP 148/90, sats 96%, temp 36.8. ECG shows irregularly irregular rhythm, no ST changes. Likely new AF. Trop pending. Plan: admit, rate control with bisoprolol 2.5mg, anticoagulate with apixaban after ruling out clot, echo, cardiology review.`;
});

document.getElementById('runSoap').addEventListener('click', async () => {
  const raw = document.getElementById('soapInput').value.trim();
  if (!raw) return alert('Please enter consultation notes.');
  showLoader('Structuring consultation note…');
  try {
    const text = await callClaude(SOAP_SYSTEM, raw);
    const data  = parseJSON(text);
    renderSoap(data);
    document.getElementById('soapActions').style.display = 'flex';
  } catch (e) {
    document.getElementById('soapOutput').innerHTML = `<div class="empty-state" style="color:var(--danger)">Error: ${e.message}</div>`;
  } finally {
    hideLoader();
  }
});

function renderSoap(data) {
  const out = document.getElementById('soapOutput');
  out.innerHTML = '';

  const soap = data.soap || {};
  const soapDiv = document.createElement('div');
  soapDiv.className = 'soap-note';

  ['subjective','objective','assessment','plan'].forEach(key => {
    if (!soap[key]) return;
    const labels = { subjective:'Subjective', objective:'Objective', assessment:'Assessment', plan:'Plan' };
    const sec = document.createElement('div');
    sec.className = 'soap-section';
    sec.innerHTML = `<div class="soap-label">${labels[key]}</div><div class="soap-content">${soap[key]}</div>`;
    soapDiv.appendChild(sec);
  });
  out.appendChild(soapDiv);

  const flags = data.redFlags || [];
  if (flags.length) {
    const hdr = document.createElement('div');
    hdr.className = 'red-flags-header';
    hdr.textContent = `⚠ Red Flags (${flags.length})`;
    out.appendChild(hdr);

    const sevMap = { critical: { cls: '', icon: '🔴', sev: 'sev-critical' },
                     warning:  { cls: 'warn', icon: '🟡', sev: 'sev-warning' },
                     watch:    { cls: 'watch', icon: '🔵', sev: 'sev-watch' } };

    flags.forEach(f => {
      const m = sevMap[f.severity?.toLowerCase()] || sevMap.watch;
      const div = document.createElement('div');
      div.className = `red-flag ${m.cls}`;
      div.innerHTML = `
        <span class="flag-icon">${m.icon}</span>
        <div class="flag-content">
          <div class="flag-title">${f.title}</div>
          <div class="flag-detail">${f.detail}</div>
        </div>
        <span class="flag-severity ${m.sev}">${f.severity}</span>
      `;
      out.appendChild(div);
    });
  }

  out.appendChild(feedbackRow());
}

document.getElementById('copySoap').addEventListener('click', () => {
  const text = document.getElementById('soapOutput').innerText;
  navigator.clipboard.writeText(text).then(() => {
    const btn = document.getElementById('copySoap');
    btn.textContent = '✓ Copied!';
    setTimeout(() => btn.textContent = '⧉ Copy Note', 1800);
  });
});

// ──────────────────────────────────────────────
// MODULE 3 — DIFFERENTIAL Dx
// ──────────────────────────────────────────────
const DDX_SYSTEM = `You are a clinical AI assistant. Generate a ranked differential diagnosis.
Return ONLY valid JSON with this exact shape (no markdown, no preamble):
{
  "differentials": [
    {
      "rank": 1,
      "name": "Diagnosis name",
      "confidence": 85,
      "reasoning": "Plain-language explanation of why this fits",
      "confirmTests": ["Test 1", "Test 2"],
      "ruleOutTests": ["Test A", "Test B"],
      "redFlag": "Any red flag specific to this diagnosis, or empty string"
    }
  ]
}
Return 5-8 diagnoses ranked by likelihood. Confidence is a number 0-100.`;

document.getElementById('ddxSample').addEventListener('click', () => {
  document.getElementById('ddxAge').value = '58';
  document.getElementById('ddxGender').value = 'Male';
  document.getElementById('ddxSymptoms').value = 'chest pain, diaphoresis, dyspnoea';
  document.getElementById('ddxDuration').value = '2 hours, sudden onset';
  document.getElementById('ddxHistory').value = 'HTN, ex-smoker 30py, troponin mildly elevated, ECG: ST depression V4-V6, BP 150/95, HR 104';
});

document.getElementById('runDdx').addEventListener('click', async () => {
  const age      = document.getElementById('ddxAge').value.trim();
  const gender   = document.getElementById('ddxGender').value;
  const symptoms = document.getElementById('ddxSymptoms').value.trim();
  const duration = document.getElementById('ddxDuration').value.trim();
  const history  = document.getElementById('ddxHistory').value.trim();

  if (!symptoms) return alert('Please enter at least the presenting symptoms.');

  const userMsg = `Patient: ${age ? age + 'yo' : 'age unknown'} ${gender || ''}
Symptoms: ${symptoms}
Duration: ${duration || 'not specified'}
History / Results: ${history || 'none provided'}`;

  showLoader('Generating differential…');
  try {
    const text = await callClaude(DDX_SYSTEM, userMsg);
    const data  = parseJSON(text);
    renderDdx(data.differentials || []);
  } catch (e) {
    document.getElementById('ddxOutput').innerHTML = `<div class="empty-state" style="color:var(--danger)">Error: ${e.message}</div>`;
  } finally {
    hideLoader();
  }
});

function renderDdx(diffs) {
  const out = document.getElementById('ddxOutput');
  if (!diffs.length) { out.innerHTML = '<div class="empty-state">No differentials generated.</div>'; return; }
  out.innerHTML = '';

  diffs.forEach((d, i) => {
    const conf = Math.min(100, Math.max(0, d.confidence || 0));
    const fillClass = conf >= 70 ? 'high' : conf >= 40 ? 'medium' : 'low';

    const item = document.createElement('div');
    item.className = 'ddx-item';
    item.style.animationDelay = (i * 0.08) + 's';

    item.innerHTML = `
      <div class="ddx-header">
        <span class="ddx-rank">#${d.rank || i+1}</span>
        <span class="ddx-name">${d.name || 'Unknown'}</span>
        <div class="confidence-bar-wrap">
          <span class="confidence-pct">${conf}%</span>
          <div class="confidence-bar-bg">
            <div class="confidence-bar-fill ${fillClass}" style="width:${conf}%"></div>
          </div>
        </div>
      </div>
      <div class="ddx-body">
        <div>${d.reasoning || ''}</div>
        ${d.redFlag ? `<div class="watch-flag" style="margin-top:8px">⚑ ${d.redFlag}</div>` : ''}
        <div class="ddx-tests">
          ${(d.confirmTests || []).map(t => `<span class="test-chip confirm">✓ ${t}</span>`).join('')}
          ${(d.ruleOutTests || []).map(t => `<span class="test-chip rule-out">✕ ${t}</span>`).join('')}
        </div>
      </div>
    `;

    out.appendChild(item);
  });

  out.appendChild(feedbackRow());
}
