"""Run the frozen extra checks on the recommended design and report every result.

These are checks and never fits: nothing here feeds back into a model.
"""
from copy import deepcopy
from pathlib import Path
import csv
import hashlib
import json
import subprocess
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
from compare_measured import BANK, KEY, module_segment, run, starting_charge
from run_design_study_v2 import build, simulate

RAW = (ROOT/'configs/engineering_checks_v1.json').read_bytes()
C = json.loads(RAW)
COMPARE = json.loads((ROOT/'configs/measured_comparison_v1.json').read_text())
MEASURED = json.loads((ROOT/'reports/measured_comparison_v1/final/result.json').read_text())
STUDY = json.loads((ROOT/'reports/design_study_v2/run1/summary.json').read_text())
DESIGN = next(d for d in STUDY['designs'] if d['count'] == C['design']['count'] and d['option'] == C['design']['option'])
OUT = ROOT/'reports/engineering_checks_v1'


def unique_rows(result):
    rows = result.rows; t = np.array([r['time_s'] for r in rows]); keep = np.r_[True, np.diff(t) > 0]
    return t[keep], np.array([r['cell_current_A'] for r in rows])[keep], np.array([r['voltage_V'] for r in rows])[keep]


def current_sharing():
    bands = C['current_sharing']['bands']; out = []
    for record in C['current_sharing']['records']:
        c = next(x for x in COMPARE['comparisons'] if x['id'] == record)
        seg = module_segment(ROOT/c['file'], c['discharge_step'])
        charge = starting_charge(seg['rest_voltage'], float(np.mean(seg['rest_temperature'])))
        result = run(seg['temperature'][0].tolist(), charge, seg['cycler_current'], float(seg['time'][-1]), seg['ambient'], c['link_resistance_mohm'])
        st, si, _ = unique_rows(result)
        mask = (seg['time'] <= st[-1]) & (np.abs(seg['branch'].sum(axis=1)) > 1.)
        t, branch = seg['time'][mask], seg['branch'][mask]
        simulated = np.column_stack([np.interp(t, st, si[:, i]) for i in range(si.shape[1])])
        ms = 100*branch/branch.sum(axis=1, keepdims=True); ss = 100*simulated/simulated.sum(axis=1, keepdims=True)
        error = ss-ms
        row = dict(record=record, samples=int(len(t)), mean_absolute_share_error_points=float(np.abs(error).mean()),
                   worst_share_error_points=float(np.abs(error).max()), busiest_cell_match_fraction=float(np.mean(ms.argmax(axis=1) == ss.argmax(axis=1))),
                   measured_mean_share_pct=ms.mean(axis=0).tolist(), simulated_mean_share_pct=ss.mean(axis=0).tolist(),
                   measured_spread_points=float((ms.max(axis=1)-ms.min(axis=1)).mean()), simulated_spread_points=float((ss.max(axis=1)-ss.min(axis=1)).mean()),
                   measured_peak_cell_A=float(np.abs(branch).max()), simulated_peak_cell_A=float(np.abs(simulated).max()))
        row['within_band'] = bool(row['mean_absolute_share_error_points'] <= bands['mean_absolute_share_error_points'] and row['busiest_cell_match_fraction'] >= bands['busiest_cell_match_fraction'])
        out.append(row)
    return out


def voltage_window(name, ah):
    case = next(c for c in MEASURED['cases'] if c['case'] == name)
    rows = np.array([[float(x) for x in r] for r in list(csv.reader(open(ROOT/f'reports/measured_comparison_v1/final/{name}.csv')))[1:]])
    charge = case['starting_charge_pct']-100*case['current_A']*rows[:, 0]/3600/ah
    low, high = C['error_budget']['voltage']['charge_window_pct']; mask = (charge >= low) & (charge <= high)
    error = rows[mask, 2]-rows[mask, 1]
    return dict(case=name, samples=int(mask.sum()), mean_error_V=float(error.mean()), largest_optimistic_error_V=float(error.max()), largest_abs_error_V=float(np.abs(error).max()))


def error_budget():
    margin = DESIGN['worst_required']['lowest_voltage_V']-STUDY_FLOOR
    primary = voltage_window('test28_exact_m50t_module', 20.)
    others = [voltage_window('test28_exact_m50t_module__hall_sum_current', 20.)]+[voltage_window(f'warwick_lg_m50_single_cell__LGM50_cell0{i}__5A', 5.) for i in (2, 3, 4)]
    ratios = [c['peak_rise_measured_K']/c['peak_rise_simulated_K'] for c in MEASURED['cases'] if 'peak_rise_simulated_K' in c]
    rise = DESIGN['worst_required']['highest_temperature_C']-23.
    scaled = 23.+rise*max(ratios); limit = C['error_budget']['temperature']['limit_C']
    return dict(voltage=dict(margin_V=margin, primary=primary, others=others, passed=bool(primary['largest_abs_error_V'] < margin)),
                temperature=dict(worst_rise_K=rise, largest_measured_over_simulated=max(ratios), scaled_C=scaled, limit_C=limit, passed=bool(scaled < limit)))


