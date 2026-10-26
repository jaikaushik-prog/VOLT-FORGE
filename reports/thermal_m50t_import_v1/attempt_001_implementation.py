"""Strict, bounded LG M50T test-103 development import; no model fitting."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
from io import BytesIO
import json
from pathlib import Path
import re
import warnings
from zipfile import ZipFile

import h5py
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / 'reports/thermal_m50t_import_v1'
ARCHIVE = ROOT / 'data/raw/thermal_m50t/M50.zip'
ARCHIVE_SHA = '960ac78db8005d6b33072bbafdea95eb473057037ac5df85cbd99cf690a8cbb9'
ALLOCATION_SHA = '289e6bd52ef7e9e2a43725f33f349d46782e09f8ae70acc91b59d3069cb9d951'
THERMAL = 'M50/M50_50SOC_20deg_cell1_test103.txt'
ELECTRICAL = 'M50/Electrical/M50_50SOC_20deg_cell1_test103_CF8.txt'
MATLAB = 'M50/M50_50SOC_20deg_cell1_test103.mat'
ALLOW = (THERMAL, ELECTRICAL, MATLAB)


def sha(path):
    result = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(block)
    return result.hexdigest()


def write_json(path, value):
    with Path(path).open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')


def check_sources():
    if sha(ARCHIVE) != ARCHIVE_SHA:
        raise ValueError('Original archive hash mismatch')
    policy = ROOT / 'configs/thermal_m50t_allocation_v1.json'
    if sha(policy) != ALLOCATION_SHA:
        raise ValueError('Sealed allocation hash mismatch')
    seal = json.loads((REPORT / 'procedure_seal.json').read_text())
    for name, expected in seal['sha256'].items():
        if sha(ROOT / name) != expected:
            raise ValueError('Changed prospective procedure/input: ' + name)


def read_member(archive, member):
    if member not in ALLOW:
        raise ValueError('Member outside the exact test-103 development allowlist')
    info = archive.getinfo(member)
    if not 0 < info.file_size < 100_000_000:
        raise ValueError('Unexpected development member size')
    with archive.open(member) as stream:
        data = stream.read()
    return data


def decode_lines(data):
    try:
        text = data.decode('utf-8-sig'); encoding = 'utf-8-sig'
    except UnicodeDecodeError:
        text = data.decode('cp1252'); encoding = 'cp1252 fallback, instrument encoding not independently documented'
    lines, nul_count = [], 0
    for line in text.splitlines():
        clean = line.lstrip('\x00')
        nul_count += len(line) - len(clean)
        if '\x00' in clean:
            raise ValueError('Unexpected NUL inside a row')
        lines.append(clean)
    return lines, dict(encoding=encoding, leading_nul_bytes_removed=nul_count,
                       original_bytes_unchanged=True)


def numeric_rows(lines, width):
    rows = []
    for line in lines:
        if not line.strip():
            raise ValueError('Blank numeric row; no silent row removal')
        tokens = line.split('\t')
        if len(tokens) == width + 1 and tokens[-1] == '':
            tokens.pop()  # explicit trailing tab after the declared final column
        if len(tokens) != width or any(not token.strip() for token in tokens):
            raise ValueError('Numeric row width/empty field differs from header')
        rows.append(' '.join(tokens))
    with warnings.catch_warnings():
        warnings.simplefilter('error', DeprecationWarning)
        values = np.fromstring('\n'.join(rows), sep=' ')
    if values.size != len(rows) * width:
        raise ValueError('Numeric conversion did not consume all fields')
    return values.reshape(len(rows), width)


def parse_thermal(data):
    lines, metadata = decode_lines(data)
    if len(lines) < 3:
        raise ValueError('Missing thermal header/data')
    columns = lines[0].split('\t'); units = lines[1].split('\t')
    if len(columns) != 16 or len(set(columns)) != 16 or len(units) != 16 or columns[0] != 'Time':
        raise ValueError('Thermal schema differs from the declared 16 columns')
    if units[0].strip() != 'Seconds' or any(u.replace(' ', '') != '(\u00b0C)' for u in units[1:]):
        raise ValueError('Thermal units are not explicitly seconds/degC')
    values = numeric_rows(lines[2:], 16)
    return values, dict(metadata, columns=columns, units=['s'] + ['degC'] * 15,
                        rows=len(values), classification='recorded raw thermal')


def parse_electrical(data):
    lines, metadata = decode_lines(data)
    if not lines or lines[0] != 'BT-Lab ASCII FILE':
        raise ValueError('Unsupported electrical instrument header')
    matches = [re.fullmatch(r'Nb header lines\s*:\s*(\d+)\s*', line) for line in lines[:5]]
    counts = [int(m.group(1)) for m in matches if m]
    if len(counts) != 1 or not 3 <= counts[0] < len(lines):
        raise ValueError('Invalid electrical header count')
    count = counts[0]
    columns = lines[count - 1].rstrip('\t').split('\t')
    if len(set(columns)) != len(columns) or 'time/s' not in columns:
        raise ValueError('Missing explicit time/s or duplicate electrical columns')
    values = numeric_rows(lines[count:], len(columns))
    public = {}
    for line in lines[:count-1]:
        for label in ['Acquisition started on', 'Battery capacity', 'Initial state', 'Cycle Definition']:
            if line.startswith(label + ' :'):
                public[label] = line.split(':', 1)[1].strip()
        if line.startswith('Loaded Setting File'):
            public['settings_filename_only'] = re.split(r'[\\/]', line.split(':', 1)[1].strip())[-1]
    program = {}
    in_program = False
    for line in lines[:count-1]:
        if line.startswith('Ns '):in_program = True
        if in_program and line.strip():
            key = line[:20].strip()
            program[key] = [line[i:i+20].strip() for i in range(20, len(line), 20)]
    return values, dict(metadata, columns=columns, rows=len(values), header_lines=count,
        public_header=public, program=program, classification='recorded raw electrical',
        omitted_metadata='Lab hosts, IP addresses, personal names and original local directories omitted')


def decode_matlab(data):
    if not data.startswith(b'MATLAB 7.3 MAT-file'):
        raise ValueError('Only this declared MATLAB 7.3 layout is supported')
    arrays, labels, storage = {}, {}, {}
    with h5py.File(BytesIO(data), 'r') as file:
        for name in file:
            if not isinstance(file.get(name, getlink=True), h5py.HardLink):
                raise ValueError('External/soft HDF5 root links unsupported')
        group = file['data']
        for name in group:
            if not isinstance(group.get(name, getlink=True), h5py.HardLink):
                raise ValueError('External/soft HDF5 data links unsupported')
            dataset = group[name]
            if not isinstance(dataset, h5py.Dataset) or dataset.is_virtual or dataset.external is not None:
                raise ValueError('Unsupported HDF5 data object')
            storage[name] = dict(shape=list(dataset.shape), dtype=str(dataset.dtype))
            kind = dataset.attrs.get('MATLAB_class', b'')
            if kind == b'cell':
                text = []
                for ref in dataset[()].reshape(-1):
                    item = file[ref]
                    if not item.name.startswith('/#refs#/') or item.attrs.get('MATLAB_class') != b'char':
                        raise ValueError('Unsupported MATLAB label reference')
                    text.append(item[()].astype('<u2').reshape(-1).tobytes().decode('utf-16le'))
                labels[name] = text
            elif kind == b'double':
                arrays[name] = np.asarray(dataset[()], dtype=float)
            else:
                raise ValueError('Unsupported MATLAB class for ' + name)
    return arrays, dict(labels=labels, storage=storage,
        classification='author-derived arrays; numeric units/formulas require evidence',
        storage_orientation='Preserved HDF5 order; no automatic MATLAB transpose')


def finite_range(values):
    finite = np.asarray(values)[np.isfinite(values)]
    return dict(min=float(finite.min()) if finite.size else None,
                max=float(finite.max()) if finite.size else None,
                nonfinite=int(np.size(values)-finite.size))


def time_quality(time):
    diff = np.diff(time)
    valid = np.isfinite(diff)
    return dict(rows=len(time), start=float(time[0]), end=float(time[-1]),
        span_s=float(time[-1]-time[0]), duplicates=int(np.sum(diff == 0)),
        reversals=int(np.sum(diff < 0)), nonfinite=int(np.sum(~np.isfinite(time))),
        dt_quantiles_s=[float(x) for x in np.quantile(diff[valid], [0, .01, .5, .99, 1])] if valid.any() else None)


def summarize(thermal, tmeta, electrical, emeta, arrays, mmeta):
    etime = electrical[:, emeta['columns'].index('time/s')]
    return dict(schema='voltforge.thermal_m50t_development_import/1',
        evidence_kind='USED DEVELOPMENT: cell 1 test 103 only',
        thermal=dict(metadata=tmeta, time_quality=time_quality(thermal[:,0]),
            column_ranges={k:finite_range(thermal[:,i]) for i,k in enumerate(tmeta['columns'])}),
        electrical=dict(metadata=emeta, time_quality=time_quality(etime),
            column_ranges={k:finite_range(electrical[:,i]) for i,k in enumerate(emeta['columns'])}),
        matlab=dict(metadata=mmeta, array_ranges={k:finite_range(v) for k,v in arrays.items()}),
        alignment=dict(status='unresolved', applied_offset_s=None, resampling_performed=False),
        model_fitted=False, assessment_members_opened=0)


def import_record(output):
    output = Path(output).resolve()
    if output.exists() or not any(output.is_relative_to(ROOT / p) for p in ('tmp', 'data/processed/thermal_m50t')):
        raise ValueError('Choose a fresh local output directory under tmp or data/processed/thermal_m50t')
    check_sources()
    output.mkdir(parents=True)
    opened, hashes = [], {}
    started = dict(started_utc=datetime.now(timezone.utc).isoformat(), implementation_sha256=sha(__file__),
                   procedure_seal_sha256=sha(REPORT / 'procedure_seal.json'), allowed=list(ALLOW))
    write_json(output / 'started.json', started)
    try:
        with ZipFile(ARCHIVE) as archive:
            payloads = {}
            for member in ALLOW:
                opened.append(member)
                payloads[member] = read_member(archive, member)
                hashes[member] = hashlib.sha256(payloads[member]).hexdigest()
        thermal, tmeta = parse_thermal(payloads[THERMAL])
        electrical, emeta = parse_electrical(payloads[ELECTRICAL])
        arrays, mmeta = decode_matlab(payloads[MATLAB])
        report = summarize(thermal, tmeta, electrical, emeta, arrays, mmeta)
        np.savez_compressed(output / 'imported_arrays.npz', thermal=thermal, electrical=electrical,
                            **{'mat_'+k:v for k,v in arrays.items()})
        write_json(output / 'report.json', report)
        write_json(output / 'manifest.json', dict(**started, status='completed', opened=opened,
            source_members_sha256=hashes, archive_sha256=ARCHIVE_SHA, allocation_sha256=ALLOCATION_SHA,
            outputs_sha256={p.name:sha(p) for p in output.iterdir() if p.is_file()}))
        return report
    except Exception as exc:
        write_json(output / 'failure.json', dict(**started, status='failed', opened=opened,
                   error_type=type(exc).__name__, error=str(exc), source_members_sha256=hashes))
        raise


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out', type=Path, required=True)
    args = p.parse_args()
    result = import_record(args.out)
    print(json.dumps(dict(status='imported development record', thermal_rows=result['thermal']['metadata']['rows'],
        electrical_rows=result['electrical']['metadata']['rows'], assessment_members_opened=0, model_fitted=False)))


if __name__ == '__main__':main()
