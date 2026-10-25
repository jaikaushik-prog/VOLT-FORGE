"""Synthetic analytic checks only; do not load battery measurements/artifacts."""
import copy
import importlib.util
import json
import math
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('thermal_prototype', ROOT/'scripts/thermal_prototype.py')
thermal = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(thermal)


def cfg():
    return json.loads((ROOT/'configs/thermal_feasibility_v1.json').read_text())


def segment(start=0., end=120., q=2., ambient=25.):
    return dict(start_s=start,end_s=end,prescribed_heat_W=q,ambient_temperature_degC=ambient)


@pytest.mark.parametrize('q', [-2., 0., 2.])
@pytest.mark.parametrize('initial', [20., 25., 30.])
def test_exact_step_against_independent_closed_form(q,initial):
    c,h,a,d=100.,.5,25.,120.
    t,e_in,e_out,stored=thermal.exact_interval(initial,a,q,c,h,d)
    equilibrium=a+q/h
    expected=equilibrium+(initial-equilibrium)*math.exp(-h*d/c)
    assert t == pytest.approx(expected,abs=1e-12)
    assert stored == pytest.approx(c*(expected-initial),abs=1e-11)
    assert e_in == q*d
    assert e_in-e_out-stored == pytest.approx(0,abs=1e-11)


@pytest.mark.parametrize('q', [-2., 0., 2.])
def test_adiabatic_limit_and_zero_boundary_flow(q):
    t,source,outward,stored=thermal.exact_interval(25.,80.,q,100.,0.,120.)
    assert t == pytest.approx(25.+q*1.2)
    assert source == stored == q*120.
    assert outward == 0.


def test_near_zero_h_and_zero_duration():
    tiny=thermal.exact_interval(25.,20.,2.,100.,1e-15,120.)
    zero=thermal.exact_interval(25.,20.,2.,100.,0.,120.)
    assert tiny == pytest.approx(zero,abs=1e-10)
    assert thermal.exact_interval(25.,20.,2.,100.,.5,0.) == (25.,0.,0.,0.)


def test_boundary_energy_independent_simpson_quadrature():
    c,h,t0,a,q,d=71.,.31,31.,24.,-1.7,311.
    _,source,outward,stored=thermal.exact_interval(t0,a,q,c,h,d)
    # Independent high-resolution quadrature of the analytic boundary heat rate.
    n=10000; step=d/n
    def flow(t): return h*(q/h+(t0-a-q/h)*math.exp(-h*t/c))
    integral=step/3*(flow(0)+flow(d)+sum((4 if i%2 else 2)*flow(i*step) for i in range(1,n)))
    assert outward == pytest.approx(integral,abs=1e-9)
    assert source-outward-stored == pytest.approx(0.,abs=1e-10)


def test_constant_equilibrium_and_cold_ambient_sign():
    assert thermal.exact_interval(29.,25.,2.,100.,.5,1000.)[0] == 29.
    end,_,outward,_=thermal.exact_interval(20.,25.,0.,100.,.5,120.)
    assert 20. < end < 25.
    assert outward < 0.


def test_events_continuity_and_output_grid_invariance():
    profile=[segment(end=123.),segment(start=123.,end=301.,q=-1.,ambient=30.)]
    args=dict(heat_capacity_J_per_K=100.,conductance_W_per_K=.5,initial_temperature_degC=25.,profile=profile)
    coarse=thermal.simulate(**args,output_step_s=10.)
    fine=thermal.simulate(**args,output_step_s=2.5)
    lookup={r['time_s']:r for r in fine}
    assert all(r==lookup[r['time_s']] for r in coarse)
    event=lookup[123.]
    end,source,outward,stored=thermal.exact_interval(25.,25.,2.,100.,.5,123.)
    assert event['temperature_degC'] == end
    assert event['source_energy_J'] == source
    assert event['outward_boundary_energy_J'] == outward
    assert event['stored_energy_change_J'] == pytest.approx(stored)
    assert event['prescribed_heat_W'] == -1.
    assert event['ambient_temperature_degC'] == 30.
    assert event['interval_index'] == 1


def test_unknown_heat_capacity_conductance_joint_scaling_not_identifiable():
    profile=[segment(),segment(120.,240.,0.)]
    args=dict(heat_capacity_J_per_K=100.,conductance_W_per_K=.5,
              initial_temperature_degC=25.,profile=profile,output_step_s=10.)
    first=thermal.simulate(**args)
    scaled=copy.deepcopy(args); scaled['heat_capacity_J_per_K']*=3; scaled['conductance_W_per_K']*=3
    for p in scaled['profile']: p['prescribed_heat_W']*=3
    second=thermal.simulate(**scaled)
    assert [r['temperature_degC'] for r in first] == pytest.approx([r['temperature_degC'] for r in second],abs=1e-12)


@pytest.mark.parametrize('key,value', [('heat_capacity_J_per_K',0),('heat_capacity_J_per_K',-1),
    ('conductance_W_per_K',-1),('initial_temperature_degC',-273.15),('output_step_s',0),
    ('output_step_s',float('nan')),('heat_capacity_J_per_K',True),('comparison_output_step_s',1e-10),
    ('model','module_thermal'),('evidence_kind','measured'),('cell_identity','LG M50T'),
    ('electrical_coupling',True),('schema_version',True)])
def test_invalid_configuration_rejected(key,value):
    data=cfg(); data[key]=value
    with pytest.raises(ValueError): thermal.validate_config(data)


@pytest.mark.parametrize('change', ['missing','unknown','gap','overlap','nonfinite','ambient','provenance'])
def test_no_defaults_silent_fields_or_profile_repair(change):
    data=cfg()
    if change=='missing': del data['conductance_W_per_K']
    if change=='unknown': data['electrical_loss_csv']='would_be_unsupported.csv'
    if change=='gap': data['profile'][1]['start_s']+=1
    if change=='overlap': data['profile'][1]['start_s']-=1
    if change=='nonfinite': data['profile'][0]['prescribed_heat_W']=float('inf')
    if change=='ambient': data['profile'][0]['ambient_temperature_degC']=-280
    if change=='provenance': data['provenance']['profile']=''
    with pytest.raises(ValueError): thermal.validate_config(data)


def test_stops_instead_of_clipping_absolute_zero():
    with pytest.raises(ValueError,match='absolute zero'):
        thermal.exact_interval(25.,25.,-1e6,100.,0.,120.)


def test_export_replay_and_tamper_rejection(tmp_path):
    out=tmp_path/'synthetic_run'
    summary=thermal.run(ROOT/'configs/thermal_feasibility_v1.json',out)
    assert summary['electrical_coupling'] is False
    assert summary['reporting_grid_check']['max_shared_temperature_difference_degC'] == 0.
    assert thermal.verify(out)['rows_replayed'] == 242
    with pytest.raises(ValueError,match='already exists'):
        thermal.run(ROOT/'configs/thermal_feasibility_v1.json',out)
    with (out/'series.csv').open('a') as f: f.write('\n')
    with pytest.raises(ValueError,match='Output changed'):
        thermal.verify(out)
