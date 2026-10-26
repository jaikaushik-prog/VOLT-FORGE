"""Bounded schema-only opening of the declared test-103 development family."""
from __future__ import annotations

import argparse
from io import BytesIO
import json
import math
from pathlib import Path
import re
from zipfile import ZipFile

from scipy.io import whosmat
from intake_thermal_m50t import ROOT, POLICY, build, digest

ALLOW = {
    'M50/M50_50SOC_20deg_cell1_test103.txt',
    'M50/M50_50SOC_20deg_cell1_test103.mat',
    'M50/Electrical/M50_50SOC_20deg_cell1_test103_CF8.txt',
}
PROCEDURE = ROOT / 'reports/thermal_m50t_intake_v1/SCHEMA_PROBE_PROCEDURE.md'
ADDENDUM = ROOT / 'reports/thermal_m50t_intake_v1/SCHEMA_PROBE_ADDENDUM.md'


def read_allowed(archive, member, limit=None):
    if member not in ALLOW:
        raise ValueError('Member is outside the declared development schema probe')
    with archive.open(member) as stream:
        return stream.read(limit) if limit is not None else stream.read()


def text_schema(payload):
    try:
        text = payload.decode('utf-8-sig')
        encoding = 'utf-8-sig'
    except UnicodeDecodeError:
        text = payload.decode('cp1252')
        encoding = 'cp1252 fallback; source encoding not independently documented'
    lines = text.splitlines()[:64]
    headers, numeric_rows = [], []
    for number, line in enumerate(lines, 1):
        normalized = line.lstrip('\x00 \t')
        if not normalized.strip():
            continue
        # A numeric-leading row is a possible measurement. Publish types only.
        if re.match(r'^[+\-]?(?:\d|\.\d|nan\b|inf\b)', normalized, re.I):
            tokens = re.split(r'[\t;, ]+', normalized.strip())
            types = []
            for token in tokens:
                try:
                    value = float(token)
                    types.append('finite_number' if math.isfinite(value) else 'nonfinite_number')
                except ValueError:
                    types.append('text')
            numeric_rows.append(dict(line=number, token_count=len(tokens), token_types=types))
        else:
            headers.append(dict(line=number, text=normalized))
    return dict(prefix_bytes=len(payload), lines_inspected=len(lines), decoding=encoding,
                leading_nul_lines=sum(line.startswith('\x00') for line in lines),
                nonnumeric_leading_lines=headers, numeric_leading_rows_redacted=numeric_rows,
                unit_inference='No units or time origin inferred from numerical magnitudes')


def matlab_schema(data):
    if not data.startswith(b'MATLAB 7.3 MAT-file'):
        return {'format': 'MAT pre-7.3', 'mat_variables': [dict(name=name, shape=list(shape), matlab_class=kind)
                    for name, shape, kind in whosmat(BytesIO(data))]}
    import h5py
    objects, visited = [], set()
    with h5py.File(BytesIO(data), 'r') as file:
        def walk(group, prefix=''):
            address = h5py.h5o.get_info(group.id).addr
            if address in visited:
                return
            visited.add(address)
            for key in sorted(group.keys()):
                if not isinstance(group.get(key, getlink=True), h5py.HardLink):
                    raise ValueError('Linked external/soft HDF5 data is unsupported')
                item = group[key]
                name = prefix + '/' + key
                if len(objects) >= 1000:
                    raise ValueError('HDF5 schema exceeds the inspection limit')
                if isinstance(item, h5py.Dataset):
                    if item.is_virtual or item.external is not None:
                        raise ValueError('Virtual/external HDF5 datasets are unsupported')
                    kind = item.attrs.get('MATLAB_class')
                    if isinstance(kind, bytes):kind = kind.decode('ascii', errors='replace')
                    objects.append(dict(name=name, shape=list(item.shape), dtype=str(item.dtype),
                                        matlab_class=kind if isinstance(kind, str) else None))
                else:
                    objects.append(dict(name=name, type='group'))
                    walk(item, name)
        walk(file)
    return {'format':'MATLAB 7.3/HDF5', 'objects':objects, 'dataset_values_read':False}


def probe():
    inventory = build()
    family = next(f for f in inventory['families'] if f['family_id'] == 'cell_1_test_103')
    if family['allocation'] != 'development_candidate' or set(family['members'].values()) != ALLOW:
        raise ValueError('Development allocation differs from the declared probe')
    policy = json.loads(POLICY.read_text())
    opened, schemas = [], {}
    with ZipFile(ROOT / policy['archive_path']) as archive:
        for member in sorted(ALLOW):
            if member.endswith('.mat'):
                data = read_allowed(archive, member)
                schemas[member] = matlab_schema(data)
            else:
                schemas[member] = text_schema(read_allowed(archive, member, 32768))
            opened.append(member)
    return dict(schema='voltforge.thermal_m50t_schema_probe/1', archive_sha256=inventory['archive_sha256'],
        allocation_sha256=digest(POLICY), procedure_sha256=digest(PROCEDURE), addendum_sha256=digest(ADDENDUM),
        opened_development_members=opened, schemas=schemas, numerical_outcomes_presented=False,
        used_development_families=['cell_1_test_103'], untouched_measurement_members=30,
        assessment_members_opened=0, model_fitted=False,
        warning='Only schema inspected. These development members are no longer fresh assessment evidence.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    out = args.out.resolve()
    if not any(out.is_relative_to(ROOT / p) for p in ('tmp', 'reports/thermal_m50t_intake_v1')):
        raise ValueError('Choose an output under tmp or this intake report')
    if out.exists():
        raise FileExistsError(out)
    result = probe()
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    print(json.dumps(dict(status='schema recorded', opened_development_members=result['opened_development_members'],
                         assessment_members_opened=0, model_fitted=False)))


if __name__ == '__main__':
    main()
