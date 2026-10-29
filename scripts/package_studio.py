"""Create a deterministic local source bundle, without raw data or user projects.

Only Git-indexed source/reference files and explicitly selected evidence enter it.
The bundle is a candidate until the separate clean-install check has passed.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def build(output, evidence=None):
    if output.exists():
        raise ValueError('Choose a new bundle path; existing releases are preserved.')
    names = subprocess.check_output(['git', 'ls-files', '-z'], cwd=ROOT).decode().split('\0')
    files = {}
    for name in names:
        if not name or name.endswith('.zip'):
            continue
        path = ROOT / name
        if path.is_symlink() or not path.is_file():
            raise ValueError('A release input is missing or is a symlink: ' + name)
        if (name.startswith(('.env', 'data/raw/', 'workspace/', '.codex/', '.agents/'))
                or path.suffix in ('.pem', '.key')):
            raise ValueError('A private/local file is present in the release index: ' + name)
        files[name] = path.read_bytes()
    if evidence:
        selections = json.loads(evidence.read_text())
        for target, source in selections.items():
            relative = Path(target)
            if relative.is_absolute() or '..' in relative.parts or not target.startswith('evidence/'):
                raise ValueError('Evidence must have a relative path under evidence/.')
            if target in files:
                raise ValueError('Duplicate release file: ' + target)
            path = ROOT / source
            if not path.resolve().is_relative_to(ROOT) or not path.is_file() or path.is_symlink():
                raise ValueError('Evidence must be an existing file inside this checkout.')
            files[target] = path.read_bytes()
    hashes = {name: hashlib.sha256(value).hexdigest() for name, value in sorted(files.items())}
    tree_hash = hashlib.sha256(json.dumps(hashes, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    manifest = dict(version='voltforge.source-bundle/1', status='Candidate; verify its clean-install record',
                    git_head=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT).decode().strip(),
                    content_sha256=tree_hash, files=hashes,
                    raw_data_included=False, user_projects_included=False, credentials_included=False)
    files['BUNDLE_MANIFEST.json'] = (json.dumps(manifest, indent=2) + '\n').encode()
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for name, body in sorted(files.items()):
            entry = zipfile.ZipInfo('VOLT-FORGE-v3/' + name, date_time=(2026, 1, 1, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.external_attr = 0o100644 << 16
            archive.writestr(entry, body)
    checksum = hashlib.sha256(output.read_bytes()).hexdigest()
    output.with_suffix(output.suffix + '.sha256').write_text(checksum + '  ' + output.name + '\n')
    print(json.dumps(dict(bundle=str(output), bytes=output.stat().st_size, files=len(files),
                          sha256=checksum, content_sha256=tree_hash), indent=2))
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--evidence', type=Path)
    args = parser.parse_args()
    build(args.out.resolve(), args.evidence.resolve() if args.evidence else None)
