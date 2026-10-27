"""Verify the local v1 software release evidence without fitting or opening raw outcomes.

Run after pytest has written reports/v1_release/pytest.xml and the browser check has
written browser/verification.json. Rechecks the small Node suite and frozen hashes.
"""
import hashlib
import json
import subprocess
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'reports/v1_release'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    suites = ET.parse(OUT/'pytest.xml').getroot().findall('testsuite')
    counts = {key: sum(int(s.get(key, '0')) for s in suites)
              for key in ['tests', 'failures', 'errors', 'skipped']}
    assert counts['tests'] > 0 and counts['failures'] == counts['errors'] == 0, counts
    counts['passed'] = counts['tests']-counts['skipped']
    junit_time = (OUT/'pytest.xml').stat().st_mtime
    for folder in ['src', 'tests']:
        assert all(p.stat().st_mtime <= junit_time for p in (ROOT/folder).rglob('*.py')), 'Python source changed after pytest'
    node_command = ['node', '--test', 'tests/editor_state.test.mjs', 'tests/assembly.test.mjs', 'tests/panels.test.mjs', 'tests/workspace.test.mjs']
    node = subprocess.run(node_command, cwd=ROOT, text=True, capture_output=True)
    (OUT/'node-tests.tap').write_text(node.stdout+node.stderr)
    assert node.returncode == 0, node.stdout+node.stderr
    node_counts = {key: int(next(line.split()[-1] for line in node.stdout.splitlines()
                               if line.startswith('# '+key+' '))) for key in ['tests', 'pass', 'fail', 'skipped']}
    syntax = subprocess.run(['node', '--check', '--input-type=module'], cwd=ROOT,
                            input=(ROOT/'web/editor/app.js').read_text(), text=True, capture_output=True)
    assert syntax.returncode == 0, syntax.stderr
    protected = []
    for name, key in [('reports/module_simulation_v1/manifest.json', 'declared_inputs'),
                      ('configs/reference_initial_state_v1.lock.json', 'protected'),
                      ('reports/improvement_v2/procedure_seal.json', 'artifacts')]:
        hashes = json.loads((ROOT/name).read_text())[key]
        bad = [p for p, expected in hashes.items() if not (ROOT/p).is_file() or digest(ROOT/p) != expected]
        assert not bad, (name, bad)
        protected.append(dict(manifest=name, files=len(hashes), status='PASS'))
    browser = json.loads((OUT/'browser/verification.json').read_text())
    assert browser['status'] == 'PASS' and all(c['status'] == 'PASS' for c in browser['checks'])
    refinement = json.loads((ROOT/'reports/ui_cleanup/final_render_checks.json').read_text())
    forms = json.loads((ROOT/'reports/ui_cleanup/form_binding_checks.json').read_text())
    for evidence in [refinement, forms]:
        assert evidence['status'] == 'PASS' and all(c['status'] == 'PASS' for c in evidence['checks'])
    assert all(digest(ROOT/name)==expected for name,expected in refinement['source_sha256'].items()), 'Rendered source changed after the final UI check'
    checkpoints = sorted(p for folder in ['src', 'web/editor', 'tests'] for p in (ROOT/folder).rglob('*')
                         if p.is_file() and p.suffix in ('.py', '.js', '.mjs', '.html', '.css'))
    report = dict(status='PASS', date_utc=datetime.now(timezone.utc).isoformat(),
        scope='Software/numerical/UI reproduction only; not experimental validation',
        python=counts, javascript=node_counts, app_module_syntax='PASS', protected_artifacts=protected,
        browser_checks=len(browser['checks']), exported_replays='electrical and thermal, two runs',
        final_render_checks=len(refinement['checks']), property_input_checks=len(forms['checks']),
        source_sha256={p.relative_to(ROOT).as_posix():digest(p) for p in checkpoints},
        empirical_validation=False, new_model_fitting=False,
        independent_review='Previous findings repaired and regression-tested; no new cold review claimed',
        git_head=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        git_branch=subprocess.check_output(['git', 'branch', '--show-current'], cwd=ROOT, text=True).strip())
    (OUT/'release_verification.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({k: report[k] for k in ['status', 'scope', 'python', 'javascript', 'protected_artifacts', 'browser_checks', 'final_render_checks', 'property_input_checks']}, indent=2))


if __name__ == '__main__':
    main()
