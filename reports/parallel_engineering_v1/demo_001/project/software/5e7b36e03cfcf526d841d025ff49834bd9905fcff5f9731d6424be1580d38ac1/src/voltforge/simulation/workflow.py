"""Configure, simulate and compare predeclared module scenarios without fitting."""
import copy
import json
import re
from pathlib import Path
from zipfile import ZipFile
import numpy as np
import pandas as pd
from voltforge.models import improvement as m
from voltforge.models import coupling_v2 as dynamic

APPLICATION=Path('configs/module_application_v1.json')
SCENARIOS=Path('configs/module_scenarios_v1.json')
DEFAULT_OUT=Path('reports/module_simulation_v1')


def digest(p): return m.v1.digest(p)
def read(p): return m.read_json(p)
def save(p,value): return m.save(p,value)


def safe_output(out):
    out=Path(out).resolve()
    protected=[Path(p).resolve() for p in ['reports/identification_v1','reports/improvement_v2','reports/reference_initial_state_v1','data/raw','src','configs']]
    if any(out==p or p in out.parents for p in protected): raise ValueError('Output would enter a protected/source directory')
    return out


def check_baseline():
    lock=read('configs/reference_initial_state_v1.lock.json')
    for p,h in lock['protected'].items():
        if digest(p)!=h: raise ValueError('Preserved baseline changed: '+p)
    return len(lock['protected'])


def check_case(c):
    if c['topology']!='1s4p same-side-terminal ladder' or c['cell_order']!=['P7','P17','P19','P13']:
        raise ValueError('This application version supports the declared four-cell order only')
    if c['reference_extrapolation']!='forbidden': raise ValueError('No reference extrapolation implemented')
    if c['permit_unvalidated_waveform_transfer'] is not True: raise ValueError('Investigation requires explicit permission for unvalidated waveform transfer')
    for key,n in [('initial_soc',4),('initial_polarization_V',4),('positive_rail_ohm',3),('negative_rail_ohm',3)]:
        a=np.asarray(c[key],float)
        if a.shape!=(n,) or not np.isfinite(a).all(): raise ValueError('Invalid '+key)
        if 'rail' in key and np.any(a<0): raise ValueError('Negative rail resistance')
    if not np.isfinite(c['dt_s']) or c['dt_s']<=0: raise ValueError('Invalid time step')
    dynamic.validate_profile(c['load'])
    t=c['temperature']
    if t['thermal_model'] or t['parameter_temperature_scaling']: raise ValueError('No thermal model or temperature law')
    if len(t['assumed_surface_C'])!=4 or not np.isfinite(t['assumed_surface_C']+[t['assumed_ambient_C']]).all(): raise ValueError('Temperature assumptions must be explicit')
    req=c['requirements']
    if req['minimum_terminal_voltage_V'] is not None and (not np.isfinite(req['minimum_terminal_voltage_V']) or req['minimum_terminal_voltage_V']<=0): raise ValueError('Invalid minimum voltage')
    if req['maximum_contiguous_excursion_s'] is not None and (not np.isfinite(req['maximum_contiguous_excursion_s']) or req['maximum_contiguous_excursion_s']<0): raise ValueError('Invalid excursion duration')


