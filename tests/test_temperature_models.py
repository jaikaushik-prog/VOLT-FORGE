"""Independent physical limits and numerical references for the new model path."""
from copy import deepcopy
import json
from pathlib import Path

import numpy as np
import pytest
from scipy.integrate import solve_ivp

from voltforge.models.cell_catalogue import CellModel
from voltforge.studio.network import simulate, template, settings_default
from voltforge.studio.temperature_engine import ThermalResponse, convolution, integrated_convolution

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def candidates():
    path = ROOT/'reports/model_catalogue_v1/candidate_catalogue.json'
    if not path.exists(): pytest.skip('Candidate catalogue not built')
    return json.loads(path.read_text())['models']


def setup(seconds=3., temperature=35., ambient=35., current=2., dt=.5):
    g = template('parallel', 1)
    g['cells'][0].update(model='LG_M50T_ECN', temperature_C=temperature)
    s = settings_default(); s['ambient_C'] = ambient; s['dt_s'] = dt
    s['profile'] = [dict(start_s=0., end_s=seconds, current_A=current)]
    return g, s


@pytest.mark.parametrize('a,b',[(0.,0.),(-.02,-.02),(-.02,-.02000000001),(-.002,-1e8),(-200.,0.)])
def test_thermal_exponential_convolutions_against_ode(a,b):
    h=.4
    # Independent integration of a scalar forced system and its integral.
    if b < -1e6:
        assert convolution(np.array(a),np.array(b),h) == pytest.approx(np.exp(a*h)/(a-b),rel=1e-8)
        return
    result=solve_ivp(lambda t,y:[a*y[0]+np.exp(b*t),y[0]],(0,h),[0.,0.],method='DOP853',rtol=2e-12,atol=1e-13)
    assert convolution(np.array(a),np.array(b),h) == pytest.approx(result.y[0,-1],abs=2e-11)
    assert integrated_convolution(np.array(a),np.array(b),h) == pytest.approx(result.y[1,-1],abs=2e-11)


def test_three_node_heat_network_matches_independent_ode():
    C=np.array([50.,70.,90.]);G=np.array([.1,.2,.3])
    K=np.diag(G)+np.array([[.07,-.07,0.],[-.07,.12,-.05],[0.,-.05,.05]])
    q=np.array([2.,3.,4.])+G*25
    f=np.array([[.4,-.1],[.2,.3],[-.1,.4]]);decay=np.array([-.2,-.01]);initial=np.array([22.,26.,30.]);h=13.
    expected=solve_ivp(lambda t,y:np.r_[(-K@y[:3]+q+f@np.exp(decay*t))/C,y[:3]],(0,h),np.r_[initial,[0.,0.,0.]],method='DOP853',rtol=1e-12,atol=1e-12)
    end,integral=ThermalResponse(C,K).step(initial,q,f,decay,h)
    assert end == pytest.approx(expected.y[:3,-1],abs=2e-10)
    assert integral == pytest.approx(expected.y[3:,-1],abs=2e-9)


def test_published_whole_cell_parameters_and_temperature_feedback(candidates):
    m=CellModel(candidates['LG_M50T_ECN'])
    assert m.capacity == 5.
    assert m.nrc == 3
    assert m.parameters(.7,15)[1] > m.parameters(.7,45)[1]
    assert m.parameters(.7,35)[0] != m.parameters(.7,15)[0]
    for T in (15.,35.,55.):
        u,r0,r,tau=m.parameters(.7,T)
        assert np.all(r>0) and np.all(tau>0)
        assert np.isfinite(np.r_[u,r0,r,tau]).all()


def test_ambient_is_boundary_condition_and_initial_voltage_is_independent(candidates):
    g,s=setup(1,35,65,2)
    result=simulate(g,s,candidates)
    m=CellModel(candidates['LG_M50T_ECN']);u,r0,_,_=m.parameters(.7,35)
    assert result.status=='completed'
    assert result.rows[0]['voltage_V'] == pytest.approx(u-2*r0,abs=1e-12)
    assert result.rows[-1]['temperature_C'][0]>35
    assert result.summary['verification']['max_thermal_residual_J']<1e-8


@pytest.mark.parametrize('charge,current',[(70,200),(95,-4.9)])
def test_invalid_operating_points_cannot_complete_without_custom_targets(candidates,charge,current):
    g,s=setup(.1,25,25,current)
    g['cells'][0]['charge_pct']=charge
    with pytest.raises(ValueError,match='cutoff|operating limit'):
        simulate(g,s,candidates)


def test_charge_temperature_limit_is_distinct_from_parameter_table(candidates):
    g,s=setup(1,46,46,-.5)
    with pytest.raises(ValueError,match='Charging exceeds'):
        simulate(g,s,candidates)


def test_first_temperature_boundary_is_localized(candidates):
    g,s=setup(10,54.99,70,1)
    result=simulate(g,s,candidates)
    assert result.status=='stopped' and result.stop['reason']=='temperature_domain'
    assert 0<result.rows[-1]['time_s']<10
    assert result.rows[-1]['temperature_C'][0] <=55
    assert result.rows[-1]['temperature_C'][0] == pytest.approx(55,abs=1e-8)
    assert result.summary['metrics']['duration_s']==result.rows[-1]['time_s']


def test_coupled_trajectory_refines_in_time(candidates):
    values=[]
    for dt in (1.,.5,.25,.125):
        g,s=setup(20,35,40,4,dt)
        r=simulate(g,s,candidates)
        assert r.status=='completed'
        values.append(np.array([r.rows[-1]['voltage_V'],r.rows[-1]['temperature_C'][0]]))
        assert r.summary['verification']['max_cell_charge_residual_As']<1e-8
        assert r.summary['verification']['max_thermal_residual_J']<1e-8
    assert np.linalg.norm(values[2]-values[3])<np.linalg.norm(values[1]-values[3])<np.linalg.norm(values[0]-values[3])


def test_temperature_lookup_never_extrapolates(candidates):
    m=CellModel(candidates['LG_M50T_ECN'])
    with pytest.raises(ValueError,match='recorded model domain'):m.parameters(.7,56)
    with pytest.raises(ValueError,match='recorded model domain'):m.parameters(.01,25)
