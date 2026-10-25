"""Synthetic-only local two-RC diagnostics checks; no measurement outcomes."""
import json
from pathlib import Path
import sys

import numpy as np
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import ae_p45b_local_dynamics as study
from ae_p45b_equations import Parameters, State, advance, terminal_voltage


def synthetic():
    t=np.r_[np.arange(0.,121.),np.arange(123.,1002.,3.)]
    i=np.where(t<121.,-4.5,0.)
    reference=3.7+2e-6*t
    initial=np.array([.004,-.008]);tau=np.array([8.,160.]);r=np.array([.02,.01,.03])
    y=study.prediction(t,i,reference,r,tau,initial)
    return t,i,reference,initial,tau,r,y,121


def test_exact_constant_pulse_and_rest():
    t=np.arange(0.,101.);i=np.where(t<40.,-3.,0.);tau=20.
    b,m=study.rc_basis(t,i,tau)
    assert b[40]==pytest.approx(-3*(1-np.exp(-40/tau)),abs=1e-14)
    assert b[-1]==pytest.approx(b[40]*np.exp(-60/tau),abs=1e-14)
    assert m==pytest.approx(np.exp(-t/tau))


def test_sign_and_nonzero_initial_state_match_existing_electrical_kernel():
    t=np.array([0.,.2,1.,4.,20.,31.,90.]);i=np.array([-4.,-4.,-4.,0.,2.,2.,0.])
    p=Parameters(3.7,3.7,.01,.02,250.,.03,3000.,0.)
    state=State(.8,-1.,.004,-.006);states=[state]
    for dt,c in zip(np.diff(t),i[:-1]):
        state=advance(state,p,float(c),float(dt),4.5);states.append(state)
    actual=[terminal_voltage(s,p,float(c)) for s,c in zip(states,i)]
    y=study.prediction(t,i,np.full(len(t),3.7),[.01,.02,.03],[5.,90.],[.004,-.006])
    assert y==pytest.approx(actual,abs=1e-13)
    assert y[0] < 3.7


def test_exact_recurrence_is_invariant_to_subdivision():
    sparse=np.array([0.,10.,20.,50.]);current=np.array([-2.,-2.,0.,0.])
    fine=np.arange(51.);fine_i=np.where(fine<20.,-2.,0.)
    a,_=study.rc_basis(sparse,current,17.);b,_=study.rc_basis(fine,fine_i,17.)
    assert a==pytest.approx(b[sparse.astype(int)],abs=1e-13)


@pytest.mark.parametrize('times,current,tau', [([0,0],[1,1],1),([0,1],[1,float('nan')],1),([0,1],[1,1],0),([0,1],[1,1],float('inf')),([0],[1],1)])
def test_bad_recurrence_inputs_fail(times,current,tau):
    with pytest.raises(ValueError):study.rc_basis(times,current,tau)


def test_tau_labels_cannot_swap():
    with pytest.raises(ValueError,match='tau1'):
        study.design([0,1],[0,1],[2,1],[0,0])


def test_phase_weights_preserve_complete_phases_without_bridging():
    t=np.array([0.,1.,2.,100.,101.,105.]);w=study.pair_weights(t,3)
    assert w[:3].sum()==pytest.approx(.5) and w[3:].sum()==pytest.approx(.5)
    assert w==pytest.approx([.125,.25,.125,.05,.25,.20])
    for split in [0,1,5,6]:
        with pytest.raises(ValueError):study.pair_weights(t,split)


def test_known_resistances_and_grid_time_constants_recovered():
    t,i,ref,init,tau,r,y,split=synthetic();w=study.pair_weights(t,split)
    best,grid=study.grid_fit(t,i,ref,y,init,tau/2,w)
    assert best['resistance_Ohm']==pytest.approx(r,abs=1e-10)
    assert best['tau_s']==pytest.approx(tau)
    assert best['objective_rmse_mV']<1e-9
    assert all(g['tau_s'][0] < g['tau_s'][1] for g in grid)
    assert all(0<=g['resistance_Ohm'][0]<=.2 for g in grid)
    assert json.loads(json.dumps(best))==best


