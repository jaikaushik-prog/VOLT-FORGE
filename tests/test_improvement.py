"""Independent dynamics, bounded identification, masking and metric tests."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
from voltforge.models import improvement as m

ROOT=Path(__file__).resolve().parents[1]


def test_rc_vector_bases_are_exact_on_irregular_clock():
    t=np.array([0.,.3,2.,8.,11.]);d=np.column_stack([np.full(5,2.),np.full(5,-3.)])
    x=m.rc_basis(t,d,4)
    np.testing.assert_allclose(x,(1-np.exp(-t[:,None]/4))*np.array([2.,-3.]),atol=1e-14)
    # Right-held change at t=.3 integrates the new input over the first interval.
    z=m.rc_basis([0,.3],[0,2],4,'right')
    assert z[-1,0]==pytest.approx(2*(1-np.exp(-.3/4)))


def test_soc_bases_partition_and_positive_resistance():
    b=m.basis([0,.1,.3,.5,.7,.9,1],[.1,.5,.9])
    np.testing.assert_allclose(b.sum(axis=1),1)
    assert np.all(b>=0)
    np.testing.assert_allclose(b@np.array([.02,.03,.04]),[.02,.02,.025,.03,.035,.04,.04])


def test_small_bounded_solver_coupling():
    p=m.box_solve(np.array([[2.,1.],[1.,2.]]),np.array([5.,4.]),[0,0],[1,3])
    np.testing.assert_allclose(p,[1,1.5],atol=1e-8)


def test_reference_is_monotone_and_does_not_silently_extend():
    ref={'rest':[{'soc':.2,'V':3.4},{'soc':.5,'V':3.8},{'soc':.8,'V':4.1}]}
    u=m.reference(np.linspace(.2,.8,101),np.zeros(101),ref,'rest')
    assert np.all(np.diff(u)>0)
    outside=m.reference([.1,.9],[0,0],ref,'rest')
    assert np.isnan(outside).all()


def test_bin_time_metric_does_not_bridge_excluded_samples_or_cycles():
    f=pd.DataFrame(dict(time_s=[0,1,2,1000,1001],cycle=[1,1,1,2,2],
        row=[1,2,3,4,5],error_V=[.01,100,.03,.04,.04]))
    got=m.aggregate(f,[True,False,True,True,True])
    assert got['sample_rmse_mV']==pytest.approx(np.sqrt((100+900+1600+1600)/4))
    assert got['time_rmse_mV']==pytest.approx(40)
    assert got['duration_s']==1


def test_source_masks_nonpermitted_voltages_before_calibration(monkeypatch):
    monkeypatch.chdir(ROOT)
    try: m.v1.source_archive()
    except ValueError: pytest.skip('Official archive required')
    plan=m.read_json(m.PLAN)
    # Opened P7 only: this test cannot consume the reserved fresh cells.
    _,f,_=m.load_cell('P7',plan['calibration_cycles'])
    held=f.cycle.isin(plan['evaluation_cycles'])
    assert f.loc[held,'V_V'].isna().all() and f.loc[held,'surface_C'].isna().all()
    a=m.references(f,plan['calibration_cycles'])
    poisoned=f.copy();poisoned.loc[held,'V_V']=1000
    assert m.references(poisoned,plan['calibration_cycles'])==a
    for c in plan['calibration_cycles']:
        pd.testing.assert_frame_equal(f[f.cycle==c],poisoned[poisoned.cycle==c])


def test_fresh_allocation_and_v1_hashes_are_preserved(monkeypatch):
    monkeypatch.chdir(ROOT);plan=m.read_json(m.PLAN);lock=m.read_json(m.LOCK)
    assert set(plan['fresh_cells']).isdisjoint(plan['development_cells'])
    assert set(plan['fresh_cells']).issubset(lock['previously_uninspected_nmc_cells'])
    assert set(plan['calibration_cycles']).isdisjoint(plan['evaluation_cycles'])
    for p,h in lock['protected'].items(): assert m.v1.digest(p)==h
    for cell in lock['cells'].values():
        for c in range(1,9): assert cell['cycles'][str(c)]['last_row']+1==cell['cycles'][str(c+1)]['first_row']


def test_soc_offset_is_not_an_observation_based_initializer():
    f=pd.DataFrame(dict(row=[1,2,3],time_s=[0.,1.,2.],I_A=[0,0,0],V_V=[3.6,3.6,3.6],
        surface_C=[23]*3,cycle=[2]*3,step=[10]*3,soc=[.4]*3,loaded_V=[3.6]*3))
    model=dict(kind=m.METHODS[1],parameters_ohm=[.02],tau_s=1,soc_knots=[.1,.5,.9],
        reference={'rest':[{'soc':.2,'V':3.4},{'soc':.8,'V':4.0}]})
    first=m.predictions(f,model,[2],soc_offset=.02)
    f.V_V=999.
    second=m.predictions(f,model,[2],soc_offset=.02)
    np.testing.assert_array_equal(first.predicted_V,second.predicted_V)
    np.testing.assert_allclose(first.predicted_V,3.62)


def test_v2_parameter_recovery_from_analytical_pulses():
    plan=m.read_json(ROOT/'configs/model_improvement_v2.json');tau=float(np.geomspace(1,300,41)[20])
    t=np.arange(0,120,.5);current=np.zeros(len(t));state=np.zeros(len(t))
    for time,change in [(0,2),(20,-2),(40,-1),(50,1),(70,1),(80,-1)]:
        current+=np.where(t>=time,change,0)
        state+=np.where(t>=time,change*(1-np.exp(-np.maximum(0,t-time)/tau)),0)
    frames=[]
    for c in plan['calibration_cycles']:
        soc=np.full(len(t),.95-.08*c);u=3.65+.5*soc
        step=np.select([t<20,t<40,t<50,t<70,t<80],[10,11,12,13,14],default=15)
        frames.append(pd.DataFrame(dict(cycle=c,step=step,time_s=t+c*1000,I_A=current,soc=soc,loaded_V=u,V_V=u-.02*current-.03*state)))
    ref={'rest':[{'soc':.1,'V':3.7},{'soc':.9,'V':4.1}]}
    model=m.fit_model(pd.concat(frames),ref,m.METHODS[2],plan)
    np.testing.assert_allclose(model['parameters_ohm'],[.02,.03],atol=1e-11)
    assert model['tau_s']==pytest.approx(tau)
    assert model['identifiable']


def test_coupled_symmetric_charge_accounting():
    from voltforge.models.coupling import simulate
    model=dict(kind='C1_rest_reference_R',capacity_Ah=5.,parameters_ohm=[.02],tau_s=1.,soc_knots=[.1,.5,.9],
        reference={'rest':[{'soc':0.,'V':3.7},{'soc':1.,'V':3.7}]})
    f=simulate([model]*4,[.7]*4,12.,360.,1.,rail_ohm=0.)
    np.testing.assert_allclose(f[[f'I{k}_A' for k in range(1,5)]],3.,atol=1e-12)
    np.testing.assert_allclose(f[[f'SOC{k}' for k in range(1,5)]].iloc[-1],.64,atol=1e-12)
    assert max(abs(f.total_charge_balance_As))<1e-8
    np.testing.assert_allclose(f.terminal_V,3.64,atol=1e-12)


def test_coupled_polarization_matches_constant_current_closed_form():
    from voltforge.models.coupling import simulate
    model=dict(kind='C2_rest_reference_RC',capacity_Ah=5.,parameters_ohm=[.02,.03],tau_s=20.,soc_knots=[.1,.5,.9],
        reference={'rest':[{'soc':0.,'V':3.7},{'soc':1.,'V':3.7}]})
    f=simulate([model],[.7],2.,30.,.7,rail_ohm=0.)
    expected=3.7-.02*2-.03*2*(1-np.exp(-f.time_s/20))
    np.testing.assert_allclose(f.terminal_V,expected,atol=1e-13)


def test_current_coverage_dwell_does_not_bridge_charge_or_cycle_gaps(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT/'scripts'))
    from summarize_improvement import longest_contiguous_span
    f=pd.DataFrame(dict(row=[1,2,3,4,5,6,7],cycle=[1,1,1,1,1,2,2],
        time_s=[0,1,2,3,4,100,101],I_A=[1,-1,1,1,1,1,1]))
    assert longest_contiguous_span(f,f.I_A>0)==2
