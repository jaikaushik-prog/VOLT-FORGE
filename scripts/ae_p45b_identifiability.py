"""Two predeclared low-SOC resistance candidates on used development evidence."""
import argparse
import csv
from dataclasses import replace
import gzip
import io
import json
import math
from pathlib import Path

import numpy as np
from scipy.optimize import lsq_linear

from ae_p45b_reproduction import ROOT, sha, write_json, metrics, difference, simulate, summarize
from ae_p45b_gitt_replay import load_sources, replay, summarize_gitt, write_predictions, read_csv
from ae_p45b_low_soc import write_csv

CANDIDATES = {'C1_R0': [0], 'C2_R0_R1_R2': [0, 1, 2]}
PARAMETERS = ['delta_R0_Ohm', 'delta_R1_Ohm', 'delta_R2_Ohm']
UPPER = .20
LOCK = 'configs/ae_p45b_identifiability_v1.json'


def low_soc_basis(soc):
    if not math.isfinite(soc):
        raise ValueError('Nonfinite SOC')
    return max(0., (.20-soc)/.20)


class ResistanceTable:
    """Add resistance after interpolation while preserving the original tau(z)."""
    def __init__(self, table, increments):
        self.table = table
        self.increments = np.asarray(increments, dtype=float)
        if self.increments.shape != (3,) or not np.all(np.isfinite(self.increments)):
            raise ValueError('Need three finite resistance increments')
        if np.any(self.increments < 0) or np.any(self.increments > UPPER):
            raise ValueError('Resistance increment outside declared bounds')
        # GITT replay uses these ONLY for unchanged tau/hysteresis memory bounds.
        self.values = table.values

    def query(self, soc, outside='stop'):
        if outside != 'stop':
            raise ValueError('No reference extension in this investigation')
        p, flags = self.table.query(soc, outside)
        delta = self.increments * low_soc_basis(soc)
        if not np.any(delta):
            return p, flags
        r1, r2 = p.r1_Ohm+delta[1], p.r2_Ohm+delta[2]
        if (delta[1] and p.r1_Ohm == 0) or (delta[2] and p.r2_Ohm == 0):
            raise ValueError('Cannot activate a zero-time-constant branch')
        return replace(p, r0_Ohm=p.r0_Ohm+delta[0], r1_Ohm=r1, r2_Ohm=r2,
            c1_F=p.r1_Ohm*p.c1_F/r1 if r1 else p.c1_F,
            c2_F=p.r2_Ohm*p.c2_F/r2 if r2 else p.c2_F), flags


def values(run, key='predicted_voltage_V'):
    return np.array([r[key] if r[key] is not None else np.nan for r in run['rows']])


def make_basis(table, source, segments, case, progress=lambda _: None):
    base = replay(table, source, segments, case)
    if base['stopped'] is not None:
        raise ValueError('Basis undefined: '+str(base['stopped']))
    voltage = values(base)
    matrix = np.zeros((len(source), 3))
    matrix[:, 0] = values(base, 'source_current_A') * np.array([low_soc_basis(z) for z in values(base, 'soc')])
    for j in (1, 2):
        delta = np.zeros(3); delta[j] = .01
        progress(f'{case}: frozen-solver resistance basis {j}')
        perturbed = replay(ResistanceTable(table, delta), source, segments, case)
        if perturbed['stopped'] is not None:
            raise ValueError('Perturbed basis undefined')
        matrix[:, j] = (values(perturbed)-voltage)/.01
    return base, matrix


def phase_weights(times):
    times = np.asarray(times, dtype=float)
    if len(times) < 2 or not np.all(np.isfinite(times)) or np.any(np.diff(times) <= 0):
        raise ValueError('A phase needs at least two strictly ordered times')
    dt = np.diff(times)
    w = np.zeros(len(times)); w[:-1] += dt/2; w[1:] += dt/2
    return w/w.sum()


