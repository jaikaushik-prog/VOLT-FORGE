"""Synthetic tests; never open a real P45B outcome or validation workbook."""
import io
from pathlib import Path
import sys
import warnings
from zipfile import ZipFile

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import ae_p45b_intake as ae


def csv_bytes(columns=ae.EXPERIMENTAL,values=None):
    return (','.join(columns)+'\n'+('\n'.join(values) if values else '0,-4.5,3.9,25\n1,-4.5,3.89,25')+'\n').encode()


def test_archive_headers_only_even_with_undecodable_outcomes(tmp_path):
    archive=tmp_path/'synthetic.zip'
    with ZipFile(archive,'w') as z:
        for suffix in ['', '-charge']:
            z.writestr(f'MOLICEL_P45B_025degC_1C_Ch{suffix}.csv',(','.join(ae.EXPERIMENTAL+ae.AUTHOR_OUTPUTS)+'\n').encode()+b'\xff\xfeUNOPENED')
    result=ae.archive_inventory(archive)
    assert result['file_count']==2 and result['family_count']==1
    assert result['outcomes_decoded']==0 and result['author_simulation_rows_decoded']==0
    assert result['families'][0]['access']=='protected_unopened'
    assert len(result['families'][0]['members'])==2


@pytest.mark.parametrize('payload',[b't,t\n',b't,,v\n',b'a'*65537+b'\n',b't,v'],ids=['duplicate','empty','oversized','unterminated'])
def test_header_rejects_ambiguous_or_incomplete_values(payload):
    with pytest.raises(ValueError):ae.header(io.BytesIO(payload))


@pytest.mark.parametrize('name',['../MOLICEL_P45B_025degC_1C_Ch.csv','MOLICEL_P45B_030degC_1C_Ch.csv','unknown.csv'])
def test_unknown_or_unsafe_member_rejected(tmp_path,name):
    archive=tmp_path/'synthetic.zip'
    with ZipFile(archive,'w') as z:z.writestr(name,csv_bytes())
    with pytest.raises(ValueError):ae.archive_inventory(archive)


def test_bad_archive_identity_rejected_before_header_decode(tmp_path,monkeypatch):
    archive=tmp_path/'synthetic.zip';archive.write_bytes(b'not a zip')
    monkeypatch.setattr(ae,'header',lambda *_:pytest.fail('Decoded unverified header'))
    with pytest.raises(ValueError,match='published release'):ae.archive_inventory(archive,'bad')


def test_duplicate_members_and_orphan_charge_variant_rejected(tmp_path):
    archive=tmp_path/'synthetic.zip'
    name='MOLICEL_P45B_025degC_1C_Ch-charge.csv'
    with ZipFile(archive,'w') as z:z.writestr(name,csv_bytes(ae.EXPERIMENTAL+ae.AUTHOR_OUTPUTS))
    with pytest.raises(ValueError,match='corresponding base'):ae.archive_inventory(archive)
    with warnings.catch_warnings():
        warnings.simplefilter('ignore',UserWarning)
        with ZipFile(archive,'a') as z:z.writestr(name,csv_bytes())
    with pytest.raises(ValueError,match='Duplicate'):ae.archive_inventory(archive)


def test_filename_allocations_do_not_open_outcomes():
    assert ae.record_metadata('MOLICEL_P45B_025degC_GITT_Dch.csv')['proposed_allocation']=='development_candidate'
    assert ae.record_metadata('MOLICEL_P45B_025degC_WLTP.csv')['proposed_allocation']=='assessment_candidate'
    assert ae.record_metadata('MOLICEL_P45B_040degC_1C_Ch.csv')['proposed_allocation']=='reserved_temperature_transfer'
    assert ae.record_metadata('MOLICEL_P45B_025degC_3C_Ch-charge.csv')['access']=='protected_unopened'


def test_source_polarity_units_and_line_numbers_preserved():
    result=ae.experimental_rows(csv_bytes(values=['0,-4.5,3.9,25','1,2,4.1,25']))
    assert result['rows'][0]['source_current_A']==-4.5
    assert result['rows'][0]['current_discharge_positive_A']==4.5
    assert result['rows'][1]['current_discharge_positive_A']==-2
    assert result['rows'][1]['source_line']==3 and result['rows'][1]['time_s']==1
    assert result['units']['controlled_temperature_degC']=='degC'
    assert result['initial_soc'] is None and result['initial_polarization'] is None


def test_author_predictions_cannot_supply_experimental_values():
    # A radically different simulated current/SOC/voltage must never enter inputs.
    raw=csv_bytes(ae.EXPERIMENTAL+ae.AUTHOR_OUTPUTS,['0,-4.5,3.9,25,999,999,999,999,999,999'])
    result=ae.experimental_rows(raw)
    assert result['rows'][0]['source_current_A']==-4.5
    assert result['rows'][0]['voltage_V']==3.9
    assert result['excluded_author_fields']==ae.AUTHOR_OUTPUTS
    assert set(result['rows'][0])=={'source_line','raw_time','time_s','source_current_A','current_discharge_positive_A','voltage_V','controlled_temperature_degC'}
    assert ae.experimental_rows(raw.replace(b'999',b'unused'))['rows']==result['rows']
    with pytest.raises(ValueError):ae.experimental_rows(raw.replace(b'3.9',b''))


@pytest.mark.parametrize('values',[
    ['0,-4.5,NaN,25'],['0,-4.5,3.9,inf'],['0,-4.5,3.9,25','0,-4.5,3.9,25'],
    ['1,-4.5,3.9,25','0,-4.5,3.9,25'],['0,,3.9,25'],['0,-4.5,3.9'],
],ids=['nan','infinite','duplicate-time','reversed-time','missing','ragged'])
def test_invalid_experimental_rows_are_not_repaired(values):
    with pytest.raises(ValueError):ae.experimental_rows(csv_bytes(values=values))


def test_simulated_only_schema_is_rejected():
    with pytest.raises(ValueError):ae.experimental_rows(csv_bytes(['t_s','I_sim_A','V_sim_V','T_sim_degC']))
