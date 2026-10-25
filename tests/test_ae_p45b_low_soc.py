"""Synthetic checks for charge coordinates, finite rests and source allocation."""
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
import ae_p45b_low_soc as low
from ae_p45b_intake import EXPERIMENTAL, PARAMETERS
from ae_p45b_reproduction import Table25


def table_bytes():
    s=io.StringIO();w=csv.writer(s);w.writerow(PARAMETERS)
    for soc in (0,1):w.writerow([soc,4.5*(soc-1),25,3.1+soc,3+soc,.01,.005,2000,.01,10000,20,0])
    return s.getvalue().encode()


def records(times,currents,voltages=None):
    return [dict(time_s=float(t),source_current_A=float(i),voltage_V=float(voltages[n] if voltages is not None else 3.9),
        controlled_temperature_degC=25.,source_line=n+2,raw_time=str(t),current_discharge_positive_A=-float(i)) for n,(t,i) in enumerate(zip(times,currents))]


def test_known_current_integrals_and_no_soc_clipping():
    rows,summary=low.annotate(Table25(table_bytes()),records([0,60,120],[4.5,4.5,-4.5]))
    assert rows[1]['nominal_soc_linear']==pytest.approx(1+1/60)
    assert rows[1]['reference_discharge_V'] is None
    assert rows[2]['nominal_soc_linear']==pytest.approx(rows[1]['nominal_soc_linear'])
    assert rows[2]['nominal_soc_left']==pytest.approx(1+1/30)
    assert summary['possible_gaps']==0


def test_possible_gap_stops_soc_without_erasing_later_measurements():
    rows,summary=low.annotate(Table25(table_bytes()),records([0,1,2,500,501],[-.15]*5))
    assert summary['possible_gaps']==1 and rows[3]['nominal_soc_linear'] is None
    assert rows[4]['voltage_V']==3.9 and rows[4]['nominal_soc_linear'] is None
    segments,_=low.segments(Table25(table_bytes()),rows)
    assert len(segments)==2 and segments[1]['gap_before']


def test_finite_rest_window_slope_and_sample_limited_transition():
    t=[0,1,2]+list(range(3,604,30))+[603.5]
    currents=[-4.5]*3+[0.]*(len(t)-3)
    voltage=[3.8]*3+[3.9+.00001*(x-3) for x in t[3:]]
    rows,_=low.annotate(Table25(table_bytes()),records(t,currents,voltage))
    segments,pairs=low.segments(Table25(table_bytes()),rows)
    rest=segments[1]
    assert rest['duration_s']==600.5 and rest['late_rest_slope_mV_per_min']==pytest.approx(.6)
    assert pairs[0]['apparent_transition_resistance_Ohm']==pytest.approx(.1/4.5)
    assert pairs[0]['cross_record_endpoint_eligible']
    assert pairs[0]['table_steady_drop_scale_mV']==pytest.approx(4.5*.025*1000)
    assert pairs[0]['table_tau1_s']==10 and pairs[0]['table_tau2_s']==100


def test_short_rest_is_not_an_equilibrium_point_or_long_rest_overlap():
    rows,_=low.annotate(Table25(table_bytes()),records([0,1,2,3],[-4.5,-4.5,0,0]))
    segments,pairs=low.segments(Table25(table_bytes()),rows)
    assert segments[1]['late_rest_slope_mV_per_min'] is None
    assert pairs[0]['cross_record_endpoint_eligible'] is False


def test_slow_transition_not_reported_as_ohmic_resistance():
    rows,_=low.annotate(Table25(table_bytes()),records([0,1,10,11],[-4.5,-4.5,0,0]))
    _,pairs=low.segments(Table25(table_bytes()),rows)
    assert pairs[0]['transition_sample_separation_s']==9
    assert pairs[0]['apparent_transition_resistance_Ohm'] is None


def test_nonuniform_reference_metrics_and_masks():
    rows=[dict(time_s=t,reference_minus_measured_mV=e,gap_before=False) for t,e in [(0,1),(1,2),(4,3)]]
    result=low.error_stats(rows,[True]*3)
    assert result['sample_rmse_mV']==pytest.approx(np.sqrt(14/3))
    assert result['time_rmse_mV']==pytest.approx(np.sqrt(22/4))
    assert low.error_stats(rows,[True,False,True])['time_rmse_mV'] is None
    rows[2]['gap_before']=True
    assert low.error_stats(rows,[True]*3)['covered_duration_s']==1


