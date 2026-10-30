"""Independent library and closed-form electrical and heat checks on synthetic cells.

Run in an isolated environment with the pinned PyBaMM version. This script never
opens experimental observations and never uses a PyBaMM default battery model
as a source of cell data. The three implementations share declared parameters,
not interpolation, state propagation or summary code.
"""
from copy import deepcopy
import argparse
from datetime import datetime, timezone
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import sys

import numpy as np
import pybamm

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from voltforge.studio.network import settings_default, simulate, template


def synthetic_record(p, nrc):
    z = [.1, 1.]
    resistances = p['rc_resistance_ohm'][:nrc]
    times = p['rc_time_constant_s'][:nrc]
    return dict(kind='temperature_dependent_ecm/1', key='synthetic_reference',
                name='Synthetic numerical reference', family='Synthetic verification',
                origin='user', capacity_Ah=p['capacity_Ah'], nrc=nrc,
                soc=z, temperature_C=[15., 35.],
                operating_limits=dict(voltage_V=[2., 4.8], max_charge_A=10., max_discharge_A=10.),
                ocv_V=[[p['ocv_intercept_V'] + p['ocv_soc_slope_V'] * x for x in z]] * 2,
                r0_ohm=[[p['r0_ohm']] * 2] * 2,
                r_ohm=[[resistances] * 2] * 2, tau_s=[[times] * 2] * 2)


def branch_initial(p, nrc, total):
    r = np.asarray(p['rc_resistance_ohm'][:nrc], float)
    return total * r / r.sum() if nrc else np.empty(0)


def exact_response(p, nrc, current, total, time):
    # Independent continuous-time solution. No production lookup or RC helper.
    soc = p['initial_soc'] - current * time / (3600 * p['capacity_Ah'])
    r = np.asarray(p['rc_resistance_ohm'][:nrc], float)
    tau = np.asarray(p['rc_time_constant_s'][:nrc], float)
    vp = current * r + (branch_initial(p, nrc, total) - current * r) * np.exp(-time[:, None] / tau)
    voltage = p['ocv_intercept_V'] + p['ocv_soc_slope_V'] * soc - current * p['r0_ohm'] - vp.sum(axis=1)
    # Heat energy by integrating I*v in closed form for each branch, plus R0 loss.
    d = branch_initial(p, nrc, total) - current * r
    work = current * np.sum(current * r * time[:, None] + d * tau * -np.expm1(-time[:, None] / tau), axis=1)
    return voltage, soc, current**2 * p['r0_ohm'] * time + work


def library_response(p, nrc, current, total, time):
    model = pybamm.equivalent_circuit.Thevenin(options={'number of rc elements': nrc})
    params = model.default_parameter_values.copy()
    values = {
        'Initial SoC': p['initial_soc'], 'Initial temperature [K]': p['temperature_C'] + 273.15,
        'Ambient temperature [K]': p['temperature_C'] + 273.15,
        'Cell capacity [A.h]': p['capacity_Ah'], 'Nominal cell capacity [A.h]': p['capacity_Ah'],
        'Current function [A]': current, 'Upper voltage cut-off [V]': 4.8, 'Lower voltage cut-off [V]': 2.,
        'Open-circuit voltage [V]': lambda soc: p['ocv_intercept_V'] + p['ocv_soc_slope_V'] * soc,
        'R0 [Ohm]': p['r0_ohm'], 'Entropic change [V/K]': 0.,
    }
    # PyBaMM's overpotential uses the opposite sign to Studio's voltage drop.
    for i, initial in enumerate(branch_initial(p, nrc, total)):
        r = p['rc_resistance_ohm'][i]
        values.update({f'Element-{i+1} initial overpotential [V]': -float(initial),
                       f'R{i+1} [Ohm]': r, f'C{i+1} [F]': p['rc_time_constant_s'][i] / r})
    params.update(values, check_already_exists=False)
    solver = pybamm.CasadiSolver(mode='safe', **p['solver'])
    # Sample densely: PyBaMM interpolates linearly between requested times, which
    # would otherwise add quadrature error to the heat integral below.
    dense = np.linspace(0, p['duration_s'], 20*(len(time)-1)+1)
    solution = pybamm.Simulation(model, parameter_values=params, solver=solver).solve(t_eval=dense)
    if solution.termination != 'final time':
        raise ValueError('PyBaMM stopped before the reference horizon: ' + solution.termination)
    # PyBaMM's own heat variable. Its sign convention is handled by the library,
    # so a sign or formula mismatch fails this comparison.
    rate = np.asarray(solution['Irreversible heat generation [W]'](dense))
    energy = np.interp(time, dense, np.r_[0, np.cumsum((rate[1:]+rate[:-1])/2*np.diff(dense))])
    return np.asarray(solution['Voltage [V]'](time)), np.asarray(solution['SoC'](time)), energy


