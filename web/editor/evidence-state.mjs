// Pure presentation and request coordination. No HTML, URLs, actions or physics.
// Every returned string is data: render it with textContent or the editor's h().
const SCHEMA = 'voltforge.copilot_contract/1';
const SELECTION_FIELDS = ['variant_id', 'revision_id', 'component_id', 'run_id'];
const GROUPS = [
  ['inputs', 'Configured inputs and requirements', ['configured_input', 'configured_requirements', 'existing_input']],
  ['models', 'Cell identity and fitted model', ['component_identity', 'fitted_artifact_reference', 'fitted_parameter', 'derived_capacity']],
  ['outputs', 'Saved simulated outputs', ['simulated_output', 'simulated_sample', 'units']],
  ['evidence', 'Evidence and limitations', ['experimental_evidence_status', 'solver_evidence_status']],
];
const KINDS = new Set(GROUPS.flatMap(group => group[2]));
const isObject = value => value !== null && typeof value === 'object' && !Array.isArray(value)
  && [Object.prototype, null].includes(Object.getPrototypeOf(value));
const isText = value => typeof value === 'string' && value.trim().length > 0;
const isTextList = value => Array.isArray(value) && value.every(item => typeof item === 'string');

function require(condition, message) { if (!condition) throw new TypeError(message); }
function canonical(value, seen = new Set(), depth = 0) {
  require(depth <= 64, 'Evidence data is nested too deeply.');
  if (value === null || typeof value === 'string' || typeof value === 'boolean') return JSON.stringify(value);
  if (typeof value === 'number') { require(Number.isFinite(value), 'Evidence contains a nonfinite number.'); return JSON.stringify(value); }
  require(Array.isArray(value) || isObject(value), 'Evidence must contain JSON data only.');
  require(!seen.has(value), 'Evidence contains a circular reference.');
  seen.add(value);
  const result = Array.isArray(value)
    ? '[' + value.map(item => canonical(item, seen, depth + 1)).join(',') + ']'
    : '{' + Object.keys(value).sort().map(key => JSON.stringify(key) + ':' + canonical(value[key], seen, depth + 1)).join(',') + '}';
  seen.delete(value);
  return result;
}
// Validate as JSON, then retain exact numeric values (including signed zero).
const clone = value => { canonical(value); return structuredClone(value); };

/** Exact physics selection only; display positions/camera are deliberately absent. */
export function selectionKey(selection) {
  require(isObject(selection) && Object.keys(selection).length === SELECTION_FIELDS.length
    && SELECTION_FIELDS.every(key => Object.hasOwn(selection, key)), 'Select a variant, revision, component and explicit run or null.');
  require(['variant_id', 'revision_id', 'component_id'].every(key => isText(selection[key])), 'Selection identifiers must be nonempty strings.');
  require(selection.run_id === null || isText(selection.run_id), 'Run selection must be a nonempty ID or null.');
  return canonical(selection);
}

/** Use one instance per request stream. Invalidate on every input/selection event,
 * including edit-then-revert: equality alone cannot detect an intervening edit.
 */
export class EvidenceRequestGuard {
  constructor() { this.epoch = 0; this.ticket = null; }
  begin(selection, edit = null) {
    this.ticket = null;
    const ticket = Object.freeze({epoch: ++this.epoch, selectionKey: selectionKey(selection), editKey: canonical(edit)});
    this.ticket = ticket;
    return ticket;
  }
  current(ticket, selection, edit = null) {
    if (!ticket || ticket !== this.ticket) return false;
    try { return ticket.selectionKey === selectionKey(selection) && ticket.editKey === canonical(edit); }
    catch { return false; }
  }
  invalidate() { this.epoch += 1; this.ticket = null; }
}

