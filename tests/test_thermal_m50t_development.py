"""Synthetic checks only; real test-103 replay is an explicitly separate command."""
from io import BytesIO
import json
from pathlib import Path
import sys
from zipfile import ZipFile

import h5py
import numpy as np
import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import import_thermal_m50t_development as importer


def thermal_fixture(values=None):
    if values is None:values=np.column_stack((np.arange(8),np.full((8,15),20.)))
    text='\t'.join(importer.THERMAL_COLUMNS)+'\n'+'\t'.join(['Seconds']+['(\u00b0C)']*15)+'\n'
    text+='\n'.join('\t'.join(str(v) for v in row)+'\t' for row in values)
    return ('\0'+text).encode('cp1252')


def electrical_fixture():
    lines=['BT-Lab ASCII FILE','Nb header lines : 97','Battery capacity : 1.000 Ah',
        'Initial state :','Acquisition started on : 10/20/2020 13:11:42.142',
        'Lab host : private-machine','Loaded Setting File : C:\\private\\synthetic.mps']
    lines+=['']*(96-len(lines))
    lines+=['time/s\tEcell/V\tI/mA\t\t',
        '10/20/2020 13:11:42.142\t3.5\t0\t9',
        '10/20/2020 13:12:42.142\t3.6\t1000\t8',
        '10/20/2020 13:13:42.142\t3.5\t-1000\t7',
        '10/20/2020 13:14:42.142\t3.5\t0\t6']
    return '\n'.join(lines).encode()


def matlab_fixture(tmp_path,soft=False,invalid_label=False):
    path=tmp_path/'synthetic.mat'
    with h5py.File(path,'w',userblock_size=512) as f:
        group=f.create_group('data');refs=f.create_group('#refs#')
        labels={'celltemplabels':importer.CELL_LABELS,
            'templabels':['Amb','+ve clamp',*importer.CELL_LABELS,'-ve clamp','Tab +ve','finC','finH','Tab -ve C','Tab -ve H','Ins']}
        counter=0
        for name,values in labels.items():
            label_refs=[]
            for text in values:
                counter+=1
                d=refs.create_dataset(str(counter),data=np.frombuffer(text.encode('utf-16le'),dtype='<u2')[:,None])
                d.attrs['MATLAB_class']=np.bytes_('double' if invalid_label else 'char');label_refs.append(d.ref)
            d=group.create_dataset(name,(len(values),1),dtype=h5py.ref_dtype)
            d[:,0]=label_refs;d.attrs['MATLAB_class']=np.bytes_('cell')
        ss=np.arange(90,dtype=float).reshape(15,6)+20
        summary=np.arange(1,7,dtype=float)[None,:]
        arrays={'celltemps':np.full((5,7),20.1),'SS_T':ss,'SS_Q':summary,'SS_MaxT':ss[2:3],
            'SS_CST':ss[6:7],'SS_delT':ss[2:3]-ss[6:7],'SS_CCC':summary/(ss[2:3]-ss[6:7]),
            'Qnet':summary,'Qgain':np.zeros((1,6)),'Qloss':np.zeros((1,6)),
            'AltQ':np.ones((3,6)),'AltdelT':np.ones((3,6))}
        for name,values in arrays.items():
            d=group.create_dataset(name,data=values);d.attrs['MATLAB_class']=np.bytes_('double')
        if soft:group['forbidden']=h5py.SoftLink('/data/SS_Q')
    with path.open('r+b') as stream:stream.write(b'MATLAB 7.3 MAT-file, SYNTHETIC FIXTURE')
    return path.read_bytes()


def test_thermal_preserves_16_channels_nul_and_legacy_units():
    values,meta=importer.parse_thermal(thermal_fixture())
    assert values.shape==(8,16)
    assert meta['leading_nul_bytes_removed']==1
    assert meta['encoding'].startswith('cp1252')
    assert meta['columns'][-1]=='AO027/105 Cold Junction'
    assert meta['units']==['s']+['degC']*15


