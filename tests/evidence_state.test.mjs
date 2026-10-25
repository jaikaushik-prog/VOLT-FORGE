// Read-only contract fixtures and synthetic UI mutations; no physical calculation.
import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {EvidenceRequestGuard, selectionKey, presentEvidence, presentPreview} from '../web/editor/evidence-state.mjs';
import {escapeHTML} from '../web/editor/state.mjs';

function fixture(name) {
  const url = new URL(`../reports/parallel_engineering_v1/demo_001/examples/${name}_request_response.json`, import.meta.url);
  return JSON.parse(readFileSync(url, 'utf8'));
}
const saved = fixture('05_saved_run_explanation');
const config = fixture('02_configuration_explanation');
const historical = fixture('15_A1_historical_explanation');
const preview = fixture('06_structured_preview');
const copy = value => structuredClone(value);
function selection(result = saved.response.result) {
  const b = result.binding;
  return {variant_id:b.variant_id,revision_id:b.current_revision_id,component_id:b.component_id,run_id:b.run_id};
}

test('current presentation retains actual values, units, context and every citation', () => {
  const original = JSON.stringify(saved);
  const model = presentEvidence(saved.response, selection());
  assert.equal(model.ok, true);
  assert.equal(model.state, 'current');
  assert.equal(model.contextId, saved.response.result.binding.context_id);
  assert.deepEqual(model.runStatus, saved.response.result.run_status);
  assert.deepEqual(model.coverage, saved.response.result.coverage);
  assert.equal(model.claims.length, saved.response.result.claims.length);
  assert.deepEqual(model.groups.map(group => group.id), ['inputs','models','outputs','evidence']);
  for (const [i, claim] of model.claims.entries()) {
    const actual = saved.response.result.claims[i];
    assert.deepEqual(claim.value, actual.value);
    assert.deepEqual(claim.source, actual.source);
    assert.equal(claim.unit, actual.unit ?? null);
    assert.ok(claim.citationText.includes(actual.source.source_pointer));
    assert.ok(claim.citationText.includes(actual.source.context_id));
  }
  assert.deepEqual(presentEvidence(saved.response.result, selection()), model);
  assert.equal(JSON.stringify(saved), original);
});

test('unconfigured requirements cannot become a pass or experimental acceptance', () => {
  const model = presentEvidence(saved.response, selection());
  assert.equal(model.requirement.state, 'unconfigured');
  assert.equal(model.requirement.statusText, 'requirement not configured');
  assert.equal(model.decision, 'insufficient evidence');
  assert.match(model.requirement.warning, /no pass/);
  const configured = copy(saved.response.result);
  configured.requirement_check = {status:'within configured voltage requirement',source:'synthetic UI fixture'};
  const changed = presentEvidence(configured, selection(configured));
  assert.equal(changed.requirement.state, 'simulated_screen');
  assert.match(changed.requirement.warning, /not experimental acceptance/);
});

test('configuration-only evidence never acquires simulated claims or an implied run', () => {
  const model = presentEvidence(config.response, selection(config.response.result));
  assert.equal(model.ok, true);
  assert.equal(model.state, 'configuration_only');
  assert.equal(model.binding.run_id, null);
  assert.equal(model.runStatus, null);
  assert.equal(model.coverage, null);
  assert.equal(model.requirement.state, 'not_available');
  assert.equal(model.groups.some(group => group.id === 'outputs'), false);
  assert.match(model.warnings.join(' '), /not predictions/);
  const forged = copy(config.response.result);
  forged.claims.push(copy(saved.response.result.claims.find(claim => claim.kind === 'simulated_output')));
  assert.equal(presentEvidence(forged, selection(forged)).state, 'malformed');
});

test('historical evidence preserves current design and historical output revision separately', () => {
  const result = historical.response.result;
  const model = presentEvidence(result, selection(result));
  assert.equal(model.ok, true);
  assert.equal(model.state, 'outdated');
  assert.equal(model.flags.outdated, true);
  assert.notEqual(model.binding.run_revision_id, model.binding.current_revision_id);
  assert.deepEqual(model.runStatus.outdated_reasons, result.run_status.outdated_reasons);
  const output = model.claims.find(claim => claim.kind === 'simulated_output');
  assert.equal(output.source.revision_id, model.binding.run_revision_id);
  assert.match(model.warnings.join(' '), /historical run is outdated/);
});

