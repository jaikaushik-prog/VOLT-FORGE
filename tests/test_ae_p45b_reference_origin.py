"""Synthetic policy and finite-rest diagnostic tests; no protected measurements."""
import json
from pathlib import Path
import sys

import numpy as np
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import ae_p45b_reference_origin as study


def author():return dict(mode='author_reproduction',record_id='SYNTHETIC',temperature_degC=25,protocol='discharge')


def declared():
    return dict(mode='declared_anchor',record_id='SYNTHETIC',temperature_degC=25,protocol='discharge',cell_id='SYNTHETIC_CELL',
        preparation_source='synthetic prep',anchor_definition=study.ANCHOR,nominal_capacity_Ah=4.5,
        history_source='synthetic history',time_s=[0.,60.,120.],current_A=[-4.5,-4.5,0.],polarity='charge_positive',
        integration='left',max_gap_s=60.,anchor_time_s=0.,initial_time_s=120.,initial_hysteresis=-1.,
        initial_polarization_V=[-.01,-.02],state_basis='assumed',state_source='synthetic states',reference_compatibility_source='unverified synthetic declaration')


def test_charge_convention_and_no_voltage_tuning():
    t=[0,60,120];i=[-4.5,0,4.5]
    assert study.charge_coordinate(t,i)[-1]==pytest.approx(1-1/60)
    assert study.charge_coordinate(t,i,mode='linear')[-1]==pytest.approx(1.)
    assert study.charge_coordinate(t,i,.995)[-1]==pytest.approx(.995-1/60)


@pytest.mark.parametrize('t,i,kw',[([0,0],[0,0],{}),([0,1],[0,np.nan],{}),([0,1],[0,0],{'mode':'other'}),([0,121],[0,0],{'max_gap_s':120}),([0,1],[0,0],{'max_gap_s':float('inf')})])
def test_invalid_or_missing_charge_history_rejected(t,i,kw):
    with pytest.raises(ValueError):study.charge_coordinate(t,i,**kw)


def test_author_conditions_are_explicit_assumptions_not_verified_evidence():
    result=study.initial_state_policy(author(),(-.01,1.))
    assert result['initial_state']==dict(soc=1.,hysteresis=-1.,polarization_V=[0.,0.])
    assert result['runnable'] and not result['evidence_verified'] and not result['reference_equilibrium_verified']
    assert result['missing_evidence'] and 'NOT measured' in result['state_basis']
    assert json.loads(json.dumps(result))==result


def test_declared_anchor_integrates_only_current_and_never_certifies_provenance():
    req=declared();r=study.initial_state_policy(req,(-.01,1.))
    assert r['initial_state']['soc']==pytest.approx(1-1/30)
    assert not r['evidence_verified'] and r['status']=='conditional_declared_anchor'
    req['preparation_source']='I assert this is verified';req['reference_compatibility_source']='perfectly calibrated'
    again=study.initial_state_policy(req,(-.01,1.))
    assert not again['evidence_verified'] and again['initial_state']==r['initial_state']


def test_unknown_missing_metadata_and_missing_states_remain_unrunnable():
    unknown=study.initial_state_policy({'mode':'unknown'},(-.01,1.))
    assert not unknown['runnable'] and unknown['initial_state'] is None
    req=declared();del req['initial_polarization_V']
    result=study.initial_state_policy(req,(-.01,1.))
    assert not result['runnable'] and 'initial_polarization_V' in result['missing_evidence']


@pytest.mark.parametrize('field,value',[('measured_voltage_V',4.2),('initial_soc_fit',.99),('ocv_inversion',True),('verified',True)])
def test_voltage_calibration_or_certification_fields_rejected(field,value):
    req=author();req[field]=value
    with pytest.raises(ValueError,match='fields'):study.initial_state_policy(req,(-.01,1.))


@pytest.mark.parametrize('field,value',[('state_basis','measured'),('polarity','discharge_positive'),('initial_time_s',121.),('nominal_capacity_Ah',4.4),('temperature_degC',40),('protocol','charge'),('initial_hysteresis',2.)])
def test_unsupported_initial_state_declarations_rejected(field,value):
    req=declared();req[field]=value
    with pytest.raises(ValueError):study.initial_state_policy(req,(-.01,1.))


def rest(slope=1e-5):
    return [dict(source_line=j+2,time_s=float(j),voltage_V=3.7+slope*j,reference_V=3.71,nominal_soc=.5,source_current_A=0.) for j in range(1801)]


def test_drift_windows_keep_exact_source_lines_and_do_not_claim_equilibrium():
    rows=rest();r=study.rest_window(rows,60.)
    assert r['source_first_line']==1742 and r['source_last_line']==1802 and r['samples']==61
    assert r['slope_mV_per_min']==pytest.approx(.6,abs=1e-10)
    assert not r['equilibrium_established']
    flat=study.rest_window(rest(0),600.)
    assert flat['slope_mV_per_min']==pytest.approx(0.,abs=1e-10) and not flat['equilibrium_established']


def test_short_or_sparse_windows_not_extended_and_reference_failure_visible():
    rows=rest();assert study.rest_window(rows[:20],60.)['reference_status']=='unsupported_window'
    assert study.rest_window(rows[::500],60.)['reference_status']=='unsupported_window'
    rows[-1]['reference_V']=None
    result=study.rest_window(rows,60.)
    assert result['reference_status']=='unsupported_reference' and result['measured_median_V'] is not None


def test_metrics_do_not_bridge_undefined_reference():
    m=study.metrics([0,1,100,200,202],[1,1,np.nan,2,2])
    assert m['duration_s']==3 and m['time_rmse_mV']==pytest.approx(np.sqrt(3.))


def test_reference_stop_preserves_every_original_channel_and_never_clips_soc():
    class Table:
        def query(self,z):
            if z<.98:raise ValueError('outside support')
            class P:ocv_discharge_V=3.7
            return P(),[]
    source=[dict(source_line=j+2,time_s=j*60.,source_current_A=-4.5,voltage_V=3.6,controlled_temperature_degC=25) for j in range(5)]
    trace,stop=study.reference_trace(Table(),source,1.,'left')
    assert stop['source_line']==4 and len(trace)==len(source)
    assert trace[-1]['nominal_soc']<.98 and trace[-1]['reference_V'] is None
    for a,b in zip(source,trace):assert all(a[k]==b[k] for k in source[0])


def test_cross_record_interpolation_does_not_extend_or_identify_cells():
    co=[dict(nominal_soc=.9,voltage_V=4,source_line=2,source_current_A=-.15),dict(nominal_soc=.8,voltage_V=3.9,source_line=3,source_current_A=-.15)]
    gitt=[dict(rest_endpoint_nominal_soc=z,rest_last_source_line=j,windows={'60':{'measured_median_V':v}}) for z,j,v in [(.9,5,4.01),(.8,8,3.91)]]
    one=[dict(nominal_soc=.7,voltage_V=3.5,source_line=99,reference_minus_measured_mV=30.)]
    r=study.endpoint_context(co,gitt,one)
    assert r['co30_loaded']['value_V'] is None and r['gitt_finite_rest']['value_V'] is None
    assert r['cross_record_cell_and_preparation_equivalence'].startswith('unverified')


def test_independent_verifier_known_window_and_charge():
    from verify_p45b_reference_origin import independent_coordinate,independent_window
    assert independent_coordinate(np.array([0.,60.,120.]),np.array([-4.5,-4.5,0.]),1.,'left')[-1]==pytest.approx(1-1/30)
    r=independent_window(rest(),60.)
    assert r['slope_mV_per_min']==pytest.approx(.6,abs=1e-8)
