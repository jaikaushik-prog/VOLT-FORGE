"""Integration tests: thermal runs, engineering screen and v1-project compatibility through the Project service."""
import math
import json
from pathlib import Path
import shutil

import numpy as np
import pandas as pd
import pytest

from voltforge.project import Project
from voltforge.project import schema as s

V1_DEMO = Path(__file__).resolve().parents[1] / 'reports/product_integration_v1/demo/project'
LIMITS = {'peak_branch_current_A', 'current_imbalance_pct', 'peak_cell_temperature_C'}
NOT_CONFIGURED = 'requirement not configured'


def change(target='connection', cid='rail_p_1', prop='resistance', value=.0005, unit='ohm', classification='assumed'):
    return dict(target=target, id=cid, property=prop, value=value, unit=unit,
        source='Declared software test assumption', classification=classification)


def edit(project, request, variant='A0'):
    return project.apply_edit(variant, request, project.inspect(variant)['revision_id'])


def set_limit(project, amps):
    return edit(project, change('engineering_requirements', 'module', 'peak_branch_current',
        {'limit': amps, 'documented_source': 'Test proposal'}, 'A', 'proposed_requirement'))


def run(p, variant='A0', **kw):
    return p.run(variant, expected_revision=p.inspect(variant)['revision_id'], plots=False, **kw)


def is_number(x):
    return isinstance(x, float) and math.isfinite(x)


@pytest.fixture
def project(tmp_path):
    p = Project.create_reference(tmp_path / 'project')
    edit(p, change('scenario', 'module', 'load_profile', [{'start_s': 0., 'end_s': 20., 'current_A': 14.55}], 'A,s'))
    return p


def test_new_project_is_v2_with_thermal(project):
    x = project.inspect()
    assert project._state()['schema_version'] == 'voltforge.project/2'
    assert x['design']['schema_version'] == 'voltforge.design/2'
    assert x['capabilities']['thermal'] is True
    capacities = x['thermal_parameters']['heat_capacity_J_per_K']
    assert len(capacities) == 4 and all(c > 0 for c in capacities)  # one lumped node per cell; heat capacity is positive
    assert {'thermal', 'engineering_requirements'} <= {e['target'] for e in x['editable_properties']}


def test_run_writes_thermal_and_screen(project):
    r = run(project)
    folder = project.path / 'runs' / r['run_id']
    assert r['execution_status'] == 'completed' and r['thermal_output'] == 'available'
    assert (folder / 'thermal.csv').is_file()
    thermal = r['summary']['thermal']
    assert thermal['status'] == 'completed'
    assert thermal['relative_ledger_residual'] < 1e-9  # first law: stored heat = generated - exchanged, to round-off
    assert thermal['peak_cell_temperature_C'] > 23.0  # Joule heat only warms cells that start at the 23 C ambient
    requirements = r['summary']['engineering']['requirements']
    assert set(requirements) == LIMITS and all(v['status'] == NOT_CONFIGURED for v in requirements.values())
    electrical, temperatures = (pd.read_csv(folder / name) for name in ['trajectory.csv', 'thermal.csv'])
    assert 'T1_C' not in electrical.columns and 'T1_C' in temperatures.columns  # thermal output is kept separate
    assert len(temperatures) == len(electrical)  # one temperature row per electrical sample


def test_series_includes_temperature(project):
    rid = run(project)['run_id']
    cell = project.series('A0', rid, 'cell_2', limit=3)
    assert cell['units']['temperature_C'] == 'degC' and cell['units']['heat_W'] == 'W' and len(cell['rows']) == 3
    assert all(is_number(row['temperature_C']) and is_number(row['heat_W']) for row in cell['rows'])
    assert cell['rows'][0]['temperature_C'] == 23.0  # initial condition is the declared 23 C surface temperature
    # Joule heat from a few amperes (mean 14.55/4 = 3.6 A) through a positive resistance is > 0; cells starting at ambient never cool below it.
    assert all(row['temperature_C'] >= 23.0 and row['heat_W'] > 0 for row in cell['rows'])
    module = project.series('A0', rid, 'module')
    assert module['rows'] and module['next_offset'] is None and all(row['ambient_C'] == 23.0 for row in module['rows'])
    rail = project.series('A0', rid, 'rail_p_1')
    assert rail['rows'] and not any('temperature' in key for row in rail['rows'] for key in row)
    assert 'temperature_C' not in rail['units']


def test_configured_limit_reports_violation(project):
    set_limit(project, 3.0)
    requirements = run(project)['summary']['engineering']['requirements']
    peak = requirements['peak_branch_current_A']
    # KCL: the four branch currents sum to 14.55 A, so the largest is at least 14.55/4 = 3.6375 A > 3.0 A.
    assert peak['status'] == 'simulated violation of configured limit'
    assert peak['value'] >= 14.55 / 4 - 1e-9 and peak['margin'] < 0
    assert peak['margin'] == pytest.approx(3.0 - peak['value'])  # margin = limit - value
    assert requirements['current_imbalance_pct']['status'] == requirements['peak_cell_temperature_C']['status'] == NOT_CONFIGURED
    set_limit(project, 10.0)  # a branch above 10 A would leave < 4.55 A for the other three: not a milliohm-rail imbalance
    peak = run(project)['summary']['engineering']['requirements']['peak_branch_current_A']
    assert peak['status'] == 'no sampled exceedance; insufficient evidence for a pass' and peak['margin'] > 0


