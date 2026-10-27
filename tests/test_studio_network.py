"""Analytical circuit, accounting and replay verification, not empirical validation."""
from copy import deepcopy
import io
import json
from pathlib import Path
import subprocess
import sys
import zipfile

import numpy as np
import pytest

from voltforge.models import coupling_v2
from voltforge.project.service import Project
from voltforge.studio.network import Circuit, MODEL_KEYS, digest, physics, readiness, settings_default, simulate, template, validate_graph
from voltforge.studio.store import Studio
from voltforge.studio.copilot import apply_actions

ROOT=Path(__file__).resolve().parents[1]

@pytest.fixture
def bank():
    base=json.loads((ROOT/'reports/module_simulation_v1/configured/equal_soc.json').read_text())
    return dict(zip(MODEL_KEYS,base['models']))

@pytest.fixture
def constant_bank():
    model=dict(kind='C2_rest_reference_RC',parameters_ohm=[.025,.02],tau_s=60.,capacity_Ah=5.,
               reference=dict(rest=[dict(soc=.1,V=3.7),dict(soc=1.,V=3.7)]))
    return {k:deepcopy(model) for k in MODEL_KEYS}

def short(seconds=5,current=4,dt=.5):
    s=settings_default();s['profile']=[dict(start_s=0.,end_s=seconds,current_A=current)];s['dt_s']=dt;return s

@pytest.mark.parametrize('kind,count,voltage,current',[('parallel',4,3.7-.025,1.),('series',4,4*(3.7-.1),4.),('mixed',4,2*(3.7-.05),2.),('parallel',1,3.7-.1,4.)])
def test_analytical_topologies(kind,count,voltage,current):
    g=template(kind,count)
    for w in g['connections']:w['resistance_mohm']=0
    result=Circuit(g).solve(np.full(count,3.7),np.full(count,.025),4.)
    assert result['terminal']==pytest.approx(voltage,abs=1e-12)
    assert result['current']==pytest.approx(np.full(count,current),abs=1e-12)
    assert abs(result['power_residual'])<1e-11

@pytest.mark.parametrize('current',[-8.,0.,8.])
def test_editable_parallel_is_identical_to_sealed_ladder(bank,current):
    g=template();s=short(10,current)
    r=simulate(g,s,bank)
    legacy=coupling_v2.simulate(list(bank.values()),[.7]*4,[0.]*4,s['profile'],s['dt_s'],[.001]*3,[.001]*3)
    for i,row in enumerate(r.rows):
        assert row['voltage_V']==pytest.approx(legacy.frame.iloc[i].terminal_V,abs=2e-12)
        assert row['cell_current_A']==pytest.approx([legacy.frame.iloc[i][f'I{k+1}_A'] for k in range(4)],abs=2e-10)

@pytest.mark.parametrize('kind',['series','parallel','mixed'])
def test_all_topologies_conserve_current_power_charge_heat(bank,kind):
    r=simulate(template(kind,4),short(20,2),bank)
    checks=r.summary['verification']
    assert checks['max_kcl_A']<1e-9
    assert checks['max_kvl_V']<1e-12
    assert checks['max_power_residual_W']<1e-10
    assert checks['max_cell_charge_residual_As']<1e-8
    assert checks['max_thermal_residual_J']<1e-8
    assert all(np.isfinite(list(row['temperature_C'])).all() for row in r.rows)


def test_single_cell_adiabatic_heat_matches_exact_rc_loss(constant_bank):
    g=template('parallel',1);g['thermal']['ambient_conductance_W_K']=0
    r=simulate(g,short(120,1,.5),constant_bank)
    _,loss,_=coupling_v2.rc_interval(0.,1.,.02,60.,120.)
    expected=23+(.025*120+loss)/69.25
    assert r.rows[-1]['temperature_C'][0]==pytest.approx(expected,abs=1e-11)
    assert abs(r.rows[-1]['thermal_residual_J'])<1e-9


def test_passive_rest_and_cooling_analytic(constant_bank):
    g=template('parallel',1);g['cells'][0]['temperature_C']=26
    r=simulate(g,short(120,0),constant_bank)
    expected=23+3*np.exp(-g['thermal']['ambient_conductance_W_K']*120/69.25)
    assert r.rows[-1]['temperature_C'][0]==pytest.approx(expected,abs=1e-11)
    assert all(row['power_W']==0 for row in r.rows)


def test_electrical_steps_converge_voltage_and_bound_energy_error(bank):
    g=template();voltage=[];errors=[]
    for dt in [1.,.5,.25,.125]:
        r=simulate(g,short(30,10,dt),bank)
        voltage.append(r.rows[-1]['voltage_V'])
        errors.append(abs(r.summary['verification']['final_energy_residual_Wh']))
    # Independent endpoint refinement: cancellation in an energy residual can be nonmonotonic.
    assert abs(voltage[2]-voltage[3])<abs(voltage[1]-voltage[3])<abs(voltage[0]-voltage[3])
    assert max(errors)<1e-6


