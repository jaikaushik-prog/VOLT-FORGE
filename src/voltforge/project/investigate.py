"""Failure Investigator v1: deterministic finite search over permitted perturbations of one design revision. Every case uses the same electrical engine, thermal model and engineering screen as a normal run. Cases are simulated in memory and saved as one immutable record; reproduce a case by opening it as a variant and running it. No optimizer, no cross-requirement ranking, no repair claim."""
import itertools
import math

import numpy as np

from voltforge.models import thermal_v1
from voltforge.simulation import workflow as w
from . import engineering
from . import schema as s
from .service import digest, now, read, software, valid_id, write_once

MAX_CASES = 200
MAX_VALUES = 50  # per list; with the six rail segments the requested grid stays under 50 * 50 * (1 + 6 * 50) = 752,500 cases
CLASSIFICATION = 'simulated finite search; worst case only within the evaluated set; no repair claim'
METRIC_LABEL = 'exploration order by metric value; not a requirement verdict'
RANKED_METRICS = ('peak_branch_current_A', 'current_imbalance_pct', 'peak_cell_temperature_C')
VIOLATION = 'simulated violation of configured limit'
PLAN_KEYS = ('rail_segments', 'added_resistance_ohm', 'load_current_A', 'ambient_C', 'max_cases')


def _clean(value):
    """Plain JSON data only: numpy scalars become Python numbers and non-finite floats become null."""
    if isinstance(value, dict):
        return {str(k): _clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_clean(v) for v in value]
    if isinstance(value, np.ndarray):
        return _clean(value.tolist())
    if isinstance(value, np.generic):
        value = value.item()
    return None if isinstance(value, float) and not math.isfinite(value) else value


def _numbers(plan, key, accepts, rule):
    values = plan[key]
    message = f'{key} must be a list of finite numbers {rule}'
    s.require(isinstance(values, list), message)
    s.require(len(values) <= MAX_VALUES, f'{key} may list at most {MAX_VALUES} values (got {len(values)})')  # before any per-item work
    s.require(all(s.finite(x) and accepts(x) for x in values), message)
    return [float(x) for x in values]


def validate_plan(plan, design):
    s.require(isinstance(plan, dict), 'Investigation plan must be an object')
    unknown = sorted(str(k) for k in plan if k not in PLAN_KEYS)
    s.require(not unknown, 'Unknown plan field(s): ' + ', '.join(unknown))
    missing = [k for k in PLAN_KEYS if k not in plan]
    s.require(not missing, 'Missing plan field(s): ' + ', '.join(missing))
    segments = plan['rail_segments']
    s.require(isinstance(segments, list) and all(isinstance(x, str) and x in design['connections'] for x in segments),
        'rail_segments must list connection ids that exist in the design')
    s.require(len(set(segments)) == len(segments), 'rail_segments must be unique')
    added = _numbers(plan, 'added_resistance_ohm', lambda x: x > 0, 'greater than 0')
    s.require(len(set(added)) == len(added), 'added_resistance_ohm values must be unique')
    loads = _numbers(plan, 'load_current_A', lambda x: x > 0, 'greater than 0 (or an empty list)')
    ambients = _numbers(plan, 'ambient_C', lambda x: -40 <= x <= 80, 'between -40 and 80 (or an empty list)')
    budget = plan['max_cases']
    s.require(type(budget) is int and 1 <= budget <= MAX_CASES, f'max_cases must be an integer from 1 to {MAX_CASES}')
    return dict(rail_segments=list(segments), added_resistance_ohm=added, load_current_A=loads, ambient_C=ambients, max_cases=budget)


def requested_cases(plan):
    """Size of the full grid from the dimension sizes alone; nothing is built. An empty load or ambient list keeps the design value."""
    return (max(len(plan['load_current_A']), 1) * max(len(plan['ambient_C']), 1)
        * (1 + len(plan['rail_segments']) * len(plan['added_resistance_ohm'])))


