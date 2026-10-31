"""Synthetic access-boundary checks; no measurement file is read."""
import hashlib
import importlib.util
import json
from pathlib import Path
from zipfile import ZipFile

import pytest

MODULE = Path(__file__).resolve().parents[1] / 'reports/thermal_public_evidence_v1/inspect_calorimetry_documentation.py'
spec = importlib.util.spec_from_file_location('thermal_documentation', MODULE)
documentation = importlib.util.module_from_spec(spec)
spec.loader.exec_module(documentation)


def fixture_archive(tmp_path, monkeypatch, size=343779):
    notebook = {'cells': [
        {'cell_type':'markdown','source':['Units and schema only']},
        {'cell_type':'code','source':['raise RuntimeError("MUST NOT EXECUTE")'],
         'outputs':[{'output_type':'display_data','data':{'text/html':'SECRET_SAVED_OUTCOME'}}]},
    ]}
    raw = json.dumps(notebook).encode().ljust(size, b' ')
    path = tmp_path / 'synthetic.zip'
    with ZipFile(path,'w') as archive:
        archive.writestr(documentation.MEMBER,raw)
        archive.writestr('heat_sensor_tr_4mins.npy', b'FORBIDDEN_MEASUREMENT')
    monkeypatch.setattr(documentation,'ROOT',tmp_path)
    monkeypatch.setattr(documentation,'ARCHIVE',path)
    monkeypatch.setattr(documentation,'EXPECTED',hashlib.sha256(path.read_bytes()).hexdigest())
    return tmp_path / 'data/raw/thermal_public_evidence/result'


def test_source_only_extraction_keeps_outputs_and_measurements_closed(tmp_path, monkeypatch):
    out = fixture_archive(tmp_path,monkeypatch)
    opened = []
    original = ZipFile.open
    def guard(self,name,*args,**kwargs):
        assert name == documentation.MEMBER
        opened.append(name)
        return original(self,name,*args,**kwargs)
    monkeypatch.setattr(ZipFile,'open',guard)
    result = documentation.inspect(out)
    text = (out/'example_source.txt').read_text()
    assert opened == [documentation.MEMBER]
    assert 'MUST NOT EXECUTE' in text
    assert 'SECRET_SAVED_OUTCOME' not in text and 'FORBIDDEN_MEASUREMENT' not in text
    assert result['skipped_saved_outputs'] == 1
    assert result['code_executed'] is False and result['numerical_members_opened'] == 0


def test_archive_hash_mismatch_rejected_before_member_access(tmp_path,monkeypatch):
    out = fixture_archive(tmp_path,monkeypatch)
    monkeypatch.setattr(documentation,'EXPECTED','0'*64)
    monkeypatch.setattr(ZipFile,'open',lambda *a,**k:pytest.fail('Unexpected member access'))
    with pytest.raises(ValueError,match='hash differs'):
        documentation.inspect(out)
    assert not out.exists()


def test_changed_notebook_layout_rejected_before_member_access(tmp_path,monkeypatch):
    out = fixture_archive(tmp_path,monkeypatch,size=400)
    monkeypatch.setattr(ZipFile,'open',lambda *a,**k:pytest.fail('Unexpected member access'))
    with pytest.raises(ValueError,match='identity differs'):
        documentation.inspect(out)
    assert not out.exists()


def test_previous_output_cannot_be_overwritten(tmp_path,monkeypatch):
    out = fixture_archive(tmp_path,monkeypatch)
    out.mkdir(parents=True)
    marker=out/'prior.txt';marker.write_text('KEEP')
    with pytest.raises(ValueError,match='fresh'):
        documentation.inspect(out)
    assert marker.read_text() == 'KEEP'
