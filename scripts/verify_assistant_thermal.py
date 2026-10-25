"""Verify the local-command/thermal release and explicitly preserved UI history."""
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
for directory in (ROOT,ROOT/'src',ROOT/'scripts'):sys.path.insert(0,str(directory))
import verify_evidence_panel as previous
from demonstrate_local_assistant import verify_saved
from thermal_prototype import verify as verify_thermal


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def preserved_versions():
    declaration=json.loads((ROOT/'reports/assistant_thermal_v1/preservation_map.json').read_text())
    mapping={}
    for name,item in declaration.items():
        path=(ROOT/item['preserved_path']).resolve()
        if not path.is_relative_to(ROOT/'reports/assistant_thermal_v1/previous'):
            raise ValueError('Historical file is outside the declared archive')
        if sha(path)!=item['sha256']:raise ValueError('Changed preserved bytes: '+name)
        mapping[(ROOT/name).resolve()]=path
    return mapping


@contextmanager
def historical_release_hashes(mapping):
    # Only the prior release verifier's living-file hash reads use the recorded
    # old versions. Numerical sources, calculations and project runtime do not.
    original=previous.sha
    previous.sha=lambda path:original(mapping.get(Path(path).resolve(),path))
    try:yield
    finally:previous.sha=original


def verify(tests,browser):
    mapping=preserved_versions()
    prior=json.loads((ROOT/'reports/evidence_panel_v1/verification.json').read_text())
    for name,expected in prior['artifacts_sha256'].items():
        if sha(mapping.get((ROOT/name).resolve(),ROOT/name))!=expected:
            raise ValueError('Prior release preservation failed: '+name)
    with historical_release_hashes(mapping):
        older=previous.verify(ROOT/'reports/evidence_panel_v1/pytest.xml',ROOT/'reports/evidence_panel_v1/browser_005')
    receipts={}
    for name,key in [('reports/local_assistant_v1/verification.json','implementation_and_receipt_sha256'),
                     ('reports/local_assistant_integration_v1/backend/verification.json','artifacts_sha256')]:
        receipt=json.loads((ROOT/name).read_text())
        for artifact,expected in receipt[key].items():
            if sha(ROOT/artifact)!=expected:raise ValueError('Changed new release artifact: '+artifact)
        receipts[name]=len(receipt[key])
    demo=verify_saved(ROOT/'reports/local_assistant_integration_v1/backend/demo_002')
    thermal=verify_thermal(ROOT/'reports/thermal_feasibility_v1/run_001')
    browser_receipt=json.loads((browser/'verification.json').read_text())
    assert browser_receipt['status']=='passed' and not browser_receipt['browser_errors']
    assert browser_receipt['external_ai_calls']==0
    for name,expected in browser_receipt['screenshots'].items():assert sha(browser/name)==expected,name
    suites=ET.parse(tests).getroot().findall('testsuite')
    assert suites and all(all(int(s.get(k,'0'))==0 for k in ('failures','errors','skipped')) for s in suites)
    node=(ROOT/'reports/assistant_thermal_v1/node_tests.txt').read_text(encoding='utf-8')
    assert '# fail 0' in node and '# pass 27' in node
    folders=['reports/assistant_thermal_v1','reports/local_assistant_v1','reports/local_assistant_integration_v1','reports/thermal_feasibility_v1']
    files=[p for folder in folders for p in (ROOT/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts
           and p!=ROOT/'reports/assistant_thermal_v1/verification.json']
    names=['README.md','scripts/run_editor.py','scripts/local_assistant.py','scripts/thermal_prototype.py',
           'scripts/demonstrate_local_assistant.py','scripts/check_assistant_browser.py','scripts/verify_assistant_thermal.py',
           'configs/local_assistant_eval_v1.json','configs/thermal_feasibility_v1.json','tests/test_local_assistant.py',
           'tests/test_editor_assistant.py','tests/test_thermal_prototype.py','tests/assistant_panel.test.mjs',
           'web/editor/app.js','web/editor/index.html','web/editor/assistant-panel.mjs','web/editor/assistant.css']
    files.extend(ROOT/n for n in names)
    return dict(schema='voltforge.assistant_thermal_verification/1',status='passed',
        python_tests=sum(int(s.get('tests')) for s in suites),javascript_tests=27,
        prior_release_artifacts_preserved=len(prior['artifacts_sha256']),prior_source_chain_verified=older['status'],
        new_agent_receipts=receipts,local_command_demo=demo,thermal_replay=thermal,
        browser_checks=browser_receipt['checks'],browser_path=browser.relative_to(ROOT).as_posix(),
        mode='local_commands',external_ai_calls=0,language_model_integrated=False,
        frozen_electrical_models_changed=False,new_measurement_outcomes_opened=0,
        thermal_applicability='synthetic only; no real-cell/module applicability established',
        experimental_module_validation='awaiting suitable measurements',
        artifacts_sha256={p.relative_to(ROOT).as_posix():sha(p) for p in sorted(set(files))})


def main():
    import argparse
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--tests',type=Path,default=ROOT/'reports/assistant_thermal_v1/pytest.xml')
    p.add_argument('--browser',type=Path,default=ROOT/'reports/assistant_thermal_v1/browser_003')
    p.add_argument('--out',type=Path,required=True);args=p.parse_args()
    out=args.out.resolve()
    if out.exists() or not any(out.is_relative_to(ROOT/n) for n in ['tmp','reports/assistant_thermal_v1']):
        raise ValueError('Choose a fresh receipt under tmp/ or reports/assistant_thermal_v1/')
    result=verify(args.tests,args.browser.resolve());out.parent.mkdir(parents=True,exist_ok=True)
    with out.open('x',encoding='utf-8') as f:json.dump(result,f,indent=2)
    print(json.dumps({k:v for k,v in result.items() if k!='artifacts_sha256'},indent=2))


if __name__=='__main__':main()
