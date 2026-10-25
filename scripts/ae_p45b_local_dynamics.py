"""Bounded local two-RC diagnostics on already-opened complete GITT pairs.

No parameters are installed into a product model. Fitted local descriptions
are conditional, in-sample diagnostics, not predictions on held-out evidence.
"""
import argparse
import csv
import gzip
import io
import json
import math
from pathlib import Path

import numpy as np
from scipy.optimize import lsq_linear

from ae_p45b_reproduction import ROOT, Table25, sha, write_json
from ae_p45b_identifiability import phase_weights, compact_csv

LOCK = 'configs/ae_p45b_local_dynamics_v1.json'
MULTIPLIERS = (.25, .5, 1., 2., 4., 8., 16.)
LOWER = np.array([0., 1e-6, 1e-6])
UPPER = np.array([.20, .20, .20])
MODELS = ('B0', 'L0', 'LR', 'LRT')
IMPLEMENTATIONS = ['scripts/ae_p45b_local_dynamics.py',
                   'scripts/verify_p45b_local_dynamics.py',
                   'tests/test_ae_p45b_local_dynamics.py']


def read_csv(path):
    opener = gzip.open if Path(path).suffix == '.gz' else open
    with opener(path, 'rt', encoding='utf-8', newline='') as stream:
        return list(csv.DictReader(stream))


def column(rows, key):
    return np.array([float(r[key]) for r in rows])


def rc_basis(times, current, tau):
    """Exact response per ohm and memory fraction at original timestamps."""
    times, current = np.asarray(times, float), np.asarray(current, float)
    if times.ndim != 1 or len(times) < 2 or times.shape != current.shape:
        raise ValueError('Need matching time/current vectors with two samples')
    if not np.all(np.isfinite(times)) or not np.all(np.isfinite(current)):
        raise ValueError('Nonfinite time/current')
    if np.any(np.diff(times) <= 0) or not math.isfinite(tau) or tau <= 0:
        raise ValueError('Strictly increasing times and positive finite tau required')
    basis = np.zeros(len(times))
    for n, dt in enumerate(np.diff(times)):
        alpha = -math.expm1(-dt/tau)
        basis[n+1] = basis[n] + (current[n]-basis[n])*alpha
    return basis, np.exp(-(times-times[0])/tau)


def design(times, current, tau, initial):
    tau, initial = np.asarray(tau, float), np.asarray(initial, float)
    if tau.shape != (2,) or initial.shape != (2,) or not np.all(np.isfinite(initial)):
        raise ValueError('Two finite initial RC voltages and two taus required')
    if tau[0] >= tau[1]:
        raise ValueError('Require tau1 < tau2')
    b1, m1 = rc_basis(times, current, tau[0])
    b2, m2 = rc_basis(times, current, tau[1])
    return np.column_stack([current, b1, b2]), initial[0]*m1+initial[1]*m2


def pair_weights(times, rest_start):
    if not isinstance(rest_start, (int, np.integer)) or not 2 <= rest_start <= len(times)-2:
        raise ValueError('Need complete pulse and rest with at least two samples each')
    return np.r_[.5*phase_weights(times[:rest_start]), .5*phase_weights(times[rest_start:])]


def fit_resistance(matrix, target, weights):
    matrix, target, weights = map(np.asarray, (matrix, target, weights))
    if matrix.shape != (len(target), 3) or target.shape != weights.shape:
        raise ValueError('Inconsistent fit arrays')
    if not all(np.all(np.isfinite(x)) for x in (matrix, target, weights)):
        raise ValueError('Nonfinite fit input')
    if np.any(weights < 0) or weights.sum() <= 0:
        raise ValueError('Invalid weights')
    root = np.sqrt(weights/weights.sum())
    solution = lsq_linear(matrix*root[:, None], target*root,
        bounds=(LOWER, UPPER), method='bvls', tol=1e-12)
    if not solution.success:
        raise ValueError('Resistance fit failed: '+solution.message)
    error = matrix@solution.x-target
    score = float(1000*np.sqrt(np.dot(weights, error**2)/weights.sum()))
    return solution.x, score


