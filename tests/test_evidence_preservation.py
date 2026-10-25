"""Historical UI versions remain verifiable without replacing current source."""
import json
from pathlib import Path
import sys
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import verify_evidence_panel as check


def test_declared_history_and_live_file_remain_distinct(tmp_path):
    old=tmp_path/'old.py';old.write_text('old version')
    current=tmp_path/'current.py';current.write_text('new version')
    unrelated=tmp_path/'physics.py';unrelated.write_text('untouched')
    original=check.verify_p45b_intake.file_hash
    with check.historical_frontend_hashes({current.resolve():old}):
        assert check.verify_p45b_intake.file_hash(current)==check.sha(old)
        assert check.verify_p45b_intake.file_hash(unrelated)==check.sha(unrelated)
        assert check.sha(current)!=check.sha(old)
    assert check.verify_p45b_intake.file_hash is original
    assert current.read_text()=='new version'


def test_failed_historical_check_restores_function(tmp_path):
    original=check.verify_p45b_intake.file_hash
    with pytest.raises(RuntimeError):
        with check.historical_frontend_hashes({}):raise RuntimeError('synthetic failure')
    assert check.verify_p45b_intake.file_hash is original


def test_preserved_bytes_and_location_are_checked(tmp_path):
    report=tmp_path/'reports/evidence_panel_v1';old=report/'previous/app.js'
    old.parent.mkdir(parents=True);old.write_text('historical')
    declaration={'web/editor/app.js':{'preserved_path':str(old.relative_to(tmp_path)),'sha256':check.sha(old)}}
    (report/'preservation_map.json').write_text(json.dumps(declaration))
    assert check.preservation_map(tmp_path)[(tmp_path/'web/editor/app.js').resolve()]==old.resolve()
    old.write_text('tampered')
    with pytest.raises(ValueError,match='changed'):check.preservation_map(tmp_path)
