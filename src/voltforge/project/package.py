"""Export exact selected experiments, source and provenance without raw archives."""
from pathlib import Path
import shutil

from . import schema as s
from .service import destination, file_hash, read, verify_files, write_once


def export_package(project, selections, out):
    out = destination(out)
    s.require(not out.exists(), 'Export is immutable; choose a new destination', 'conflict')
    s.require(not out.is_relative_to(project.path) and not project.path.is_relative_to(out), 'Export must be outside the project directory')
    s.require(isinstance(selections, list) and bool(selections), 'Select explicit variant/run pairs')
    state = project._state()
    project._inputs(state)
    selected, run_ids = [], set()
    for item in selections:
        s.keys(item, ['variant_id', 'run_id'], 'run selection')
        view = project.get_run(**item)
        s.require(item['run_id'] not in run_ids, 'Duplicate exported run')
        run_ids.add(item['run_id'])
        selected.append(view)
    comparison = project.compare(selections) if len(selections) > 1 else None
    out.mkdir(parents=True)
    shutil.copytree(project.path / 'assets', out / 'assets')
    software_ids, revision_ids = set(), set()
    for item in selections:
        folder, record, snapshot = project._run_record(state, item['run_id'])
        shutil.copytree(folder, out / 'runs' / item['run_id'])
        sid = snapshot['software']['id']
        verify_files(project.path / 'software' / sid, snapshot['software']['files'])
        if sid not in software_ids:
            shutil.copytree(project.path / 'software' / sid, out / 'software' / sid)
            software_ids.add(sid)
        # Include the complete ancestry for design/edit provenance, not only the leaf.
        rid = record['revision_id']
        while rid and rid not in revision_ids:
            source = project.path / 'revisions' / (rid + '.json')
            revision = read(source)
            from .service import digest
            s.require(rid == 'rev_' + digest(revision), 'Revision ancestry integrity failure', 'integrity_error')
            target = out / 'revisions' / source.name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
            revision_ids.add(rid)
            rid = revision['parent']
    measurements = {}
    for mid, metadata in state['measurements'].items():
        if metadata['run_id'] in run_ids:
            verify_files(project.path / 'measurements' / mid, metadata['artifacts'])
            shutil.copytree(project.path / 'measurements' / mid, out / 'measurements' / mid)
            measurements[mid] = metadata
    # Exported project state describes only selected history; no unexported current-run references.
    write_once(out / 'project_export.json', dict(schema_version=1, source_project_schema=state['schema_version'],
        selections=selections, selected_run_views=selected, display=state['display'], measurements=measurements,
        note='Historical experiment package, not a mutable project or an engineering acceptance certificate'))
    if comparison is not None:
        write_once(out / 'comparison.json', comparison)
    # A standard-library bootstrap selects the captured implementation before importing it.
    launcher = '''from pathlib import Path
import json, sys
sys.dont_write_bytecode = True
root = Path(__file__).resolve().parent
if len(sys.argv) != 2:
    raise SystemExit("Usage: python replay.py RUN_ID")
manifest = json.loads((root / "export_manifest.json").read_text(encoding="utf-8"))
if sys.argv[1] not in manifest["run_software"]:
    raise SystemExit("Run is not in this export")
sid = manifest["run_software"][sys.argv[1]]
sys.path.insert(0, str(root / "software" / sid / "src"))
from voltforge.project.replay import replay
print(json.dumps(replay(root, sys.argv[1]), indent=2, allow_nan=False))
'''
    (out / 'replay.py').write_text(launcher, encoding='utf-8', newline='\n')
    (out / 'README.md').write_text('''# Reproducible electrical and thermal simulation package

These are simulations, not validated repairs or battery-performance gains.
The frozen cell models and reference arrays are included; no raw archive is needed.
Voltage requirements may be unset. Read each run's summary and coverage evidence.

Use Python 3.12 and the pinned requirements under `software/<id>/requirements.txt`.
Run `python replay.py RUN_ID` from any working directory. The launcher imports the
captured source version for that run. It checks all exported bytes and dependency
versions, reruns the existing electrical backend, and compares every numeric
trajectory column with the saved run (rtol=1e-10, atol=1e-10). A completed thermal result requires its declared inputs and a verified thermal.csv; replay recomputes that model with the same tolerance. A recorded thermal failure cannot be certified as full-run reproduction. The thermal model is not experimentally validated.
It prints a software reproduction result and never overwrites saved outputs.
Matching calculations do not establish experimental accuracy.

The export manifest hashes every included file except itself. These are integrity
checks, not cryptographic signatures. Source/calibration references are metadata,
not a bundled copy of the original measurements. Inspect `assets/evidence` and
the original source-manifest hashes for experimental limitations and attribution.
''', encoding='utf-8', newline='\n')
    write_once(out / 'export_manifest.json', dict(schema_version=1, classification='simulation comparison',
        run_software={item['run_id']: project._run_record(state, item['run_id'])[1]['software_id'] for item in selections},
        artifacts={p.relative_to(out).as_posix(): file_hash(p) for p in sorted(out.rglob('*')) if p.is_file()},
        experimental_validation='awaiting suitable measurements'))
    return dict(path=str(out), run_ids=[x['run_id'] for x in selections], manifest_sha256=file_hash(out / 'export_manifest.json'),
        classification='reproducible simulation package', experimental_validation='awaiting suitable measurements')