def allocation(base, segments, pairs, selected_ids=None):
    """Complete pair selection from charge coordinate only, never voltage."""
    rows = base['rows']; groups = []; weights = np.zeros(len(rows))
    for pair in pairs:
        pid = int(pair['pair_index'])
        loaded = rows[int(pair['pulse_last_source_line'])-2]
        include = loaded['soc'] < .20 if selected_ids is None else pid in selected_ids
        if not include:
            continue
        ids = []
        for key in ['pulse_segment_id', 'rest_segment_id']:
            seg = segments[int(pair[key])]
            index = np.arange(int(seg['start_index']), int(seg['end_index'])+1)
            weights[index] = .5*phase_weights([rows[i]['time_s'] for i in index])
            ids.extend(index.tolist())
        groups.append(dict(pair_index=pid, indices=ids,
            pulse_segment_id=int(pair['pulse_segment_id']), rest_segment_id=int(pair['rest_segment_id']),
            loaded_source_line=int(pair['pulse_last_source_line']),
            first_source_line=rows[ids[0]]['source_line'], last_source_line=rows[ids[-1]]['source_line'],
            nominal_soc_loaded=loaded['soc']))
    if len(groups) < 2:
        raise ValueError('Need at least two complete low-SOC pairs')
    weights /= len(groups)
    return groups, weights


def fit(matrix, target, weights, columns, fixed=None):
    matrix = np.asarray(matrix); target = np.asarray(target); weights = np.asarray(weights)
    if matrix.shape != (len(target), 3) or weights.shape != target.shape:
        raise ValueError('Inconsistent design/target/weights')
    if not np.all(np.isfinite(matrix)) or not np.all(np.isfinite(target)):
        raise ValueError('Nonfinite design/target')
    if not np.all(np.isfinite(weights)) or np.any(weights < 0) or weights.sum() <= 0:
        raise ValueError('Invalid fitting weights')
    fixed = fixed or {}; coef = np.zeros(3)
    for j, value in fixed.items():
        if j not in columns or not 0 <= value <= UPPER:
            raise ValueError('Invalid fixed parameter')
        coef[j] = value
    free = [j for j in columns if j not in fixed]
    mask = weights > 0; rootw = np.sqrt(weights[mask]/weights.sum())
    if free:
        result = lsq_linear(matrix[mask][:, free]*rootw[:, None],
            (target[mask]-matrix[mask]@coef)*rootw, bounds=(0., UPPER),
            method='bvls', tol=1e-12)
        if not result.success:
            raise ValueError('Bounded fit did not converge: '+result.message)
        coef[free] = result.x
    error = matrix@coef-target
    objective = float(1000*np.sqrt(np.dot(weights, error**2)/weights.sum()))
    return coef, objective


def identifiability(matrix, target, weights, columns, coef):
    mask = weights > 0
    a = matrix[mask][:, columns]*np.sqrt(weights[mask]/weights.sum())[:, None]
    singular = np.linalg.svd(a, compute_uv=False)
    norms = np.linalg.norm(a, axis=0)
    normalized = a/np.where(norms > 0, norms, 1.)
    sv = np.linalg.svd(normalized, compute_uv=False)
    rank = int(np.linalg.matrix_rank(a))
    condition = float(sv[0]/sv[-1]) if rank == len(columns) else None
    _, best = fit(matrix, target, weights, columns)
    profiles = {}; bands = {}
    for j in columns:
        grid = sorted(set(np.linspace(0, UPPER, 81).tolist()+[float(coef[j])]))
        curve = [dict(value_Ohm=x, objective_rmse_mV=fit(matrix, target, weights, columns, {j:x})[1]) for x in grid]
        near = [p['value_Ohm'] for p in curve if p['objective_rmse_mV'] <= best*1.01+1e-10]
        profiles[PARAMETERS[j]] = curve
        bands[PARAMETERS[j]] = [min(near), max(near)]
    return dict(rank=rank, parameters=len(columns), weighted_singular_values_V_per_Ohm=singular.tolist(),
        normalized_condition_number=condition, column_cosines=(normalized.T@normalized).tolist(),
        active_lower_bounds=[PARAMETERS[j] for j in columns if coef[j] <= 1e-9],
        active_upper_bounds=[PARAMETERS[j] for j in columns if UPPER-coef[j] <= 1e-9],
        profile_grid=profiles, within_1pct_objective_grid_bands_Ohm=bands,
        uncertainty_interpretation='conditional objective sensitivity, NOT confidence intervals; correlated residuals/model discrepancy')


