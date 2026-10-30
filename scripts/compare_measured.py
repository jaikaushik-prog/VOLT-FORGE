"""Compare V4 simulations with published measurements under the frozen protocol.

This is a check and never a fit: nothing here feeds back into a model, and every
case is written out, including poor matches, refusals and early stops.
"""
from pathlib import Path
import argparse
import csv
import hashlib
import json
import subprocess
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
sys.path.insert(0, str(ROOT/'scripts'))
from reconcile_independent import independent_table
from voltforge.models.cell_catalogue import CellModel, load_additional
from voltforge.studio.network import settings_default, simulate, template

BANK = load_additional(ROOT)
KEY = 'LG_M50T_ECN'


def starting_charge(voltage, temperature):
    """Invert the model OCV by bisection; a voltage above the table caps at 100%."""
    model = CellModel(BANK[KEY]); low, high = model.soc_range
    ocv = lambda z: float(model.parameters(z, temperature)[0])
    if voltage >= ocv(high): return 100.
    if voltage <= ocv(low): return 100*low
    for _ in range(60):
        mid = (low+high)/2
        if ocv(mid) < voltage: low = mid
        else: high = mid
    return 100*(low+high)/2


def run(temperatures, charge, current, seconds, ambient, link_mohm):
    g = template('parallel', len(temperatures))
    for c, t in zip(g['cells'], temperatures): c.update(model=KEY, charge_pct=charge, temperature_C=t)
    for w in g['connections']: w['resistance_mohm'] = float(link_mohm)
    s = settings_default(); s.update(ambient_C=ambient, dt_s=.5, profile=[dict(start_s=0., end_s=float(seconds), current_A=float(current))])
    return simulate(g, s, BANK)


def compare(seg, current, link_mohm, bands):
    """Score one simulation against one measured discharge segment."""
    start = seg['temperature'][0].tolist(); seconds = float(seg['time'][-1])
    charge = starting_charge(seg['rest_voltage'], float(np.mean(seg['rest_temperature'])))
    base = dict(current_A=float(current), link_mohm=link_mohm, starting_charge_pct=charge, ambient_C=seg['ambient'],
                chamber_range_C=seg['chamber_range'], measured_duration_s=seconds)
    try:
        r = run(start, charge, current, seconds, seg['ambient'], link_mohm)
    except ValueError as exc:
        return dict(base, outcome='refused', message=str(exc)), None
    rows = r.rows
    st = np.array([x['time_s'] for x in rows]); sv = np.array([x['voltage_V'] for x in rows])
    keep = np.r_[True, np.diff(st) > 0]; st, sv = st[keep], sv[keep]
    stt = np.array([x['temperature_C'] for x in rows])[keep]
    mask = seg['time'] <= st[-1]
    t, mv, mt = seg['time'][mask], seg['voltage'][mask], seg['temperature'][mask]
    pv = np.interp(t, st, sv); pt = np.column_stack([np.interp(t, st, stt[:, i]) for i in range(stt.shape[1])])
    verror = pv-mv; terror = pt-mt
    measured_rise = (mt-mt[0]).max(axis=0); simulated_rise = (pt-pt[0]).max(axis=0)
    rise_m, rise_s = float(measured_rise.max()), float(simulated_rise.max())
    v = r.summary['verification']
    voltage_ok = bool(np.sqrt(np.mean(verror**2)) <= bands['voltage']['rmse_V'] and np.abs(verror).max() <= bands['voltage']['max_abs_V'])
    temperature_ok = bool(abs(rise_s-rise_m) <= max(1., .25*rise_m))
    result = dict(base, outcome=r.status, stop=(r.stop or {}).get('reason'), coverage_pct=float(100*t[-1]/seconds),
                  voltage_rmse_V=float(np.sqrt(np.mean(verror**2))), voltage_max_abs_V=float(np.abs(verror).max()),
                  temperature_rmse_K=float(np.sqrt(np.mean(terror**2))), temperature_rmse_by_channel_K=np.sqrt(np.mean(terror**2, axis=0)).tolist(),
                  peak_rise_measured_K=rise_m, peak_rise_simulated_K=rise_s, peak_rise_error_K=rise_s-rise_m,
                  voltage_within_band=voltage_ok, temperature_within_band=temperature_ok,
                  first_law_closed=v.get('first_law_closed'), simulated_peak_cell_current_A=r.summary['metrics']['peak_cell_current_A'])
    if 'branch' in seg:
        result['hall_peak_cell_current_A_unresolved'] = float(np.abs(seg['branch']).max())
    hot = int(np.argmax(measured_rise))
    series = np.column_stack([t, mv, pv, mt[:, hot], pt[:, hot]])
    return result, series[np.unique(np.linspace(0, len(series)-1, 240).astype(int))]


