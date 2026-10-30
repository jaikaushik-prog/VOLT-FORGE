"""Run the frozen V4 design study in parallel and keep one compact record per case."""
from concurrent.futures import ProcessPoolExecutor
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
import argparse
import hashlib
import json
import sys
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from voltforge.models.cell_catalogue import load_additional
from voltforge.studio.conductors import apply, copper_reference
from voltforge.studio.loads import battery_current
from voltforge.studio.network import digest, settings_default, simulate, template
from voltforge.studio.parts import estimate, load_prices
from voltforge.studio.store import Studio

P = json.loads((ROOT/'configs/round1_design_study_v2.json').read_text())
BANK = load_additional(ROOT)
KEY = P['cell_model']


def conductor(dimensions):
    c = copper_reference(); c.update(dimensions); c['assumption_source'] = 'Declared in configs/round1_design_study_v2.json'
    return c


def build(case):
    n, option = case['count'], case['option']; common = P['common']; s = case.get('scenario', {})
    g = template('parallel', n, f'{n} cells, {option}'); bank = {KEY: BANK[KEY]}
    for c in g['cells']: c.update(model=KEY, charge_pct=common['charge_pct']+s.get('charge_delta_pp', 0.), temperature_C=common['temperature_C'])
    for w in g['connections']:
        c = conductor(P['link_dimensions'])
        if option in ('thicker', 'combined'): c['thickness_mm'] *= 2
        c['contact_mohm'] *= s.get('contact_factor', 1.)*case.get('contact', 1.)
        apply(w, c)
    g['output_leads'] = {pole: conductor(P['output_route']) for pole in ('positive', 'negative')}
    if option in ('opposite', 'combined') and n > 1:
        g['output']['negative'] = f'cell{n}:n'
        g['output_leads']['negative']['length_mm'] += P['opposite_return_extra_mm_per_link']*(n-1)
    th = g['thermal']; th['wire_heat_fraction'] = s.get('wire_heat_fraction', th['wire_heat_fraction'])
    defaults = BANK[KEY]['thermal_defaults']
    values = {}
    if 'cooling_W_K' in s: values['ambient_conductance_W_K'] = s['cooling_W_K']
    if 'cooling_factor' in s: values['ambient_conductance_W_K'] = defaults['ambient_conductance_W_K']*s['cooling_factor']
    if 'heat_capacity_J_K' in s: values['heat_capacity_J_K'] = s['heat_capacity_J_K']
    if 'heat_capacity_factor' in s: values['heat_capacity_J_K'] = defaults['heat_capacity_J_K']*s['heat_capacity_factor']
    if values: th['cell_parameters'] = {c['id']: dict(values) for c in g['cells']}
    for index, change in (case.get('cells') or {}).items():
        cell = g['cells'][int(index)]; model = deepcopy(BANK[KEY])  # Its inner key keeps the sourced LG limits.
        model['capacity_Ah'] *= change.get('capacity_factor', 1.)
        for table in ('r0_ohm', 'r_ohm'):
            model[table] = (np.asarray(model[table])*change.get('resistance_factor', 1.)).tolist()
        model['ocv_V'] = (np.asarray(model['ocv_V'])+change.get('ocv_offset_V', 0.)).tolist()
        name = f'clone{index}'; bank[name] = model; cell['model'] = name
        cell['charge_pct'] += change.get('charge_delta_pp', 0.); cell['polarization_V'] = change.get('polarization_V', 0.)
    settings = settings_default(); mission = P['missions'][case['mission']]
    current = mission.get('current_A') or battery_current(mission['power_W'], case.get('efficiency', mission['converter_efficiency']), common['voltage_floor_V'])
    settings.update(ambient_C=common['ambient_C']+s.get('ambient_delta_C', 0.), dt_s=case.get('dt', common['dt_s']),
                    profile=[dict(start_s=0., end_s=common['duration_s'], current_A=float(current))])
    settings['limits']['min_voltage_V'] = common['voltage_floor_V']
    return g, settings, bank


def run_case(case):
    record = {k: case[k] for k in ('id', 'tier', 'count', 'option', 'mission', 'label')}
    try:
        g, s, bank = build(case); result = simulate(g, s, bank)
    except ValueError as exc:
        return dict(record, passed=False, outcome='refused', reason=str(exc)[:200])
    m = result.summary['metrics']; v = result.summary['verification']
    served = result.status == 'completed' and result.summary['assessment']['requested_demand_met']
    floor = m['minimum_voltage_V'] >= P['common']['voltage_floor_V']
    thermal = result.summary['thermal_available'] and v.get('first_law_closed') is True
    return dict(record, passed=bool(served and floor and thermal), outcome=result.status, reason=(result.stop or {}).get('reason'), stop_time_s=(result.stop or {}).get('time_s'),
                min_voltage_V=m['minimum_voltage_V'], peak_cell_current_A=m['peak_cell_current_A'], busiest_cell=m['busiest_cell'], peak_temperature_C=m['peak_temperature_C'],
                temperature_spread_C=m['maximum_temperature_spread_C'], delivered_Wh=m['delivered_energy_Wh'], first_law_closed=v.get('first_law_closed'),
                warnings=[w['rule'] for w in result.summary['design_warnings']])


