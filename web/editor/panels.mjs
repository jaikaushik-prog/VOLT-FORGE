import {escapeHTML as h, number as n} from './state.mjs';
import {componentLabel, limitLabel} from './workspace.mjs';

// Pure HTML builders for the v1 results and investigation panels. They only format text and numbers that the
// Python backend produced. The page CSP forbids inline styles and inline handlers, so the markup carries class
// names and data-* attributes only, and every interpolated string passes through h() (numbers through n()).

const CELLS = ['cell_1', 'cell_2', 'cell_3', 'cell_4'];
const REQUIREMENTS = [
  ['peak_branch_current_A', 'Peak branch current', 'A'],
  ['current_imbalance_pct', 'Current imbalance', '%'],
  ['peak_cell_temperature_C', 'Peak cell temperature', '°C'],
];
const REQUIREMENT_KEYS = REQUIREMENTS.map(([key]) => key);
// A Map, not an object, so a status such as "constructor" can never select an inherited property.
const STATUS_CLASS = new Map([
  ['simulated violation of configured limit', 'violation'],
  ['no sampled exceedance; insufficient evidence for a pass', 'clear'],
  ['insufficient simulation', 'partial'],
  ['not evaluable', 'na'],
  ['requirement not configured', 'unset'],
]);
const TOP = 10;

const statusBadge = (status, compact=false) => `<span class="status s-${STATUS_CLASS.get(status) ?? 'unknown'}"${compact?` title="${h(status ?? '')}"`:''}>${h(compact?limitLabel(status):status ?? '—')}</span>`;
const table = (head, rows) => `<div class="table-wrap"><table><thead><tr>${head.map(label => `<th>${h(label)}</th>`).join('')}</tr></thead><tbody>${rows.join('')}</tbody></table></div>`;
const openButton = caseId => `<button class="small open-case" data-case="${h(caseId)}">Open as variant</button>`;
// Known keys first, in their fixed order; any other key follows so that nothing the backend reports is dropped.
const keysInOrder = (object, preferred) => {
  const keys = object && typeof object === 'object' ? Object.keys(object) : [];
  return [...preferred.filter(key => keys.includes(key)), ...keys.filter(key => !preferred.includes(key))];
};
// Backend rankings arrive either as a bare list or as {cases: [...]}; read both.
const casesOf = entry => {
  const list = Array.isArray(entry) ? entry : entry?.cases;
  return (Array.isArray(list) ? list : []).filter(row => row && row.case_id != null);
};

export function rangeOf(seriesByComponent, key) {
  let lo = Infinity, hi = -Infinity;
  for (const id of CELLS) {
    const rows = seriesByComponent?.[id]?.rows;
    if (!Array.isArray(rows)) continue;
    for (const row of rows) {
      const value = row?.[key];
      if (Number.isFinite(value)) { lo = Math.min(lo, value); hi = Math.max(hi, value); }
    }
  }
  if (lo > hi) return [0, 1];
  return lo === hi ? [lo - 0.5, hi + 0.5] : [lo, hi];
}

export function thermalMetricsHTML(summary) {
  const thermal = summary?.thermal;
  if (!thermal || thermal.status !== 'completed') {
    const error = thermal?.error;
    const reason = thermal?.reason || (typeof error === 'string' ? error : error?.message) || 'Electrical-only run';
    return `<div class="metric unavailable"><span>Thermal output</span><strong>Unavailable</strong><small>${h(reason)}</small></div>`;
  }
  const card = (label, value, digits, unit) => `<div class="metric"><span>${h(label)}</span><strong>${n(value, digits)}</strong><small>${h(unit)}</small></div>`;
  const peakUnit = ['°C', thermal.peak_cell, 'simulated'].filter(Boolean).join(' · ');
  return card('Peak cell temperature', thermal.peak_cell_temperature_C, 2, peakUnit)
    + card('Max temperature spread', thermal.maximum_spread_K, 2, 'K')
    + card('Current imbalance', summary.engineering?.metrics?.current_imbalance_pct?.value, 1, '%');
}

