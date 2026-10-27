import copy
import json
from pathlib import Path
import subprocess
import sys

import numpy as np
import pandas as pd
import pytest

from voltforge.project import Project, dispatch
from voltforge.project import schema as s
from voltforge.project.service import file_hash, read, software
from voltforge.simulation import workflow as w


def change(target='connection', cid='rail_p_1', prop='resistance', value=.0005, unit='ohm'):
    return dict(target=target, id=cid, property=prop, value=value, unit=unit,
        source='Declared software test assumption', classification='assumed')


def edit(project, request, variant='A0'):
    return project.apply_edit(variant, request, project.inspect(variant)['revision_id'])


@pytest.fixture
def project(tmp_path):
    p = Project.create_reference(tmp_path / 'project')
    edit(p, change('scenario', 'module', 'load_profile', [{'start_s': 0., 'end_s': 2., 'current_A': 14.55}], 'A,s'))
    return p


def run(p, variant='A0', **kw):
    return p.run(variant, expected_revision=p.inspect(variant)['revision_id'], plots=False, **kw)


def test_explicit_ladder_and_original_model_identity(project):
    x = project.inspect()
    d = x['design']
    assert list(d['cells']) == ['cell_1', 'cell_2', 'cell_3', 'cell_4']
    assert [c['identity'] for c in d['cells'].values()] == s.CELLS
    assert len(d['connections']) == 6 and len(d['nodes']) == 8
    assert d['terminals'] == {'positive': 'p1', 'negative': 'n1', 'voltage_reference': 'n1'}
    assert d['connections']['rail_p_1']['node_a'] == 'p1'
    assert d['connections']['rail_p_1']['node_b'] == 'p2'
    assert all(v is None for v in d['requirements'].values())
    assert x['capabilities']['thermal'] is True
    base, manifest = project._inputs(project._state())
    for mutation in ['topology', 'terminal', 'rewire', 'identity', 'model']:
        bad = copy.deepcopy(d)
        if mutation == 'topology': bad['topology'] = '2s2p'
        if mutation == 'terminal': bad['terminals']['positive'] = 'p4'
        if mutation == 'rewire': bad['connections']['rail_p_1']['node_b'] = 'p3'
        if mutation == 'identity': bad['cells']['cell_1']['identity'] = 'P3'
        if mutation == 'model': bad['cells']['cell_1']['model']['sha256'] = 'fake'
        with pytest.raises(s.RequestError, match='supported|Unsupported|read-only'):
            s.validate_design(bad, base, manifest)


@pytest.mark.parametrize('edit_request', [
    change(value=-.001), change(value=float('nan')), change(value=True), change(unit='mOhm'),
    change(cid='rail_p_4'), change(prop='R0'), change('cell', 'cell_1', 'initial_soc', 1.1, 'fraction'),
    change('cell', 'cell_1', 'identity', 'P3', 'identity'),
    change('simulation', 'module', 'dt_s', 0, 's'),
    change('scenario', 'module', 'load_profile', [{'start_s': 1., 'end_s': 2., 'current_A': 14.55}], 'A,s'),
])
def test_invalid_edits_rejected_without_mutation(project, edit_request):
    original = file_hash(project.path / 'project.json')
    result = dispatch(project.path, dict(operation='validate_edit', arguments=dict(variant_id='A0', edit=edit_request,
        expected_revision=project.inspect()['revision_id'])))
    assert result['status'] == 'error'
    assert result['error']['code'] in ['invalid_request', 'unsupported_request']
    assert file_hash(project.path / 'project.json') == original