def enumerate_cases():
    cases = []
    def add(tier, count, option, mission, label, **extra):
        cases.append(dict(id=len(cases), tier=tier, count=count, option=option, mission=mission, label=label, **extra))
    def options(count): return ['baseline'] if count == 1 else list(P['options'])
    mismatch = P['position_mismatch']
    for count in P['counts']:
        for option in options(count):
            for mission in P['missions']:
                add('nominal', count, option, mission, 'nominal')
                add('half_step', count, option, mission, 'half step', dt=P['common']['half_step_dt_s'])
                for name, scenario in P['shared_sensitivities'].items():
                    add('shared_sensitivity', count, option, mission, name, scenario=scenario)
                if count > 1:
                    for position in range(count):
                        for key, values in (('capacity_factor', mismatch['capacity_factor']), ('resistance_factor', mismatch['resistance_factor']),
                                            ('ocv_offset_V', mismatch['ocv_offset_V']), ('charge_delta_pp', mismatch['charge_delta_pp'])):
                            for value in values:
                                add('position_mismatch', count, option, mission, f'cell {position+1} {key} {value:g}', cells={str(position): {key: value}})
                        add('position_mismatch', count, option, mission, f'cell {position+1} combined weak', cells={str(position): mismatch['combined_weak']})
            for efficiency in P['converter_efficiency_check']:
                add('converter_efficiency', count, option, 'pi', f'efficiency {efficiency:g}', efficiency=efficiency)
    # Same seed and draw order as the audit, so the four-cell set is its 247 cases.
    rng = np.random.default_rng(P['combined_samples']['seed'])
    strong = dict(resistance_factor=.9, ocv_offset_V=.025, charge_delta_pp=2.); weak = dict(resistance_factor=1.1, ocv_offset_V=-.025, charge_delta_pp=-2.)
    def draw(count):
        return {str(i): dict(capacity_factor=float(rng.uniform(.95, 1.05)), resistance_factor=float(rng.uniform(.9, 1.1)), ocv_offset_V=float(rng.uniform(-.025, .025)),
                             charge_delta_pp=float(rng.uniform(-2, 2))) for i in range(count)}
    def samples(count, corners, randoms):
        rows = list(corners.items())
        rows += [(f'random{i}', draw(count), float(rng.uniform(1., 2.))) for i in range(randoms)]
        return [(r[0], r[1], r[2] if len(r) > 2 else 1.) for r in rows]
    four = dict(nominal={}, strong_4_weak_1={'3': strong, '0': weak}, strong_1_weak_4={'0': strong, '3': weak}, strong_2={'1': strong}, strong_3={'2': strong},
                strong_2_3={'1': strong, '2': strong}, weak_2_3={'1': weak, '2': weak})
    sets = {4: samples(4, four, P['combined_samples']['four_cell']['random'])}
    for count in (2, 3):
        last = str(count-1)
        sets[count] = samples(count, {'strong_1_weak_last': {'0': strong, last: weak}, 'strong_last_weak_1': {last: strong, '0': weak}}, P['combined_samples']['two_and_three_cell']['random'])
    for count, rows in sets.items():
        for label, cells, contact in rows:
            for option in P['options']:
                for mission in P['missions']:
                    add('combined_sample', count, option, mission, label, cells=cells, contact=contact)
    return cases


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, default=ROOT/'reports/design_study_v2/run1')
    parser.add_argument('--pilot', type=int, default=0, help='Run this many evenly spaced cases to estimate the time')
    parser.add_argument('--workers', type=int, default=7)
    args = parser.parse_args()
    cases = enumerate_cases(); total = len(cases)
    if args.pilot: cases = cases[::max(1, total//args.pilot)]
    args.out.mkdir(parents=True, exist_ok=True)
    start = time.time(); done = 0
    with open(args.out/'cases.jsonl', 'w') as out, ProcessPoolExecutor(args.workers) as pool:
        for row in pool.map(run_case, cases, chunksize=8):
            out.write(json.dumps(row, allow_nan=False)+'\n'); done += 1
            if done % 250 == 0: print(f'{done}/{len(cases)} in {time.time()-start:.0f} s', flush=True)
    raw = (ROOT/'configs/round1_design_study_v2.json').read_bytes()
    manifest = dict(version='voltforge.design-study-run/2', created_utc=datetime.now(timezone.utc).isoformat(), cases_planned=total, cases_run=len(cases), pilot=bool(args.pilot),
                    seconds=time.time()-start, protocol_sha256=hashlib.sha256(raw).hexdigest(), software_hash=Studio._software_hash(), model_hash=digest({KEY: BANK[KEY]}),
                    parts=estimate(build(dict(count=1, option='baseline', mission='pi'))[0], BANK, load_prices(ROOT))['checked'], experimental_validation=False)
    (args.out/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    print(json.dumps({k: manifest[k] for k in ('cases_planned', 'cases_run', 'seconds', 'software_hash')}))


if __name__ == '__main__':
    main()
