"""Frozen-model GITT replay of already-used development evidence; no fitting."""
import argparse
import csv
import gzip
import io
import json
import math
from pathlib import Path

import numpy as np

from ae_p45b_reproduction import (ROOT, TABLE_NAME, Table25, simulate, summarize,
    metrics, difference, sha, write_json, soc_region)
from ae_p45b_low_soc import write_csv

CASES = {
    'primary': (.25, 'left', 0.),
    'fine_step': (.0625, 'left', 0.),
    'linear_current_sensitivity': (.25, 'linear', 0.),
    'initial_soc_minus_0p005': (.25, 'left', -.005),
    'initial_soc_plus_0p005': (.25, 'left', .005),
}
IMPLEMENTATIONS = ['scripts/ae_p45b_gitt_replay.py', 'scripts/ae_p45b_reproduction.py',
    'scripts/ae_p45b_equations.py', 'scripts/ae_p45b_low_soc.py']


class OriginTable:
    """Constant coordinate transform; no changes to parameters or state equations."""
    def __init__(self, table, offset):
        if not math.isfinite(offset):
            raise ValueError('Nonfinite initial SOC offset')
        self.table, self.offset = table, offset

    def query(self, solver_soc, outside='stop'):
        if outside != 'stop':
            raise ValueError('GITT diagnosis does not permit reference extension')
        return self.table.query(solver_soc + self.offset, outside)


def read_csv(path):
    with Path(path).open(newline='', encoding='utf-8') as stream:
        return list(csv.DictReader(stream))


def load_sources():
    lock = json.loads((ROOT / 'configs/ae_p45b_gitt_replay_v1.json').read_text())
    for name, expected in lock['frozen_files'].items():
        if sha(ROOT / name) != expected:
            raise ValueError('Frozen source/procedure mismatch: ' + name)
    rows = []
    for saved in read_csv(ROOT / lock['saved_samples']):
        row = {k: float(saved[k]) for k in ['time_s', 'source_current_A', 'voltage_V', 'controlled_temperature_degC']}
        if not all(math.isfinite(v) for v in row.values()):
            raise ValueError('Nonfinite measurement')
        row.update(source_line=int(saved['source_line']), segment_id=int(saved['segment_id']))
        if row['source_line'] != len(rows) + 2:
            raise ValueError('Changed source row order')
        rows.append(row)
    segments = read_csv(ROOT / lock['saved_segments'])
    pairs = read_csv(ROOT / lock['saved_pairs'])
    cursor = 0
    for n, s in enumerate(segments):
        a, b = int(s['start_index']), int(s['end_index'])
        if a != cursor or b < a or int(s['segment_id']) != n or b >= len(rows):
            raise ValueError('Incomplete segment inventory')
        if any(r['segment_id'] != n for r in rows[a:b+1]):
            raise ValueError('Segment/source mismatch')
        cursor = b + 1
    if cursor != len(rows):
        raise ValueError('Segments must retain every source sample')
    for pair in pairs:
        a, b = int(pair['pulse_segment_id']), int(pair['rest_segment_id'])
        if b != a + 1 or segments[a]['phase'] != 'discharge' or segments[b]['phase'] != 'rest':
            raise ValueError('Noncontiguous pulse/rest pair')
        for key, expected in [('pulse_last_source_line', segments[a]['last_source_line']),
            ('rest_first_source_line', segments[b]['first_source_line']), ('rest_last_source_line', segments[b]['last_source_line'])]:
            if pair[key] != expected:
                raise ValueError('Pair/source mismatch')
    return Table25((ROOT / TABLE_NAME).read_bytes()), rows, segments, pairs, lock


def absolute_charge(times, currents, mode, max_step_s=None):
    dt = np.diff(times); a, b = currents[:-1], currents[1:]
    if mode == 'left':
        intervals = abs(a) * dt
    else:
        intervals = (abs(a) + abs(b)) * dt / 2
        opposite = a * b < 0
        intervals[opposite] = dt[opposite] * (a[opposite]**2 + b[opposite]**2) / (2 * (abs(a[opposite]) + abs(b[opposite])))
        if max_step_s is not None:
            # Match the frozen solver's sampled absolute current at a sign change.
            for n in np.flatnonzero(opposite):
                count = max(1, math.ceil(dt[n]/max_step_s))
                midpoint = a[n] + (b[n]-a[n])*(np.arange(count)+.5)/count
                intervals[n] = float(sum(abs(midpoint))*dt[n]/count)
    return np.r_[0., np.cumsum(intervals)]


