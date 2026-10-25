"""Standalone synthetic one-node heat balance; never an LG/module heat model.

No electrical source, measurement file, fitted cell artifact or external data is
read. Q is prescribed signed heat into the node, excluding the separately
modelled H exchange. Every physical input is mandatory. Reporting steps are not
numerical integration steps: each constant-input interval is solved exactly.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import platform

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / 'configs/thermal_feasibility_v1.json'
REPORT = ROOT / 'reports/thermal_feasibility_v1'
MAX_ROWS = 100001
MODEL = 'one_node_prescribed_heat_v1'
LABEL = 'SYNTHETIC ONLY - no established real-cell applicability'


def finite_number(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f'{name} must be a finite number')
    if not math.isfinite(value):
        raise ValueError(f'{name} must be a finite number')
    return float(value)


def exact_fields(obj, keys, name):
    if not isinstance(obj, dict) or set(obj) != set(keys):
        raise ValueError(f'{name} has missing or unsupported fields; required: {sorted(keys)}')


def validate_config(config):
    exact_fields(config, {'schema_version', 'model', 'evidence_kind', 'cell_identity',
        'electrical_coupling', 'scenario_id', 'description', 'heat_capacity_J_per_K',
        'conductance_W_per_K', 'initial_temperature_degC', 'output_step_s',
        'comparison_output_step_s', 'profile', 'provenance'}, 'configuration')
    if type(config['schema_version']) is not int or config['schema_version'] != 1:
        raise ValueError('Unsupported schema_version')
    if config['model'] != MODEL or config['evidence_kind'] != 'synthetic_only':
        raise ValueError('Only the synthetic one-node prototype is supported')
    if config['cell_identity'] is not None or config['electrical_coupling'] is not False:
        raise ValueError('Real-cell attribution and automatic electrical coupling are unsupported')
    for key in ('scenario_id', 'description'):
        if not isinstance(config[key], str) or not config[key].strip():
            raise ValueError(f'{key} must be nonempty text')
    exact_fields(config['provenance'], {'heat_capacity_J_per_K', 'conductance_W_per_K',
        'initial_temperature_degC', 'profile', 'output_steps'}, 'provenance')
    if any(not isinstance(v, str) or not v.strip() for v in config['provenance'].values()):
        raise ValueError('Each synthetic input must have explicit provenance text')
    # Provenance is a declaration, never verified experimental evidence.
    for key in ('output_step_s', 'comparison_output_step_s'):
        if finite_number(config[key], key) <= 0:
            raise ValueError('Reporting steps must be positive')
    validate_inputs(config['heat_capacity_J_per_K'], config['conductance_W_per_K'],
        config['initial_temperature_degC'], config['profile'], config['output_step_s'])
    validate_inputs(config['heat_capacity_J_per_K'], config['conductance_W_per_K'],
        config['initial_temperature_degC'], config['profile'], config['comparison_output_step_s'])
    return config


def validate_inputs(capacity, conductance, initial, profile, output_step):
    c = finite_number(capacity, 'heat capacity')
    h = finite_number(conductance, 'conductance')
    t = finite_number(initial, 'initial temperature')
    dt = finite_number(output_step, 'output step')
    if c <= 0 or h < 0 or dt <= 0 or t <= -273.15:
        raise ValueError('Require C_th>0, H>=0, dt>0 and temperature above absolute zero')
    if not isinstance(profile, list) or not profile:
        raise ValueError('A nonempty contiguous profile is required')
    end = 0.0
    for segment in profile:
        exact_fields(segment, {'start_s', 'end_s', 'prescribed_heat_W',
            'ambient_temperature_degC'}, 'profile interval')
        values = {k: finite_number(v, k) for k, v in segment.items()}
        if values['start_s'] != end or values['end_s'] <= values['start_s']:
            raise ValueError('Profile must be exactly contiguous from zero, without gaps/overlap')
        if values['ambient_temperature_degC'] <= -273.15:
            raise ValueError('Ambient temperature must be above absolute zero')
        end = values['end_s']
    if end / dt + len(profile) + 1 > MAX_ROWS:
        raise ValueError('Reporting grid exceeds the row limit')


def _phi_and_complement(x):
    """Return (1-exp(-x))/x and its complement without small-x cancellation."""
    if x < 1e-5:
        complement = x * (0.5 + x * (-1/6 + x * (1/24 - x/120)))
        return 1 - complement, complement
    phi = -math.expm1(-x) / x
    return phi, 1 - phi


def exact_interval(temperature_degC, ambient_temperature_degC, prescribed_heat_W,
                   heat_capacity_J_per_K, conductance_W_per_K, duration_s):
    """Return endpoint T, signed source/outward energy, and stored-energy change."""
    t, a, q, c, h, duration = [finite_number(v, name) for v, name in zip(
        (temperature_degC, ambient_temperature_degC, prescribed_heat_W,
         heat_capacity_J_per_K, conductance_W_per_K, duration_s),
        ('temperature', 'ambient', 'heat', 'capacity', 'conductance', 'duration'))]
    if c <= 0 or h < 0 or duration < 0 or min(t, a) <= -273.15:
        raise ValueError('Invalid thermal interval domain')
    x = h * duration / c
    if not math.isfinite(x):
        raise ValueError('Thermal time-scale arithmetic is not finite')
    phi, complement = _phi_and_complement(x)
    storage = (q - h * (t-a)) * duration * phi
    outward = h * (t-a) * duration * phi + q * duration * complement
    source = q * duration
    end = t + storage / c
    if not all(math.isfinite(v) for v in (storage, outward, source, end)):
        raise ValueError('Thermal arithmetic is not finite')
    if end <= -273.15:
        raise ValueError('Prescribed scenario crosses absolute zero; stopped without clipping')
    return end, source, outward, storage


def simulate(*, heat_capacity_J_per_K, conductance_W_per_K,
             initial_temperature_degC, profile, output_step_s):
    """Generic synthetic mathematics; no physical evidence is inferred from inputs."""
    validate_inputs(heat_capacity_J_per_K, conductance_W_per_K,
                    initial_temperature_degC, profile, output_step_s)
    c, h = float(heat_capacity_J_per_K), float(conductance_W_per_K)
    initial = float(initial_temperature_degC)
    # Evaluate from each exact event start, so intermediate reporting samples do
    # not perturb state or energy propagated into later intervals.
    start_temperature = initial
    source_before = outward_before = 0.0
    rows = []
    duration = profile[-1]['end_s']
    grid = {0.0, float(duration)}
    grid.update(float(k * output_step_s) for k in range(1, math.ceil(duration/output_step_s)))
    grid.update(float(p['start_s']) for p in profile)
    grid.update(float(p['end_s']) for p in profile)
    grid = sorted(grid)
    segment_index = 0
    for time in grid:
        while segment_index < len(profile)-1 and time >= profile[segment_index]['end_s']:
            previous = profile[segment_index]
            start_temperature, e_in, e_out, _ = exact_interval(start_temperature,
                previous['ambient_temperature_degC'], previous['prescribed_heat_W'], c, h,
                previous['end_s']-previous['start_s'])
            source_before += e_in
            outward_before += e_out
            segment_index += 1
        p = profile[segment_index]
        temperature, e_in, e_out, _ = exact_interval(start_temperature,
            p['ambient_temperature_degC'], p['prescribed_heat_W'], c, h, time-p['start_s'])
        source, outward = source_before + e_in, outward_before + e_out
        stored = c * (temperature-initial)
        rows.append(dict(time_s=time, interval_index=segment_index,
            temperature_degC=temperature, ambient_temperature_degC=p['ambient_temperature_degC'],
            prescribed_heat_W=p['prescribed_heat_W'],
            outward_boundary_heat_W=h*(temperature-p['ambient_temperature_degC']),
            source_energy_J=source, outward_boundary_energy_J=outward,
            stored_energy_change_J=stored, energy_residual_J=source-outward-stored))
    return rows


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False)+'\n', encoding='utf-8')


def run(config_path, output):
    config_path, output = Path(config_path).resolve(), Path(output).resolve()
    config = validate_config(json.loads(config_path.read_text(encoding='utf-8')))
    if output.exists():
        raise ValueError('Output already exists; choose a fresh directory to preserve prior runs')
    kwargs = {k: config[k] for k in ('heat_capacity_J_per_K', 'conductance_W_per_K',
                                    'initial_temperature_degC', 'profile')}
    coarse = simulate(**kwargs, output_step_s=config['output_step_s'])
    fine = simulate(**kwargs, output_step_s=config['comparison_output_step_s'])
    fine_by_time = {r['time_s']: r for r in fine}
    shared = [r for r in coarse if r['time_s'] in fine_by_time]
    maximum_grid_delta = max(abs(r['temperature_degC']-fine_by_time[r['time_s']]['temperature_degC']) for r in shared)
    summary = dict(model=MODEL, scenario_id=config['scenario_id'], evidence_kind='synthetic_only',
        applicability=LABEL, experimental_validation='not performed; awaiting suitable measurements',
        physical_parameter_identification='not attempted; missing applicable heat/cooling/transient evidence',
        electrical_coupling=False, simulation_status='completed',
        final_temperature_degC=coarse[-1]['temperature_degC'],
        minimum_sampled_temperature_degC=min(r['temperature_degC'] for r in coarse),
        maximum_sampled_temperature_degC=max(r['temperature_degC'] for r in coarse),
        final_source_energy_J=coarse[-1]['source_energy_J'],
        final_outward_boundary_energy_J=coarse[-1]['outward_boundary_energy_J'],
        final_stored_energy_change_J=coarse[-1]['stored_energy_change_J'],
        max_absolute_energy_residual_J=max(abs(r['energy_residual_J']) for r in coarse+fine),
        reporting_grid_check=dict(output_steps_s=[config['output_step_s'],config['comparison_output_step_s']],
            coarse_rows=len(coarse), fine_rows=len(fine), shared_timestamps=len(shared),
            max_shared_temperature_difference_degC=maximum_grid_delta,
            interpretation='Exact interval solution; reporting density is not an integration convergence study'),
        conventions=dict(heat='positive into node; excludes separately represented H exchange',
            boundary_heat='positive outward; negative when environment heats node',
            transition_sample='right-hand input at events; temperature and cumulative energy continuous',
            temperature='one lumped mathematical node, not predicted cell core/surface/maximum'),
        decision='insufficient evidence for real-cell or module thermal decisions')
    output.mkdir(parents=True)
    write_json(output/'config_snapshot.json', config)
    for name, rows in [('series.csv',coarse),('series_fine.csv',fine)]:
        with (output/name).open('w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    write_json(output/'summary.json', summary)
    plot(coarse, fine, config, output/'synthetic_heat_balance.png')
    input_paths = [config_path, Path(__file__), ROOT/'tests/test_thermal_prototype.py',
                   REPORT/'PROCEDURE.md', REPORT/'SOURCE_AUDIT.md']
    manifest = dict(schema_version=1, evidence_kind='synthetic_only', python=platform.python_version(),
        input_sha256={p.relative_to(ROOT).as_posix() if p.is_relative_to(ROOT) else str(p):digest(p) for p in input_paths},
        output_sha256={p.name:digest(p) for p in sorted(output.iterdir()) if p.is_file()},
        new_experimental_records_read=0, protected_records_opened=0,
        source_note='Only synthetic configuration used numerically; online metadata/literature audit is documentary.')
    write_json(output/'manifest.json', manifest)
    return summary


def plot(coarse, fine, config, output):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(3, 1, figsize=(10, 9), sharex=True, constrained_layout=True)
    time = [r['time_s'] for r in coarse]
    axes[0].plot([r['time_s'] for r in fine], [r['temperature_degC'] for r in fine], label='Lumped node, exact interval solution')
    axes[0].plot(time, [r['temperature_degC'] for r in coarse], '.', label=f"{config['output_step_s']:g} s reporting grid")
    axes[0].step(time, [r['ambient_temperature_degC'] for r in coarse], where='post', linestyle='--', label='Prescribed ambient')
    axes[0].set_ylabel('Temperature (degC)'); axes[0].legend(loc='upper left', fontsize=8)
    axes[1].step(time, [r['prescribed_heat_W'] for r in coarse], where='post', label='Prescribed signed heat into node')
    # A changed ambient causes an instantaneous boundary-flow jump, while T is
    # continuous. Include both sides rather than drawing a ramp across the step.
    boundary_time, boundary_heat = [], []
    previous_index = 0
    for row in fine:
        index = row['interval_index']
        if index != previous_index:
            boundary_time.append(row['time_s'])
            boundary_heat.append(config['conductance_W_per_K'] *
                (row['temperature_degC']-config['profile'][previous_index]['ambient_temperature_degC']))
        boundary_time.append(row['time_s']); boundary_heat.append(row['outward_boundary_heat_W'])
        previous_index = index
    axes[1].plot(boundary_time, boundary_heat, label='Boundary heat, positive outward')
    axes[1].axhline(0, color='0.5', linewidth=.6); axes[1].set_ylabel('Heat rate (W)'); axes[1].legend(fontsize=8)
    for key, label in [('source_energy_J','Prescribed source'),('outward_boundary_energy_J','Outward boundary'),('stored_energy_change_J','Stored change')]:
        axes[2].plot(time, [r[key] for r in coarse], label=label)
    axes[2].set_ylabel('Signed energy (J)'); axes[2].set_xlabel('Time (s)'); axes[2].legend(fontsize=8)
    for ax in axes:
        ax.grid(alpha=.2)
        for p in config['profile'][1:]: ax.axvline(p['start_s'], color='0.6', linewidth=.5, linestyle=':')
    fig.suptitle('Synthetic one-node heat balance - no real-cell applicability\n'
        f"C_th = {config['heat_capacity_J_per_K']:g} J/K; H = {config['conductance_W_per_K']:g} W/K; no electrical coupling", fontsize=12)
    fig.savefig(output, dpi=150); plt.close(fig)


def verify(output):
    """Verify hashes and exact replay; analytic independence resides in the tests."""
    output = Path(output).resolve()
    manifest = json.loads((output/'manifest.json').read_text(encoding='utf-8'))
    for name, expected in manifest['input_sha256'].items():
        if digest(ROOT/name) != expected: raise ValueError(f'Input changed: {name}')
    for name, expected in manifest['output_sha256'].items():
        if digest(output/name) != expected: raise ValueError(f'Output changed: {name}')
    config = validate_config(json.loads((output/'config_snapshot.json').read_text(encoding='utf-8')))
    kwargs = {k:config[k] for k in ('heat_capacity_J_per_K','conductance_W_per_K','initial_temperature_degC','profile')}
    count = 0
    for filename, step in [('series.csv',config['output_step_s']),('series_fine.csv',config['comparison_output_step_s'])]:
        expected = simulate(**kwargs, output_step_s=step)
        with (output/filename).open(newline='',encoding='utf-8') as f: actual=list(csv.DictReader(f))
        if len(actual) != len(expected): raise ValueError('Saved row count changed')
        for saved, calculated in zip(actual,expected):
            if set(saved) != set(calculated): raise ValueError('Saved columns changed')
            for key, value in calculated.items():
                if float(saved[key]) != value: raise ValueError(f'Saved calculation differs: {filename}/{key}')
            count += 1
    return dict(status='verified', rows_replayed=count, protected_records_opened=0,
        interpretation='Provenance/replay and synthetic mathematics only; no experimental validation')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    run_parser = sub.add_parser('run'); run_parser.add_argument('--config',type=Path,required=True)
    run_parser.add_argument('--out',type=Path,required=True)
    check = sub.add_parser('verify'); check.add_argument('run_directory',type=Path)
    args = parser.parse_args()
    result = run(args.config,args.out) if args.command=='run' else verify(args.run_directory)
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == '__main__':
    main()
