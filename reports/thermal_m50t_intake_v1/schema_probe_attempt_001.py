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


def read_allowed(archive, member, limit=None):
    if member not in ALLOW:
        raise ValueError('Member is outside the declared development schema probe')
    with archive.open(member) as stream:
        return stream.read(limit) if limit is not None else stream.read()


def text_schema(payload):
    text = payload.decode('utf-8-sig', errors='replace')
    lines = text.splitlines()[:64]
    headers, numeric_rows = [], []
    for number, line in enumerate(lines, 1):
        if not line.strip():
            continue
        # A numeric-leading row is a possible measurement. Publish types only.
        if re.match(r'^\s*[+\-]?(?:\d|\.\d|nan\b|inf\b)', line, re.I):
            tokens = re.split(r'[\t;, ]+', line.strip())
            types = []
            for token in tokens:
                try:
                    value = float(token)
                    types.append('finite_number' if math.isfinite(value) else 'nonfinite_number')
                except ValueError:
                    types.append('text')
            numeric_rows.append(dict(line=number, token_count=len(tokens), token_types=types))
        else:
            headers.append(dict(line=number, text=line))
    return dict(prefix_bytes=len(payload), lines_inspected=len(lines),
                nonnumeric_leading_lines=headers, numeric_leading_rows_redacted=numeric_rows,
                unit_inference='No units or time origin inferred from numerical magnitudes')


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
                schemas[member] = {'mat_variables': [dict(name=name, shape=list(shape), matlab_class=kind)
                    for name, shape, kind in whosmat(BytesIO(data))]}
            else:
                schemas[member] = text_schema(read_allowed(archive, member, 32768))
            opened.append(member)
    return dict(schema='voltforge.thermal_m50t_schema_probe/1', archive_sha256=inventory['archive_sha256'],
        allocation_sha256=digest(POLICY), procedure_sha256=digest(PROCEDURE),
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
