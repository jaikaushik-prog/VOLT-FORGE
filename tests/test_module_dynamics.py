import copy
import numpy as np
import pytest
from voltforge.models import coupling_v2 as d
from voltforge.models import coupling as old
from voltforge.simulation import workflow as w


def cell():
    return dict(kind='C2_rest_reference_RC',capacity_Ah=5.,parameters_ohm=[.02,.03],tau_s=20.,soc_knots=[.1,.5,.9],
        reference={'rest':[{'soc':0.,'V':3.7},{'soc':1.,'V':3.7}]})


def run(dt=.25,profile=None,polar=None):
    return d.simulate([cell()]*4,[.5]*4,[0.]*4 if polar is None else polar,
        profile or [dict(start_s=0,end_s=60,current_A=8.)],dt,[0.]*3,[0.]*3).frame


def test_analytic_symmetric_rc_voltage_and_integrated_energy():
    f=run();t=f.time_s.to_numpy();a=np.exp(-t/20)
    np.testing.assert_allclose(f.terminal_V,3.6+.06*a,atol=1e-13)
    np.testing.assert_allclose(f[[f'I{k}_A' for k in range(1,5)]],2.,atol=1e-12)
    expected_Wh=8*(3.6*60+.06*20*(1-np.exp(-3)))/3600
    assert f.delivered_net_Wh.iloc[-1]==pytest.approx(expected_Wh,abs=4e-8)
    assert f.R0_and_rail_loss_Wh.iloc[-1]==pytest.approx(4*.02*4*60/3600)
    r1_J=4*.06**2/.03*(60-40*(1-np.exp(-3))+10*(1-np.exp(-6)))
    assert f.R1_loss_Wh.iloc[-1]==pytest.approx(r1_J/3600,abs=1e-12)
    assert abs(f.energy_balance_residual_Wh.iloc[-1])<4e-8
    assert abs(f.charge_balance_As).max()<1e-8


def test_rc_work_splits_into_heat_and_storage_for_arbitrary_initial_state():
    v=np.array([.02,-.01]);i=np.array([-1.,3.]);r=np.array([.03,.04]);tau=np.array([20.,30.])
    end,loss,work=d.rc_interval(v,i,r,tau,3.7)
    np.testing.assert_allclose(work,loss+.5*tau/r*(end**2-v**2),atol=1e-15)
    assert np.all(loss>=0)


def test_charge_rest_discharge_events_and_signed_service():
    profile=[dict(start_s=0,end_s=10,current_A=-8.),dict(start_s=10,end_s=15,current_A=0.),dict(start_s=15,end_s=25,current_A=8.)]
    f=run(.7,profile);assert {10.,15.,25.}<=set(f.time_s)
    np.testing.assert_allclose(f[[f'SOC{k}' for k in range(1,5)]].iloc[-1],.5,atol=1e-13)
    assert f.terminal_V.iloc[0]>3.7 and f.received_Wh.iloc[-1]>0 and f.delivered_positive_Wh.iloc[-1]>0
    assert f.module_charge_As.iloc[-1]==pytest.approx(0,abs=1e-12)
    fine=run(.05,profile)
    assert abs(f.delivered_net_Wh.iloc[-1]-fine.delivered_net_Wh.iloc[-1])<1e-6


def test_nonzero_initial_polarization_and_node_drops_match_frozen_solver():
    models=[cell()]*4;initial=[.005,-.005,0,.003]
    result=d.simulate(models,[.5]*4,initial,[dict(start_s=0,end_s=5,current_A=8.)],.25,[.001,.002,.003],[.004,.002,.001])
    f=result.frame
    for k in range(1,5):np.testing.assert_allclose(f[f'V{k}_V'],f[f'positive_node{k}_V']-f[f'negative_node{k}_V'],atol=1e-13)
    np.testing.assert_allclose(f.positive_node2_V-f.positive_node1_V,f.positive_rail1_drop_V,atol=1e-13)
    assert abs(f.complete_power_residual_W).max()<1e-12
    assert abs(f.kcl_residual_A).max()<1e-12
    for k in range(1,5):assert abs(f[f'charge_balance{k}_As']).max()<1e-8


def test_zero_external_current_can_have_circulation_and_losses():
    models=[cell()]*4;models=copy.deepcopy(models);models[0]['reference']['rest'][1]['V']=4.1
    f=d.simulate(models,[.5]*4,[0.]*4,[dict(start_s=0,end_s=5,current_A=0.)],.1,[.001]*3,[.001]*3).frame
    assert f.I1_A.iloc[0]>0 and f.I2_A.iloc[0]<0
    assert f.delivered_net_Wh.iloc[-1]==0 and f.cell_R0_loss_W.min()>0
    assert abs(f.charge_balance_As).max()<1e-8


def test_domain_stop_preserves_partial_state_without_clipping():
    a=cell();a['reference']['rest'][0]['soc']=.1
    result=d.simulate([a],[.1001],[0.],[dict(start_s=0,end_s=10,current_A=20)],1,[],[])
    assert result.status.startswith('stopped') and result.frame.time_s.iloc[-1]==0
    assert result.stop['attempted_SOC'][0]<.1 and result.frame.SOC1.iloc[0]==.1001
    assert result.stop['first_reference_boundary_time_s']==pytest.approx(.09)


def test_same_state_convention_reproduces_legacy_coupling():
    models=[cell()]*4
    before=old.simulate(models,[.5]*4,8.,5.,.25,.001)
    after=d.simulate(models,[.5]*4,[0.]*4,[dict(start_s=0,end_s=5,current_A=8)],.25,[.001]*3,[.001]*3).frame
    for col in ['terminal_V']+[f'I{k}_A' for k in range(1,5)]+[f'SOC{k}' for k in range(1,5)]:
        np.testing.assert_allclose(before[col],after[col],atol=1e-12)


def test_energy_quadrature_converges_and_missing_requirement_is_not_pass():
    coarse=run(1);fine=run(.25)
    assert abs(coarse.energy_balance_residual_Wh.iloc[-1])>10*abs(fine.energy_balance_residual_Wh.iloc[-1])
    req={'requirements':dict(minimum_terminal_voltage_V=None,maximum_contiguous_excursion_s=None,documented_source=None)}
    assert w.requirement_result(fine,req,True)['status']=='requirement not configured'
    assert w.requirement_result(fine,req,False)['status']=='requirement not configured'


def test_invalid_profile_and_reference_extrapolation_rejected():
    with pytest.raises(ValueError):d.validate_profile([dict(start_s=1,end_s=2,current_A=1)])
    with pytest.raises(ValueError):d.VoltageReference(cell(),'unknown')
    ref=d.VoltageReference(cell())
    with pytest.raises(ValueError):ref.value(-.01)
