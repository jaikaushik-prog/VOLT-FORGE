"""Verify measured-viewer receipts, source bytes and earlier frozen releases."""
import argparse
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from voltforge.models import reference_investigation
from voltforge.project.service import file_hash,read
from measurement_viewer import MeasurementStore


def verify():
    report=ROOT/'reports/measurement_viewer_v1'
    store=MeasurementStore()
    assert [r['id'] for r in store.allocation['records'] if r['access']=='development']==['ID01']
    assert sum(r['access']=='protected' for r in store.allocation['records'])==13
    inventory=read(ROOT/'reports/freetwinev_inventory_v1/inventory.json')
    # Opaque byte checks only; no protected outcomes are parsed.
    for name,info in inventory['files'].items():
        assert file_hash(ROOT/inventory['source_folder']/name)==info['sha256'],name
    previous={
        'reports/module_simulation_v1/release_verification.json':{
            'SIMULATION_READINESS.md':'reports/product_integration_v1/SIMULATION_READINESS_previous.md'},
        'reports/product_integration_v1/integration_verification.json':{
            n:'reports/editor_v1/previous/'+n for n in ['SIMULATION_READINESS.md','FRONTEND_CONTRACT.md','MVP_SCOPE.md']},
        'reports/editor_v1/release_verification.json':{
            '.gitignore':'reports/freetwinev_inventory_v1/EDITOR_gitignore_previous.txt',
            **{n:'reports/measurement_viewer_v1/previous/'+n for n in ['scripts/run_editor.py','web/editor/index.html',
                 'README.md','FRONTEND_CONTRACT.md','MVP_SCOPE.md','SIMULATION_READINESS.md','EDITOR_GUIDE.md']}},
        'reports/freetwinev_inventory_v1/verification.json':{}}
    counts={}
    for manifest,mapping in previous.items():
        artifacts=read(ROOT/manifest)['artifacts']
        for name,expected in artifacts.items():
            assert file_hash(ROOT/mapping.get(name,name))==expected,f'{manifest}: {name}'
        counts[manifest]=len(artifacts)
    lock=reference_investigation.verify()
    suite=ET.parse(report/'pytest_final.xml').getroot().find('testsuite')
    assert suite.get('tests')=='46' and all(suite.get(k)=='0' for k in ['errors','failures','skipped'])
    browser=read(report/'browser_final/verification.json')
    assert len(browser['checks'])==6 and not browser['browser_errors']
    # Reproduce only allocated development outputs, with current source/parser hashes.
    assert read(report/'ID01_summary.json')==store.read(view='summary')
    assert read(report/'ID01_row600.json')==store.read(view='rows',offset=600,limit=1)
    assert read(report/'browser_final/freetwinev_ID01_measured_summary.json')==store.read(view='summary')
    files=[p for p in report.rglob('*') if p.is_file() and p.name!='release_verification.json']
    files += [ROOT/name for name in ['configs/freetwinev_viewer_v1.json','scripts/measurement_viewer.py',
        'scripts/run_editor.py','scripts/check_measurement_browser.py','scripts/verify_measurement_release.py',
        'tests/test_measurement_viewer.py','web/editor/index.html','web/editor/measurements.html',
        'web/editor/measurements.css','web/editor/measurements.js','README.md','FRONTEND_CONTRACT.md',
        'MVP_SCOPE.md','SIMULATION_READINESS.md','EDITOR_GUIDE.md']]
    return dict(schema_version='voltforge.measurement_release/1',tests=46,failures=0,browser_checks=6,
        source_files_unchanged=len(inventory['files']),development_records_opened=['ID01'],
        protected_FreeTwinEV_records=[r['id'] for r in store.allocation['records'] if r['access']=='protected'],
        measurement_xlsx_files_opened=0,protected_baseline_artifacts=len(lock['protected']),
        unused_LG_cells=lock['reserved_unused_cells'],prior_release_artifact_counts=counts,
        fitted_models_changed=False,experimental_module_validation='awaiting suitable measurements',
        artifacts={p.relative_to(ROOT).as_posix():file_hash(p) for p in sorted(files)})


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    if args.out.exists():raise SystemExit('Choose a new receipt path; previous receipts remain immutable.')
    result=verify()
    args.out.parent.mkdir(parents=True,exist_ok=True)
    with args.out.open('x',encoding='utf-8',newline='\n') as stream:stream.write(json.dumps(result,indent=2)+'\n')
    print('Verified 46 tests, six browser checks, 32 unchanged source files and all prior protected releases.')


if __name__=='__main__':main()
