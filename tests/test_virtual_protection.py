from copy import deepcopy
import json
from pathlib import Path

import pytest

from voltforge.models.custom_cells import normalize
from voltforge.studio.network import simulate,template,settings_default,validate_settings
from voltforge.studio.protection import defaults


def configuration():
    graph=template('parallel',1);graph['cells'][0]['model']='custom_control'
    bank={'custom_control':normalize(dict(name='Synthetic resistive control fixture',capacity_Ah=2.,nominal_voltage_V=3.7,resistance_mohm=20.),'custom_control')}
    settings=settings_default();settings['profile']=[dict(start_s=0.,end_s=2.,current_A=1.),dict(start_s=2.,end_s=8.,current_A=3.)]
    settings['dt_s']=.4;settings['protection']=defaults();settings['protection']['current_max_A']=2.
    settings['limits']['min_voltage_V']=3.
    return graph,settings,bank


def test_sensor_sampling_response_delay_disconnect_and_unserved_mission():
    graph,settings,bank=configuration();result=simulate(graph,settings,bank)
    control=result.summary['protection'];event=control['event']
    assert event['detected_time_s']==2.
    assert event['disconnect_time_s']==2.5
    assert control['actuated']
    assert event['true_value']==pytest.approx(3.) and event['measured_value']==pytest.approx(3.)
    switch=[r for r in result.rows if r['time_s']==2.5]
    assert [r['current_A'] for r in switch]==[3.,0.]
    assert [r['external_disconnected'] for r in switch]==[False,True]
    assert [r['event_side'] for r in switch]==['before','after']
    assert all(r['requested_current_A']==3. for r in switch)
    service=result.summary['service']
    assert not service['requested_demand_met']
    assert service['unserved_demand_s']==5.5
    assert service['unserved_requested_charge_As']==16.5
    assert result.status=='completed' and result.rows[-1]['time_s']==8.
    assert result.summary['checks'][0]['status']=='inconclusive'
    assert result.summary['verification']['max_cell_charge_residual_As']<1e-8
    assert abs(result.rows[-1]['energy_residual_Wh'])<1e-9
    assert result.rows[-1]['delivered_energy_Wh']==pytest.approx((1*(3.7-.02)*2+3*(3.7-.06)*.5)/3600,abs=1e-12)


def test_declared_sensor_offset_can_change_control_response():
    graph,settings,bank=configuration();settings['protection']['sensor_bias']['current_A']=-1.1
    result=simulate(graph,settings,bank)
    assert result.summary['protection']['event'] is None
    assert result.summary['service']['requested_demand_met']
    assert result.rows[-1]['current_A']==3.
    assert result.summary['checks'][0]['status']=='within_target'


def test_threshold_between_sensor_samples_waits_for_the_next_sample_then_response_delay():
    graph,settings,bank=configuration()
    settings['profile'][0]['end_s']=2.1;settings['profile'][1]['start_s']=2.1
    result=simulate(graph,settings,bank);event=result.summary['protection']['event']
    assert event['detected_time_s']==2.5
    assert event['disconnect_time_s']==3.
    assert result.summary['service']['unserved_demand_s']==5.


def test_positive_sensor_offset_can_cause_an_earlier_false_trip():
    graph,settings,bank=configuration();settings['protection']['sensor_bias']['current_A']=1.1
    result=simulate(graph,settings,bank);event=result.summary['protection']['event']
    assert event['true_value']==pytest.approx(1.)
    assert event['measured_value']==pytest.approx(2.1)
    assert event['detected_time_s']==0.
    assert event['disconnect_time_s']==.5


def test_zero_load_cutoff_is_recorded_and_later_requested_load_edges_survive():
    graph,settings,bank=configuration()
    settings['profile']=[dict(start_s=0.,end_s=2.,current_A=0.),dict(start_s=2.,end_s=8.,current_A=3.)]
    settings['protection']['voltage_min_V']=3.8
    settings['protection']['response_delay_s']=0.
    result=simulate(graph,settings,bank)
    at_start=[r for r in result.rows if r['time_s']==0.]
    assert [r['external_disconnected'] for r in at_start]==[False,True]
    assert all(r['event_kind']=='protective_disconnect' for r in at_start)
    at_request=[r for r in result.rows if r['time_s']==2.]
    assert [r['requested_current_A'] for r in at_request]==[0.,3.]
    assert [r['current_A'] for r in at_request]==[0.,0.]
    assert all(r['event_kind']=='requested_load_change' for r in at_request)
    assert result.summary['service']['unserved_demand_s']==6.


def test_controlled_experiment_exports_and_replays_without_parent_repository(tmp_path):
    from voltforge.project.service import Project
    from voltforge.studio.store import Studio
    import io,zipfile,subprocess,sys
    root=tmp_path/'project';Project.create_reference(root);studio=Studio(root)
    graph,settings,bank=configuration()
    definition={k:v for k,v in bank['custom_control'].items() if k in ('name','capacity_Ah','nominal_voltage_V','resistance_mohm','thermal_defaults')}
    card=studio.create_cell(definition=definition);graph['cells'][0]['model']=card['key']
    doc=studio.create_from_graph(graph,settings);record=studio.run(doc['id'],doc['version'])
    with zipfile.ZipFile(io.BytesIO(studio.export(record['id']))) as z:
        report=z.read('report.html').decode();assert 'Virtual sensing and protection' in report and 'Known unserved demand' in report
        csv=z.read('results.csv').decode();assert 'Requested current (A)' in csv and 'External disconnect open' in csv
        z.extractall(tmp_path/'export')
    replay=subprocess.run([sys.executable,'replay.py'],cwd=tmp_path/'export',capture_output=True,text=True)
    assert replay.returncode==0,replay.stderr


