"""Verify current editor evidence and resolve historical UI hashes to preserved bytes."""
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'));sys.path.insert(0,str(ROOT/'src'))
import verify_p45b_intake
from verify_parallel_engineering import verify as verify_previous
from verify_p45b_reference_origin import verify as verify_origin


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def preservation_map(root=ROOT):
    mapping=json.loads((root/'reports/evidence_panel_v1/preservation_map.json').read_text())
    resolved={}
    for name,item in mapping.items():
        preserved=(root/item['preserved_path']).resolve()
        if not preserved.is_relative_to((root/'reports/evidence_panel_v1/previous').resolve()):
            raise ValueError('Historical version must stay inside the preserved directory')
        if sha(preserved)!=item['sha256']:raise ValueError('Historical bytes changed: '+name)
        resolved[(root/name).resolve()]=preserved
    return resolved


@contextmanager
def historical_frontend_hashes(mapping):
    """Only the old intake verifier's hash lookups use preserved living files.

    No numerical source, measurement, calibration or application runtime is
    patched. Every previous expected hash is still checked against exact bytes.
    Current frontend files are checked separately against this release receipt.
    """
    original=verify_p45b_intake.file_hash
    def historical(path):return original(mapping.get(Path(path).resolve(),path))
    verify_p45b_intake.file_hash=historical
    try:yield
    finally:verify_p45b_intake.file_hash=original


def verify(tests,browser):
    mapping=preservation_map()
    receipt=json.loads((ROOT/'reports/parallel_engineering_v1/verification.json').read_text())
    for name,expected in receipt['artifacts_sha256'].items():
        target=mapping.get((ROOT/name).resolve(),ROOT/name)
        assert sha(target)==expected,name
    with historical_frontend_hashes(mapping):
        previous=verify_previous(ROOT/'reports/parallel_engineering_v1/pytest.xml')
    origin=verify_origin(ROOT/'reports/p45b_reference_origin_v1/run_001')
    backend=json.loads((ROOT/'reports/evidence_panel_v1/backend/verification.json').read_text())
    for name,expected in backend['artifacts_sha256'].items():assert sha(ROOT/name)==expected,name
    browser_receipt=json.loads((browser/'verification.json').read_text())
    assert browser_receipt['status']=='passed' and not browser_receipt['browser_errors']
    for name,expected in browser_receipt['screenshots'].items():assert sha(browser/name)==expected,name
    suites=ET.parse(tests).getroot().findall('testsuite')
    assert suites and all(all(int(s.get(k,'0'))==0 for k in ('failures','errors','skipped')) for s in suites)
    node=(ROOT/'reports/evidence_panel_v1/node_tests_final.txt').read_text(encoding='utf-8')
    assert '# fail 0' in node and '# pass 22' in node
    files=[p for folder in ['reports/evidence_panel_v1','reports/p45b_reference_origin_v1']
           for p in (ROOT/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts
           and p!=ROOT/'reports/evidence_panel_v1/verification.json']
    files += [ROOT/n for n in ['README.md','scripts/run_editor.py','scripts/check_evidence_browser.py','scripts/verify_evidence_panel.py',
        'scripts/ae_p45b_reference_origin.py','scripts/verify_p45b_reference_origin.py','configs/ae_p45b_reference_origin_v1.json',
        'web/editor/app.js','web/editor/index.html','web/editor/style.css','web/editor/evidence.css','web/editor/evidence-panel.mjs','web/editor/evidence-state.mjs',
        'tests/test_editor_evidence.py','tests/test_evidence_preservation.py','tests/evidence_state.test.mjs','tests/test_ae_p45b_reference_origin.py']]
    return dict(schema='voltforge.evidence_panel_verification/1',status='passed',
        python_tests=sum(int(s.get('tests')) for s in suites),presentation_tests=22,
        browser_observations=browser_receipt['observations'],browser_receipt=str(browser.relative_to(ROOT)),
        previous_release_artifacts_preserved=len(receipt['artifacts_sha256']),
        historical_frontend_map={str(k.relative_to(ROOT)):str(v.relative_to(ROOT)) for k,v in mapping.items()},
        numerical_prior_checks=previous['electrical_diagnostics'],reference_origin=origin,
        frozen_models_changed=False,new_measurement_outcomes_opened=0,language_model_integrated=False,
        experimental_module_validation='awaiting suitable measurements',
        artifacts_sha256={p.relative_to(ROOT).as_posix():sha(p) for p in sorted(set(files))})


def main():
    import argparse
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--tests',type=Path,default=ROOT/'reports/evidence_panel_v1/pytest.xml')
    p.add_argument('--browser',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True);args=p.parse_args()
    out=args.out.resolve()
    if out.exists() or not any(out.is_relative_to(ROOT/n) for n in ['tmp','reports/evidence_panel_v1']):
        raise ValueError('Use a new receipt under tmp/ or reports/evidence_panel_v1/')
    result=verify(args.tests,args.browser.resolve());out.parent.mkdir(parents=True,exist_ok=True)
    with out.open('x',encoding='utf-8') as f:json.dump(result,f,indent=2)
    print(json.dumps({k:v for k,v in result.items() if k!='artifacts_sha256'},indent=2))


if __name__=='__main__':main()
