"""Predeclared 25 degC single-cell reproduction; no fitting or assessment access."""
import argparse
from bisect import bisect_right
import csv
from dataclasses import asdict
import hashlib
import io
import json
import math
from pathlib import Path
from zipfile import ZipFile

import numpy as np

from ae_p45b_equations import Parameters, State, advance, reference_query, terminal_voltage
from ae_p45b_intake import PARAMETERS, experimental_rows, hashes, header

ROOT = Path(__file__).resolve().parents[1]
TABLE_NAME = 'Molicel_INR-21700-P45B_ECM.csv'
MEMBER = 'MOLICEL_P45B_025degC_1C_Dch.csv'
FIELDS = ['E_OCV_ch_V', 'E_OCV_dch_V', 'R_R0_Ohm', 'R_R1_Ohm', 'C_C1_F',
          'R_R2_Ohm', 'C_C2_F', 'gamma']
CASES = {'primary': (0.25, 'left', 'stop'),
         'fine_step': (0.0625, 'left', 'stop'),
         'linear_current_sensitivity': (0.25, 'linear', 'stop'),
         'nearest_extension_sensitivity': (0.25, 'left', 'nearest')}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    serialized = json.dumps(value, indent=2, allow_nan=False)+'\n'
    with Path(path).open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(serialized)


class Table25:
    """Actual electrical use is restricted to the exact 25 degC slice."""

    def __init__(self, data):
        if header(io.BytesIO(data)) != PARAMETERS:
            raise ValueError('Unexpected parameter schema')
        reader = csv.reader(io.StringIO(data.decode('utf-8-sig')), strict=True)
        next(reader)
        rows = []
        keys = set()
        for fields in reader:
            if len(fields) != len(PARAMETERS):
                raise ValueError('Ragged parameter row')
            values = list(map(float, fields))
            if not all(math.isfinite(v) for v in values):
                raise ValueError('Nonfinite parameter')
            row = dict(zip(PARAMETERS, values))
            key = row['T_degC'], row['SOC']
            if key in keys:
                raise ValueError('Duplicate temperature/SOC key')
            keys.add(key)
            Parameters(*(row[k] for k in FIELDS))
            row['source_line'] = reader.line_num
            rows.append(row)
        if not rows:
            raise ValueError('Empty parameter table')
        self.rows = sorted((r for r in rows if r['T_degC'] == 25), key=lambda r:r['SOC'])
        if len(self.rows) < 2:
            raise ValueError('Need at least two knots at exactly 25 degC')
        self.soc = [r['SOC'] for r in self.rows]
        self.values = np.array([[r[k] for k in FIELDS] for r in self.rows])
        slices = []
        for temp in sorted({r['T_degC'] for r in rows}):
            rr = sorted((r for r in rows if r['T_degC'] == temp), key=lambda r:r['SOC'])
            slices.append(dict(temperature_degC=temp, rows=len(rr),
                soc_min=rr[0]['SOC'], soc_max=rr[-1]['SOC'],
                nonmonotone_charge_intervals=sum(b['E_OCV_ch_V'] < a['E_OCV_ch_V'] for a,b in zip(rr,rr[1:])),
                nonmonotone_discharge_intervals=sum(b['E_OCV_dch_V'] < a['E_OCV_dch_V'] for a,b in zip(rr,rr[1:])),
                tau_order_violations=sum(r['R_R1_Ohm']*r['C_C1_F'] > r['R_R2_Ohm']*r['C_C2_F'] for r in rr)))
        self.audit = dict(rows=len(rows), temperatures=slices, active_temperature_degC=25,
            active_soc_range=[self.soc[0], self.soc[-1]],
            active_source_lines=[r['source_line'] for r in self.rows],
            active_ranges={k:[min(r[k] for r in self.rows),max(r[k] for r in self.rows)] for k in FIELDS},
            active_tau1_s_range=[min(r['R_R1_Ohm']*r['C_C1_F'] for r in self.rows),max(r['R_R1_Ohm']*r['C_C1_F'] for r in self.rows)],
            active_tau2_s_range=[min(r['R_R2_Ohm']*r['C_C2_F'] for r in self.rows),max(r['R_R2_Ohm']*r['C_C2_F'] for r in self.rows)],
            max_abs_Q_Ah_minus_4p5_times_SOC_minus_1=max(abs(r['Q_Ah']-4.5*(r['SOC']-1)) for r in rows),
            thermal_columns_used=False, fitted_parameters_modified=False,
            interpolation='piecewise linear in SOC at exact 25 degC only')

    def query(self, soc, outside='stop', temperature_degC=25):
        if temperature_degC != 25:
            raise ValueError('Unsupported temperature: this reproduction supports exactly 25 degC')
        query, flags = reference_query(soc, self.soc[0], self.soc[-1], outside=outside)
        index = min(max(bisect_right(self.soc, query)-1, 0), len(self.soc)-2)
        fraction = (query-self.soc[index])/(self.soc[index+1]-self.soc[index])
        values = self.values[index]*(1-fraction)+self.values[index+1]*fraction
        return Parameters(*values), flags


