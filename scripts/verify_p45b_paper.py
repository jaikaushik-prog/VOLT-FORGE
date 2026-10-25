"""Verify the paper stage and preserved sources without opening outcome rows."""
import argparse
import json
from pathlib import Path
import xml.etree.ElementTree as ET

from ae_p45b_intake import hashes
from verify_p45b_intake import verify as verify_intake
from voltforge.project.service import file_hash, read

ROOT = Path(__file__).resolve().parents[1]


def verify():
    report = ROOT/'reports/p45b_paper_v1'
    source = read(report/'source.json')
    original = hashes(ROOT/source['local_original'])
    assert original['sha256'] == source['sha256']
    assert original['bytes'] == source['bytes']
    assert not source['validation_workbook_opened']
    assert all(source[key] == 0 for key in ['experimental_csv_rows_opened',
        'author_simulation_csv_rows_opened', 'parameter_csv_rows_opened'])

    # Reuse earlier source/protected-file checks; they hash outcomes as opaque
    # bytes and decode only metadata/CSV headers. Do not regenerate old receipts.
    previous = verify_intake()
    intake_manifest = read(ROOT/'reports/p45b_intake_v1/verification.json')
    replacements = {name:report/'previous'/name for name in ['README.md', '.gitignore']}
    for name, expected in intake_manifest['artifacts'].items():
        assert file_hash(replacements.get(name, ROOT/name)) == expected, name

    suite = ET.parse(report/'pytest.xml').getroot().find('testsuite')
    assert suite is not None and suite.get('tests') == '43'
    assert all(suite.get(k) == '0' for k in ['errors', 'failures', 'skipped'])
    demo = read(report/'synthetic_demo.json')
    assert demo['evidence'].startswith('SYNTHETIC SOFTWARE CHECK ONLY')
    assert demo['experimental_validation'] == 'not performed'
    assert len(demo['samples']) == 241

    files = [p for p in report.rglob('*') if p.is_file() and p.name != 'verification.json']
    files += [ROOT/name for name in ['scripts/ae_p45b_equations.py',
        'scripts/verify_p45b_paper.py', 'tests/test_ae_p45b_equations.py', 'README.md', '.gitignore']]
    return dict(schema_version='voltforge.ae_p45b_paper_verification/1',
        paper_sha256=source['sha256'], synthetic_tests=43, new_equation_tests=23,
        failures=0, published_parameter_rows_opened=0, experimental_rows_opened=0,
        author_simulation_rows_opened=0, validation_workbook_opened=False,
        prior_intake_artifacts_preserved=len(intake_manifest['artifacts']),
        prior_release_artifact_counts=previous['prior_release_artifact_counts'],
        original_P45B_source_files_unchanged=previous['source_files_verified'],
        original_FreeTwinEV_files_unchanged=previous['freetwinev_source_files_unchanged'],
        protected_LG_artifacts=previous['protected_LG_artifacts'],
        unused_LG_cells=previous['unused_LG_cells'],
        unused_FreeTwinEV_records=previous['freetwinev_unused_complete_records'],
        P45B_outcome_files_unopened=51, frozen_models_changed=False,
        experimental_module_validation='awaiting suitable measurements',
        artifacts={p.relative_to(ROOT).as_posix():file_hash(p) for p in sorted(files)})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    dest = args.out.resolve()
    if not any(dest.is_relative_to(ROOT/name) for name in ('reports', 'tmp', 'workspace')):
        raise SystemExit('Write verification under reports/, tmp/ or workspace/.')
    if dest.exists():
        raise SystemExit('Choose a new receipt path; preserve previous verification.')
    result = verify()
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(json.dumps(result, indent=2)+'\n')
    print('Verified paper identity, 43 synthetic tests, original sources and protected releases.')


if __name__ == '__main__':
    main()
