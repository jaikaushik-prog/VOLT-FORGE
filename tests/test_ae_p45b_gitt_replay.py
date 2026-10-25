"""Synthetic integration checks; no additional experimental outcomes are read."""
import csv
import gzip
import io
import json
import math
from pathlib import Path
import sys

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
import ae_p45b_gitt_replay as replay
import ae_p45b_low_soc as low
from ae_p45b_intake import PARAMETERS


def synthetic():
    stream = io.StringIO(); writer = csv.writer(stream); writer.writerow(PARAMETERS)
    for soc in (0, 1):
        writer.writerow([soc, 4.5*(soc-1), 25, 3.1+soc, 3+soc, .01, .005, 2000, .01, 10000, 20, 0])
    data = stream.getvalue().encode(); table = replay.Table25(data)
    times = list(range(132))
    source = [dict(source_line=n+2, time_s=float(t), source_current_A=-4.5 if t<10 else 0.,
        voltage_V=3.8 if t<10 else 3.9+.00001*(t-10), controlled_temperature_degC=25.) for n,t in enumerate(times)]
    annotated, _ = low.annotate(table, source)
    segments, pairs = low.segments(table, annotated)
    for a, r in zip(annotated, source): r['segment_id'] = a['segment_id']
    return data, table, source, segments, pairs


def test_primary_reuses_frozen_solver_exactly_without_rest_reset():
    _, table, source, segments, _ = synthetic()
    old = replay.simulate(table, source)
    new = replay.replay(table, source, segments, 'primary')
    for a, b in zip(old['rows'], new['rows']):
        for key in ['predicted_voltage_V', 'soc', 'hysteresis', 'v1_V', 'v2_V', 'residual_V']:
            assert a[key] == b[key]
        assert abs(b['closure_mV']) < 1e-10
    assert new['rows'][10]['v2_V'] < 0  # No reset at the start of rest.


def test_origin_adapter_agrees_with_independent_constant_rc_solution():
    _, table, source, segments, _ = synthetic()
    run = replay.replay(table, source, segments, 'initial_soc_minus_0p005')
    for row in run['rows']:
        t = row['time_s']; duration = min(t, 10); rest = max(t-10, 0)
        soc = .995 - 4.5*duration/16200
        v1 = -4.5*.005*(1-math.exp(-duration/10))*math.exp(-rest/10)
        v2 = -4.5*.01*(1-math.exp(-duration/100))*math.exp(-rest/100)
        expected = 3+soc+row['source_current_A']*.01+v1+v2
        assert row['soc'] == pytest.approx(soc, abs=1e-13)
        assert row['predicted_voltage_V'] == pytest.approx(expected, abs=1e-12)
    assert run['configuration']['initial_soc'] == .995


def test_unsupported_positive_origin_stops_without_clipping_or_erasure():
    _, table, source, segments, pairs = synthetic()
    run = replay.replay(table, source, segments, 'initial_soc_plus_0p005')
    assert 'outside reference' in run['stopped']['reason']
    assert len(run['rows']) == len(source)
    assert all(r['predicted_voltage_V'] is None and r['soc'] is None for r in run['rows'])
    summary, _, output = replay.summarize_gitt(run, segments, pairs)
    assert summary['full_available_interval']['samples'] == 0
    assert not output[0]['complete_prediction'] and output[0]['predicted_recovery_mV'] is None
    with pytest.raises(ValueError, match='does not permit'): replay.OriginTable(table, 0).query(2, 'nearest')


def test_gap_stops_without_restarting_and_keeps_measurements():
    _, table, source, segments, _ = synthetic()
    for row in source[50:]: row['time_s'] += 100
    run = replay.replay(table, source, segments, 'primary')
    assert run['stopped']['reason'] == 'acquisition_gap'
    assert all(r['predicted_voltage_V'] is None for r in run['rows'][50:])
    assert run['rows'][-1]['voltage_V'] == source[-1]['voltage_V']


def test_absolute_current_integral_handles_linear_sign_crossing():
    times = np.array([0., 2., 5.]); currents = np.array([-4., 2., 2.])
    assert replay.absolute_charge(times, currents, 'left') == pytest.approx([0, 8, 14])
    assert replay.absolute_charge(times, currents, 'linear') == pytest.approx([0, 10/3, 28/3])
    assert replay.absolute_charge(times, currents, 'linear', max_step_s=2) == pytest.approx([0, 2, 8])


def test_time_constant_bound_includes_interior_interpolation_extremum():
    values = np.array([[1., 3.], [3., 1.]])
    assert replay.maximum_tau(values, 0, 1) == 4  # Endpoints both give only 3.


def test_pair_recovery_uses_whole_sequence_and_finite_window():
    _, table, source, segments, pairs = synthetic()
    run = replay.replay(table, source, segments, 'primary')
    output = replay.pair_diagnostics(run['rows'], segments, pairs)[0]
    late = [r for r in run['rows'] if r['time_s'] >= 71]
    median = np.median([r['voltage_V'] for r in late])
    predicted = np.median([r['predicted_voltage_V'] for r in late])
    assert output['measured_recovery_mV'] == pytest.approx(1000*(median-3.8))
    assert output['predicted_recovery_mV'] == pytest.approx(1000*(predicted-run['rows'][9]['predicted_voltage_V']))
    assert output['measured_late_slope_mV_per_min'] == pytest.approx(.6)
    assert output['late_median_difference_mV'] == pytest.approx(1000*(predicted-median))


