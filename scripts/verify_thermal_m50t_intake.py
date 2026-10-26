"""Replay the bounded intake and verify prior source hashes without new assessments."""
import argparse
import importlib.metadata
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from intake_thermal_m50t import build, digest
from probe_thermal_m50t_schema import probe
from voltforge.project.service import software

REPORT = ROOT / 'reports/thermal_m50t_intake_v1'


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def verify():
    inventory = build()
    if inventory != read(REPORT / 'inventory.json'):
        raise ValueError('Inventory/allocation replay mismatch')
    schema = probe()
    if schema != read(REPORT / 'development_schema_003.json'):
        raise ValueError('Corrected development schema replay mismatch')
    if schema['assessment_members_opened'] != 0 or len(schema['opened_development_members']) != 3:
        raise ValueError('Unexpected probe access scope')
    sources = read(REPORT / 'sources.json')
    for source in sources['sources']:
        if digest(ROOT / source['local_path']) != source['sha256']:
            raise ValueError('Changed raw/document source: ' + source['kind'])
    prior_path = ROOT / 'reports/assistant_thermal_v1/verification.json'
    prior = read(prior_path)
    for name, expected in prior['artifacts_sha256'].items():
        if digest(ROOT / name) != expected:
            raise ValueError('Changed preceding release artifact: ' + name)
    snapshot = read(ROOT / 'reports/local_assistant_integration_v1/backend/demo_002/project/runs/run_0001/snapshot.json')
    expected_software = snapshot['software']
    if software() != expected_software:
        raise ValueError('Frozen electrical source/runtime differs from the last saved demonstration')
    suites = ET.parse(REPORT / 'tests_001.xml').getroot().findall('testsuite')
    if not suites or any(int(s.get(k, '0')) for s in suites for k in ('failures', 'errors', 'skipped')):
        raise ValueError('The focused test receipt is not clean')
    count = sum(int(s.get('tests', '0')) for s in suites)
    if count != 65:
        raise ValueError('Unexpected focused test count')
    code = ['THERMAL_DATA_READINESS.md', 'configs/thermal_m50t_allocation_v1.json',
            'scripts/intake_thermal_m50t.py', 'scripts/probe_thermal_m50t_schema.py',
            'scripts/verify_thermal_m50t_intake.py', 'tests/test_thermal_m50t_intake.py']
    files = [ROOT / name for name in code]
    files += [p for p in REPORT.rglob('*') if p.is_file() and '__pycache__' not in p.parts
              and p != REPORT / 'verification.json']
    return dict(schema='voltforge.thermal_m50t_intake_verification/1', status='passed',
        focused_tests=count, new_intake_probe_tests=26, existing_synthetic_thermal_tests=39,
        inventory_replayed=True, development_schema_replayed=True,
        used_development_families=['cell_1_test_103'], unopened_measurement_members=30,
        unopened_assessment_families=6, assessment_members_opened=0,
        prior_release_artifacts_unchanged=len(prior['artifacts_sha256']),
        prior_receipt_sha256=digest(prior_path), frozen_software_id=expected_software['id'],
        runtime={name:importlib.metadata.version(name) for name in ['scipy', 'h5py']},
        thermal_model_fitted=False, electrical_model_changed=False,
        historic_probe_exposure='One initial development row in attempt 002; preserved and corrected, no assessment exposure',
        experimental_module_validation='awaiting suitable measurements',
        artifacts_sha256={p.relative_to(ROOT).as_posix():digest(p) for p in sorted(files)})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    out = args.out.resolve()
    if out.exists() or not any(out.is_relative_to(ROOT / p) for p in ('tmp', 'reports/thermal_m50t_intake_v1')):
        raise ValueError('Choose a fresh output under tmp or the intake report')
    result = verify()
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    print(json.dumps({k:v for k,v in result.items() if k != 'artifacts_sha256'}, indent=2))


if __name__ == '__main__':
    main()