def test_variant_isolation_invalidation_reload_and_existing_solver_equivalence(project):
    a0 = run(project)
    a0_hashes = {p.name: file_hash(p) for p in (project.path / 'runs' / a0['run_id']).iterdir()}
    rid = project.inspect()['revision_id']
    a1 = project.create_variant('A0', 'A1', 'One changed rail', rid)
    assert a1['current_run_ids'] == []
    assert a1['runs'][0]['freshness'] == 'outdated'  # even identical physics cannot change run ownership
    preview = project.validate_edit('A1', change(), a1['revision_id'])
    assert preview['valid'] and preview['physics_changed']
    edit(project, change(), 'A1')
    assert project.inspect('A1')['runs'][0]['freshness'] == 'outdated'
    r1 = run(project, 'A1')
    assert r1['freshness'] == 'current'
    assert project.get_run('A0', a0['run_id'])['freshness'] == 'current'
    with pytest.raises(s.RequestError, match='not associated'):
        project.get_run('A0', r1['run_id'])
    selections = [{'variant_id': 'A0', 'run_id': a0['run_id']}, {'variant_id': 'A1', 'run_id': r1['run_id']}]
    comparison = Project(project.path).compare(selections)
    assert comparison['conditions'] == 'identical operating conditions'
    assert len(comparison['ordered_results']) == 2
    assert all(x['requirement'] == 'requirement not configured' for x in comparison['ordered_results'])
    assert comparison['ordered_results'][0]['maximum_branch_current_A'] != comparison['ordered_results'][1]['maximum_branch_current_A']
    saved = pd.read_csv(project.path / 'runs' / r1['run_id'] / 'trajectory.csv')
    case = read(project.path / 'runs' / r1['run_id'] / 'configuration.json')
    direct = w.execute_case(case, None).frame  # sealed rested reference requires no loaded curve
    np.testing.assert_allclose(saved.to_numpy(), direct.to_numpy(), atol=1e-13, rtol=1e-13)
    assert abs(saved.kcl_residual_A).max() < 1e-12
    assert {p.name: file_hash(p) for p in (project.path / 'runs' / a0['run_id']).iterdir()} == a0_hashes
    edit(project, change(value=.0007), 'A1')
    historical = project.compare(selections)
    assert historical['historical_results'] is True
    assert historical['ordered_results'][1]['freshness'] == 'outdated'


def test_display_does_not_change_revision_or_invalidate(project):
    result = run(project)
    before = project.inspect()
    changed = project.update_display(dict(positions={'cell_1': [100, 25, 0]}, camera={'zoom': 2}, selection=['cell_1']))
    after = Project(project.path).inspect()
    assert changed['physics_changed'] is False and changed['invalidated_run_ids'] == []
    assert after['revision_id'] == before['revision_id']
    assert after['current_runs_by_scenario'] == {'nominal': [result['run_id']]}
    assert after['runs'][0]['snapshot_id'] == result['snapshot_id']


def test_conflicting_edits_and_active_writer_are_rejected(project):
    old = project.inspect()['revision_id']
    edit(project, change())
    with pytest.raises(s.RequestError, match='reload'):
        project.apply_edit('A0', change(value=.0006), old)
    with pytest.raises(s.RequestError, match='expected_revision'):
        project.run('A0', expected_revision=old, plots=False)
    with project._writer():
        with pytest.raises(s.RequestError, match='writer'):
            project.update_display(dict(positions={}, camera={}, selection=[]))


def test_results_and_assets_cannot_be_silently_tampered(project):
    result = run(project)
    summary = project.path / 'runs' / result['run_id'] / 'summary.json'
    summary.write_text('{}', encoding='utf-8')
    with pytest.raises(s.RequestError, match='integrity'):
        project.get_run('A0', result['run_id'])
    asset = project.path / 'assets/base_case.json'
    asset.write_text('{}', encoding='utf-8')
    with pytest.raises(s.RequestError, match='integrity'):
        project.inspect()


