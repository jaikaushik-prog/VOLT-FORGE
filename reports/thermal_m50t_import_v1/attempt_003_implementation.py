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
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / 'reports/thermal_m50t_import_v1'
ARCHIVE = ROOT / 'data/raw/thermal_m50t/M50.zip'
ARCHIVE_SHA = '960ac78db8005d6b33072bbafdea95eb473057037ac5df85cbd99cf690a8cbb9'
ALLOCATION_SHA = '289e6bd52ef7e9e2a43725f33f349d46782e09f8ae70acc91b59d3069cb9d951'
THERMAL = 'M50/M50_50SOC_20deg_cell1_test103.txt'
ELECTRICAL = 'M50/Electrical/M50_50SOC_20deg_cell1_test103_CF8.txt'
MATLAB = 'M50/M50_50SOC_20deg_cell1_test103.mat'
ALLOW = (THERMAL, ELECTRICAL, MATLAB)
THERMAL_COLUMNS = ['Time', 'A0080/212 Cold Junction',
    *[f'A0080/212 Channel {i}' for i in range(1, 9)],
    *[f'AO027/105 Channel {i}' for i in range(1, 6)], 'AO027/105 Cold Junction']
CELL_LABELS = ['CellH top', 'cell +ve', 'cell mid', 'cell -ve', 'CellC bottom']


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
    if columns != THERMAL_COLUMNS or len(units) != 16:
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
    raw_columns = lines[count - 1].split('\t')
    if raw_columns != ['time/s', 'Ecell/V', 'I/mA', '', '']:
        raise ValueError('Electrical header differs from the explicitly inspected test-103 layout')
    fields = [line.split('\t') for line in lines[count:]]
    if any(len(row) != 4 or any(not value.strip() for value in row) for row in fields):
        raise ValueError('Electrical row differs from the observed timestamp + three numeric fields')
    timestamp_text = np.asarray([row[0] for row in fields])
    datetimes = pd.to_datetime(timestamp_text, format='%m/%d/%Y %H:%M:%S.%f', errors='raise')
    elapsed = np.asarray((datetimes - datetimes[0]).total_seconds(), dtype=float)
    numeric = numeric_rows(['\t'.join(row[1:]) for row in fields], 3)
    values = np.column_stack((elapsed, numeric))
    columns = ['derived_elapsed_s_from_recorded_datetime', 'Ecell/V', 'I/mA', 'unlabelled_column_4']
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
    return values, timestamp_text, dict(metadata, columns=columns, rows=len(values), header_lines=count,
        raw_header_fields=raw_columns, units=['s', 'V', 'mA', None],
        timestamp=dict(start=timestamp_text[0], end=timestamp_text[-1], timezone=None,
                       conversion='Derived seconds since first calendar timestamp; no cross-instrument alignment'),
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


def integrate(time, value, convention='trapezoid'):
    time, value = np.asarray(time), np.asarray(value)
    if time.ndim != 1 or value.shape != time.shape or len(time) < 2:
        raise ValueError('Integration needs equal-length vectors and two samples')
    if not np.isfinite(time).all() or not np.isfinite(value).all() or np.any(np.diff(time) <= 0):
        raise ValueError('Integration requires finite strictly increasing timestamps')
    if convention == 'left':held = value[:-1]
    elif convention == 'right':held = value[1:]
    elif convention == 'trapezoid':held = (value[:-1]+value[1:])/2
    else:raise ValueError('Unknown integration convention')
    return float(np.sum(np.diff(time)*held))


def electrical_accounting(time, voltage, current_A):
    result = {}
    for method in ('left', 'right', 'trapezoid'):
        positive = integrate(time, np.maximum(current_A, 0), method)/3600
        negative = integrate(time, np.minimum(current_A, 0), method)/3600
        power = voltage*current_A
        positive_work = integrate(time, np.maximum(power, 0), method)/3600
        negative_work = integrate(time, np.minimum(power, 0), method)/3600
        result[method] = dict(positive_charge_Ah=positive, negative_charge_Ah=negative,
            signed_charge_Ah=integrate(time,current_A,method)/3600,
            positive_terminal_work_Wh=positive_work, negative_terminal_work_Wh=negative_work,
            signed_terminal_work_Wh=integrate(time,power,method)/3600,
            charge_split_residual_Ah=positive+negative-integrate(time,current_A,method)/3600,
            work_split_residual_Wh=positive_work+negative_work-integrate(time,power,method)/3600)
    return result


def runs(mask):
    edges = np.r_[0, np.flatnonzero(np.diff(np.asarray(mask,dtype=int)))+1, len(mask)]
    return [(int(a),int(b),bool(mask[a])) for a,b in zip(edges[:-1],edges[1:])]


def electrical_blocks(electrical, threshold_A=.01):
    time, voltage, current = electrical[:,0], electrical[:,1], electrical[:,2]*.001
    if np.any(np.diff(time) <= 0) or not np.isfinite(electrical[:,:3]).all():
        raise ValueError('Electrical block diagnostics require finite monotonic samples')
    blocks=[]
    for a,b,active in runs(np.abs(current)>threshold_A):
        t, v, i = time[a:b], voltage[a:b], current[a:b]
        signs = np.sign(i)
        changes = np.flatnonzero(np.diff(signs)!=0)+1
        span=float(t[-1]-t[0])
        kind=('bipolar_pulse_candidate' if active and len(changes)>=100 else 'active_other') if active else ('rest_candidate' if span>=60 else 'short_below_threshold')
        change_intervals=np.diff(t[changes])
        blocks.append(dict(kind=kind, first_index=a,last_index=b-1,samples=b-a,
            first_sample_s=float(t[0]),last_sample_s=float(t[-1]),sampled_span_s=span,
            outer_start_s=float(time[a-1]) if a else None,outer_end_s=float(time[b]) if b<len(time) else None,
            max_internal_gap_s=float(np.diff(t).max()) if b-a>1 else None,
            current_A=finite_range(i),voltage_V=finite_range(v),positive_samples=int(np.sum(i>0)),negative_samples=int(np.sum(i<0)),
            median_abs_current_A=float(np.median(np.abs(i))),sign_changes=len(changes),
            sign_change_interval_quantiles_s=[float(x) for x in np.quantile(change_intervals,[0,.5,1])] if len(change_intervals) else None,
            accounting=electrical_accounting(t,v,i) if b-a>1 else None))
    return blocks


def representation_checks(thermal, arrays, metadata):
    labels=metadata['labels'].get('celltemplabels')
    cell=arrays['celltemps']
    if labels!=CELL_LABELS or cell.shape!=(5,len(thermal)-1):
        raise ValueError('Cell labels/dimensions differ; no inferred permutation or resampling')
    result={}
    for name,offset in [('omit_last_raw_row',0),('omit_first_raw_row',1)]:
        raw=thermal[offset:offset+cell.shape[1],3:8].T
        diff=cell-raw
        result[name]=[dict(label=label,median_processed_minus_raw_degC=float(np.median(d)),
            min_difference_degC=float(d.min()),max_difference_degC=float(d.max()),
            std_difference_degC=float(d.std()),range_of_difference_degC=float(np.ptp(d))) for label,d in zip(labels,diff)]
    return dict(raw_cell_columns_1_based=[4,5,6,7,8],mat_storage_channel_axis=0,
        basis='Five decoded labels and five-channel storage dimension; no permutation search',
        alternatives=result,raw_rows_preserved=len(thermal),processed_samples=cell.shape[1],
        note='Same-record representation diagnostics only; no cross-instrument alignment or correction applied')


def author_processing_checks(arrays, metadata):
    labels=metadata['labels']['templabels']
    expected=['Amb','+ve clamp',*CELL_LABELS,'-ve clamp','Tab +ve','finC','finH','Tab -ve C','Tab -ve H','Ins']
    if labels!=expected or arrays['SS_T'].shape!=(15,6):
        raise ValueError('Author temperature labels/dimensions differ from inspected layout')
    ss=arrays['SS_T']; n=6
    vector=lambda key:arrays[key].reshape(-1)
    if any(vector(k).size!=n for k in ('SS_Q','SS_MaxT','SS_CST','SS_delT','SS_CCC','Qnet','Qgain','Qloss')):
        raise ValueError('Unexpected author summary dimensions')
    def residual(observed, expected):
        d=np.asarray(observed)-expected
        return dict(max_abs_residual=float(np.max(np.abs(d))),residuals=d.tolist())
    dtfin=ss[10]-ss[9]
    if np.any(dtfin==0) or np.any(vector('SS_delT')==0):raise ValueError('Undefined author ratio')
    factor=vector('SS_Q')/dtfin
    alt_expected=np.vstack([ss[2]-ss[8],ss[11]-ss[12],ss[2]-ss[13]])
    checks=dict(
        SS_MaxT_equals_cap=residual(vector('SS_MaxT'),ss[2]),
        SS_CST_equals_base=residual(vector('SS_CST'),ss[6]),
        SS_delT_equals_cap_minus_base=residual(vector('SS_delT'),ss[2]-ss[6]),
        SS_CCC_equals_SS_Q_over_SS_delT=residual(vector('SS_CCC'),vector('SS_Q')/vector('SS_delT')),
        Qnet_equals_SS_Q_plus_Qgain_minus_Qloss=residual(vector('Qnet'),vector('SS_Q')+vector('Qgain')-vector('Qloss')),
        AltdelT_declared_tab_tab_insulation_order=residual(arrays['AltdelT'],alt_expected))
    return dict(relationships=checks,fin_temperature_difference_degC=dtfin.tolist(),
        implied_SS_Q_per_fin_deltaT=factor.tolist(),
        inferred_rod_conductivity_if_SS_Q_is_W=(factor*.060/(np.pi*.006**2/4)).tolist(),
        geometry_source='Primary paper section 3.2: rod diameter 6 mm, TC separation 60 mm',
        AltQ_over_AltdelT=(arrays['AltQ']/arrays['AltdelT']).tolist(),
        classification='Author-processing algebra; inferred constants are not independent calibration',
        notes=['SS_T has 15 rows but only 14 templabels; final raw cold-junction label remains unassigned in the author labels.',
               'Amb is the author label for the first raw cold-junction position; physical ambient location unverified.',
               'No averaging windows, synchronization, heat units or uncertainty propagation inferred from matching algebra.'])


def summarize(thermal, tmeta, electrical, emeta, arrays, mmeta):
    etime = electrical[:, 0]
    blocks=electrical_blocks(electrical)
    thresholds={str(x):sum(b['kind']=='rest_candidate' for b in electrical_blocks(electrical,x)) for x in [.005,.01,.02]}
    return dict(schema='voltforge.thermal_m50t_development_import/1',
        evidence_kind='USED DEVELOPMENT: cell 1 test 103 only',
        thermal=dict(metadata=tmeta, time_quality=time_quality(thermal[:,0]),
            column_ranges={k:finite_range(thermal[:,i]) for i,k in enumerate(tmeta['columns'])}),
        electrical=dict(metadata=emeta, time_quality=time_quality(etime),
            column_ranges={k:finite_range(electrical[:,i]) for i,k in enumerate(emeta['columns'])}),
        matlab=dict(metadata=mmeta, array_ranges={k:finite_range(v) for k,v in arrays.items()}),
        representation=representation_checks(thermal,arrays,mmeta),
        author_processing=author_processing_checks(arrays,mmeta),
        electrical_blocks=blocks,long_rest_counts_by_threshold_A=thresholds,
        electrical_accounting=electrical_accounting(etime,electrical[:,1],electrical[:,2]*.001),
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
        electrical, timestamp_text, emeta = parse_electrical(payloads[ELECTRICAL])
        arrays, mmeta = decode_matlab(payloads[MATLAB])
        report = summarize(thermal, tmeta, electrical, emeta, arrays, mmeta)
        np.savez_compressed(output / 'imported_arrays.npz', thermal=thermal, electrical=electrical,
                            electrical_timestamp_text=timestamp_text,
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