STUDY_FLOOR = 3.3


def metrics(result):
    m = result.summary['metrics']; rows = result.rows
    return dict(status=result.status, peak_cell_current_A=m['peak_cell_current_A'], minimum_voltage_V=m['minimum_voltage_V'], peak_temperature_C=m['peak_temperature_C'],
                final_lowest_charge_pct=float(min(rows[-1]['charge_pct'])), lowest_charge_pct=float(min(min(r['charge_pct']) for r in rows)))


def design_case(**extra):
    return dict(C['design'], **extra)


def constant_power():
    g, s, bank = build(design_case()); fixed = simulate(g, s, bank); current = metrics(fixed)
    p = json.loads((ROOT/'configs/round1_design_study_v2.json').read_text())['missions']['pi']
    edges = np.linspace(0, s['profile'][-1]['end_s'], 49); result = fixed; rounds = []
    for _ in range(3):
        t = np.array([r['time_s'] for r in result.rows]); v = np.array([r['voltage_V'] for r in result.rows])
        mid = (edges[:-1]+edges[1:])/2; load = p['power_W']/(p['converter_efficiency']*np.interp(mid, t, v))
        s2 = deepcopy(s); s2['profile'] = [dict(start_s=float(a), end_s=float(b), current_A=float(i)) for a, b, i in zip(edges[:-1], edges[1:], load)]
        result = simulate(g, s2, bank); rounds.append(dict(metrics(result), peak_load_A=float(load.max()), lowest_load_A=float(load.min())))
    power = rounds[-1]
    harder = current['peak_cell_current_A'] >= power['peak_cell_current_A'] and current['minimum_voltage_V'] <= power['minimum_voltage_V'] and current['final_lowest_charge_pct'] <= power['final_lowest_charge_pct']
    return dict(constant_current=current, constant_power=power, rounds=rounds, passed=bool(harder))


def entropy_variants():
    model = BANK[KEY]; temperatures = np.array(model['temperature_C']); ocv = np.array(model['ocv_V']); soc = np.array(model['soc'])
    if ocv.shape[0] != len(soc): ocv = ocv.T
    low, high = np.searchsorted(temperatures, 25.), np.searchsorted(temperatures, 35.)
    slope = (ocv[:, high]-ocv[:, low])/(temperatures[high]-temperatures[low])
    deployed = model['entropy']
    return dict(as_deployed=deployed, no_reversible_heat=dict(deployed, dOCV_dT_V_K=(0*np.array(deployed['dOCV_dT_V_K'])).tolist()),
                slope_from_ocv_table=dict(soc=soc.tolist(), dOCV_dT_V_K=slope.tolist()), slope_from_ocv_table_reversed=dict(soc=soc.tolist(), dOCV_dT_V_K=(-slope).tolist()))


def entropy_sensitivity():
    rows = []; limit = C['error_budget']['temperature']['limit_C']
    for name, table in entropy_variants().items():
        for scenario, change in (('normal', {}), ('halved_cooling_and_heat_capacity', dict(cooling_factor=.5, heat_capacity_factor=.5))):
            g, s, bank = build(design_case(scenario=change)); bank[KEY] = dict(bank[KEY], entropy=table)
            m = metrics(simulate(g, s, bank)); rows.append(dict(variant=name, scenario=scenario, peak_temperature_C=m['peak_temperature_C'], status=m['status']))
    return dict(rows=rows, passed=bool(all(r['peak_temperature_C'] < limit for r in rows)))


def low_charge():
    weak = json.loads((ROOT/'configs/round1_design_study_v2.json').read_text())['position_mismatch']['combined_weak']; rows = []
    for label, cells in (('normal', None), ('weak cell 1', {'0': weak}), ('weak cell 2', {'1': weak})):
        g, s, bank = build(design_case(cells=cells)); rows.append(dict(case=label, lowest_charge_pct=metrics(simulate(g, s, bank))['lowest_charge_pct']))
    return dict(rows=rows, threshold_pct=C['low_charge']['threshold_pct'], passed=bool(all(r['lowest_charge_pct'] > C['low_charge']['threshold_pct'] for r in rows)))


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    commit = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    result = dict(version='voltforge.engineering-check-results/1', protocol_sha256=hashlib.sha256(RAW).hexdigest(), source_commit=commit, experimental_validation=False,
                  current_sharing=current_sharing(), error_budget=error_budget(), constant_power=constant_power(), entropy_sensitivity=entropy_sensitivity(), low_charge=low_charge())
    (OUT/'result.json').write_text(json.dumps(result, indent=2, allow_nan=False)+'\n')
    print(json.dumps(result, indent=1)[:6000])


if __name__ == '__main__': main()
