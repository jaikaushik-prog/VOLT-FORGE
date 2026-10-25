"""Independent bookkeeping, constrained-fit optimality and preservation checks."""
import argparse
import csv
import gzip
import json
from pathlib import Path
import xml.etree.ElementTree as ET

import numpy as np

from ae_p45b_reproduction import ROOT, sha, write_json
from verify_p45b_gitt_replay import verify as verify_previous


def read(path):
    with gzip.open(path,'rt',encoding='utf-8',newline='') if path.suffix=='.gz' else path.open(encoding='utf-8',newline='') as f:
        return list(csv.DictReader(f))


def column(rows,key):
    return np.array([float(r[key]) if r[key] else np.nan for r in rows])


def independent_metrics(t, measured, predicted):
    valid = np.isfinite(predicted); error = 1000*(predicted-measured)
    dt = np.diff(t); intervals = valid[:-1]&valid[1:]; duration = float(dt[intervals].sum())
    return dict(samples=int(valid.sum()),covered_duration_s=duration,
        sample_rmse_mV=float(np.sqrt(np.mean(error[valid]**2))) if any(valid) else None,
        sample_bias_mV=float(np.mean(error[valid])) if any(valid) else None,
        max_abs_error_mV=float(max(abs(error[valid]))) if any(valid) else None,
        time_rmse_mV=float(np.sqrt(np.sum((dt*(error[:-1]**2+error[1:]**2)/2)[intervals])/duration)) if duration else None,
        time_bias_mV=float(np.sum((dt*(error[:-1]+error[1:])/2)[intervals])/duration) if duration else None)


def check_values(computed, expected):
    for key,value in computed.items():
        if value is None: assert expected[key] is None
        else: assert abs(value-expected[key]) < 1e-7, (key,value,expected[key])


def kkt(matrix,target,weights,coef,columns):
    """Convex box optimum: free gradient zero; correct inward sign at bounds."""
    coef = np.asarray(coef); assert coef.shape==(3,)
    assert np.all(coef >= -1e-12) and np.all(coef <= .2+1e-12)
    assert all(coef[j]==0 for j in range(3) if j not in columns)
    residual = matrix@coef-target
    gradient = matrix.T@(weights*residual)/weights.sum()
    for j in columns:
        if coef[j] < 1e-9: assert gradient[j] >= -1e-8, (j,gradient)
        elif coef[j] > .2-1e-9: assert gradient[j] <= 1e-8, (j,gradient)
        else: assert abs(gradient[j]) < 1e-8, (j,gradient)
    return float(1000*np.sqrt(np.dot(weights,residual**2)/weights.sum()))