def leave_pair_out(matrix, target, weights, columns, groups):
    prediction = np.full(len(target), np.nan); folds = []
    for group in groups:
        ids = group['indices']; train = weights.copy(); train[ids] = 0
        coef, score = fit(matrix, target, train, columns)
        prediction[ids] = matrix[ids]@coef
        folds.append(dict(pair_index=group['pair_index'], increments_Ohm=coef.tolist(),
            training_objective_rmse_mV=score))
    error = prediction-target
    mask = weights > 0
    score = float(1000*np.sqrt(np.dot(weights[mask], error[mask]**2)/weights[mask].sum()))
    coefs = np.array([r['increments_Ohm'] for r in folds])
    return prediction, dict(objective_rmse_mV=score, folds=folds,
        increments_min_Ohm=coefs.min(axis=0).tolist(), increments_max_Ohm=coefs.max(axis=0).tolist(),
        evidence='leave-complete-pair-out development diagnostic on previously opened GITT; not fresh assessment')


def vector_run(base, predicted):
    run = {k:v for k,v in base.items() if k != 'rows'}; rows = []
    for original, y in zip(base['rows'], predicted):
        row = dict(original); valid = bool(np.isfinite(y))
        row.update(predicted_voltage_V=float(y) if valid else None,
            residual_V=float(y-row['voltage_V']) if valid else None)
        rows.append(row)
    run['rows'] = rows
    return run


def subset_metrics(base, predicted, groups):
    run = vector_run(base, predicted); selected = np.zeros(len(predicted), dtype=bool)
    for g in groups: selected[g['indices']] = True
    return {label:metrics(run['rows'], selected & np.array([r['direction']==label for r in run['rows']]))
        for label in ['discharge', 'rest']}


def screening(base, baseline_pairs, cv_run, cv_pairs, groups, baseline_objective, cv_objective):
    selected = {g['pair_index'] for g in groups}
    b = [p for p in baseline_pairs if int(p['pair_index']) in selected]
    c = [p for p in cv_pairs if int(p['pair_index']) in selected]
    bm = subset_metrics(base, values(base), groups)
    cm = subset_metrics(base, values(cv_run), groups)
    def maximum(rows, key): return max(abs(p[key]) for p in rows)
    checks = dict(objective_improves_20pct=cv_objective <= .8*baseline_objective,
        pulse_time_rmse_not_worse=cm['discharge']['time_rmse_mV'] <= bm['discharge']['time_rmse_mV'],
        rest_time_rmse_not_worse=cm['rest']['time_rmse_mV'] <= bm['rest']['time_rmse_mV'],
        loaded_endpoint_max_improves_20pct=maximum(c,'loaded_error_mV') <= .8*maximum(b,'loaded_error_mV'),
        late_rest_median_max_degrades_at_most_5mV=maximum(c,'late_median_difference_mV') <= maximum(b,'late_median_difference_mV')+5)
    checks = {key: bool(value) for key, value in checks.items()}
    return dict(checks=checks, all_pass=all(checks.values()), baseline_phase_metrics=bm,
        cv_phase_metrics=cm, baseline_loaded_max_mV=maximum(b,'loaded_error_mV'),
        cv_loaded_max_mV=maximum(c,'loaded_error_mV'), baseline_late_rest_max_mV=maximum(b,'late_median_difference_mV'),
        cv_late_rest_max_mV=maximum(c,'late_median_difference_mV'),
        interpretation='proposed development screen only; never application acceptance or automatic adoption')


def compact_csv(path, rows):
    stream = io.StringIO(newline=''); writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
    writer.writeheader(); writer.writerows(rows)
    with path.open('xb') as output: output.write(gzip.compress(stream.getvalue().encode(), mtime=0))


def load_lock():
    lock = json.loads((ROOT/LOCK).read_text())
    for name, expected in lock['frozen_files'].items():
        if sha(ROOT/name) != expected: raise ValueError('Frozen dependency changed: '+name)
    return lock


