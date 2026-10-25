"""No-fit reference/origin diagnostics and an explicit research initial-state policy."""
import argparse
import csv
import json
import math
from pathlib import Path

import numpy as np

from ae_p45b_reproduction import ROOT, Table25, sha, write_json
from ae_p45b_low_soc import interpolate_adjacent
from ae_p45b_identifiability import compact_csv

LOCK='configs/ae_p45b_reference_origin_v1.json'
SCENARIOS={'primary_left':(1.,'left'),'primary_linear':(1.,'linear'),
           'origin_minus_0p005_left':(.995,'left'),'origin_minus_0p005_linear':(.995,'linear')}
WINDOWS=(60.,300.,600.)
ANCHOR='25degC_charge_direction_4p2V_equilibrium'
BASE_WARNING='Loaded C/30 reference; finite rests are not verified equilibrium OCV. No module validation.'


def read(path):
    with Path(path).open(encoding='utf-8',newline='') as f:return list(csv.DictReader(f))


def col(rows,key):return np.array([float(r[key]) for r in rows])


def charge_coordinate(times,current,origin=1.,mode='left',max_gap_s=None):
    t,i=np.asarray(times,float),np.asarray(current,float)
    if t.ndim!=1 or len(t)<2 or t.shape!=i.shape:raise ValueError('Need matched time/current vectors')
    if not all(np.all(np.isfinite(x)) for x in (t,i)) or not math.isfinite(origin):raise ValueError('Nonfinite charge inputs')
    d=np.diff(t)
    if np.any(d<=0):raise ValueError('Times must increase strictly')
    limit=max(120.,10*float(np.median(d))) if max_gap_s is None else float(max_gap_s)
    if not math.isfinite(limit) or limit<=0:raise ValueError('Invalid acquisition-gap declaration')
    if np.any(d>limit):raise ValueError('Possible acquisition gap; cannot infer omitted charge')
    if mode not in ('left','linear'):raise ValueError('Integration must be left or linear')
    applied=i[:-1] if mode=='left' else (i[:-1]+i[1:])/2
    return origin+np.r_[0.,np.cumsum(d*applied)/16200.]


