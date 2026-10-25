"""Verify same-record author diagnostics and earlier immutable releases."""
import argparse
import csv
import json
from pathlib import Path
import xml.etree.ElementTree as ET

import numpy as np

from ae_p45b_reproduction import ROOT, sha, write_json
from verify_p45b_reproduction import verify as verify_previous


def verify():
    report=ROOT/'reports/p45b_author_comparison_v1'
    previous=verify_previous()
    previous_manifest=json.loads((ROOT/'reports/p45b_reproduction_v1/verification.json').read_text())
    for name,expected in previous_manifest['artifacts'].items():
        path=report/'previous/README.md' if name=='README.md' else ROOT/name
        assert sha(path)==expected,name
    lock=json.loads((ROOT/'configs/ae_p45b_author_comparison_v1.json').read_text())
    for name,expected in lock['preaccess_files'].items():assert sha(ROOT/name)==expected,name
    run=report/'run_001'
    manifest=json.loads((run/'manifest.json').read_text())
    for name,expected in manifest.items():assert sha(run/name)==expected,name
    summary=json.loads((run/'summary.json').read_text())
    for name,expected in summary['implementation_sha256'].items():assert sha(ROOT/name)==expected,name
    assert summary['source_lock']==lock
    assert summary['rows']==3433 and all(v==0 for v in summary['author_missing_counts'].values())
    assert summary['unused_archive_members']==50 and not summary['validation_workbook_opened']
    assert not summary['parameters_or_initial_states_changed']
    assert summary['requirement_status']=='requirement not configured'
    with (run/'comparison.csv').open(newline='',encoding='utf-8') as stream:rows=list(csv.DictReader(stream))
    array=lambda key:np.array([float(r[key]) for r in rows])
    time=array('time_s');delta=np.diff(time)
    measured=array('voltage_V');ours=array('ours_predicted_voltage_V');authors=array('author_V_sim_V')
    independent={}
    for name,residual in [('ours_minus_measured_mV',1000*(ours-measured)),
        ('author_minus_measured_mV',1000*(authors-measured)),('ours_minus_author_mV',1000*(ours-authors))]:
        computed=dict(sample_rmse=float(np.sqrt(sum(residual**2)/len(residual))),
            time_rmse=float(np.sqrt(sum(delta*(residual[:-1]**2+residual[1:]**2)/2)/sum(delta))),
            sample_bias=float(sum(residual)/len(residual)),max_abs=float(max(abs(residual))))
        for key,value in computed.items():
            assert abs(value-summary['voltage_comparisons'][name]['all_available'][key])<1e-9
        independent[name]=computed
    closure=1000*(ours-authors)-(array('reference_difference_mV')+array('ohmic_difference_mV')+array('polarization_difference_mV'))
    assert max(abs(closure))<1e-9
    current=array('source_current_A');author_soc=array('author_SOC_sim')
    linear_soc=np.r_[author_soc[0],author_soc[0]+np.cumsum((current[:-1]+current[1:])/2*delta)/16200]
    max_linear_soc_difference=float(max(abs(author_soc-linear_soc)))
    assert max_linear_soc_difference<1e-8
    power_error=array('author_Q_sim_W')-array('author_I_sim_A')*authors
    power_rmse=float(np.sqrt(np.mean(power_error**2)))
    assert abs(power_rmse-summary['state_diagnostics']['author_power_minus_current_times_voltage']['sample_rmse'])<1e-10
    interpretation=json.loads((report/'INTERPRETATION.json').read_text())
    assert interpretation['Q_sim_W']['interpretation_status'].startswith('unresolved')
    assert not interpretation['Q_sim_W']['may_use_as_delivered_power']
    assert not interpretation['Q_sim_W']['may_use_as_heat_generation']
    for name,count in [('preaccess_pytest.xml',15),('pytest.xml',74)]:
        suite=ET.parse(report/name).getroot().find('testsuite')
        assert int(suite.get('tests'))==count
        assert all(suite.get(k)=='0' for k in ['errors','failures','skipped'])
    files=[p for p in report.rglob('*') if p.is_file() and p.name!='verification.json']
    files+=[ROOT/n for n in ['scripts/ae_p45b_author_comparison.py','scripts/verify_p45b_author_comparison.py',
        'tests/test_ae_p45b_author_comparison.py','configs/ae_p45b_author_comparison_v1.json','README.md']]
    return dict(schema_version='voltforge.ae_p45b_author_comparison_verification/1',
        new_tests_before_author_access=15,focused_tests=74,failures=0,
        experimental_families_newly_opened=0,author_output_rows_newly_interpreted=3433,
        author_columns_per_row=6,unused_archive_members=50,unused_filename_families=42,
        validation_workbook_opened=False,charge_optimized_table_opened=False,
        fitted_parameters_changed=False,initial_states_changed=False,
        previous_reproduction_artifacts_preserved=len(previous_manifest['artifacts']),
        protected_LG_artifacts=previous['protected_LG_artifacts'],unused_LG_cells=previous['unused_LG_cells'],
        unused_FreeTwinEV_records=previous['unused_FreeTwinEV_records'],
        original_P45B_files_unchanged=6,original_FreeTwinEV_files_unchanged=32,
        independent_voltage_metrics=independent,independent_max_voltage_decomposition_closure_mV=float(max(abs(closure))),
        independent_max_author_soc_minus_measured_linear_current_integral=max_linear_soc_difference,
        Q_sim_W_definition_status='unresolved; not used for electrical power or heat',
        independent_Q_sim_minus_I_sim_times_V_sim_rmse_W=power_rmse,
        experimental_module_validation='awaiting suitable measurements',
        artifacts={p.relative_to(ROOT).as_posix():sha(p) for p in sorted(files)})


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args();dest=args.out.resolve()
    if not any(dest.is_relative_to(ROOT/n) for n in ('reports','tmp','workspace')):raise SystemExit('Write under reports/, tmp/ or workspace/.')
    if dest.exists():raise SystemExit('Choose a new receipt path.')
    result=verify();dest.parent.mkdir(parents=True,exist_ok=True);write_json(dest,result)
    print('Verified same-record comparison, 74 tests, independent diagnostics and all protected releases.')


if __name__=='__main__':main()
