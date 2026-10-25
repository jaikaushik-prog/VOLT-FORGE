"""Independent equation, constrained-fit, source and preservation checks."""
import argparse
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET

import numpy as np

from ae_p45b_reproduction import ROOT, sha, write_json
from verify_p45b_identifiability import verify as verify_previous
from ae_p45b_local_dynamics import read_csv, column


def direct_voltage(t,current,reference,tau,resistance,initial):
    x1,x2=map(float,initial);out=[]
    for j,time in enumerate(t):
        if j:
            dt=time-t[j-1];a=math.exp(-dt/tau[0]);b=math.exp(-dt/tau[1])
            x1=x1*a+current[j-1]*resistance[1]*(1-a)
            x2=x2*b+current[j-1]*resistance[2]*(1-b)
        out.append(reference[j]+current[j]*resistance[0]+x1+x2)
    return np.asarray(out)


def weights(t):
    d=np.diff(t);w=np.zeros(len(t));w[:-1]+=d/2;w[1:]+=d/2
    return w/w.sum()


def independent_metrics(t,measured,predicted):
    e=1000*(predicted-measured);d=np.diff(t);duration=t[-1]-t[0]
    return dict(sample_rmse_mV=float(np.sqrt(np.mean(e**2))),sample_bias_mV=float(e.mean()),
        time_rmse_mV=float(np.sqrt(np.sum(d*(e[1:]**2+e[:-1]**2)/2)/duration)),
        time_bias_mV=float(np.sum(d*(e[1:]+e[:-1])/2)/duration),max_abs_error_mV=float(np.max(abs(e))))


def check_kkt(a,target,w,r):
    lower=np.array([0.,1e-6,1e-6]);upper=np.full(3,.2);r=np.asarray(r)
    assert np.all(r>=lower-1e-12) and np.all(r<=upper+1e-12)
    g=a.T@(w*(a@r-target))/w.sum()
    for j in range(3):
        if r[j]<=lower[j]+1e-9:assert g[j]>=-1e-8,(j,g)
        elif r[j]>=upper[j]-1e-9:assert g[j]<=1e-8,(j,g)
        else:assert abs(g[j])<1e-8,(j,g)


