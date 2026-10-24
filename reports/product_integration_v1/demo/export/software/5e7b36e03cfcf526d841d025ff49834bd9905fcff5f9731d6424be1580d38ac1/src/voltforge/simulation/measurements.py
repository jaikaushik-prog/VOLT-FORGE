"""Strict future-measurement ingestion; no channel scaling, tuning or time shifting."""
import shutil
from pathlib import Path
import numpy as np
import pandas as pd
from .workflow import read,save,digest,safe_output

CELLS=['P7','P17','P19','P13']
CHANNELS={'module_current_A':('A','module_load_path'),'terminal_V':('V','positive_node1-negative_node1'),
          'ambient_C':('degC','chamber_ambient')}
for k in range(1,5):
    CHANNELS.update({f'I{k}_A':('A',f'cell{k}_branch'),f'V{k}_V':('V',f'positive_node{k}-negative_node{k}'),
                     f'surface{k}_C':('degC',f'cell{k}_surface')})


def preserve(source,out):
    dest=out/'original';dest.mkdir(parents=True,exist_ok=True);records={}
    for name in ['metadata.json','measurements.csv']:
        p=source/name
        if not p.is_file(): raise ValueError('Missing input file '+name)
        h=digest(p);target=dest/name
        if target.exists() and digest(target)!=h: raise ValueError('Output already preserves different input; choose another directory')
        if p.resolve()!=target.resolve():shutil.copy2(p,target)
        records[name]=dict(source=str(p.resolve()),sha256=h,bytes=p.stat().st_size)
    return records


