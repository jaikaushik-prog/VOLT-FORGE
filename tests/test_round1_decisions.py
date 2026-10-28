"""Independent audit counterexamples. These verify code, not physical accuracy."""
from copy import deepcopy
import json
from pathlib import Path

import numpy as np
import pytest

from voltforge.models.coupling_v2 import VoltageReference
from voltforge.studio.network import MODEL_KEYS, settings_default, simulate, template

ROOT=Path(__file__).resolve().parents[1]


@pytest.fixture
def bank():
    data=json.loads((ROOT/'reports/module_simulation_v1/configured/equal_soc.json').read_text())
    return dict(zip(MODEL_KEYS,data['models']))


@pytest.mark.parametrize('current,h',[(4.,10.),(4.9,.5)])
def test_both_load_event_sides_and_independent_voltage_oracle(bank,current,h):
    graph=template('parallel',1);settings=settings_default();settings['dt_s']=h
    settings['profile']=[dict(start_s=0.,end_s=h,current_A=current),dict(start_s=h,end_s=h+.1,current_A=0.)]
    model=bank['P7'];ref=VoltageReference(model);r0,r1=model['parameters_ohm']
    z=.7-current*h/(3600*model['capacity_Ah'])
    expected=ref.value(z)-r0*current-r1*current*(1-np.exp(-h/model['tau_s']))
    initial=ref.value(.7)-r0*current
    settings['limits']['min_voltage_V']=(initial+expected)/2
    result=simulate(graph,settings,bank)
    at_event=[row for row in result.rows if row['time_s']==h]
    assert [r['event_side'] for r in at_event]==['before','after']
    assert at_event[0]['voltage_V']==pytest.approx(expected,abs=1e-11)
    assert at_event[1]['voltage_V']-at_event[0]['voltage_V']==pytest.approx(r0*current,abs=1e-11)
    assert result.summary['metrics']['minimum_voltage_V']==pytest.approx(expected,abs=1e-11)
    assert result.summary['checks'][0]['status']=='exceeded'


def test_partial_mission_cannot_clear_unobserved_remainder(bank):
    graph=template('series',4);settings=settings_default()
    settings.update(ambient_C=58.,dt_s=1.)
    settings['profile']=[dict(start_s=0.,end_s=600.,current_A=4.)]
    settings['limits'].update(temperature_C=40.,current_A=100.,min_voltage_V=2.)
    result=simulate(graph,settings,bank)
    assert result.status=='stopped'
    assert 0<result.summary['coverage']['completed_duration_s']<600
    assert not result.summary['coverage']['complete']
    assert {check['status'] for check in result.summary['checks']}=={'inconclusive'}
    assert result.summary['assessment']['physical_clearance'] is False


def test_zero_duration_prefix_is_not_a_pass(bank):
    graph=template('parallel',1);graph['cells'][0]['temperature_C']=28.
    settings=settings_default();settings['ambient_C']=28.
    settings['profile']=[dict(start_s=0.,end_s=60.,current_A=1.)]
    settings['limits']['temperature_C']=40.
    result=simulate(graph,settings,bank)
    assert result.status=='stopped'
    assert result.summary['coverage']['completed_duration_s']==0
    assert result.summary['checks'][0]['status']=='inconclusive'


def test_completed_duty_preserves_nominal_target_status(bank):
    settings=settings_default();settings['profile']=[dict(start_s=0.,end_s=2.,current_A=4.)]
    settings['limits']['current_A']=5.
    result=simulate(template(),settings,bank)
    assert result.summary['coverage']['complete']
    assert result.summary['checks'][0]['status']=='within_target'


def test_observed_violation_stays_exceeded_when_run_later_stops(bank):
    graph=template('parallel',1);graph['cells'][0]['temperature_C']=28.
    settings=settings_default();settings['ambient_C']=28.
    settings['profile']=[dict(start_s=0.,end_s=60.,current_A=1.)]
    settings['limits']['current_A']=.5
    result=simulate(graph,settings,bank)
    assert result.status=='stopped'
    assert result.summary['checks'][0]['status']=='exceeded'


@pytest.mark.parametrize('current',[200.,-200.])
def test_extreme_current_cannot_be_an_ordinary_completed_test(bank,current):
    settings=settings_default();settings['profile']=[dict(start_s=0.,end_s=.1,current_A=current)]
    settings['dt_s']=.01
    with pytest.raises(ValueError,match='cutoff|operating limit|Charging exceeds'):
        simulate(template('parallel',1),settings,bank)
