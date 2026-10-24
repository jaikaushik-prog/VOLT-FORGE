"""Verify editor software evidence and every previous scientific release without opening fresh measurements."""
import argparse
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from voltforge.models import reference_investigation
from voltforge.project import Project
from voltforge.project.service import file_hash, read, verify_files


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=ROOT/'reports/editor_v1/release_verification.json')
    args = parser.parse_args()
    if args.out.exists():
        raise SystemExit('Choose a new verification output path; release records are preserved.')
    lock = reference_investigation.verify()  # hashes only, including original archive
    module = read(ROOT/'reports/module_simulation_v1/release_verification.json')
    previous = read(ROOT/'reports/product_integration_v1/integration_verification.json')
    for name, expected in module['artifacts'].items():
        path = ROOT / name if name != 'SIMULATION_READINESS.md' else ROOT/'reports/product_integration_v1/SIMULATION_READINESS_previous.md'
        assert file_hash(path) == expected, name
    moved = {'SIMULATION_READINESS.md','FRONTEND_CONTRACT.md','MVP_SCOPE.md'}
    for name, expected in previous['artifacts'].items():
        path = ROOT / name if name not in moved else ROOT/'reports/editor_v1/previous'/name
        assert file_hash(path) == expected, name
    demo = ROOT/'reports/product_integration_v1/demo'
    verify_files(demo, read(demo/'demo_manifest.json')['artifacts'])
    project = Project(demo/'project')
    for selection in read(demo/'demo_result.json')['selections']:
        assert project.get_run(**selection)['freshness'] == 'current'
    out = ROOT/'reports/editor_v1'
    suite = ET.parse(out/'pytest.xml').getroot().find('testsuite')
    assert int(suite.get('tests')) >= 117
    assert all(suite.get(key) == '0' for key in ['errors','failures','skipped'])
    final_transport = ET.parse(out/'transport_final_pytest.xml').getroot().find('testsuite')
    assert int(final_transport.get('tests')) == 17
    assert all(final_transport.get(key) == '0' for key in ['errors','failures','skipped'])
    browser = read(out/'browser_acceptance/verification.json')
    assert browser['status'] == 'passed' and not browser['browser_errors']
    assert len(browser['replays']) == 2 and all(x['reproduced'] for x in browser['replays'])
    assert len(browser['observations']) >= 9
    node = (out/'node_tests.txt').read_text(encoding='utf-8')
    assert '# pass 4' in node and '# fail 0' in node
    files = list((ROOT/'web/editor').glob('*')) + list((out/'previous').glob('*')) + list((out/'browser_acceptance').glob('*'))
    files += [ROOT/p for p in ['scripts/run_editor.py','scripts/check_editor_browser.py','scripts/verify_editor_release.py',
        'scripts/prepare_github_upload.py','tests/test_editor_server.py','tests/editor_state.test.mjs',
        'EDITOR_PLAN.md','EDITOR_GUIDE.md','FRONTEND_CONTRACT.md','MVP_SCOPE.md','SIMULATION_READINESS.md','README.md','.gitignore',
        'reports/editor_v1/pytest.xml','reports/editor_v1/node_tests.txt','reports/editor_v1/VERIFICATION.md']]
    files += [out/'partial_result_pytest.xml',out/'transport_pytest.xml',out/'transport_final_pytest.xml']
    report = dict(python_tests=int(suite.get('tests')), javascript_tests=4, browser_observations=len(browser['observations']),
        browser_replayed_runs=2, failures=0, protected_baseline_artifacts=len(lock['protected']),
        previous_module_artifacts_verified=len(module['artifacts']), previous_product_artifacts_verified=len(previous['artifacts']),
        original_archive_hash_verified=True,unused_cells=lock['reserved_unused_cells'],
        fresh_measurement_outcomes_opened=[],electrical_source_changed=False,
        experimental_validation='awaiting suitable measurements',
        preserved_document_locations={name:'reports/editor_v1/previous/'+name for name in sorted(moved)},
        artifacts={p.relative_to(ROOT).as_posix():file_hash(p) for p in files if p.is_file()})
    args.out.parent.mkdir(parents=True,exist_ok=True)
    with args.out.open('x',encoding='utf-8',newline='\n') as stream:
        stream.write(json.dumps(report,indent=2)+'\n')
    print(f"Verified {report['python_tests']} Python + 4 presentation tests, 9 browser checks, two replays and all protected releases.")


if __name__=='__main__':
    main()