def classify(rows):
    """Descriptive bins frozen before outcome access; no automatic segmentation fit."""
    result = []
    transition = rows[0]['time_s']
    for index, row in enumerate(rows):
        current = row['source_current_A']
        if index and abs(current-rows[index-1]['source_current_A']) >= 0.1:
            transition = row['time_s']
        elapsed = row['time_s']-transition
        magnitude = abs(current)
        result.append(dict(direction='rest' if magnitude <= 0.05 else ('charge' if current > 0 else 'discharge'),
            current_range='0-0.5 A' if magnitude < 0.5 else ('0.5-3 A' if magnitude < 3 else ('3-5 A' if magnitude <= 5 else '>5 A')),
            transition_region='0-10 s' if elapsed <= 10 else ('10-60 s' if elapsed <= 60 else '>60 s'),
            time_since_transition_s=elapsed,
            temperature_evidence='within 1.5 degC of nominal' if abs(row['controlled_temperature_degC']-25) <= 1.5 else 'outside 1.5 degC of nominal'))
    return result


def soc_region(value):
    if value is None:
        return 'unpredicted'
    return '<0' if value < 0 else ('0-0.2' if value < 0.2 else ('0.2-0.8' if value <= 0.8 else ('0.8-1' if value <= 1 else '>1')))


def simulate(table, rows, *, dt_s=0.25, current_mode='left', outside='stop'):
    if not math.isfinite(dt_s) or not 0.001 <= dt_s <= 60:
        raise ValueError('Invalid integration step')
    if current_mode not in ('left', 'linear') or outside not in ('stop', 'nearest'):
        raise ValueError('Unsupported numerical convention')
    if not rows:
        raise ValueError('Empty measurement sequence')
    times = np.array([r['time_s'] for r in rows])
    if not np.all(np.isfinite(times)) or np.any(np.diff(times) <= 0):
        raise ValueError('Invalid time base')
    gaps = np.diff(times)
    gap_limit = max(10., 10*float(np.median(gaps))) if len(gaps) else 10.
    labels = classify(rows)
    state = State(1.0, -1.0)
    predictions = []
    stopped = None
    extension_affected_state = False
    for index, row in enumerate(rows):
        flags = []
        interval_extended = False
        if index and stopped is None:
            elapsed = times[index]-times[index-1]
            if elapsed > gap_limit:
                stopped = dict(reason='acquisition_gap', source_line=row['source_line'], gap_s=float(elapsed), gap_limit_s=gap_limit)
            else:
                steps = max(1, math.ceil(elapsed/dt_s))
                step = float(elapsed/steps)
                left_current = rows[index-1]['source_current_A']
                for j in range(steps):
                    current = left_current if current_mode == 'left' else left_current+(row['source_current_A']-left_current)*(j+0.5)/steps
                    try:
                        p, ff = table.query(state.soc, outside)
                        next_state = advance(state, p, current, step, 4.5)
                        _, ff_end = table.query(next_state.soc, outside)
                    except ValueError as exc:
                        stopped = dict(reason=str(exc), source_line=row['source_line'], substep=j,
                            last_complete_sample_time_s=float(times[index-1]))
                        break
                    interval_extended |= bool(ff or ff_end)
                    state = next_state
        extension_affected_state |= interval_extended
        prediction = dict(**row, **labels[index], predicted_voltage_V=None, residual_V=None,
            soc=None, hysteresis=None, v1_V=None, v2_V=None, reference_extended=False,
            extension_affected_state=extension_affected_state, status='unpredicted')
        if stopped is None:
            try:
                p, flags = table.query(state.soc, outside)
                voltage = terminal_voltage(state, p, row['source_current_A'])
                extension_affected_state |= bool(flags)
                prediction.update(predicted_voltage_V=voltage, residual_V=voltage-row['voltage_V'],
                    **asdict(state), reference_extended=bool(flags or interval_extended),
                    extension_affected_state=extension_affected_state,
                    status='unsupported_reference_extension' if extension_affected_state else 'predicted_with_declared_assumptions')
            except ValueError as exc:
                stopped = dict(reason=str(exc), source_line=row['source_line'])
        prediction['soc_region'] = soc_region(prediction['soc'])
        predictions.append(prediction)
    return dict(rows=predictions, stopped=stopped, gap_limit_s=gap_limit,
        configuration=dict(max_step_s=dt_s, current_mode=current_mode, reference_policy=outside,
            initial_soc=1, initial_hysteresis=-1, initial_v1_V=0, initial_v2_V=0,
            capacity_Ah=4.5, temperature_degC=25))


