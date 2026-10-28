from copy import deepcopy
import io
import zipfile

import pytest

from voltforge.models.custom_cells import normalize
from voltforge.studio.conductors import copper_reference,calculate,apply,add_contact_resistance
from voltforge.studio.network import template,settings_default,simulate,validate_graph


def fixture():
    graph=template('parallel',2)
    for cell in graph['cells']:cell['model']='custom_ohmic'
    for wire in graph['connections']:apply(wire,copper_reference())
    models={'custom_ohmic':normalize(dict(name='Synthetic 2 Ah cell',capacity_Ah=2.,nominal_voltage_V=3.7,resistance_mohm=20.),'custom_ohmic')}
    settings=settings_default();settings['profile']=[dict(start_s=0.,end_s=1.,current_A=4.)]
    return graph,settings,models


def test_units_mass_and_contact_floor_against_hand_calculation():
    definition=copper_reference();values=calculate(definition)
    # 30 mm x 8 mm x .2 mm = 48 mm3, 1.6 mm2 cross section.
    assert values['volume_mm3']==pytest.approx(48.)
    assert values['bulk_resistance_mohm']==pytest.approx(.320625)
    assert values['resistance_mohm']==pytest.approx(.520625)
    assert values['mass_g']==pytest.approx(.42912)
    definition['thickness_mm']*=2
    thicker=calculate(definition)
    assert thicker['mass_g']==pytest.approx(.85824)
    assert thicker['resistance_mohm']==pytest.approx(.3603125)
    assert thicker['resistance_mohm']>.5*values['resistance_mohm'] # Contacts did not disappear.


def test_dimensioned_links_change_the_actual_circuit_and_mass():
    graph,settings,models=fixture();result=simulate(graph,settings,models)
    # Two equal cells with same-end collection: each far-cell path has two links.
    # I_near=I_total*(R_cell+2*R_link)/(2*R_cell+2*R_link).
    rw=.000520625;expected_near=4*(.02+2*rw)/(.04+2*rw)
    assert result.rows[0]['cell_current_A'][0]==pytest.approx(expected_near,abs=1e-11)
    assert result.rows[0]['cell_current_A'][1]==pytest.approx(4-expected_near,abs=1e-11)
    assert result.summary['metrics']['conductor_mass_g']==pytest.approx(.85824)
    changed=deepcopy(graph)
    for wire in changed['connections']:
        wire['conductor']['thickness_mm']*=2;apply(wire,wire['conductor'])
    alternative=simulate(changed,settings,models)
    assert alternative.summary['metrics']['conductor_mass_g']==pytest.approx(1.71648)
    assert alternative.summary['metrics']['current_gap_A']<result.summary['metrics']['current_gap_A']
    assert alternative.summary['physical_components']['complete_assembly_mass'] is False
    graph['cells'][0]['x']+=100
    assert simulate(graph,settings,models).rows[0]['cell_current_A']==result.rows[0]['cell_current_A']


def test_inconsistent_conductor_definition_cannot_silently_override_the_solver():
    graph,_,models=fixture();graph['connections'][0]['resistance_mohm']=.01
    with pytest.raises(ValueError,match='does not match'):validate_graph(graph,models)
    for value in [0.,-1.,float('nan')]:
        c=copper_reference();c['thickness_mm']=value
        with pytest.raises(ValueError):calculate(c)


def test_contact_wear_preserves_dimensions_and_adds_to_physical_joint_resistance():
    graph,_,models=fixture();wire=graph['connections'][0]
    before=deepcopy(wire['conductor']);add_contact_resistance(wire,3.,'Declared worn-contact scenario')
    assert wire['conductor']['length_mm']==before['length_mm']
    assert wire['resistance_mohm']==pytest.approx(3.520625)
    assert wire['conductor']['contact_mohm']==pytest.approx(3.2)
    validate_graph(graph,models)


@pytest.mark.parametrize('load',[4.,-4.])
def test_external_route_voltage_and_energy_loss_against_series_resistor(load):
    graph,settings,models=fixture();settings['profile'][0]['current_A']=load
    baseline=simulate(graph,settings,models)
    lead=copper_reference();lead['length_mm']=100.
    graph['output_leads']={'negative':lead}
    result=simulate(graph,settings,models)
    # 100 mm / 1.6 mm2, plus .2 mOhm contacts, is .00126875 Ohm.
    rout=.00126875
    assert result.rows[0]['cell_current_A']==baseline.rows[0]['cell_current_A']
    assert result.rows[0]['voltage_V']==pytest.approx(baseline.rows[0]['voltage_V']-load*rout,abs=1e-11)
    assert result.rows[0]['output_route_loss_W']==pytest.approx(load**2*rout,abs=1e-12)
    assert result.rows[-1]['delivered_energy_Wh']==pytest.approx(baseline.rows[-1]['delivered_energy_Wh']-load**2*rout/3600,abs=1e-12)
    assert abs(result.rows[-1]['energy_residual_Wh'])<1e-10
    assert result.summary['metrics']['conductor_mass_g']==pytest.approx(.85824+1.4304)


def test_physical_definition_report_and_replay_are_portable(tmp_path):
    from voltforge.project.service import Project
    from voltforge.studio.store import Studio
    import subprocess,sys
    root=tmp_path/'project';Project.create_reference(root);studio=Studio(root)
    graph=template('parallel',2)
    for cell in graph['cells']:cell['model']='LG_M50T_ECN'
    for wire in graph['connections']:apply(wire,copper_reference())
    settings=settings_default();settings['profile']=[dict(start_s=0.,end_s=1.,current_A=4.)]
    doc=studio.create_from_graph(graph,settings);record=studio.run(doc['id'],doc['version'])
    assert record['summary']['physical_components']['listed_component_mass_g']==pytest.approx(140.85824)
    with zipfile.ZipFile(io.BytesIO(studio.export(record['id']))) as z:
        html=z.read('report.html').decode()
        assert 'Physical connection trade-offs' in html and '0.429' in html
        assert 'copper.org' in html and 'not included' in html
        z.extractall(tmp_path/'bundle')
    replay=subprocess.run([sys.executable,'replay.py'],cwd=tmp_path/'bundle',capture_output=True,text=True)
    assert replay.returncode==0,replay.stderr
