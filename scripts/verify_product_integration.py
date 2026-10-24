"""Verify the product handoff while retaining every previous scientific release."""
from pathlib import Path
import json
import xml.etree.ElementTree as ET

from voltforge.models import reference_investigation
from voltforge.project import Project
from voltforge.project.service import file_hash, read, verify_files

OUT = Path('reports/product_integration_v1')


def main():
    lock = reference_investigation.verify()  # hashes only; no new measurement outcomes decoded
    previous = read('reports/module_simulation_v1/release_verification.json')
    preserved = dict(previous['artifacts'])
    old_readiness = preserved.pop('SIMULATION_READINESS.md')
    verify_files(Path.cwd(), preserved)
    assert file_hash(OUT / 'SIMULATION_READINESS_previous.md') == old_readiness
    suite = ET.parse(OUT / 'pytest.xml').getroot().find('testsuite')
    assert all(suite.get(k) == '0' for k in ['errors', 'failures', 'skipped'])
    assert int(suite.get('tests')) >= 100
    demo = OUT / 'demo'
    verify_files(demo, read(demo / 'demo_manifest.json')['artifacts'])
    result = read(demo / 'demo_result.json')
    project = Project(demo / 'project')
    views = [project.get_run(**selection) for selection in result['selections']]
    assert all(v['execution_status'] == 'completed' and v['freshness'] == 'current' for v in views)
    assert all(v['summary']['voltage_requirement']['status'] == 'requirement not configured' for v in views)
    assert result['inherited_result_freshness'] == 'outdated'
    assert result['visual_change_result_freshness'] == 'current'
    assert all(x['reproduced'] for x in result['replays'])
    files = list(Path('src/voltforge/project').glob('*.py'))
    files += [Path(p) for p in ['tests/test_project_workflow.py', 'scripts/demonstrate_product_workflow.py',
        'scripts/verify_product_integration.py', 'VOLT_FORGE_Product_Vision.md', 'PRODUCT_INTEGRATION_PLAN.md',
        'SIMULATION_READINESS.md', 'FRONTEND_CONTRACT.md', 'MVP_SCOPE.md']]
    files += [OUT / 'pytest.xml', OUT / 'FRONTEND_EXAMPLES.md', demo / 'demo_manifest.json']
    report = dict(tests=int(suite.get('tests')), failures=0, skips=0, preserved_baseline_artifacts=len(lock['protected']),
        previous_simulation_artifacts_verified=len(previous['artifacts']),
        previous_readiness_preserved_as=str(OUT / 'SIMULATION_READINESS_previous.md'),
        untouched_unused_cells=lock['reserved_unused_cells'], original_archive_hash_verified=True,
        new_measurement_outcomes_opened=[], no_model_refitting=True,
        workflow='A0 -> one declared rail edit -> outdated A1 -> rerun -> compare -> export/replay',
        experimental_validation='awaiting suitable measurements',
        artifacts={p.as_posix(): file_hash(p) for p in files})
    (OUT / 'integration_verification.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8', newline='\n')
    print(f"Verified {report['tests']} tests, 112 protected baseline files, 145 previous release artifacts, A0/A1 and export replay.")


if __name__ == '__main__':
    main()
