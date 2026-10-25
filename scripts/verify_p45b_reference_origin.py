"""Independent bookkeeping for the no-fit reference/origin investigation."""
import argparse
import csv
import gzip
import json
from pathlib import Path
import xml.etree.ElementTree as ET

import numpy as np

from ae_p45b_reproduction import ROOT,Table25,sha,write_json
from ae_p45b_reference_origin import SCENARIOS,initial_state_policy


def read(path):
    opener=gzip.open if Path(path).suffix=='.gz' else open
    with opener(path,'rt',encoding='utf-8',newline='') as f:return list(csv.DictReader(f))


def col(rows,key):return np.array([float(r[key]) if r[key] not in ('',None) else np.nan for r in rows])


def independent_coordinate(t,i,origin,mode):
    out=[origin]
    for j in range(len(t)-1):
        effective=i[j] if mode=='left' else .5*(i[j]+i[j+1])
        out.append(out[-1]+effective*(t[j+1]-t[j])/(4.5*3600))
    return np.array(out)


def independent_window(rows,duration,end=None):
    end=float(rows[-1]['time_s']) if end is None else end
    selected=[r for r in rows if end-duration<=float(r['time_s'])<=end]
    t=col(selected,'time_s');v=col(selected,'voltage_V');ref=col(selected,'reference_V')
    result=dict(source_first_line=int(selected[0]['source_line']),source_last_line=int(selected[-1]['source_line']),samples=len(selected),
        measured_median_V=float(np.median(v)),slope_mV_per_min=float(np.polyfit(t-t[0],v,1)[0]*60000))
    if np.all(np.isfinite(ref)):result['reference_median_V']=float(np.median(ref))
    return result


