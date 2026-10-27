import pytest

from voltforge.project import Project
from voltforge.project import investigate as inv
from voltforge.project import schema as s

VIOLATION = 'simulated violation of configured limit'
PLAN = dict(rail_segments=['rail_p_1'], added_resistance_ohm=[0.002], load_current_A=[], ambient_C=[], max_cases=5)


def edit(p, target, ident, prop, value, unit, cls='assumed'):
    return p.apply_edit('A0', dict(target=target, id=ident, property=prop, value=value, unit=unit,
        source='Declared investigation test assumption', classification=cls), p.inspect()['revision_id'])


def search(p, **changes):
    return inv.run(p, 'A0', p.inspect()['revision_id'], {**PLAN, **changes})


@pytest.fixture
def project(tmp_path):
    p = Project.create_reference(tmp_path / 'project')
    edit(p, 'scenario', 'module', 'load_profile', [{'start_s': 0., 'end_s': 20., 'current_A': 14.55}], 'A,s')
    return p


def test_grid_count_and_order(project):
    design = project.inspect()['design']
    plan = dict(rail_segments=['rail_p_1', 'rail_n_2'], added_resistance_ohm=[0.001, 0.002], load_current_A=[12.0, 14.55], ambient_C=[25.0], max_cases=50)
    cases = inv.generate_cases(inv.validate_plan(plan, design), design)
    assert len(cases) == 2 * 1 * (1 + 2 * 2)
    assert [c['case_id'] for c in cases] == [f'case_{n:04d}' for n in range(1, 11)]
    expected = [(12.0, None, 0.0), (12.0, 'rail_p_1', 0.001), (12.0, 'rail_p_1', 0.002), (12.0, 'rail_n_2', 0.001), (12.0, 'rail_n_2', 0.002),
                (14.55, None, 0.0), (14.55, 'rail_p_1', 0.001), (14.55, 'rail_p_1', 0.002), (14.55, 'rail_n_2', 0.001), (14.55, 'rail_n_2', 0.002)]
    assert [(c['load_current_A'], c['rail_segment'], c['added_resistance_ohm']) for c in cases] == expected
    assert {c['ambient_C'] for c in cases} == {25.0}
    assert sorted(e['property'] for e in cases[0]['edits']) == ['load_profile', 'temperature']  # baseline: no degradation edit
    edits = {e['property']: e for e in cases[1]['edits']}  # case_0002 = rail_p_1 + 0.001 at 12 A, 25 degC
    assert set(edits) == {'resistance', 'load_profile', 'temperature'}
    assert (edits['resistance']['target'], edits['resistance']['id'], edits['resistance']['unit']) == ('connection', 'rail_p_1', 'ohm')
    assert edits['resistance']['value'] == pytest.approx(design['connections']['rail_p_1']['resistance']['value'] + 0.001, abs=1e-15)
    assert edits['load_profile']['value'] == [{'start_s': 0.0, 'end_s': 20.0, 'current_A': 12.0}]
    assert edits['temperature']['value']['assumed_ambient_C'] == 25.0 and edits['temperature']['value']['assumed_surface_C'] == [25.0] * 4
    assert all(e['source'] == 'Failure investigation case case_0002' and e['classification'] == 'assumed' for e in edits.values())


def test_plan_validation(project):
    design = project.inspect()['design']
    assert inv.validate_plan(PLAN, design)['max_cases'] == 5  # the unmodified plan is accepted, so each rejection below is caused by its change
    rejected = [{'surprise': 1}, {'rail_segments': ['rail_p_9']}, {'rail_segments': ['rail_p_1', 'rail_p_1']},
                {'added_resistance_ohm': [0]}, {'added_resistance_ohm': [-0.001]}, {'load_current_A': [-1.0]},
                {'ambient_C': [200.0]}, {'max_cases': 0}, {'max_cases': 201}]
    for change in rejected:
        with pytest.raises(s.RequestError):
            inv.validate_plan({**PLAN, **change}, design)


def test_known_violation_found_and_ranked(project):
    edit(project, 'engineering_requirements', 'module', 'peak_branch_current', {'limit': 3.9, 'documented_source': 'test'}, 'A', 'proposed_requirement')
    rec = search(project, rail_segments=['rail_p_1', 'rail_n_1'], added_resistance_ohm=[0.003], max_cases=10)
    assert rec['coverage'] == dict(requested=3, evaluated=3, skipped_by_budget=0, electrical_stopped=0, errors=0, thermal_failures=0)
    ranked = rec['rankings']['by_requirement']['peak_branch_current_A']
    by_id = {c['case_id']: c for c in rec['cases']}
    margins = [x['margin'] for x in ranked['cases']]
    assert len(margins) == 3 and margins == sorted(margins)
    assert [x['case_id'] for x in ranked['cases']] == sorted(by_id, key=lambda i: (by_id[i]['requirements']['peak_branch_current_A']['margin'], i))
    for row in ranked['cases']:
        peak = by_id[row['case_id']]['metrics']['peak_branch_current_A']
        assert row['margin'] == pytest.approx(3.9 - peak, abs=1e-12)  # margin = configured limit - sampled peak
        assert (row['status'] == VIOLATION) == (peak > 3.9)  # a violation exactly when the sampled peak exceeds the limit
    assert any(x['status'] == VIOLATION for x in ranked['cases'])
    assert ranked['violations'] == sum(x['status'] == VIOLATION for x in ranked['cases'])
    assert ranked['cases'][0]['case_id'] != 'case_0001'  # extra rail resistance shifts current toward cell 1, so the baseline is not the worst margin
    unconfigured = rec['rankings']['by_requirement']['current_imbalance_pct']  # no limit configured: nothing is ranked, nothing is combined
    assert unconfigured['cases'] == [] and unconfigured['violations'] == 0
    assert 'not a requirement verdict' in rec['rankings']['by_metric']['peak_branch_current_A']['label']