def verify(run, release_tests=None):
    previous = verify_previous()
    prior_receipt = json.loads((ROOT/'reports/p45b_gitt_replay_v1/verification.json').read_text())
    for name, expected in prior_receipt['artifacts'].items():
        path=ROOT/'reports/p45b_identifiability_v1/previous/README.md' if name=='README.md' else ROOT/name
        assert sha(path)==expected,name
    summary = json.loads((run/'summary.json').read_text()); lock = summary['source_lock']
    assert lock == json.loads((ROOT/'configs/ae_p45b_identifiability_v1.json').read_text())
    for name,expected in lock['frozen_files'].items(): assert sha(ROOT/name)==expected,name
    for name,expected in summary['implementation_sha256'].items(): assert sha(ROOT/name)==expected,name
    for name,expected in json.loads((run/'manifest.json').read_text()).items(): assert sha(run/name)==expected,name
    assert summary['new_measurement_families_opened']==0 and not summary['model_adopted']
    assert not summary['fresh_independent_assessment']
    assert summary['remaining_unopened_members']==48 and summary['remaining_unopened_families']==40
    assert lock['reserved_future_family']['family_id']=='MOLICEL_P45B_025degC_3C_Dch'
    source = read(ROOT/'reports/p45b_low_soc_v1/run_001/gitt_samples.csv')
    baseline = read(ROOT/'reports/p45b_gitt_replay_v1/run_001/primary.csv.gz')
    t,current,measured = [column(source,k) for k in ['time_s','source_current_A','voltage_V']]
    b = column(baseline,'predicted_voltage_V'); n=len(t); assert n==98426
    basis = np.load(run/'basis_primary.npz'); a=basis['matrix']; w=basis['weights']; target=measured-b
    assert a.shape==(n,3) and np.array_equal(basis['measured'],measured)
    assert np.max(abs(b-basis['voltage'])) <= 1e-12
    assert np.max(abs(basis['soc']-(1+np.r_[0,np.cumsum(np.diff(t)*current[:-1])/16200]))) < 1e-10
    assert np.max(abs(a[:,0]-current*np.maximum(0,(.2-basis['soc'])/.2))) < 1e-10
    groups = json.loads((run/'pair_allocation.json').read_text())
    segments = read(ROOT/'reports/p45b_low_soc_v1/run_001/gitt_segments.csv')
    pairs = read(ROOT/'reports/p45b_low_soc_v1/run_001/gitt_pairs.csv')
    expected_ids = [int(p['pair_index']) for p in pairs if basis['soc'][int(p['pulse_last_source_line'])-2] < .2]
    assert [g['pair_index'] for g in groups]==expected_ids==summary['selected_pair_ids']
    expected_w = np.zeros(n)
    for g in groups:
        for key in ['pulse_segment_id','rest_segment_id']:
            seg=segments[g[key]]; first,last=int(seg['start_index']),int(seg['end_index'])
            d=np.diff(t[first:last+1]); phase=np.r_[d/2,0]+np.r_[0,d/2]
            expected_w[first:last+1]=phase/phase.sum()/(2*len(groups))
    assert np.max(abs(w-expected_w)) < 1e-15
    assert abs(1000*np.sqrt(np.dot(w,target**2))-summary['baseline_objective_rmse_mV']) < 1e-8
    cvrows=read(run/'leave_pair_out.csv.gz'); independent={}
    for name,desc in summary['fits'].items():
        columns=[0] if name=='C1_R0' else [0,1,2]
        coef=np.array(desc['increments_Ohm']); objective=kkt(a,target,w,coef,columns)
        assert abs(objective-desc['objective_rmse_mV']) < 1e-8
        rows=read(run/(name+'.csv.gz')); y=column(rows,'predicted_voltage_V')
        for key in ['source_line','time_s','source_current_A','voltage_V']:
            assert np.array_equal(column(rows,key),column(source,key)),key
        assert np.max(abs(y-(b+a@coef))) < 1e-8
        closure=column(rows,'reference_V')+column(rows,'ohmic_V')+column(rows,'v1_V')+column(rows,'v2_V')-y
        assert np.max(abs(closure)) < 1e-10
        computed=independent_metrics(t,measured,y)
        check_values(computed,summary['runs'][name]['full_available_interval'])
        cv=column(cvrows,name+'_V'); assert np.array_equal(np.isfinite(cv),w>0)
        for g,fold in zip(groups,desc['leave_pair_out']['folds']):
            assert g['pair_index']==fold['pair_index']
            ids=np.arange(g['first_source_line']-2,g['last_source_line']-1)
            train=w.copy(); train[ids]=0
            score=kkt(a,target,train,fold['increments_Ohm'],columns)
            assert abs(score-fold['training_objective_rmse_mV']) < 1e-8
            assert np.max(abs(cv[ids]-(b[ids]+a[ids]@np.array(fold['increments_Ohm'])))) < 1e-10
        objective_cv=1000*np.sqrt(np.dot(w[w>0],(cv[w>0]-measured[w>0])**2)/w.sum())
        assert abs(objective_cv-desc['leave_pair_out']['objective_rmse_mV']) < 1e-8
        for suffix,predicted in [('_pairs.csv',y),('_leave_pair_out_pairs.csv',cv)]:
            for pair in read(run/(name+suffix)):
                loaded=int(pair['pulse_last_source_line'])-2
                first,last=int(pair['rest_first_source_line'])-2,int(pair['rest_last_source_line'])-2
                ids=np.arange(first,last+1); late=ids[t[ids]>=t[last]-60]
                if pair['complete_prediction']=='True':
                    recovery=1000*(np.median(predicted[late])-predicted[loaded])
                    assert abs(recovery-float(pair['predicted_recovery_mV'])) < 1e-8
        independent[name]=dict(metrics=computed,cv_objective_rmse_mV=float(objective_cv),constrained_optimum_KKT_verified=True)
    shifted=np.load(run/'basis_soc_minus_0p005.npz'); sr=read(run/'soc_sensitivity.csv.gz')
    assert np.max(abs(shifted['soc']-(basis['soc']-.005))) < 1e-10
    for name,desc in summary['initial_soc_sensitivity'].items():
        columns=[0] if name=='C1_R0' else [0,1,2]
        objective=kkt(shifted['matrix'],measured-shifted['voltage'],w,desc['refitted_parameters_Ohm'],columns)
        assert abs(objective-desc['refitted_objective_rmse_mV']) < 1e-8
        for tag,key in [('held','primary_parameters_Ohm'),('refit','refitted_parameters_Ohm')]:
            y=shifted['voltage']+shifted['matrix']@np.array(desc[key])
            assert np.max(abs(y-column(sr,name+'_'+tag+'_V'))) < 1e-10
    one=read(run/'used_1C_transfer.csv.gz'); original=read(ROOT/lock['used_1C_trace'])
    for key in ['source_line','time_s','source_current_A','voltage_V']:
        assert np.array_equal(column(one,key),column(original,key))
    for name,desc in summary['used_1C_transfer'].items():
        check_values(independent_metrics(column(one,'time_s'),column(one,'voltage_V'),column(one,name+'_V')),desc['full_available_interval'])
    assert np.nanmax(abs(column(one,'B0_V')-column(original,'predicted_voltage_V'))) < 1e-12
    tests={}
    paths=[ROOT/'reports/p45b_identifiability_v1/pre_fit_pytest.xml',
        ROOT/'reports/p45b_identifiability_v1/pre_fit_pytest_02.xml']
    if release_tests is not None: paths.append(release_tests)
    for path in paths:
        suite=ET.parse(path).getroot().find('testsuite')
        assert all(suite.get(k)=='0' for k in ['failures','errors','skipped'])
        tests[path.name]=int(suite.get('tests'))
    files=[p for p in (ROOT/'reports/p45b_identifiability_v1').rglob('*') if p.is_file() and p.name!='verification.json']
    files += [ROOT/n for n in ['scripts/ae_p45b_identifiability.py','scripts/verify_p45b_identifiability.py',
        'scripts/plot_p45b_identifiability.py','tests/test_p45b_identifiability_verifier.py',
        'tests/test_ae_p45b_identifiability.py','configs/ae_p45b_identifiability_v1.json','README.md']]
    files += [p for p in run.rglob('*') if p.is_file()]
    return dict(schema_version='voltforge.ae_p45b_identifiability_verification/1',tests=tests,
        verified_run=run.resolve().relative_to(ROOT).as_posix(),verified_run_manifest_sha256=sha(run/'manifest.json'),
        previous_artifacts_preserved=len(prior_receipt['artifacts']),
        protected_LG_artifacts=previous['protected_LG_artifacts'],unused_LG_cells=previous['unused_LG_cells'],
        unused_FreeTwinEV_records=previous['unused_FreeTwinEV_records'],remaining_unopened_P45B_members=48,
        independent_recomputations=independent,new_measurement_families_opened=0,model_adopted=False,
        artifacts={p.resolve().relative_to(ROOT).as_posix():sha(p) for p in sorted(set(files))})


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',type=Path,default=ROOT/'reports/p45b_identifiability_v1/run_002')
    parser.add_argument('--tests',type=Path)
    parser.add_argument('--out',type=Path,required=True); args=parser.parse_args()
    dest=args.out.resolve()
    if not any(dest.is_relative_to(ROOT/n) for n in ['reports','tmp','workspace']): raise SystemExit('Write under reports/, tmp/ or workspace/.')
    if dest.exists(): raise SystemExit('Use a new verification path.')
    result=verify(args.run,args.tests); dest.parent.mkdir(parents=True,exist_ok=True); write_json(dest,result)
    print('Verified constrained fits, whole-sequence bookkeeping and prior preservation chain.')


if __name__=='__main__': main()