def maximum_tau(values, r_column, c_column):
    """Bound R*C including interior extrema of linearly interpolated R and C."""
    resistance, capacitance = values[:, r_column], values[:, c_column]
    maximum = float(max(resistance*capacitance))
    for r, c, dr, dc in zip(resistance[:-1], capacitance[:-1], np.diff(resistance), np.diff(capacitance)):
        quadratic, linear = dr*dc, r*dc+c*dr
        if quadratic < 0:
            fraction = -linear/(2*quadratic)
            if 0 < fraction < 1:
                maximum = max(maximum, float((r+fraction*dr)*(c+fraction*dc)))
    return maximum


def replay(table, source, segments, case):
    step, mode, offset = CASES[case]
    # The frozen simulator, including its stop behavior, remains the sole solver.
    run = simulate(OriginTable(table, offset), source, dt_s=step, current_mode=mode, outside='stop')
    run['configuration'].update(initial_soc=1+offset, initial_soc_offset=offset,
        evidence_role='sensitivity scenario' if offset else 'frozen-model development replay')
    times = np.array([r['time_s'] for r in source])
    currents = np.array([r['source_current_A'] for r in source])
    charge = absolute_charge(times, currents, mode, step)
    tau1 = maximum_tau(table.values, 3, 4)
    tau2 = maximum_tau(table.values, 5, 6)
    gamma = min(table.values[:, 7])
    for n, row in enumerate(run['rows']):
        row['phase_elapsed_s'] = row['time_s'] - float(segments[row['segment_id']]['start_time_s'])
        row.update(reference_V=None, ohmic_V=None, closure_mV=None,
            initial_v1_memory_upper_fraction=None, initial_v2_memory_upper_fraction=None,
            initial_hysteresis_memory_upper_fraction=None)
        if row['soc'] is None:
            continue
        row['soc'] += offset
        row['soc_region'] = soc_region(row['soc'])
        p, _ = table.query(row['soc'])
        h = row['hysteresis']
        reference = ((1+h)*p.ocv_charge_V + (1-h)*p.ocv_discharge_V) / 2
        ohmic = row['source_current_A'] * p.r0_Ohm
        voltage = reference + ohmic + (row['v1_V'] if p.r1_Ohm else 0.) + (row['v2_V'] if p.r2_Ohm else 0.)
        elapsed = times[n] - times[0]
        decay = lambda tau: math.exp(-elapsed/tau) if tau > 0 else (1. if elapsed == 0 else 0.)
        row.update(reference_V=reference, ohmic_V=ohmic,
            closure_mV=1000*(voltage-row['predicted_voltage_V']),
            initial_v1_memory_upper_fraction=decay(tau1), initial_v2_memory_upper_fraction=decay(tau2),
            initial_hysteresis_memory_upper_fraction=math.exp(-gamma*charge[n]/16200))
    run['conditional_memory_bounds'] = dict(max_tau1_s=float(tau1), max_tau2_s=float(tau2),
        min_gamma=float(gamma), interpretation='fixed SOC/current history only; not real-error or initial-SOC bounds')
    return run


def pair_diagnostics(rows, segments, pairs):
    result = []
    for pair in pairs:
        loaded = rows[int(pair['pulse_last_source_line']) - 2]
        rest = segments[int(pair['rest_segment_id'])]
        group = rows[int(rest['start_index']):int(rest['end_index']) + 1]
        late = [r for r in group if r['time_s'] >= group[-1]['time_s'] - 60]
        complete = loaded['predicted_voltage_V'] is not None and all(r['predicted_voltage_V'] is not None for r in group)
        measured_median = float(np.median([r['voltage_V'] for r in late]))
        predicted_median = float(np.median([r['predicted_voltage_V'] for r in late])) if complete else None
        def slope(key):
            if len(late) < 3 or late[-1]['time_s'] - late[0]['time_s'] < 30 or any(r[key] is None for r in late):
                return None
            x = np.array([r['time_s'] - late[0]['time_s'] for r in late]); y = np.array([r[key] for r in late])
            return float(np.dot(x-x.mean(), y-y.mean()) / np.dot(x-x.mean(), x-x.mean()) * 60000)
        measured_recovery = 1000*(measured_median-loaded['voltage_V'])
        predicted_recovery = 1000*(predicted_median-loaded['predicted_voltage_V']) if complete else None
        item = {k: pair[k] for k in ['pair_index', 'pulse_segment_id', 'rest_segment_id',
            'pulse_last_source_line', 'rest_first_source_line', 'rest_last_source_line',
            'pulse_duration_s', 'rest_duration_s', 'transition_sample_separation_s']}
        item.update(nominal_soc_loaded=loaded['soc'], current_charge_positive_A=loaded['source_current_A'],
            complete_prediction=complete, loaded_measured_V=loaded['voltage_V'], loaded_predicted_V=loaded['predicted_voltage_V'],
            loaded_error_mV=1000*loaded['residual_V'] if loaded['residual_V'] is not None else None,
            first_rest_error_mV=1000*group[0]['residual_V'] if group[0]['residual_V'] is not None else None,
            late_measured_median_V=measured_median, late_predicted_median_V=predicted_median,
            late_median_difference_mV=1000*(predicted_median-measured_median) if complete else None,
            measured_recovery_mV=measured_recovery, predicted_recovery_mV=predicted_recovery,
            recovery_difference_mV=predicted_recovery-measured_recovery if complete else None,
            measured_late_slope_mV_per_min=slope('voltage_V'), predicted_late_slope_mV_per_min=slope('predicted_voltage_V'),
            late_polarization_median_mV=float(np.median([1000*(r['v1_V']+r['v2_V']) for r in late])) if complete else None,
            initial_v2_memory_upper_fraction=loaded['initial_v2_memory_upper_fraction'],
            initial_hysteresis_memory_upper_fraction=loaded['initial_hysteresis_memory_upper_fraction'])
        result.append(item)
    return result