def test_reordered_cells_do_not_change_physics(bank):
    g=template();other=deepcopy(g);other['cells']=other['cells'][::-1];other['connections']=other['connections'][::-1]
    a=simulate(g,short(),bank);b=simulate(other,short(),bank)
    assert a.rows[-1]['voltage_V']==pytest.approx(b.rows[-1]['voltage_V'],abs=1e-12)
    assert a.rows[-1]['cell_current_A']==pytest.approx(b.rows[-1]['cell_current_A'][::-1],abs=1e-12)


def test_load_events_and_charging_abs_peak(bank):
    g=template();s=short();s['profile']=[dict(start_s=0,end_s=1.3,current_A=3),dict(start_s=1.3,end_s=2.1,current_A=-7),dict(start_s=2.1,end_s=3,current_A=0)]
    r=simulate(g,s,bank)
    assert [row['time_s'] for row in r.rows if row['time_s'] in (1.3,2.1)]==[1.3,2.1]
    assert r.summary['metrics']['peak_cell_current_A']==pytest.approx(max(abs(i) for row in r.rows for i in row['cell_current_A']))


def test_temperature_gate_prevents_false_hot_room_result(bank):
    g=template();s=short();s['ambient_C']=58
    with pytest.raises(ValueError,match='22–28'):simulate(g,s,bank)
    s['ambient_C']=23;g['cells'][0]['temperature_C']=60
    with pytest.raises(ValueError,match='22–28'):simulate(g,s,bank)


def test_warming_stops_before_leaving_model_support(bank):
    r=simulate(template('series',4),short(600,12),bank)
    assert r.status=='stopped' and r.stop['reason']=='temperature_domain'
    assert max(v for row in r.rows for v in row['temperature_C'])<=28
    assert r.rows[-1]['time_s']<600


def test_soc_domain_is_not_clipped_or_extrapolated(bank):
    g=template('parallel',1);g['cells'][0]['charge_pct']=15
    r=simulate(g,short(3600,2,1),bank)
    assert r.status=='stopped' and r.stop['reason']=='charge_domain'
    assert r.rows[-1]['charge_pct'][0]>9

@pytest.mark.parametrize('case',['output_short','cell_short','disconnected','missing_output','duplicate','negative','nan'])
def test_bad_circuits_cannot_be_simulated(case):
    g=template()
    if case=='output_short':g['output']['negative']=g['output']['positive']
    elif case=='cell_short':g['connections'].append(dict(id='short',a='cell2:p',b='cell2:n',resistance_mohm=0,source='Software test'))
    elif case=='disconnected':g['connections']=[]
    elif case=='missing_output':g['output']['positive']=None
    elif case=='duplicate':g['connections'].append(deepcopy(g['connections'][0]))
    elif case=='negative':g['connections'][0]['resistance_mohm']=-1
    elif case=='nan':g['cells'][0]['charge_pct']=float('nan')
    with pytest.raises(ValueError):Circuit(g)
    assert not readiness(g)['ready']


def test_geometry_is_not_connectivity_or_a_new_analysis(bank):
    g=template();other=deepcopy(g);other['cells'][0].update(x=790,y=600,name='Renamed cell');other['name']='New title'
    assert digest(physics(g))==digest(physics(other))
    assert simulate(g,short(),bank).rows==simulate(other,short(),bank).rows
    other['connections'][0]['resistance_mohm']=6
    assert simulate(g,short(),bank).rows[0]['cell_current_A']!=simulate(other,short(),bank).rows[0]['cell_current_A']


def test_sixteen_cells_are_real_network_elements(bank):
    r=simulate(template('parallel',16),short(2,16),bank)
    assert len(r.rows[0]['cell_current_A'])==16
    assert sum(r.rows[0]['cell_current_A'])==pytest.approx(16,abs=1e-10)


def test_series_does_not_report_parallel_current_imbalance(bank):
    result=simulate(template('series',4),short(2,2),bank)
    assert result.summary['metrics']['imbalance_pct'] is None


