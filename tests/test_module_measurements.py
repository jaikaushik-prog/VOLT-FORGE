import copy
import json
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
from voltforge.simulation import measurements as v
from voltforge.simulation import workflow as w
from voltforge.models import coupling_v2 as d


def fixture(folder,change=None):
    folder.mkdir(parents=True,exist_ok=True);t=np.arange(0,3.,.25)
    data={'source_row':np.arange(1,len(t)+1),'time_s':t};channels={}
    for name,(unit,location) in v.CHANNELS.items():
        data[name]=(np.full(len(t),8 if name=='module_current_A' else 2) if unit=='A'
                    else 3.6+.06*np.exp(-t/20)+.01 if unit=='V' else np.full(len(t),23.))
        channels[name]=dict(unit=unit,location=location,sensor_id='synthetic-'+name,time_column='time_s',
            calibration=dict(status='synthetic',source='analytical fixture, not an instrument',date='2026-10-25',absolute_uncertainty=.001))
        if unit=='A':channels[name]['polarity']='discharge_positive'
        if unit=='V':channels[name]['polarity']='positive_minus_negative'
    meta=dict(schema_version=1,data_kind='synthetic_fixture',cell_order=v.CELLS,time_unit='s',time_origin='synthetic elapsed time',channels=channels,
        preparation=dict(history='analytic initial state',initial_soc=[.5]*4,initial_polarization_V=[0.]*4,rest_s=0,source='fixture'),
        synchronization=dict(method='shared synthetic clock',evidence='generated',alignment_tolerance_s=.001,maximum_gap_s=.5))
    f=pd.DataFrame(data)
    if change:change(f,meta)
    f.to_csv(folder/'measurements.csv',index=False);w.save(folder/'metadata.json',meta)
    return folder


def test_ingestion_preserves_raw_bytes_and_declared_polarity(tmp_path):
    def change(f,meta):f['I2_A']=-f.I2_A;meta['channels']['I2_A']['polarity']='charge_positive'
    source=fixture(tmp_path/'source',change);h=w.digest(source/'measurements.csv')
    r,f,_=v.validate(source,tmp_path/'out')
    assert r['valid_structure'] and r['alignment_ok']
    assert r['current_conservation']['maximum_abs_A']==0
    assert w.digest(source/'measurements.csv')==h==w.digest(tmp_path/'out/original/measurements.csv')
    assert f.I2_A.iloc[0]==2 and r['experimental_validation']=='awaiting suitable measurements'


def test_current_discrepancy_is_retained_not_normalized(tmp_path):
    source=fixture(tmp_path/'source',lambda f,m:f.__setitem__('I1_A',f.I1_A+.2))
    r,f,_=v.validate(source,tmp_path/'out')
    assert r['current_conservation']['mean_A']==pytest.approx(.2)
    assert not r['current_conservation']['within_declared_bound']
    assert f.I1_A.iloc[0]==pytest.approx(2.2)


@pytest.mark.parametrize('failure',['missing','unit','location','duplicate','gap','nonfinite','mapping'])
def test_incomplete_or_incompatible_records_fail_structure(tmp_path,failure):
    def change(f,m):
        if failure=='missing':f.drop(columns='V3_V',inplace=True)
        elif failure=='unit':m['channels']['I1_A']['unit']='mA'
        elif failure=='location':m['channels']['terminal_V']['location']='unknown converter output'
        elif failure=='duplicate':f.loc[1,'time_s']=0
        elif failure=='gap':f.loc[2:,'time_s']+=10
        elif failure=='nonfinite':f.loc[3,'I1_A']=np.nan
        elif failure=='mapping':m['cell_order']=['P3','P17','P19','P13']
    source=fixture(tmp_path/'source',change);r,_,_=v.validate(source,tmp_path/'out')
    assert not r['valid_structure'] and r['decision']=='insufficient evidence'


def test_alignment_and_missing_calibration_are_explicit(tmp_path):
    def change(f,m):
        f['branch_clock']=f.time_s+.02;m['channels']['I1_A']['time_column']='branch_clock'
        m['channels']['I1_A']['calibration']={}
    r,_,_=v.validate(fixture(tmp_path/'source',change),tmp_path/'out')
    assert r['valid_structure'] and not r['alignment_ok']
    assert r['max_channel_skew_s']['I1_A']==pytest.approx(.02)
    assert any('Calibration provenance missing' in x for x in r['issues'])


def test_future_comparison_recovers_known_voltage_error_without_fitting(tmp_path):
    model=dict(kind='C2_rest_reference_RC',capacity_Ah=5.,parameters_ohm=[.02,.03],tau_s=20.,
        reference={'rest':[{'soc':0.,'V':3.7},{'soc':1.,'V':3.7}]})
    f=d.simulate([model]*4,[.5]*4,[0.]*4,[dict(start_s=0,end_s=3,current_A=8.)],.25,[0.]*3,[0.]*3).frame
    run=tmp_path/'run';run.mkdir();f.to_csv(run/'trajectory.csv',index=False)
    w.save(run/'configuration.json',dict(initial_soc=[.5]*4,initial_polarization_V=[0.]*4))
    r=v.compare_measurements(run,fixture(tmp_path/'source'),tmp_path/'compare')
    assert r['comparisons']['terminal_V']['bias']==pytest.approx(-.01,abs=1e-12)
    assert r['comparisons']['terminal_V']['time_rmse']==pytest.approx(.01,abs=1e-12)
    assert r['experimental_validation']=='awaiting suitable measurements'


def test_comparison_does_not_smear_a_load_jump_or_extrapolate():
    f=pd.DataFrame(dict(time_s=[0.,1.,2.],step_s=[1.,1.,0.],terminal_V=[4.,3.,3.],
        interval_end_terminal_V=[4.,3.,3.],module_current_A=[0,10,10]))
    np.testing.assert_allclose(v.prediction_at(f,[.99,1.],'terminal_V'),[4.,3.])
    np.testing.assert_allclose(v.prediction_at(f,[.99,1.],'module_current_A'),[0.,10.])
    with pytest.raises(ValueError):v.prediction_at(f,[-.1],'terminal_V')


def test_output_cannot_overwrite_frozen_models_or_original_raw_data():
    for path in ['reports/improvement_v2','reports/reference_initial_state_v1/sub','src/voltforge','data/raw']:
        with pytest.raises(ValueError):w.safe_output(path)