def test_budget_and_coverage(project):
    rec = search(project, rail_segments=['rail_p_1', 'rail_n_1'], added_resistance_ohm=[0.001, 0.002], max_cases=2)
    assert rec['coverage'] == dict(requested=5, evaluated=2, skipped_by_budget=3, electrical_stopped=0, errors=0, thermal_failures=0)
    assert [c['case_id'] for c in rec['cases']] == ['case_0001', 'case_0002']


def test_record_is_immutable_and_verified(project):
    first = search(project)
    path = project.path / 'investigations' / first['investigation_id'] / 'investigation.json'
    original = path.read_text(encoding='utf-8')
    assert inv.get(project, first['investigation_id']) == first
    second = search(project)
    assert (first['investigation_id'], second['investigation_id']) == ('inv_0001', 'inv_0002')
    assert path.read_text(encoding='utf-8') == original  # a later investigation never rewrites an earlier record
    tampered = original.replace('"requested": 2', '"requested": 3')
    assert tampered != original
    path.write_text(tampered, encoding='utf-8')
    with pytest.raises(s.RequestError) as caught:
        inv.get(project, first['investigation_id'])
    assert caught.value.code == 'integrity_error'
    assert inv.get(project, second['investigation_id']) == second  # the untouched record still verifies


def test_open_case_reproduces_metrics(project):
    r0 = project.inspect()['design']['connections']['rail_p_1']['resistance']['value']
    rec = search(project)
    case = next(c for c in rec['cases'] if c['rail_segment'] == 'rail_p_1')
    assert case['added_resistance_ohm'] == 0.002 and case['electrical_status'] == 'completed'
    opened = inv.open_case(project, rec['investigation_id'], case['case_id'], 'C1', 'Degraded rail_p_1')
    assert opened['variant_id'] == 'C1' and opened['runs'] == []
    assert opened['design']['connections']['rail_p_1']['resistance']['value'] == pytest.approx(r0 + 0.002, abs=1e-15)
    assert project.inspect('A0')['design']['connections']['rail_p_1']['resistance']['value'] == r0  # the investigated variant is untouched
    run = project.run('C1', expected_revision=project.inspect('C1')['revision_id'], plots=False)
    assert run['execution_status'] == 'completed'
    assert run['summary']['maximum_branch_current_A'] == pytest.approx(case['metrics']['peak_branch_current_A'], abs=1e-12)
    assert run['summary']['thermal']['peak_cell_temperature_C'] == pytest.approx(case['peak_cell_temperature_C'], abs=1e-9)


def test_stale_revision_rejected(project):
    stale = project.inspect()['revision_id']
    edit(project, 'connection', 'rail_n_3', 'resistance', 0.002, 'ohm')
    assert project.inspect()['revision_id'] != stale
    with pytest.raises(s.RequestError) as caught:
        inv.run(project, 'A0', stale, PLAN)
    assert caught.value.code == 'conflict'
    assert not (project.path / 'investigations').exists() and not (project.path / 'project.lock').exists()


def test_case_budget_bounds_grid_construction(project, monkeypatch):
    built = []
    original = inv._case
    def track(*args, **kwargs):
        built.append(args[2])
        return original(*args, **kwargs)
    monkeypatch.setattr(inv, '_case', track)
    rec = search(project, rail_segments=['rail_p_1', 'rail_n_1'],
        added_resistance_ohm=[(i+1)*0.0001 for i in range(50)],
        load_current_A=[float(i+1) for i in range(50)], ambient_C=[float(i-10) for i in range(50)], max_cases=1)
    assert rec['coverage']['requested'] == 50*50*(1+2*50)
    assert rec['coverage']['evaluated'] == 1 and built == [1]
    assert rec['coverage']['skipped_by_budget'] == rec['coverage']['requested']-1


@pytest.mark.parametrize('key', ['added_resistance_ohm', 'load_current_A', 'ambient_C'])
def test_plan_lists_have_an_explicit_resource_limit(project, key):
    with pytest.raises(s.RequestError, match='at most 50'):
        inv.validate_plan({**PLAN, key: [1.0]*51}, project.inspect()['design'])


def test_thermal_failure_preserves_electrical_case_and_matches_normal_run(project, monkeypatch):
    def broken(*args, **kwargs):
        raise ValueError('Injected thermal failure')
    edit(project, 'engineering_requirements', 'module', 'peak_branch_current',
         {'limit': 3.9, 'documented_source': 'Declared test target'}, 'A', 'proposed_requirement')
    monkeypatch.setattr(inv.thermal_v1, 'simulate', broken)
    rec = search(project)
    normal = project.run('A0', expected_revision=project.inspect()['revision_id'], plots=False)
    assert normal['execution_status'] == 'completed' and normal['summary']['thermal']['status'] == 'failed'
    assert rec['coverage']['errors'] == 0 and rec['coverage']['thermal_failures'] == 2
    baseline = rec['cases'][0]
    assert baseline['electrical_status'] == 'completed' and baseline['stop'] is None
    assert baseline['thermal_status'] == 'failed' and baseline['thermal_error']['message'] == 'Injected thermal failure'
    assert baseline['metrics']['peak_branch_current_A'] == pytest.approx(normal['summary']['maximum_branch_current_A'])
    assert baseline['requirements']['peak_branch_current_A']['status'] == VIOLATION
    assert baseline['peak_cell_temperature_C'] is None