test('failed and outdated flags coexist; missing coverage never means supported', () => {
  const result = copy(historical.response.result);
  result.run_status.execution_status = 'failed';
  result.run_status.error = {message:'Synthetic UI failure',last_valid_time_s:0};
  result.coverage = null;
  const model = presentEvidence(result, selection(result));
  assert.equal(model.ok, true);
  assert.equal(model.state, 'failed');
  assert.equal(model.flags.failed, true);
  assert.equal(model.flags.outdated, true);
  assert.equal(model.title, 'Failed historical run');
  assert.deepEqual(model.runStatus.error, result.run_status.error);
  assert.match(model.warnings.join(' '), /partial execution/);
  assert.match(model.warnings.join(' '), /Missing coverage does not establish support/);
  assert.equal(model.claims.length, result.claims.length);
});

test('no response, rejected response and malformed response remain distinct', () => {
  assert.equal(presentEvidence(null, selection()).state, 'none');
  const error = presentEvidence({status:'error',error:{code:'stale_context',message:'Reload the current context.'}}, selection());
  assert.equal(error.state, 'error');
  assert.equal(error.errorCode, 'stale_context');
  assert.equal(error.ok, false);
  for (const response of [{}, {status:'ok',result:{}}, {status:'error'}, [], 2, 'not evidence']) {
    const model = presentEvidence(response, selection());
    assert.equal(model.ok, false);
    assert.equal(model.state, 'malformed');
    assert.deepEqual(model.groups, []);
  }
  const inconsistent = copy(saved.response.result);
  inconsistent.binding.run_revision_id = 'a_different_design_revision';
  assert.equal(presentEvidence(inconsistent, selection(inconsistent)).state, 'malformed');
});

test('every selection dimension prevents a response from being shown in another context', () => {
  for (const [key, value] of [['variant_id','A_other'],['revision_id','rev_other'],['component_id','cell_4'],['run_id','run_other']]) {
    const changed = {...selection(),[key]:value};
    assert.equal(presentEvidence(saved.response, changed).state, 'selection_changed');
    assert.equal(presentPreview(preview.response, changed, preview.request.arguments.edit).state, 'selection_changed');
  }
  assert.equal(presentEvidence(saved.response, {...selection(),run_id:null}).state, 'selection_changed');
});

test('numerical claims require a citation, a unit and the actual bound run and snapshot', () => {
  const mutations = [
    claim => { delete claim.source; },
    claim => { delete claim.unit; },
    claim => { claim.source.context_id = 'another_context'; },
    claim => { claim.source.snapshot_id = 'another_snapshot'; },
    claim => { claim.source.run_id = 'run_other'; },
    claim => { claim.source.arguments.variant_id = 'A_other'; },
    claim => { claim.source.operation = 'ai_prediction'; },
    claim => { claim.value = Infinity; },
  ];
  for (const mutate of mutations) {
    const changed = copy(saved.response.result);
    mutate(changed.claims.find(claim => claim.kind === 'simulated_output'));
    assert.equal(presentEvidence(changed, selection(changed)).state, 'malformed');
  }
});

test('sample citations bind to selected component without treating module summary as cell output', () => {
  const changed = copy(saved.response.result);
  changed.claims.find(claim => claim.kind === 'simulated_sample').source.component_id = 'cell_4';
  assert.equal(presentEvidence(changed, selection(changed)).state, 'malformed');
  const normal = presentEvidence(saved.response, selection());
  const output = normal.claims.find(claim => claim.kind === 'simulated_output');
  assert.equal(output.componentId, 'module');
});

test('request tickets reject late results after selection changes and reverse completion order', () => {
  const guard = new EvidenceRequestGuard();
  const initial = selection();
  const old = guard.begin(initial);
  const changed = {...initial,component_id:'cell_2'};
  assert.equal(guard.current(old, changed), false);
  const fresh = guard.begin(changed);
  assert.equal(guard.current(fresh, changed), true);
  assert.equal(guard.current(old, initial), false);
  assert.equal(guard.current({...fresh}, changed), false);
  guard.invalidate();
  assert.equal(guard.current(fresh, changed), false);
});