def test_thermal_edit_invalidates_and_changes_temperature(project):
    c_old = project.inspect()['thermal_parameters']['heat_capacity_J_per_K'][0]
    r1 = run(project)
    edit(project, change('thermal', 'module', 'heat_capacity', [35.] * 4, 'J/K'))
    assert project.get_run('A0', r1['run_id'])['freshness'] == 'outdated' and project.inspect()['current_run_ids'] == []
    r2 = run(project)
    assert project.inspect()['current_run_ids'] == [r2['run_id']]
    rise = [r['summary']['thermal']['peak_cell_temperature_C'] - 23. for r in (r1, r2)]
    # Same heat input, smaller heat capacity: the rise is ~heat/C, so the ratio is at most the ideal c_old/35 (losses to
    # ambient only subtract, and more in the hotter run). With C/G ~ 35/0.15 = 235 s >> 20 s the losses stay below ~10 %.
    assert 0 < rise[0] < rise[1]
    assert .8 * c_old / 35. < rise[1] / rise[0] <= c_old / 35.
    trajectories = [pd.read_csv(project.path / 'runs' / r['run_id'] / 'trajectory.csv') for r in (r1, r2)]
    pd.testing.assert_frame_equal(trajectories[0], trajectories[1], check_exact=True)  # one-way coupling: electrics untouched


def test_compare_includes_thermal_metrics(project):
    a0 = run(project)
    project.create_variant('A0', 'A1', 'Rail study', project.inspect()['revision_id'])
    edit(project, change(value=.003), 'A1')
    pair = lambda second: [{'variant_id': 'A0', 'run_id': a0['run_id']}, {'variant_id': 'A1', 'run_id': second['run_id']}]
    comparison = project.compare(pair(run(project, 'A1')))
    first, second = comparison['ordered_results']
    for row in (first, second):
        assert is_number(row['peak_cell_temperature_C']) and is_number(row['current_imbalance_pct'])
        assert isinstance(row['engineering_requirements'], dict) and set(row['engineering_requirements']) == LIMITS
    delta = comparison['deltas_vs_first'][0]['peak_cell_temperature_C']
    assert delta == pytest.approx(second['peak_cell_temperature_C'] - first['peak_cell_temperature_C'])
    # rail_p_1 carries the current of cells 2-4; tripling it diverts current to cell 1 and puts more rail heat into cells 1-2.
    assert delta > 0 and second['current_imbalance_pct'] > first['current_imbalance_pct']
    edit(project, change('thermal', 'module', 'ambient_conductance', [.3] * 4, 'W/K'), 'A1')
    with pytest.raises(s.RequestError, match='thermal parameters'):
        project.compare(pair(run(project, 'A1')))


def test_v1_project_still_opens_and_runs(tmp_path):
    shutil.copytree(V1_DEMO, tmp_path / 'old')
    old = Project(tmp_path / 'old')
    x = old.inspect('A0')
    assert x['design']['schema_version'] == 'voltforge.design/1' and old._state()['schema_version'] == 'voltforge.project/1'
    assert x['capabilities']['thermal'] is False and x['thermal_parameters'] is None
    assert not {'thermal', 'engineering_requirements'} & {e['target'] for e in x['editable_properties']}
    assert x['runs'] and old.get_run('A0', x['runs'][0]['run_id'])['thermal_output'] == 'unavailable'
    r = old.run('A0', expected_revision=x['revision_id'], plots=False)
    assert r['execution_status'] == 'completed'
    assert r['summary']['thermal']['status'] == 'unavailable' and r['thermal_output'] == 'unavailable'
    assert not (old.path / 'runs' / r['run_id'] / 'thermal.csv').exists()
    assert old._state()['schema_version'] == 'voltforge.project/1'  # no implicit migration


def test_invalid_thermal_summary_is_never_published_as_available(project, monkeypatch):
    from voltforge.models import thermal_v1
    def invalid_summary(*args, **kwargs):
        raise ValueError('Injected thermal summary failure')
    monkeypatch.setattr(thermal_v1, 'summarize', invalid_summary)
    result = run(project)
    assert result['execution_status'] == 'completed'
    assert result['summary']['thermal']['status'] == 'failed'
    assert result['thermal_output'] == 'unavailable'
    assert not (project.path / 'runs' / result['run_id'] / 'thermal.csv').exists()
    assert not (project.path / 'runs' / result['run_id'] / 'thermal.csv.tmp').exists()
    rows = project.series('A0', result['run_id'], 'cell_1')['rows']
    assert rows and all('temperature_C' not in row for row in rows)
    assert result['summary']['engineering']['metrics']['peak_branch_current_A']['value'] > 0


