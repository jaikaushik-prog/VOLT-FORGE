from copy import deepcopy
import json

import pytest

from voltforge.project.service import Project
from voltforge.studio.store import Studio
from voltforge.studio.copilot import Copilot


@pytest.fixture
def studio(tmp_path):
    path=tmp_path/'project';Project.create_reference(path);return Studio(path)


def baseline(studio,seconds=1.,current=12.):
    doc=studio.create();s=deepcopy(doc['settings']);s['profile'][0].update(end_s=seconds,current_A=current)
    doc=studio.save(doc['id'],doc['version'],doc['graph'],s)
    return doc,studio.run(doc['id'],doc['version'])


def test_pressure_test_finds_real_component_limit_and_does_not_modify_baseline(studio):
    doc,test=baseline(studio)
    inv=studio.begin_investigation(doc['id'],doc['version'],test['id'],'load')
    before=studio.document(doc['id']);count=len(studio.catalog()['designs'])
    for i in range(len(inv['planned'])):inv=studio.investigate_case(inv['id'],i)
    assert inv['complete']
    assert any(c['outcome']['kind']=='component_limit' for c in inv['cases'])
    first=next(c for c in inv['cases'] if c['outcome']['kind']=='component_limit')
    assert first['outcome']['affected_cells']==['cell1']
    assert first['outcome']['first_limit']['current_A']>7.275
    assert studio.document(doc['id'])==before
    assert len(studio.catalog()['designs'])==count
    assert all('rows' not in c for c in inv['cases'])
    assert studio.investigation(inv['id'],include_rows=True)['cases'][0]['rows']


def test_configured_target_is_highlighted_at_first_observed_sample(studio):
    doc,test=baseline(studio)
    s=deepcopy(doc['settings']);s['limits']['current_A']=3.5
    doc=studio.save(doc['id'],doc['version'],doc['graph'],s);test=studio.run(doc['id'],doc['version'])
    inv=studio.begin_investigation(doc['id'],doc['version'],test['id'])
    inv=studio.investigate_case(inv['id'],0);case=inv['cases'][0]
    assert case['outcome']['kind']=='design_target'
    assert case['outcome']['first_limit']['time_s']==0.
    assert case['outcome']['first_limit']['value']>3.5
    assert case['sample_row']['time_s']==0.


def test_warming_outside_recorded_cell_data_is_a_model_boundary(studio):
    doc=studio.create('parallel',1);g=deepcopy(doc['graph']);s=deepcopy(doc['settings'])
    g['cells'][0]['temperature_C']=54.99;s['ambient_C']=54.99;s['profile'][0].update(end_s=10.,current_A=1.)
    doc=studio.save(doc['id'],doc['version'],g,s);test=studio.run(doc['id'],doc['version'])
    inv=studio.begin_investigation(doc['id'],doc['version'],test['id'],'temperature')
    inv=studio.investigate_case(inv['id'],0);inv=studio.investigate_case(inv['id'],1)
    case=inv['cases'][1]
    assert case['outcome']['kind']=='model_boundary'
    assert case['status']=='stopped'
    assert 0<case['outcome']['first_limit']['time_s']<10
    assert case['outcome']['affected_cells']==['cell1']


def test_partial_investigation_can_resume_and_completed_case_is_idempotent(studio):
    doc,test=baseline(studio)
    inv=studio.begin_investigation(doc['id'],doc['version'],test['id'],'connection')
    one=studio.investigate_case(inv['id'],0)
    reopened=Studio(studio.root.parent)
    assert reopened.investigate_case(inv['id'],0)==one
    two=reopened.investigate_case(inv['id'],1)
    assert len(two['cases'])==2 and not two['complete']
    assert two['cases'][1]['graph']['connections'][0]['resistance_mohm']==2


def test_pressure_test_context_is_grounded_and_case_opens_as_separate_design(studio,monkeypatch):
    doc,test=baseline(studio)
    inv=studio.begin_investigation(doc['id'],doc['version'],test['id']);inv=studio.investigate_case(inv['id'],0)
    copilot=Copilot(studio);contexts=[]
    monkeypatch.setattr(copilot,'_infer',lambda prompt:(contexts.append(json.loads(prompt)['context']) or dict(message='Saved pressure test.',actions=[])))
    copilot.chat([dict(role='user',content='Explain where this design reaches its limits')],doc['id'],investigation_id=inv['id'])
    assert contexts[0]['investigation']['baseline_payload_hash']==test['payload_hash']
    assert contexts[0]['investigation']['cases'][0]['summary']==inv['cases'][0]['summary']
    result=studio.open_investigation_case(inv['id'],0)
    assert result['design']['id']!=doc['id']
    assert result['test']['rows']==test['rows']


def test_unallocated_or_out_of_order_pressure_case_is_rejected(studio):
    doc,test=baseline(studio);inv=studio.begin_investigation(doc['id'],doc['version'],test['id'])
    with pytest.raises(ValueError,match='declared order'):studio.investigate_case(inv['id'],1)
    with pytest.raises(ValueError,match='allocated'):studio.investigate_case(inv['id'],-1)
