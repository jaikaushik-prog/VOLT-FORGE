"""Verify the engineering handoff and explicitly preserved status-document history."""
from contextlib import contextmanager
from collections import Counter
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
import verify_thermal_m50t_intake as previous

REPORT = ROOT / 'reports/thermal_m50t_handoff_v1'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def historical_paths():
    mapping = {}
    for name, record in read(REPORT / 'preservation_map.json').items():
        path = (ROOT / record['preserved_path']).resolve()
        if not path.is_relative_to(REPORT / 'previous') or sha(path) != record['sha256']:
            raise ValueError('Changed/out-of-scope preserved status document: ' + name)
        mapping[(ROOT / name).resolve()] = path
    return mapping


@contextmanager
def historical_document_hashes(mapping):
    # Only historical document hash reads in the old verifier use preserved
    # versions. Model sources, input reads and calculations remain unchanged.
    original = previous.digest
    previous.digest = lambda path: original(mapping.get(Path(path).resolve(), path))
    try:
        yield
    finally:
        previous.digest = original


def verify_history():
    mapping = historical_paths()
    preserved = {}
    for name in ('reports/assistant_thermal_v1/verification.json',
                 'reports/thermal_m50t_intake_v1/verification.json'):
        receipt = read(ROOT / name)
        for artifact, expected in receipt['artifacts_sha256'].items():
            path = mapping.get((ROOT / artifact).resolve(), ROOT / artifact)
            if sha(path) != expected:
                raise ValueError('Changed historical artifact: ' + artifact)
        preserved[name] = len(receipt['artifacts_sha256'])
    with historical_document_hashes(mapping):
        older = previous.verify()
    return dict(preserved_receipt_artifacts=preserved, prior_intake_replay=older['status'],
                frozen_software_id=older['frozen_software_id'])


def read_tests(path):
    suites = ET.parse(path).getroot().findall('testsuite')
    if not suites or any(int(s.get(k, '0')) for s in suites for k in ('failures', 'errors', 'skipped')):
        raise ValueError('Combined test receipt is not clean')
    cases = [case for suite in suites for case in suite.findall('testcase')]
    expected = {'tests.test_thermal_m50t_development': 24,
                'tests.test_thermal_m50t_intake': 26,
                'tests.test_thermal_prototype': 39}
    if dict(Counter(case.get('classname') for case in cases)) != expected:
        raise ValueError('Combined receipt must contain the three declared test modules')
    if any(case.find(tag) is not None for case in cases for tag in ('failure', 'error', 'skipped')):
        raise ValueError('Combined test case did not pass')
    if sum(int(s.get('tests', '0')) for s in suites) != len(cases):
        raise ValueError('Combined receipt count disagrees with its test cases')
    return len(cases)


def verify(import_run, tests):
    import_run = Path(import_run).resolve()
    if not any(import_run.is_relative_to(ROOT / p) for p in ('tmp', 'data/processed/thermal_m50t')):
        raise ValueError('Use a local development import under tmp or data/processed/thermal_m50t')
    history = verify_history()
    receipt_path = ROOT / 'reports/thermal_m50t_import_v1/verification.json'
    receipt = read(receipt_path)
    if receipt['status'] not in ('passed', 'verified'):
        raise ValueError('Engineering receipt did not pass')
    for name, expected in receipt['artifacts_sha256'].items():
        if sha(ROOT / name) != expected:
            raise ValueError('Changed engineering artifact: ' + name)
    replay = subprocess.run([sys.executable, '-B', str(ROOT / 'scripts/import_thermal_m50t_development.py'),
                             '--verify', str(Path(import_run).resolve())], cwd=ROOT,
                            check=True, capture_output=True, text=True)
    result = json.loads(replay.stdout)
    if result.get('status') not in ('passed', 'verified'):
        raise ValueError('Development import replay did not verify')
    manifest = read(import_run / 'manifest.json')
    expected_members = {'M50/M50_50SOC_20deg_cell1_test103.txt',
                        'M50/M50_50SOC_20deg_cell1_test103.mat',
                        'M50/Electrical/M50_50SOC_20deg_cell1_test103_CF8.txt'}
    if len(manifest['opened']) != 3 or set(manifest['opened']) != expected_members:
        raise ValueError('Import manifest exceeds the development member boundary')
    count = read_tests(tests)
    files = [p for folder in ('reports/thermal_m50t_handoff_v1', 'reports/thermal_m50t_import_v1')
             for p in (ROOT / folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts
             and p != REPORT / 'verification.json']
    files += [ROOT / name for name in ('README.md', 'THERMAL_DATA_READINESS.md',
        'scripts/verify_thermal_m50t_handoff.py', 'scripts/import_thermal_m50t_development.py',
        'tests/test_thermal_m50t_development.py')]
    return dict(schema='voltforge.thermal_m50t_handoff_verification/1', status='passed',
        **history, combined_tests=count, engineering_receipt_sha256=sha(receipt_path),
        development_replay=result, import_run=Path(import_run).resolve().relative_to(ROOT).as_posix(),
        assessment_records_opened=0, model_fitted=False,
        scope='Used development data; preservation and reproducibility checks, not experimental module accuracy',
        artifacts_sha256={p.relative_to(ROOT).as_posix():sha(p) for p in sorted(set(files))})


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--import-run', type=Path, required=True)
    parser.add_argument('--tests', type=Path, default=REPORT / 'tests.xml')
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    out = args.out.resolve()
    if out.exists() or not any(out.is_relative_to(ROOT / p) for p in ('tmp', 'reports/thermal_m50t_handoff_v1')):
        raise ValueError('Choose a fresh output under tmp or this handoff report')
    result = verify(args.import_run, args.tests)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    print(json.dumps({k:v for k,v in result.items() if k != 'artifacts_sha256'}, indent=2))


if __name__ == '__main__':
    main()