export function requirementsHTML(engineering) {
  if (!engineering) return '';
  const requirements = engineering.requirements && typeof engineering.requirements === 'object' ? engineering.requirements : {};
  const rows = keysInOrder(requirements, REQUIREMENT_KEYS).map(key => {
    const r = requirements[key] || {};
    const [, label, unit] = REQUIREMENTS.find(([known]) => known === key) || [key, key, ''];
    const crossing = Number.isFinite(r.first_crossing_time_s) ? `${n(r.first_crossing_time_s, 1)} s` : '—';
    // Source is the documented source; when none exists the backend's reason explains why the row has no limit.
    const source = r.documented_source || r.reason;
    return `<tr><td>${h(unit ? `${label} (${unit})` : label)}</td><td>${statusBadge(r.status)}</td><td>${n(r.value, 3)}</td><td>${n(r.limit, 3)}</td><td>${n(r.margin, 3)}</td><td>${crossing}</td><td>${source ? h(source) : '—'}</td></tr>`;
  });
  return '<div class="requirements"><h3>Engineering screen (simulated)</h3>'
    + table(['Limit', 'Status', 'Value', 'Limit value', 'Margin', 'First crossing', 'Source'], rows)
    + '<p class="evidence-note">Simulated screen at saved solver samples. Not experimental acceptance or a safety rating. Unset limits are never passes.</p></div>';
}

export function investigationFormHTML(design) {
  const railName = cid => {
    const m = /^rail_([pn])_(\d+)$/.exec(cid);
    return m ? `${m[1] === 'p' ? 'Positive' : 'Negative'} connection ${m[2]}` : cid;
  };
  const boxes = Object.keys(design?.connections || {})
    .map(cid => `<label class="inv-check"><input type="checkbox" id="inv-seg-${h(cid)}" value="${h(cid)}"> ${h(railName(cid))}</label>`).join('');
  const text = (label, id, value) => `<label>${h(label)}<input id="${id}" name="${id}" type="text" value="${h(value)}" autocomplete="off"></label>`;
  const configured = Object.values(design?.engineering_requirements || {}).filter(r=>r&&typeof r==='object'&&Number.isFinite(r.limit)&&typeof r.documented_source==='string'&&r.documented_source.trim()).length;
  return '<div class="investigation-form">'
    + `<div class="inv-config-note">${configured?`${configured} engineering limit${configured===1?'':'s'} configured.`:'No engineering limits set. You can explore scenarios, but detecting a violation requires a limit.'} <button id="configure-inv-limits" class="text-button" type="button">Edit limits</button></div>`
    + `<fieldset class="inv-segments"><legend>Connections to test</legend>${boxes}</fieldset>`
    + '<div>'+text('Added contact resistance (mΩ)', 'inv-added', '1, 3')+'<p class="field-hint">Separate values with commas. Each value is added to one selected connection; the unchanged design is included too.</p></div>'
    + '<details class="inv-advanced"><summary>Load, ambient temperature & search budget</summary><div class="inv-inputs">'
    + '<div>'+text('Load currents (A)', 'inv-loads', '')+'<p class="field-hint">Blank keeps the design’s load.</p></div>'
    + '<div>'+text('Ambient temperatures (°C)', 'inv-ambient', '')+'<p class="field-hint">Blank keeps the design. Each ambient test also starts all cells at that temperature.</p></div>'
    + '<label>Maximum cases<input id="inv-max" name="inv-max" type="number" value="60" min="1" max="200" step="1" autocomplete="off"></label></div></details>'
    + '<div class="form-actions"><button type="button" id="inv-run" class="primary">Run investigation</button><span id="inv-preview" class="inv-description" aria-live="polite">Select connections to define the test set.</span></div>'
    + '<p class="evidence-note">Uses the same electrical and thermal model as a normal run. Findings apply only to the evaluated cases.</p></div>';
}

const NUMBER_LIST_ERROR = 'Enter finite numbers separated by commas.';
function numberList(text) {
  return String(text ?? '').split(/[\s,]+/).filter(Boolean).map(token => {
    const value = Number(token);
    if (!Number.isFinite(value)) throw new Error(NUMBER_LIST_ERROR);
    return value;
  });
}

export function parsePlan(values) {
  const {segments, added, loads, ambient, max} = values || {};
  const addedOhm = numberList(added).map(milliohm => milliohm / 1000);
  const loadA = numberList(loads);
  const ambientC = numberList(ambient);
  if (addedOhm.some(ohm => !(ohm > 0))) throw new Error('Added resistance must be positive.');
  if (loadA.some(amp => !(amp > 0))) throw new Error('Load currents must be positive.');
  const railSegments = Array.isArray(segments) ? segments.map(String) : [];
  if (addedOhm.length && !railSegments.length) throw new Error('Select at least one rail segment.');
  const budget = Number(max);
  if (!Number.isInteger(budget) || budget < 1 || budget > 200) throw new Error('Case budget must be 1-200.');
  return {rail_segments: railSegments, added_resistance_ohm: addedOhm, load_current_A: loadA, ambient_C: ambientC, max_cases: budget};
}