def metrics(rows, mask=None):
    valid = np.array([r['residual_V'] is not None for r in rows])
    if mask is not None:
        valid &= np.array(mask, dtype=bool)
    errors = np.array([r['residual_V'] if r['residual_V'] is not None else 0 for r in rows])
    times = np.array([r['time_s'] for r in rows])
    weights = np.zeros(len(rows))
    for i, delta in enumerate(np.diff(times)):
        if valid[i] and valid[i+1]:
            weights[i] += delta/2
            weights[i+1] += delta/2
    duration = float(weights.sum())
    selected = errors[valid]
    return dict(samples=int(valid.sum()), covered_duration_s=duration,
        sample_rmse_mV=float(1000*np.sqrt(np.mean(selected**2))) if len(selected) else None,
        sample_bias_mV=float(1000*np.mean(selected)) if len(selected) else None,
        max_abs_error_mV=float(1000*np.max(np.abs(selected))) if len(selected) else None,
        time_rmse_mV=float(1000*np.sqrt(np.dot(weights, errors**2)/duration)) if duration else None,
        time_bias_mV=float(1000*np.dot(weights, errors)/duration) if duration else None)


def summarize(run):
    rows = run['rows']
    measured_cross = next((i for i,r in enumerate(rows) if r['voltage_V'] <= 2.5), None)
    predicted_cross = next((i for i,r in enumerate(rows) if r['predicted_voltage_V'] is not None and r['predicted_voltage_V'] <= 2.5), None)
    first = min([i for i in [measured_cross, predicted_cross] if i is not None], default=len(rows))
    groups = {}
    for key in ('soc_region', 'direction', 'current_range', 'transition_region', 'temperature_evidence'):
        groups[key] = {v:metrics(rows, [r[key] == v for r in rows]) for v in sorted({r[key] for r in rows})}
    coverage = dict(rows=len(rows), predicted_rows=sum(r['predicted_voltage_V'] is not None for r in rows),
        extended_reference_rows=sum(r['reference_extended'] for r in rows),
        extension_affected_state_rows=sum(r['extension_affected_state'] for r in rows),
        recorded_temperature_deviation_rows=sum(r['temperature_evidence'].startswith('outside') for r in rows),
        initial_conditions='author reproduction assumptions; not measured or fitted here',
        waveform_scope='this one complete development discharge only',
        experimental_module_validation='awaiting suitable measurements')
    return dict(configuration=run['configuration'], stopped=run['stopped'], coverage=coverage,
        full_available_interval=metrics(rows), common_pre_protocol_cutoff=metrics(rows, [i < first for i in range(len(rows))]),
        protocol_cutoff_V=2.5, protocol_cutoff_is_application_requirement=False,
        measured_cutoff_source_line=rows[measured_cross]['source_line'] if measured_cross is not None else None,
        predicted_cutoff_source_line=rows[predicted_cross]['source_line'] if predicted_cross is not None else None,
        by_group=groups, requirement_status='requirement not configured')


