"""Verify the bounded literature search; never open numerical measurement members."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / 'reports/thermal_public_evidence_v1'
RECEIPT = REPORT / 'verification.json'
sys.path.insert(0,str(ROOT/'src'))
from voltforge.project.service import software


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def checked_path(name, prefix=None):
    path = (ROOT/name).resolve()
    if not path.is_relative_to(prefix or ROOT):
        raise ValueError('Out-of-scope artifact: '+name)
    return path


def check_hashes(mapping, historical=None, prefix=None):
    for name, expected in mapping.items():
        path = (historical or {}).get(name,checked_path(name,prefix))
        if sha(path) != expected:
            raise ValueError('Artifact hash mismatch: '+name)
    return len(mapping)


def history():
    preserved = read(ROOT/'reports/thermal_m50t_handoff_v1/preservation_map.json')
    versions = {}
    for name, record in preserved.items():
        path = checked_path(record['preserved_path'],ROOT/'reports/thermal_m50t_handoff_v1/previous')
        if sha(path) != record['sha256']:
            raise ValueError('Historical status document differs: '+name)
        versions[name] = path
    receipts = {}
    for name in ('reports/assistant_thermal_v1/verification.json',
                 'reports/thermal_m50t_intake_v1/verification.json',
                 'reports/thermal_m50t_handoff_v1/verification.json'):
        data = read(ROOT/name)
        historical = versions if 'thermal_m50t_handoff_v1' not in name else None
        receipts[name] = dict(sha256=sha(ROOT/name),
            artifacts_checked=check_hashes(data['artifacts_sha256'],historical))
    snapshot = read(ROOT/'reports/local_assistant_integration_v1/backend/demo_002/project/runs/run_0001/snapshot.json')
    if software() != snapshot['software']:
        raise ValueError('Frozen numerical source/runtime identity changed')
    return receipts,snapshot['software']['id']


def check_screen():
    screen = read(REPORT/'qualification.json')
    if (screen['decision'] != 'insufficient evidence' or screen['physical_fitting_authorized']
        or screen['candidate_models_adopted'] != 0 or len(screen['candidates']) != 6
        or len({r['id'] for r in screen['candidates']}) != 6
        or any(r['fitting_authorized'] for r in screen['candidates'])):
        raise ValueError('Screen exceeds the declared search-only scope')
    if screen['requirements'] != dict(application_temperature_limit_degC=None,
        permitted_temperature_error_degC=None,status='requirement not configured'):
        raise ValueError('Unestablished requirements changed')
    suites=ET.parse(REPORT/'tests.xml').getroot().findall('testsuite')
    cases=[c for s in suites for c in s.findall('testcase')]
    if (len(cases)!=4 or any(int(s.get(k,'0')) for s in suites for k in ('failures','errors','skipped'))
        or any(c.find(k) is not None for c in cases for k in ('failure','error','skipped'))):
        raise ValueError('Documentation-boundary test receipt did not pass')
    author=read(REPORT/'author_sources.json')
    if sha(REPORT/'AUTHOR_SEARCH.md') != author['report_sha256']:
        raise ValueError('Author report changed after handoff')
    check_hashes(author['existing_inputs_sha256'])
    extraction=read(REPORT/'notebook_source_receipt.json')
    if (extraction['opened_members'] != ['example_code.ipynb'] or extraction['code_executed']
        or extraction['numerical_members_opened'] != 0 or extraction['saved_outputs_displayed'] != 0
        or extraction['skipped_saved_outputs'] != 2):
        raise ValueError('Notebook access differs from declared documentation-only inspection')


def local_sources():
    count=0
    for name in ('author_sources.json','alternative_sources.json'):
        count+=check_hashes(read(REPORT/name)['local_artifacts_sha256'],
                            prefix=ROOT/'data/raw/thermal_public_evidence')
    return count


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    mode=parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--seal',action='store_true',help='Create the initial immutable search receipt')
    mode.add_argument('--verify',action='store_true',help='Verify the existing sealed receipt')
    parser.add_argument('--local-sources',action='store_true',help='Also hash ignored documentation/archive bytes; no array parsing')
    args=parser.parse_args()
    if args.seal and RECEIPT.exists():
        raise ValueError('Search receipt already exists; never overwrite it')
    if args.verify:
        saved=read(RECEIPT)
        check_hashes(saved['artifacts_sha256'])
    check_screen()
    prior,frozen_id=history()
    count=local_sources() if args.local_sources else None
    result=dict(schema='voltforge.thermal_public_evidence_verification/1',
        status='artifact_integrity_verified',preserved_receipts=prior,frozen_software_id=frozen_id,
        synthetic_boundary_tests=4,candidate_families_screened=6,
        new_measurement_archives_downloaded=1,numerical_members_opened_in_search=0,
        local_source_hashes_checked=count,engineering_decision='insufficient evidence',
        meaning='Documentation and preservation checks, not experimental prediction accuracy')
    if args.verify:
        if prior != saved['preserved_receipts'] or frozen_id != saved['frozen_software_id']:
            raise ValueError('Preserved history differs from sealed search')
    if args.seal:
        paths=[p for p in REPORT.rglob('*') if p.is_file() and p!=RECEIPT and '__pycache__' not in p.parts]
        paths += [ROOT/'THERMAL_EVIDENCE_DECISION.md',Path(__file__),ROOT/'tests/test_thermal_evidence_documentation.py']
        result['artifacts_sha256']={p.relative_to(ROOT).as_posix():sha(p) for p in sorted(paths)}
        with RECEIPT.open('x',encoding='utf-8') as stream:
            json.dump(result,stream,indent=2);stream.write('\n')
    print(json.dumps({k:v for k,v in result.items() if k!='artifacts_sha256'},indent=2))


if __name__ == '__main__':main()
