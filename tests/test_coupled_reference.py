"""Independent state-dependent ODE oracle, without production lookup/RC/circuit helpers.

These are synthetic numerical verification fixtures, not experimental cell data.
The formulas are deliberately bilinear so their gridded representation is exact.
"""
from copy import deepcopy

import numpy as np
import pytest
from scipy.integrate import solve_ivp

from voltforge.studio.network import simulate, template, settings_default


def coefficients(z,t,nrc):
    u=3.3+.8*z+.0007*(t-25)
    r0=.020*(1+.01*(30-t))*(1+.2*(z-.5))
    r=np.array([.012*(1+.005*(30-t))*(1+.1*(z-.5)),.006*(1+.008*(30-t))])[:nrc]
    tau=np.array([5.+.04*(t-30)+z,30.+.1*(t-30)+2*z])[:nrc]
    return u,r0,r,tau


def record(key,nrc,capacity,heat,cooling):
    zs=[.2,.5,.8,1.];ts=[15.,30.,45.,55.]
    grid=[[coefficients(z,t,nrc) for z in zs] for t in ts]
    result=dict(kind='temperature_dependent_ecm/1',key=key,name=key,family='Synthetic verification fixture',
                origin='user',capacity_Ah=capacity,nrc=nrc,soc=zs,temperature_C=ts,
                operating_limits={'voltage_V':[2.5,4.3],'max_charge_A':10.,'max_discharge_A':10.},
                thermal_defaults={'heat_capacity_J_K':heat,'ambient_conductance_W_K':cooling})
    for i,k in enumerate(('ocv_V','r0_ohm','r_ohm','tau_s')):result[k]=[[np.asarray(v[i]).tolist() for v in row] for row in grid]
    return result


def setup(dt):
    g=template('parallel',2);g['cells'][0].update(model='synthetic_one',charge_pct=70.,temperature_C=30.,polarization_V=.01)
    g['cells'][1].update(model='synthetic_two',charge_pct=61.,temperature_C=37.,polarization_V=0.)
    g['thermal']['contacts']=[dict(a='cell1',b='cell2',conductance_W_K=.2)]
    bank={'synthetic_one':record('synthetic_one',1,2.,40.,.3),'synthetic_two':record('synthetic_two',2,2.5,60.,.4)}
    s=settings_default();s['profile']=[dict(start_s=0.,end_s=12.,current_A=3.)];s['ambient_C']=40.;s['dt_s']=dt
    return g,s,bank


def independent_state_rhs(_,state):
    # Nodes are cell1+, cell2+, cell2-; cell1- is the reference node.
    z=state[:2];v=[state[2:3],state[3:5]];T=state[5:7]
    pars=[coefficients(z[i],T[i],nrc) for i,nrc in enumerate((1,2))]
    Y=np.zeros((3,3));rhs=np.zeros(3)
    for a,b,resistance in [(0,1,.001),(None,2,.001)]:
        inc=np.zeros(3);inc[b]=-1
        if a is not None:inc[a]=1
        Y+=np.outer(inc,inc)/resistance
    incidence=[np.array([1.,0.,0.]),np.array([0.,1.,-1.])]
    for inc,(u,r0,_,_),vp in zip(incidence,pars,v):
        Y+=np.outer(inc,inc)/r0;rhs+=inc*(u-vp.sum())/r0
    rhs[0]-=3.
    potentials=np.linalg.solve(Y,rhs)
    current=np.array([(p[0]-vp.sum()-inc@potentials)/p[1] for inc,p,vp in zip(incidence,pars,v)])
    vp_dot=[(current[i]*pars[i][2]-v[i])/pars[i][3] for i in range(2)]
    wire_loss=(potentials[0]-potentials[1])**2/.001+potentials[2]**2/.001
    # Half of each rail's heat enters the two cells, shared equally.
    heating=np.array([pars[i][1]*current[i]**2+np.sum(v[i]**2/pars[i][2]) for i in range(2)])+.25*wire_loss
    heat_flow=np.array([.2*(T[1]-T[0]),.2*(T[0]-T[1])])
    T_dot=(heating+np.array([.3,.4])*(40.-T)+heat_flow)/np.array([40.,60.])
    return np.r_[-current/(3600*np.array([2.,2.5])),*vp_dot,T_dot]


def test_mixed_order_coupled_network_converges_to_independent_ode():
    initial=np.array([.7,.61,.01,0.,0.,30.,37.])
    reference=solve_ivp(independent_state_rhs,(0.,12.),initial,method='DOP853',rtol=2e-12,atol=1e-13,dense_output=True)
    assert reference.success
    errors=[]
    for dt in (.4,.2,.1,.05):
        g,s,bank=setup(dt);result=simulate(g,s,bank)
        assert result.status=='completed'
        end=result.rows[-1]
        physical=np.r_[np.array(end['charge_pct'])/100,end['temperature_C']]
        expected=reference.y[[0,1,5,6],-1]
        error=np.abs(physical-expected);errors.append(error)
        assert result.summary['verification']['max_thermal_residual_J']<1e-8
    # Accuracy budget is fixed for this synthetic oracle, before any holdout use.
    assert np.max(errors[-1][:2])<1e-6
    assert np.max(errors[-1][2:])<2e-4
    assert np.linalg.norm(errors[-1])<np.linalg.norm(errors[-2])<np.linalg.norm(errors[-3])<np.linalg.norm(errors[-4])


def test_cooling_time_constant_alone_cannot_identify_driven_heating():
    from voltforge.studio.temperature_engine import ThermalResponse
    # Scaling heat capacity and conductance together keeps passive cooling equal,
    # but changes temperature rise under the same applied heat.
    a=ThermalResponse(np.array([20.]),np.array([[.2]]))
    b=ThermalResponse(np.array([40.]),np.array([[.4]]))
    empty=np.empty((1,0));decay=np.array([])
    cool_a,_=a.step(np.array([35.]),np.array([.2*25]),empty,decay,60)
    cool_b,_=b.step(np.array([35.]),np.array([.4*25]),empty,decay,60)
    assert cool_a==pytest.approx(cool_b,abs=1e-12)
    warm_a,_=a.step(np.array([25.]),np.array([2.+.2*25]),empty,decay,60)
    warm_b,_=b.step(np.array([25.]),np.array([2.+.4*25]),empty,decay,60)
    assert warm_a[0]-25==pytest.approx(2*(warm_b[0]-25),abs=1e-12)
