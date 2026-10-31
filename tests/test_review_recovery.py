"""Synthetic recovery and snapshot checks for the Round 1 review corrections."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import threading
from urllib.request import Request, urlopen
from urllib.error import HTTPError

import pytest

from voltforge.project.service import Project
from voltforge.studio.store import Studio
from voltforge.studio.copilot import Copilot


@pytest.fixture
def studio(tmp_path):
    Project.create_reference(tmp_path/'project')
    return Studio(tmp_path/'project')


def test_conflicted_draft_recovery_preserves_newer_source_and_old_run(studio):
    first=studio.create(mission={'preset':'pi5_gateway_backup'})
    settings=deepcopy(first['settings']);settings['profile'][0]['end_s']=1.
    first=studio.save(first['id'],first['version'],first['graph'],settings)
    run=studio.run(first['id'],first['version'])
    stale_graph=deepcopy(first['graph']);stale_graph['connections'][0]['resistance_mohm']=3.
    newer_graph=deepcopy(first['graph']);newer_graph['cells'][0]['charge_pct']=65.
    newer=studio.save(first['id'],first['version'],newer_graph,settings)
    with pytest.raises(ValueError,match='another window'):
        studio.save(first['id'],first['version'],stale_graph,settings)
    recovered=studio.save_copy(stale_graph,settings,source_design_id=first['id'],source_version=first['version'])
    assert recovered['id']!=first['id']
    assert recovered['version']==1 and recovered['history']==[]
    assert recovered['graph']['connections'][0]['resistance_mohm']==3.
    assert recovered['graph']['cells'][0]['charge_pct']==70.
    assert recovered['origin']['source_version']==first['version']
    assert recovered['origin']['saved_source_version']==newer['version']
    assert studio.document(first['id'])['graph']==newer_graph
    assert studio.test(run['id'])['payload_hash']==run['payload_hash']
    assert not studio.test(run['id'])['current']
    assert stale_graph['name']==first['graph']['name']


def test_invalid_recovery_never_creates_partial_design(studio):
    first=studio.create();before=len(studio.catalog()['designs'])
    bad=deepcopy(first['graph']);bad['connections'][0]['resistance_mohm']=-1.
    with pytest.raises(ValueError):studio.save_copy(bad,first['settings'])
    with pytest.raises(ValueError):studio.save_copy(first['graph'],first['settings'],source_version=True)
    with pytest.raises(ValueError):studio.save_copy(first['graph'],first['settings'],source_design_id='unknown')
    with pytest.raises(ValueError):studio.save_copy(first['graph'],first['settings'],name=' ')
    assert len(studio.catalog()['designs'])==before


def test_import_as_new_draft_has_no_inherited_test_or_remote_source_claim(studio):
    original=studio.create()
    imported=studio.save_copy(original['graph'],original['settings'],name='Imported draft')
    assert imported['origin']['source_design_id'] is None
    assert imported['tests']==[] and imported['history']==[]
    assert imported['graph']['name']=='Imported draft'


def test_recovery_default_name_keeps_valid_long_names_recoverable(studio):
    original=studio.create(name='A'*100)
    recovered=studio.save_copy(original['graph'],original['settings'])
    assert len(recovered['graph']['name'])==100
    assert recovered['graph']['name'].endswith(' recovered copy')
    assert studio.document(original['id'])['graph']['name']=='A'*100


def test_saved_model_cards_survive_a_current_design_model_change(studio):
    doc=studio.create();settings=deepcopy(doc['settings']);settings['profile'][0]['end_s']=1.
    doc=studio.save(doc['id'],doc['version'],doc['graph'],settings)
    run=studio.run(doc['id'],doc['version']);cards=deepcopy(run['model_cards'])
    graph=deepcopy(doc['graph'])
    for cell in graph['cells']:cell['model']='SAMSUNG_30T'
    studio.save(doc['id'],doc['version'],graph,settings)
    historical=studio.test(run['id'])
    assert historical['model_cards']==cards
    assert 'SAMSUNG_30T' not in historical['model_cards']
    assert historical['payload_hash']==run['payload_hash']


def test_runtime_and_provider_metadata_do_not_claim_persistence_or_authentication(studio,tmp_path,monkeypatch):
    assert studio.catalog()['runtime']['persistence']=='local_workspace'
    browser_project=tmp_path/'browser';Project.create_reference(browser_project)
    browser=Studio(browser_project,runtime='browser_session')
    assert 'temporary' in browser.catalog()['runtime']['description']
    assert browser.catalog()['runtime']['design_draft_import_supported']
    assert not browser.catalog()['runtime']['project_import_supported']
    copilot=Copilot(studio);copilot.provider='Codex'
    monkeypatch.setattr(copilot,'_infer',lambda _:pytest.fail('Metadata must not call a provider'))
    assert copilot.status()['available']
    assert not copilot.status()['connection_verified']
    assert copilot.status()['availability_basis']=='provider_executable_present'


def test_http_recovery_route_validates_and_creates_a_separate_document(tmp_path):
    spec=importlib.util.spec_from_file_location('review_editor_server',Path(__file__).parents[1]/'scripts/run_editor.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    server=module.EditorServer(('127.0.0.1',0),tmp_path/'http_project')
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    def request(operation,arguments):
        req=Request(f'http://127.0.0.1:{server.server_port}/api/studio',
                    data=json.dumps({'operation':operation,'arguments':arguments}).encode(),
                    headers={'Content-Type':'application/json','X-Voltforge-Token':server.token})
        try:response=urlopen(req,timeout=30)
        except HTTPError as error:response=error
        with response:return response.status,json.loads(response.read())
    try:
        _,value=request('create',{'count':2});doc=value['result']
        status,value=request('save_copy',{'graph':doc['graph'],'settings':doc['settings'],
                                          'source_design_id':doc['id'],'source_version':doc['version'],'name':'Recovered over HTTP'})
        assert status==200 and value['result']['id']!=doc['id']
        assert server.studio.document(doc['id'])['version']==doc['version']
        status,_=request('save_copy',{'graph':doc['graph'],'settings':{},'name':'Invalid'})
        assert status==400
    finally:
        server.shutdown();server.server_close();thread.join()