def summarize_gitt(run, segments, pairs):
    summary = summarize(run)
    rows = run['rows']
    summary['coverage']['waveform_scope'] = 'already-used complete GITT development record; no fresh assessment'
    summary['conditional_memory_bounds'] = run['conditional_memory_bounds']
    windows = [('0-1 s', 0, 1), ('1-10 s', 1, 10), ('10-60 s', 10, 60), ('60-600 s', 60, 600), ('>600 s', 600, float('inf'))]
    summary['rest_windows'] = {name: metrics(rows, [r['direction']=='rest' and
        ((r['phase_elapsed_s'] >= lo) if lo == 0 else (r['phase_elapsed_s'] > lo)) and r['phase_elapsed_s'] <= hi for r in rows])
        for name, lo, hi in windows}
    summary['max_voltage_decomposition_closure_mV'] = max((abs(r['closure_mV']) for r in rows if r['closure_mV'] is not None), default=None)
    segment_results = []
    for segment in segments:
        a, b = int(segment['start_index']), int(segment['end_index'])
        segment_results.append(dict(segment_id=int(segment['segment_id']), phase=segment['phase'],
            first_source_line=int(segment['first_source_line']), last_source_line=int(segment['last_source_line']),
            **metrics(rows[a:b+1])))
    return summary, segment_results, pair_diagnostics(rows, segments, pairs)


def write_predictions(path, rows):
    fields = ['source_line', 'time_s', 'source_current_A', 'voltage_V', 'predicted_voltage_V', 'residual_V',
        'soc', 'hysteresis', 'v1_V', 'v2_V', 'reference_V', 'ohmic_V', 'closure_mV', 'segment_id', 'direction',
        'phase_elapsed_s', 'status', 'initial_v1_memory_upper_fraction', 'initial_v2_memory_upper_fraction',
        'initial_hysteresis_memory_upper_fraction']
    stream = io.StringIO(newline='')
    writer = csv.DictWriter(stream, fieldnames=fields, extrasaction='ignore')
    writer.writeheader(); writer.writerows(rows)
    with path.open('xb') as target:
        target.write(gzip.compress(stream.getvalue().encode('utf-8'), mtime=0))


