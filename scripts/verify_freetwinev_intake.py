"""Verify downloaded bytes, unused measurement records and prior release preservation."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import sys
import xml.etree.ElementTree as ET
from zipfile import ZipFile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from voltforge.models import reference_investigation
from voltforge.project.service import file_hash,read


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive',type=Path,required=True)
    parser.add_argument('--out',type=Path,default=ROOT/'reports/freetwinev_inventory_v1/verification.json')
    args=parser.parse_args()
    if args.out.exists():raise SystemExit('Choose a new output path to preserve evidence')
    report=ROOT/'reports/freetwinev_inventory_v1'
    inventory=read(report/'inventory.json')
    source=ROOT/inventory['source_folder']
    md5=hashlib.md5()
    with args.archive.open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):md5.update(block)
    assert md5.hexdigest()=='dea7c0e8c7146f517d71979ac546249d','Archive differs from published Zenodo v1 checksum'
    matched=set()
    with ZipFile(args.archive) as archive:
        for info in archive.infolist():
            if info.is_dir():continue
            parts=PurePosixPath(info.filename).parts
            if parts[0]==source.name:parts=parts[1:]
            name=PurePosixPath(*parts).as_posix()
            assert name in inventory['files'],name
            digest=hashlib.sha256()
            with archive.open(info) as stream:
                for block in iter(lambda:stream.read(1024*1024),b''):digest.update(block)
            assert digest.hexdigest()==inventory['files'][name]['sha256']==file_hash(source/name),name
            matched.add(name)
    assert matched==set(inventory['files'])
    assert inventory['outcome_rows_interpreted']==0 and inventory['measurement_xlsx_files_opened']==0
    assert all(r['protocol_matches'] and r['xlsx_exists'] for r in inventory['records'])
    # Verify prior artifacts, resolving explicitly preserved versions of living docs.
    preserved={
        'reports/module_simulation_v1/release_verification.json':{
            'SIMULATION_READINESS.md':'reports/product_integration_v1/SIMULATION_READINESS_previous.md'},
        'reports/product_integration_v1/integration_verification.json':{
            name:'reports/editor_v1/previous/'+name for name in ['SIMULATION_READINESS.md','FRONTEND_CONTRACT.md','MVP_SCOPE.md']},
        'reports/editor_v1/release_verification.json':{
            '.gitignore':'reports/freetwinev_inventory_v1/EDITOR_gitignore_previous.txt'}}
    counts={}
    for manifest,mapping in preserved.items():
        artifacts=read(ROOT/manifest)['artifacts']
        for name,expected in artifacts.items():assert file_hash(ROOT/mapping.get(name,name))==expected,name
        counts[manifest]=len(artifacts)
    lock=reference_investigation.verify()  # Original archive/protected bytes only, no new decoded outcomes.
    suite=ET.parse(report/'pytest.xml').getroot().find('testsuite')
    assert suite.get('tests')=='5' and all(suite.get(k)=='0' for k in ['errors','failures','skipped'])
    files=[report/'inventory.json',report/'ASSESSMENT.md',report/'pytest.xml',report/'EDITOR_gitignore_previous.txt',
        ROOT/'.gitignore',ROOT/'scripts/inventory_freetwinev.py',ROOT/'scripts/verify_freetwinev_intake.py',ROOT/'tests/test_freetwinev_inventory.py']
    result=dict(archive_name=args.archive.name,archive_md5=md5.hexdigest(),archive_sha256=file_hash(args.archive),
        published_Zenodo_v1_md5_matches=True,extracted_files_match_archive=len(matched),
        prior_release_artifact_counts=counts,protected_baseline_artifacts=len(lock['protected']),
        original_LG_archive_verified=True,unused_LG_cells=lock['reserved_unused_cells'],
        outcome_rows_interpreted=0,new_complete_records_retained=inventory['record_count'],tests=5,failures=0,
        experimental_module_validation='awaiting suitable measurements',
        artifacts={p.relative_to(ROOT).as_posix():file_hash(p) for p in files})
    args.out.parent.mkdir(parents=True,exist_ok=True)
    with args.out.open('x',encoding='utf-8',newline='\n') as stream:stream.write(json.dumps(result,indent=2)+'\n')
    print(f'Verified published ZIP checksum, {len(matched)} unchanged source files, five tests and all prior protected releases.')


if __name__=='__main__':main()