def test_failing_domain_run_preserves_partial_trajectory_and_cannot_compare(project):
    normal = run(project)
    edit(project, change('scenario', 'module', 'load_profile', [{'start_s': 0., 'end_s': 2., 'current_A': 100000.}], 'A,s'))
    failed = run(project)
    assert failed['execution_status'] == 'failed'
    assert failed['error']['reason'].startswith('Step would leave')
    assert failed['summary']['decision'] == 'insufficient evidence'
    assert project.inspect()['current_run_ids'] == []
    rows = project.series('A0', failed['run_id'])
    assert 0 < rows['total_samples'] < 9 and rows['rows'][0]['time_s'] == 0
    assert rows['rows'][-1]['time_s'] < 2
    assert rows['rows'][-1]['time_s'] == failed['error']['last_valid_time_s']
    with pytest.raises(s.RequestError, match='incomplete'):
        project.compare([{'variant_id': 'A0', 'run_id': x['run_id']} for x in [normal, failed]])


def test_backend_exception_is_a_saved_failed_run(project, monkeypatch):
    def broken(*args): raise RuntimeError('synthetic numerical failure')
    monkeypatch.setattr(w, 'execute_case', broken)
    result = run(project)
    assert result['execution_status'] == 'failed'
    assert result['error']['message'] == 'synthetic numerical failure'
    assert project.series('A0', result['run_id'])['rows'] == []


def test_comparison_rejects_changed_service_and_requirements_need_source(project, tmp_path):
    a0 = run(project)
    project.create_variant('A0', 'A1', 'Lower service', project.inspect()['revision_id'])
    edit(project, change('scenario', 'module', 'load_profile', [{'start_s': 0., 'end_s': 2., 'current_A': 12.}], 'A,s'), 'A1')
    a1 = run(project, 'A1')
    selections = [{'variant_id': 'A0', 'run_id': a0['run_id']}, {'variant_id': 'A1', 'run_id': a1['run_id']}]
    with pytest.raises(s.RequestError, match='load'):
        project.compare(selections)
    with pytest.raises(s.RequestError, match='load'):
        project.export(selections, tmp_path / 'bad_export')
    assert not (tmp_path / 'bad_export').exists()
    edit(project, change('requirements', 'module', 'voltage_requirement', dict(minimum_terminal_voltage_V=3.5,
        maximum_contiguous_excursion_s=0., documented_source=None), 'V,s'))
    assert run(project)['summary']['voltage_requirement']['status'] == 'requirement not configured'


def test_seven_declared_sensitivities_remain_separate_from_nominal(project):
    nominal = run(project)
    before = project.inspect()['revision_id']
    result = project.run_sensitivities('A0', before)
    assert len(result['runs']) == 7
    assert 'not confidence' in result['classification']
    assert all(x['summary']['run_type'] == 'sensitivity scenario' for x in result['runs'])
    assert all(x['summary']['experimental_validation'] == 'awaiting suitable measurements' for x in result['runs'])
    state = project.inspect()
    assert state['revision_id'] == before
    assert state['current_runs_by_scenario']['nominal'] == [nominal['run_id']]
    assert len(state['current_runs_by_scenario']) == 8


def test_series_mapping_and_no_thermal_output(project):
    r = run(project)
    cell = project.series('A0', r['run_id'], 'cell_1', limit=2)
    assert cell['units']['current_A'] == 'A' and len(cell['rows']) == 2 and cell['next_offset'] == 2
    rail = project.series('A0', r['run_id'], 'rail_p_1')
    for row in rail['rows']:
        assert row['loss_W'] == pytest.approx(row['current_A']**2*.001)
    with pytest.raises(s.RequestError, match='unavailable'):
        project.series('A0', r['run_id'], 'temperature')
    response = dispatch(project.path, {'operation': 'run_thermal', 'arguments': {}})
    assert response['error']['code'] == 'unsupported_request'


