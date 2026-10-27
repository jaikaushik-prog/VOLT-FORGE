"""Replay a captured experiment without refitting, raw data, or modifying the package."""
from pathlib import Path
import numpy as np
import pandas as pd

from voltforge.simulation import workflow as w
from . import schema as s
from .service import read, software, verify_files


def replay(root, run_id):
    root = Path(root).resolve()
    manifest = read(root / 'export_manifest.json')
    verify_files(root, manifest['artifacts'])
    s.require(run_id in manifest['run_software'], 'Run not exported', 'not_found')
    run_record = read(root / 'runs' / run_id / 'run.json')
    verify_files(root / 'runs' / run_id, run_record['artifacts'])
    snapshot = read(root / 'runs' / run_id / 'snapshot.json')
    s.require((root / 'runs' / run_id / 'trajectory.csv').exists(), 'Run failed without a trajectory; inputs/error are preserved, no numeric replay is available', 'unsupported_request')
    s.require(software()['runtime'] == snapshot['software']['runtime'], 'Runtime versions differ from captured run', 'unsupported_request')
    with np.load(root / 'assets/reference_sensitivity.npz', allow_pickle=False) as npz:
        curves = [(npz[c+'_soc'].copy(), npz[c+'_V'].copy()) for c in s.CELLS]
    result = w.execute_case(snapshot['effective_case'], curves)
    saved = pd.read_csv(root / 'runs' / run_id / 'trajectory.csv')
    actual = result.frame if len(result.frame) else pd.DataFrame(columns=['time_s', 'step_s'])
    same = actual.shape == saved.shape and list(actual) == list(saved)
    if same and len(saved):
        same = bool(np.allclose(actual.to_numpy(), saved.to_numpy(), rtol=1e-10, atol=1e-10, equal_nan=True))
    s.require(same, 'Replayed trajectory differs from saved output', 'integrity_error')
    original = read(root / 'runs' / run_id / 'summary.json')
    s.require(result.status == original['status'], 'Replayed solver status differs', 'integrity_error')
    thermal_reproduced = False
    thermal_status = (original.get('thermal') or {}).get('status')
    declared_thermal = snapshot.get('thermal') is not None
    recorded_thermal = 'thermal.csv' in run_record['artifacts']
    if declared_thermal and thermal_status == 'failed':
        raise s.RequestError('unsupported_request', 'Original thermal calculation failed; full-run reproduction cannot be certified. Electrical outputs are preserved for inspection.')
    if thermal_status == 'completed':
        s.require(declared_thermal and recorded_thermal, 'Completed thermal result is missing declared inputs or its verified artifact', 'integrity_error')
    if recorded_thermal:
        th = snapshot.get('thermal')
        s.require(th is not None and thermal_status == 'completed', 'Thermal artifact does not match recorded thermal status/inputs', 'integrity_error')
        from voltforge.models import thermal_v1
        actual_t = thermal_v1.simulate(result.frame, snapshot['effective_case']['models'], th['parameters'], th['initial_C'], th['ambient_C'])
        saved_t = pd.read_csv(root / 'runs' / run_id / 'thermal.csv')
        thermal_v1.validate_output(saved_t, actual)
        same_t = actual_t.shape == saved_t.shape and list(actual_t) == list(saved_t) and bool(np.allclose(actual_t.to_numpy(), saved_t.to_numpy(), rtol=1e-10, atol=1e-10, equal_nan=True))
        s.require(same_t, 'Replayed thermal trajectory differs from saved output', 'integrity_error')
        thermal_reproduced = True
    elif declared_thermal and len(actual):
        raise s.RequestError('unsupported_request', 'Declared thermal calculation has no reproducible thermal result')
    return dict(run_id=run_id, reproduced=True, samples=len(saved), solver_status=result.status,
        scope='software reproduction only', experimental_validation='awaiting suitable measurements', thermal_reproduced=thermal_reproduced)
