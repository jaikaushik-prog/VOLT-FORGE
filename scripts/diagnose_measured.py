"""Post-hoc bounds on the measured comparison, written after seeing its first result.

The frozen protocol's result stays primary. This only asks how much of the gap the
already-declared cooling range explains. No default, table or protocol value changes.
"""
from pathlib import Path
import json
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
from compare_measured import BANK, KEY, ROOT as _, module_segment, run, simulate, settings_default, starting_charge, template, warwick_segment

COOLING = dict(deployed=None, declared_low=.07636608544985142, declared_high=.18042153349476536, no_cooling=0.)


def simulate_with(seg, current, link, cooling):
    charge = starting_charge(seg['rest_voltage'], float(np.mean(seg['rest_temperature'])))
    g = template('parallel', seg['temperature'].shape[1])
    for c, t in zip(g['cells'], seg['temperature'][0].tolist()): c.update(model=KEY, charge_pct=charge, temperature_C=t)
    for w in g['connections']: w['resistance_mohm'] = float(link)
    if cooling is not None: g['thermal']['cell_parameters'] = {c['id']: dict(ambient_conductance_W_K=cooling) for c in g['cells']}
    s = settings_default(); s.update(ambient_C=seg['ambient'], dt_s=.5, profile=[dict(start_s=0., end_s=float(seg['time'][-1]), current_A=float(current))])
    r = simulate(g, s, BANK); st = np.array([x['time_s'] for x in r.rows]); keep = np.r_[True, np.diff(st) > 0]
    return st[keep], np.array([x['voltage_V'] for x in r.rows])[keep], np.array([x['temperature_C'] for x in r.rows])[keep]


def phases(seg, st, sv, stt):
    mask = seg['time'] <= st[-1]; t = seg['time'][mask]; rise = seg['temperature'][mask]-seg['temperature'][0]
    sim = np.column_stack([np.interp(t, st, stt[:, i]) for i in range(stt.shape[1])]); sim -= sim[0]
    out = {}
    for fraction in (.2, .4, .6, .8, 1.):
        i = min(int(fraction*len(t))-1, len(t)-1)
        out[f'{int(fraction*100)}%'] = dict(measured_K=float(rise[i].mean()), simulated_K=float(sim[i].mean()))
    peak_m, peak_s = float(rise.max(axis=0).max()), float(sim.max(axis=0).max())
    return dict(peak_rise_measured_K=peak_m, peak_rise_simulated_K=peak_s, voltage_rmse_mV=float(1000*np.sqrt(np.mean((np.interp(t, st, sv)-seg['voltage'][mask])**2))), by_time=out)


def main():
    root = ROOT/'data/raw/measured_comparison_v1'; cases = []
    sources = [('test28 cycler', module_segment(root/'test28/M1_NMC_Unaged_R3_T25.mat', 5), 'cycler_current', 3.),
               ('test28 Hall sum', module_segment(root/'test28/M1_NMC_Unaged_R3_T25.mat', 5), 'hall_current', 3.),
               ('warwick cell02 5A', warwick_segment(root/'warwick/LGM50_cell02.csv', 17), 'cycler_current', 0.),
               ('warwick cell03 5A', warwick_segment(root/'warwick/LGM50_cell03.csv', 17), 'cycler_current', 0.),
               ('warwick cell04 5A', warwick_segment(root/'warwick/LGM50_cell04.csv', 17), 'cycler_current', 0.),
               ('warwick cell02 2.5A', warwick_segment(root/'warwick/LGM50_cell02.csv', 12), 'cycler_current', 0.)]
    for name, seg, key, link in sources:
        for label, cooling in COOLING.items():
            row = dict(case=name, cooling=label, cooling_W_K=cooling, **phases(seg, *simulate_with(seg, seg[key], link, cooling)))
            cases.append(row)
            print(f"{name:20} {label:14} peak {row['peak_rise_measured_K']:5.2f} -> {row['peak_rise_simulated_K']:5.2f}  V {row['voltage_rmse_mV']:4.0f} mV  40%: {row['by_time']['40%']['measured_K']:.2f} vs {row['by_time']['40%']['simulated_K']:.2f}", flush=True)
    out = ROOT/'reports/measured_comparison_v1/post_hoc_diagnostic.json'
    out.write_text(json.dumps(dict(label='Post-hoc diagnostic. Written after seeing the frozen result, which stays primary. Nothing here changed the model.', cases=cases), indent=2)+'\n')


if __name__ == '__main__':
    main()