def test_export_replays_in_clean_process_without_repo_or_raw_data(project, tmp_path):
    r = run(project)
    out = tmp_path / 'export'
    report = project.export([{'variant_id': 'A0', 'run_id': r['run_id']}], out)
    assert report['experimental_validation'] == 'awaiting suitable measurements'
    assert not list(out.rglob('*.zip'))
    before = {p.relative_to(out).as_posix(): file_hash(p) for p in out.rglob('*') if p.is_file()}
    process = subprocess.run([sys.executable, '-B', str(out / 'replay.py'), r['run_id']], cwd=tmp_path,
        capture_output=True, text=True)
    assert process.returncode == 0, process.stderr
    assert json.loads(process.stdout)['reproduced'] is True
    assert {p.relative_to(out).as_posix(): file_hash(p) for p in out.rglob('*') if p.is_file()} == before
    with pytest.raises(s.RequestError, match='immutable'):
        project.export([{'variant_id': 'A0', 'run_id': r['run_id']}], out)
    (out / 'runs' / r['run_id'] / 'trajectory.csv').write_text('tampered', encoding='utf-8')
    process = subprocess.run([sys.executable, '-B', str(out / 'replay.py'), r['run_id']], cwd=tmp_path,
        capture_output=True, text=True)
    assert process.returncode != 0 and 'integrity' in process.stderr


def test_existing_synthetic_measurement_importer_is_reused(project, tmp_path, monkeypatch):
    monkeypatch.syspath_prepend('scripts')
    from make_module_fixture import make
    r = run(project)
    fixture = tmp_path / 'synthetic'
    make(project.path / 'runs' / r['run_id'], fixture)
    originals = {p.name: file_hash(p) for p in fixture.iterdir()}
    result = project.compare_measurements('A0', r['run_id'], fixture)
    assert result['result']['data_kind'] == 'synthetic_fixture'
    assert result['result']['comparisons']['terminal_V']['bias'] == pytest.approx(-.01, abs=1e-12)
    assert result['result']['experimental_validation'] == 'awaiting suitable measurements'
    for name, h in originals.items():
        assert file_hash(project.path / 'measurements' / result['measurement_id'] / 'ingestion/original' / name) == h


def test_json_cli_and_unknown_schema(tmp_path):
    path = tmp_path / 'project'
    process = subprocess.run([sys.executable, '-m', 'voltforge.project', '--project', str(path)],
        input=json.dumps({'operation': 'load_reference', 'arguments': {}}), capture_output=True, text=True)
    assert process.returncode == 0, process.stderr
    assert json.loads(process.stdout)['result']['variant_id'] == 'A0'
    state = read(path / 'project.json')
    state['schema_version'] = 'voltforge.project/999'
    (path / 'project.json').write_text(json.dumps(state))
    result = dispatch(path, {'operation': 'inspect', 'arguments': {}})
    assert result['error']['code'] == 'unsupported_request'


def test_software_version_change_marks_results_outdated(project, monkeypatch):
    from voltforge.project import service
    result = run(project)
    changed = software()
    changed['id'] = 'different-software-version'
    monkeypatch.setattr(service, 'software', lambda: changed)
    view = project.get_run('A0', result['run_id'])
    assert view['freshness'] == 'outdated' and 'software/runtime changed' in view['outdated_reasons']
    assert project.inspect()['current_run_ids'] == []


def test_unsupported_initial_sensitivity_has_no_fabricated_samples_and_replays(project, tmp_path):
    edit(project, change('cell', 'cell_1', 'initial_soc', .999, 'fraction'))
    result = run(project, scenario_id='soc_plus_2pp')
    assert result['execution_status'] == 'failed'
    assert project.series('A0', result['run_id'])['total_samples'] == 0
    out = tmp_path / 'failed_export'
    project.export([{'variant_id': 'A0', 'run_id': result['run_id']}], out)
    process = subprocess.run([sys.executable, '-B', str(out / 'replay.py'), result['run_id']], cwd=tmp_path,
        capture_output=True, text=True)
    assert process.returncode == 0, process.stderr
    assert json.loads(process.stdout)['samples'] == 0
