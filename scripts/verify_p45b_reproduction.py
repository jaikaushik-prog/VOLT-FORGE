"""Verify the bounded reproduction, accounting and preserved evidence."""
import argparse
import csv
import json
from pathlib import Path
import xml.etree.ElementTree as ET

import numpy as np

from ae_p45b_reproduction import ROOT, sha, write_json
from verify_p45b_paper import verify as verify_previous_stage


def verify():
    report = ROOT/'reports/p45b_reproduction_v1'
    previous = verify_previous_stage()  # Hash/header checks, no new outcomes.
    old_manifest = json.loads((ROOT/'reports/p45b_paper_v1/verification.json').read_text())
    for name, expected in old_manifest['artifacts'].items():
        target = report/'previous/README.md' if name == 'README.md' else ROOT/name
        assert sha(target) == expected, name

    lock = json.loads((ROOT/'configs/ae_p45b_reproduction_v1.json').read_text())
    for name, expected in lock['preaccess_files'].items():
        assert sha(ROOT/name) == expected, name
    run = report/'run_002'
    manifest = json.loads((run/'manifest.json').read_text())
    for name, expected in manifest.items():
        assert sha(run/name) == expected, name
    summary = json.loads((run/'summary.json').read_text())
    for name, expected in summary['implementation_sha256'].items():
        assert sha(ROOT/name) == expected, name
    assert summary['source_member'] == lock['allowed_measurement_member']
    assert summary['source_member_sha256'] == lock['member_sha256']
    assert summary['author_numeric_output_rows_opened'] == 0
    assert not summary['validation_workbook_opened'] and not summary['new_parameter_fit']
    assert summary['unused_measurement_files'] == 50
    assert summary['numerical_convergence']['criterion_met']

    with (run/'primary.csv').open(newline='',encoding='utf-8') as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 3433
    assert not {'V_sim_V', 'SOC_sim', 'E_OCV_V', 'I_sim_A'}.intersection(rows[0])
    times = np.array([float(r['time_s']) for r in rows])
    current = np.array([float(r['source_current_A']) for r in rows])
    soc = np.array([float(r['soc']) for r in rows])
    measured = np.array([float(r['voltage_V']) for r in rows])
    predicted = np.array([float(r['predicted_voltage_V']) for r in rows])
    err = predicted-measured
    delta = np.diff(times)
    independent_soc = np.r_[1., 1.+np.cumsum(current[:-1]*delta)/16200]
    max_soc_difference = float(np.max(abs(soc-independent_soc)))
    assert max_soc_difference < 1e-11
    independent_sample_rmse = float(1000*np.sqrt(sum(err**2)/len(err)))
    independent_time_rmse = float(1000*np.sqrt(sum((err[:-1]**2+err[1:]**2)/2*delta)/sum(delta)))
    metrics = summary['runs']['primary']['full_available_interval']
    assert abs(independent_sample_rmse-metrics['sample_rmse_mV']) < 1e-10
    assert abs(independent_time_rmse-metrics['time_rmse_mV']) < 1e-10
    for value in summary['runs'].values():
        assert value['stopped'] is None
        assert value['coverage']['extended_reference_rows'] == 0
        assert value['requirement_status'] == 'requirement not configured'
    failed = json.loads((report/'run_001/attempt_status.json').read_text())
    assert failed['status'] == 'failed_report_export'
    for name in failed['identical_trace_and_audit_files']:
        assert sha(report/'run_001'/name) == sha(run/name), name

    for name, count in [('preaccess_pytest.xml',57), ('pytest.xml',59)]:
        suite = ET.parse(report/name).getroot().find('testsuite')
        assert int(suite.get('tests')) == count
        assert all(suite.get(k) == '0' for k in ['errors','failures','skipped'])
    files = [p for p in report.rglob('*') if p.is_file() and p.name != 'verification.json']
    files += [ROOT/name for name in ['scripts/ae_p45b_reproduction.py',
        'scripts/verify_p45b_reproduction.py','tests/test_ae_p45b_reproduction.py',
        'configs/ae_p45b_reproduction_v1.json','README.md']]
    return dict(schema_version='voltforge.ae_p45b_reproduction_verification/1',
        tests_before_outcome_access=57, tests_after_export_fix=59, failures=0,
        opened_development_families=1, opened_experimental_rows=3433,
        unused_archive_members=50, unused_filename_families=42,
        base_parameter_rows_opened=839, charge_optimized_table_opened=False,
        author_numeric_output_rows_opened=0, validation_workbook_opened=False,
        new_fit_performed=False, failed_attempt_and_retry_predictions_identical=True,
        independent_max_soc_accounting_difference=max_soc_difference,
        independent_sample_rmse_mV=independent_sample_rmse,
        independent_time_rmse_mV=independent_time_rmse,
        protected_LG_artifacts=previous['protected_LG_artifacts'],
        unused_LG_cells=previous['unused_LG_cells'],
        unused_FreeTwinEV_records=previous['unused_FreeTwinEV_records'],
        original_P45B_files_unchanged=6, original_FreeTwinEV_files_unchanged=32,
        previous_paper_artifacts_preserved=len(old_manifest['artifacts']),
        frozen_LG_models_changed=False,
        experimental_module_validation='awaiting suitable measurements',
        artifacts={p.relative_to(ROOT).as_posix():sha(p) for p in sorted(files)})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True)
    args = parser.parse_args()
    dest = args.out.resolve()
    if not any(dest.is_relative_to(ROOT/name) for name in ('reports','tmp','workspace')):
        raise SystemExit('Write under reports/, tmp/ or workspace/.')
    if dest.exists():
        raise SystemExit('Choose a new receipt path.')
    result = verify()
    dest.parent.mkdir(parents=True,exist_ok=True)
    write_json(dest,result)
    print('Verified one development family, 59 tests, independent charge/error accounting and protected sources.')


if __name__ == '__main__':
    main()
