"""Release check: run headline tests, export them, replay each in isolation, confirm tampering fails."""
from pathlib import Path
import argparse
import io
import json
import shutil
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from voltforge.project import Project
from voltforge.studio.store import Studio


def replay(folder):
    return subprocess.run([sys.executable, '-I', 'replay.py'], cwd=folder, capture_output=True, text=True, timeout=300)


def check(studio, test, root):
    folder = root/test['id']; folder.mkdir()
    with zipfile.ZipFile(io.BytesIO(studio.export(test['id']))) as z: z.extractall(folder)
    clean = replay(folder)
    tampered = root/(test['id']+'_tampered'); shutil.copytree(folder, tampered)
    record = json.loads((tampered/'experiment.json').read_text()); record['settings']['ambient_C'] += 1
    (tampered/'experiment.json').write_text(json.dumps(record))
    bad_model = root/(test['id']+'_model'); shutil.copytree(folder, bad_model)
    models = json.loads((bad_model/'models.json').read_text())
    first = next(iter(models)); models[first]['capacity_Ah'] *= 1.01
    (bad_model/'models.json').write_text(json.dumps(models))
    return dict(name=test['name'], status=test['status'], stop=(test['stop'] or {}).get('reason'), peak_temperature_C=test['summary']['metrics']['peak_temperature_C'],
                first_law_closed=test['summary']['verification'].get('first_law_closed'), replay_passed=clean.returncode == 0,
                tampered_result_refused=replay(tampered).returncode != 0, tampered_model_refused=replay(bad_model).returncode != 0)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, default=ROOT/'reports/v4_release/replay_receipt.json')
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='vf-release-') as folder:
        root = Path(folder); project = root/'project'; Project.create_reference(project); studio = Studio(project)
        rows = []
        pi2 = studio.create('parallel', 2, 'Two-cell Pi backup', mission=dict(preset='pi5_gateway_backup')); rows.append(studio.run(pi2['id'], pi2['version']))
        pi4 = studio.create('parallel', 4, 'Four-cell Pi backup', mission=dict(preset='pi5_gateway_backup')); rows.append(studio.run(pi4['id'], pi4['version']))
        stress = studio.create('parallel', 2, 'Two-cell stress', mission=dict(preset='stress_12a')); rows.append(studio.run(stress['id'], stress['version']))
        charge = studio.create('parallel', 2, 'Two-cell charge', mission=dict(test_type='charge', current_A=2., duration_s=600.)); rows.append(studio.run(charge['id'], charge['version']))
        samsung = studio.create('parallel', 1, 'Samsung 6 A', mission=dict(current_A=6., duration_s=1560.))
        samsung['graph']['cells'][0]['model'] = 'SAMSUNG_30T'
        saved = studio.save(samsung['id'], samsung['version'], samsung['graph'], samsung['settings']); rows.append(studio.run(saved['id'], saved['version']))
        results = [check(studio, t, root) for t in rows]
    receipt = dict(version='voltforge.release-replay/1', software_hash=Studio._software_hash(), passed=all(r['replay_passed'] and r['tampered_result_refused'] and r['tampered_model_refused'] for r in results), checks=results)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(receipt, indent=2)+'\n')
    print(json.dumps(receipt, indent=1))
    if not receipt['passed']: raise SystemExit(1)


if __name__ == '__main__':
    main()