def validate(source,out):
    source=Path(source);out=safe_output(out);out.mkdir(parents=True,exist_ok=True)
    provenance=preserve(source,out);meta=read(source/'metadata.json');f=pd.read_csv(source/'measurements.csv')
    errors=[];issues=[];skews={};uncertainties={};normalized=f.copy()
    if meta.get('schema_version')!=1:errors.append('Unsupported measurement schema')
    if meta.get('data_kind') not in ['synthetic_fixture','experimental']:errors.append('data_kind must be explicit')
    if meta.get('cell_order')!=CELLS:errors.append('Cell/position mapping does not match this application')
    if meta.get('time_unit')!='s' or not meta.get('time_origin'):errors.append('Seconds and explicit common time origin required')
    prep=meta.get('preparation',{})
    if not all(prep.get(k) is not None for k in ['history','initial_soc','initial_polarization_V','rest_s','source']):
        issues.append('Preparation history/initial state evidence incomplete')
    sync=meta.get('synchronization',{})
    tolerance=sync.get('alignment_tolerance_s');gap=sync.get('maximum_gap_s')
    if not isinstance(tolerance,(float,int)) or not np.isfinite(tolerance) or tolerance<0:errors.append('Explicit finite alignment tolerance required')
    if not isinstance(gap,(float,int)) or not np.isfinite(gap) or gap<=0:errors.append('Explicit finite maximum timestamp gap required')
    if not sync.get('method') or not sync.get('evidence'):issues.append('Synchronization evidence missing')
    for name in ['source_row','time_s']:
        if name not in f:errors.append('Missing '+name)
    if not errors:
        if len(f)<2 or not np.isfinite(f[['time_s','source_row']].to_numpy(dtype=float)).all():errors.append('At least two finite timestamp/source rows required')
        elif np.any(np.diff(f.time_s)<=0) or np.any(np.diff(f.source_row)<=0) or np.any(f.source_row<1) or np.any(f.source_row%1!=0):errors.append('Timestamps and original source rows must increase; do not sort or deduplicate silently')
        elif np.diff(f.time_s).max()>gap:errors.append('Common timestamp gap exceeds declared maximum')
    for name,(unit,location) in CHANNELS.items():
        ch=meta.get('channels',{}).get(name,{})
        if name not in f:errors.append('Missing channel '+name);continue
        if ch.get('unit')!=unit:errors.append('Unsupported/missing unit for '+name)
        if ch.get('location')!=location:errors.append('Undefined or incompatible measurement location for '+name)
        if not ch.get('sensor_id'):issues.append('Missing sensor mapping for '+name)
        if not np.isfinite(f[name].to_numpy(dtype=float)).all():errors.append('Nonfinite samples in '+name)
        if unit=='A':
            if ch.get('polarity') not in ['discharge_positive','charge_positive']:errors.append('Explicit current polarity required for '+name)
            elif ch['polarity']=='charge_positive':normalized[name]=-f[name]
        elif unit=='V' and ch.get('polarity')!='positive_minus_negative':errors.append('Voltage node polarity required for '+name)
        clock=ch.get('time_column')
        if clock not in f:errors.append('Timestamp column missing for '+name)
        elif 'time_s' in f:
            t=f[clock].to_numpy(dtype=float)
            if not np.isfinite(t).all() or np.any(np.diff(t)<=0):errors.append('Invalid channel timestamps for '+name)
            elif isinstance(gap,(float,int)) and np.diff(t).max()>gap:errors.append('Channel timestamp gap for '+name)
            skews[name]=float(np.max(abs(t-f.time_s.to_numpy()))) if np.isfinite(t).all() else None
        cal=ch.get('calibration',{});u=cal.get('absolute_uncertainty')
        synthetic=meta.get('data_kind')=='synthetic_fixture'
        if not cal.get('source') or not cal.get('date') or cal.get('status') not in (['documented','synthetic'] if synthetic else ['documented']):
            issues.append('Calibration provenance missing for '+name)
        if not isinstance(u,(float,int)) or not np.isfinite(u) or u<0 or (u==0 and not synthetic):
            issues.append('Absolute uncertainty missing/invalid for '+name)
        else:uncertainties[name]=float(u)
    aligned=bool(not errors and len(skews)==len(CHANNELS) and all(v is not None and v<=tolerance for v in skews.values()))
    if not aligned:issues.append('Channels incomplete or not aligned within declared timestamp tolerance')
    report=dict(schema_version=1,data_kind=meta.get('data_kind'),source=provenance,valid_structure=not errors,errors=errors,issues=issues,
        alignment_ok=aligned,max_channel_skew_s=skews,normalized_polarity='discharge_positive',
        source_rows_preserved=True,experimental_validation='awaiting suitable measurements',decision='insufficient evidence')
    if not errors:
        residual=normalized[[f'I{k}_A' for k in range(1,5)]].sum(axis=1)-normalized.module_current_A
        current_names=['module_current_A']+[f'I{k}_A' for k in range(1,5)]
        bound=sum(uncertainties[k] for k in current_names) if all(k in uncertainties for k in current_names) else None
        report['current_conservation']=dict(mean_A=float(residual.mean()),rmse_A=float(np.sqrt(np.mean(residual**2))),
            maximum_abs_A=float(abs(residual).max()),worst_source_row=int(normalized.source_row.iloc[int(np.argmax(abs(residual)))]),
            declared_sum_absolute_uncertainty_A=bound,within_declared_bound=bool(abs(residual).max()<=bound+1e-12) if bound is not None else None,
            note='No rescaling or fitted correction. Reported bound is metadata, not independently verified calibration; alignment uncertainty is not silently absorbed.')
        normalized['branch_sum_minus_module_A']=residual;normalized.to_csv(out/'normalized.csv',index=False)
        if bound is None or abs(residual).max()>bound+1e-12:issues.append('Current conservation unresolved against declared calibration bounds')
        if meta.get('data_kind')=='experimental' and aligned and not issues:
            report['experimental_validation']='suitable input structure supplied; experimental accuracy not established'
    save(out/'validation.json',report)
    return report,normalized,meta


def prediction_at(frame,times,column):
    """Interpolate within held-load intervals, never across a load discontinuity."""
    times=np.asarray(times,float);t=frame.time_s.to_numpy()
    if not np.isfinite(times).all() or times.min()<t[0] or times.max()>t[-1]:raise ValueError('Measurement times outside simulated support')
    index=np.searchsorted(t,times,side='right')-1;h=frame.step_s.to_numpy()[index]
    alpha=np.divide(times-t[index],h,out=np.zeros(len(times)),where=h>0)
    start=frame[column].to_numpy()[index]
    if column=='module_current_A':return start
    end=frame['interval_end_'+column].to_numpy()[index]
    return start+alpha*(end-start)