test('editing any preview input invalidates the ticket, including edit then revert', () => {
  const guard = new EvidenceRequestGuard();
  const original = preview.request.arguments.edit;
  const first = guard.begin(selection(), original);
  assert.equal(guard.current(first, selection(), copy(original)), true);
  const changed = {...original,source:'Another declared assumption'};
  assert.equal(guard.current(first, selection(), changed), false);
  guard.invalidate(); // every editor input event, including an edit reverted before response
  assert.equal(guard.current(first, selection(), original), false);
  const second = guard.begin(selection(), changed);
  assert.equal(guard.current(second, selection(), changed), true);
  assert.equal(presentPreview(preview.response, selection(), changed).state, 'edit_changed');
});

test('request keys are stable JSON identities and reject missing or extra selection fields', () => {
  const selected = selection();
  assert.equal(selectionKey(selected), selectionKey(Object.fromEntries(Object.entries(selected).reverse())));
  assert.throws(() => selectionKey({...selected,camera:{zoom:2}}));
  assert.throws(() => selectionKey({...selected,run_id:''}));
  assert.throws(() => selectionKey({...selected,revision_id:null}));
  assert.throws(() => selectionKey({variant_id:'A0'}));
  const guard = new EvidenceRequestGuard();
  const old = guard.begin(selected);
  assert.throws(() => guard.begin(selected, {value:NaN}));
  assert.equal(guard.current(old, selected), false);
  assert.equal(guard.current(null, selected), false);
});

test('a valid preview exposes exact before/proposed data and invalidated IDs without executing', () => {
  const original = JSON.stringify(preview);
  const model = presentPreview(preview.response, selection(), preview.request.arguments.edit);
  assert.equal(model.ok, true);
  assert.equal(model.state, 'approval_required');
  assert.equal(model.contextId, preview.response.result.binding.context_id);
  assert.deepEqual(model.proposed, preview.request.arguments.edit);
  assert.deepEqual(model.before.value, preview.response.result.before.value);
  assert.deepEqual(model.invalidatedRunIds, preview.response.result.validation.invalidated_run_ids);
  assert.equal(model.applied, false);
  assert.equal(model.simulationStarted, false);
  assert.equal(model.predictedEffect, null);
  assert.match(model.warnings.join(' '), /not changed the project/);
  assert.equal(JSON.stringify(preview), original);
  model.proposed.value = 999;
  assert.notEqual(preview.request.arguments.edit.value, model.proposed.value);
});

function scalarPreview(target, id, property, unit, nextValue) {
  // Same saved design and unchanged field values; only the proposed UI edit and
  // its direct inspect citation are synthesized. No backend/model is modified.
  const result = copy(preview.response.result);
  const design = preview.request.context.result.project.design;
  const field = target === 'simulation' ? `simulation/${property}`
    : `${target === 'cell' ? 'cells' : 'connections'}/${id}/${property}`;
  result.proposed_edit = {...result.proposed_edit,target,id,property,unit,value:nextValue};
  result.before.value = field.split('/').reduce((value, key) => value[key], design);
  delete result.before.unit;
  result.before.source.context_pointer = '/project/design/' + field;
  result.before.source.source_pointer = '/result/design/' + field;
  result.before.source.component_id = id;
  return result;
}

test('timestep preview derives seconds from the exact supported schema while preserving its source claim', () => {
  const result = scalarPreview('simulation','module','dt_s','s',0.5);
  const original = copy(result);
  assert.equal(typeof result.before.value, 'number');
  assert.equal(Object.hasOwn(result.before,'unit'), false);
  const model = presentPreview(result, selection(result), result.proposed_edit);
  assert.equal(model.ok, true);
  assert.equal(model.before.unit, 's');
  assert.equal(model.before.unitProvenance.kind, 'schema_derived');
  assert.equal(model.before.unitProvenance.schema, 'voltforge.design/1');
  assert.equal(model.before.unitProvenance.property, 'simulation.dt_s');
  assert.equal(model.before.unitProvenance.sourceUnit, null);
  assert.equal(model.before.unitProvenance.sourceUnitPresent, false);
  assert.deepEqual(model.before.sourceClaim, original.before);
  assert.deepEqual(model.before.source, original.before.source);
  assert.equal(model.before.value, original.before.value);
  assert.deepEqual(result, original);
});