def initial_state_policy(request,reference_support):
    """Declared metadata is never certified. No voltage-to-SOC route exists."""
    common={'mode','record_id','temperature_degC','protocol'}
    documented={'cell_id','preparation_source','anchor_definition','nominal_capacity_Ah',
        'history_source','time_s','current_A','polarity','integration','max_gap_s',
        'anchor_time_s','initial_time_s','initial_hysteresis','initial_polarization_V',
        'state_basis','state_source','reference_compatibility_source'}
    if not isinstance(request,dict):raise ValueError('Policy request must be an object')
    mode=request.get('mode','unknown')
    allowed=common|documented if mode=='declared_anchor' else common
    if set(request)-allowed:raise ValueError('Unknown or calibration fields are not allowed: '+', '.join(sorted(set(request)-allowed)))
    lo,hi=reference_support
    if not all(math.isfinite(x) for x in (lo,hi)) or lo>=hi:raise ValueError('Invalid reference support')
    result=dict(schema_version='voltforge.p45b_initial_state_policy/1',mode=mode,
        evidence_verified=False,experimental_accuracy_established=False,
        reference_kind='published loaded C/30 pOCV',reference_equilibrium_verified=False,
        warning=BASE_WARNING,initial_state=None,runnable=False,missing_evidence=[])
    if mode=='unknown':
        result.update(status='insufficient_evidence',missing_evidence=['traceable charge-origin/preparation history','initial hysteresis and polarization assumptions'])
        return result
    if mode not in ('author_reproduction','declared_anchor'):raise ValueError('Unsupported initial-state mode')
    required=common if mode=='author_reproduction' else common|documented
    missing=sorted(k for k in required if k not in request or request[k] is None or isinstance(request[k],str) and not request[k].strip())
    if missing:
        result.update(status='insufficient_evidence',missing_evidence=missing);return result
    if not isinstance(request['record_id'],str):raise ValueError('Record identity must be a nonempty string')
    if request['temperature_degC']!=25:raise ValueError('This policy supports nominal 25 degC only')
    if request['protocol']!='discharge':raise ValueError('Only the declared discharge route is implemented')
    if mode=='author_reproduction':
        if not lo<=1<=hi:raise ValueError('Author starting SOC outside reference support')
        result.update(status='conditional_author_reproduction',runnable=True,
            initial_state=dict(soc=1.,hysteresis=-1.,polarization_V=[0.,0.]),
            state_basis='documented author simulation assumptions; NOT measured initial state',
            source='SSRN 6861858, PDF pp.9,53',record_id=request['record_id'],
            missing_evidence=['record-specific preparation trace and cell identity','independent charge-origin verification','equilibrium reference compatibility'])
        return result
    if request['anchor_definition']!=ANCHOR or request['nominal_capacity_Ah']!=4.5:raise ValueError('Unsupported anchor/capacity convention')
    if request['polarity']!='charge_positive':raise ValueError('Explicit charge-positive current required; no automatic sign repair')
    if request['state_basis'] not in ('assumed','model_propagated'):raise ValueError('This tool cannot certify a measured or validated internal state')
    for k in ('cell_id','preparation_source','history_source','state_source','reference_compatibility_source'):
        if not isinstance(request[k],str) or not request[k].strip():raise ValueError('Named provenance declarations required')
    t=np.asarray(request['time_s'],float)
    if len(t)<2 or t[0]!=request['anchor_time_s'] or t[-1]!=request['initial_time_s']:raise ValueError('History must cover declared anchor to initial time')
    soc=charge_coordinate(t,request['current_A'],1.,request['integration'],request['max_gap_s'])
    if np.any(soc<lo) or np.any(soc>hi):raise ValueError('Declared history outside reference support; no clipping')
    h=float(request['initial_hysteresis']);v=np.asarray(request['initial_polarization_V'],float)
    if not math.isfinite(h) or not -1<=h<=1 or v.shape!=(2,) or not np.all(np.isfinite(v)):raise ValueError('Invalid declared internal states')
    result.update(status='conditional_declared_anchor',runnable=True,
        initial_state=dict(soc=float(soc[-1]),hysteresis=h,polarization_V=v.tolist()),
        state_basis=request['state_basis'],record_id=request['record_id'],
        declarations={k:request[k] for k in ('cell_id','preparation_source','history_source','state_source','reference_compatibility_source')},
        missing_evidence=['independent verification of declared source identity, preparation and current calibration',
            'reference compatibility with this physical cell and protocol','experimental accuracy for intended use'])
    return result


def metrics(t,error):
    t,error=np.asarray(t,float),np.asarray(error,float);valid=np.isfinite(error)
    d=np.diff(t);interval=valid[:-1]&valid[1:];duration=float(d[interval].sum())
    if not np.any(valid):return dict(samples=0,duration_s=0.,sample_rmse_mV=None,time_rmse_mV=None,sample_bias_mV=None,time_bias_mV=None,max_abs_mV=None)
    squared=error**2
    return dict(samples=int(valid.sum()),duration_s=duration,sample_rmse_mV=float(np.sqrt(np.mean(squared[valid]))),
        sample_bias_mV=float(error[valid].mean()),max_abs_mV=float(np.max(abs(error[valid]))),
        time_rmse_mV=float(np.sqrt(np.sum((d*(squared[:-1]+squared[1:])/2)[interval])/duration)) if duration else None,
        time_bias_mV=float(np.sum((d*(error[:-1]+error[1:])/2)[interval])/duration) if duration else None)


def reference_trace(table,source,origin,mode):
    t,i=col(source,'time_s'),col(source,'source_current_A');z=charge_coordinate(t,i,origin,mode)
    out=[];stopped=None
    for j,r in enumerate(source):
        if int(r['source_line'])!=j+2:raise ValueError('Original source-line order must be complete')
        if not all(math.isfinite(float(r[k])) for k in ('voltage_V','controlled_temperature_degC')):raise ValueError('Nonfinite measured channel')
        reference=None
        if stopped is None:
            try:p,_=table.query(float(z[j]));reference=float(p.ocv_discharge_V)
            except ValueError as e:stopped=dict(source_line=int(r['source_line']),reason=str(e))
        out.append(dict(source_line=int(r['source_line']),time_s=float(t[j]),source_current_A=float(i[j]),
            voltage_V=float(r['voltage_V']),controlled_temperature_degC=float(r['controlled_temperature_degC']),
            nominal_soc=float(z[j]),reference_V=reference,
            reference_minus_measured_mV=1000*(reference-float(r['voltage_V'])) if reference is not None else None,
            reference_status='defined_loaded_reference' if reference is not None else 'stopped_reference_undefined'))
    return out,stopped


