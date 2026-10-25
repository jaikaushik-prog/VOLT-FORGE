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
    return dict(run_id=run_id, reproduced=True, samples=len(saved), solver_status=result.status,
        scope='software reproduction only', experimental_validation='awaiting suitable measurements')