function unavailable(state, title, message, code = null) {
  return {ok: false, state, title, warnings: message ? [message] : [], errorCode: code,
    binding: null, groups: [], claims: [], runStatus: null, requirement: null,
    coverage: null, invalidatedRunIds: [], before: null, proposed: null};
}
function unwrap(response, operation) {
  canonical(response);
  require(isObject(response), 'The evidence response is not an object.');
  if (response.status === 'error') {
    require(isObject(response.error) && isText(response.error.code) && isText(response.error.message), 'Malformed error response.');
    return {error: unavailable('error', operation === 'explain' ? 'Evidence unavailable' : 'Preview unavailable',
      response.error.message, response.error.code)};
  }
  const result = response.status === 'ok' ? response.result : response;
  require(isObject(result) && result.schema === SCHEMA && result.operation === operation, 'Unsupported evidence response format.');
  return {result};
}
function matchedBinding(binding, selection) {
  selectionKey(selection);
  require(isObject(binding) && isText(binding.context_id) && isText(binding.current_revision_id), 'The evidence response has no valid context binding.');
  for (const key of ['variant_id', 'component_id']) require(isText(binding[key]), 'The evidence response has incomplete selection identifiers.');
  if (binding.run_id === null) {
    require(binding.snapshot_id === null && binding.run_revision_id === null, 'Configuration-only evidence cannot cite a run snapshot.');
  } else {
    require(isText(binding.run_id) && isText(binding.snapshot_id) && isText(binding.run_revision_id), 'Saved output requires run, revision and snapshot IDs.');
  }
  return binding.variant_id === selection.variant_id && binding.current_revision_id === selection.revision_id
    && binding.component_id === selection.component_id && binding.run_id === selection.run_id;
}
function citation(source, binding) {
  require(isObject(source), 'Every evidence claim requires a source citation.');
  for (const key of ['context_id', 'context_pointer', 'reference_id', 'operation', 'source_pointer', 'revision_id']) {
    require(isText(source[key]), 'The claim citation is missing ' + key + '.');
  }
  require(source.context_id === binding.context_id, 'A claim belongs to a different evidence context.');
  require(source.context_pointer.startsWith('/') && source.source_pointer.startsWith('/'), 'Evidence citations require explicit JSON pointers.');
  require(['inspect', 'get_run', 'series'].includes(source.operation) && isObject(source.arguments), 'Unsupported claim source operation.');
  require(source.arguments.variant_id === binding.variant_id, 'A claim belongs to a different viewed variant.');
  if (source.operation === 'inspect') {
    require(source.revision_id === binding.current_revision_id, 'Configured input citation does not match the current design.');
    require(!Object.hasOwn(source, 'run_id') && !Object.hasOwn(source, 'snapshot_id'), 'Configured input citation unexpectedly claims a saved run.');
  } else {
    require(binding.run_id !== null && source.run_id === binding.run_id && source.snapshot_id === binding.snapshot_id
      && source.revision_id === binding.run_revision_id && source.arguments.run_id === binding.run_id,
    'A claim belongs to a different run, revision or snapshot.');
    if (source.operation === 'series') {
      require(source.component_id === binding.component_id && source.arguments.component_id === binding.component_id,
        'A stored sample belongs to a different selected component.');
    }
  }
  const fields = [['Source', source.operation], ['Field', source.source_pointer], ['Revision', source.revision_id]];
  for (const [key, label] of [['run_id', 'Run'], ['snapshot_id', 'Snapshot'], ['component_id', 'Component']]) {
    if (Object.hasOwn(source, key)) { require(isText(source[key]), 'Invalid citation ' + key + '.'); fields.push([label, source[key]]); }
  }
  fields.push(['Context', source.context_id]);
  return {source: clone(source), citationText: fields.map(([label, value]) => `${label}: ${value}`).join(' | '),
    citationFields: fields.map(([label, value]) => ({label, value}))};
}
function presentClaim(item, binding) {
  require(isObject(item) && KINDS.has(item.kind) && isText(item.label) && Object.hasOwn(item, 'value'), 'Malformed or unsupported evidence claim.');
  if (Object.hasOwn(item, 'unit')) require(isText(item.unit), 'Claim units must be explicit text.');
  if (typeof item.value === 'number') require(isText(item.unit), 'A numerical claim requires units.');
  if (item.kind.startsWith('simulated') || item.kind === 'units') {
    require(binding.run_id !== null && ['get_run', 'series'].includes(item.source?.operation), 'Simulated output requires a saved-run citation.');
  }
  const value = clone(item.value);
  return {kind: item.kind, label: item.label, value, valueText: typeof value === 'string' ? value : JSON.stringify(value, null, 2),
    unit: item.unit ?? null, componentId: item.source?.component_id ?? null, ...citation(item.source, binding)};
}
function presentBefore(item, binding, edit) {
  // The frozen preview copies design.simulation.dt_s as a direct number and does
  // not attach a claim unit. Unlike quantity-object inputs, its unit lives in
  // voltforge.design/1 EDITABLE metadata. Infer only this exact supported field;
  // never borrow an arbitrary edit's unit or modify the source claim/citation.
  const timestep = typeof item?.value === 'number' && !Object.hasOwn(item, 'unit')
    && edit.target === 'simulation' && edit.id === 'module' && edit.property === 'dt_s' && edit.unit === 's'
    && item.source?.operation === 'inspect'
    && item.source.context_pointer === '/project/design/simulation/dt_s'
    && item.source.source_pointer === '/result/design/simulation/dt_s';
  if (!timestep) return presentClaim(item, binding);
  return {...presentClaim({...item, unit:'s'}, binding),
    unitProvenance: {kind:'schema_derived',schema:'voltforge.design/1',property:'simulation.dt_s',
      source:'src/voltforge/project/schema.py:EDITABLE',sourceUnit:null,sourceUnitPresent:false,
      explanation:'Seconds are defined by the supported project schema; the original before claim supplied no unit.'},
    sourceClaim:clone(item)};
}
function groupClaims(claims) {
  return GROUPS.map(([id, title, kinds]) => ({id, title, claims: claims.filter(item => kinds.includes(item.kind))})).filter(group => group.claims.length);
}
function requirementView(check) {
  if (check === null) return {state: 'not_available', statusText: 'No requirement check available', detail: null,
    warning: 'No requirement check is available; this is not a pass.'};
  require(isObject(check) && isText(check.status), 'Malformed requirement-check result.');
  const missing = check.status === 'requirement not configured';
  return {state: missing ? 'unconfigured' : 'simulated_screen', statusText: check.status, detail: clone(check),
    warning: missing ? 'The voltage requirement is not configured; no pass is asserted.'
      : 'This requirement result is a simulation screen, not experimental acceptance.'};
}

