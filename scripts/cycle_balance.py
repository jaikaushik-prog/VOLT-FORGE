"""Cycle charge balance per current channel for the two already-opened M1 runs.

Reads only the reconciliation residual CSVs already in this repository. A discharge from a
CV-terminated full state to cutoff, followed by a recharge to the same CV termination, must
return at least the discharged charge (coulombic efficiency <= 1). Each channel is checked
against itself, so a pure gain error cancels; a direction-dependent error does not. This
identifies a direction-dependent inconsistency, not which direction has an absolute calibration
error. Equivalent endpoints and measurement uncertainty still need independent verification.
It corrects, rescales and admits nothing.
"""
import argparse
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
RUNS = {'test_53': 'M1_NMC_Unaged_R0_T25', 'test_28': 'M1_NMC_Unaged_R3_T25'}
CHANNELS = {'cycler_module_current': 'module_discharge_A', 'hall_branch_sum': 'branch_sum_discharge_A'}


def integral_Ah(t, x, rows):
    """Integrate only observed contiguous selected blocks; never bridge excluded rows."""
    rows = np.asarray(rows, dtype=int)
    if not len(rows):
        return 0.0
    if np.any(np.diff(rows) <= 0):
        raise ValueError('Selected rows must be strictly increasing')
    blocks = np.split(rows, np.flatnonzero(np.diff(rows) > 1) + 1)
    return float(sum(np.trapz(x[block], t[block]) for block in blocks if len(block) > 1) / 3600)


def balance(csv_path):
    d = np.genfromtxt(csv_path, delimiter=',', names=True)
    t, module = d['time_s'], d['module_discharge_A']
    active = np.flatnonzero(module > 1.0)
    if not len(active):
        raise ValueError('No active discharge block; balance undefined')
    blocks = np.split(active, np.flatnonzero(np.diff(active) > 1) + 1)
    discharge = max(blocks, key=len)  # the CC discharge step; brief pulses cannot be longer
    after = np.arange(discharge[-1] + 1, len(t))
    recharge = after[module[after] < -0.05]
    if not len(recharge):
        raise ValueError('No recharge after the discharge; balance undefined')
    out = dict(source=csv_path.relative_to(ROOT).as_posix(),
        discharge=dict(first_row=int(discharge[0]), last_row=int(discharge[-1]),
            duration_s=float(t[discharge[-1]] - t[discharge[0]])),
        recharge=dict(first_row=int(recharge[0]), last_row=int(recharge[-1])), channels={})
    for name, column in CHANNELS.items():
        x = d[column]
        removed, returned = integral_Ah(t, x, discharge), -integral_Ah(t, x, recharge)
        out['channels'][name] = dict(column=column, mean_discharge_current_A=float(x[discharge].mean()),
            discharged_Ah=removed, recharged_Ah=returned, discharged_over_recharged=removed / returned)
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=ROOT / 'reports/reconciliation/cycle_balance')
    args = parser.parse_args()
    results = {test: balance(ROOT / 'reports/reconciliation' / f'{run}_residual.csv') | {'run': run} for test, run in RUNS.items()}
    record = dict(method='Trapezoidal integral of each discharge-positive channel over the longest >1 A discharge block '
        'and separately within each contiguous later charging block (<-0.05 A); never bridges excluded rows. '
        'Ratio = discharged / recharged on the same channel.',
        physical_bound='For equivalent full-state endpoints the ideal charge-balance bound is ratio <= 1; '
        'endpoint equivalence and independent measurement uncertainty are not established by this diagnostic.',
        runs=results, interpretation='Direction-dependent inconsistency; faulty direction is not uniquely identified. '
        'No channel is corrected, rescaled or admitted by this check.')
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / 'results.json').write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8', newline='\n')
    for test, r in results.items():
        c = r['channels']
        print(f"{test} ({r['run']}): cycler {c['cycler_module_current']['discharged_over_recharged']:.4f}, "
              f"Hall sum {c['hall_branch_sum']['discharged_over_recharged']:.4f}")


if __name__ == '__main__':
    main()