def test_rest_window_allocation_has_no_duplicate_boundaries():
    _, table, source, segments, pairs = synthetic()
    run = replay.replay(table, source, segments, 'primary')
    summary, per_segment, _ = replay.summarize_gitt(run, segments, pairs)
    assert [v['samples'] for v in summary['rest_windows'].values()] == [2, 9, 50, 61, 0]
    assert sum(v['samples'] for v in summary['rest_windows'].values()) == 122
    assert sum(v['samples'] for v in per_segment) == len(source)
    first_errors = np.array([r['residual_V'] for r in run['rows'][10:12]])
    assert summary['rest_windows']['0-1 s']['time_rmse_mV'] == pytest.approx(1000*np.sqrt(np.mean(first_errors**2)))


def test_conditional_initial_memory_fractions_match_analytic_bounds():
    _, table, source, segments, _ = synthetic()
    run = replay.replay(table, source, segments, 'primary')
    for row in run['rows']:
        t = row['time_s']
        assert row['initial_v1_memory_upper_fraction'] == pytest.approx(math.exp(-t/10))
        assert row['initial_v2_memory_upper_fraction'] == pytest.approx(math.exp(-t/100))
        assert row['initial_hysteresis_memory_upper_fraction'] == pytest.approx(math.exp(-20*4.5*min(t,10)/16200))


def test_compressed_predictions_are_deterministic_complete_and_no_overwrite(tmp_path):
    _, table, source, segments, _ = synthetic()
    rows = replay.replay(table, source, segments, 'primary')['rows']
    a, b = tmp_path/'a.csv.gz', tmp_path/'b.csv.gz'
    replay.write_predictions(a, rows); replay.write_predictions(b, rows)
    assert a.read_bytes() == b.read_bytes()
    decoded = list(csv.DictReader(io.StringIO(gzip.decompress(a.read_bytes()).decode())))
    assert len(decoded) == len(source) and float(decoded[-1]['time_s']) == 131
    with pytest.raises(FileExistsError): replay.write_predictions(a, rows)


def make_source_lock(root):
    data, _, source, segments, pairs = synthetic()
    (root/'configs').mkdir(); (root/replay.TABLE_NAME).write_bytes(data)
    low.write_csv(root/'samples.csv', source); low.write_csv(root/'segments.csv', segments); low.write_csv(root/'pairs.csv', pairs)
    lock = dict(saved_samples='samples.csv', saved_segments='segments.csv', saved_pairs='pairs.csv',
        frozen_files={n:replay.sha(root/n) for n in ['samples.csv', 'segments.csv', 'pairs.csv', replay.TABLE_NAME]})
    (root/'configs/ae_p45b_gitt_replay_v1.json').write_text(json.dumps(lock))
    return lock


def test_source_lock_reads_only_saved_evidence_and_detects_changes(tmp_path, monkeypatch):
    make_source_lock(tmp_path)
    (tmp_path/'PROTECTED.csv').write_bytes(b'\xffDO NOT DECODE')
    monkeypatch.setattr(replay, 'ROOT', tmp_path)
    _, source, segments, pairs, _ = replay.load_sources()
    assert len(source) == 132 and len(segments) == 2 and len(pairs) == 1
    (tmp_path/'samples.csv').write_text('changed')
    with pytest.raises(ValueError, match='Frozen source/procedure'): replay.load_sources()


def test_incomplete_segment_inventory_is_rejected(tmp_path, monkeypatch):
    lock = make_source_lock(tmp_path)
    segments = replay.read_csv(tmp_path/'segments.csv'); segments[1]['start_index'] = 11
    (tmp_path/'segments.csv').unlink(); low.write_csv(tmp_path/'segments.csv', segments)
    lock['frozen_files']['segments.csv'] = replay.sha(tmp_path/'segments.csv')
    (tmp_path/'configs/ae_p45b_gitt_replay_v1.json').write_text(json.dumps(lock))
    monkeypatch.setattr(replay, 'ROOT', tmp_path)
    with pytest.raises(ValueError, match='Incomplete segment'): replay.load_sources()


def test_full_cli_exports_five_declared_cases_and_stops_unsupported_origin(tmp_path, monkeypatch):
    make_source_lock(tmp_path); (tmp_path/'scripts').mkdir()
    for name in replay.IMPLEMENTATIONS: (tmp_path/name).write_text('synthetic provenance fixture')
    monkeypatch.setattr(replay, 'ROOT', tmp_path)
    out = tmp_path/'tmp/replay'
    monkeypatch.setattr(sys, 'argv', ['replay', '--out', str(out)])
    replay.main()
    summary = json.loads((out/'summary.json').read_text())
    assert len(summary['runs']) == 5 and summary['measurement_families_newly_opened'] == 0
    assert summary['runs']['initial_soc_plus_0p005']['coverage']['predicted_rows'] == 0
    assert summary['numerical_convergence']['criterion_met']
    assert summary['requirement_status'] == 'requirement not configured'
    for name, expected in json.loads((out/'manifest.json').read_text()).items():
        assert replay.sha(out/name) == expected
    assert (out/'selected_sequences.png').stat().st_size > 1000
    with pytest.raises(SystemExit, match='new output directory'): replay.main()
