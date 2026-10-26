"""Synthetic fixtures: reservation, metadata isolation and legacy-format handling."""
import copy
from io import BytesIO
import json
from pathlib import Path
import sys
from zipfile import ZipFile, ZipInfo

import h5py
import numpy as np
import pytest
from scipy.io import savemat

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import intake_thermal_m50t as intake
import probe_thermal_m50t_schema as probe


def fixture_members():
    members = {intake.DOCUMENT: b'Synthetic documentation, not real measurements.'}
    for cell, test, soc in [(1, 100, 75), (1, 103, 50), (2, 106, 50)]:
        stem = f'M50_{soc}SOC_20deg_cell{cell}_test{test}'
        members[f'M50/{stem}.txt'] = b'FORBIDDEN thermal payload'
        members[f'M50/{stem}.mat'] = b'FORBIDDEN processed payload'
        electrical = stem.replace('_20deg', '') if test == 100 else stem
        members[f'M50/Electrical/{electrical}_CF8.txt'] = b'FORBIDDEN electrical payload'
    return members


def archive(tmp_path, members=None):
    path = tmp_path / 'fixture.zip'
    with ZipFile(path, 'w') as z:
        for name, body in (members or fixture_members()).items():
            z.writestr(name, body)
    return path


def policy():
    value = json.loads(intake.POLICY.read_text())
    value['unused_development_reserve'] = ['cell_1_test_100']
    value['assessment_reserve'] = ['cell_2_test_106']
    return value


def test_inventory_opens_only_document_and_keeps_representations_together(tmp_path, monkeypatch):
    path = archive(tmp_path)
    original, opened = ZipFile.open, []
    def guarded(self, name, *args, **kwargs):
        assert name == intake.DOCUMENT, 'Numerical payload must never be opened'
        opened.append(name)
        return original(self, name, *args, **kwargs)
    monkeypatch.setattr(ZipFile, 'open', guarded)
    result = intake.inspect_archive(path)
    allocated = intake.assign_allocation(result, policy())
    assert opened == [intake.DOCUMENT]
    assert len(result['families']) == 3
    assert sum(len(f['members']) for f in allocated) == 9
    assert result['measurement_payloads_opened'] == 0
    missing = next(r for r in result['members'] if r['name'].endswith('test100_CF8.txt'))
    assert missing['nominal_temperature_degC'] is None
    assert result['families'][0]['metadata_flags']
    assert allocated[-1]['allocation'] == 'assessment_reserve'
    assert all(f['payload_access'] == 'unopened' for f in allocated)


@pytest.mark.parametrize('change', ['missing', 'duplicate_role', 'soc_conflict'])
def test_rejects_incomplete_duplicate_and_conflicting_families(tmp_path, change):
    members = fixture_members()
    key = 'M50/M50_50SOC_20deg_cell1_test103.mat'
    if change == 'missing':del members[key]
    elif change == 'duplicate_role':members['M50/Electrical/M50_50SOC_20deg_cell1_test103_CC3.txt'] = b'bad'
    else:members[key.replace('50SOC', '25SOC')] = members.pop(key)
    with pytest.raises(ValueError):intake.inspect_archive(archive(tmp_path, members))


@pytest.mark.parametrize('name', ['../secret.txt', '/M50/secret.txt', 'M50\\secret.txt',
                                   'C:/secret.txt', 'M50/unknown.bin', 'M50/Extra/'])
def test_rejects_unsafe_or_unknown_members(tmp_path, name):
    members = fixture_members(); members[name] = b'not opened'
    with pytest.raises(ValueError):intake.inspect_archive(archive(tmp_path, members))


def test_rejects_case_collisions_and_symlinks(tmp_path):
    path = archive(tmp_path)
    with ZipFile(path, 'a') as z:z.writestr(intake.DOCUMENT.upper(), 'ambiguous')
    with pytest.raises(ValueError):intake.inspect_archive(path)
    path = archive(tmp_path)
    info = ZipInfo('M50/link'); info.create_system = 3; info.external_attr = 0o120777 << 16
    with ZipFile(path, 'a') as z:z.writestr(info, 'elsewhere')
    with pytest.raises(ValueError):intake.inspect_archive(path)


@pytest.mark.parametrize('change', ['overlap', 'omitted', 'unknown', 'cross_specimen', 'fit', 'open', 'candidate'])
def test_allocation_cannot_leak_or_drop_families(tmp_path, change):
    result = intake.inspect_archive(archive(tmp_path)); declaration = policy()
    if change == 'overlap':declaration['assessment_reserve'].append('cell_1_test_103')
    elif change == 'omitted':declaration['assessment_reserve'] = []
    elif change == 'unknown':declaration['assessment_reserve'].append('cell_2_test_999')
    elif change == 'cross_specimen':
        declaration['unused_development_reserve'], declaration['assessment_reserve'] = declaration['assessment_reserve'], declaration['unused_development_reserve']
    elif change == 'fit':declaration['fitting_authorized_by_this_procedure'] = True
    elif change == 'open':declaration['assessment_opening_authorized'] = True
    else:
        declaration['development_candidate'], declaration['unused_development_reserve'] = declaration['unused_development_reserve'], declaration['development_candidate']
    with pytest.raises(ValueError):intake.assign_allocation(result, declaration)


