import {finiteInput, number as n} from './state.mjs';

export function loadProfile(intervals) {
  if (!Array.isArray(intervals) || !intervals.length) throw new Error('Add at least one load interval.');
  let start = 0;
  return intervals.map(({duration, current}, index) => {
    const seconds = finiteInput(duration), amps = finiteInput(current);
    if (seconds <= 0) throw new Error(`Interval ${index + 1}: duration must be greater than zero.`);
    const end = start + seconds;
    if (!Number.isFinite(end) || end <= start) throw new Error(`Interval ${index + 1}: choose a supported duration.`);
    const interval = {start_s:start, end_s:end, current_A:amps};
    start = end;
    return interval;
  });
}

export function durationLabel(seconds) {
  if (!Number.isFinite(seconds)) return '—';
  return seconds >= 60 && seconds % 60 === 0 ? `${n(seconds / 60, 0)} min` : `${n(seconds, seconds % 1 ? 2 : 0)} s`;
}

export function componentLabel(id) {
  if (id === 'module') return 'Module';
  const cell = /^cell_(\d+)$/.exec(id);
  if (cell) return `Cell ${cell[1]}`;
  const rail = /^rail_([pn])_(\d+)$/.exec(id);
  return rail ? `${rail[1] === 'p' ? 'Positive' : 'Negative'} connection ${rail[2]}` : id;
}

export function resultLabel(run) {
  const scenario = run.scenario_id === 'nominal' ? 'Nominal' : 'Sensitivity';
  const condition = run.execution_status === 'failed' ? 'Partial' : run.freshness === 'outdated' ? 'Outdated' : 'Current';
  return `${run.run_id} · ${run.owner_variant_id ?? run.variant_id} · ${condition} · ${scenario}`;
}

export function limitLabel(status) {
  return new Map([
    ['simulated violation of configured limit', 'Limit exceeded'],
    ['no sampled exceedance; insufficient evidence for a pass', 'No sampled exceedance'],
    ['insufficient simulation', 'Partial simulation'],
    ['not evaluable', 'Not evaluable'],
    ['requirement not configured', 'Not configured'],
  ]).get(status) ?? status ?? 'Unavailable';
}
