"""Synthetic author predictions, including missing values; no real data access."""
import csv
import hashlib
import io
import json
from pathlib import Path
import sys
from zipfile import ZipFile

import numpy as np
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import ae_p45b_author_comparison as ac
from ae_p45b_intake import AUTHOR_OUTPUTS, EXPERIMENTAL, PARAMETERS
from ae_p45b_reproduction import Table25, simulate


def fixture():
    stream=io.StringIO();writer=csv.writer(stream);writer.writerow(PARAMETERS)
    for soc in (0,1):writer.writerow([soc,4.5*(soc-1),25,3.1+soc,3+soc,.01,.005,2000,.01,10000,20,0])
    table=Table25(stream.getvalue().encode())
    source=[dict(source_line=i+2,time_s=float(i),source_current_A=-4.5,voltage_V=3.9,
        controlled_temperature_degC=25.,raw_time=str(i),current_discharge_positive_A=4.5) for i in range(4)]
    own=simulate(table,source)['rows']
    for row,our in zip(source,own):
        p,_=table.query(our['soc'])
        row.update(author_I_sim_A=-4.5,author_V_sim_V=our['predicted_voltage_V'],
            author_SOC_sim=our['soc'],author_E_OCV_V=p.ocv_discharge_V,
            author_T_sim_degC=25.,author_Q_sim_W=-4.5*our['predicted_voltage_V'])
    return table,source,own


def source_bytes(source):
    stream=io.StringIO();writer=csv.writer(stream);writer.writerow(EXPERIMENTAL+AUTHOR_OUTPUTS)
    for row in source:
        writer.writerow([row['time_s'],row['source_current_A'],row['voltage_V'],row['controlled_temperature_degC']]+[row['author_'+k] for k in AUTHOR_OUTPUTS])
    return stream.getvalue().encode()


def test_author_channels_stay_distinct_from_measurements_and_missing():
    _,source,_=fixture();source[0]['author_V_sim_V']=999
    source[1]['author_SOC_sim']=None;source[2]['author_V_sim_V']=float('nan')
    rows=ac.author_rows(source_bytes(source))
    assert rows[0]['voltage_V']==3.9 and rows[0]['author_V_sim_V']==999
    assert rows[1]['author_SOC_sim'] is None and rows[2]['author_V_sim_V'] is None
    assert rows[0]['source_current_A']==-4.5


@pytest.mark.parametrize('change',[float('inf'),'bad'])
def test_invalid_author_value_rejected(change):
    _,source,_=fixture();source[0]['author_I_sim_A']=change
    with pytest.raises(ValueError):ac.author_rows(source_bytes(source))


def test_matching_predictions_and_decomposition_identity():
    table,source,own=fixture();rows,summary=ac.compare(table,source,own)
    assert summary['voltage_comparisons']['ours_minus_author_mV']['all_available']['max_abs']==0
    assert summary['voltage_decomposition']['decomposition_closure_mV']['max_abs']<1e-10
    assert summary['state_diagnostics']['author_power_minus_current_times_voltage']['max_abs']==0
    assert summary['requirement_status']=='requirement not configured'
    assert rows[0]['decomposition_status'].startswith('defined')


def test_reference_and_polarization_differences_are_not_fitted_away():
    table,source,own=fixture()
    for row in source:
        row['author_E_OCV_V']-=.01
        row['author_V_sim_V']-=.03
    rows,summary=ac.compare(table,source,own)
    for row in rows:
        assert row['reference_difference_mV']==pytest.approx(10)
        assert row['ohmic_difference_mV']==0
        assert row['polarization_difference_mV']==pytest.approx(20)
        assert row['decomposition_closure_mV']==pytest.approx(0,abs=1e-10)
    assert summary['parameters_or_initial_states_changed'] is False


@pytest.mark.parametrize('field,value',[('time_s',.1),('source_line',99),('voltage_V',4.2),('source_current_A',-3)])
def test_alignment_and_source_edits_rejected(field,value):
    table,source,own=fixture();own[0][field]=value
    with pytest.raises(ValueError,match='mismatch'):ac.compare(table,source,own)