def plots(base, direct, all_pairs, groups, fits, out):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    t = values(base, 'time_s')/3600; measured = values(base, 'voltage_V')
    runs = {'B0':base, **direct}; colors = {'B0':'#667582','C1_R0':'#ce8730','C2_R0_R1_R2':'#197e8c'}
    fig, axes = plt.subplots(3, 1, figsize=(12, 9), sharex=True, constrained_layout=True)
    axes[0].plot(t, measured, color='#252d34', lw=.7, label='Measured')
    for name, run in runs.items():
        y = values(run)
        axes[0].plot(t,y,lw=.7,label=name,color=colors[name])
        axes[1].plot(t,1000*(y-measured),lw=.7,label=name,color=colors[name])
    axes[2].plot(t,values(base,'source_current_A'),lw=.7,color='#252d34')
    for ax, label in zip(axes,['Voltage (V)','Prediction - measured (mV)','Current (A), charge positive']):
        ax.set_ylabel(label); ax.grid(alpha=.2)
    axes[0].legend(); axes[1].legend(); axes[-1].set_xlabel('Recorded time (h)')
    fig.suptitle('P45B 25 degC GITT: two conditional resistance fits\nUsed development evidence; source lines preserved in CSV.gz; no model adoption')
    fig.savefig(out/'gitt_comparison.png',dpi=140); plt.close(fig)
    pairs = all_pairs['B0']; chosen = list(dict.fromkeys([min(range(len(pairs)),key=lambda i:abs(pairs[i]['nominal_soc_loaded']-z)) for z in [.1,.04]]+[len(pairs)-1]))
    fig, axes = plt.subplots(len(chosen),2,figsize=(13,3.2*len(chosen)),constrained_layout=True,squeeze=False)
    for axs, index in zip(axes, chosen):
        pair = pairs[index]
        # All rows in the pulse segment through the final rest sample.
        ids = [i for i,r in enumerate(base['rows']) if int(pair['pulse_segment_id']) <= r['segment_id'] <= int(pair['rest_segment_id'])]
        x = values(base,'time_s')[ids]-base['rows'][int(pair['rest_first_source_line'])-2]['time_s']
        axs[0].plot(x,measured[ids],color='#252d34',label='Measured')
        for name,run in runs.items():
            y = values(run)[ids]
            axs[0].plot(x,y,color=colors[name],lw=1,label=name)
            axs[1].plot(x,1000*(y-measured[ids]),color=colors[name],lw=1)
        axs[0].set_title(f"Pair {index}, SOC {pair['nominal_soc_loaded']:.4f}, source lines {ids[0]+2}-{ids[-1]+2}")
        axs[0].set_ylabel('Voltage (V)'); axs[1].set_ylabel('Residual (mV)')
        for ax in axs:
            ax.set_xscale('symlog',linthresh=1); ax.set_xlabel('Seconds from first rest sample'); ax.grid(alpha=.2)
    axes[0,0].legend(fontsize=8)
    fig.suptitle('Complete pulse/rest sequences selected by SOC\nFinite-rest voltage is not equilibrium OCV; fitting diagnostics, not independent tests')
    fig.savefig(out/'complete_sequences.png',dpi=140); plt.close(fig)
    fig, axes = plt.subplots(1,3,figsize=(13,4),constrained_layout=True)
    for name, desc in fits.items():
        for j, key in enumerate(PARAMETERS):
            curve = desc['identifiability']['profile_grid'].get(key)
            if curve:
                axes[j].plot([p['value_Ohm']*1000 for p in curve],[p['objective_rmse_mV'] for p in curve],label=name,color=colors[name])
    for j,ax in enumerate(axes):
        ax.set_xlabel(PARAMETERS[j].replace('_Ohm','')+' (mOhm)'); ax.set_ylabel('Profile objective RMSE (mV)'); ax.grid(alpha=.2)
    axes[0].legend(fontsize=8)
    fig.suptitle('Conditional parameter profiles: reoptimize other allowed resistances\nObjective sensitivity, not confidence intervals')
    fig.savefig(out/'parameter_profiles.png',dpi=140); plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--out',type=Path,required=True)
    out = parser.parse_args().out.resolve()
    if not any(out.is_relative_to(ROOT/n) for n in ['reports','tmp','workspace']):
        raise SystemExit('Outputs must be under reports/, tmp/ or workspace/.')
    if out.exists(): raise SystemExit('Use a new output directory; preserve existing results.')
    lock = load_lock(); table, source, segments, pairs, _ = load_sources()
    out.mkdir(parents=True)
    progress = lambda message: print(message,flush=True)
    base, matrix = make_basis(table,source,segments,'primary',progress)
    frozen = read_csv_gz(ROOT/'reports/p45b_gitt_replay_v1/run_001/primary.csv.gz')
    baseline_delta = float(max(abs(values(base)-np.array([float(r['predicted_voltage_V']) for r in frozen]))))
    if baseline_delta > 1e-12: raise ValueError('Baseline reproduction mismatch')
    groups, weights = allocation(base,segments,pairs)
    write_json(out/'pair_allocation.json',[{k:v for k,v in g.items() if k!='indices'} for g in groups])
    np.savez_compressed(out/'basis_primary.npz',matrix=matrix,weights=weights,
        voltage=values(base),measured=values(base,'voltage_V'),soc=values(base,'soc'))
    target = values(base,'voltage_V')-values(base)
    baseline_score = float(1000*np.sqrt(np.dot(weights,target**2)))
    summaries = {}; all_pairs = {}; fits = {}; direct = {}; cv_columns = {}
    summaries['B0'], seg, all_pairs['B0'] = summarize_gitt(base,segments,pairs)
    write_csv(out/'B0_pairs.csv',all_pairs['B0'])
    for name, columns in CANDIDATES.items():
        progress('Fitting '+name)
        coef, score = fit(matrix,target,weights,columns)
        cv, cross = leave_pair_out(matrix,target,weights,columns,groups)
        affine = values(base)+matrix@coef
        progress('Direct and fine-step frozen-solver verification '+name)
        run = replay(ResistanceTable(table,coef),source,segments,'primary')
        fine = replay(ResistanceTable(table,coef),source,segments,'fine_step')
        if run['stopped'] or fine['stopped']: raise ValueError('Candidate numerical verification stopped')
        closure = float(np.max(abs(values(run)-affine)))
        if closure > 1e-8: raise ValueError('Affine/direct mismatch')
        direct[name] = run; write_predictions(out/(name+'.csv.gz'),run['rows'])
        summaries[name], seg, all_pairs[name] = summarize_gitt(run,segments,pairs)
        write_csv(out/(name+'_segments.csv'),seg); write_csv(out/(name+'_pairs.csv'),all_pairs[name])
        cv_run = vector_run(base,values(base)+cv)
        for group, fold in zip(groups, cross['folds']):
            cc = fold['increments_Ohm']
            for i in group['indices']:
                row = cv_run['rows'][i]
                row['v1_V'] += matrix[i,1]*cc[1]
                row['v2_V'] += matrix[i,2]*cc[2]
                row['ohmic_V'] += matrix[i,0]*cc[0]
                row['closure_mV'] = 1000*(row['reference_V']+row['ohmic_V']+row['v1_V']+row['v2_V']-row['predicted_voltage_V'])
        _, _, cv_pairs = summarize_gitt(cv_run,segments,pairs)
        write_csv(out/(name+'_leave_pair_out_pairs.csv'),cv_pairs)
        cv_columns[name] = values(cv_run)
        fits[name] = dict(increments_Ohm=coef.tolist(),objective_rmse_mV=score,
            identifiability=identifiability(matrix,target,weights,columns,coef),leave_pair_out=cross,
            screening=screening(base,all_pairs['B0'],cv_run,cv_pairs,groups,baseline_score,cross['objective_rmse_mV']),
            max_affine_direct_difference_V=closure,time_step=difference(run,fine))
        fits[name]['time_step']['proposed_0p1_mV_check_met'] = fits[name]['time_step']['max_abs_voltage_difference_mV'] <= .1
        progress(json.dumps(dict(candidate=name,coef=coef.tolist(),fit_score=score,cv_score=cross['objective_rmse_mV'],screens=fits[name]['screening']['checks'])))
    cv_rows = []
    for i,r in enumerate(base['rows']):
        item = {k:r[k] for k in ['source_line','time_s','source_current_A','voltage_V','soc']}
        item['fitting_weight'] = float(weights[i]); item['baseline_V'] = r['predicted_voltage_V']
        for name,y in cv_columns.items(): item[name+'_V'] = float(y[i]) if np.isfinite(y[i]) else None
        cv_rows.append(item)
    compact_csv(out/'leave_pair_out.csv.gz',cv_rows)
    progress('Declared initial-SOC sensitivity: same allocation, fixed reference')
    shifted, shifted_matrix = make_basis(table,source,segments,'initial_soc_minus_0p005',progress)
    np.savez_compressed(out/'basis_soc_minus_0p005.npz',matrix=shifted_matrix,voltage=values(shifted),soc=values(shifted,'soc'))
    sensitivity = {}
    for name,columns in CANDIDATES.items():
        refit, score = fit(shifted_matrix,values(shifted,'voltage_V')-values(shifted),weights,columns)
        held = values(shifted)+shifted_matrix@np.array(fits[name]['increments_Ohm'])
        y = values(shifted)+shifted_matrix@refit
        sensitivity[name] = dict(primary_parameters_Ohm=fits[name]['increments_Ohm'],refitted_parameters_Ohm=refit.tolist(),
            refitted_objective_rmse_mV=score,unchanged_parameters_metrics=metrics(vector_run(shifted,held)['rows']),
            refitted_metrics=metrics(vector_run(shifted,y)['rows']),
            max_unchanged_parameter_voltage_shift_mV=float(1000*np.max(abs(held-values(direct[name])))),
            interpretation='sensitivity scenario; conditional refit, not selected calibration or uncertainty bound')
    shifted_rows = []; shifted_voltage = values(shifted)
    for i,r in enumerate(shifted['rows']):
        row = {k:r[k] for k in ['source_line','time_s','source_current_A','voltage_V','soc']}
        row['baseline_V'] = r['predicted_voltage_V']
        for name,d in sensitivity.items():
            row[name+'_held_V'] = float(shifted_voltage[i]+shifted_matrix[i]@np.array(d['primary_parameters_Ohm']))
            row[name+'_refit_V'] = float(shifted_voltage[i]+shifted_matrix[i]@np.array(d['refitted_parameters_Ohm']))
        shifted_rows.append(row)
    compact_csv(out/'soc_sensitivity.csv.gz',shifted_rows)
    progress('Complete previously used 1C transfer check; not fitting or fresh assessment')
    one_source = []
    for r in read_csv(ROOT/lock['used_1C_trace']):
        row = {k:float(r[k]) for k in ['time_s','source_current_A','voltage_V','controlled_temperature_degC']}
        row['source_line'] = int(r['source_line']); one_source.append(row)
    one_summaries = {}; one_rows = []
    for name,coef in [('B0',[0.,0.,0.])]+[(k,v['increments_Ohm']) for k,v in fits.items()]:
        run = simulate(ResistanceTable(table,coef),one_source)
        one_summaries[name] = summarize(run)
        if not one_rows:
            one_rows = [{k:r[k] for k in ['source_line','time_s','source_current_A','voltage_V']} for r in run['rows']]
        for item,r in zip(one_rows,run['rows']): item[name+'_V'] = r['predicted_voltage_V']
    compact_csv(out/'used_1C_transfer.csv.gz',one_rows)
    selected = next((name for name in CANDIDATES if fits[name]['screening']['all_pass']),None)
    summary = dict(schema_version='voltforge.ae_p45b_identifiability/1',source_lock=lock,
        baseline_reproduction_max_difference_V=baseline_delta,baseline_objective_rmse_mV=baseline_score,
        selected_pair_ids=[g['pair_index'] for g in groups],fits=fits,runs=summaries,
        initial_soc_sensitivity=sensitivity,used_1C_transfer=one_summaries,
        candidate_for_further_review_only=selected,model_adopted=False,new_measurement_families_opened=0,
        remaining_unopened_members=48,remaining_unopened_families=40,
        fresh_independent_assessment=False,requirement_status='requirement not configured',
        experimental_module_validation='awaiting suitable measurements',
        implementation_sha256={n:sha(ROOT/n) for n in ['scripts/ae_p45b_identifiability.py','tests/test_ae_p45b_identifiability.py',
            'scripts/ae_p45b_gitt_replay.py','scripts/ae_p45b_reproduction.py','scripts/ae_p45b_equations.py']})
    write_json(out/'summary.json',summary)
    plots(base,direct,all_pairs,groups,fits,out)
    write_json(out/'manifest.json',{p.name:sha(p) for p in sorted(out.iterdir()) if p.is_file()})
    progress('Completed bounded investigation. No model adopted; no unused outcomes opened.')


def read_csv_gz(path):
    with gzip.open(path,'rt',newline='',encoding='utf-8') as stream: return list(csv.DictReader(stream))


if __name__ == '__main__': main()