def compare_measurements(run,source,out):
    run=Path(run);out=safe_output(out);report,f,meta=validate(source,out/'ingestion')
    c=read(run/'configuration.json');frame=pd.read_csv(run/'trajectory.csv')
    result=dict(data_kind=meta.get('data_kind'),experimental_validation=report['experimental_validation'],
        decision='insufficient evidence',validation_report='ingestion/validation.json',comparisons={},issues=list(report['issues']))
    if not len(frame):
        result['status']='comparison unavailable: simulation has no supported samples';save(out/'comparison.json',result);return result
    if not report['valid_structure'] or not report['alignment_ok']:
        result['status']='comparison unavailable: incomplete or misaligned measurements';save(out/'comparison.json',result);return result
    if f.time_s.min()<frame.time_s.min() or f.time_s.max()>frame.time_s.max():
        result['status']='comparison unavailable: measurement timestamps outside simulated domain';save(out/'comparison.json',result);return result
    prep=meta.get('preparation',{})
    for name in ['initial_soc','initial_polarization_V']:
        if prep.get(name)!=c[name]:result['issues'].append('Preparation '+name+' differs from simulated assumption; no voltage-based reinitialization applied')
    normalized={'source_row':f.source_row,'time_s':f.time_s}
    for name in ['module_current_A','terminal_V']+[f'I{k}_A' for k in range(1,5)]+[f'V{k}_V' for k in range(1,5)]:
        # Each channel uses its own recorded timestamp; no inferred shift.
        times=f[meta['channels'][name]['time_column']].to_numpy()
        try:pred=prediction_at(frame,times,name)
        except ValueError:
            result['status']='comparison unavailable: channel timestamp outside simulated domain';save(out/'comparison.json',result);return result
        error=pred-f[name].to_numpy();dt=np.diff(times);duration=times[-1]-times[0]
        result['comparisons'][name]=dict(unit=meta['channels'][name]['unit'],n=len(error),sample_rmse=float(np.sqrt(np.mean(error**2))),
            time_rmse=float(np.sqrt(np.sum(dt*(error[:-1]**2+error[1:]**2)/2)/duration)),bias=float(error.mean()),
            maximum_abs=float(abs(error).max()),worst_source_row=int(f.source_row.iloc[int(np.argmax(abs(error)))]))
        normalized[name+'_measured']=f[name];normalized[name+'_predicted']=pred;normalized[name+'_error']=error
    input_bound=meta['channels']['module_current_A'].get('calibration',{}).get('absolute_uncertainty')
    if input_bound is None or result['comparisons']['module_current_A']['maximum_abs']>input_bound+1e-12:
        result['issues'].append('Simulated load differs from measured module current; reconfigure a sourced load profile before interpreting voltage errors')
    result['temperature_evidence']={name:dict(min_C=float(f[name].min()),max_C=float(f[name].max())) for name in CHANNELS if CHANNELS[name][0]=='degC'}
    result['issues'].append('Temperature has no model prediction; compare measured history to characterization evidence separately')
    result['status']='diagnostic comparison only; no accuracy pass configured'
    result['provenance']=dict(run_configuration_sha256=digest(run/'configuration.json'),trajectory_sha256=digest(run/'trajectory.csv'))
    compared=pd.DataFrame(normalized);compared.to_csv(out/'comparison.csv',index=False);save(out/'comparison.json',result)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(2,1,figsize=(10,6),layout='constrained')
    axes[0].plot(f.time_s,f.terminal_V,label='Imported terminal voltage')
    axes[0].plot(f.time_s,compared.terminal_V_predicted,label='Prediction');axes[0].set_ylabel('Voltage [V]');axes[0].legend()
    axes[1].plot(f.time_s,compared.terminal_V_error*1000);axes[1].set(xlabel='Elapsed time [s]',ylabel='Predicted - imported [mV]')
    residual_mV=compared.terminal_V_error.to_numpy()*1000
    padding=max(.5,float(np.ptp(residual_mV))*.1)
    axes[1].set_ylim(float(residual_mV.min())-padding,float(residual_mV.max())+padding)
    axes[1].ticklabel_format(axis='y',style='plain',useOffset=False)
    fig.suptitle(f"{meta['data_kind']} | source rows {int(f.source_row.iloc[0])}-{int(f.source_row.iloc[-1])} | diagnostic only")
    fig.savefig(out/'measured_vs_predicted.png',dpi=140);plt.close(fig)
    return result