def configure(out=DEFAULT_OUT,application=APPLICATION,scenarios=SCENARIOS):
    out=safe_output(out);check_baseline();app=read(application);plan=read(scenarios);check_case(app)
    inputs={str(Path(p).as_posix()):digest(p) for p in [application,scenarios,'SIMULATION_PLAN.md']}
    if (out/'manifest.json').exists():
        if read(out/'manifest.json')['declared_inputs']!=inputs: raise ValueError('Configuration changed; use a new version/output directory')
        load_configuration(out);print('Existing predeclared configuration verified.');return out
    out.mkdir(parents=True,exist_ok=True);models=[];sources={};model_seal=read(m.OUT/'procedure_seal.json')
    for cell in app['cell_order']:
        p=Path(app['model_directory'])/f'{cell}_models.json'
        h=digest(p)
        if model_seal['artifacts'].get(p.as_posix())!=h: raise ValueError('Model does not match frozen v2 seal')
        full=read(p)[app['model_key']]
        models.append({k:full[k] for k in ['kind','parameters_ohm','tau_s','capacity_Ah','reference','soc_knots']})
        sources[cell]=dict(path=p.as_posix(),sha256=h,classification=app['parameter_classification'])
    # Only already-used C/20 files, no HPPC or module measurement outcomes.
    arrays={};low_sources={};lock=read(m.LOCK)
    with ZipFile(m.v1.source_archive()) as z:
        for cell in app['cell_order']:
            low,source=m.v1.read_cell(z,cell,'low_rate')
            if source['sha256']!=lock['cells'][cell]['sha256']['low_rate']: raise ValueError('C/20 source changed')
            _,x,y=m.v1.loaded_curve(low);arrays[cell+'_soc']=x;arrays[cell+'_V']=y;low_sources[cell]=source
    np.savez_compressed(out/'reference_sensitivity.npz',**arrays)
    fit={r['cell']:r for r in read(m.OUT/'calibration_coverage.json')}
    assessed=pd.read_csv(m.OUT/'observed_evaluation_coverage.csv')
    materialized=[];ids=set()
    for scenario in plan['scenarios']:
        name=scenario['id']
        if not re.fullmatch('[a-z0-9_]+',name) or name in ids: raise ValueError('Invalid/duplicate scenario ID')
        ids.add(name);c=copy.deepcopy(app)
        if set(scenario['overrides'])-{'initial_soc','positive_rail_ohm','negative_rail_ohm','load'}: raise ValueError('Undeclared override')
        c.update(scenario['overrides']);check_case(c);c.update(id=name,description=scenario['description'],models=models,
            reference_kind='sealed_rest_pchip',capacity_factor=1.,origin_shift=0.,run_type='manual scenario',
            fitting_evidence={s:fit[s] for s in app['cell_order']},
            assessment_evidence={s:assessed[assessed.cell==s].to_dict('records') for s in app['cell_order']})
        save(out/'configured'/f'{name}.json',c);materialized.append(name)
    save(out/'scenario_plan.json',plan)
    generated=[out/'reference_sensitivity.npz',out/'scenario_plan.json']+list((out/'configured').glob('*.json'))
    save(out/'manifest.json',dict(schema_version=1,configured_utc=m.now(),declared_inputs=inputs,
        model_sources=sources,loaded_reference_sources=low_sources,
        artifacts={p.relative_to(out).as_posix():digest(p) for p in generated},scenarios=materialized,
        experimental_validation='awaiting suitable measurements',new_characterization_cells_opened=[],
        measurement_outcomes_opened=[],note='Scenario assumptions recorded before new simulation outputs.'))
    print('Configured four scenarios before simulation; requirements remain unset.',flush=True)
    return out


def load_configuration(out):
    out=Path(out);manifest=read(out/'manifest.json')
    for p,h in manifest['artifacts'].items():
        if digest(out/p)!=h: raise ValueError('Configured scenario/reference changed: '+p)
    for source in manifest['model_sources'].values():
        if digest(source['path'])!=source['sha256']: raise ValueError('Frozen model changed')
    for p,h in manifest['declared_inputs'].items():
        if digest(p)!=h: raise ValueError('Predeclared input changed: '+p)
    return manifest


def intervals(f,mask):
    """Contiguous held-input intervals; terminal-only samples contribute no duration."""
    out=[]
    for t,h,ok in zip(f.time_s,f.step_s,np.asarray(mask,bool)):
        if not ok or h<=0: continue
        if out and abs(out[-1]['end_s']-t)<1e-9: out[-1]['end_s']=float(t+h)
        else: out.append(dict(start_s=float(t),end_s=float(t+h)))
    for r in out:r['duration_s']=r['end_s']-r['start_s']
    return out