def module_segment(path, step):
    d = independent_table(Path(path).read_bytes())
    mask = d['Step_Index'] == step
    first = int(np.argmax(mask)); idx = np.arange(first, first+int(mask[first:].argmin() or mask[first:].size))
    channels = [f'TemperatureC_Cell_{i}' for i in range(1, 5)]
    temperature = np.column_stack([d[c][idx] for c in channels])
    branch = np.column_stack([d[f'CurrentA_Cell_{i}'][idx] for i in range(1, 5)])
    chamber = d['Ambient_TemperatureC'][idx]
    return dict(time=d['Test_Times'][idx]-d['Test_Times'][first], voltage=d['VoltageV'][idx], temperature=temperature,
                rest_voltage=float(d['VoltageV'][first-1]), rest_temperature=[float(d[c][first-1]) for c in channels],
                ambient=float(chamber.mean()), chamber_range=[float(chamber.min()), float(chamber.max())], branch=branch,
                cycler_current=float(np.abs(d['CurrentA'][idx]).mean()), hall_current=float(np.abs(branch.sum(axis=1)).mean()))


def warwick_segment(path, step):
    rows = list(csv.reader(open(path, errors='replace')))
    head = next(i for i, r in enumerate(rows) if r and r[0] == 'Rec'); names = rows[head]
    data = [r for r in rows[head+1:] if len(r) >= len(names)-1 and r[0]]
    col = lambda name: np.array([float(r[names.index(name)]) for r in data])
    mode = np.array([r[names.index('Md')] for r in data])
    steps, time, voltage, current = col('Step'), col('Test Time [s]'), col('Voltage [V]'), col('Current [A]')
    cell, chamber = col('Temperature Cell [degC]'), col('Temperature Chamber [degC]')
    idx = np.nonzero((steps == step) & (mode == 'D'))[0]; first = idx[0]
    return dict(time=time[idx]-time[first], voltage=voltage[idx], temperature=cell[idx, None], rest_voltage=float(voltage[first-1]),
                rest_temperature=[float(cell[first-1])], ambient=float(chamber[idx].mean()),
                chamber_range=[float(chamber[idx].min()), float(chamber[idx].max())], cycler_current=float(np.abs(current[idx]).mean()))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, default=ROOT/'reports/measured_comparison_v1/pilot')
    args = parser.parse_args()
    raw = (ROOT/'configs/measured_comparison_v1.json').read_bytes(); p = json.loads(raw); bands = p['bands']
    args.out.mkdir(parents=True, exist_ok=True)
    cases = []

    def record(name, comparison, seg, current, link, sensitivity=None):
        result, series = compare(seg, current, link, bands)
        result.update(case=name, comparison=comparison['id'], role=comparison['role'], sensitivity=sensitivity)
        cases.append(result)
        if series is not None:
            with open(args.out/f'{name}.csv', 'w', newline='') as f:
                w = csv.writer(f); w.writerow(['time_s', 'measured_V', 'simulated_V', 'measured_hottest_C', 'simulated_same_channel_C'])
                w.writerows(np.round(series, 5).tolist())

    for c in p['comparisons']:
        if 'file' in c:
            path = ROOT/c['file']
            if hashlib.sha256(path.read_bytes()).hexdigest() != c['sha256']: raise SystemExit('Input hash mismatch: '+c['file'])
            seg = module_segment(path, c['discharge_step'])
            record(c['id'], c, seg, seg['cycler_current'], c['link_resistance_mohm'])
            record(c['id']+'__hall_sum_current', c, seg, seg['hall_current'], c['link_resistance_mohm'], 'hall_sum_current')
            record(c['id']+'__link_plus_1_mohm', c, seg, seg['cycler_current'], c['link_resistance_mohm']+1, 'link_plus_1_mohm')
        else:
            for name, md5 in zip(c['files'], c['md5']):
                path = ROOT/name
                if hashlib.md5(path.read_bytes()).hexdigest() != md5: raise SystemExit('Input hash mismatch: '+name)
                for step in c['discharge_steps']:
                    seg = warwick_segment(path, step['step'])
                    record(f"{c['id']}__{path.stem}__{step['nominal_A']:g}A", c, seg, seg['cycler_current'], 0)
    commit = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    output = dict(version='voltforge.measured-comparison-results/1', protocol_sha256=hashlib.sha256(raw).hexdigest(),
                  catalogue_sha256=hashlib.sha256((ROOT/'configs/cell_catalogue_v2.json').read_bytes()).hexdigest(),
                  source_commit=commit, experimental_validation=False, cases=cases)
    (args.out/'result.json').write_text(json.dumps(output, indent=2, allow_nan=False)+'\n')
    for c in cases:
        if 'voltage_rmse_V' in c:
            print(f"{c['case'][:62]:62} {c['current_A']:6.2f}A soc{c['starting_charge_pct']:6.1f} cov{c['coverage_pct']:6.1f}% V {c['voltage_rmse_V']*1000:5.0f}/{c['voltage_max_abs_V']*1000:4.0f}mV T {c['temperature_rmse_K']:.2f}K rise {c['peak_rise_measured_K']:.2f}->{c['peak_rise_simulated_K']:.2f} {'V+' if c['voltage_within_band'] else 'V-'}{'T+' if c['temperature_within_band'] else 'T-'} {c['outcome']} {c.get('stop') or ''}")
        else: print(c['case'], c['outcome'], c.get('message'))


if __name__ == '__main__':
    main()