/** Plain presentation model. It never treats failed/outdated evidence as current. */
export function presentEvidence(response, selection) {
  if (response === null || response === undefined) return unavailable('none', 'No evidence loaded', 'Inspect the current selection to load its evidence.');
  try {
    const unwrapped = unwrap(response, 'explain');
    if (unwrapped.error) return unwrapped.error;
    const result = unwrapped.result;
    if (!matchedBinding(result.binding, selection)) return unavailable('selection_changed', 'Selection changed', 'This evidence belongs to another selection. Inspect the current selection again.');
    require(Array.isArray(result.claims) && isText(result.explanation) && isTextList(result.limitations), 'Evidence claims or limitations are missing.');
    require(result.decision === 'insufficient evidence', 'Unexpected experimental decision from this unvalidated module.');
    const configurationOnly = result.status === 'configuration_only';
    require(configurationOnly || result.status === 'evidence_explanation', 'Unknown explanation status.');
    let failed = false, outdated = false, runStatus = null;
    if (configurationOnly) {
      require(result.binding.run_id === null && result.run_status === null && result.coverage === null && result.requirement_check === null,
        'Configuration-only evidence unexpectedly contains run results.');
    } else {
      const run = result.run_status;
      require(result.binding.run_id !== null && isObject(run) && ['completed', 'failed'].includes(run.execution_status)
        && ['current', 'outdated'].includes(run.freshness) && isTextList(run.outdated_reasons) && Object.hasOwn(run, 'error'), 'Malformed saved-run status.');
      failed = run.execution_status === 'failed'; outdated = run.freshness === 'outdated';
      require(failed || run.error === null, 'A completed run cannot hide an execution error.');
      require(outdated || result.binding.run_revision_id === result.binding.current_revision_id,
        'A current run must belong to the current design revision.');
      require(result.coverage === null || isObject(result.coverage), 'Malformed coverage metadata.');
      runStatus = clone(run);
    }
    const claims = result.claims.map(item => presentClaim(item, result.binding));
    const requirement = requirementView(result.requirement_check);
    const warnings = [requirement.warning];
    if (configurationOnly) warnings.push('No saved run is selected. These are configured inputs and fitted values, not predictions.');
    if (failed) warnings.push('The run failed. Any retained outputs describe partial execution, not completed service.');
    if (outdated) warnings.push('This historical run is outdated for the selected variant. Current inputs and saved outputs have different ownership or dependencies.');
    if (!configurationOnly && result.coverage === null) warnings.push('Coverage metadata is unavailable. Missing coverage does not establish support.');
    warnings.push('Experimental module validation is awaiting suitable measurements.', 'Electrical losses do not predict temperature.', ...result.limitations);
    return {ok: true, state: configurationOnly ? 'configuration_only' : failed ? 'failed' : outdated ? 'outdated' : 'current',
      title: configurationOnly ? 'Configuration evidence' : failed ? (outdated ? 'Failed historical run' : 'Failed run / partial evidence')
        : outdated ? 'Historical simulation evidence' : 'Current simulation evidence',
      flags: {configurationOnly, failed, outdated}, binding: clone(result.binding), contextId: result.binding.context_id,
      runStatus, claims, groups: groupClaims(claims), requirement, coverage: clone(result.coverage),
      explanation: result.explanation, decision: result.decision,
      pagination: clone(result.evidence_pagination ?? null), warnings: [...new Set(warnings)],
      unavailableCapabilities: clone(result.unavailable_capabilities ?? [])};
  } catch (error) { return unavailable('malformed', 'Evidence unavailable', error.message, 'malformed_response'); }
}