def coverage(f,c,status):
    cells={};global_reasons=['Module waveform/current-sharing accuracy has no experimental validation',
        'Initial SOC and polarization are assumptions', 'Rail/contact values and feasibility unverified',
        'Module surface-temperature history unmeasured; no thermal model']
    for k,cell in enumerate(c['cell_order'],1):
        fit=c['fitting_evidence'][cell];current=f[f'I{k}_A'];soc=f[f'SOC{k}']-c['origin_shift']
        groups={'charge':current<-.01,'rest':abs(current)<=.01,'discharge':current>.01,
            'discharge_below_4_8A':(current>.01)&(current<4.8),'near_4_85A':current.between(4.8,4.9),
            'above_4_9A':current>4.9,
            'outside_fitting_amplitude':(current<fit['actual_fit_current_min_A'])|(current>fit['actual_fit_current_max_A']),
            'outside_v2_primary_SOC_current':~(soc.between(.2,.8)&current.between(-.01,4.9))}
        iv={name:intervals(f,mask) for name,mask in groups.items()}
        durations={name:sum(x['duration_s'] for x in seq) for name,seq in iv.items()}
        longest={name:max([x['duration_s'] for x in seq],default=0.) for name,seq in iv.items()}
        reasons=list(global_reasons)
        if longest['above_4_9A']>fit['bands']['above_4_9A']['longest_observed_contiguous_span_s']:
            reasons.append('Contiguous >4.9 A load exceeds observed brief calibration span')
        if durations['outside_fitting_amplitude']:reasons.append('Current leaves fitted amplitude range')
        if durations['outside_v2_primary_SOC_current']:reasons.append('Leaves primary assessed SOC/current subset')
        if not 22<=c['temperature']['assumed_surface_C'][k-1]<=28:reasons.append('Assumed temperature outside primary subset')
        a=c['models'][k-1]['reference']['rest']
        cells[cell]=dict(SOC_range=[float(soc.min()),float(soc.max())],current_range_A=[float(current.min()),float(current.max())],
            reference_SOC_bounds=[a[0]['soc'],a[-1]['soc']],mathematical_support=status=='completed',
            initial_soc=c['initial_soc'][k-1],initial_polarization_V=c['initial_polarization_V'][k-1],
            temperature_assumption_C=c['temperature']['assumed_surface_C'][k-1],temperature_prediction=None,
            fitting=fit,assessment=c['assessment_evidence'][cell],intervals=iv,total_duration_s=durations,longest_duration_s=longest,
            experimental_waveform_support='unsupported transfer',reasons=reasons,
            interpretation='Amplitude bands are descriptive only. Even matching a plateau amplitude/duration is not validation of this module waveform.')
    return dict(cells=cells,experimental_validation='awaiting suitable measurements',decision='insufficient evidence')


def requirement_result(f,c,completed):
    r=c['requirements']
    if any(r.get(k) is None or r.get(k)=='' for k in ['minimum_terminal_voltage_V','maximum_contiguous_excursion_s','documented_source']):
        return dict(status='requirement not configured',reason='Load/device minimum voltage, permitted excursion and documented source must all be supplied')
    if not completed:return dict(status='insufficient simulation',reason='Run stopped before requested duration')
    # Sampled/held interval screen, not a certified crossing-time estimator.
    seq=intervals(f,f.terminal_V<r['minimum_terminal_voltage_V'])
    longest=max([v['duration_s'] for v in seq],default=0.)
    return dict(status='simulated excursion exceeds configured limit' if longest>r['maximum_contiguous_excursion_s'] else 'no sampled exceedance; insufficient evidence for a pass',
        longest_sampled_excursion_s=longest,intervals=seq,source=r['documented_source'],
        note='Finite time-step diagnostic. Does not resolve excursions between sample nodes or experimental model uncertainty.')


def execute_case(c,curves):
    return dynamic.simulate(c['models'],c['initial_soc'],c['initial_polarization_V'],c['load'],c['dt_s'],
        c['positive_rail_ohm'],c['negative_rail_ohm'],capacity_factor=c['capacity_factor'],reference_kind=c['reference_kind'],
        loaded_curves=curves,origin_shift=c['origin_shift'])


def summarize(result,c):
    f=result.frame
    base=dict(id=c['id'],run_type=c['run_type'],status=result.status,stop=result.stop,
        experimental_validation='awaiting suitable measurements',decision='insufficient evidence',
        decision_reasons=['Voltage requirement not established' if c['requirements']['minimum_terminal_voltage_V'] is None else 'No experimental error bound',
                          'Unvalidated module-current reference and waveform transfer','Unverified initial states, temperature and physical connections'])
    if not len(f):return dict(**base,voltage_requirement=requirement_result(f,c,False))
    cover=coverage(f,c,result.status)
    base.update(maximum_branch_current_A=float(f[[f'I{k}_A' for k in range(1,5)]].max().max()),
        minimum_branch_current_A=float(f[[f'I{k}_A' for k in range(1,5)]].min().min()),
        minimum_cell_voltage_V=float(f[[f'V{k}_V' for k in range(1,5)]].min().min()),minimum_terminal_voltage_V=float(f.terminal_V.min()),
        delivered_net_Wh=float(f.delivered_net_Wh.iloc[-1]),delivered_positive_Wh=float(f.delivered_positive_Wh.iloc[-1]),
        received_Wh=float(f.received_Wh.iloc[-1]),mean_delivered_power_W=float(f.delivered_net_Wh.iloc[-1]*3600/f.time_s.iloc[-1]) if f.time_s.iloc[-1]>0 else None,
        requested_charge_Ah=float(sum(p['current_A']*(p['end_s']-p['start_s']) for p in c['load'])/3600),
        delivered_charge_Ah=float(f.module_charge_As.iloc[-1]/3600),
        R0_and_rail_loss_Wh=float(f.R0_and_rail_loss_Wh.iloc[-1]),R1_loss_Wh=float(f.R1_loss_Wh.iloc[-1]),
        cell_R0_loss_Wh=float(np.dot(f.cell_R0_loss_W,f.step_s)/3600),rail_loss_Wh=float(np.dot(f.rail_loss_W,f.step_s)/3600),
        maximum_total_resistive_loss_W=float((f.cell_R0_loss_W+f.rail_loss_W+f.polarization_R1_loss_W).max()),
        max_kcl_residual_A=float(abs(f.kcl_residual_A).max()),max_charge_balance_As=float(abs(f.charge_balance_As).max()),
        max_instantaneous_power_balance_W=float(abs(f.complete_power_residual_W).max()),
        final_energy_balance_residual_Wh=float(f.energy_balance_residual_Wh.iloc[-1]),
        above_4_9A_cell_seconds=sum(v['total_duration_s']['above_4_9A'] for v in cover['cells'].values()),
        coverage=cover,voltage_requirement=requirement_result(f,c,result.status=='completed'))
    return base


