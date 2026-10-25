"""Synthetic-only tests of interpolation, sequencing and comparison bookkeeping."""
import csv
from dataclasses import asdict
import hashlib
import io
import json
from pathlib import Path
import sys
from zipfile import ZipFile

import numpy as np
import pytest
from scipy.integrate import solve_ivp

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import ae_p45b_reproduction as rep
from ae_p45b_equations import Parameters, State, terminal_voltage
from ae_p45b_intake import EXPERIMENTAL, AUTHOR_OUTPUTS, PARAMETERS


def table_bytes(knots=(0., 0.5, 1.), temperatures=(25,), change=None):
    stream=io.StringIO(newline='')
    writer=csv.writer(stream); writer.writerow(PARAMETERS)
    for temp in temperatures:
        for soc in reversed(knots):
            row=dict(zip(PARAMETERS,[soc,4.5*(soc-1),temp,3.1+soc,3+soc,
                .01,.005+.005*soc,2000.,.02,5000.,20.,0.]))
            if change: row.update(change)
            writer.writerow([row[k] for k in PARAMETERS])
    return stream.getvalue().encode()


def records(times, currents=None, voltage=3.8):
    currents=currents if currents is not None else [-4.5]*len(times)
    return [dict(time_s=float(t),source_current_A=float(i),voltage_V=voltage,
        controlled_temperature_degC=25.,source_line=n+2) for n,(t,i) in enumerate(zip(times,currents))]


def test_lookup_exact_and_linear_with_source_rows():
    table=rep.Table25(table_bytes())
    p,flags=table.query(.25)
    assert not flags
    assert p.ocv_discharge_V==3.25 and p.r1_Ohm==pytest.approx(.00625)
    assert table.query(1)[0].ocv_discharge_V==4
    assert table.audit['active_source_lines']==[4,3,2]
    assert table.audit['max_abs_Q_Ah_minus_4p5_times_SOC_minus_1']==0
    with pytest.raises(ValueError,match='Unsupported temperature'):table.query(.5,temperature_degC=40)
    with pytest.raises(ValueError,match='outside reference'):table.query(1.001)
    assert table.query(1.001,'nearest')[1]


@pytest.mark.parametrize('kind',['duplicate','missing25','nonfinite','negative','ragged'])
def test_malformed_table_is_not_repaired(kind):
    raw=table_bytes()
    if kind=='duplicate': raw+=raw.splitlines(keepends=True)[1]
    if kind=='missing25':raw=table_bytes(temperatures=(40,))
    if kind=='nonfinite':raw=table_bytes(change={'R_R0_Ohm':float('nan')})
    if kind=='negative':raw=table_bytes(change={'R_R1_Ohm':-1})
    if kind=='ragged':raw+=b'0,0,25\n'
    with pytest.raises(ValueError):rep.Table25(raw)


def test_voltage_transition_is_instant_but_state_has_left_integral():
    rows=records([0,1,2],[-4.5,0,4.5])
    result=rep.simulate(rep.Table25(table_bytes()),rows)
    assert result['rows'][1]['soc']==pytest.approx(1-4.5/16200)
    assert result['rows'][2]['soc']==pytest.approx(result['rows'][1]['soc'])
    assert result['rows'][0]['predicted_voltage_V']==pytest.approx(4-.045)
    assert result['rows'][1]['v1_V']<0
    assert result['rows'][2]['v1_V']>result['rows'][1]['v1_V']


def test_linear_current_exact_coulomb_integral():
    table=rep.Table25(table_bytes())
    rows=records([0,10],[-4.5,4.5])
    left=rep.simulate(table,rows)
    linear=rep.simulate(table,rows,current_mode='linear')
    assert left['rows'][-1]['soc']==pytest.approx(1-45/16200)
    assert linear['rows'][-1]['soc']==pytest.approx(1,abs=1e-13)


def test_reference_stop_keeps_unpredicted_rows_and_does_not_restart():
    table=rep.Table25(table_bytes(knots=(.999,1)))
    rows=records([0,5,10],[-4.5,-4.5,4.5])
    strict=rep.simulate(table,rows)
    assert strict['stopped'] and strict['rows'][1]['predicted_voltage_V'] is None
    assert len(strict['rows'])==3 and strict['rows'][2]['predicted_voltage_V'] is None
    extended=rep.simulate(table,rows,outside='nearest')
    assert extended['rows'][1]['soc']<.999
    assert extended['rows'][1]['reference_extended']
    assert extended['rows'][2]['extension_affected_state']


