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


def build(output, evidence=None, verification=None):
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
    verified = None
    if verification:
        proof = json.loads(verification.read_text())
        if (proof.get('status') != 'passed' or proof.get('dependency_install_returncode') != 0
                or proof.get('full_suite_returncode') != 0 or proof.get('pip_check_returncode') != 0
                or not proof.get('lock_matches_installed_environment')
                or not proof.get('browser_checks_passed') or proof.get('browser_export_replay_returncode') != 0):
            raise ValueError('The clean installation, browser workflow and replay must pass before release packaging.')
        candidate = Path(proof['bundle'])
        if hashlib.sha256(candidate.read_bytes()).hexdigest() != proof['bundle_sha256']:
            raise ValueError('The clean-install candidate no longer matches its recorded hash.')
        with zipfile.ZipFile(candidate) as archive:
            original = json.loads(archive.read('VOLT-FORGE-v3/BUNDLE_MANIFEST.json'))
        # Documentation, the complete dependency lock and this packaging tool
        # can be finalized after the application was exercised. Every existing
        # runtime, test, source-model and evidence input must remain identical.
        permitted = {'README.md', 'V3_RELEASE.md', 'scripts/package_studio.py'}
        changed = [name for name, wanted in original['files'].items()
                   if hashes.get(name) != wanted and name not in permitted]
        if changed:
            raise ValueError('Recheck changed release inputs before packaging: ' + ', '.join(changed[:8]))
        lock = [s.lower().replace('_', '-') for s in files['requirements-lock.txt'].decode().splitlines()
                if s and not s.startswith('#')]
        installed = [s.lower().replace('_', '-') for s in proof['distributions']]
        if sorted(lock) != sorted(installed):
            raise ValueError('The final dependency lock differs from the exercised environment.')
        verified = dict(record_sha256=hashlib.sha256(verification.read_bytes()).hexdigest(),
                        installed_candidate_sha256=proof['bundle_sha256'],
                        unchanged_captured_inputs=len(original['files'])-len(permitted),
                        permitted_postcheck_changes=sorted(permitted))
    manifest = dict(version='voltforge.source-bundle/1',
                    status='Round 1 locally verified release' if verified else 'Candidate; verify its clean-install record',
                    git_head=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT).decode().strip(),
                    content_sha256=tree_hash, files=hashes,
                    raw_data_included=False, user_projects_included=False, credentials_included=False,
                    clean_install_verification=verified)
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
    parser.add_argument('--verification', type=Path)
    args = parser.parse_args()
    build(args.out.resolve(), args.evidence.resolve() if args.evidence else None,
          args.verification.resolve() if args.verification else None)