def simulate_all(out=DEFAULT_OUT,include_sensitivities=True):
    out=safe_output(out);manifest=load_configuration(out);plan=read(out/'scenario_plan.json');verification={}
    with np.load(out/'reference_sensitivity.npz',allow_pickle=False) as npz:
        curves=[(npz[s+'_soc'].copy(),npz[s+'_V'].copy()) for s in ['P7','P17','P19','P13']]
    for name in manifest['scenarios']:
        base=read(out/'configured'/f'{name}.json');jobs=[base]
        if include_sensitivities:
            for change in plan['sensitivity_scenarios']:
                c=copy.deepcopy(base);c['id']=name+'__'+change['id'];c['run_type']='sensitivity scenario'
                c['sensitivity']=change;c['parent_scenario']=name
                c['initial_soc']=[v+change.get('soc_delta',0) for v in c['initial_soc']]
                c['initial_polarization_V']=[v+change.get('polarization_delta_V',0) for v in c['initial_polarization_V']]
                c['capacity_factor']=change.get('capacity_factor',1.);c['reference_kind']=change.get('reference','sealed_rest_pchip');jobs.append(c)
        for c in jobs:
            result=execute_case(c,curves);folder=out/'runs'/c['id'];folder.mkdir(parents=True,exist_ok=True)
            save(folder/'configuration.json',c)
            (result.frame if len(result.frame) else pd.DataFrame(columns=['time_s','step_s'])).to_csv(folder/'trajectory.csv',index=False)
            score=summarize(result,c);score['provenance']=dict(config_sha256=digest(folder/'configuration.json'),
                manifest_sha256=digest(out/'manifest.json'),implementation_sha256=digest('src/voltforge/models/coupling_v2.py'))
            save(folder/'summary.json',score)
            if c is base:reference=result.frame;main_status=result.status
        if main_status!='completed':
            verification[name]=dict(status='Time-step and coordinate checks unavailable: main simulation stopped')
            continue
        convergence=[]
        for dt in plan['time_step_checks_s']:
            if dt==base['dt_s']:f=reference
            else:
                c=copy.deepcopy(base);c['dt_s']=dt;f=execute_case(c,curves).frame
            delta={col:float(np.max(abs(f[col]-np.interp(f.time_s,reference.time_s,reference[col])))) for col in
                ['terminal_V']+[f'I{k}_A' for k in range(1,5)]+[f'SOC{k}' for k in range(1,5)]}
            convergence.append(dict(dt_s=dt,max_differences=delta,delivered_energy_difference_Wh=float(f.delivered_net_Wh.iloc[-1]-reference.delivered_net_Wh.iloc[-1]),
                energy_balance_residual_Wh=float(f.energy_balance_residual_Wh.iloc[-1])))
        verification[name]=dict(time_step_sensitivity=convergence)
        if name=='equal_soc':
            verification[name]['coordinate_relabelling']=[]
            for change in plan['coordinate_checks']:
                c=copy.deepcopy(base);c['origin_shift']=change['origin_shift'];c['initial_soc']=[v+c['origin_shift'] for v in c['initial_soc']]
                f=execute_case(c,curves).frame
                verification[name]['coordinate_relabelling'].append(dict(shift=change['origin_shift'],
                    max_voltage_change_V=float(abs(f.terminal_V-reference.terminal_V).max()),
                    max_current_change_A=float(np.max(abs(f[[f'I{k}_A' for k in range(1,5)]].to_numpy()-reference[[f'I{k}_A' for k in range(1,5)]].to_numpy())))))
        print(name,'simulation, sensitivities and time-step checks complete',flush=True)
    save(out/'software_verification.json',verification);check_baseline()
    return verification