test('other supported scalar edits retain their quantity-object units without inventing claim metadata', () => {
  for (const args of [
    ['connection','rail_p_1','resistance','ohm',0.0007],
    ['cell','cell_1','initial_soc','fraction',0.69],
    ['cell','cell_1','initial_polarization','V',0.001],
  ]) {
    const result = scalarPreview(...args);
    const model = presentPreview(result, selection(result), result.proposed_edit);
    assert.equal(model.ok, true);
    assert.deepEqual(model.before.value, result.before.value);
    assert.equal(model.before.value.unit, args[3]);
    assert.equal(model.before.unit, null);
    assert.equal(model.before.unitProvenance, undefined);
    assert.deepEqual(model.before.source, result.before.source);
  }
});

test('schema unit fallback cannot accept arbitrary unitless claims, edits or mismatched pointers', () => {
  for (const mutate of [
    result => { result.proposed_edit.unit = 'V'; },
    result => { result.proposed_edit.property = 'arbitrary_parameter'; },
    result => { result.proposed_edit.id = 'cell_1'; },
    result => { result.before.source.context_pointer = '/project/design/requirements/minimum_terminal_voltage_V'; },
    result => { result.before.source.source_pointer = '/result/design/simulation/unknown_field'; },
    result => { result.before.unit = null; },
  ]) {
    const result = scalarPreview('simulation','module','dt_s','s',0.5);
    mutate(result);
    assert.equal(presentPreview(result, selection(result), result.proposed_edit).state, 'malformed');
  }
  const rail = scalarPreview('connection','rail_p_1','resistance','ohm',0.0007);
  rail.before.value = 0.001; // not the actual quantity-object schema
  assert.equal(presentPreview(rail, selection(rail), rail.proposed_edit).state, 'malformed');
  const evidence = copy(saved.response.result);
  const output = evidence.claims.find(claim => claim.kind === 'simulated_output');
  delete output.unit;
  assert.equal(presentEvidence(evidence, selection(evidence)).state, 'malformed');
});

test('preview rejects supplied outcomes or execution and cannot hide a revision mismatch', () => {
  for (const mutate of [
    result => { result.predicted_effect = {terminal_V:4.2}; },
    result => { result.applied = true; },
    result => { result.simulation_started = true; },
    result => { result.validation.expected_revision = 'other_revision'; },
    result => { result.validation.valid = false; },
    result => { result.before.source = null; },
  ]) {
    const changed = copy(preview.response.result);
    mutate(changed);
    assert.equal(presentPreview(changed, selection(), preview.request.arguments.edit).state, 'malformed');
  }
  assert.equal(presentPreview(null, selection(), {}).state, 'none');
});

test('hostile strings stay inspectable data and are escaped only at the rendering boundary', () => {
  const hostile = '<img src=x onerror="globalThis.compromised=true"> & \'quoted\'';
  const changed = copy(config.response.result);
  changed.claims[0].label = hostile;
  changed.claims[0].value = hostile;
  changed.explanation = hostile;
  const model = presentEvidence(changed, selection(changed));
  assert.equal(model.ok, true);
  assert.equal(model.claims[0].label, hostile);
  assert.equal(model.claims[0].valueText, hostile);
  assert.equal(model.explanation, hostile);
  assert.equal(Object.hasOwn(model.claims[0], 'html'), false);
  assert.equal(Object.hasOwn(model.claims[0], 'href'), false);
  assert.ok(escapeHTML(model.claims[0].valueText).startsWith('&lt;img'));
  assert.equal(globalThis.compromised, undefined);
  const proposed = copy(preview.response.result);
  proposed.proposed_edit.source = hostile;
  const shown = presentPreview(proposed, selection(), proposed.proposed_edit);
  assert.equal(shown.ok, true);
  assert.equal(shown.proposed.source, hostile);
  assert.equal(shown.predictedEffect, null);
});
