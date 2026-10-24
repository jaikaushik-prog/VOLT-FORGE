"""Reports, sensitivity and software coupling from frozen v2 models; no refitting."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from voltforge.models import improvement as m
from voltforge.models.coupling import simulate

SHORT={'baseline':'v1 method','C1_rest_reference_R':'C1: rest + R','C2_rest_reference_RC':'C2: rest + RC','C3_rest_reference_SOC_RC':'C3: SOC + RC'}
COLORS=['#777777','#D55E00','#0072B2','#009E73']


def longest_contiguous_span(f,mask):
    g=f[np.asarray(mask,bool)]
    if not len(g): return 0.
    breaks=np.r_[True,(np.diff(g.row.to_numpy())!=1)|(np.diff(g.cycle.to_numpy())!=0)]
    return max(float(x.time_s.iloc[-1]-x.time_s.iloc[0]) for _,x in g.groupby(np.cumsum(breaks)))


def get_predictions(folder,cell,kind,plan):
    path=folder/f'{cell}_{kind}_predictions.csv'
    if not path.exists():
        # Reproduction from sealed parameters; used evidence is reopened, never fit.
        models=m.read_json(folder/f'{cell}_models.json')
        _,f,_=m.load_cell(cell,plan['evaluation_cycles'])
        pred=m.predictions(f,models[kind],plan['evaluation_cycles']);pred.to_csv(path,index=False)
    return pd.read_csv(path)


def plot_cell(folder,cell,plan,selected):
    data={k:get_predictions(folder,cell,k,plan) for k in m.METHODS}
    fig,axes=plt.subplots(4,3,figsize=(16,12),layout='constrained')
    for row,c in enumerate(plan['evaluation_cycles']):
        measured=data[selected];measured=measured[measured.cycle==c]
        start=measured.time_s.iloc[0];t=(measured.time_s-start)/60
        axes[row,0].plot(t,measured.V_V,color='black',lw=1,label='Measured')
        long=measured.step==10
        axes[row,1].plot(measured.time_s[long]-start,measured.V_V[long],color='black',lw=1,label='Measured')
        for k,color in zip(m.METHODS,COLORS):
            g=data[k];g=g[g.cycle==c];tt=(g.time_s-start)/60;s=g.step==10
            axes[row,0].plot(tt,g.predicted_V,lw=.7,color=color,label=SHORT[k])
            axes[row,1].plot(g.time_s[s]-start,g.predicted_V[s],lw=.8,color=color)
            axes[row,2].plot(tt,g.error_V*1000,lw=.7,color=color)
        axes[row,0].set(title=f'{cell}, cycle {c}, source rows {int(measured.row.iloc[0])}-{int(measured.row.iloc[-1])}',ylabel='Voltage [V]',xlabel='Cycle time [min]')
        axes[row,1].set(title='4.85 A discharge detail',ylabel='Voltage [V]',xlabel='Cycle time [s]')
        axes[row,2].set(title='Complete-sequence residual',ylabel='Predicted - measured [mV]',xlabel='Cycle time [min]')
        axes[row,2].axhline(0,color='black',lw=.5)
        for ax in axes[row]: ax.grid(alpha=.2)
    axes[0,0].legend(fontsize=7,ncol=2)
    fig.suptitle('Frozen procedure | '+('Additional characterized cell assessment' if folder.name=='fresh' else 'Used development evidence'))
    fig.savefig(folder/f'{cell}_comparison.png',dpi=130);plt.close(fig)
    # Pulse/MS zoom and time-residual structure are otherwise hidden by the hour rest.
    fig,axes=plt.subplots(4,2,figsize=(12,10),layout='constrained')
    for row,c in enumerate(plan['evaluation_cycles']):
        g=data[selected];g=g[(g.cycle==c)&(g.step>=12)];t=g.time_s-g.time_s.iloc[0]
        axes[row,0].plot(t,g.V_V,color='black',label='Measured',lw=1)
        axes[row,0].plot(t,g.predicted_V,color='#0072B2',label='Selected RC',lw=.8)
        axes[row,1].plot(t,g.error_V*1000,color='#0072B2',lw=.8);axes[row,1].axhline(0,color='black',lw=.5)
        axes[row,0].set(ylabel='Voltage [V]',title=f'{cell} cycle {c}: rows {int(g.row.iloc[0])}-{int(g.row.iloc[-1])}')
        axes[row,1].set(ylabel='Error [mV]',title='Continuous state from preceding discharge/rest')
        for ax in axes[row]: ax.set_xlabel('Time since HPPC pulse start [s]');ax.grid(alpha=.2)
    axes[0,0].legend(fontsize=8);fig.savefig(folder/f'{cell}_pulse_detail.png',dpi=130);plt.close(fig)


def main():
    m.check_procedure();plan=m.read_json(m.PLAN);selected=m.read_json(m.OUT/'selection.json')['selected']
    fresh_seal=m.read_json(m.OUT/'fresh_model_seal.json')
    for p,h in fresh_seal['artifacts'].items():
        if m.v1.digest(p)!=h: raise ValueError('Fresh model changed')
    roles={'development':m.read_json(m.OUT/'development/scores.json'),'fresh':m.read_json(m.OUT/'fresh/scores.json')['cells']}
    rows=[];parameters=[];coverage=[];threshold=[]
    for role,scores in roles.items():
        for cell,by in scores.items():
            folder=m.OUT/role;models=m.read_json(folder/f'{cell}_models.json')
            for kind,s in by.items():
                pred=get_predictions(folder,cell,kind,plan);primary=m.primary_mask(pred,plan)
                actual=m.aggregate(pred,primary)
                if abs(actual['sample_rmse_mV']-s['primary']['sample_rmse_mV'])>1e-8: raise ValueError('CSV/score disagreement')
                rows.append(dict(role=role,cell=cell,model=kind,**s['primary'],pass_all=s['primary_criteria_pass'],
                    full_sample_rmse_mV=s['full']['sample_rmse_mV'],full_time_rmse_mV=s['full']['time_rmse_mV'],full_max_abs_mV=s['full']['max_abs_mV']))
                mm=models[kind];st=np.array([x['parameters_ohm'] for x in mm['leave_one_calibration_cycle_out']]);ts=[x['tau_s'] for x in mm['leave_one_calibration_cycle_out']]
                parameters.append(dict(role=role,cell=cell,model=kind,parameters_ohm=mm['parameters_ohm'],tau_s=mm['tau_s'],
                    leave_one_out_parameter_min_ohm=st.min(axis=0).tolist(),leave_one_out_parameter_max_ohm=st.max(axis=0).tolist(),
                    leave_one_out_tau_range_s=[min(ts),max(ts)],profile_support_s=mm['profile_5percent_support_s'],
                    condition=mm['normalized_sensitivity_condition'],identifiable=mm['identifiable']))
                th=plan['provisional_criterion']['operational_voltage_threshold_V']
                threshold.append(dict(role=role,cell=cell,model=kind,
                    unguarded_false_clearance_n=int(((pred.predicted_V>=th)&(pred.V_V<th)&primary).sum()),
                    unguarded_false_low_n=int(((pred.predicted_V<th)&(pred.V_V>=th)&primary).sum()),
                    **s['threshold_diagnostics'],near_threshold_primary=s['primary_near_threshold']))
            pred=get_predictions(folder,cell,selected,plan)
            for phase,g in pred.groupby('phase'):
                coverage.append(dict(role=role,cell=cell,phase=phase,rows=len(g),current_min_A=float(g.I_A.min()),current_max_A=float(g.I_A.max()),
                    soc_min=float(g.soc.min()),soc_max=float(g.soc.max()),surface_min_C=float(g.surface_C.min()),surface_max_C=float(g.surface_C.max()),
                    longest_continuous_positive_load_s=longest_contiguous_span(g,g.I_A>.01)))
            plot_cell(folder,cell,plan,selected)
            print('Compared and plotted',role,cell,flush=True)
    summary=pd.DataFrame(rows);summary.to_csv(m.OUT/'comparison_summary.csv',index=False)
    pd.DataFrame(coverage).to_csv(m.OUT/'observed_evaluation_coverage.csv',index=False)
    m.save(m.OUT/'parameter_stability.json',parameters);m.save(m.OUT/'threshold_diagnostics.json',threshold)
    m.save(m.OUT/'comparison_summary.json',rows)
    fig,axes=plt.subplots(1,3,figsize=(14,4.5),layout='constrained')
    fresh=summary[summary.role=='fresh'];x=np.arange(len(plan['fresh_cells']));width=.2
    for j,(kind,color) in enumerate(zip(m.METHODS,COLORS)):
        f=fresh[fresh.model==kind].set_index('cell').loc[plan['fresh_cells']]
        for ax,col,title in zip(axes,['sample_rmse_mV','time_rmse_mV','max_abs_mV'],['Sample RMSE','Time-weighted RMSE','Maximum absolute error']):
            ax.bar(x+(j-1.5)*width,f[col],width,color=color,label=SHORT[kind]);ax.set(xticks=x,xticklabels=f.index,title=title,ylabel='Primary-domain error [mV]')
    axes[0].axhline(10,color='black',ls='--',lw=.8);axes[1].axhline(10,color='black',ls='--',lw=.8);axes[2].axhline(25,color='black',ls='--',lw=.8)
    axes[0].legend(fontsize=8);fig.suptitle('Additional characterized cells: identical evaluation rows; dashed = proposed model budget')
    fig.savefig(m.OUT/'fresh_comparison.png',dpi=150);plt.close(fig)

    # Declared assumption sensitivity; prediction perturbations, never refits.
    scenarios={'nominal':{},'initial_SOC_minus_0.02':{'soc_offset':-.02},'initial_SOC_plus_0.02':{'soc_offset':.02},
        'capacity_minus_1percent':{'capacity_factor':.99},'capacity_plus_1percent':{'capacity_factor':1.01},
        'right_endpoint_hold':{'hold':'right'},'loaded_rest_reference':{'alternate_reference':True},
        'initial_polarization_minus5mV':{'initial_polarization_V':-.005},'initial_polarization_plus5mV':{'initial_polarization_V':.005}}
    sensitivities={}
    for cell in ['P7']+plan['fresh_cells']:
        folder=m.OUT/('development' if cell=='P7' else 'fresh');models=m.read_json(folder/f'{cell}_models.json')
        _,f,_=m.load_cell(cell,plan['evaluation_cycles']);sensitivities[cell]={}
        for kind,model in models.items():
            base=m.predictions(f,model,plan['evaluation_cycles']);mask=m.primary_mask(base,plan)
            ss={}
            for label,args in scenarios.items():
                p=m.predictions(f,model,plan['evaluation_cycles'],**args)
                stat=m.aggregate(p,mask);change=(p.predicted_V-base.predicted_V)[mask].dropna()
                stat['max_prediction_change_mV']=float(abs(change).max()*1000) if len(change) else None
                ss[label]=stat
            sensitivities[cell][kind]=ss
        print('Sensitivity',cell,flush=True)
    m.save(m.OUT/'assumption_sensitivity.json',sensitivities)

    cells=['P7','P17','P19','P13'];models=[m.read_json(m.OUT/'development'/f'{c}_models.json')[selected] for c in cells]
    coupling={};out=m.OUT/'software_coupling';out.mkdir(exist_ok=True)
    for soc in [.3,.5,.7,.8]:
        runs={dt:simulate(models,[soc]*4,14.55,360,dt,.001) for dt in [1.,.5,.25]}
        fine=runs[.25];coarse=runs[1.];middle=runs[.5]
        case=dict(cell_order=cells,initial_soc=soc,module_A=14.55,duration_s=360,rail_segment_ohm=.001,
            branch_ranges_A={c:[float(fine[f'I{k+1}_A'].min()),float(fine[f'I{k+1}_A'].max())] for k,c in enumerate(cells)},
            soc_min=float(fine[[f'SOC{k+1}' for k in range(4)]].min().min()),terminal_min_V=float(fine.terminal_V.min()),
            max_kcl_residual_A=float(abs(fine.kcl_residual_A).max()),max_charge_balance_As=float(abs(fine.total_charge_balance_As).max()),
            max_network_power_residual_W=float(abs(fine.electrical_energy_residual_W).max()),
            terminal_change_1s_vs_0_25s_mV=float(np.max(abs(coarse.terminal_V.to_numpy()-fine.terminal_V.to_numpy()[::4]))*1000),
            terminal_change_0_5s_vs_0_25s_mV=float(np.max(abs(middle.terminal_V.to_numpy()-fine.terminal_V.to_numpy()[::2]))*1000),
            status='Software verification only; currents/temperatures/contact values not experimentally validated')
        case['branch_current_within_4_9A']=all(0<=lo and hi<=4.9 for lo,hi in case['branch_ranges_A'].values())
        coupling[str(soc)]=case;fine.to_csv(out/f'load14_55A_SOC{soc}_dt0_25.csv',index=False)
    m.save(out/'results.json',coupling)

    # Near-domain reference and tau profile diagnostics for P7; no held-point fitting.
    p7=m.read_json(m.OUT/'development/P7_models.json');a=p7[selected]['reference']['rest']
    fig,axes=plt.subplots(1,2,figsize=(12,4.5),layout='constrained')
    _,f,_=m.load_cell('P7',list(range(1,10)));s=np.linspace(a[0]['soc'],a[-1]['soc'],400)
    axes[0].plot(s,m.reference(s,np.zeros(len(s)),p7[selected]['reference'],'rest'),label='Calibration-rest PCHIP')
    axes[0].scatter([v['soc'] for v in a],[v['V'] for v in a],color='black',label='Calibration anchors')
    rest=f[f.cycle.isin(plan['evaluation_cycles'])&(f.step==11)]
    for c,g in rest.groupby('cycle'):
        tail=g[g.time_s>=g.time_s.iloc[-1]-30];axes[0].scatter(tail.soc.median(),tail.V_V.median(),marker='x',color='#D55E00')
    axes[0].set(xlabel='SOC proxy',ylabel='Voltage [V]',title='P7 rest reference; crosses = used development rests');axes[0].legend(fontsize=8)
    for kind in m.METHODS[2:]:
        mm=p7[kind];ss=np.asarray(mm['profile_sse']);axes[1].semilogx(mm['tau_grid_s'],ss/min(ss),label=SHORT[kind])
    axes[1].axhline(1.05,ls='--',color='black',lw=.7);axes[1].set(xlabel='tau [s]',ylabel='Weighted SSE / minimum',ylim=(.99,2),title='Conditional RC identifiability, not a confidence interval');axes[1].legend()
    fig.savefig(m.OUT/'reference_and_identifiability.png',dpi=150);plt.close(fig)

    lines=['# V2 baseline-versus-candidate results','','All v1 cells are used development evidence. P2/P5/P8 assessment follows the frozen procedure and their own allowed calibration; it is not zero-shot prediction or independent module validation.','',
        'Primary domain: SOC proxy 0.2-0.8, rest/discharge -0.01 to 4.9 A (small negative threshold is a zero-current tolerance), surface 22-28 C under this nominal-23 C protocol. Values below are per-cell, on identical rows.','',
        '| Role / cell | Model | Sample / time RMSE [mV] | Bias [mV] | Max [mV] | Proposed criteria met? |',
        '|---|---|---:|---:|---:|---|']
    for r in rows:
        lines.append(f"| {r['role']} / {r['cell']} | {SHORT[r['model']]} | {r['sample_rmse_mV']:.2f} / {r['time_rmse_mV']:.2f} | {r['bias_mV']:.2f} | {r['max_abs_mV']:.2f} | {'Yes' if r['pass_all'] else 'No'} |")
    lines+=['','Selection was **C2, rest reference + constant one-RC**, before fresh outcomes. C3 has more parameters and does not improve the primary development score. Passing the complexity selection rule does not mean passing the engineering error budget.','',
        'Complete-sequence and phase/cycle/SOC/current/temperature/time-since-transition metrics (sample RMSE, time RMSE, bias, maxima, worst source row) are in `development/scores.json` and `fresh/scores.json`. Full-record metrics are also in `comparison_summary.csv`. Unsupported reference rows are counted explicitly; the reference never silently extrapolates.','',
        '[Fresh comparison](fresh_comparison.png) | [Reference/identifiability](reference_and_identifiability.png) | [V1 diagnosis](diagnosis/P7_residual_diagnosis.png)','',
        'Plots contain original source rows; CSVs retain row, time, current, SOC, measured temperature, reference, prediction and residual. The long discharge and later pulse/rest/MS views are both shown.']
    for role,scores in roles.items():
        lines+=['',role+': '+ ' | '.join(f'[{c} comparison]({role}/{c}_comparison.png) / [pulse detail]({role}/{c}_pulse_detail.png)' for c in scores)]
    lines+=['','`parameter_stability.json` reports conditional leave-one-calibration-cycle-out ranges and normalized sensitivity conditioning for every baseline/candidate/cell. Reference anchors are held fixed, so these are stability diagnostics, not measurement uncertainty intervals. `assumption_sensitivity.json` covers all four models on P7 and all three fresh cells; masks stay fixed at nominal-domain rows.','',
        '`threshold_diagnostics.json` distinguishes unguarded classification changes, guarded false clearances and ambiguous results. Zero observed guarded false clearances does not validate the unmeasured instrumentation/initial-condition budget or establish a rare-event rate.','',
        '`software_coupling/results.json` gives per-branch current coverage, SOC balance, current conservation and dt sensitivity for the specified 14.55 A application. These are synthetic model predictions for software verification, not new experimental results.','',
        'The raw archive and all preserved v1 artifacts remain unchanged. The root decision report states the supported domain and outstanding gates.']
    (m.OUT/'RESULTS.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print('Comparison, sensitivity, source-referenced plots and software coupling complete.',flush=True)


if __name__=='__main__': main()