def rest_window(rows,duration_s,end_time=None):
    if duration_s<=0 or not math.isfinite(duration_s):raise ValueError('Invalid rest window')
    if len(rows)<2:raise ValueError('Need a complete recorded rest')
    end=float(rows[-1]['time_s']) if end_time is None else float(end_time)
    start=end-duration_s
    selected=[r for r in rows if start<=r['time_s']<=end]
    result=dict(duration_requested_s=duration_s,window_end_time_s=end,source_first_line=None,source_last_line=None,
        samples=len(selected),measured_median_V=None,reference_median_V=None,slope_mV_per_min=None,
        reference_minus_measured_metrics=None,reference_status='unsupported_window',equilibrium_established=False)
    if len(selected)<3 or end-rows[0]['time_s']<duration_s or selected[-1]['time_s']-selected[0]['time_s']<.8*duration_s:
        result['reason']='insufficient complete window duration or samples';return result
    t=col(selected,'time_s');v=col(selected,'voltage_V');x=t-t[0];x-=x.mean()
    slope=float(np.dot(x,v-v.mean())/np.dot(x,x)*60000.)
    result.update(source_first_line=selected[0]['source_line'],source_last_line=selected[-1]['source_line'],
        observed_span_s=float(t[-1]-t[0]),measured_median_V=float(np.median(v)),slope_mV_per_min=slope,
        interpretation='finite observed rest only; no drift threshold establishes equilibrium')
    if any(r['reference_V'] is None for r in selected):
        result.update(reference_status='unsupported_reference',reason='reference undefined in this window');return result
    ref=col(selected,'reference_V')
    result.update(reference_status='defined_loaded_reference_comparison',reference_median_V=float(np.median(ref)),
        reference_minus_measured_metrics=metrics(t,1000*(ref-v)))
    return result


def rest_diagnostics(trace,segments,pairs):
    out=[]
    for p in pairs:
        seg=segments[int(p['rest_segment_id'])];a,b=int(seg['start_index']),int(seg['end_index'])
        rr=trace[a:b+1]
        if rr[0]['source_line']!=int(p['rest_first_source_line']) or rr[-1]['source_line']!=int(p['rest_last_source_line']):raise ValueError('Rest/source mismatch')
        windows={str(int(w)):rest_window(rr,w) for w in WINDOWS}
        earlier=rest_window(rr,300.,rr[-1]['time_s']-300.)
        recent=windows['300']['measured_median_V'];old=earlier['measured_median_V']
        out.append(dict(pair_index=int(p['pair_index']),rest_first_source_line=rr[0]['source_line'],rest_last_source_line=rr[-1]['source_line'],
            rest_duration_s=rr[-1]['time_s']-rr[0]['time_s'],rest_endpoint_nominal_soc=rr[-1]['nominal_soc'],
            windows=windows,preceding_300s=earlier,
            final_minus_preceding_300s_median_mV=1000*(recent-old) if recent is not None and old is not None else None,
            equilibrium_established=False))
    return out


def endpoint_context(co30,gitt,one):
    q=one[-1]['nominal_soc']
    slow=[(r['nominal_soc'],r['voltage_V'],r['source_line']) if r['source_current_A']<-.05 else None for r in co30]
    finite=[(r['rest_endpoint_nominal_soc'],r['windows']['60']['measured_median_V'],r['rest_last_source_line'])
        if r['windows']['60']['measured_median_V'] is not None else None for r in gitt]
    a=interpolate_adjacent(slow,[q])[0];b=interpolate_adjacent(finite,[q])[0]
    return dict(oneC_source_line=one[-1]['source_line'],nominal_soc=q,oneC_loaded_voltage_V=one[-1]['voltage_V'],
        co30_loaded=a,gitt_finite_rest=b,
        co30_minus_oneC_mV=1000*(a['value_V']-one[-1]['voltage_V']) if a['value_V'] is not None else None,
        gitt_minus_oneC_mV=1000*(b['value_V']-one[-1]['voltage_V']) if b['value_V'] is not None else None,
        reference_minus_oneC_mV=one[-1]['reference_minus_measured_mV'],
        cross_record_cell_and_preparation_equivalence='unverified; coordinate comparison only')