def assert_electrical_survives_thermal_failure(project, result):
    folder = project.path / 'runs' / result['run_id']
    assert result['execution_status'] == 'completed'
    assert result['summary']['thermal']['status'] == 'failed'
    assert result['thermal_output'] == 'unavailable'
    assert result['summary']['maximum_branch_current_A'] > 0
    assert result['summary']['engineering']['metrics']['peak_branch_current_A']['value'] > 0
    assert not (folder / 'thermal.csv').exists()
    assert not (folder / 'thermal.csv.tmp').exists()
    rows = project.series('A0', result['run_id'], 'cell_1')['rows']
    assert rows and all('temperature_C' not in row for row in rows)


def test_extreme_positive_capacity_cannot_publish_nonfinite_temperature(project):
    edit(project, change('thermal', 'module', 'heat_capacity', [1e-300] * 4, 'J/K'))
    with np.errstate(over='ignore', invalid='ignore', divide='ignore'):
        result = run(project)
    assert_electrical_survives_thermal_failure(project, result)


def test_interrupted_thermal_csv_write_never_publishes_partial_file(project, monkeypatch):
    original = pd.DataFrame.to_csv
    def interrupted(self, target, *args, **kwargs):
        if Path(target).name == 'thermal.csv.tmp':
            Path(target).write_text('time_s,T1_C\n0,', encoding='utf-8')
            raise OSError('Injected interrupted thermal write')
        return original(self, target, *args, **kwargs)
    monkeypatch.setattr(pd.DataFrame, 'to_csv', interrupted)
    result = run(project)
    assert_electrical_survives_thermal_failure(project, result)
    assert result['summary']['thermal']['error']['type'] == 'OSError'


@pytest.mark.parametrize('defect', ['truncated', 'missing_column', 'nonfinite', 'misaligned'])
def test_invalid_thermal_frame_cannot_be_published(project, monkeypatch, defect):
    from voltforge.models import thermal_v1
    original = thermal_v1.simulate
    def broken(*args, **kwargs):
        frame = original(*args, **kwargs)
        if defect == 'truncated':
            return frame.iloc[:-1]
        if defect == 'missing_column':
            return frame.drop(columns=['T1_C'])
        frame.loc[1, 'T1_C' if defect == 'nonfinite' else 'time_s'] = float('nan') if defect == 'nonfinite' else 100.
        return frame
    monkeypatch.setattr(thermal_v1, 'simulate', broken)
    assert_electrical_survives_thermal_failure(project, run(project))


def test_unregistered_thermal_file_cannot_create_results_for_legacy_project(tmp_path):
    shutil.copytree(V1_DEMO, tmp_path / 'old')
    old = Project(tmp_path / 'old')
    rid = old.inspect()['runs'][0]['run_id']
    (old.path / 'runs' / rid / 'thermal.csv').write_text('time_s,T1_C\n0,999\n', encoding='utf-8')
    assert old.get_run('A0', rid)['thermal_output'] == 'unavailable'
    series = old.series('A0', rid, 'cell_1')
    assert series['rows'] and 'temperature_C' not in series['units']
    assert all('temperature_C' not in row for row in series['rows'])


def test_failed_thermal_export_cannot_certify_full_reproduction(project, monkeypatch, tmp_path):
    from voltforge.models import thermal_v1
    from voltforge.project.replay import replay
    def broken(*args, **kwargs):
        raise ValueError('Injected thermal failure')
    monkeypatch.setattr(thermal_v1, 'simulate', broken)
    result = run(project)
    assert_electrical_survives_thermal_failure(project, result)
    rid = result['run_id']
    # An unregistered file must not promote a failed calculation to available.
    (project.path / 'runs' / rid / 'thermal.csv').write_text('time_s,T1_C\n0,999\n', encoding='utf-8')
    assert project.get_run('A0', rid)['thermal_output'] == 'unavailable'
    assert 'temperature_C' not in project.series('A0', rid, 'cell_1')['units']
    out = tmp_path / 'export'
    project.export([dict(variant_id='A0', run_id=rid)], out)
    with pytest.raises(s.RequestError, match='full-run reproduction cannot be certified') as error:
        replay(out, rid)
    assert error.value.code == 'unsupported_request'


def test_replay_checks_inner_run_manifest_when_outer_manifest_omits_thermal(project, tmp_path):
    from voltforge.project.replay import replay
    rid = run(project)['run_id']
    out = tmp_path / 'export'
    project.export([dict(variant_id='A0', run_id=rid)], out)
    relative = f'runs/{rid}/thermal.csv'
    (out / relative).unlink()
    manifest = json.loads((out / 'export_manifest.json').read_text())
    del manifest['artifacts'][relative]
    (out / 'export_manifest.json').write_text(json.dumps(manifest))
    with pytest.raises(s.RequestError, match='integrity.*thermal.csv') as error:
        replay(out, rid)
    assert error.value.code == 'integrity_error'