def grid_fit(times, current, reference, measured, initial, published_tau, weights):
    published_tau = np.asarray(published_tau, float)
    if published_tau.shape != (2,) or np.any(published_tau <= 0) or not np.all(np.isfinite(published_tau)):
        raise ValueError('Invalid published tau')
    basis = {float(t): rc_basis(times, current, t)
             for tau in published_tau for t in tau*np.array(MULTIPLIERS)}
    grid = []
    for m1 in MULTIPLIERS:
        for m2 in MULTIPLIERS:
            tau = published_tau*np.array([m1, m2])
            if tau[0] >= tau[1]:
                continue
            b1, h1 = basis[float(tau[0])]; b2, h2 = basis[float(tau[1])]
            a = np.column_stack([current, b1, b2])
            target = measured-reference-initial[0]*h1-initial[1]*h2
            resistance, score = fit_resistance(a, target, weights)
            grid.append(dict(multipliers=[m1, m2], tau_s=tau.tolist(),
                resistance_Ohm=resistance.tolist(), objective_rmse_mV=score))
    if not grid:
        raise ValueError('No ordered tau grid points')
    chosen = min(grid, key=lambda r:r['objective_rmse_mV'])
    return chosen, grid


def prediction(times, current, reference, resistance, tau, initial):
    a, memory = design(times, current, tau, initial)
    return reference+memory+a@np.asarray(resistance)


def describe_identifiability(times, current, weights, initial, fitted, grid):
    a, _ = design(times, current, fitted['tau_s'], initial)
    a = a*np.sqrt(weights/weights.sum())[:, None]
    norm = np.linalg.norm(a, axis=0)
    normalized = a/np.where(norm, norm, 1)
    singular = np.linalg.svd(normalized, compute_uv=False)
    rank = int(np.linalg.matrix_rank(a))
    near = [g for g in grid if g['objective_rmse_mV'] <= fitted['objective_rmse_mV']*1.01+1e-10]
    profiles = []
    for j in range(2):
        profile = []
        for m in MULTIPLIERS:
            group = [g for g in grid if g['multipliers'][j] == m]
            if group:
                best = min(group, key=lambda g:g['objective_rmse_mV'])
                profile.append(dict(multiplier=m, tau_s=best['tau_s'][j],
                    objective_rmse_mV=best['objective_rmse_mV']))
        profiles.append(profile)
    r = np.asarray(fitted['resistance_Ohm'])
    return dict(rank=rank, normalized_condition_number=float(singular[0]/singular[-1]) if rank==3 else None,
        column_cosines=(normalized.T@normalized).tolist(),
        active_lower_bounds=np.flatnonzero(r-LOWER < 1e-9).tolist(),
        active_upper_bounds=np.flatnonzero(UPPER-r < 1e-9).tolist(),
        tau_grid_boundary=[bool(m in (MULTIPLIERS[0], MULTIPLIERS[-1])) for m in fitted['multipliers']],
        tau_within_1pct_grid_range_s=[[min(g['tau_s'][j] for g in near), max(g['tau_s'][j] for g in near)] for j in range(2)],
        near_optimal_grid_points=len(near), total_grid_points=len(grid),
        flat_profile_flags=[len({g['multipliers'][j] for g in near}) >= 4 for j in range(2)],
        tau_profiles=profiles,
        uncertainty='conditional finite-grid objective sensitivity, NOT confidence intervals or unique mechanisms')


def error_metrics(times, measured, predicted):
    e = 1000*(np.asarray(predicted)-measured)
    w = phase_weights(times)
    return dict(samples=len(e), duration_s=float(times[-1]-times[0]),
        sample_rmse_mV=float(np.sqrt(np.mean(e**2))), sample_bias_mV=float(e.mean()),
        time_rmse_mV=float(np.sqrt(np.dot(w,e**2))), time_bias_mV=float(np.dot(w,e)),
        max_abs_error_mV=float(np.max(abs(e))))


def pair_metrics(times, measured, predicted, rest_start, weights):
    late = times >= times[-1]-60
    rest = slice(rest_start, None)
    center_error = (predicted[rest]-np.median(predicted[late]))-(measured[rest]-np.median(measured[late]))
    return dict(full=error_metrics(times, measured, predicted),
        pulse=error_metrics(times[:rest_start], measured[:rest_start], predicted[:rest_start]),
        rest=error_metrics(times[rest], measured[rest], predicted[rest]),
        objective_rmse_mV=float(1000*np.sqrt(np.dot(weights,(predicted-measured)**2))),
        loaded_end_error_mV=float(1000*(predicted[rest_start-1]-measured[rest_start-1])),
        late_rest_median_error_mV=float(1000*(np.median(predicted[late])-np.median(measured[late]))),
        centered_rest_time_rmse_mV=float(1000*np.sqrt(np.dot(phase_weights(times[rest]),center_error**2))),
        measured_loaded_to_late_recovery_mV=float(1000*(np.median(measured[late])-measured[rest_start-1])),
        described_loaded_to_late_recovery_mV=float(1000*(np.median(predicted[late])-predicted[rest_start-1])))