def test_overlap_does_not_extend_bridge_missing_points_or_hide_reversal():
    points=[(1.,4.,2),(.8,3.8,3),None,(.4,3.4,5),(.2,3.2,6)]
    result=low.interpolate_adjacent(points,[1.1,.9,.6,.3])
    assert result[0]['value_V'] is None and result[2]['value_V'] is None
    assert result[1]['value_V']==pytest.approx(3.9)
    assert result[3]['source_line_a']==5 and result[3]['source_line_b']==6
    repeated=[(1.,4.,2),(.5,3.5,3),(1.,4.1,4),(.5,3.6,5)]
    assert low.interpolate_adjacent(repeated,[.75])[0]['status'].startswith('ambiguous')


def test_cross_record_omitted_pair_does_not_create_false_overlap():
    pairs=[dict(cross_record_endpoint_eligible=True,contiguous_with_previous_pair=False,rest_endpoint_soc=z,late_rest_median_V=v,rest_last_source_line=i)
        for z,v,i in [(1.,4.,2),(.5,3.5,5)]]
    co30=[dict(phase='discharge',nominal_soc_linear=z,voltage_V=v,source_line=i,gap_before=False) for z,v,i in [(1.,4.,2),(.5,3.5,3)]]
    own=[dict(soc=.75,voltage_V=3.6,predicted_voltage_V=3.65,time_s=0,source_line=2)]
    cross=low.cross_record(co30,pairs,own)[0]
    assert cross['gitt_late_rest_value_V'] is None
    assert cross['co30_loaded_value_V']==pytest.approx(3.75)


@pytest.mark.parametrize('times',[[0,0],[1,0],[0,float('nan')]])
def test_invalid_times_not_repaired(times):
    with pytest.raises(ValueError):low.annotate(Table25(table_bytes()),records(times,[-.15]*2))


def test_cli_reads_only_two_allocated_records_and_preserves_outputs(tmp_path,monkeypatch):
    (tmp_path/'configs').mkdir();(tmp_path/'scripts').mkdir()
    for name in ('ae_p45b_low_soc.py','ae_p45b_reproduction.py','ae_p45b_intake.py'):
        (tmp_path/'scripts'/name).write_text('synthetic implementation fixture')
    raw={}
    for key in low.MEMBERS:
        s=io.StringIO();w=csv.writer(s);w.writerow(EXPERIMENTAL)
        if key=='co30':
            for t in range(0,901,60):w.writerow([t,-.15,4-t/900,25])
        else:
            for t in range(901):w.writerow([t,-4.5 if t<100 or 800<=t<810 else 0,3.8 if t<100 or 800<=t<810 else 3.95,25])
        raw[key]=s.getvalue().encode()
    archive=tmp_path/'molicel_p45b_data.zip'
    with ZipFile(archive,'w') as z:
        for key,name in low.MEMBERS.items():z.writestr(name,raw[key])
        z.writestr('PROTECTED.csv',b'\xffUNOPENED')
    parameter=tmp_path/low.TABLE_NAME;parameter.write_bytes(table_bytes())
    own=tmp_path/'own.csv';own.write_text('source_line,time_s,soc,voltage_V,predicted_voltage_V\n2,0,1,4,4\n3,1,0.99,3.9,3.91\n')
    lock=dict(allowed_members=low.MEMBERS,member_sha256={k:hashlib.sha256(v).hexdigest() for k,v in raw.items()},
        oneC_saved_trace='own.csv',preaccess_files={'molicel_p45b_data.zip':low.sha(archive),low.TABLE_NAME:low.sha(parameter),'own.csv':low.sha(own)})
    (tmp_path/'configs/ae_p45b_low_soc_v1.json').write_text(json.dumps(lock))
    monkeypatch.setattr(low,'ROOT',tmp_path)
    opened=[];original=ZipFile.read
    def tracked(self,name,*args,**kwargs):opened.append(name);return original(self,name,*args,**kwargs)
    monkeypatch.setattr(ZipFile,'read',tracked)
    out=tmp_path/'tmp/run';monkeypatch.setattr(sys,'argv',['diagnose','--out',str(out)])
    low.main()
    assert opened==list(low.MEMBERS.values())
    summary=json.loads((out/'summary.json').read_text())
    assert not summary['late_rest_is_equilibrium_OCV'] and summary['remaining_unopened_members']==48
    for name,expected in json.loads((out/'manifest.json').read_text()).items():assert low.sha(out/name)==expected
    with pytest.raises(SystemExit):low.main()
    own.write_text('changed')
    with pytest.raises(ValueError,match='mismatch'):low.load_sources()
    assert opened==list(low.MEMBERS.values())
