"""Check preserved evidence, test receipts and local release assets without raw data access."""
from pathlib import Path
import argparse
import hashlib
import json
import sys
import xml.etree.ElementTree as ET
import zipfile

ROOT=Path(__file__).resolve().parents[1]
REPORT=ROOT/'reports/round1_improvements_v1'
sys.path.insert(0,str(ROOT/'src'))


def sha(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def junit(path):
    cases=list(ET.parse(path).iter('testcase'))
    result=dict(tests=len(cases),failures=sum(c.find('failure') is not None for c in cases),
                errors=sum(c.find('error') is not None for c in cases),
                skipped=sum(c.find('skipped') is not None for c in cases))
    assert cases and not result['failures'] and not result['errors'],(path,result)
    result['passed']=result['tests']-result['skipped']
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--public-build',action='store_true',help='Also verify generated public assets; does not deploy')
    args=parser.parse_args()
    preserved=json.loads((REPORT/'PRESERVATION.json').read_text(encoding='utf-8'))
    for relative,expected in preserved['artifacts_sha256'].items():
        path=(ROOT/relative).resolve()
        assert path.is_relative_to(ROOT) and sha(path)==expected,f'Protected artifact changed: {relative}'
    from voltforge.studio.store import Studio
    receipt=dict(schema='voltforge.review-improvements-verification/1',
                 protected_artifacts_unchanged=len(preserved['artifacts_sha256']),
                 software_hash=Studio._software_hash(),
                 python=junit(REPORT/'python_tests.xml'),javascript=junit(REPORT/'javascript_tests.xml'),
                 live_browser_status='not_exercised_browser_host_unavailable',
                 experimental_validation='not_established',external_ai_inference_performed=False)
    slide=ROOT/'reports/slide_round1_review_v1'
    checks=json.loads((slide/'verification.json').read_text(encoding='utf-8'))
    assert sha(slide/'VOLT-FORGE_Round1_Reviewed_Draft.pdf')==checks['pdf_sha256']
    receipt['revised_slide']=dict(pages=checks['pages'],pdf_sha256=checks['pdf_sha256'],
                                 visual_review='Recorded separately in slide_round1_review_v1/VISUAL_QA.md')
    if args.public_build:
        out=ROOT/'public_site';matches=0
        for source in (ROOT/'web/editor').iterdir():
            if source.is_file() and source.name.startswith('studio'):
                assert sha(source)==sha(out/'app'/source.name),f'Public asset stale: {source.name}'
                matches+=1
        for name in ('worker.js','backend.js','ai-status.mjs'):
            assert sha(ROOT/'site'/name)==sha(out/'app'/name)
        assert sha(ROOT/'site/api/ai.js')==sha(out/'api/ai.js')
        with zipfile.ZipFile(out/'app/engine.zip') as archive:
            assert archive.testzip() is None
            assert archive.read('bridge.py')==(ROOT/'site/bridge.py').read_bytes()
            for source in (ROOT/'src/voltforge/studio').glob('*.py'):
                # zipfile normalizes separators on Windows when writing members.
                assert archive.read('src/voltforge/studio/'+source.name)==source.read_bytes()
        receipt['public_build']=dict(assets_matched=matches,engine_archive_verified=True,deployed=False)
    receipt['artifact_hashes']={name:sha(REPORT/name) for name in ('PRESERVATION.json','python_tests.xml','javascript_tests.xml')}
    (REPORT/'verification.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(receipt,indent=2))


if __name__=='__main__':main()