def test_reordered_thermal_header_rejected_before_positional_mapping():
    raw=thermal_fixture().decode('cp1252')
    raw=raw.replace('A0080/212 Channel 1','TEMP').replace('A0080/212 Channel 2','A0080/212 Channel 1').replace('TEMP','A0080/212 Channel 2')
    with pytest.raises(ValueError,match='schema'):importer.parse_thermal(raw.encode('cp1252'))


@pytest.mark.parametrize('change',[lambda x:x.replace(b'(\xb0C)',b'(K)',1),lambda x:x.replace(b'20.0\t20.0',b'20.0\t\t20.0',1),lambda x:x+b'\n'])
def test_thermal_invalid_units_and_empty_fields_rejected(change):
    # An actual blank data row, rather than an ordinary final newline, is rejected.
    data=change(thermal_fixture())
    if data.endswith(b'\n'):data+=b'\n'
    with pytest.raises(ValueError):importer.parse_thermal(data)


def test_embedded_nul_rejected():
    with pytest.raises(ValueError,match='inside'):importer.decode_lines(b'one\x00two')


def test_numeric_garbage_rejected_without_partial_conversion():
    with pytest.raises((ValueError,DeprecationWarning)):importer.numeric_rows(['1\t2bad'],2)


def test_electrical_actual_four_fields_calendar_units_and_private_metadata():
    array,strings,meta=importer.parse_electrical(electrical_fixture())
    np.testing.assert_array_equal(array[:,0],[0,60,120,180])
    np.testing.assert_array_equal(array[:,3],[9,8,7,6])
    assert strings[0]=='10/20/2020 13:11:42.142'
    assert meta['header_lines']==97 and meta['units']==['s','V','mA',None]
    assert meta['timestamp']['timezone'] is None
    assert meta['public_header']['settings_filename_only']=='synthetic.mps'
    assert 'private-machine' not in json.dumps(meta)
    assert 'C:\\private' not in json.dumps(meta)


@pytest.mark.parametrize('before,after',[(b'I/mA',b'I/A'),(b'97',b'96'),(b'\t0\t9',b'\t0\t9\textra')])
def test_electrical_rejects_changed_header_units_or_data_width(before,after):
    with pytest.raises(ValueError):importer.parse_electrical(electrical_fixture().replace(before,after,1))


def test_matlab_labels_orientation_and_mapping(tmp_path):
    arrays,meta=importer.decode_matlab(matlab_fixture(tmp_path))
    assert arrays['celltemps'].shape==(5,7)
    assert meta['labels']['celltemplabels']==importer.CELL_LABELS
    thermal,_=importer.parse_thermal(thermal_fixture())
    check=importer.representation_checks(thermal,arrays,meta)
    assert check['mat_storage_channel_axis']==0
    assert len(check['alternatives'])==2
    arrays['celltemps']=arrays['celltemps'].T
    with pytest.raises(ValueError,match='dimensions'):importer.representation_checks(thermal,arrays,meta)


@pytest.mark.parametrize('kwargs',[{'soft':True},{'invalid_label':True}])
def test_matlab_rejects_unsupported_links_and_label_class(tmp_path,kwargs):
    with pytest.raises(ValueError):importer.decode_matlab(matlab_fixture(tmp_path,**kwargs))


def test_allowlist_denies_before_archive_inspection():
    class ForbiddenArchive:
        def getinfo(self,*args):raise AssertionError('Must not inspect a forbidden numerical member')
    for name in ('M50/M50_50SOC_20deg_cell2_test106.txt','M50/M50_75SOC_20deg_cell1_test100.mat','../'+importer.THERMAL):
        with pytest.raises(ValueError,match='allowlist'):importer.read_member(ForbiddenArchive(),name)


def test_time_quality_reports_duplicates_and_resets_without_repair():
    time=np.array([0.,1.,1.,3.,2.]);original=time.copy()
    result=importer.time_quality(time)
    assert result['duplicates']==1 and result['reversals']==1
    np.testing.assert_array_equal(time,original)
    with pytest.raises(ValueError,match='strictly'):importer.integrate(time,np.ones(5))