def difference(left, right):
    deltas = [a['predicted_voltage_V']-b['predicted_voltage_V'] for a,b in zip(left['rows'],right['rows'])
              if a['predicted_voltage_V'] is not None and b['predicted_voltage_V'] is not None]
    return dict(common_samples=len(deltas), max_abs_voltage_difference_mV=float(1000*max(map(abs,deltas))) if deltas else None,
        rmse_voltage_difference_mV=float(1000*np.sqrt(np.mean(np.array(deltas)**2))) if deltas else None)


def source_diagnostics(rows):
    times = np.array([r['time_s'] for r in rows])
    delta = np.diff(times)
    currents = np.array([r['source_current_A'] for r in rows])
    labels = classify(rows)
    intervals = []
    start = 0
    # Contiguous sample runs; duration uses first/last observed time, no endpoint extrapolation.
    for i in range(1,len(rows)+1):
        if i == len(rows) or labels[i]['direction'] != labels[start]['direction']:
            intervals.append(dict(direction=labels[start]['direction'], source_line_start=rows[start]['source_line'],
                source_line_end=rows[i-1]['source_line'], duration_s=float(times[i-1]-times[start]),
                current_min_A=float(min(currents[start:i])), current_max_A=float(max(currents[start:i]))))
            start = i
    return dict(samples=len(rows), first_time_s=float(times[0]), last_time_s=float(times[-1]),
        duration_s=float(times[-1]-times[0]), sample_interval_s=dict(min=float(min(delta)), median=float(np.median(delta)), max=float(max(delta))),
        current_charge_positive_A=[float(min(currents)),float(max(currents))],
        voltage_V=[min(r['voltage_V'] for r in rows), max(r['voltage_V'] for r in rows)],
        controlled_temperature_degC=[min(r['controlled_temperature_degC'] for r in rows),max(r['controlled_temperature_degC'] for r in rows)],
        discharge_Ah_left=float(-np.dot(currents[:-1],delta)/3600),
        discharge_Ah_linear=float(-np.dot((currents[:-1]+currents[1:])/2,delta)/3600),
        contiguous_direction_runs=intervals)


def plot_runs(runs, out):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    primary = runs['primary']['rows']
    time = np.array([r['time_s'] for r in primary])/60
    fig, axes = plt.subplots(4,1,figsize=(11,10),sharex=True, constrained_layout=True)
    axes[0].plot(time, [r['voltage_V'] for r in primary], color='#1b2733', label='Measured voltage', lw=1.6)
    colors = dict(primary='#177c92', fine_step='#9b598f', linear_current_sensitivity='#e28c32', nearest_extension_sensitivity='#599c60')
    for name, run in runs.items():
        rows = run['rows']
        if name != 'fine_step':
            axes[0].plot(time, [r['predicted_voltage_V'] for r in rows], label=name.replace('_',' '), color=colors[name], lw=1, alpha=.8)
        axes[1].plot(time, [1000*r['residual_V'] if r['residual_V'] is not None else np.nan for r in rows], label=name.replace('_',' '), color=colors[name], lw=1)
    axes[0].set_ylabel('Voltage (V)'); axes[0].legend(fontsize=8)
    axes[1].set_ylabel('Prediction - measured (mV)'); axes[1].axhline(0,color='#888',lw=.6); axes[1].legend(fontsize=8)
    axes[2].plot(time, [r['source_current_A'] for r in primary], color='#1b2733'); axes[2].set_ylabel('Current (A)\ncharge positive')
    axes[3].plot(time, [r['controlled_temperature_degC'] for r in primary], color='#b15c38',label='Recorded surface temperature')
    axes[3].axhline(25,color='#177c92',ls='--',label='Isothermal model assumption')
    axes[3].set_ylabel('Temperature (degC)'); axes[3].set_xlabel('Recorded time (min)'); axes[3].legend(fontsize=8)
    for ax in axes: ax.grid(alpha=.2)
    fig.suptitle('P45B 25 degC 1C discharge: published-parameter reproduction\nOne development record; no parameter fitting or module validation',fontsize=13)
    fig.savefig(out/'voltage_comparison.png',dpi=160); plt.close(fig)
    fig, axes = plt.subplots(1,3,figsize=(13,4.5),constrained_layout=True)
    valid = [r for r in primary if r['residual_V'] is not None]
    for ax, field, label in zip(axes,['soc','time_since_transition_s','controlled_temperature_degC'],['Nominal-capacity SOC','Seconds since current transition','Recorded temperature (degC)']):
        ax.scatter([r[field] for r in valid],[1000*r['residual_V'] for r in valid],s=4,alpha=.4,color='#177c92')
        ax.set_xlabel(label); ax.set_ylabel('Residual (mV)'); ax.grid(alpha=.2)
    axes[1].set_xscale('symlog',linthresh=1)
    fig.suptitle('Primary residual diagnostics: SOC, elapsed time and temperature are confounded in one discharge')
    fig.savefig(out/'residual_diagnostics.png',dpi=160); plt.close(fig)