def _grid(plan):
    """Yield (load, ambient, segment, added) in the fixed exploration order; None keeps the design value."""
    for load in (plan['load_current_A'] or [None]):
        for ambient in (plan['ambient_C'] or [None]):
            yield load, ambient, None, None  # contact baseline: no degradation, same load and ambient
            for segment in plan['rail_segments']:
                for added in plan['added_resistance_ohm']:
                    yield load, ambient, segment, added


def _case(design, horizon, number, load, ambient, segment, added):
    case_id = f'case_{number:04d}'
    edit = lambda target, ident, prop, value, unit: dict(target=target, id=ident, property=prop, value=value, unit=unit,
        source=f'Failure investigation case {case_id}', classification='assumed')
    edits = []
    if segment is not None:
        edits.append(edit('connection', segment, 'resistance', design['connections'][segment]['resistance']['value'] + added, 'ohm'))
    if load is not None:
        edits.append(edit('scenario', 'module', 'load_profile', [{'start_s': 0.0, 'end_s': horizon, 'current_A': load}], 'A,s'))
    if ambient is not None:
        edits.append(edit('scenario', 'module', 'temperature',
            {**design['scenario']['temperature'], 'assumed_ambient_C': ambient, 'assumed_surface_C': [ambient]*4}, 'degC'))
    return dict(case_id=case_id, load_current_A=load, ambient_C=ambient, rail_segment=segment,
        added_resistance_ohm=0.0 if added is None else added, edits=edits)


def iter_cases(plan, design):
    """Lazily yield the grid's cases in exploration order; a case is built only when it is consumed."""
    horizon = design['scenario']['load_profile'][-1]['end_s']
    for number, point in enumerate(_grid(plan), 1):
        yield _case(design, horizon, number, *point)


def generate_cases(plan, design, limit=None):
    """The first `limit` cases of the grid (all of them when limit is None); only those cases are ever built."""
    return list(itertools.islice(iter_cases(plan, design), limit))


def evaluate_case(design, case, base, manifest, sensitivities, curves):
    try:
        d = design
        for e in case['edits']:
            d = s.edited(d, e, base, manifest)
        c = s.to_case(d, base, 'nominal', sensitivities)
        w.check_case(c)
        result = w.execute_case(c, curves)
        params, temperature = s.thermal_parameters(d), d['scenario']['temperature']
        tf = thermal_summary = thermal_error = None
        thermal_status = 'unavailable'  # electrical-only design or no electrical samples, as in Project.run
        if params and len(result.frame):
            try:  # as in Project.run, a thermal failure never discards the electrical result; it is recorded on its own
                tf = thermal_v1.simulate(result.frame, c['models'], params, temperature['assumed_surface_C'], temperature['assumed_ambient_C'])
                thermal_v1.validate_output(tf, result.frame)
                thermal_summary = thermal_v1.summarize(tf, params)
                thermal_status = 'completed'
            except Exception as exc:
                tf = thermal_summary = None
                thermal_status, thermal_error = 'failed', {'type': type(exc).__name__, 'message': str(exc)}
        screen = engineering.screen(result.frame, tf, d.get('engineering_requirements'), completed=result.status == 'completed')
        return _clean({**case, 'electrical_status': result.status, 'stop': result.stop,
            'thermal_status': thermal_status, 'thermal_error': thermal_error,
            'metrics': {name: m['value'] for name, m in screen['metrics'].items()},
            'requirements': {name: {'status': r['status'], 'margin': r.get('margin'), 'value': r.get('value'),
                'time_s': r.get('time_s'), 'component': r.get('component')} for name, r in screen['requirements'].items()},
            'peak_cell_temperature_C': thermal_summary and thermal_summary['peak_cell_temperature_C']})
    except Exception as exc:  # one failed case never stops the search; it is recorded as an error
        return {**case, 'electrical_status': 'error', 'error': {'type': type(exc).__name__, 'message': str(exc)},
            'stop': None, 'thermal_status': 'unavailable', 'thermal_error': None,
            'metrics': {}, 'requirements': {}, 'peak_cell_temperature_C': None}


def _number(value):
    return type(value) in (int, float) and math.isfinite(value)