def test_gaps_stop_without_interpolating_or_sorting():
    table=rep.Table25(table_bytes())
    result=rep.simulate(table,records([0,1,2,100,101]))
    assert result['stopped']['reason']=='acquisition_gap'
    assert len(result['rows'])==5 and result['rows'][3]['soc'] is None
    with pytest.raises(ValueError):rep.simulate(table,records([0,0]))


def test_nonuniform_metrics_and_group_adjacency():
    rows=[dict(time_s=t,residual_V=e) for t,e in [(0,1),(1,2),(4,3),(5,None)]]
    result=rep.metrics(rows)
    assert result['sample_rmse_mV']==pytest.approx(1000*np.sqrt(14/3))
    assert result['time_rmse_mV']==pytest.approx(1000*np.sqrt((.5*1+2*4+1.5*9)/4))
    assert result['time_bias_mV']==pytest.approx(2250)
    assert result['covered_duration_s']==4
    grouped=rep.metrics(rows,[True,False,True,False])
    assert grouped['samples']==2 and grouped['time_rmse_mV'] is None
    assert rep.metrics(rows,[False]*4)['sample_rmse_mV'] is None


def test_protocol_cutoff_not_used_to_hide_full_record_error():
    rows=records([0,1,2])
    result=rep.simulate(rep.Table25(table_bytes()),rows)
    result['rows'][1]['voltage_V']=2.4
    result['rows'][1]['residual_V']=result['rows'][1]['predicted_voltage_V']-2.4
    summary=rep.summarize(result)
    assert summary['full_available_interval']['samples']==3
    assert summary['common_pre_protocol_cutoff']['samples']==1
    assert not summary['protocol_cutoff_is_application_requirement']
    assert summary['requirement_status']=='requirement not configured'


def test_variable_parameter_step_converges_to_independent_ode():
    table=rep.Table25(table_bytes())
    rows=records(list(range(61)))
    coarse=rep.simulate(table,rows,dt_s=.25)['rows'][-1]
    fine=rep.simulate(table,rows,dt_s=.0625)['rows'][-1]
    def derivative(t,y):
        soc,h,v1,v2=y
        r1=.005+.005*soc
        return [-4.5/16200,20*4.5/16200*(-1-h),(-4.5*r1-v1)/(r1*2000),(-4.5*.02-v2)/100]
    exact=solve_ivp(derivative,[0,60],[1,-1,0,0],rtol=1e-11,atol=1e-13).y[:,-1]
    exact_voltage=3+exact[0]-.045+exact[2]+exact[3]
    coarse_error=abs(coarse['predicted_voltage_V']-exact_voltage)
    fine_error=abs(fine['predicted_voltage_V']-exact_voltage)
    assert fine_error<coarse_error/3
    assert fine_error<1e-6


def test_only_allocated_member_read_and_author_values_unused(tmp_path,monkeypatch):
    (tmp_path/'configs').mkdir()
    param=tmp_path/rep.TABLE_NAME;param.write_bytes(table_bytes())
    data=(','.join(EXPERIMENTAL+AUTHOR_OUTPUTS)+'\n0,-4.5,4,25,'+','.join(['not-a-number']*6)+'\n1,-4.5,3.99,25,'+','.join(['not-a-number']*6)+'\n').encode()
    archive=tmp_path/'molicel_p45b_data.zip'
    with ZipFile(archive,'w') as z:
        z.writestr(rep.MEMBER,data)
        z.writestr('PROTECTED.csv',b'\xffDO NOT DECODE')
    lock=dict(preaccess_files={rep.TABLE_NAME:rep.sha(param),'molicel_p45b_data.zip':rep.sha(archive)},
        allowed_measurement_member=rep.MEMBER,allowed_parameter_file=rep.TABLE_NAME,
        member_sha256=hashlib.sha256(data).hexdigest())
    (tmp_path/'configs/ae_p45b_reproduction_v1.json').write_text(json.dumps(lock))
    monkeypatch.setattr(rep,'ROOT',tmp_path)
    opened=[]
    original=ZipFile.read
    def read_one(self,name,*args,**kwargs):
        opened.append(name)
        return original(self,name,*args,**kwargs)
    monkeypatch.setattr(ZipFile,'read',read_one)
    table,source,_=rep.load_allowed_sources()
    assert opened==[rep.MEMBER]
    assert source['rows'][0]['voltage_V']==4
    assert source['initial_soc'] is None
    param.write_bytes(b'changed')
    with pytest.raises(ValueError,match='hash mismatch'):rep.load_allowed_sources()
    assert opened==[rep.MEMBER]
