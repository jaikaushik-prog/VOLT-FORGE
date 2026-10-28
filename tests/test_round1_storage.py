from copy import deepcopy
import json

import pytest

from voltforge.project.service import Project
from voltforge.studio import store
from voltforge.studio.copilot import Copilot


@pytest.fixture
def studio(tmp_path):
    project=tmp_path/'project';Project.create_reference(project)
    return store.Studio(project)


@pytest.mark.parametrize('fault',['before_document','after_document','index'])
def test_interrupted_save_recovers_one_committed_revision(studio,monkeypatch,fault):
    doc=studio.create();graph=deepcopy(doc['graph']);graph['name']='Recovered change'
    original=store.write
    def interrupted(path,data):
        path=store.Path(path)
        isdoc=path.parent.name=='documents'
        if fault=='before_document' and isdoc:raise OSError('Injected write failure')
        if fault=='index' and path.name=='index.json':raise OSError('Injected index failure')
        original(path,data)
        if fault=='after_document' and isdoc:raise OSError('Injected post-replace failure')
    with monkeypatch.context() as m:
        m.setattr(store,'write',interrupted)
        with pytest.raises(ValueError,match='recorded for recovery'):
            studio.save(doc['id'],doc['version'],graph,doc['settings'])
    recovered=store.Studio(studio.root.parent)
    actual=recovered.document(doc['id'])
    assert actual['version']==doc['version']+1
    assert actual['graph']['name']=='Recovered change'
    assert next(d for d in recovered.catalog()['designs'] if d['id']==doc['id'])['name']=='Recovered change'
    assert not recovered.journal_path.exists()
    with pytest.raises(ValueError,match='another window'):
        recovered.save(doc['id'],doc['version'],graph,doc['settings'])


def test_failure_before_commit_keeps_saved_revision(studio,monkeypatch):
    doc=studio.create();graph=deepcopy(doc['graph']);graph['name']='Not committed'
    original=store.write
    def fail(path,data):
        if store.Path(path)==studio.journal_path:raise OSError('No journal bytes committed')
        return original(path,data)
    with monkeypatch.context() as m:
        m.setattr(store,'write',fail)
        with pytest.raises(ValueError,match='previous saved version is unchanged'):
            studio.save(doc['id'],doc['version'],graph,doc['settings'])
    assert studio.document(doc['id'])['graph']['name']==doc['graph']['name']


def test_unused_model_does_not_invalidate_a_saved_experiment(studio):
    doc=studio.create();settings=deepcopy(doc['settings']);settings['profile'][0]['end_s']=1
    doc=studio.save(doc['id'],doc['version'],doc['graph'],settings)
    test=studio.run(doc['id'],doc['version'])
    studio.models['unused_other_model']=deepcopy(studio.models['SAMSUNG_30T'])
    assert studio.test(test['id'])['current']


def test_live_source_change_requires_restart_before_a_new_experiment(studio,monkeypatch):
    doc=studio.create()
    monkeypatch.setattr(studio,'_software_hash',lambda:'changed-files')
    with pytest.raises(ValueError,match='Restart the local editor'):
        studio.run(doc['id'],doc['version'])
    assert not studio.document(doc['id'])['tests']


def test_old_baseline_whatif_changes_only_the_declared_input(studio):
    doc=studio.create();settings=deepcopy(doc['settings']);settings['profile'][0]['end_s']=1
    doc=studio.save(doc['id'],doc['version'],doc['graph'],settings)
    baseline=studio.run(doc['id'],doc['version'])
    graph=deepcopy(doc['graph']);graph['cells'][2]['charge_pct']=60
    current=studio.save(doc['id'],doc['version'],graph,settings)
    result=studio.investigate(doc['id'],current['version'],'connection',baseline_test_id=baseline['id'])
    assert result['test']['graph']['cells'][2]['charge_pct']==70
    assert result['test']['graph']['connections'][0]['resistance_mohm']==4
    comparison=studio.compare([baseline['id'],result['test']['id']])
    assert comparison['single_factor_comparison']
    assert any(c['path'].endswith('resistance_mohm') for c in comparison['design_changes'])


def test_ai_receives_old_graph_and_shows_full_resistance(studio,monkeypatch):
    doc=studio.create();settings=deepcopy(doc['settings']);settings['profile'][0]['end_s']=1
    doc=studio.save(doc['id'],doc['version'],doc['graph'],settings)
    old=studio.run(doc['id'],doc['version'])
    graph=deepcopy(doc['graph']);graph['cells'][0]['charge_pct']=65
    current=studio.save(doc['id'],doc['version'],graph,settings)
    copilot=Copilot(studio);contexts=[]
    def infer(prompt):
        contexts.append(json.loads(prompt)['context'])
        return dict(message='A proposed connection.',actions=[dict(op='set_connection_resistance',target='wire1',value=999.,text='',from_terminal='',to_terminal='')])
    monkeypatch.setattr(copilot,'_infer',infer)
    answer=copilot.chat([dict(role='user',content='Explain the old result')],doc['id'],test_id=old['id'])
    assert contexts[0]['design']['cells'][0]['charge_pct']==70
    assert contexts[0]['editable_design']['cells'][0]['charge_pct']==65
    assert contexts[0]['test']['model_hash']==old['model_hash']
    assert any('999' in text for text in answer['proposal']['changes'])
    assert any(d['after']==999. for d in answer['proposal']['diff'])


def test_ai_preview_and_saved_draft_share_preflight(studio,monkeypatch):
    doc=studio.create();copilot=Copilot(studio)
    monkeypatch.setattr(copilot,'_infer',lambda p:dict(message='Set the temperature.',actions=[dict(op='set_temperature',target='cell1',value=60.,text='',from_terminal='',to_terminal='')]))
    proposal=copilot.chat([dict(role='user',content='Change starting temperature')],doc['id'])['proposal']
    assert not proposal['readiness']['ready']
    draft=copilot.apply(proposal['id'])
    assert draft['readiness']==proposal['readiness']


def test_home_copilot_creates_one_complete_draft_without_an_empty_interim_design(studio,monkeypatch):
    before={d['id'] for d in studio.catalog()['designs']};copilot=Copilot(studio)
    monkeypatch.setattr(copilot,'_infer',lambda p:dict(message='Here is a draft.',actions=[dict(op='use_template',target='',value=4.,text='parallel',from_terminal='',to_terminal='')]))
    proposal=copilot.chat([dict(role='user',content='Build four parallel cells')])['proposal']
    assert proposal['new_design'] and proposal['cell_count']==4
    draft=copilot.apply(proposal['id'])
    assert len(draft['graph']['cells'])==4 and draft['readiness']['ready']
    assert {d['id'] for d in studio.catalog()['designs']}-before=={draft['id']}
    assert draft['version']==1


def test_existing_design_proposal_is_never_classified_as_a_new_home_draft(studio,monkeypatch):
    doc=studio.create();copilot=Copilot(studio)
    monkeypatch.setattr(copilot,'_infer',lambda p:dict(message='Here is a proposed change.',actions=[dict(op='set_charge',target='cell1',value=60.,text='',from_terminal='',to_terminal='')]))
    proposal=copilot.chat([dict(role='user',content='Change Cell 1 to 60 percent')],doc['id'])['proposal']
    assert not proposal['new_design']
    assert studio.document(doc['id'])['graph']['cells'][0]['charge_pct']==70
