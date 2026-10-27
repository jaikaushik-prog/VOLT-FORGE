"""Strict schema rejection assertions and the downstream thermal parameter contract."""
import copy
import json
from pathlib import Path

import pytest

from voltforge.models import thermal_v1
from voltforge.project import Project
from voltforge.project import schema as s


@pytest.fixture
def inputs(tmp_path):
    project = Project.create_reference(tmp_path/'project')
    base, manifest = project._inputs(project._state())
    thermal = json.loads(Path('configs/thermal_v1.json').read_text())
    return base, manifest, thermal, s.reference_design(base, manifest, 2, thermal)


def edit(target, prop, value, unit):
    return dict(target=target, id='module', property=prop, value=value,
                unit=unit, source='Declared test input', classification='assumed')


def test_reference_and_v2(inputs):
    base, manifest, thermal, design = inputs
    legacy = s.reference_design(base, manifest)
    assert legacy['schema_version'] == 'voltforge.design/1'
    assert 'thermal' not in legacy and 'engineering_requirements' not in legacy
    assert design['schema_version'] == 'voltforge.design/2'
    assert design['thermal']['model'] == 'lumped_four_node_v1'
    for key in ['heat_capacity_J_per_K', 'ambient_conductance_W_per_K',
                'neighbour_conductance_W_per_K', 'rail_heat_to_cells_fraction']:
        assert design['thermal'][key] == thermal[key]
    assert s.validate_design(design, base, manifest) == design


@pytest.mark.parametrize('capacity', [[0,70,70,70], [-1,70,70,70],
    [float('nan'),70,70,70], [float('inf'),70,70,70], [70,70,70], True, [True,70,70,70]])
def test_invalid_capacity_rejected_by_validation_and_edit(inputs, capacity):
    base, manifest, _, design = inputs
    bad = copy.deepcopy(design)
    bad['thermal']['heat_capacity_J_per_K']['value'] = capacity
    with pytest.raises(s.RequestError) as error:
        s.validate_design(bad, base, manifest)
    assert error.value.code == 'invalid_request'
    with pytest.raises(s.RequestError) as error:
        s.edited(design, edit('thermal', 'heat_capacity', capacity, 'J/K'), base, manifest)
    assert error.value.code == 'invalid_request'


@pytest.mark.parametrize('path,value,code', [
    (('extra',), 1, 'invalid_request'),
    (('thermal','ambient_conductance_W_per_K','value'), [-.1,.1,.1,.1], 'invalid_request'),
    (('thermal','rail_heat_to_cells_fraction','value'), 1.2, 'invalid_request'),
    (('thermal','coupling'), 'changed', 'unsupported_request'),
    (('thermal','heat_capacity_J_per_K','unit'), 'kJ/K', 'invalid_request'),
    (('thermal','heat_capacity_J_per_K','source'), '', 'invalid_request'),
    (('thermal','heat_capacity_J_per_K','classification'), 'bad', 'invalid_request'),
    (('thermal','heat_capacity_J_per_K','classification'), [], 'invalid_request'),
    (('thermal','rail_heat_to_cells_fraction','classification'), {}, 'invalid_request'),
    (('engineering_requirements','active_current_floor_A'), .3, 'unsupported_request'),
    (('engineering_requirements','peak_branch_current_A'), {'limit':-1,'unit':'A','documented_source':'x'}, 'invalid_request'),
    (('engineering_requirements','unknown_x'), {'limit':1,'unit':'A','documented_source':'x'}, 'invalid_request'),
])
def test_v2_rejections(inputs, path, value, code):
    base, manifest, _, design = inputs
    bad = copy.deepcopy(design)
    owner = bad
    for key in path[:-1]:
        owner = owner[key]
    owner[path[-1]] = value
    with pytest.raises(s.RequestError) as error:
        s.validate_design(bad, base, manifest)
    assert error.value.code == code