def test_noisy_grid_contains_fixed_tau_and_does_not_claim_confidence():
    t,i,ref,init,tau,r,y,split=synthetic();w=study.pair_weights(t,split)
    y=y+.001*np.sin(t/15.)
    best,grid=study.grid_fit(t,i,ref,y,init,tau,w)
    fixed=next(g for g in grid if g['multipliers']==[1.,1.])
    assert best['objective_rmse_mV']<=fixed['objective_rmse_mV']+1e-10
    desc=study.describe_identifiability(t,i,w,init,best,grid)
    assert desc['rank']==3 and 'NOT confidence' in desc['uncertainty']
    assert json.loads(json.dumps(desc))==desc


def test_rank_deficiency_and_flat_grid_reported():
    t=np.arange(20.);i=np.zeros(20);w=study.pair_weights(t,10)
    best,grid=study.grid_fit(t,i,np.ones(20)*3.7,np.ones(20)*3.7,[0,0],[2,30],w)
    desc=study.describe_identifiability(t,i,w,[0,0],best,grid)
    assert desc['rank']==0 and desc['normalized_condition_number'] is None
    assert desc['flat_profile_flags']==[True,True]


def test_box_fit_reports_active_boundary_and_rejects_bad_data():
    a=np.eye(3);w=np.ones(3);coef,_=study.fit_resistance(a,np.ones(3),w)
    assert coef==pytest.approx([.2,.2,.2])
    with pytest.raises(ValueError):study.fit_resistance(a,[0,np.nan,0],w)
    with pytest.raises(ValueError):study.fit_resistance(a,[0,0,0],[0,0,0])


def test_centered_rest_metric_removes_constant_offset_but_not_claims_ocv():
    t,i,ref,init,tau,r,y,split=synthetic();w=study.pair_weights(t,split)
    desc=study.pair_metrics(t,y,y+.025,split,w)
    assert desc['objective_rmse_mV']==pytest.approx(25.)
    assert desc['rest']['time_bias_mV']==pytest.approx(25.)
    assert desc['centered_rest_time_rmse_mV']<1e-10
    assert desc['late_rest_median_error_mV']==pytest.approx(25.)


def test_slow_tau_retains_prior_history_while_fast_tau_forgets():
    t=np.r_[np.arange(100.),np.arange(100.,1901.,10.)];i=np.where(t<100.,-4.5,0.)
    slow,_=study.rc_basis(t,i,1280.);fast,_=study.rc_basis(t,i,5.)
    assert abs(slow[-1]) > .07 and abs(fast[-1]) < 1e-100
    assert np.exp(-1800/1280)> .2


def test_source_hash_failure_stops_before_outcome_open(tmp_path,monkeypatch):
    source=tmp_path/'source.txt';source.write_text('original')
    config=tmp_path/'configs';config.mkdir()
    (config/'ae_p45b_local_dynamics_v1.json').write_text(json.dumps({'frozen_files':{'source.txt':study.sha(source)}}))
    source.write_text('changed');monkeypatch.setattr(study,'ROOT',tmp_path)
    with pytest.raises(ValueError,match='Frozen source changed'):study.load_sources()


def test_independent_verifier_metrics_and_bound_conditions():
    import verify_p45b_local_dynamics as verify
    t,i,ref,init,tau,r,y,split=synthetic();w=study.pair_weights(t,split)
    a,m=study.design(t,i,tau,init)
    fitted,_=study.fit_resistance(a,y-ref-m,w)
    verify.check_kkt(a,y-ref-m,w,fitted)
    with pytest.raises(AssertionError):verify.check_kkt(a,y-ref-m,w,np.array([.1,.1,.1]))
    independent=verify.direct_voltage(t,i,ref,tau,r,init)
    assert independent==pytest.approx(y,abs=1e-13)
    got=verify.independent_metrics(t,y,y+.01)
    assert got['sample_rmse_mV']==pytest.approx(10.)
    assert got['time_bias_mV']==pytest.approx(10.)
