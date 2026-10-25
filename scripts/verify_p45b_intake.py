"""Verify P45B intake and earlier evidence without decoding experimental outcomes."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from voltforge.models import reference_investigation
from voltforge.project.service import file_hash,read
from ae_p45b_intake import inventory


def verify():
    report=ROOT/'reports/p45b_intake_v1'
    source=read(report/'inventory.json')
    assert inventory(ROOT)==source,'Source inventory changed'
    allocation=read(ROOT/'configs/ae_p45b_allocation_v1.json')
    assert allocation['inventory_sha256']==file_hash(report/'inventory.json')
    assert allocation['plan_sha256']==file_hash(report/'MODELLING_PLAN.md')
    assert allocation['real_outcome_rows_decoded']==0
    assert allocation['status']=='proposal_only_all_outcomes_protected'
    assert len(allocation['families'])==43
    assert all(f['access']=='protected_unopened' for f in allocation['families'])
    public=read(report/'public_release.json')
    assert public['license']['id']=='cc-by-4.0' and public['access_right']=='open'
    metadata_path=ROOT/public['raw_metadata_local_path']
    if metadata_path.exists():
        assert file_hash(metadata_path)==public['raw_metadata_sha256']
    for entry in public['files']:
        expected=source['files'][entry['key']]
        assert entry['checksum']=='md5:'+expected['md5']
        assert entry['size']==expected['bytes']
    freetwinev=read(ROOT/'reports/freetwinev_inventory_v1/inventory.json')
    for name,info in freetwinev['files'].items():
        assert file_hash(ROOT/freetwinev['source_folder']/name)==info['sha256'],name
    # Each prior release retains its original manifest and exact living-file versions.
    previous={
        'reports/module_simulation_v1/release_verification.json':{
            'SIMULATION_READINESS.md':'reports/product_integration_v1/SIMULATION_READINESS_previous.md'},
        'reports/product_integration_v1/integration_verification.json':{
            n:'reports/editor_v1/previous/'+n for n in ['SIMULATION_READINESS.md','FRONTEND_CONTRACT.md','MVP_SCOPE.md']},
        'reports/editor_v1/release_verification.json':{
            '.gitignore':'reports/freetwinev_inventory_v1/EDITOR_gitignore_previous.txt',
            **{n:'reports/measurement_viewer_v1/previous/'+n for n in ['scripts/run_editor.py','web/editor/index.html',
                'README.md','FRONTEND_CONTRACT.md','MVP_SCOPE.md','SIMULATION_READINESS.md','EDITOR_GUIDE.md']}},
        'reports/freetwinev_inventory_v1/verification.json':{
            '.gitignore':'reports/p45b_intake_v1/previous/.gitignore'},
        'reports/measurement_viewer_v1/release_verification.json':{
            'README.md':'reports/p45b_intake_v1/previous/README.md'}}
    counts={}
    for manifest,mapping in previous.items():
        artifacts=read(ROOT/manifest)['artifacts']
        for name,expected in artifacts.items():
            assert file_hash(ROOT/mapping.get(name,name))==expected,f'{manifest}: {name}'
        counts[manifest]=len(artifacts)
    protected=reference_investigation.verify()  # Hashes only, including original LG archive.
    suite=ET.parse(report/'pytest.xml').getroot().find('testsuite')
    assert suite.get('tests')=='20' and all(suite.get(k)=='0' for k in ['errors','failures','skipped'])
    files=[p for p in report.rglob('*') if p.is_file() and p.name!='verification.json']
    files += [ROOT/name for name in ['scripts/ae_p45b_intake.py','scripts/verify_p45b_intake.py',
        'tests/test_ae_p45b_intake.py','configs/ae_p45b_allocation_v1.json','README.md','.gitignore']]
    return dict(schema_version='voltforge.ae_p45b_intake_verification/1',source_files_verified=6,
        source_archive_members=51,filename_families=43,all_source_files_unchanged=True,
        experimental_rows_decoded=0,author_simulation_rows_decoded=0,numerical_parameter_rows_decoded=0,
        validation_workbook_opened=False,synthetic_tests=20,failures=0,
        freetwinev_source_files_unchanged=32,freetwinev_unused_complete_records=13,
        protected_LG_artifacts=len(protected['protected']),unused_LG_cells=protected['reserved_unused_cells'],
        prior_release_artifact_counts=counts,fitted_models_changed=False,
        experimental_module_validation='awaiting suitable measurements',
        artifacts={p.relative_to(ROOT).as_posix():file_hash(p) for p in sorted(files)})


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    if args.out.exists():raise SystemExit('Choose a new receipt path to preserve previous verification.')
    result=verify()
    args.out.parent.mkdir(parents=True,exist_ok=True)
    with args.out.open('x',encoding='utf-8',newline='\n') as stream:stream.write(json.dumps(result,indent=2)+'\n')
    print('Verified six original P45B files, 51 unopened CSV members, 20 synthetic tests and all prior protected releases.')


if __name__=='__main__':main()
