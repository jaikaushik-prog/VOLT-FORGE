// Presentation helpers only. Physical outcomes always come from the Python backend.
export function escapeHTML(value) {
  return String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}
export function chooseRun(info, scenario = 'nominal', preferred = '') {
  if (preferred && info.runs.some(r => r.run_id === preferred)) return preferred;
  return (info.current_runs_by_scenario[scenario] || []).at(-1) || '';
}
export function viewLabel(run) {
  return `${run.run_id} · ${run.owner_variant_id} · ${run.scenario_id} · ${run.execution_status} · ${run.freshness}`;
}
export function bounds(values) {
  const finite = values.filter(Number.isFinite);
  if (!finite.length) return [0, 1];
  let lo = Infinity, hi = -Infinity;
  for (const value of finite) {lo = Math.min(lo, value); hi = Math.max(hi, value);}
  const pad = (hi - lo || Math.max(Math.abs(hi) * .05, .01)) * .12;
  return [lo - pad, hi + pad];
}
export class RequestEpoch {
  constructor() { this.value = 0; }
  begin() { return ++this.value; }
  current(value) { return value === this.value; }
}
export function number(value, digits = 3) { return typeof value === 'number' && Number.isFinite(value) ? value.toFixed(digits) : '—'; }
export function finiteInput(value) {
  if (typeof value !== 'string' || !value.trim() || !Number.isFinite(Number(value))) throw new Error('Enter a finite number.');
  return Number(value);
}
export function failureMessage(error) {
  if (!error) return '';
  if (typeof error === 'string') return error;
  const time = Number.isFinite(error.last_valid_time_s) ? `Stopped at ${number(error.last_valid_time_s,2)} s. ` : '';
  return time + (error.reason || error.message || 'Inspect the saved failure details in Evidence.');
}