@pytest.mark.parametrize('method',['left','right','trapezoid'])
def test_analytical_charge_and_work_conservation(method):
    r=importer.electrical_accounting(np.array([0.,3600.,7200.]),np.full(3,4.),np.full(3,-2.))[method]
    assert r['signed_charge_Ah']==-4 and r['signed_terminal_work_Wh']==-16
    assert r['charge_split_residual_Ah']==r['work_split_residual_Wh']==0
    assert r['positive_charge_Ah']==0


def test_signed_accounting_and_endpoint_uncertainty():
    r=importer.electrical_accounting(np.array([0.,3600.,7200.]),np.full(3,4.),np.array([1.,-1.,-1.]))
    assert r['left']['signed_charge_Ah']==0
    assert r['right']['signed_charge_Ah']==-2
    assert r['trapezoid']['signed_charge_Ah']==-1
    assert r['trapezoid']['positive_charge_Ah']==.5
    assert r['trapezoid']['negative_charge_Ah']==-1.5


def test_pulse_rest_boundaries_gaps_and_censored_following_rest():
    time=np.r_[0,60,60.01+np.arange(202)*.5,220.5,280.5]
    current=np.r_[0,0,np.tile([-1000.,1000.],101),0,0]
    electrical=np.column_stack((time,np.full(len(time),4.),current,np.zeros(len(time))))
    blocks=importer.electrical_blocks(electrical)
    assert [b['kind'] for b in blocks]==['rest_candidate','bipolar_pulse_candidate','rest_candidate']
    coverage=importer.coverage_report(electrical,blocks)['pulse_rest_sequences'][0]
    assert coverage['pulse_has_recorded_rest_on_both_sides']
    assert coverage['following_rest_right_censored']
    assert not coverage['following_rest_covers_nominal_90_min_with_boundary_bracket']
    assert coverage['max_pulse_sampling_gap_s']==.5
    assert blocks[1]['outer_end_s']-blocks[1]['last_sample_s']>50


def test_short_zero_region_is_retained_not_bridged():
    e=np.column_stack((np.arange(5),np.full(5,4),[1000,1000,0,-1000,-1000],np.zeros(5)))
    blocks=importer.electrical_blocks(e)
    assert len(blocks)==3 and blocks[1]['kind']=='short_below_threshold'


def test_fixed_algebra_reports_mismatch_without_fitting(tmp_path):
    arrays,meta=importer.decode_matlab(matlab_fixture(tmp_path))
    result=importer.author_processing_checks(arrays,meta)
    assert result['relationships']['Qnet_equals_SS_Q_plus_Qgain_minus_Qloss']['max_abs_residual']==0
    assert result['relationships']['AltdelT_declared_tab_tab_insulation_order']['max_abs_residual']>0
    assert 'not independent calibration' in result['classification']


def test_import_replay_and_tamper_detection_only_exact_allowed_members(tmp_path,monkeypatch):
    archive=tmp_path/'synthetic.zip'
    with ZipFile(archive,'w') as z:
        for name,data in [(importer.THERMAL,thermal_fixture()),(importer.ELECTRICAL,electrical_fixture()),(importer.MATLAB,matlab_fixture(tmp_path))]:z.writestr(name,data)
        z.writestr('M50/M50_50SOC_20deg_cell2_test106.txt',b'MUST REMAIN UNOPENED')
    opened=[];original=ZipFile.open
    def guard(self,name,*args,**kwargs):
        if self.filename==str(archive):
            assert name in importer.ALLOW
            opened.append(name)
        return original(self,name,*args,**kwargs)
    monkeypatch.setattr(ZipFile,'open',guard)
    monkeypatch.setattr(importer,'ARCHIVE',archive)
    monkeypatch.setattr(importer,'ROOT',tmp_path)
    monkeypatch.setattr(importer,'check_sources',lambda:None)
    out=tmp_path/'tmp/synthetic_import'
    importer.import_record(out)
    result=importer.verify_import(out)
    assert opened==list(importer.ALLOW)*2
    assert result['exact_report_and_array_replay'] and result['assessment_members_opened']==0
    with pytest.raises(ValueError,match='fresh'):importer.import_record(out)
    (out/'quality.json').write_text('{}')
    with pytest.raises(ValueError,match='hash mismatch'):importer.verify_import(out)
