"""Create a curated local GitHub upload copy; never publish or modify originals."""
from pathlib import Path
import hashlib
import json
import re
import shutil
from zipfile import ZipFile, ZIP_DEFLATED

ROOT=Path(__file__).resolve().parents[1]
DEST=ROOT/'github-upload'/'volt-forge'
FOLDERS=['src','scripts','tests','configs','reports']
ROOT_FILES=['.gitignore','.gitattributes','ATTRIBUTION.md','DATA_READINESS.md',
    'MODELLING_DECISION.md','MODEL_IMPROVEMENT_DECISION.md','MODEL_IMPROVEMENT_PLAN.md',
    'REFERENCE_INITIAL_STATE_PLAN.md','REFERENCE_INITIAL_STATE_DECISION.md','README.md',
    'SIMULATION_PLAN.md','SIMULATION_READINESS.md','MEASUREMENT_IMPORT_SPEC.md',
    'VOLT_FORGE_Codex_Start_Here.txt','pyproject.toml','requirements.txt','GITHUB_UPLOAD.md']


def main():
    files=[ROOT/n for n in ROOT_FILES if (ROOT/n).exists()]
    for folder in FOLDERS:
        files.extend(p for p in (ROOT/folder).rglob('*') if p.is_file()
            and not any(x in p.parts for x in ['__pycache__','.pytest_cache','.git'])
            and not (p.suffix=='.csv' and 'improvement_v2' in p.parts and ('predictions' in p.name or 'software_coupling' in p.parts))
            and p.suffix not in ['.pyc','.zip','.pem','.key'])
    files=sorted(set(files))
    token=re.compile(rb'(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)')
    for p in files:
        if token.search(p.read_bytes()):
            raise ValueError('Potential credential found; inspect locally: '+str(p.relative_to(ROOT)))
    DEST.mkdir(parents=True,exist_ok=True)
    entries=[]
    for p in files:
        rel=p.relative_to(ROOT);target=DEST/rel;target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(p,target)
        entries.append(dict(path=rel.as_posix(),bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
    manifest=ROOT/'github-upload'/'upload_manifest.json'
    manifest.write_text(json.dumps(entries,indent=2)+'\n',encoding='utf-8')
    archive=ROOT/'github-upload'/'volt-forge-github-upload.zip'
    with ZipFile(archive,'w',ZIP_DEFLATED) as z:
        for p in files: z.write(DEST/p.relative_to(ROOT),Path('volt-forge')/p.relative_to(ROOT))
    print(f'Prepared {len(files)} files ({sum(e["bytes"] for e in entries)/2**20:.1f} MiB uncompressed).')
    print(archive)
    print('No remote repository created and no upload performed.')


if __name__=='__main__': main()
