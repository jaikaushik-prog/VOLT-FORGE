"""Verify the bounded reference diagnosis and earlier immutable releases."""
import argparse
import csv
import json
from pathlib import Path
import xml.etree.ElementTree as ET

import numpy as np

from ae_p45b_reproduction import ROOT, sha, write_json
from verify_p45b_author_comparison import verify as verify_previous


def read_csv(path):
    with path.open(newline='', encoding='utf-8') as stream:
        return list(csv.DictReader(stream))


def verify():
    report = ROOT / 'reports/p45b_low_soc_v1'
    previous = verify_previous()
    old_manifest = json.loads((ROOT / 'reports/p45b_author_comparison_v1/verification.json').read_text())
    for name, expected in old_manifest['artifacts'].items():
        path = report / 'previous/README.md' if name == 'README.md' else ROOT / name
        assert sha(path) == expected, name
    lock = json.loads((ROOT / 'configs/ae_p45b_low_soc_v1.json').read_text())
    for name, expected in lock['preaccess_files'].items():
        assert sha(ROOT / name) == expected, name
    run = report / 'run_001'
    for name, expected in json.loads((run / 'manifest.json').read_text()).items():
        assert sha(run / name) == expected, name
    summary = json.loads((run / 'summary.json').read_text())
    assert summary['source_lock'] == lock
    for name, expected in summary['implementation_sha256'].items():
        assert sha(ROOT / name) == expected, name
    assert summary['remaining_unopened_members'] == 48
    assert not any(summary[k] for k in [
        'model_parameters_changed', 'initial_states_fitted',
        'late_rest_is_equilibrium_OCV', 'cross_record_same_cell_and_preparation_verified',
        'reference_comparisons_are_terminal_prediction_errors', 'validation_workbook_opened'])
    assert summary['requirement_status'] == 'requirement not configured'

    independent = {}
    for key, expected_count, expected_segments in [('co30', 2784, 2), ('gitt', 98426, 65)]:
        rows = read_csv(run / (key + '_samples.csv'))
        array = lambda field: np.array([float(r[field]) for r in rows])
        assert len(rows) == expected_count
        assert [int(r['source_line']) for r in rows] == list(range(2, expected_count + 2))
        t = array('time_s'); delta = np.diff(t); current = array('source_current_A')
        assert np.all(delta > 0) and all(r['gap_before'] == 'False' for r in rows)
        assert np.max(abs(current + array('current_discharge_positive_A'))) == 0
        linear = np.r_[1., 1. + np.cumsum(delta * (current[:-1] + current[1:]) / 2) / 16200]
        left = np.r_[1., 1. + np.cumsum(delta * current[:-1]) / 16200]
        assert np.max(abs(linear - array('nominal_soc_linear'))) < 1e-12
        assert np.max(abs(left - array('nominal_soc_left'))) < 1e-12
        recorded = summary['records'][key]
        assert abs(linear[-1] - recorded['final_soc_linear']) < 1e-12
        residual = 1000 * (array('reference_discharge_V') - array('voltage_V'))
        assert np.max(abs(residual - array('reference_minus_measured_mV'))) < 1e-10
        mask = current < -.05
        valid_intervals = mask[:-1] & mask[1:]
        duration = sum(delta[valid_intervals])
        metrics = dict(sample_rmse_mV=float(np.sqrt(np.mean(residual[mask] ** 2))),
            time_rmse_mV=float(np.sqrt(sum((delta * (residual[:-1] ** 2 + residual[1:] ** 2) / 2)[valid_intervals]) / duration)),
            sample_bias_mV=float(np.mean(residual[mask])), max_abs_mV=float(max(abs(residual[mask]))))
        for name, value in metrics.items():
            assert abs(value - recorded['reference_errors_by_phase']['discharge'][name]) < 1e-8
        segments = read_csv(run / (key + '_segments.csv'))
        assert len(segments) == expected_segments
        cursor = 0
        for segment in segments:
            start, end = int(segment['start_index']), int(segment['end_index'])
            assert start == cursor and end >= start
            assert int(segment['samples']) == end - start + 1
            assert all(r['segment_id'] == segment['segment_id'] for r in rows[start:end + 1])
            cursor = end + 1
        assert cursor == expected_count
        independent[key] = dict(samples=len(rows), final_soc_linear=float(linear[-1]),
            final_soc_left=float(left[-1]), integrated_discharge_Ah=float(4.5 * (1 - linear[-1])),
            reference_minus_loaded_voltage=metrics, segments_cover_every_sample=True)
        if key == 'gitt':
            pairs = read_csv(run / 'gitt_pairs.csv')
            assert len(pairs) == 32
            max_recovery_difference = 0.
            for pair in pairs:
                loaded = rows[int(pair['pulse_last_source_line']) - 2]
                first = rows[int(pair['rest_first_source_line']) - 2]
                rest = segments[int(pair['rest_segment_id'])]
                assert int(rest['segment_id']) == int(pair['pulse_segment_id']) + 1
                group = rows[int(rest['start_index']):int(rest['end_index']) + 1]
                end_time = float(group[-1]['time_s'])
                late = [float(r['voltage_V']) for r in group if float(r['time_s']) >= end_time - 60]
                median = float(np.median(late))
                recovery = 1000 * (median - float(loaded['voltage_V']))
                max_recovery_difference = max(max_recovery_difference, abs(recovery - float(pair['loaded_to_late_rest_recovery_mV'])))
                assert abs(median - float(pair['late_rest_median_V'])) < 1e-12
                assert abs(float(first['time_s']) - float(loaded['time_s']) - float(pair['transition_sample_separation_s'])) < 1e-10
                scale = abs(float(pair['pulse_endpoint_current_A'])) * (float(pair['table_r0_Ohm']) + float(pair['table_r1_plus_r2_Ohm'])) * 1000
                assert abs(scale - float(pair['table_steady_drop_scale_mV'])) < 1e-10
            assert max_recovery_difference < 1e-10
            independent[key].update(complete_pairs=32, max_recomputed_recovery_difference_mV=max_recovery_difference)

    interpretation = json.loads((report / 'INTERPRETATION.json').read_text())
    assert not interpretation['new_model_adopted']
    assert not interpretation['reference']['is_terminal_prediction_accuracy']
    assert not interpretation['gitt_recovery']['scale_is_full_transient_prediction']
    assert not interpretation['gitt_recovery']['physical_cause_uniquely_identified']
    for name, count in [('preaccess_pytest.xml', 12), ('pytest.xml', 86)]:
        suite = ET.parse(report / name).getroot().find('testsuite')
        assert int(suite.get('tests')) == count
        assert all(suite.get(k) == '0' for k in ['errors', 'failures', 'skipped'])
    files = [p for p in report.rglob('*') if p.is_file() and p.name != 'verification.json']
    files += [ROOT / n for n in ['scripts/ae_p45b_low_soc.py', 'scripts/verify_p45b_low_soc.py',
        'tests/test_ae_p45b_low_soc.py', 'configs/ae_p45b_low_soc_v1.json', 'README.md']]
    return dict(schema_version='voltforge.ae_p45b_low_soc_verification/1',
        new_tests_before_record_access=12, focused_tests=86, failures=0,
        experimental_families_newly_opened=2, experimental_rows_newly_opened=101210,
        remaining_unopened_members=48, remaining_unopened_filename_families=40,
        validation_workbook_opened=False, charge_optimized_table_opened=False,
        model_parameters_changed=False, initial_states_fitted=False, new_model_adopted=False,
        previous_author_comparison_artifacts_preserved=len(old_manifest['artifacts']),
        protected_LG_artifacts=previous['protected_LG_artifacts'], unused_LG_cells=previous['unused_LG_cells'],
        unused_FreeTwinEV_records=previous['unused_FreeTwinEV_records'],
        original_P45B_files_unchanged=6, original_FreeTwinEV_files_unchanged=32,
        independent_recomputations=independent,
        experimental_module_validation='awaiting suitable measurements',
        artifacts={p.relative_to(ROOT).as_posix(): sha(p) for p in sorted(files)})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    dest = parser.parse_args().out.resolve()
    if not any(dest.is_relative_to(ROOT / n) for n in ('reports', 'tmp', 'workspace')):
        raise SystemExit('Write under reports/, tmp/ or workspace/.')
    if dest.exists():
        raise SystemExit('Choose a new receipt path.')
    result = verify()
    dest.parent.mkdir(parents=True, exist_ok=True)
    write_json(dest, result)
    print('Verified 86 tests, full-sequence diagnostics and all protected releases.')


if __name__ == '__main__':
    main()