def test_missing_author_voltage_keeps_our_full_and_shared_masks_separate():
    table,source,own=fixture();source[1]['author_V_sim_V']=None
    rows,summary=ac.compare(table,source,own)
    comparisons=summary['voltage_comparisons']
    assert comparisons['ours_minus_measured_mV']['all_available']['samples']==4
    assert comparisons['ours_minus_measured_mV']['identical_common_samples']['samples']==3
    assert comparisons['author_minus_measured_mV']['all_available']['covered_duration_s']==1
    assert rows[1]['decomposition_status']=='missing author state or output'


@pytest.mark.parametrize('field,value',[('author_SOC_sim',-.1),('author_T_sim_degC',40)])
def test_unsupported_reference_not_extended(field,value):
    table,source,own=fixture();source[1][field]=value
    rows,summary=ac.compare(table,source,own)
    assert rows[1]['reference_difference_mV'] is None
    assert summary['voltage_comparisons']['ours_minus_author_mV']['all_available']['samples']==4


def test_time_weights_do_not_bridge_missing_points_or_gaps():
    result=ac.stats([0,1,4],[1,2,3],'mV')
    assert result['time_rmse']==pytest.approx(np.sqrt(22/4))
    assert ac.stats([0,1,4],[1,None,3],'mV')['time_rmse'] is None
    assert ac.stats([0,1,2,100,101],[1]*5,'mV')['covered_duration_s']==3
    assert ac.integrate([0,1,2,100,101],[-4.5]*5,1,'left')[3:]==[None,None]


def test_soc_integrals_preserve_own_origins_and_unknown_intervals():
    result=ac.integrate([0,1,2],[-4.5,0,4.5],.9,'linear')
    assert result[-1]==pytest.approx(.9)
    assert ac.integrate([0,1,2],[-4.5,None,4.5],.9,'left')[-1] is None
    assert ac.integrate([0,1],[-4.5,-4.5],None,'left')==[None,None]


def test_loader_reads_only_allocated_member_and_export_is_complete(tmp_path,monkeypatch):
    table,source,own=fixture()
    (tmp_path/'configs').mkdir();(tmp_path/'scripts').mkdir()
    for name in ('ae_p45b_author_comparison.py','ae_p45b_reproduction.py','ae_p45b_equations.py','ae_p45b_intake.py'):
        (tmp_path/'scripts'/name).write_text('synthetic provenance fixture')
    raw=source_bytes(source)
    archive=tmp_path/'molicel_p45b_data.zip'
    with ZipFile(archive,'w') as z:
        z.writestr(ac.MEMBER,raw);z.writestr('PROTECTED.csv',b'\xffUNOPENED')
    param=tmp_path/ac.TABLE_NAME;param.write_bytes(b'synthetic table placeholder')
    saved=tmp_path/'ours.csv'
    stream=io.StringIO();writer=csv.DictWriter(stream,fieldnames=list(own[0]));writer.writeheader();writer.writerows(own)
    saved.write_text(stream.getvalue())
    lock=dict(allowed_member=ac.MEMBER,member_sha256=hashlib.sha256(raw).hexdigest(),own_prediction='ours.csv',
        preaccess_files={'molicel_p45b_data.zip':ac.sha(archive),ac.TABLE_NAME:ac.sha(param),'ours.csv':ac.sha(saved)})
    (tmp_path/'configs/ae_p45b_author_comparison_v1.json').write_text(json.dumps(lock))
    monkeypatch.setattr(ac,'ROOT',tmp_path);monkeypatch.setattr(ac,'Table25',lambda _:table)
    opened=[];original=ZipFile.read
    def tracked(self,name,*args,**kwargs):
        opened.append(name);return original(self,name,*args,**kwargs)
    monkeypatch.setattr(ZipFile,'read',tracked)
    out=tmp_path/'tmp/output';monkeypatch.setattr(sys,'argv',['compare','--out',str(out)])
    ac.main()
    assert opened==[ac.MEMBER]
    summary=json.loads((out/'summary.json').read_text())
    assert summary['rows']==4 and summary['unused_archive_members']==50
    for name,expected in json.loads((out/'manifest.json').read_text()).items():
        assert ac.sha(out/name)==expected
    assert (out/'author_voltage_comparison.png').stat().st_size>1000
    with pytest.raises(SystemExit,match='new directory'):ac.main()
    saved.write_text('changed')
    with pytest.raises(ValueError,match='mismatch'):ac.load_sources()
    assert opened==[ac.MEMBER]