def studio_response(p, nrc, current, total, time):
    graph = template('parallel', 1)
    graph['cells'][0].update(model='synthetic_reference', charge_pct=100*p['initial_soc'],
                             temperature_C=p['temperature_C'], polarization_V=total)
    settings = settings_default()
    settings.update(ambient_C=p['temperature_C'], dt_s=p['step_s'],
                    profile=[dict(start_s=0., end_s=p['duration_s'], current_A=current)])
    result = simulate(graph, settings, {'synthetic_reference': synthetic_record(p, nrc)})
    if result.status != 'completed':
        raise ValueError('Studio stopped before the reference horizon: ' + str(result.stop))
    actual_time = np.array([r['time_s'] for r in result.rows])
    if actual_time.shape != time.shape or not np.allclose(actual_time, time, atol=1e-12, rtol=0):
        raise ValueError('Reference sample clocks differ.')
    return (np.array([r['voltage_V'] for r in result.rows]), np.array([r['charge_pct'][0]/100 for r in result.rows]),
            np.array([3600*r['loss_energy_Wh'] for r in result.rows]))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--protocol', type=Path, default=ROOT/'configs/numerical_reference_v2.json')
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    raw = args.protocol.read_bytes(); p = json.loads(raw)
    if version('pybamm') != p['library']['version']:
        raise SystemExit('Use the pinned PyBaMM version before comparing results.')
    out = args.out.resolve()
    if out.exists() and any(out.iterdir()):
        raise SystemExit('Choose a new empty output directory; previous results are retained.')
    out.mkdir(parents=True, exist_ok=True)
    (out/'protocol.json').write_bytes(raw)
    time = np.linspace(0, p['duration_s'], int(round(p['duration_s']/p['step_s']))+1)
    records = []
    for nrc in p['rc_orders']:
        for current in p['current_A']:
            for total in p['initial_total_polarization_V'] if nrc else [0.]:
                row = dict(rc_order=nrc, current_A=current, initial_polarization_V=total, samples=len(time))
                try:
                    independent = exact_response(p, nrc, current, total, time)
                    library = library_response(p, nrc, current, total, time)
                    studio = studio_response(p, nrc, current, total, time)
                    for name, a, b in [('studio_to_library', studio, library),
                                       ('studio_to_analytic', studio, independent),
                                       ('library_to_analytic', library, independent)]:
                        row[name] = dict(maximum_voltage_difference_V=float(np.max(abs(a[0]-b[0]))),
                                         maximum_soc_difference=float(np.max(abs(a[1]-b[1]))),
                                         maximum_heat_energy_difference_J=float(np.max(abs(a[2]-b[2]))))
                    row['passed'] = all(row[key][metric] <= bound for key in
                                        ('studio_to_library', 'studio_to_analytic', 'library_to_analytic')
                                        for metric, bound in p['acceptance'].items())
                except Exception as exc:
                    row.update(passed=False, error=type(exc).__name__+': '+str(exc))
                records.append(row)
                print(json.dumps(row, allow_nan=False), flush=True)
    summary = dict(version='voltforge.numerical-reference-results/1', created_utc=datetime.now(timezone.utc).isoformat(),
                   scope=p['scope'], protocol_sha256=hashlib.sha256(raw).hexdigest(),
                   driver_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                   runtime={k: version(k) for k in ('pybamm', 'numpy', 'scipy', 'casadi', 'pandas', 'matplotlib')},
                   passed=all(r['passed'] for r in records), checks=records,
                   experimental_observations_accessed=False, heat_comparison_performed=True, temperature_comparison_performed=False,
                   limitations=[p['temperature_scope'], p['heat_scope']])
    (out/'verification.json').write_text(json.dumps(summary, indent=2, allow_nan=False)+'\n')
    print(json.dumps(dict(passed=summary['passed'], cases=len(records), output=str(out)), indent=2))
    if not summary['passed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
