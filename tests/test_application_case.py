from copy import deepcopy
import io
import json
import zipfile

from voltforge.project.service import Project
from voltforge.studio.store import Studio
from voltforge.studio.copilot import Copilot


def test_application_and_requirements_are_immutable_across_new_assessments(tmp_path,monkeypatch):
    project=tmp_path/'project';Project.create_reference(project);studio=Studio(project)
    doc=studio.create();settings=deepcopy(doc['settings']);settings['profile'][0]['end_s']=1
    doc=studio.save(doc['id'],doc['version'],doc['graph'],settings);first=studio.run(doc['id'],doc['version'])
    assert first['case']['description']['name']=='Low-voltage backup design study'
    assert first['case']['mission']['profile']==settings['profile']
    settings['limits']['min_voltage_V']=4.
    doc=studio.save(doc['id'],doc['version'],doc['graph'],settings);second=studio.run(doc['id'],doc['version'])
    assert first['case']['requirements_fingerprint']!=second['case']['requirements_fingerprint']
    assert studio.test(first['id'])['case']==first['case']
    assert not studio.compare([first['id'],second['id']])['requirements_match']
    copilot=Copilot(studio);contexts=[]
    monkeypatch.setattr(copilot,'_infer',lambda prompt:(contexts.append(json.loads(prompt)['context']) or dict(message='Saved case.',actions=[])))
    copilot.chat([dict(role='user',content='Explain the original requirement')],doc['id'],test_id=first['id'])
    assert contexts[0]['test']['case']==first['case']
    with zipfile.ZipFile(io.BytesIO(studio.export(first['id']))) as archive:
        record=json.loads(archive.read('experiment.json'))
        assert record['case']==first['case']
        assert first['case']['requirements_fingerprint'] in archive.read('report.html').decode()
