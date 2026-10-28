from copy import deepcopy
import io
import json
import subprocess
import zipfile

import numpy as np
import pytest

from voltforge.models.custom_cells import normalize, csv_definition
from voltforge.project.service import Project
from voltforge.studio.store import Studio


def basic(**extra):
    result=dict(name='My measured cell',capacity_Ah=2.,nominal_voltage_V=3.7,resistance_mohm=20.,thermal_defaults=None)
    result.update(extra);return result


@pytest.fixture
def studio(tmp_path):
    project=tmp_path/'project';Project.create_reference(project)
    return Studio(project)


def custom_test(studio,definition=None,count=1):
    card=studio.create_cell(definition=definition or basic())
    doc=studio.create('parallel',count)
    graph=deepcopy(doc['graph']);settings=deepcopy(doc['settings'])
    for c in graph['cells']:c.update(model=card['key'],temperature_C=-10.,charge_pct=70.)
    settings['profile']=[dict(start_s=0.,end_s=10.,current_A=2.)]
    doc=studio.save(doc['id'],doc['version'],graph,settings)
    assert doc['readiness']['ready']
    return card,doc,studio.run(doc['id'],doc['version'])


def test_resistive_cell_matches_hand_calculation_and_does_not_invent_temperature(studio):
    card,doc,result=custom_test(studio)
    end=result['rows'][-1]
    assert result['status']=='completed'
    assert end['voltage_V']==pytest.approx(3.7-2*.020)
    assert end['charge_pct']==pytest.approx([70-100*2*10/(3600*2)])
    assert end['loss_energy_Wh']==pytest.approx(2**2*.020*10/3600)
    assert end['delivered_energy_Wh']==pytest.approx(2*3.66*10/3600)
    assert end['temperature_C']==[None]
    assert end['thermal_residual_J'] is None
    assert result['summary']['metrics']['peak_temperature_C'] is None
    assert not result['summary']['experimental_validation']
    assert card['custom'] and not card['thermal_available']
    assert card['operating_limits']=={}
    assert max(abs(r['energy_residual_Wh']) for r in result['rows'])<1e-10


def test_custom_parallel_current_sharing_matches_resistance_network(studio):
    _,_,result=custom_test(studio,count=2)
    # Same-end collection: second cell adds two 1 mΩ connecting rails.
    assert result['rows'][0]['cell_current_A']==pytest.approx([2*.022/.042,2*.020/.042])


def test_declared_custom_thermal_properties_have_analytic_solution(studio):
    definition=basic(thermal_defaults=dict(heat_capacity_J_K=100.,ambient_conductance_W_K=.5))
    _,doc,_=custom_test(studio,definition)
    settings=deepcopy(doc['settings']);settings['ambient_C']=-10.
    doc=studio.save(doc['id'],doc['version'],doc['graph'],settings)
    result=studio.run(doc['id'],doc['version'])
    expected=-10.+(2**2*.02/.5)*(1-np.exp(-.5*10/100))
    assert result['rows'][-1]['temperature_C'][0]==pytest.approx(expected,abs=1e-10)
    assert max(abs(r['thermal_residual_J']) for r in result['rows'])<1e-8


def test_four_required_values_provide_a_traceable_assumed_temperature_estimate(studio):
    definition=basic();definition.pop('thermal_defaults')
    card,_,result=custom_test(studio,definition)
    assert card['thermal_available']
    assert card['thermal_provenance']['status']=='Assumed heat model'
    assert result['summary']['metrics']['peak_temperature_C'] is not None
    assert result['summary']['thermal_assumptions'][0]['version']=='example_cylindrical/1'
    assert not result['summary']['experimental_validation']


def test_new_custom_version_does_not_change_old_design_or_results(studio):
    card,doc,result=custom_test(studio)
    new=studio.create_cell(definition=basic(),parent_key=card['key'])
    assert new['key']!=card['key']
    reopened=Studio(studio.root.parent)
    assert reopened.document(doc['id'])['graph']['cells'][0]['model']==card['key']
    assert reopened.test(result['id'])['current']
    assert reopened.models[new['key']]['revision']==2


def test_other_editor_refreshes_custom_model_registry(studio):
    other=Studio(studio.root.parent)
    card,doc,_=custom_test(studio)
    assert other.document(doc['id'])['readiness']['ready']
    assert card['key'] in other.models


def test_custom_export_contains_definition_and_replays(studio,tmp_path):
    card,_,result=custom_test(studio)
    with zipfile.ZipFile(io.BytesIO(studio.export(result['id']))) as archive:archive.extractall(tmp_path/'export')
    models=json.loads((tmp_path/'export/models.json').read_text())
    assert models[card['key']]['resistance_mohm']==20.
    assert 'Temperature not modeled' in (tmp_path/'export/report.html').read_text()
    run=subprocess.run([__import__('sys').executable,'replay.py'],cwd=tmp_path/'export',capture_output=True,text=True)
    assert run.returncode==0,run.stderr


@pytest.mark.parametrize('changes',[
    {'capacity_Ah':True},{'resistance_mohm':-1},{'nominal_voltage_V':float('nan')},
    {'kind':'python'},{'source':'javascript:alert(1)'},{'thermal_defaults':{'heat_capacity_J_K':20}},
    {'operating_limits':{'max_discharge_A':-1}},{'reference':{'soc':[.8,.4],'voltage_V':[3.7,3.8]}}
])
def test_malformed_cell_definitions_rejected(changes):
    definition=basic();definition.update(changes)
    with pytest.raises(ValueError):normalize(definition,'custom_test')


def test_csv_import_preserves_supplied_voltage_reference():
    data=csv_definition('soc_pct,voltage_V\n10,3.1\n50,3.6\n90,4.1\n',basic())
    record=normalize(data,'custom_csv')
    from voltforge.models.cell_catalogue import CellModel
    assert CellModel(record).parameters(.7,40.)[0]==pytest.approx(3.85)


def test_custom_operating_limit_is_used_without_builtin_fallback(studio):
    card=studio.create_cell(definition=basic(operating_limits={'max_discharge_A':1.}))
    doc=studio.create('parallel',1);g=deepcopy(doc['graph']);g['cells'][0]['model']=card['key']
    doc=studio.save(doc['id'],doc['version'],g,doc['settings'])
    assert not doc['readiness']['ready']
    with pytest.raises(ValueError,match='1 A operating limit'):studio.run(doc['id'],doc['version'])