def policy_examples(table):
    support=(table.soc[0],table.soc[-1]);cases={}
    for record in ('co30','gitt','oneC'):
        req=dict(mode='author_reproduction',record_id='already_opened_25degC_'+record,temperature_degC=25,protocol='discharge')
        cases[record]=dict(request=req,response=initial_state_policy(req,support),evidence='real record classification; no invented preparation metadata')
    req=dict(mode='declared_anchor',record_id='SYNTHETIC',temperature_degC=25,protocol='discharge',cell_id='SYNTHETIC_CELL',
        preparation_source='SYNTHETIC fixture, not a real preparation log',anchor_definition=ANCHOR,nominal_capacity_Ah=4.5,
        history_source='SYNTHETIC history',time_s=[0.,60.,120.],current_A=[-4.5,-4.5,0.],polarity='charge_positive',
        integration='left',max_gap_s=60.,anchor_time_s=0.,initial_time_s=120.,initial_hysteresis=-1.,
        initial_polarization_V=[-.01,-.02],state_basis='assumed',state_source='SYNTHETIC assumed states',
        reference_compatibility_source='SYNTHETIC declaration; not independently verified')
    cases['synthetic_declared_anchor']=dict(request=req,response=initial_state_policy(req,support),evidence='SYNTHETIC SOFTWARE EXAMPLE ONLY')
    req=dict(mode='unknown',record_id='unknown');cases['unknown']=dict(request=req,response=initial_state_policy(req,support))
    return cases


def load_sources():
    lock=json.loads((ROOT/LOCK).read_text())
    for name,expected in lock['frozen_files'].items():
        if sha(ROOT/name)!=expected:raise ValueError('Source/procedure changed: '+name)
    return lock,Table25((ROOT/lock['parameter_table']).read_bytes()),{k:read(ROOT/v) for k,v in lock['saved_records'].items()},read(ROOT/lock['saved_segments']),read(ROOT/lock['saved_pairs'])