def rank(cases):
    """Each requirement and each metric is ordered on its own; nothing is combined into one score."""
    by_requirement, by_metric = {}, {}
    for name in engineering.LIMITS:
        results = [(c['case_id'], (c.get('requirements') or {}).get(name) or {}) for c in cases]
        rows = [{'case_id': cid, 'margin': r['margin'], 'status': r['status']} for cid, r in results if _number(r.get('margin'))]
        by_requirement[name] = {'cases': sorted(rows, key=lambda row: (row['margin'], row['case_id'])),
            'violations': sum(1 for _, r in results if r.get('status') == VIOLATION)}
    for name in RANKED_METRICS:
        rows = [{'case_id': c['case_id'], 'value': (c.get('metrics') or {}).get(name)} for c in cases]
        by_metric[name] = {'label': METRIC_LABEL,
            'cases': sorted((row for row in rows if _number(row['value'])), key=lambda row: (-row['value'], row['case_id']))}
    return {'by_requirement': by_requirement, 'by_metric': by_metric}


def run(project, variant_id, expected_revision, plan):
    with project._writer() as state:
        rid, revision = project._expected(state, variant_id, expected_revision)
        base, manifest = project._inputs(state)
        design = revision['design']
        normalized = validate_plan(plan, design)
        requested = requested_cases(normalized)  # from the dimension sizes; the budget bounds construction, not just evaluation
        selected = generate_cases(normalized, design, limit=normalized['max_cases'])
        with np.load(project.path / 'assets/reference_sensitivity.npz', allow_pickle=False) as npz:
            curves = [(npz[c+'_soc'].copy(), npz[c+'_V'].copy()) for c in s.CELLS]
        sensitivities = read(project.path / 'assets/scenario_plan.json')['sensitivity_scenarios']
        evaluated = [evaluate_case(design, case, base, manifest, sensitivities, curves) for case in selected]
        inv_id = f'inv_{len(state.get("investigations", {}))+1:04d}'
        folder = project.path / 'investigations' / inv_id
        s.require(not folder.exists(), 'Investigation folder exists; inspect before retrying', 'conflict')
        record = dict(schema_version=1, investigation_id=inv_id, variant_id=variant_id, revision_id=rid, software_id=software()['id'],
            created_utc=now(), plan=normalized, classification=CLASSIFICATION, cases=evaluated, rankings=rank(evaluated),
            coverage=dict(requested=requested, evaluated=len(evaluated), skipped_by_budget=requested-len(evaluated),
                electrical_stopped=sum(1 for c in evaluated if c['electrical_status'] not in ('completed', 'error')),
                errors=sum(1 for c in evaluated if c['electrical_status'] == 'error'),
                thermal_failures=sum(1 for c in evaluated if c['thermal_status'] == 'failed')))
        write_once(folder / 'investigation.json', record)
        state.setdefault('investigations', {})[inv_id] = dict(variant_id=variant_id, revision_id=rid, sha256=digest(record))
        project._save(state)
    return record


def get(project, investigation_id):
    valid_id(investigation_id)
    entry = project._state().get('investigations', {}).get(investigation_id)
    s.require(entry is not None, 'Unknown investigation', 'not_found')
    try:
        record = read(project.path / 'investigations' / investigation_id / 'investigation.json')
    except (OSError, ValueError) as exc:
        raise s.RequestError('integrity_error', 'Investigation record is missing or unreadable') from exc
    s.require(digest(record) == entry['sha256'], 'Investigation record changed', 'integrity_error')
    return record


def open_case(project, investigation_id, case_id, variant_id, name):
    record = get(project, investigation_id)
    case = next((c for c in record['cases'] if c['case_id'] == case_id), None)
    s.require(case is not None, 'Unknown case', 'not_found')
    valid_id(variant_id)
    s.require(isinstance(name, str) and bool(name.strip()), 'Variant name required')
    with project._writer() as state:
        s.require(variant_id.casefold() not in {k.casefold() for k in state['variants']}, 'Variant already exists', 'conflict')
        state['variants'][variant_id] = dict(name=name, revision_id=record['revision_id'], run_ids=[], inherited_run_ids=[])
        project._save(state)
    for edit in case['edits']:
        project.apply_edit(variant_id, edit, project.inspect(variant_id)['revision_id'])
    return project.inspect(variant_id)