def test_external_disconnect_does_not_erase_internal_parallel_current():
    graph,settings,bank=configuration();graph=template('parallel',2)
    for c in graph['cells']:c['model']='custom_control'
    # Add a supplied voltage-vs-charge relationship to create a real EMF mismatch.
    bank['custom_control']=normalize(dict(name='Synthetic varying-voltage cell',capacity_Ah=2.,nominal_voltage_V=3.7,resistance_mohm=20.,reference={'soc':[0.,1.],'voltage_V':[3.,4.2]}),'custom_control')
    graph['cells'][1]['charge_pct']=60.
    settings['profile']=[dict(start_s=0.,end_s=2.,current_A=3.)]
    settings['protection']['current_max_A']=1.;settings['protection']['response_delay_s']=0.
    result=simulate(graph,settings,bank)
    after=next(r for r in result.rows if r['external_disconnected'])
    assert after['current_A']==0.
    assert max(abs(v) for v in after['cell_current_A'])>1.
    assert sum(after['cell_current_A'])==pytest.approx(0.,abs=1e-10)


def test_delayed_action_after_model_stop_is_not_reported_as_actuated():
    graph,settings,bank=configuration()
    # Narrow source support: the numerical model ends before the pending switch.
    bank['custom_control']['reference']={'soc':[.6999,1.],'voltage_V':[3.7,3.7]}
    settings['profile']=[dict(start_s=0.,end_s=8.,current_A=3.)]
    settings['protection']['response_delay_s']=5.
    result=simulate(graph,settings,bank)
    assert result.status=='stopped'
    assert result.rows[-1]['time_s']<5.
    assert not result.summary['protection']['actuated']
    assert result.summary['service']['unserved_demand_s']==0.
    assert result.summary['service']['unconfirmed_requested_demand_s']>0.
    assert not result.summary['service']['requested_demand_met']


def test_temperature_threshold_rejects_electrical_only_model():
    graph,settings,bank=configuration();bank['custom_control']['thermal_defaults']=None
    settings['protection']['temperature_max_C']=40.
    with pytest.raises(ValueError,match='needs a thermal model'):simulate(graph,settings,bank)


def test_individual_cell_voltage_is_monitored_even_when_total_output_looks_acceptable():
    graph,settings,bank=configuration();graph=template('series',2)
    for c in graph['cells']:c['model']='custom_control'
    bank['custom_control']=normalize(dict(name='Synthetic varying-voltage cell',capacity_Ah=2.,nominal_voltage_V=3.7,resistance_mohm=20.,reference={'soc':[0.,1.],'voltage_V':[3.,4.2]}),'custom_control')
    graph['cells'][1]['charge_pct']=20.
    settings['profile']=[dict(start_s=0.,end_s=2.,current_A=1.)]
    settings['limits']['min_voltage_V']=6.6
    settings['protection'].update(current_max_A=None,voltage_min_V=3.3,response_delay_s=.25)
    result=simulate(graph,settings,bank);event=result.summary['protection']['event']
    assert result.rows[0]['voltage_V']>6.6
    assert event['cell']=='cell2' and event['quantity']=='voltage_V'
    assert event['true_value']==pytest.approx(3.22)
    assert event['detected_time_s']==0. and event['disconnect_time_s']==.25
    assert result.summary['service']['unserved_demand_s']==1.75
    assert result.summary['checks'][0]['status']=='inconclusive'


def test_temperature_threshold_samples_actual_predicted_heating():
    graph,settings,bank=configuration()
    bank['custom_control']=normalize(dict(name='Synthetic insulated cell',capacity_Ah=2.,nominal_voltage_V=3.7,resistance_mohm=20.,
        thermal_defaults={'heat_capacity_J_K':1.,'ambient_conductance_W_K':0.}),'custom_control')
    settings['profile']=[dict(start_s=0.,end_s=2.,current_A=3.)]
    settings['protection'].update(current_max_A=None,temperature_max_C=23.1,response_delay_s=.25)
    result=simulate(graph,settings,bank);event=result.summary['protection']['event']
    # .18 W into 1 J/K crosses 23.1 C at 5/9 s; sampling waits until 1 s.
    assert event['quantity']=='temperature_C' and event['detected_time_s']==1.
    assert event['true_value']==pytest.approx(23.18,abs=1e-10)
    assert event['disconnect_time_s']==1.25
    assert result.summary['metrics']['peak_temperature_C']==pytest.approx(23.225,abs=1e-10)


def test_virtual_switch_does_not_authorize_unsupported_initial_current():
    graph,settings,_=configuration()
    root=Path(__file__).resolve().parents[1]
    bank=json.loads((root/'configs/cell_catalogue_v2.json').read_text())['models'];graph['cells'][0]['model']='LG_M50T_ECN'
    settings['profile']=[dict(start_s=0.,end_s=1.,current_A=200.)]
    settings['protection']['response_delay_s']=0.
    with pytest.raises(ValueError,match='cutoff|operating limit'):simulate(graph,settings,bank)


def test_sensor_event_budget_and_unknown_fields_are_rejected():
    _,settings,_=configuration();settings['protection']['unsupported']='code'
    with pytest.raises(ValueError,match='supported virtual'):validate_settings(settings)


def test_combined_sensor_and_solver_event_budget_is_bounded():
    _,settings,_=configuration()
    settings['profile']=[dict(start_s=0.,end_s=2000.,current_A=1.)]
    settings['dt_s']=.1
    settings['protection']['sample_period_s']=.05
    settings['protection']['response_delay_s']=.025
    with pytest.raises(ValueError,match='all solver and control events'):validate_settings(settings)