def load_sources():
    lock = json.loads((ROOT/LOCK).read_text())
    for name, expected in lock['frozen_files'].items():
        if sha(ROOT/name) != expected:
            raise ValueError('Frozen source changed: '+name)
    source = read_csv(ROOT/lock['saved_samples'])
    segments = read_csv(ROOT/lock['saved_segments'])
    groups = json.loads((ROOT/lock['saved_allocation']).read_text())
    if [g['pair_index'] for g in groups] != list(range(21,32)):
        raise ValueError('Allocation must retain exactly complete pairs 21-31')
    replays = {k:read_csv(ROOT/v) for k,v in lock['saved_replays'].items()}
    for rows in replays.values():
        for key in ('source_line','time_s','source_current_A','voltage_V'):
            if not np.array_equal(column(rows,key),column(source,key)):
                raise ValueError('Replay/source mismatch: '+key)
    return lock, Table25((ROOT/lock['parameter_table']).read_bytes()), source, segments, groups, replays


def analyze_pair(table, source, segments, group, replay):
    first, last = group['first_source_line']-2, group['last_source_line']-2
    ids = np.arange(first,last+1)
    rest_segment = segments[group['rest_segment_id']]
    rest_start = int(rest_segment['start_index'])-first
    pulse_segment = segments[group['pulse_segment_id']]
    if first != int(pulse_segment['start_index']) or last != int(rest_segment['end_index']):
        raise ValueError('Pair does not preserve complete phases')
    rows = [replay[i] for i in ids]
    t, current, measured, reference = [column(rows,k) for k in ('time_s','source_current_A','voltage_V','reference_V')]
    soc = column(rows,'soc')
    for z in soc:
        table.query(z)  # Fail rather than extend reference support.
    initial = [float(rows[0]['v1_V']),float(rows[0]['v2_V'])]
    p, _ = table.query(float(soc[rest_start-1]))
    published_tau = np.array([p.r1_Ohm*p.c1_F,p.r2_Ohm*p.c2_F])
    published_r = np.array([p.r0_Ohm,p.r1_Ohm,p.r2_Ohm])
    weights = pair_weights(t,rest_start)
    a, memory = design(t,current,published_tau,initial)
    local_r, score = fit_resistance(a,measured-reference-memory,weights)
    chosen, grid = grid_fit(t,current,reference,measured,initial,published_tau,weights)
    predicted = dict(B0=column(rows,'predicted_voltage_V'), L0=reference+memory+a@published_r,
        LR=reference+memory+a@local_r,
        LRT=prediction(t,current,reference,chosen['resistance_Ohm'],chosen['tau_s'],initial))
    past = source[:first+1]
    past_t,past_i = column(past,'time_s'),column(past,'source_current_A')
    history_initial = [float(rc_basis(past_t,past_i,tau)[0][-1]*r)
        for tau,r in zip(chosen['tau_s'],chosen['resistance_Ohm'][1:])]
    history = prediction(t,current,reference,chosen['resistance_Ohm'],chosen['tau_s'],history_initial)
    previous = segments[group['pulse_segment_id']-1]
    previous_rest_s = float(previous['duration_s']) if previous['phase']=='rest' else 0.
    desc = dict(pair_index=group['pair_index'],first_source_line=first+2,last_source_line=last+2,
        rest_first_source_line=first+rest_start+2,nominal_loaded_soc=float(soc[rest_start-1]),
        pair_soc_range=[float(soc.min()),float(soc.max())], local_initial_RC_V=initial,
        published_resistance_Ohm=published_r.tolist(), published_tau_s=published_tau.tolist(),
        LR_resistance_Ohm=local_r.tolist(), LR_objective_rmse_mV=score, LRT=chosen,
        identifiability=describe_identifiability(t,current,weights,initial,chosen,grid),
        grid=grid, metrics={name:pair_metrics(t,measured,y,rest_start,weights) for name,y in predicted.items()},
        sampling=dict(pulse_duration_s=float(t[rest_start-1]-t[0]),rest_duration_s=float(t[-1]-t[rest_start]),
            transition_sample_gap_s=float(t[rest_start]-t[rest_start-1]),
            min_sample_dt_s=float(np.diff(t).min()),max_sample_dt_s=float(np.diff(t).max())),
        conditional_initial_polarization_sensitivity=dict(
            initial_RC_from_constant_local_history_V=history_initial,
            previous_rest_duration_s=previous_rest_s,
            previous_rest_memory_fraction=[math.exp(-previous_rest_s/tau) for tau in chosen['tau_s']],
            maximum_voltage_shift_mV=float(1000*np.max(abs(history-predicted['LRT']))),
            metrics=pair_metrics(t,measured,history,rest_start,weights),
            interpretation='sensitivity only: local fitted parameters assumed throughout past SOCs; states not measured; no refit'))
    exported = []
    for j,i in enumerate(ids):
        item = dict(pair_index=group['pair_index'],source_line=i+2,time_s=float(t[j]),
            source_current_A=float(current[j]),voltage_V=float(measured[j]),
            controlled_temperature_degC=float(source[i]['controlled_temperature_degC']),
            soc=float(soc[j]),reference_V=float(reference[j]), phase='pulse' if j<rest_start else 'rest',
            weight=float(weights[j]),**{name+'_V':float(y[j]) for name,y in predicted.items()},
            LRT_history_sensitivity_V=float(history[j]))
        exported.append(item)
    return desc,exported