def load_allowed_sources():
    lock = json.loads((ROOT/'configs/ae_p45b_reproduction_v1.json').read_text())
    for name, expected in lock['preaccess_files'].items():
        if sha(ROOT/name) != expected:
            raise ValueError('Preaccess source/procedure hash mismatch: '+name)
    if lock['allowed_measurement_member'] != MEMBER or lock['allowed_parameter_file'] != TABLE_NAME:
        raise ValueError('Unexpected evidence allocation')
    with ZipFile(ROOT/'molicel_p45b_data.zip') as archive:
        data = archive.read(MEMBER)  # Exactly one explicitly allocated member.
    if hashlib.sha256(data).hexdigest() != lock['member_sha256']:
        raise ValueError('Allocated member hash mismatch')
    return Table25((ROOT/TABLE_NAME).read_bytes()), experimental_rows(data), lock


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    out = args.out.resolve()
    if not any(out.is_relative_to(ROOT/name) for name in ('reports','tmp','workspace')):
        raise SystemExit('Outputs must be under reports/, tmp/ or workspace/.')
    if out.exists():
        raise SystemExit('Use a new output directory; preserve completed runs.')
    table, source, lock = load_allowed_sources()
    out.mkdir(parents=True)
    write_json(out/'table_audit.json',table.audit)
    write_json(out/'source_diagnostics.json',source_diagnostics(source['rows']))
    runs = {}
    for name, (step, current_mode, outside) in CASES.items():
        runs[name] = simulate(table, source['rows'], dt_s=step, current_mode=current_mode, outside=outside)
        with (out/(name+'.csv')).open('x',newline='',encoding='utf-8') as stream:
            writer = csv.DictWriter(stream, fieldnames=list(runs[name]['rows'][0]))
            writer.writeheader(); writer.writerows(runs[name]['rows'])
    convergence = difference(runs['primary'],runs['fine_step'])
    convergence['proposed_numerical_tolerance_mV'] = 0.1
    convergence['criterion_met'] = bool(convergence['max_abs_voltage_difference_mV'] is not None and convergence['max_abs_voltage_difference_mV'] <= 0.1)
    summary = dict(schema_version='voltforge.ae_p45b_reproduction/1',
        evidence_class='published-parameter reproduction on one development record',
        source_member=MEMBER, source_member_sha256=source['source_sha256'],
        procedure_sha256=lock['preaccess_files']['reports/p45b_reproduction_v1/PROCEDURE.md'],
        preaccess_commit=lock['preaccess_commit'], allocation=lock,
        experimental_rows_opened=len(source['rows']), author_numeric_output_rows_opened=0,
        parameter_rows_opened=table.audit['rows'], unused_measurement_files=50,
        validation_workbook_opened=False, new_parameter_fit=False,
        runs={name:summarize(run) for name,run in runs.items()}, numerical_convergence=convergence,
        sampling_sensitivity=difference(runs['primary'],runs['linear_current_sensitivity']),
        implementation_sha256={name:sha(ROOT/name) for name in ['scripts/ae_p45b_reproduction.py','scripts/ae_p45b_equations.py','scripts/ae_p45b_intake.py']})
    write_json(out/'summary.json',summary)
    plot_runs(runs,out)
    write_json(out/'manifest.json',{p.name:sha(p) for p in sorted(out.iterdir()) if p.is_file()})
    for name, run in summary['runs'].items():
        print(name, json.dumps(run['full_available_interval']), 'stop:',run['stopped'])
    print('Convergence:',json.dumps(convergence))


if __name__ == '__main__':
    main()