def plot(primary, segments, all_pairs, out):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    rows = primary['rows']; time = np.array([r['time_s'] for r in rows]) / 3600
    values = lambda key: [r[key] if r[key] is not None else np.nan for r in rows]
    fig, axes = plt.subplots(3, 1, figsize=(12, 9), sharex=True, constrained_layout=True)
    axes[0].plot(time, values('voltage_V'), color='#27323b', lw=.7, label='Measured')
    axes[0].plot(time, values('predicted_voltage_V'), color='#177c92', lw=.7, label='Frozen model')
    axes[0].set_ylabel('Voltage (V)'); axes[0].legend()
    axes[1].plot(time, np.array(values('residual_V'))*1000, color='#b56432', lw=.6)
    axes[1].set_ylabel('Prediction - measured (mV)')
    axes[2].plot(time, values('source_current_A'), color='#27323b', lw=.6)
    axes[2].set_ylabel('Current (A), charge positive'); axes[2].set_xlabel('Recorded time (h)')
    for ax in axes: ax.grid(alpha=.2)
    fig.suptitle('P45B 25 degC GITT: full-sequence frozen-model replay\nAlready-used development evidence; initial SOC=1 assumed')
    fig.savefig(out/'complete_replay.png', dpi=150); plt.close(fig)
    fig, axes = plt.subplots(3, 1, figsize=(11, 10), sharex=True, constrained_layout=True)
    for case, pairs in all_pairs.items():
        valid = [p for p in pairs if p['complete_prediction']]
        if not valid: continue
        x = [p['nominal_soc_loaded'] for p in valid]
        for ax, key in zip(axes, ['loaded_error_mV', 'late_median_difference_mV', 'recovery_difference_mV']):
            ax.plot(x, [p[key] for p in valid], '.-', lw=.8, label=case)
    for ax, label in zip(axes, ['Loaded-end error (mV)', 'Late-rest median difference (mV)', 'Predicted - measured recovery (mV)']):
        ax.set_ylabel(label); ax.grid(alpha=.2); ax.axhline(0, color='#888', lw=.5)
    axes[0].legend(fontsize=7); axes[-1].set_xlabel('Assumed nominal SOC at loaded endpoint')
    fig.suptitle('Every complete pulse/rest pair: full transient predictions\nSensitivity scenarios are not confidence bounds or replacement models')
    fig.savefig(out/'pair_diagnostics.png', dpi=150); plt.close(fig)
    pairs = all_pairs['primary']
    chosen = list(dict.fromkeys([0]+[min(range(len(pairs)), key=lambda i: abs(float(pairs[i]['nominal_soc_loaded'] or 0)-z)) for z in [.5, .1, .04]]+[len(pairs)-1]))
    fig, axes = plt.subplots(len(chosen), 2, figsize=(13, 3*len(chosen)), squeeze=False, constrained_layout=True)
    for axs, index in zip(axes, chosen):
        pair = pairs[index]; pulse = segments[int(pair['pulse_segment_id'])]; rest = segments[int(pair['rest_segment_id'])]
        group = rows[int(pulse['start_index']):int(rest['end_index'])+1]
        t = np.array([r['time_s']-float(rest['start_time_s']) for r in group])
        axs[0].plot(t, [r['voltage_V'] for r in group], label='Measured', color='#27323b')
        axs[0].plot(t, [r['predicted_voltage_V'] for r in group], label='Frozen model', color='#177c92')
        axs[1].plot(t, [1000*r['residual_V'] if r['residual_V'] is not None else np.nan for r in group], color='#b56432')
        axs[0].set_ylabel('Voltage (V)'); axs[1].set_ylabel('Residual (mV)')
        axs[0].set_title(f"Pair {index}; nominal SOC {pair['nominal_soc_loaded']:.4f}; source lines {pulse['first_source_line']}-{rest['last_source_line']}")
        for ax in axs:
            ax.set_xscale('symlog', linthresh=1); ax.grid(alpha=.2); ax.set_xlabel('Seconds from first rest sample (symlog)'); ax.axvline(0, color='#888', lw=.5)
    axes[0, 0].legend(fontsize=8)
    fig.suptitle('Complete sequences selected by SOC, not by error\n25 degC GITT development record; finite rests are not equilibrium OCV')
    fig.savefig(out/'selected_sequences.png', dpi=130); plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--out', type=Path, required=True)
    out = parser.parse_args().out.resolve()
    if not any(out.is_relative_to(ROOT/n) for n in ('reports', 'tmp', 'workspace')):
        raise SystemExit('Write under reports/, tmp/ or workspace/.')
    if out.exists(): raise SystemExit('Choose a new output directory; preserve existing runs.')
    table, source, segments, pairs, lock = load_sources()
    out.mkdir(parents=True)
    summaries = {}; comparisons = {}; all_pairs = {}; primary = None
    for case in CASES:
        print('Running '+case, flush=True)
        run = replay(table, source, segments, case)
        summaries[case], segment_results, all_pairs[case] = summarize_gitt(run, segments, pairs)
        write_predictions(out/(case+'.csv.gz'), run['rows'])
        write_csv(out/(case+'_segments.csv'), segment_results)
        write_csv(out/(case+'_pairs.csv'), all_pairs[case])
        if primary is None: primary = run
        else: comparisons[case] = difference(primary, run)
        print(json.dumps(dict(case=case, metrics=summaries[case]['full_available_interval'], stopped=run['stopped'])), flush=True)
    delta = comparisons['fine_step']['max_abs_voltage_difference_mV']
    summary = dict(schema_version='voltforge.ae_p45b_gitt_replay/1', source_lock=lock, runs=summaries,
        differences_from_primary=comparisons, numerical_convergence=dict(criterion_mV=.1,
            criterion_met=bool(delta is not None and delta <= .1), criterion_role='proposed numerical check only'),
        measurement_families_newly_opened=0, remaining_unopened_members=48,
        fitted_parameters_changed=False, initial_states_fitted=False, fresh_independent_assessment=False,
        requirement_status='requirement not configured', experimental_module_validation='awaiting suitable measurements',
        implementation_sha256={n:sha(ROOT/n) for n in IMPLEMENTATIONS})
    write_json(out/'summary.json', summary)
    plot(primary, segments, all_pairs, out)
    write_json(out/'manifest.json', {p.name:sha(p) for p in sorted(out.iterdir()) if p.is_file()})


if __name__ == '__main__': main()