def plots(results,out):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    primary = results['primary']; pairs=primary['pairs']; rows=primary['rows']
    chosen=list(dict.fromkeys([min(pairs,key=lambda p:abs(p['nominal_loaded_soc']-z))['pair_index'] for z in [.1,.04]]+[pairs[-1]['pair_index']]))
    colors={'B0':'#777777','L0':'#a99a7d','LR':'#bd7925','LRT':'#157b8b'}
    fig,axes=plt.subplots(len(chosen),2,figsize=(13,3.6*len(chosen)),constrained_layout=True)
    for axs,pid in zip(axes,chosen):
        group=[r for r in rows if r['pair_index']==pid]
        t=column(group,'time_s'); t-=t[0]; measured=column(group,'voltage_V')
        axs[0].plot(t,measured,color='#20262c',lw=1,label='Measured')
        for name in MODELS:
            y=column(group,name+'_V')
            axs[0].plot(t,y,color=colors[name],lw=.9,label=name)
            axs[1].plot(t,1000*(y-measured),color=colors[name],lw=.9,label=name)
        transition=next(t[i] for i,r in enumerate(group) if r['phase']=='rest')
        for ax in axs:
            ax.axvline(transition,color='#888888',lw=.6,ls=':'); ax.grid(alpha=.2); ax.set_xlabel('Time from pulse start (s)')
        axs[0].set_ylabel(f'Pair {pid}: voltage (V)');axs[1].set_ylabel('Description - measured (mV)')
    axes[0,0].legend(ncol=3,fontsize=8)
    fig.suptitle('Previously opened complete pulse/rest pairs: conditional local descriptions\nSource: saved About:Energy P45B 25 degC GITT, source-line mapping in CSV; no fresh validation')
    fig.savefig(out/'complete_pairs.png',dpi=150);plt.close(fig)
    fig,axes=plt.subplots(3,2,figsize=(13,11),constrained_layout=True)
    for scenario,result in results.items():
        ps=result['pairs'];x=[p['nominal_loaded_soc'] for p in ps];style='-' if scenario=='primary' else '--'
        for name in MODELS:
            axes[0,0].plot(x,[p['metrics'][name]['objective_rmse_mV'] for p in ps],style,color=colors[name],label=f'{scenario} {name}')
            axes[0,1].plot(x,[p['metrics'][name]['centered_rest_time_rmse_mV'] for p in ps],style,color=colors[name])
        for j in range(3):
            axes[1,0].plot(x,[1000*p['LR_resistance_Ohm'][j] for p in ps],style,marker='.',label=f'{scenario} R{j}')
        for j in range(2):
            axes[1,1].plot(x,[p['LRT']['tau_s'][j] for p in ps],style,marker='.',label=f'{scenario} tau{j+1}')
        axes[2,0].plot(x,[p['conditional_initial_polarization_sensitivity']['maximum_voltage_shift_mV'] for p in ps],style,marker='.',label=scenario)
        axes[2,1].plot(x,[p['identifiability']['near_optimal_grid_points'] for p in ps],style,marker='.',label=scenario)
    for ax,label in zip(axes.flat,['Balanced objective RMSE (mV)','Centered-rest time RMSE (mV)','Fixed-tau local resistance (mOhm)','Grid-selected time constants (s)','Conditional-history voltage shift (mV)','Grid points within 1% objective']):
        ax.set_ylabel(label);ax.set_xlabel('Assumed loaded-end nominal SOC');ax.grid(alpha=.2)
    axes[1,1].set_yscale('log');axes[0,0].legend(fontsize=7,ncol=2);axes[1,0].legend(fontsize=7,ncol=2);axes[1,1].legend(fontsize=7);axes[2,0].legend(fontsize=8)
    fig.suptitle('All 11 complete pairs, both linked origin/reference assumptions\nIn-sample local diagnostics; no global SOC law, confidence interval or protocol-transfer claim')
    fig.savefig(out/'local_diagnostics.png',dpi=150);plt.close(fig)
    fig,axes=plt.subplots(3,4,figsize=(15,10),constrained_layout=True)
    for ax,p in zip(axes.flat,pairs):
        for j,profile in enumerate(p['identifiability']['tau_profiles']):
            ax.plot([g['tau_s'] for g in profile],[g['objective_rmse_mV'] for g in profile],'.-',label=f'tau{j+1}')
        ax.axhline(p['LRT']['objective_rmse_mV']*1.01,color='#999999',ls=':',lw=.7)
        ax.set_xscale('log');ax.set_title(f"Pair {p['pair_index']}; SOC {p['nominal_loaded_soc']:.3f}");ax.set_xlabel('Time constant (s)');ax.set_ylabel('Profile RMSE (mV)');ax.grid(alpha=.2)
    axes.flat[-1].axis('off');axes.flat[0].legend(fontsize=8)
    fig.suptitle('Primary finite-grid objective profiles: other tau and resistances reoptimized\nOnly tested grid support; not confidence intervals or nonlinear global optimality')
    fig.savefig(out/'tau_profiles.png',dpi=150);plt.close(fig)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args();out=args.out.resolve()
    if not any(out.is_relative_to(ROOT/name) for name in ('tmp','reports')):
        raise SystemExit('Output must be under tmp/ or reports/')
    if out.exists():
        raise SystemExit('Refuse to overwrite an existing output path')
    lock,table,source,segments,groups,replays=load_sources()
    out.mkdir(parents=True);results={}
    for scenario,replay in replays.items():
        pairs=[];rows=[]
        for g in groups:
            print(f"{scenario}: complete pair {g['pair_index']}",flush=True)
            desc,exported=analyze_pair(table,source,segments,g,replay)
            pairs.append(desc);rows.extend(exported)
        results[scenario]=dict(pairs=pairs,rows=rows)
        compact_csv(out/(scenario+'.csv.gz'),rows)
        write_json(out/(scenario+'_pairs.json'),pairs)
    plots(results,out)
    aggregates={scenario:{name:dict(
        equal_pair_phase_objective_rmse_mV=float(np.sqrt(np.mean([p['metrics'][name]['objective_rmse_mV']**2 for p in result['pairs']]))),
        maximum_loaded_end_abs_error_mV=float(max(abs(p['metrics'][name]['loaded_end_error_mV']) for p in result['pairs'])),
        maximum_late_rest_median_abs_error_mV=float(max(abs(p['metrics'][name]['late_rest_median_error_mV']) for p in result['pairs'])))
        for name in MODELS} for scenario,result in results.items()}
    summary=dict(schema_version='voltforge.p45b_local_dynamics/1',source_lock=lock,
        implementation_sha256={n:sha(ROOT/n) for n in IMPLEMENTATIONS},
        source_attribution='Dickinson et al., About:Energy (2026), https://zenodo.org/records/19052626, CC BY 4.0',
        evidence='in-sample complete-pair conditional development diagnostics; all evidence previously opened',
        models_adopted=False,deployable_SOC_law=False,fresh_independent_assessment=False,
        new_measurement_families_opened=0,remaining_unopened_members=48,remaining_unopened_families=40,
        selected_pair_ids=[g['pair_index'] for g in groups],aggregates=aggregates,
        scenarios={k:dict(pairs=len(v['pairs']),samples=len(v['rows'])) for k,v in results.items()},
        limitations=['local constant resistance during pulse can masquerade as time-scale change',
            'reference and SOC-origin remain uncertain; inherited polarization is not measured',
            'local parameters cannot predict sustained 1C without an untested SOC transfer rule',
            'nominal 25 degC protocol only; no thermal model',
            'finite grid does not establish unique time constants or nonlinear global optimum'],
        requirements='requirement not configured',module_decision='insufficient evidence',
        module_experimental_validation='awaiting suitable measurements')
    write_json(out/'summary.json',summary)
    write_json(out/'manifest.json',{p.name:sha(p) for p in sorted(out.iterdir()) if p.is_file()})
    print(json.dumps(aggregates,indent=2))


if __name__=='__main__':
    main()