def verify(run,tests=None):
    prior=verify_previous(ROOT/'reports/p45b_identifiability_v1/run_002')
    previous_receipt=json.loads((ROOT/'reports/p45b_identifiability_v1/verification.json').read_text())
    for name,expected in previous_receipt['artifacts'].items():
        path=ROOT/'reports/parallel_engineering_v1/previous/README.md' if name=='README.md' else ROOT/name
        assert sha(path)==expected,name
    summary=json.loads((run/'summary.json').read_text());lock=summary['source_lock']
    assert lock==json.loads((ROOT/'configs/ae_p45b_local_dynamics_v1.json').read_text())
    for name,expected in lock['frozen_files'].items():assert sha(ROOT/name)==expected,name
    for name,expected in summary['implementation_sha256'].items():assert sha(ROOT/name)==expected,name
    for name,expected in json.loads((run/'manifest.json').read_text()).items():assert sha(run/name)==expected,name
    assert not summary['models_adopted'] and not summary['deployable_SOC_law']
    assert not summary['fresh_independent_assessment'] and summary['new_measurement_families_opened']==0
    assert summary['remaining_unopened_members']==48 and summary['remaining_unopened_families']==40
    source=read_csv(ROOT/lock['saved_samples']);groups=json.loads((ROOT/lock['saved_allocation']).read_text())
    checked=0;largest_closure=0.
    for scenario,path in lock['saved_replays'].items():
        saved=read_csv(ROOT/path);exported=read_csv(run/(scenario+'.csv.gz'))
        pairs=json.loads((run/(scenario+'_pairs.json')).read_text())
        assert [p['pair_index'] for p in pairs]==list(range(21,32))
        expected_lines=[]
        for group,desc in zip(groups,pairs):
            first,last=group['first_source_line']-2,group['last_source_line']-2
            rows=[r for r in exported if int(r['pair_index'])==group['pair_index']]
            expected_lines.extend(range(first+2,last+3))
            assert [int(r['source_line']) for r in rows]==list(range(first+2,last+3))
            for key in ['source_line','time_s','source_current_A','voltage_V','controlled_temperature_degC']:
                assert np.array_equal(column(rows,key),column(source[first:last+1],key)),key
            for key in ['soc','reference_V']:
                assert np.array_equal(column(rows,key),column(saved[first:last+1],key)),key
            t,i,y,ref=[column(rows,key) for key in ['time_s','source_current_A','voltage_V','reference_V']]
            split=desc['rest_first_source_line']-desc['first_source_line']
            w=np.r_[.5*weights(t[:split]),.5*weights(t[split:])]
            assert np.max(abs(w-column(rows,'weight')))<1e-15
            initial=desc['local_initial_RC_V']
            assert initial==[float(saved[first]['v1_V']),float(saved[first]['v2_V'])]
            definitions={'L0':(desc['published_tau_s'],desc['published_resistance_Ohm']),
                'LR':(desc['published_tau_s'],desc['LR_resistance_Ohm']),
                'LRT':(desc['LRT']['tau_s'],desc['LRT']['resistance_Ohm'])}
            for name,(tau,r) in definitions.items():
                prediction=direct_voltage(t,i,ref,tau,r,initial)
                closure=float(np.max(abs(prediction-column(rows,name+'_V'))));largest_closure=max(largest_closure,closure)
                assert closure<1e-10
            assert np.array_equal(column(rows,'B0_V'),column(saved[first:last+1],'predicted_voltage_V'))
            for name in ['B0','L0','LR','LRT']:
                yp=column(rows,name+'_V');metrics=desc['metrics'][name]
                for phase,s in [('full',slice(None)),('pulse',slice(None,split)),('rest',slice(split,None))]:
                    for key,value in independent_metrics(t[s],y[s],yp[s]).items():
                        assert abs(value-metrics[phase][key])<1e-7,(scenario,group['pair_index'],name,key)
                objective=1000*math.sqrt(float(np.dot(w,(yp-y)**2)))
                assert abs(objective-metrics['objective_rmse_mV'])<1e-7
                late=t>=t[-1]-60;centered=(yp[split:]-np.median(yp[late]))-(y[split:]-np.median(y[late]))
                center=1000*np.sqrt(np.dot(weights(t[split:]),centered**2))
                assert abs(center-metrics['centered_rest_time_rmse_mV'])<1e-7
            # Rebuild each basis using an independent state recurrence; verify every grid optimum.
            for point in desc['grid']:
                tau=point['tau_s'];zero=np.zeros(len(t))
                memory=direct_voltage(t,i,zero,tau,[0,0,0],initial)
                a=np.column_stack([i,direct_voltage(t,i,zero,tau,[0,1,0],[0,0]),direct_voltage(t,i,zero,tau,[0,0,1],[0,0])])
                target=y-ref-memory;r=np.array(point['resistance_Ohm'])
                check_kkt(a,target,w,r)
                score=1000*np.sqrt(np.dot(w,(a@r-target)**2))
                assert abs(score-point['objective_rmse_mV'])<1e-7
            assert desc['LRT']==min(desc['grid'],key=lambda p:p['objective_rmse_mV'])
            assert desc['LRT']['objective_rmse_mV']<=desc['LR_objective_rmse_mV']+1e-7
            sensitivity=desc['conditional_initial_polarization_sensitivity'];chosen=desc['LRT']
            history=source[:first+1];ht,hi=column(history,'time_s'),column(history,'source_current_A')
            history_initial=[]
            for j in range(2):
                r=[0,0,0];r[j+1]=chosen['resistance_Ohm'][j+1]
                history_initial.append(float(direct_voltage(ht,hi,np.zeros(len(ht)),chosen['tau_s'],r,[0,0])[-1]))
            assert np.max(abs(np.array(history_initial)-sensitivity['initial_RC_from_constant_local_history_V']))<1e-11
            expected=direct_voltage(t,i,ref,chosen['tau_s'],chosen['resistance_Ohm'],history_initial)
            assert np.max(abs(expected-column(rows,'LRT_history_sensitivity_V')))<1e-10
            checked+=1
        assert [int(r['source_line']) for r in exported]==expected_lines
    tests_result={}
    if tests:
        suite=ET.parse(tests).getroot().find('testsuite')
        assert all(suite.get(key)=='0' for key in ['failures','errors','skipped'])
        tests_result=dict(path=str(tests),passed=int(suite.get('tests')),sha256=sha(tests))
    return dict(schema_version='voltforge.p45b_local_dynamics_verification/1',
        checked_complete_pairs_and_scenarios=checked,maximum_equation_closure_V=largest_closure,
        all_grid_bounded_optima_KKT_checked=True,original_channels_and_complete_pairs_preserved=True,
        previous_stage_artifacts_preserved=len(previous_receipt['artifacts']),
        prior_LG_artifacts=prior.get('protected_LG_artifacts'),remaining_unopened_P45B_members=48,
        tests=tests_result,source_allocation='used development evidence only',
        experimental_validation='not established',run=str(run.relative_to(ROOT)))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',type=Path,default=ROOT/'reports/p45b_local_dynamics_v1/run_001')
    parser.add_argument('--tests',type=Path)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args();result=verify(args.run.resolve(),args.tests)
    args.out.parent.mkdir(parents=True,exist_ok=True);write_json(args.out,result)
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
