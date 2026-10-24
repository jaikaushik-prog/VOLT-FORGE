"""Regenerate diagnostics from sealed results; never fit or select models."""
import json
from pathlib import Path
from zipfile import ZipFile
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from voltforge.models.identification import (OUT, PLAN, LOCK, digest, verify_inputs,
    save, source_archive, read_cell, loaded_curve)
from voltforge.models.ladder import solve_ladder


def main():
    lock=verify_inputs()
    plan=json.loads(PLAN.read_text());seal=json.loads((OUT/'model_seal.json').read_text())
    assessment=json.loads((OUT/'assessment.json').read_text())
    if assessment['model_seal_sha256']!=digest(OUT/'model_seal.json') or seal['lock_sha256']!=digest(LOCK):
        raise ValueError('Frozen result binding changed')
    rows=[];models=[];all_metrics={};profile_rows=[]
    for cell in seal['model_files_sha256']:
        model_path=OUT/f'{cell}_model.json'
        if digest(model_path)!=seal['model_files_sha256'][cell]: raise ValueError('Frozen model changed')
        m=json.loads(model_path.read_text());models.append(m)
        f=pd.read_csv(OUT/f'{cell}_assessment_predictions.csv')
        e=f.error_V.to_numpy()*1000
        scores={}
        for name,mask in [('hppc',f.step<=15),('multisine_and_rest',f.step>=17),('full_sequence',np.ones(len(f),dtype=bool))]:
            p=f[mask];err=e[mask];worst=p.iloc[int(np.argmax(abs(err)))]
            # Integrate within each cycle, never across the omitted inter-cycle span.
            energy=duration=0.
            for _,g in p.groupby('cycle'):
                energy+=float(np.trapz((g.error_V*1000)**2,g.time_s))
                duration+=float(g.time_s.iloc[-1]-g.time_s.iloc[0])
            scores[name]=dict(n=len(err),rmse_mV=float(np.sqrt(np.mean(err**2))),
                bias_mV=float(np.mean(err)),max_abs_mV=float(np.max(abs(err))),
                time_weighted_rmse_mV=float(np.sqrt(energy/duration)),
                max_error_cycle=int(worst.cycle),max_error_source_row=int(worst.row),
                current_A_range=[float(p.I_A.min()),float(p.I_A.max())])
        all_metrics[cell]=scores
        if abs(scores['hppc']['rmse_mV']-assessment['cells'][cell]['hppc_pooled_rmse_mV'])>1e-8:
            raise ValueError('Prediction CSV does not reproduce sealed-model assessment metrics')
        interval=m['candidates']['bootstrap_intervals']['resistive_R0_ohm' if m['selected']=='resistive' else 'R0_ohm']
        rows.append(dict(cell=cell,selected=m['selected'],capacity_Ah=m['capacity_Ah'],R0_mOhm=1000*m['parameters']['R0_ohm'],
            R0_conditional_low_mOhm=1000*interval['p2_5'],R0_conditional_high_mOhm=1000*interval['p97_5'],
            calibration_hppc_rmse_mV=m['calibration']['hppc_pooled_rmse_mV'],
            development_hppc_rmse_mV=m['development'][m['selected']]['hppc_pooled_rmse_mV'],
            assessment_hppc_rmse_mV=scores['hppc']['rmse_mV'],assessment_hppc_bias_mV=scores['hppc']['bias_mV'],
            assessment_hppc_max_abs_mV=scores['hppc']['max_abs_mV'],
            assessment_ms_rest_rmse_mV=scores['multisine_and_rest']['rmse_mV'],
            assessment_ms_rest_bias_mV=scores['multisine_and_rest']['bias_mV'],
            assessment_ms_rest_max_abs_mV=scores['multisine_and_rest']['max_abs_mV'],
            assessment_surface_min_C=float(f.surface_C.min()),assessment_surface_max_C=float(f.surface_C.max()),
            assessment_soc_min=float(f.soc_proxy.min()),assessment_soc_max=float(f.soc_proxy.max())))
        c=m['candidates'];profile_rows.append(dict(cell=cell,**c['one_rc'],
            profile_support_low_s=c['profile_5percent_support_s'][0],profile_support_high_s=c['profile_5percent_support_s'][1],
            normalized_sensitivity_condition=c['normalized_sensitivity_condition'],
            development_improvement_percent=100*(1-m['development_rc_over_resistive_rmse_ratio']),
            interior_screen=c['interior_identifiability_screen']))
    frame=pd.DataFrame(rows);frame.to_csv(OUT/'summary.csv',index=False)
    pd.DataFrame(profile_rows).to_csv(OUT/'candidate_rc_summary.csv',index=False)
    save(OUT/'summary.json',dict(cells=rows,assessment_pooled=all_metrics,rc_candidates=profile_rows,
        assessment_source_sha256=digest(OUT/'assessment.json'),interpretation='Within-cell held sequences, not independent module validation'))

    fig,ax=plt.subplots(1,2,figsize=(12,4.5),layout='constrained')
    for m in models:
        c=m['candidates'];s=np.asarray(c['profile_sse_V2'])
        ax[0].semilogx(c['tau_grid_s'],s/min(s),label=m['cell'])
    ax[0].axhline(1.05,color='black',ls='--',lw=.8,label='5% SSE support screen')
    ax[0].set(xlabel='Candidate RC time constant [s]',ylabel='Calibration SSE / minimum SSE',ylim=(.99,1.6),
              title='One-RC profile; support is not a confidence interval')
    ax[0].legend(fontsize=8,ncol=2);ax[0].grid(alpha=.2)
    y=np.arange(len(frame));p=frame.R0_mOhm.to_numpy()
    ax[1].errorbar(p,y,xerr=np.vstack([p-frame.R0_conditional_low_mOhm,frame.R0_conditional_high_mOhm-p]),fmt='o',capsize=3,color='#0072B2')
    ax[1].set(yticks=y,yticklabels=frame.cell,xlabel='Selected effective R0 [mOhm]',
              title='Whole-cycle bootstrap: conditional 2.5-97.5%');ax[1].invert_yaxis();ax[1].grid(alpha=.2)
    fig.savefig(OUT/'identifiability.png',dpi=150);plt.close(fig)

    fig,ax=plt.subplots(1,2,figsize=(12,4.5),layout='constrained')
    x=np.arange(len(frame));w=.25
    for j,(label,col) in enumerate([('Calibration','calibration_hppc_rmse_mV'),('Development','development_hppc_rmse_mV'),('Assessment','assessment_hppc_rmse_mV')]):
        ax[0].bar(x+(j-1)*w,frame[col],w,label=label)
    ax[0].set(xticks=x,xticklabels=frame.cell,ylabel='HPPC + complete rests RMSE [mV]',
        title='Selected resistive model; all samples',ylim=(0,1.28*frame.development_hppc_rmse_mV.max()))
    ax[0].legend(loc='upper center',ncol=3,fontsize=8)
    ax[1].bar(x-w/2,frame.assessment_ms_rest_rmse_mV,w,label='RMSE')
    ax[1].bar(x+w/2,frame.assessment_ms_rest_max_abs_mV,w,label='Maximum absolute error')
    ax[1].set(xticks=x,xticklabels=frame.cell,ylabel='Multisine + rest error [mV]',title='Reserved stress sequences; amplitude extrapolation');ax[1].legend()
    fig.savefig(OUT/'assessment_summary.png',dpi=150);plt.close(fig)

    m=models[0]
    with ZipFile(source_archive()) as z: low,_=read_cell(z,'P7','low_rate')
    _,s,v=loaded_curve(low);a=m['rest_reference_anchors']
    correction=np.interp(s,[x['soc'] for x in a],[x['correction_V'] for x in a])
    fig,ax=plt.subplots(figsize=(8,5),layout='constrained')
    ax.plot(s,v,label='Measured C/20 loaded voltage')
    ax.plot(s,v+correction,label='Calibration-rest-referenced model input')
    ax.scatter([x['soc'] for x in a],[np.interp(x['soc'],s,v)+x['correction_V'] for x in a],color='black',label='Calibration late-rest anchors',zorder=3)
    ax.set(xlabel='SOC proxy (initial SOC and capacity assumptions)',ylabel='Voltage [V]',
           title='P7 reference curves: neither is proven equilibrium OCV');ax.legend(fontsize=8);ax.grid(alpha=.2)
    fig.savefig(OUT/'P7_loaded_reference.png',dpi=150);plt.close(fig)

    audit=json.loads(Path('reports/module_audit.json').read_text())
    independent=json.loads(Path('reports/reconciliation/independent_results.json').read_text())
    differences={}
    for name,r in independent['runs'].items():
        old=audit[name]['kcl']['by_step']['5']
        differences[name]={k:r['discharge'][k+'_A']-old[k] for k in ['mean','rms','max_abs']}
        if any(abs(d)>1e-12 for d in differences[name].values()): raise ValueError('Two calculations disagree')
    ladder_cases={
        'symmetric_four':([3.7]*4,[.02]*4,[0]*3,[0]*3,12.,[3.]*4,3.64),
        'two_cell_shared_rails':([3.7]*2,[.1]*2,[.12],[.08],10.,[7.5,2.5],2.95),
        'circulating_zero_load':([4.,3.8],[.1,.2],[0],[0],0.,[2/3,-2/3],59/15)}
    ladder={}
    for name,(e,r,rp,rn,i,expected,v) in ladder_cases.items():
        result=solve_ladder(e,r,rp,rn,i)
        np.testing.assert_allclose(result.branch_A,expected,atol=1e-12,rtol=0)
        np.testing.assert_allclose(result.terminal_V,v,atol=1e-12,rtol=0)
        ladder[name]=dict(branch_A=result.branch_A.tolist(),terminal_V=result.terminal_V,
            kcl_residual_A=result.kcl_residual_A,energy_residual_W=result.energy_residual_W)
    save(Path('reports/sprint_verification/results.json'),dict(
        protected_original_artifacts=len(lock['protected_existing']),archive_hash_verified=True,
        separate_residual_calculations_difference=differences,ladder_analytical_cases=ladder,
        ladder_experimental_validation='pending',optimizer_or_ranked_repairs=False))

    lines=['# Sealed single-cell results', '',
        'Generated from frozen model artifacts and reserved-cycle predictions. These are provisional within-cell checks on the same cells and rig; **not independent module validation**.', '',
        '| Cell | Q [Ah] | Effective R0 [mOhm] | Conditional 2.5-97.5% [mOhm] | Calibration / development / assessment HPPC RMSE [mV] |',
        '|---|---:|---:|---:|---:|']
    for r in rows:
        lines.append(f"| {r['cell']} | {r['capacity_Ah']:.4f} | {r['R0_mOhm']:.2f} | {r['R0_conditional_low_mOhm']:.2f}-{r['R0_conditional_high_mOhm']:.2f} | {r['calibration_hppc_rmse_mV']:.2f} / {r['development_hppc_rmse_mV']:.2f} / {r['assessment_hppc_rmse_mV']:.2f} |")
    lines+=['','R0 is an effective resistance conditional on the loaded/rest reference; unresolved fast dynamics and contacts can contribute. Q is an observed C/20 current integral, not a fitted nominal capacity. The bootstrap resamples only four calibration cycles; curve, capacity, SOC convention and rest anchors stay fixed. These intervals omit systematic instrument and reference-curve uncertainty.','',
        '| Cell | Reserved HPPC bias / max [mV] | Reserved multisine + rest RMSE / bias / max [mV] | Recorded assessment surface [C] |',
        '|---|---:|---:|---:|']
    for r in rows:
        lines.append(f"| {r['cell']} | {r['assessment_hppc_bias_mV']:.2f} / {r['assessment_hppc_max_abs_mV']:.2f} | {r['assessment_ms_rest_rmse_mV']:.2f} / {r['assessment_ms_rest_bias_mV']:.2f} / {r['assessment_ms_rest_max_abs_mV']:.2f} | {r['assessment_surface_min_C']:.2f}-{r['assessment_surface_max_C']:.2f} |")
    lines+=['','Errors are predicted minus measured. RMSE here weights recorded samples equally; `summary.json` and `assessment.json` also report time-weighted RMSE, per-cycle errors, current ranges and worst-error source rows. Mixed logging rates make these weightings different.','',
        '| Cell | Candidate R0 / R1 [mOhm] | Candidate tau [s] | 5%-SSE support [s] | Normalized sensitivity condition | Development HPPC improvement [%] |',
        '|---|---:|---:|---:|---:|---:|']
    for r in profile_rows:
        lines.append(f"| {r['cell']} | {1000*r['R0_ohm']:.2f} / {1000*r['R1_ohm']:.2f} | {r['tau_s']:.1f} | {r['profile_support_low_s']:.1f}-{r['profile_support_high_s']:.1f} | {r['normalized_sensitivity_condition']:.2f} | {r['development_improvement_percent']:.2f} |")
    lines+=['', 'All selected models are resistive: the candidate RC models fail the predeclared 20% development-improvement rule. This does not establish an absence of polarization. Candidate RC conditional bootstrap intervals are in each `*_model.json`; the profile support is a descriptive identifiability screen, not a confidence interval. No assessment result was used to alter this choice.', '',
        'Calibration cycles: 1, 4, 5, 9. Development: 2, 7. Reserved assessment: 3, 6, 8. Every source cycle stays in one allocation. HPPC predictions include both pulses, all intervening/following rests and the last 10 s of the preceding rest. The subsequent multisine and final rest are simulated without resetting to measured voltage. The preceding SOC-setting discharge and long rest are reserved with their cycles but not scored as identified dynamics.', '',
        'The calibration HPPC currents are approximately -2.00 to +2.66 A. Reserved multisine inputs reach about -6.73 to +17.88 A, beyond that fitting amplitude. Large errors in those sequences are retained as limits of this baseline. The nominal chamber setting is 23 C; recorded surface excursions are not a temperature-identification experiment. No 10-40 C parameter law or core-temperature model is inferred.', '',
        '[Identification and uncertainty plot](identifiability.png) · [Assessment summary](assessment_summary.png) · [P7 reference curve](P7_loaded_reference.png)', '']
    lines+=['Measured/predicted figures: '+ ' · '.join(f'[{r["cell"]}]({r["cell"]}_assessment.png)' for r in rows), '',
        'Per-sample predictions and error/source-row references: `*_assessment_predictions.csv`. The plan, input lock and model seal are under `configs/` and this directory. Reproduction commands are in the root README.']
    (OUT/'RESULTS.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(frame.to_string(index=False))
    print('Protected inputs verified; separate residual calculations agree; ladder analytical cases pass.')


if __name__=='__main__': main()