@pytest.mark.parametrize('bad', [None, [], 'design', 12])
def test_top_level_type_has_structured_error(inputs, bad):
    base, manifest, _, _ = inputs
    with pytest.raises(s.RequestError) as error:
        s.validate_design(bad, base, manifest)
    assert error.value.code == 'invalid_request'


@pytest.mark.parametrize('version', [0, 3, None, '2', True, []])
def test_unsupported_constructor_version_never_silently_downgrades(inputs, version):
    base, manifest, thermal, _ = inputs
    with pytest.raises(s.RequestError) as error:
        s.reference_design(base, manifest, version, thermal)
    assert error.value.code == 'unsupported_request'


def test_missing_thermal_is_rejected(inputs):
    base, manifest, _, design = inputs
    with pytest.raises(s.RequestError):
        s.reference_design(base, manifest, 2)
    bad = copy.deepcopy(design)
    del bad['thermal']
    with pytest.raises(s.RequestError):
        s.validate_design(bad, base, manifest)


@pytest.mark.parametrize('source', [None, '', ' ', {}, False, 123])
def test_configured_limit_cannot_lose_its_source(inputs, source):
    base, manifest, _, design = inputs
    proposal = edit('engineering_requirements', 'peak_branch_current',
                    {'limit':4.5,'documented_source':source}, 'A')
    with pytest.raises(s.RequestError) as error:
        s.edited(design, proposal, base, manifest)
    assert error.value.code == 'invalid_request'


def test_edited_v2_and_runtime_parameter_contract(inputs):
    base, manifest, _, design = inputs
    for prop,key,value,unit in [
        ('heat_capacity','heat_capacity_J_per_K',[70]*4,'J/K'),
        ('ambient_conductance','ambient_conductance_W_per_K',[0]*4,'W/K'),
        ('neighbour_conductance','neighbour_conductance_W_per_K',[0]*3,'W/K'),
        ('rail_heat_to_cells_fraction','rail_heat_to_cells_fraction',.3,'fraction')]:
        changed = s.edited(design, edit('thermal',prop,value,unit), base, manifest)
        assert changed['thermal'][key]['value'] == value
        thermal_v1.check_parameters(s.thermal_parameters(changed))
    for prop,key,value,unit in [('peak_branch_current','peak_branch_current_A',4.5,'A'),
        ('current_imbalance','current_imbalance_pct',10,'%'),
        ('peak_cell_temperature','peak_cell_temperature_C',60,'degC')]:
        changed = s.edited(design, edit('engineering_requirements',prop,
            {'limit':value,'documented_source':'Project proposal'},unit), base, manifest)
        assert changed['engineering_requirements'][key]['limit'] == value
    cleared = s.edited(design, edit('engineering_requirements','peak_branch_current',
        {'limit':None,'documented_source':None},'A'), base, manifest)
    assert cleared['engineering_requirements']['peak_branch_current_A']['limit'] is None
    with pytest.raises(s.RequestError) as error:
        s.edited(design, edit('thermal','unknown',1,'J/K'), base, manifest)
    assert error.value.code == 'unsupported_request'


def test_edited_v1_rejects_thermal_and_invalid_edit_classification(inputs):
    base, manifest, _, design = inputs
    with pytest.raises(s.RequestError) as error:
        s.edited(s.reference_design(base, manifest),edit('thermal','heat_capacity',[70]*4,'J/K'),base,manifest)
    assert error.value.code == 'unsupported_request'
    bad = edit('thermal','heat_capacity',[70]*4,'J/K')
    bad['classification'] = []
    with pytest.raises(s.RequestError) as error:
        s.edited(design,bad,base,manifest)
    assert error.value.code == 'invalid_request'


def test_thermal_parameters(inputs):
    base, manifest, thermal, design = inputs
    assert s.thermal_parameters(s.reference_design(base,manifest)) is None
    values = s.thermal_parameters(design)
    for key in ['heat_capacity_J_per_K','ambient_conductance_W_per_K',
                'neighbour_conductance_W_per_K','rail_heat_to_cells_fraction']:
        assert values[key] == thermal[key]['value']
