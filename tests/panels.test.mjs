import {test} from 'node:test';
import assert from 'node:assert/strict';
import {rangeOf, thermalMetricsHTML, requirementsHTML, investigationFormHTML, parsePlan, investigationHTML} from '../web/editor/panels.mjs';

const VIOLATION = 'simulated violation of configured limit';
const CLEAR = 'no sampled exceedance; insufficient evidence for a pass';
const PARTIAL = 'insufficient simulation';
const NOT_EVALUABLE = 'not evaluable';
const UNSET = 'requirement not configured';
const LABEL = 'exploration order by metric value; not a requirement verdict';
const NOTE = 'Worst case only within this finite set. Opening a case creates a variant you can run, compare and export; no repair benefit is claimed.';
const OPEN = 'Open as variant';

const count = (text, needle) => text.split(needle).length - 1;
const strip = html => html.replace(/<[^>]*>/g, '');
// Cell texts of every <tr> (header row first); tags stripped, entities left as emitted.
const rowsOf = html => [...html.matchAll(/<tr>(.*?)<\/tr>/g)].map(([, row]) => [...row.matchAll(/<t[dh][^>]*>(.*?)<\/t[dh]>/g)].map(([, cell]) => strip(cell)));
// {heading text: html from the heading onward} for every <h3>.
const sectionsOf = html => Object.fromEntries(html.split('<h3>').slice(1).map(part => [part.slice(0, part.indexOf('</h3>')), part]));
// Names of all attributes on all tags, after removing quoted attribute values.
const attributeNames = html => (html.match(/<[a-zA-Z][^>]*>/g) || []).flatMap(tag => [...tag.replace(/="[^"]*"/g, '=""').matchAll(/\s([^\s=\/>]+)=/g)].map(m => m[1].toLowerCase()));

const DESIGN = {connections: Object.fromEntries(['rail_p_1', 'rail_p_2', 'rail_p_3', 'rail_n_1', 'rail_n_2', 'rail_n_3'].map(id => [id, {resistance: {value: 0.001}}]))};

// Shaped like the backend record: by_requirement is a bare list for one name and {cases, violations} for the
// others; by_metric is {label, cases}.
const RECORD = {
  schema_version: 1,
  investigation_id: 'inv_0007',
  coverage: {requested: 3, evaluated: 3, skipped_by_budget: 0, electrical_stopped: 0, errors: 0, thermal_failures: 0},
  cases: [
    {case_id: 'case_0001', load_current_A: null, ambient_C: null, rail_segment: null, added_resistance_ohm: 0, electrical_status: 'completed',
      metrics: {peak_branch_current_A: 10.5, current_imbalance_pct: 4.2, peak_cell_temperature_C: 31.25}},
    {case_id: 'case_0002', load_current_A: 12, ambient_C: 25, rail_segment: 'rail_p_1', added_resistance_ohm: 0.003, electrical_status: 'completed',
      metrics: {peak_branch_current_A: 13.75, current_imbalance_pct: 18.5, peak_cell_temperature_C: 36.5}},
    {case_id: 'case_0003', load_current_A: null, ambient_C: 0, rail_segment: 'rail_n_2', added_resistance_ohm: 0.001, electrical_status: 'completed',
      metrics: {peak_branch_current_A: 11.25, current_imbalance_pct: null, peak_cell_temperature_C: null}},
  ],
  rankings: {
    by_requirement: {
      peak_branch_current_A: [
        {case_id: 'case_0002', margin: -1.75, status: VIOLATION},
        {case_id: 'case_0003', margin: 0.75, status: CLEAR},
        {case_id: 'case_0001', margin: 1.5, status: CLEAR},
      ],
      current_imbalance_pct: {cases: [
        {case_id: 'case_0002', margin: -8.5, status: VIOLATION},
        {case_id: 'case_0001', margin: 5.8, status: CLEAR},
      ], violations: 1},
      peak_cell_temperature_C: {cases: [], violations: 0},
    },
    by_metric: {
      peak_branch_current_A: {label: LABEL, cases: [{case_id: 'case_0002', value: 13.75}, {case_id: 'case_0003', value: 11.25}, {case_id: 'case_0001', value: 10.5}]},
      current_imbalance_pct: {label: LABEL, cases: [{case_id: 'case_0002', value: 18.5}]},
    },
  },
};
const withMetric = metric => ({...RECORD, rankings: {...RECORD.rankings, by_metric: {peak_branch_current_A: metric}}});

test('investigation exposes thermal failures without concealing electrical results', () => {
  const record = structuredClone(RECORD);
  record.coverage.thermal_failures = 1;
  record.cases[1].thermal_status = 'failed';
  record.cases[1].thermal_error = {message: '<unsafe> thermal failure'};
  record.cases[1].metrics.peak_cell_temperature_C = null;
  const html = investigationHTML(record);
  assert.ok(html.includes('1 thermal failures'));
  assert.ok(html.includes('electrical results are retained'));
  assert.ok(html.includes('&lt;unsafe&gt; thermal failure') && !html.includes('<unsafe>'));
  assert.ok(html.includes('13.750'));
});

// Twelve ranked cases, to exercise the top-10 cut.
const IDS = Array.from({length: 12}, (_, i) => `case_${String(i + 1).padStart(4, '0')}`);
const MANY = {
  investigation_id: 'inv_0008',
  coverage: {requested: 12, evaluated: 12, skipped_by_budget: 0, electrical_stopped: 0, errors: 0, thermal_failures: 0},
  cases: IDS.map((case_id, i) => ({case_id, rail_segment: 'rail_p_1', added_resistance_ohm: 0.001 * (i + 1), load_current_A: null, ambient_C: null,
    metrics: {peak_branch_current_A: 20 - i, current_imbalance_pct: 1, peak_cell_temperature_C: 30}})),
  rankings: {
    by_requirement: {peak_branch_current_A: {cases: IDS.map((case_id, i) => ({case_id, margin: i - 5, status: i < 5 ? VIOLATION : CLEAR})), violations: 5}},
    by_metric: {peak_branch_current_A: {label: LABEL, cases: IDS.map((case_id, i) => ({case_id, value: 20 - i}))}},
  },
};

test('rangeOf collects finite values from cell_1..cell_4 only', () => {
  const series = {
    cell_1: {rows: [{temperature_C: 25}, {temperature_C: NaN}, {temperature_C: null}, {}]},
    cell_2: {rows: [{temperature_C: 31.5}, {temperature_C: 24.25}, {temperature_C: Infinity}, {temperature_C: '99'}]},
    cell_3: {rows: []},
    cell_4: {rows: [{temperature_C: 27}]},
    module: {rows: [{temperature_C: 500}]},     // not a cell: ignored
    cell_5: {rows: [{temperature_C: -500}]},    // not one of cell_1..cell_4: ignored
  };
  assert.deepEqual(rangeOf(series, 'temperature_C'), [24.25, 31.5]);
  assert.deepEqual(rangeOf({cell_1: {rows: [{x: -3}, {x: -1}]}}, 'x'), [-3, -1]);
  // Nothing finite anywhere gives the default [0, 1].
  assert.deepEqual(rangeOf({}, 'temperature_C'), [0, 1]);
  assert.deepEqual(rangeOf(undefined, 'temperature_C'), [0, 1]);
  assert.deepEqual(rangeOf({cell_1: {rows: [{temperature_C: NaN}, {temperature_C: null}]}, cell_2: {}}, 'temperature_C'), [0, 1]);
  assert.deepEqual(rangeOf(series, 'absent_key'), [0, 1]);
  // A constant series is widened by half a unit each side.
  assert.deepEqual(rangeOf({cell_1: {rows: [{x: 5}, {x: 5}]}, cell_3: {rows: [{x: 5}]}}, 'x'), [4.5, 5.5]);
});

test('thermalMetricsHTML shows an unavailable card with its reason, or three simulated metric cards', () => {
  const unavailable = reason => `<div class="metric unavailable"><span>Thermal output</span><strong>Unavailable</strong><small>${reason}</small></div>`;
  assert.equal(thermalMetricsHTML({thermal: {status: 'unavailable', reason: 'Electrical-only v1 design'}}), unavailable('Electrical-only v1 design'));
  assert.equal(thermalMetricsHTML({}), unavailable('Electrical-only run'));
  assert.equal(thermalMetricsHTML(undefined), unavailable('Electrical-only run'));
  assert.equal(thermalMetricsHTML({thermal: {status: 'failed', error: {type: 'ValueError', message: 'Thermal and electrical samples differ'}}}), unavailable('Thermal and electrical samples differ'));
  assert.equal(thermalMetricsHTML({thermal: {status: 'failed', error: {message: 'bad <b>input</b>'}}}), unavailable('bad &lt;b&gt;input&lt;/b&gt;'));
  // A thermal block that is not "completed" never shows numbers, even if it carries some.
  assert.equal(thermalMetricsHTML({thermal: {status: 'failed', peak_cell_temperature_C: 99}}), unavailable('Electrical-only run'));

  const summary = {
    thermal: {status: 'completed', peak_cell_temperature_C: 27.4499, peak_cell: 'cell_3', maximum_spread_K: 3.14159},
    engineering: {metrics: {current_imbalance_pct: {value: 12.34, unit: '%'}}},
  };
  assert.equal(thermalMetricsHTML(summary),
    '<div class="metric"><span>Peak cell temperature</span><strong>27.45</strong><small>°C · cell_3 · simulated</small></div>'
    + '<div class="metric"><span>Max temperature spread</span><strong>3.14</strong><small>K</small></div>'
    + '<div class="metric"><span>Current imbalance</span><strong>12.3</strong><small>%</small></div>');
  // A missing imbalance prints an em dash, still with its % unit.
  const noImbalance = thermalMetricsHTML({thermal: summary.thermal, engineering: {metrics: {current_imbalance_pct: {value: null}}}});
  assert.ok(noImbalance.includes('<span>Current imbalance</span><strong>—</strong><small>%</small>'));
  assert.ok(thermalMetricsHTML({thermal: summary.thermal}).includes('<strong>—</strong><small>%</small>'));
  assert.equal(count(thermalMetricsHTML(summary), 'class="metric"'), 3);
});

test('requirementsHTML maps every status to its class, keeps the fixed row order, and escapes the source', () => {
  const engineering = {
    requirements: {
      peak_cell_temperature_C: {status: UNSET, reason: 'An upper limit and a documented source are both required'},
      peak_branch_current_A: {status: VIOLATION, value: 14.2, limit: 12, unit: 'A', margin: -2.2, first_crossing_time_s: 31.2, documented_source: 'Datasheet <b>rev 2</b>'},
      current_imbalance_pct: {status: CLEAR, value: 8.123456, limit: 10, unit: '%', margin: 1.876544, first_crossing_time_s: null, documented_source: 'Spec A'},
    },
  };
  const html = requirementsHTML(engineering);
  assert.ok(html.startsWith('<div class="requirements"><h3>Engineering screen (simulated)</h3>'));
  assert.deepEqual(rowsOf(html), [
    ['Limit', 'Status', 'Value', 'Limit value', 'Margin', 'First crossing', 'Source'],
    ['Peak branch current (A)', VIOLATION, '14.200', '12.000', '-2.200', '31.2 s', 'Datasheet &lt;b&gt;rev 2&lt;/b&gt;'],
    ['Current imbalance (%)', CLEAR, '8.123', '10.000', '1.877', '—', 'Spec A'],
    ['Peak cell temperature (°C)', UNSET, '—', '—', '—', '—', 'An upper limit and a documented source are both required'],
  ]);
  assert.ok(!html.includes('<b>') && !html.includes('</b>'));
  assert.ok(html.includes('&lt;b&gt;rev 2&lt;/b&gt;'));
  assert.ok(html.endsWith('<p class="evidence-note">Simulated screen at saved solver samples. Not experimental acceptance or a safety rating. Unset limits are never passes.</p></div>'));
  assert.ok(html.includes('Unset limits are never passes'));

  // Backend status text is printed verbatim with the class that matches it.
  for (const [status, key] of [[VIOLATION, 'violation'], [CLEAR, 'clear'], [PARTIAL, 'partial'], [NOT_EVALUABLE, 'na'], [UNSET, 'unset']]) {
    const one = requirementsHTML({requirements: {peak_branch_current_A: {status}}});
    assert.ok(one.includes(`<span class="status s-${key}">${status}</span>`), status);
    assert.equal(count(one, 'class="status '), 1);
  }
  assert.ok(requirementsHTML({requirements: {peak_branch_current_A: {status: 'something new'}}}).includes('<span class="status s-unknown">something new</span>'));
  assert.ok(requirementsHTML({requirements: {peak_branch_current_A: {status: 'constructor'}}}).includes('<span class="status s-unknown">constructor</span>'));
  // A key the panel does not know still gets a row, after the known ones.
  const extra = rowsOf(requirementsHTML({requirements: {custom_limit: {status: PARTIAL}, current_imbalance_pct: {status: CLEAR}}}));
  assert.deepEqual(extra.slice(1).map(row => row[0]), ['Current imbalance (%)', 'custom_limit']);
  // No engineering block, no panel.
  assert.equal(requirementsHTML(undefined), '');
  assert.equal(requirementsHTML(null), '');
});

test('parsePlan converts milliohms to ohms, keeps lists in order, and rejects bad input', () => {
  const ok = {segments: ['rail_p_1', 'rail_n_3'], added: '1, 3', loads: '12 14.55', ambient: '25, 35', max: '60'};
  assert.deepEqual(parsePlan(ok), {
    rail_segments: ['rail_p_1', 'rail_n_3'], added_resistance_ohm: [0.001, 0.003], load_current_A: [12, 14.55], ambient_C: [25, 35], max_cases: 60,
  });
  assert.deepEqual(parsePlan({...ok, added: ' 2.5 ,  0.5 ', loads: '', ambient: '-10 0'}).added_resistance_ohm, [0.0025, 0.0005]);
  assert.deepEqual(parsePlan({...ok, ambient: '-10 0'}).ambient_C, [-10, 0]);
  assert.equal(parsePlan({...ok, max: 200}).max_cases, 200);
  assert.equal(parsePlan({...ok, max: '1'}).max_cases, 1);
  // Empty strings give empty lists, and no segment is needed when nothing is added.
  assert.deepEqual(parsePlan({segments: [], added: '', loads: '', ambient: '', max: 60}),
    {rail_segments: [], added_resistance_ohm: [], load_current_A: [], ambient_C: [], max_cases: 60});
  assert.deepEqual(parsePlan({segments: [], added: '  ', loads: ',', ambient: undefined, max: 60}).load_current_A, []);

  const fails = (values, message) => assert.throws(() => parsePlan(values), {message});
  const finite = 'Enter finite numbers separated by commas.';
  fails({...ok, added: 'abc'}, finite);
  fails({...ok, added: '1, two'}, finite);
  fails({...ok, loads: 'Infinity'}, finite);
  fails({...ok, ambient: '25;35'}, finite);
  fails({...ok, added: '-1'}, 'Added resistance must be positive.');
  fails({...ok, added: '0'}, 'Added resistance must be positive.');
  fails({...ok, added: '1, -3'}, 'Added resistance must be positive.');
  fails({...ok, loads: '0'}, 'Load currents must be positive.');
  fails({...ok, loads: '12 -1'}, 'Load currents must be positive.');
  fails({...ok, max: 0}, 'Case budget must be 1-200.');
  fails({...ok, max: '0'}, 'Case budget must be 1-200.');
  fails({...ok, max: 201}, 'Case budget must be 1-200.');
  fails({...ok, max: '60.5'}, 'Case budget must be 1-200.');
  fails({...ok, max: ''}, 'Case budget must be 1-200.');
  fails({...ok, max: 'many'}, 'Case budget must be 1-200.');
  fails({...ok, segments: []}, 'Select at least one rail segment.');
  fails({...ok, segments: undefined}, 'Select at least one rail segment.');
});

test('investigationFormHTML has the six segment checkboxes and the named inputs', () => {
  const html = investigationFormHTML(DESIGN);
  assert.equal(count(html, 'type="checkbox"'), 6);
  for (const cid of Object.keys(DESIGN.connections)) {
    assert.ok(html.includes(`<input type="checkbox" id="inv-seg-${cid}" value="${cid}">`), cid);
  }
  assert.deepEqual([...html.matchAll(/<label class="inv-check">.*?<\/label>/g)].map(m => strip(m[0]).trim()),
    ['Positive connection 1', 'Positive connection 2', 'Positive connection 3', 'Negative connection 1', 'Negative connection 2', 'Negative connection 3']);
  assert.equal(count(html, 'id="inv-seg-'), 6);
  assert.match(html, /<input id="inv-added"[^>]*type="text"[^>]*value="1, 3"/);
  assert.match(html, /<input id="inv-loads"[^>]*type="text"[^>]*value=""/);
  assert.match(html, /<input id="inv-ambient"[^>]*type="text"[^>]*value=""/);
  assert.ok(html.includes('id="inv-max" name="inv-max" type="number" value="60" min="1" max="200"'));
  assert.ok(html.includes('id="inv-run" class="primary">Run investigation</button>'));
  for (const label of ['Added contact resistance (mΩ)', 'Load currents (A)', 'Ambient temperatures (°C)']) {
    assert.ok(html.includes(`<label>${label}<input`), label);
  }
  assert.ok(html.includes('Uses the same electrical and thermal model as a normal run. Findings apply only to the evaluated cases.'));
  for (const id of ['inv-added', 'inv-loads', 'inv-ambient', 'inv-max', 'inv-run']) assert.equal(count(html, `id="${id}"`), 1, id);
  // A design with no connections yields no checkboxes; an id is escaped, never raw.
  assert.equal(count(investigationFormHTML({connections: {}}), 'type="checkbox"'), 0);
  assert.equal(count(investigationFormHTML({}), 'type="checkbox"'), 0);
  const odd = investigationFormHTML({connections: {'<i>': {}}});
  assert.ok(odd.includes('id="inv-seg-&lt;i&gt;"') && !odd.includes('<i>'));
});

test('investigationHTML lists coverage, per-requirement rankings and the exploration table, each case with an open button', () => {
  const html = investigationHTML(RECORD);
  assert.ok(html.includes('Evaluated 3 of 3'));
  assert.ok(html.includes('inv_0007'));
  assert.ok(html.includes('0 skipped by budget') && html.includes('0 stopped by solver') && html.includes('0 electrical errors') && html.includes('0 thermal failures'));
  // Distinct coverage numbers, so a swapped field would show.
  const partial = investigationHTML({...RECORD, coverage: {requested: 5, evaluated: 3, skipped_by_budget: 2, electrical_stopped: 1, errors: 4}});
  assert.ok(partial.includes('Evaluated 3 of 5'));
  assert.ok(partial.includes('2 skipped by budget') && partial.includes('1 stopped by solver') && partial.includes('4 electrical errors'));
  assert.ok(html.includes('Positive connection 1 +3.00 mΩ'));
  assert.ok(html.includes(NOTE));
  assert.ok(html.endsWith(`<p class="evidence-note">${NOTE}</p></div>`));
  // 3 exploration rows + 3 rows (list form) + 2 rows (object form); nothing ranked for temperature.
  assert.equal(count(html, 'class="small open-case"'), 8);
  const sections = sectionsOf(html);
  assert.deepEqual(Object.keys(sections), ['Peak branch current', 'Current imbalance', 'Exploration by peak branch current']);
  assert.ok(!html.includes('Peak cell temperature'));

  const open = id => `<button class="small open-case" data-case="${id}">${OPEN}</button>`;
  assert.deepEqual(rowsOf(sections['Peak branch current']), [
    ['Case', 'Change', 'Margin', 'Status', 'Action'],
    ['case_0002', 'Positive connection 1 +3.00 mΩ · 12.00 A · 25.0 °C', '-1.750', 'Limit exceeded', OPEN],
    ['case_0003', 'Negative connection 2 +1.00 mΩ · 0.0 °C', '0.750', 'No sampled exceedance', OPEN],
    ['case_0001', 'baseline contacts', '1.500', 'No sampled exceedance', OPEN],
  ]);
  assert.deepEqual(rowsOf(sections['Current imbalance']), [
    ['Case', 'Change', 'Margin', 'Status', 'Action'],
    ['case_0002', 'Positive connection 1 +3.00 mΩ · 12.00 A · 25.0 °C', '-8.500', 'Limit exceeded', OPEN],
    ['case_0001', 'baseline contacts', '5.800', 'No sampled exceedance', OPEN],
  ]);
  assert.ok(!sections['Peak branch current'].includes('Simulated violations'));                                   // bare list carries no count
  assert.ok(sections['Current imbalance'].includes('Simulated violations among evaluated cases: 1'));            // {cases, violations} does
  assert.ok(sections['Peak branch current'].includes(`<td>${open('case_0002')}</td>`));
  assert.ok(sections['Peak branch current'].includes(`<span class="status s-violation" title="${VIOLATION}">Limit exceeded</span>`));
  assert.ok(sections['Peak branch current'].includes(`<span class="status s-clear" title="${CLEAR}">No sampled exceedance</span>`));

  // by_metric in the backend's object shape {label, cases}: the label is shown above the table, rows come from cases.
  const exploration = sections['Exploration by peak branch current'];
  assert.ok(exploration.includes(LABEL));
  assert.ok(exploration.indexOf(LABEL) < exploration.indexOf('<table>'));
  assert.deepEqual(rowsOf(exploration), [
    ['Case', 'Change', 'Peak current (A)', 'Peak temperature (°C)', 'Imbalance (%)', 'Action'],
    ['case_0002', 'Positive connection 1 +3.00 mΩ · 12.00 A · 25.0 °C', '13.750', '36.50', '18.5', OPEN],
    ['case_0003', 'Negative connection 2 +1.00 mΩ · 0.0 °C', '11.250', '—', '—', OPEN],
    ['case_0001', 'baseline contacts', '10.500', '31.25', '4.2', OPEN],
  ]);
  assert.equal(count(exploration, 'class="small open-case"'), 3);

  // by_metric as a bare list gives the same rows and, having no label, shows none.
  const listForm = investigationHTML(withMetric(RECORD.rankings.by_metric.peak_branch_current_A.cases));
  assert.deepEqual(rowsOf(sectionsOf(listForm)['Exploration by peak branch current']), rowsOf(exploration));
  assert.ok(!listForm.includes(LABEL));
  assert.equal(count(listForm, 'class="small open-case"'), 8);
  // Case metrics given as {value, unit} objects (the engineering summary's shape) read the same as plain numbers.
  const objectMetrics = {...RECORD, cases: RECORD.cases.map(c => ({...c, metrics: Object.fromEntries(Object.entries(c.metrics).map(([k, v]) => [k, {value: v, unit: 'u'}]))}))};
  assert.deepEqual(rowsOf(sectionsOf(investigationHTML(objectMetrics))['Exploration by peak branch current']), rowsOf(exploration));
  // A metric entry with an empty case list draws no exploration table.
  assert.ok(!('Exploration by peak branch current' in sectionsOf(investigationHTML(withMetric({label: LABEL, cases: []})))));

  // Only the top 10 of 12 are drawn in each table, and the cut is stated.
  const many = investigationHTML(MANY);
  const manySections = sectionsOf(many);
  assert.equal(rowsOf(manySections['Peak branch current']).length - 1, 10);
  assert.equal(rowsOf(manySections['Exploration by peak branch current']).length - 1, 10);
  assert.ok(!many.includes('case_0011') && !many.includes('case_0012'));
  assert.equal(count(many, 'Showing the first 10 of 12 ranked cases.'), 2);
  assert.equal(count(many, 'class="small open-case"'), 20);
  assert.ok(!html.includes('Showing the first'));

  // A ranked case the record does not contain still gets a row, with no invented change summary.
  const ghost = investigationHTML({investigation_id: 'inv_0009', coverage: {}, cases: [], rankings: {by_requirement: {}, by_metric: {peak_branch_current_A: [{case_id: 'ghost', value: 1}]}}});
  assert.deepEqual(rowsOf(ghost).slice(1), [['ghost', '—', '1.000', '—', '—', OPEN]]);
  // Missing input never throws.
  assert.equal(investigationHTML(undefined), '');
  assert.equal(investigationHTML(null), '');
  const bare = investigationHTML({});
  assert.ok(bare.includes(NOTE) && !bare.includes('open-case'));
  // Text from the record is escaped.
  const hostile = investigationHTML({...RECORD, investigation_id: 'inv<b>', cases: [{...RECORD.cases[1], case_id: 'case_0002', rail_segment: 'rail<i>_1'}, ...RECORD.cases.slice(0, 1)]});
  assert.ok(hostile.includes('inv&lt;b&gt;') && hostile.includes('rail&lt;i&gt;_1 +3.00 mΩ'));
  assert.ok(!hostile.includes('<b>') && !hostile.includes('<i>'));
});

test('no output carries a style attribute or an inline event handler attribute', () => {
  const engineering = {requirements: {
    peak_branch_current_A: {status: VIOLATION, value: 14.2, limit: 12, margin: -2.2, first_crossing_time_s: 31.2, documented_source: 'Datasheet <b>rev 2</b>'},
    current_imbalance_pct: {status: CLEAR, value: 8, limit: 10, margin: 2, documented_source: 'Spec A'},
    peak_cell_temperature_C: {status: UNSET, reason: 'An upper limit and a documented source are both required'},
  }};
  const outputs = {
    unavailable: thermalMetricsHTML(undefined),
    failed: thermalMetricsHTML({thermal: {status: 'failed', error: {message: 'bad <b>input</b>'}}}),
    completed: thermalMetricsHTML({thermal: {status: 'completed', peak_cell_temperature_C: 27.4, peak_cell: 'cell_3', maximum_spread_K: 3.1}, engineering: {metrics: {current_imbalance_pct: {value: 12}}}}),
    requirements: requirementsHTML(engineering),
    form: investigationFormHTML(DESIGN),
    investigation: investigationHTML(RECORD),
    investigationListForm: investigationHTML(withMetric(RECORD.rankings.by_metric.peak_branch_current_A.cases)),
    many: investigationHTML(MANY),
    empty: investigationHTML({}),
  };
  for (const [name, html] of Object.entries(outputs)) {
    assert.ok(html.length > 0, name);
    assert.doesNotMatch(html, /\sstyle\s*=/i, name);
    assert.doesNotMatch(html, /\son[a-z]+\s*=/i, name);
    assert.doesNotMatch(html, /<script|javascript:/i, name);
  }

  // Hostile text in every interpolated slot: after escaping, no tag gains a style or on* attribute, and no markup opens.
  const hostile = 'x" onfocus="alert(1)';
  const record = {investigation_id: hostile, coverage: {requested: 1, evaluated: 1}, cases: [{case_id: hostile, rail_segment: hostile, added_resistance_ohm: 0.001}],
    rankings: {by_requirement: {peak_branch_current_A: [{case_id: hostile, margin: 1, status: hostile}]}, by_metric: {peak_branch_current_A: {label: hostile, cases: [{case_id: hostile, value: 1}]}}}};
  const hostileOutputs = [
    thermalMetricsHTML({thermal: {status: 'failed', error: {message: hostile}}}),
    thermalMetricsHTML({thermal: {status: 'completed', peak_cell_temperature_C: 1, peak_cell: hostile, maximum_spread_K: 1}}),
    requirementsHTML({requirements: {peak_branch_current_A: {status: hostile, documented_source: hostile}, [hostile]: {status: hostile, reason: hostile}}}),
    investigationFormHTML({connections: {[hostile]: {}}}),
    investigationHTML(record),
  ];
  for (const html of hostileOutputs) {
    const names = attributeNames(html);
    assert.ok(names.length > 0);
    assert.ok(names.every(name => name !== 'style' && !name.startsWith('on')), names.join(','));
    assert.equal(count(html, '<'), count(html, '>'));
    assert.ok(!html.includes('x" onfocus'));
  }
});