def plots(results,out):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    primary=results['primary_left'];pairs=primary['pairs'];source=primary['traces']['gitt']
    chosen=list(dict.fromkeys([min(pairs,key=lambda p:abs(p['rest_endpoint_nominal_soc']-z))['pair_index'] for z in [.5,.1,.04]]+[pairs[-1]['pair_index']]))
    fig,axes=plt.subplots(2,2,figsize=(13,8),constrained_layout=True)
    for ax,pid in zip(axes.flat,chosen):
        p=next(p for p in pairs if p['pair_index']==pid);rr=source[p['rest_first_source_line']-2:p['rest_last_source_line']-1]
        t=col(rr,'time_s');elapsed=t-t[0]
        ax.plot(elapsed,col(rr,'voltage_V'),color='#1c252e',label='Measured finite rest')
        ax.plot(elapsed,[r['reference_V'] if r['reference_V'] is not None else np.nan for r in rr],color='#a96d25',label='Loaded C/30 reference')
        for w,color in zip(WINDOWS,['#136b79','#4f8391','#a9bec1']):ax.axvline(elapsed[-1]-w,color=color,lw=.7,ls='--',label=f'Final {int(w)} s begins')
        ax.set_title(f"Pair {pid}, nominal SOC {p['rest_endpoint_nominal_soc']:.3f}");ax.set_xlabel('Time since rest began (s)');ax.set_ylabel('Voltage (V)');ax.grid(alpha=.2)
    axes.flat[0].legend(fontsize=7)
    fig.suptitle('Complete used GITT rests: finite windows do not establish equilibrium\nSource: About:Energy P45B 25 degC; original source-line windows in rest JSON')
    fig.savefig(out/'complete_rests.png',dpi=150);plt.close(fig)
    fig,axes=plt.subplots(2,2,figsize=(13,9),constrained_layout=True)
    for scenario,result in results.items():
        p=result['pairs'];z=[r['rest_endpoint_nominal_soc'] for r in p]
        for w in ['60','300','600']:
            if scenario=='primary_left':axes[0,0].plot(z,[r['windows'][w]['slope_mV_per_min'] for r in p],'.-',label=f'Final {w} s')
        axes[0,1].plot(z,[r['final_minus_preceding_300s_median_mV'] for r in p],'.-',label=scenario)
        axes[1,0].plot(z,[r['windows']['60']['reference_minus_measured_metrics']['sample_bias_mV'] if r['windows']['60']['reference_minus_measured_metrics'] else np.nan for r in p],'.-',label=scenario)
        rr=result['traces']['co30'];axes[1,1].plot([r['nominal_soc'] for r in rr],[r['reference_minus_measured_mV'] if r['reference_minus_measured_mV'] is not None else np.nan for r in rr],label=scenario)
    for ax,label in zip(axes.flat,['Measured finite-window drift (mV/min)','Final minus preceding 300 s median (mV)','Final-60-s reference minus measurement (mV)','C/30 reference minus loaded voltage (mV)']):
        ax.set_ylabel(label);ax.set_xlabel('Assumed nominal SOC');ax.grid(alpha=.2);ax.legend(fontsize=7)
    fig.suptitle('All 32 rests and declared origin/integration sensitivities\nReference differences are not dynamic prediction errors; no SOC tuning')
    fig.savefig(out/'reference_origin_diagnostics.png',dpi=150);plt.close(fig)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True);args=p.parse_args();out=args.out.resolve()
    if not any(out.is_relative_to(ROOT/x) for x in ('tmp','reports')):raise SystemExit('Output must be under tmp/ or reports/')
    if out.exists():raise SystemExit('Refuse to overwrite existing output')
    lock,table,sources,segments,pairs=load_sources();out.mkdir(parents=True);results={};summary={}
    for name,(origin,mode) in SCENARIOS.items():
        traces={};stops={};stats={}
        for record,source in sources.items():
            print(name,record,flush=True);trace,stop=reference_trace(table,source,origin,mode);traces[record]=trace;stops[record]=stop
            compact_csv(out/(name+'_'+record+'.csv.gz'),trace)
            stats[record]=dict(samples=len(trace),origin_soc=origin,integration=mode,final_nominal_soc=trace[-1]['nominal_soc'],
                charge_passed_Ah=4.5*(trace[-1]['nominal_soc']-origin),reference_stop=stop,
                full_reference_difference=metrics(col(trace,'time_s'),np.array([r['reference_minus_measured_mV'] if r['reference_minus_measured_mV'] is not None else np.nan for r in trace])))
        rest=rest_diagnostics(traces['gitt'],segments,pairs);write_json(out/(name+'_rests.json'),rest)
        results[name]=dict(traces=traces,pairs=rest)
        summary[name]=dict(records=stats,endpoint_context=endpoint_context(traces['co30'],rest,traces['oneC']))
    plots(results,out);write_json(out/'policy_examples.json',policy_examples(table))
    result=dict(schema_version='voltforge.p45b_reference_origin/1',source_lock=lock,
        implementation_sha256={n:sha(ROOT/n) for n in ['scripts/ae_p45b_reference_origin.py','scripts/verify_p45b_reference_origin.py','tests/test_ae_p45b_reference_origin.py']},
        source='Dickinson et al., About:Energy (2026), https://zenodo.org/records/19052626, CC BY 4.0',
        scenarios=summary,reference_support=[table.soc[0],table.soc[-1]],parameter_fits=0,models_adopted=False,
        fresh_independent_assessment=False,new_measurement_families_opened=0,remaining_unopened_members=48,remaining_unopened_families=40,
        initial_state_evidence='author assumptions; record-specific preparation/cell mapping not verified',
        equilibrium_reference_established=False,experimental_module_validation='awaiting suitable measurements',
        requirements='requirement not configured',affected_design_decision='insufficient evidence')
    write_json(out/'summary.json',result);write_json(out/'manifest.json',{f.name:sha(f) for f in sorted(out.iterdir()) if f.is_file()})
    print('No-fit reference/origin diagnostics complete; no model adopted.')


if __name__=='__main__':main()