// What a case changed relative to the design: rail contact, load, ambient. Null and zero parts are left out,
// except an ambient of exactly 0 degC, which is a real temperature and is shown.
function changeSummary(c) {
  if (!c) return '—';
  const parts = [];
  if (c.rail_segment && Number.isFinite(c.added_resistance_ohm) && c.added_resistance_ohm > 0) parts.push(`${componentLabel(c.rail_segment)} +${n(c.added_resistance_ohm * 1000, 2)} mΩ`);
  if (Number.isFinite(c.load_current_A) && c.load_current_A !== 0) parts.push(`${n(c.load_current_A, 2)} A`);
  if (Number.isFinite(c.ambient_C)) parts.push(`${n(c.ambient_C, 1)} °C`);
  return parts.length ? parts.join(' · ') : 'baseline contacts';
}
const metricOf = (c, name) => {
  const metric = c?.metrics?.[name];
  return metric && typeof metric === 'object' ? metric.value : metric;
};

export function investigationHTML(record) {
  if (!record || typeof record !== 'object') return '';
  const cov = record.coverage || {};
  const byId = new Map((Array.isArray(record.cases) ? record.cases : []).filter(c => c && c.case_id != null).map(c => [c.case_id, c]));
  const rankings = record.rankings || {};
  const truncation = total => total > TOP ? `<p class="evidence-note">Showing the first ${TOP} of ${total} ranked cases.</p>` : '';

  const head = `<p class="investigation-head"><strong>${h(record.investigation_id ?? '—')}</strong> · Evaluated ${n(cov.evaluated, 0)} of ${n(cov.requested, 0)}`
    + ` · ${n(cov.skipped_by_budget, 0)} skipped by budget · ${n(cov.electrical_stopped, 0)} stopped by solver · ${n(cov.errors, 0)} electrical errors · ${n(cov.thermal_failures, 0)} thermal failures</p>`;
  const thermalErrors = [...byId.values()].filter(c => c.thermal_status === 'failed');
  const thermalNotes = thermalErrors.length ? `<div class="evidence-note"><strong>Thermal output unavailable for ${thermalErrors.length} case(s); electrical results are retained.</strong>${thermalErrors.map(c => `<p>${h(c.case_id)}: ${h(c.thermal_error?.message || 'Thermal calculation failed')}</p>`).join('')}</div>` : '';

  const requirementTables = keysInOrder(rankings.by_requirement, REQUIREMENT_KEYS).map(name => {
    const entry = rankings.by_requirement[name];
    const ranked = casesOf(entry);
    if (!ranked.length) return '';
    const label = (REQUIREMENTS.find(([key]) => key === name) || [name, name])[1];
    const violations = !Array.isArray(entry) && Number.isFinite(entry?.violations)
      ? `<p class="muted">Simulated violations among evaluated cases: ${n(entry.violations, 0)}</p>` : '';
    const rows = ranked.slice(0, TOP).map(row => `<tr><td>${h(row.case_id)}</td><td>${h(changeSummary(byId.get(row.case_id)))}</td>`
      + `<td>${n(row.margin, 3)}</td><td>${statusBadge(row.status,true)}</td><td>${openButton(row.case_id)}</td></tr>`);
    return `<h3>${h(label)}</h3>${violations}${table(['Case', 'Change', 'Margin', 'Status', 'Action'], rows)}${truncation(ranked.length)}`;
  }).join('');

  const metric = rankings.by_metric?.peak_branch_current_A;
  const explored = casesOf(metric);
  let exploration = '';
  if (explored.length) {
    const label = !Array.isArray(metric) && typeof metric?.label === 'string' ? `<p class="evidence-note">${h(metric.label)}</p>` : '';
    const rows = explored.slice(0, TOP).map(row => {
      const c = byId.get(row.case_id);
      return `<tr><td>${h(row.case_id)}</td><td>${h(changeSummary(c))}</td><td>${n(row.value, 3)}</td>`
        + `<td>${n(metricOf(c, 'peak_cell_temperature_C'), 2)}</td><td>${n(metricOf(c, 'current_imbalance_pct'), 1)}</td><td>${openButton(row.case_id)}</td></tr>`;
    });
    exploration = `<details${requirementTables?'':' open'}><summary>All cases by peak branch current</summary><h3>Exploration by peak branch current</h3>${label}`
      + table(['Case', 'Change', 'Peak current (A)', 'Peak temperature (°C)', 'Imbalance (%)', 'Action'], rows) + truncation(explored.length)+'</details>';
  }

  return `<div class="investigation">${head}${thermalNotes}${requirementTables}${exploration}`
    + '<p class="evidence-note">Worst case only within this finite set. Opening a case creates a variant you can run, compare and export; no repair benefit is claimed.</p></div>';
}