/** A preview is display data, not authorization. Input changes discard it. */
export function presentPreview(response, selection, edit) {
  if (response === null || response === undefined) return unavailable('none', 'No change preview', 'Preview the exact proposed input before applying a revision.');
  try {
    const unwrapped = unwrap(response, 'preview_edit');
    if (unwrapped.error) return unwrapped.error;
    const result = unwrapped.result;
    if (!matchedBinding(result.binding, selection)) return unavailable('selection_changed', 'Selection changed', 'This preview belongs to another selection. Preview the current input again.');
    require(isObject(edit) && isObject(result.proposed_edit), 'A structured edit is required.');
    if (canonical(edit) !== canonical(result.proposed_edit)) return unavailable('edit_changed', 'Input changed', 'The proposed input changed. Discard this preview and preview the new input.');
    const validation = result.validation;
    require(result.status === 'approval_required' && isText(result.preview_id) && result.applied === false
      && result.simulation_started === false && result.predicted_effect === null, 'A preview cannot contain an executed action or calculated outcome.');
    require(isObject(validation) && validation.valid === true && typeof validation.physics_changed === 'boolean'
      && validation.expected_revision === selection.revision_id && isTextList(validation.invalidated_run_ids)
      && isTextList(validation.warnings) && isTextList(result.limitations), 'Malformed edit validation.');
    require(result.decision === 'insufficient evidence', 'A preview cannot establish experimental acceptance.');
    require(result.before?.kind === 'existing_input', 'The preview must identify the existing input.');
    const before = presentBefore(result.before, result.binding, edit);
    return {ok: true, state: 'approval_required', title: validation.physics_changed ? 'Review proposed revision' : 'No electrical change',
      binding: clone(result.binding), contextId: result.binding.context_id, previewId: result.preview_id,
      physicsChanged: validation.physics_changed, invalidatedRunIds: clone(validation.invalidated_run_ids),
      before, proposed: clone(result.proposed_edit), proposedText: JSON.stringify(result.proposed_edit, null, 2),
      warnings: [...new Set(['This preview has not changed the project or run a simulation.',
        'Previous outputs are preserved. Listed owned runs become outdated only if this revision is applied.',
        'Predicted effects are not calculated. A later explicit simulation is required.',
        ...validation.warnings, ...result.limitations])],
      decision: result.decision, applied: false, simulationStarted: false, predictedEffect: null};
  } catch (error) { return unavailable('malformed', 'Preview unavailable', error.message, 'malformed_response'); }
}