def test_probe_denies_reserved_and_unallocated_members_before_any_read():
    class NeverOpen:
        def open(self, name):raise AssertionError('Must reject before touching ZIP')
    for name in ['M50/M50_50SOC_20deg_cell2_test106.mat',
                 'M50/M50_50SOC_10deg_cell1_test104.txt', '../secret']:
        with pytest.raises(ValueError):probe.read_allowed(NeverOpen(), name)


def test_leading_nul_numeric_row_redacted_and_units_decoded():
    data = b'Time\tTemperature\r\n\x00Seconds\t( \xb0C )\r\n\x000\t987.654321\r\n1\t-123.456789\r\n'
    result = probe.text_schema(data)
    assert len(result['nonnumeric_leading_lines']) == 2
    assert len(result['numeric_leading_rows_redacted']) == 2
    assert result['nonnumeric_leading_lines'][1]['text'] == 'Seconds\t( \u00b0C )'
    assert '987.654321' not in json.dumps(result)
    assert '-123.456789' not in json.dumps(result)
    assert result['leading_nul_lines'] == 2


def test_probe_prefix_line_limit_and_nonfinite_redaction():
    result = probe.text_schema(b'NaN\tInf\n' * 80)
    assert result['lines_inspected'] == 64
    assert len(result['numeric_leading_rows_redacted']) == 64
    assert not result['nonnumeric_leading_lines']
    assert result['numeric_leading_rows_redacted'][0]['token_types'] == ['nonfinite_number'] * 2


def test_pre_v73_mat_schema_contains_no_values():
    stream = BytesIO(); savemat(stream, {'temperature': np.full((2, 3), 987.654321)})
    result = probe.matlab_schema(stream.getvalue())
    assert result['mat_variables'] == [dict(name='temperature', shape=[2, 3], matlab_class='double')]
    assert '987.654321' not in json.dumps(result)


def hdf_fixture(tmp_path, link=None):
    path = tmp_path / 'synthetic.mat'
    with h5py.File(path, 'w', userblock_size=512) as f:
        d = f.create_dataset('data/temperature', data=np.full((2, 3), 987.654321))
        d.attrs['MATLAB_class'] = np.bytes_('double')
        if link == 'soft':f['soft'] = h5py.SoftLink('/data')
        if link == 'external':f['outside'] = h5py.ExternalLink('DO_NOT_OPEN.h5', '/data')
        if link == 'cycle':f['data']['cycle'] = f['data']
    body = bytearray(path.read_bytes()); header = b'MATLAB 7.3 MAT-file, synthetic fixture'
    body[:len(header)] = header
    return bytes(body)


def test_hdf_schema_never_indexes_dataset_values(tmp_path, monkeypatch):
    data = hdf_fixture(tmp_path, 'cycle')
    def forbidden(*args, **kwargs):raise AssertionError('Numerical dataset read')
    monkeypatch.setattr(h5py.Dataset, '__getitem__', forbidden)
    result = probe.matlab_schema(data)
    assert result['dataset_values_read'] is False
    row = next(r for r in result['objects'] if r['name'] == '/data/temperature')
    assert row['shape'] == [2, 3] and row['matlab_class'] == 'double'
    assert '987.654321' not in json.dumps(result)


@pytest.mark.parametrize('link', ['soft', 'external'])
def test_hdf_rejects_links_without_following_them(tmp_path, link):
    with pytest.raises(ValueError, match='external/soft'):
        probe.matlab_schema(hdf_fixture(tmp_path, link))


def test_changed_source_hash_stops_before_archive_access(tmp_path, monkeypatch):
    base = tmp_path / 'data/raw/thermal_m50t'; base.mkdir(parents=True)
    archive_path = base / 'M50.zip'; archive_path.write_bytes(b'tampered archive')
    readme = base / 'ReadMe.txt'; readme.write_text('synthetic')
    declaration = policy(); declaration['archive_sha256'] = '0' * 64
    declaration_path = tmp_path / 'policy.json'; declaration_path.write_text(json.dumps(declaration))
    monkeypatch.setattr(intake, 'ROOT', tmp_path)
    def forbidden(*args, **kwargs):raise AssertionError('Tampered ZIP must not be opened')
    monkeypatch.setattr(intake, 'inspect_archive', forbidden)
    with pytest.raises(ValueError, match='SHA-256'):intake.build(declaration_path)