def test_saved_revisions_conflicts_exports_and_replay(tmp_path):
    project=tmp_path/'project';Project.create_reference(project);studio=Studio(project)
    doc=studio.create('mixed',4,'Editable test')
    settings=short(2,2);doc=studio.save(doc['id'],doc['version'],doc['graph'],settings)
    run=studio.run(doc['id'],doc['version']);assert run['current']
    moved=deepcopy(doc['graph']);moved['cells'][0]['x']+=30
    doc=studio.save(doc['id'],doc['version'],moved,settings)
    assert studio.test(run['id'])['current']
    changed=deepcopy(moved);changed['cells'][0]['charge_pct']=65
    prior=doc['version'];doc=studio.save(doc['id'],prior,changed,settings)
    assert not studio.test(run['id'])['current']
    with pytest.raises(ValueError,match='another window'):studio.save(doc['id'],prior,changed,settings)
    package=studio.export(run['id']);folder=tmp_path/'export';folder.mkdir()
    with zipfile.ZipFile(io.BytesIO(package)) as z:z.extractall(folder)
    p=subprocess.run([sys.executable,str(folder/'replay.py')],capture_output=True,text=True)
    assert p.returncode==0,p.stderr
    assert 'Reproduced' in p.stdout
    path=studio.root/'tests'/f'{run["id"]}.json';damaged=json.loads(path.read_text());damaged['rows'][0]['voltage_V']+=1;path.write_text(json.dumps(damaged))
    with pytest.raises(ValueError,match='modified'):studio.test(run['id'])


def test_copilot_changes_are_typed_and_validated():
    g=template();s=settings_default()
    action=dict(op='set_charge',target='cell3',value=60,text='',from_terminal='',to_terminal='')
    labels=apply_actions(g,s,[action]);validate_graph(g)
    assert g['cells'][2]['charge_pct']==60 and labels==['Cell 3: starting charge 60%']
    action['value']=150;apply_actions(g,s,[action])
    with pytest.raises(ValueError):validate_graph(g)


def test_charge_energy_is_received_not_negative_delivered_energy(bank):
    r=simulate(template(),short(10,-4),bank)
    assert r.summary['metrics']['received_energy_Wh']>0
    assert r.summary['metrics']['delivered_energy_Wh']==0
    assert r.summary['metrics']['net_energy_Wh']<0


def test_ai_preview_stale_apply_and_template_alternative(tmp_path,monkeypatch):
    from voltforge.studio.copilot import Copilot
    project=tmp_path/'project';Project.create_reference(project);s=Studio(project);doc=s.create()
    copilot=Copilot(s)
    action=dict(op='set_charge',target='cell1',value=60,text='',from_terminal='',to_terminal='')
    monkeypatch.setattr(copilot,'_infer',lambda prompt:dict(message='Proposed edit.',actions=[action]))
    proposal=copilot.chat([dict(role='user',content='Change the charge')],doc['id'])['proposal']
    assert s.document(doc['id'])['graph']['cells'][0]['charge_pct']==70
    g=deepcopy(doc['graph']);g['cells'][0]['charge_pct']=65;s.save(doc['id'],doc['version'],g,doc['settings'])
    with pytest.raises(ValueError,match='another window'):copilot.apply(proposal['id'])
    action.update(op='use_template',target='',value=4,text='series')
    latest=s.document(doc['id']);proposal=copilot.chat([dict(role='user',content='Make an alternative')],doc['id'])['proposal']
    alternative=copilot.apply(proposal['id'])
    assert alternative['id']!=doc['id']
    assert len(alternative['graph']['connections'])==3
    assert s.document(doc['id'])['graph']==latest['graph']


def test_zero_resistance_links_report_unidentifiable_current_and_replay(tmp_path):
    project=tmp_path/'project';Project.create_reference(project);s=Studio(project);doc=s.create()
    g=deepcopy(doc['graph'])
    for w in g['connections']:w['resistance_mohm']=0
    doc=s.save(doc['id'],doc['version'],g,short(2,4))
    result=s.run(doc['id'],doc['version'])
    assert result['rows'][0]['wire_current_A']==[None]*6
    assert result['rows'][0]['wire_loss_W']==[0]*6
    folder=tmp_path/'package';folder.mkdir()
    with zipfile.ZipFile(io.BytesIO(s.export(result['id']))) as z:z.extractall(folder)
    p=subprocess.run([sys.executable,str(folder/'replay.py')],capture_output=True,text=True)
    assert p.returncode==0,p.stderr


def test_individual_cell_heat_capacity_changes_temperature_not_electrical_wiring(constant_bank):
    graph=template('parallel',2)
    for w in graph['connections']:w['resistance_mohm']=0
    graph['thermal']['ambient_conductance_W_K']=0
    graph['thermal']['cell_parameters']={'cell2':{'heat_capacity_J_K':138.5}}
    result=simulate(graph,short(60,2),constant_bank)
    row=result.rows[-1]
    assert row['cell_current_A']==pytest.approx([1,1])
    assert row['temperature_C'][1]-23==pytest.approx((row['temperature_C'][0]-23)/2,abs=1e-10)
    assert result.summary['verification']['max_thermal_residual_J']<1e-8
