"""Write the versioned V4 catalogue from V1, changing only the LG branch-3 placeholder.

PyECN's LG tables hold R3=1e-4 ohm and C3=1e-4 F (tau=1e-8 s) for SOC <= 18%, then
tau=350.1424873 s from SOC 20%. Interpolating across that jump dumps the branch
voltage within seconds. The pattern looks like a switched-off branch, but no
author statement confirms it, so this is a recorded engineering assumption.
"""
from pathlib import Path
import hashlib
import json

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT/'configs/cell_catalogue_v1.json'
TARGET = ROOT/'configs/cell_catalogue_v2.json'
KEY = 'LG_M50T_ECN'
BRANCH = 2
PLATEAU_S = 350.1424873
PLACEHOLDER_S = 1e-6
REASON = ('PyECN Cylindrical_Cell1 tables set branch 3 to R=1e-4 ohm, C=1e-4 F for SOC <= 18%, then tau=350.1424873 s from SOC 20%. '
          'That interpolated jump produced an artificial upward voltage step and heating spike near 18-20% charge.')
LIMITATION = ('Branch-3 time constant is held at its 350.1424873 s plateau for SOC <= 18%. This regularizes a published table '
              'and is an unvalidated low-SOC modification, not a measured value.')


def main():
    raw = SOURCE.read_bytes(); data = json.loads(raw)
    record = data['models'][KEY]
    changed = []
    for i, temperature in enumerate(record['temperature_C']):
        for j, soc in enumerate(record['soc']):
            value = record['tau_s'][i][j][BRANCH]
            if value < PLACEHOLDER_S:
                if soc > .18: raise ValueError('Unexpected placeholder above SOC 18%.')
                record['tau_s'][i][j][BRANCH] = PLATEAU_S
                changed.append(dict(temperature_C=temperature, soc=soc, previous_tau_s=value))
    if len(changed) != 45: raise ValueError(f'Expected 45 placeholder entries, found {len(changed)}.')
    record['limitations'].append(LIMITATION)
    data['version'] = 'voltforge.cell-catalogue/2'
    data['revision'] = dict(parent_file=SOURCE.name, parent_sha256=hashlib.sha256(raw).hexdigest(), model=KEY, table='tau_s',
                            branch_index=BRANCH, replacement_tau_s=PLATEAU_S, entries_changed=len(changed), changes=changed,
                            reason=REASON, status='Unvalidated low-SOC modification; regularized published model',
                            unchanged='Every other model and table value is carried over from the parent file.')
    TARGET.write_text(json.dumps(data, indent=1)+'\n')
    print(TARGET.name, hashlib.sha256(TARGET.read_bytes()).hexdigest())


if __name__ == '__main__':
    main()
