"""Source-aware thermal inputs and independent forcing/sign checks."""
import io
import json
from pathlib import Path
import subprocess
import sys
import zipfile

import numpy as np
import pytest
from scipy.integrate import solve_ivp

from scripts.reanalyze_fixture_cooling import propagate
from voltforge.models.cell_catalogue import load_additional
from voltforge.project.service import Project
from voltforge.studio.network import template,settings_default,simulate
from voltforge.studio.store import Studio

ROOT=Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('rate',[.0025,1/120])
def test_measured_ambient_propagator_against_independent_ode(rate):
    time=np.array([0.,0.,.2,.9,2.,5.,11.])
    ambient=np.array([23.,23.,25.,24.,26.,25.,23.])
    capacity=58.5;offset=-.4;heat=.2
    expected=[29.]
    for i,h in enumerate(np.diff(time)):
        if h==0:
            expected.append(expected[-1]);continue
        def rhs(t,y):
            room=ambient[i]+(ambient[i+1]-ambient[i])*(t-time[i])/h
            return [-rate*(y[0]-room-offset)+heat*np.exp(-t/120)/capacity]
        result=solve_ivp(rhs,(time[i],time[i+1]),[expected[-1]],method='DOP853',rtol=2e-12,atol=1e-12)
        assert result.success;expected.append(result.y[0,-1])
    actual=propagate(time,ambient,29.,rate,offset,heat,capacity)
    assert actual==pytest.approx(expected,abs=2e-10)


@pytest.mark.parametrize('current',[1.,-1.])
def test_reversible_heat_uses_kelvin_and_discharge_positive_sign(current):
    model=dict(kind='temperature_dependent_ecm/1',key='synthetic',name='Synthetic heat check',family='Synthetic',origin='user',
               capacity_Ah=2.,nrc=0,soc=[.2,1.],temperature_C=[15.,35.],
               ocv_V=[[3.8,3.8]]*2,r0_ohm=[[.02,.02]]*2,r_ohm=[[[],[]]]*2,tau_s=[[[],[]]]*2,
               thermal_defaults={'heat_capacity_J_K':70.,'ambient_conductance_W_K':0.},
               operating_limits={},entropy={'soc':[.2,1.],'dOCV_dT_V_K':[.0001,.0001]})
    graph=template('parallel',1);graph['cells'][0].update(model='synthetic',temperature_C=25.)
    settings=settings_default();settings.update(dt_s=.1,profile=[dict(start_s=0.,end_s=60.,current_A=current)])
    result=simulate(graph,settings,{'synthetic':model})
    # dT_kelvin/dt=(-I alpha T_kelvin + I^2 R0)/C.
    a=-current*.0001/70.;b=current**2*.02/70.
    exact_K=298.15*np.exp(a*60)+b*np.expm1(a*60)/a
    final=result.rows[-1]['temperature_C'][0]
    assert result.status=='completed'
    assert final==pytest.approx(exact_K-273.15,abs=3e-8)
    assert (final<25.) if current>0 else (final>25.)


def test_actual_thermal_values_sources_and_user_override_survive_export(tmp_path):
    bank=load_additional(ROOT);model=bank['LG_M50T_ECN']
    assert model['thermal_defaults']['heat_capacity_J_K']==58.5
    assert model['thermal_provenance']['parameter_classification']['heat_capacity_J_K']=='published_reference_parameter'
    graph=template('parallel',1);graph['cells'][0]['model']='LG_M50T_ECN'
    settings=settings_default();settings['profile']=[dict(start_s=0.,end_s=2.,current_A=2.)]
    baseline=simulate(graph,settings,bank)
    entry=baseline.summary['thermal_assumptions'][0]
    assert entry['parameters']['heat_capacity_J_K']['value']==58.5
    assert '10.1016/j.est.2021.103065' in entry['parameters']['heat_capacity_J_K']['source']
    graph['thermal']['cell_parameters']={'cell1':{'heat_capacity_J_K':90.}}
    root=tmp_path/'project';Project.create_reference(root);studio=Studio(root)
    doc=studio.create_from_graph(graph,settings);record=studio.run(doc['id'],doc['version'])
    changed=record['summary']['thermal_assumptions'][0]['parameters']
    assert changed['heat_capacity_J_K']['value']==90.
    assert changed['heat_capacity_J_K']['classification']=='user_override'
    assert changed['ambient_conductance_W_K']['classification']=='fixture_calibration_estimate'
    assert record['rows'][-1]['temperature_C'][0]<baseline.rows[-1]['temperature_C'][0]
    with zipfile.ZipFile(io.BytesIO(studio.export(record['id']))) as archive:
        evidence=json.loads(archive.read('evidence.json'))
        assert evidence['models']['LG_M50T_ECN']['thermal_provenance']['source_registry_sha256']==model['thermal_provenance']['source_registry_sha256']
        html=archive.read('report.html').decode()
        assert '90.0000 J/K' in html and 'User-entered value for this cell instance.' in html
        assert '0.15249 W/K' in html
        archive.extractall(tmp_path/'replay')
    replay=subprocess.run([sys.executable,'replay.py'],cwd=tmp_path/'replay',capture_output=True,text=True)
    assert replay.returncode==0,replay.stderr