def verify(run,tests=None):
    summary=json.loads((run/'summary.json').read_text());lock=summary['source_lock']
    assert lock==json.loads((ROOT/'configs/ae_p45b_reference_origin_v1.json').read_text())
    for name,expected in lock['frozen_files'].items():assert sha(ROOT/name)==expected,name
    for name,expected in summary['implementation_sha256'].items():assert sha(ROOT/name)==expected,name
    for name,expected in json.loads((run/'manifest.json').read_text()).items():assert sha(run/name)==expected,name
    assert summary['parameter_fits']==0 and not summary['models_adopted'] and not summary['fresh_independent_assessment']
    assert summary['new_measurement_families_opened']==0 and summary['remaining_unopened_members']==48 and summary['remaining_unopened_families']==40
    table=Table25((ROOT/lock['parameter_table']).read_bytes())
    records={k:read(ROOT/v) for k,v in lock['saved_records'].items()};source_pairs=read(ROOT/lock['saved_pairs'])
    largest_soc=0.;checked_windows=0;checked_samples=0
    for scenario,(origin,mode) in SCENARIOS.items():
        exported={}
        for record,source in records.items():
            rows=read(run/(scenario+'_'+record+'.csv.gz'));exported[record]=rows
            assert len(rows)==len(source)
            for k in ['source_line','time_s','source_current_A','voltage_V','controlled_temperature_degC']:assert np.array_equal(col(rows,k),col(source,k)),k
            t,i=col(source,'time_s'),col(source,'source_current_A')
            z=independent_coordinate(t,i,origin,mode);delta=float(np.max(abs(z-col(rows,'nominal_soc'))));largest_soc=max(largest_soc,delta);assert delta<1e-10
            expected=np.interp(z,table.soc,table.values[:,1]);outside=(z<table.soc[0])|(z>table.soc[-1])
            if any(outside):expected[np.flatnonzero(outside)[0]:]=np.nan
            actual=col(rows,'reference_V');assert np.array_equal(np.isfinite(expected),np.isfinite(actual))
            assert np.nanmax(abs(actual-expected))<1e-9
            error=1000*(actual-col(rows,'voltage_V'));assert np.nanmax(abs(error-col(rows,'reference_minus_measured_mV')))<1e-8
            valid=np.isfinite(error);d=np.diff(t);interval=valid[:-1]&valid[1:];duration=d[interval].sum()
            m=summary['scenarios'][scenario]['records'][record]['full_reference_difference']
            assert m['samples']==int(valid.sum()) and abs(m['duration_s']-duration)<1e-6
            assert abs(m['sample_rmse_mV']-np.sqrt(np.mean(error[valid]**2)))<1e-7
            assert abs(m['sample_bias_mV']-np.mean(error[valid]))<1e-7
            assert abs(m['time_rmse_mV']-np.sqrt(np.sum((d*(error[:-1]**2+error[1:]**2)/2)[interval])/duration))<1e-7
            checked_samples+=len(rows)
        pairs=json.loads((run/(scenario+'_rests.json')).read_text());assert len(pairs)==len(source_pairs)==32
        for pair,source_pair in zip(pairs,source_pairs):
            a,b=int(source_pair['rest_first_source_line'])-2,int(source_pair['rest_last_source_line'])-2
            rr=exported['gitt'][a:b+1]
            assert pair['rest_first_source_line']==a+2 and pair['rest_last_source_line']==b+2 and not pair['equilibrium_established']
            for duration in (60,300,600):
                actual=pair['windows'][str(duration)];expected=independent_window(rr,float(duration))
                for key,value in expected.items():assert abs(actual[key]-value)<1e-7,(scenario,pair['pair_index'],duration,key)
                assert not actual['equilibrium_established'];checked_windows+=1
            previous=independent_window(rr,300.,float(rr[-1]['time_s'])-300.)
            recent=pair['windows']['300']['measured_median_V']
            assert abs(pair['final_minus_preceding_300s_median_mV']-1000*(recent-previous['measured_median_V']))<1e-7
        context=summary['scenarios'][scenario]['endpoint_context']
        assert 'unverified' in context['cross_record_cell_and_preparation_equivalence']
        for channel in ('co30_loaded','gitt_finite_rest'):
            got=context[channel]
            if got['value_V'] is None:assert 'outside' in got['status'] or 'ambiguous' in got['status']
            else:
                if channel=='co30_loaded':
                    ra,rb=[exported['co30'][int(got[k])-2] for k in ('source_line_a','source_line_b')]
                    za,zb=float(ra['nominal_soc']),float(rb['nominal_soc']);va,vb=float(ra['voltage_V']),float(rb['voltage_V'])
                else:
                    ra,rb=[next(p for p in pairs if p['rest_last_source_line']==got[k]) for k in ('source_line_a','source_line_b')]
                    za,zb=ra['rest_endpoint_nominal_soc'],rb['rest_endpoint_nominal_soc'];va,vb=ra['windows']['60']['measured_median_V'],rb['windows']['60']['measured_median_V']
                query=context['nominal_soc'];assert za>=query>=zb
                assert abs(got['value_V']-(va+(vb-va)*(za-query)/(za-zb)))<1e-10
    examples=json.loads((run/'policy_examples.json').read_text())
    for example in examples.values():
        result=initial_state_policy(example['request'],summary['reference_support'])
        assert result==example['response'] and not result['evidence_verified'] and not result['reference_equilibrium_verified']
    receipt={}
    if tests:
        suite=ET.parse(tests).getroot().find('testsuite');assert all(suite.get(k)=='0' for k in ('errors','failures','skipped'))
        receipt=dict(path=str(tests),passed=int(suite.get('tests')),sha256=sha(tests))
    return dict(schema_version='voltforge.p45b_reference_origin_verification/1',checked_source_samples_across_scenarios=checked_samples,
        checked_rest_windows=checked_windows,maximum_independent_charge_coordinate_difference=largest_soc,
        source_channels_and_complete_records_preserved=True,new_measurement_families_opened=0,remaining_unopened_P45B_members=48,
        tests=receipt,previous_release_chain='checked separately by preservation-aware integration verifier',
        experimental_validation='not established',run=str(run.relative_to(ROOT)))


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run',type=Path,default=ROOT/'reports/p45b_reference_origin_v1/run_001')
    p.add_argument('--tests',type=Path);p.add_argument('--out',type=Path,required=True);args=p.parse_args()
    result=verify(args.run.resolve(),args.tests);args.out.parent.mkdir(parents=True,exist_ok=True);write_json(args.out,result);print(json.dumps(result,indent=2))


if __name__=='__main__':main()
