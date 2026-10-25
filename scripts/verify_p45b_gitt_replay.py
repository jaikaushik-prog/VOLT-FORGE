"""Independent replay bookkeeping checks plus the immutable evidence chain."""
import argparse
import csv
import gzip
import json
from pathlib import Path
import xml.etree.ElementTree as ET

import numpy as np

from ae_p45b_reproduction import ROOT, sha, write_json
from verify_p45b_low_soc import verify as verify_previous


def read_csv(path):
    opener = gzip.open if path.suffix == '.gz' else Path.open
    kwargs = dict(newline='', encoding='utf-8')
    with opener(path, 'rt' if path.suffix == '.gz' else 'r', **kwargs) as stream:
        return list(csv.DictReader(stream))


def verify():
    report = ROOT / 'reports/p45b_gitt_replay_v1'
    previous = verify_previous()
    old_manifest = json.loads((ROOT / 'reports/p45b_low_soc_v1/verification.json').read_text())
    for name, expected in old_manifest['artifacts'].items():
        path = report / 'previous/README.md' if name == 'README.md' else ROOT / name
        assert sha(path) == expected, name
    lock = json.loads((ROOT / 'configs/ae_p45b_gitt_replay_v1.json').read_text())
    for name, expected in lock['frozen_files'].items():
        assert sha(ROOT / name) == expected, name
    run = report / 'run_001'
    for name, expected in json.loads((run / 'manifest.json').read_text()).items():
        assert sha(run / name) == expected, name
    summary = json.loads((run / 'summary.json').read_text())
    assert summary['source_lock'] == lock
    for name, expected in summary['implementation_sha256'].items():
        assert sha(ROOT / name) == expected, name
    assert summary['measurement_families_newly_opened'] == 0
    assert summary['remaining_unopened_members'] == 48
    assert not any(summary[k] for k in ['fitted_parameters_changed', 'initial_states_fitted', 'fresh_independent_assessment'])
    assert summary['requirement_status'] == 'requirement not configured'
    source = read_csv(ROOT / lock['saved_samples'])
    assert len(source) == 98426
    t = np.array([float(r['time_s']) for r in source]); delta = np.diff(t)
    current = np.array([float(r['source_current_A']) for r in source])
    measured = np.array([float(r['voltage_V']) for r in source])
    assert np.all(delta > 0)
    assert all(float(r['controlled_temperature_degC']) == 25 for r in source)
    left_charge = np.r_[0., np.cumsum(delta*current[:-1])/16200]
    linear_charge = np.r_[0., np.cumsum(delta*(current[:-1]+current[1:])/2)/16200]
    independent = {}; primary = None
    for case, description in summary['runs'].items():
        rows = read_csv(run / (case+'.csv.gz'))
        assert len(rows) == len(source)
        array = lambda key: np.array([float(r[key]) if r[key] != '' else np.nan for r in rows])
        assert [r['source_line'] for r in rows] == [r['source_line'] for r in source]
        assert np.array_equal(array('time_s'), t)
        assert np.array_equal(array('source_current_A'), current)
        assert np.array_equal(array('voltage_V'), measured)
        predicted = array('predicted_voltage_V'); valid = np.isfinite(predicted)
        assert not np.any(np.diff(valid.astype(int)) > 0), 'Prediction restarted after stop'
        configuration = description['configuration']
        expected_soc = configuration['initial_soc'] + (linear_charge if configuration['current_mode'] == 'linear' else left_charge)
        assert np.max(abs(array('soc')[valid]-expected_soc[valid]), initial=0) < 1e-10
        error = (predicted-measured)*1000
        assert np.max(abs(error[valid]-array('residual_V')[valid]*1000), initial=0) < 1e-10
        closure = 1000*(array('reference_V')+array('ohmic_V')+array('v1_V')+array('v2_V')-predicted)
        assert np.max(abs(closure[valid]), initial=0) < 1e-9
        intervals = valid[:-1] & valid[1:]
        duration = float(sum(delta[intervals]))
        computed = dict(samples=int(sum(valid)), covered_duration_s=duration,
            sample_rmse_mV=float(np.sqrt(np.mean(error[valid]**2))) if any(valid) else None,
            sample_bias_mV=float(np.mean(error[valid])) if any(valid) else None,
            max_abs_error_mV=float(max(abs(error[valid]))) if any(valid) else None,
            time_rmse_mV=float(np.sqrt(sum((delta*(error[:-1]**2+error[1:]**2)/2)[intervals])/duration)) if duration else None,
            time_bias_mV=float(sum((delta*(error[:-1]+error[1:])/2)[intervals])/duration) if duration else None)
        for key, value in computed.items():
            expected = description['full_available_interval'][key]
            if value is None: assert expected is None
            else: assert abs(value-expected) < 1e-8
        per_segment = read_csv(run/(case+'_segments.csv'))
        assert len(per_segment) == 65 and sum(int(r['samples']) for r in per_segment) == sum(valid)
        pairs = read_csv(run/(case+'_pairs.csv'))
        assert len(pairs) == 32
        recovery_difference = 0.
        for pair in pairs:
            loaded_index = int(pair['pulse_last_source_line'])-2
            first, last = int(pair['rest_first_source_line'])-2, int(pair['rest_last_source_line'])-2
            window = np.arange(first, last+1)
            window = window[t[window] >= t[last]-60]
            measured_median = float(np.median(measured[window]))
            measured_recovery = 1000*(measured_median-measured[loaded_index])
            assert abs(measured_recovery-float(pair['measured_recovery_mV'])) < 1e-10
            if pair['complete_prediction'] == 'True':
                predicted_median = float(np.median(predicted[window]))
                recovery = 1000*(predicted_median-predicted[loaded_index])
                recovery_difference = max(recovery_difference, abs(recovery-float(pair['predicted_recovery_mV'])))
                assert abs(1000*(predicted_median-measured_median)-float(pair['late_median_difference_mV'])) < 1e-10
            else:
                assert pair['predicted_recovery_mV'] == ''
        assert recovery_difference < 1e-10
        independent[case] = dict(metrics=computed, source_alignment_exact=True,
            max_recomputed_pair_recovery_difference_mV=recovery_difference)
        if primary is None:
            primary = predicted
        else:
            common = np.isfinite(primary) & valid
            difference = 1000*(predicted[common]-primary[common])
            expected = summary['differences_from_primary'][case]
            assert sum(common) == expected['common_samples']
            if any(common):
                assert abs(max(abs(difference))-expected['max_abs_voltage_difference_mV']) < 1e-9
                assert abs(np.sqrt(np.mean(difference**2))-expected['rmse_voltage_difference_mV']) < 1e-9
    assert len(independent) == 5
    for name, count in [('pre_replay_pytest.xml', 12), ('pre_replay_pytest_02.xml', 13), ('pytest.xml', 99)]:
        suite = ET.parse(report/name).getroot().find('testsuite')
        assert int(suite.get('tests')) == count
        assert all(suite.get(k) == '0' for k in ['errors', 'failures', 'skipped'])
    files = [p for p in report.rglob('*') if p.is_file() and p.name != 'verification.json']
    files += [ROOT/n for n in ['scripts/ae_p45b_gitt_replay.py', 'scripts/verify_p45b_gitt_replay.py',
        'tests/test_ae_p45b_gitt_replay.py', 'configs/ae_p45b_gitt_replay_v1.json', 'README.md']]
    return dict(schema_version='voltforge.ae_p45b_gitt_replay_verification/1',
        pre_replay_tests=13, focused_tests=99, failures=0, scenario_count=5,
        new_measurement_families_opened=0, remaining_unopened_members=48, remaining_unopened_filename_families=40,
        model_parameters_changed=False, initial_states_fitted=False,
        previous_low_soc_artifacts_preserved=len(old_manifest['artifacts']),
        protected_LG_artifacts=previous['protected_LG_artifacts'], unused_LG_cells=previous['unused_LG_cells'],
        unused_FreeTwinEV_records=previous['unused_FreeTwinEV_records'],
        original_P45B_files_unchanged=6, original_FreeTwinEV_files_unchanged=32,
        validation_workbook_opened=False, charge_optimized_table_opened=False,
        independent_recomputations=independent,
        experimental_module_validation='awaiting suitable measurements',
        artifacts={p.relative_to(ROOT).as_posix():sha(p) for p in sorted(files)})


def main():
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--out', type=Path, required=True)
    dest = parser.parse_args().out.resolve()
    if not any(dest.is_relative_to(ROOT/n) for n in ('reports', 'tmp', 'workspace')):
        raise SystemExit('Write under reports/, tmp/ or workspace/.')
    if dest.exists(): raise SystemExit('Choose a new receipt path.')
    result = verify(); dest.parent.mkdir(parents=True, exist_ok=True); write_json(dest, result)
    print('Verified 99 tests, five complete scenario exports and all protected releases.')


if __name__ == '__main__': main()
