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
    if len(counts) != 1 or counts[0] != 97 or counts[0] >= len(lines):
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
                    if (not isinstance(item,h5py.Dataset) or item.is_virtual or item.external is not None
                        or not item.name.startswith('/#refs#/') or item.attrs.get('MATLAB_class') != b'char'
                        or item.dtype != np.dtype('uint16')):
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
    if not len(mask):return []
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


def coverage_report(electrical, blocks):
    """Describe sampled sequences, without promoting nominal protocol to truth."""
    sequences=[]
    for index,block in enumerate(blocks):
        if block['kind']!='bipolar_pulse_candidate':continue
        following=blocks[index+1] if index+1<len(blocks) and blocks[index+1]['kind']=='rest_candidate' else None
        prior=blocks[index-1] if index and blocks[index-1]['kind']=='rest_candidate' else None
        sequences.append(dict(id=f'pulse_{len(sequences)+1}',pulse_block_index=index,
            pulse_has_recorded_rest_on_both_sides=prior is not None and following is not None,
            pulse_boundary_bracket_width_s=[block['first_sample_s']-block['outer_start_s'] if block['outer_start_s'] is not None else None,
                block['outer_end_s']-block['last_sample_s'] if block['outer_end_s'] is not None else None],
            sampled_pulse_span_s=block['sampled_span_s'],max_pulse_sampling_gap_s=block['max_internal_gap_s'],
            median_abs_current_A=block['median_abs_current_A'],
            nominal_paper_rest_s=5400,
            following_rest_sampled_span_s=following['sampled_span_s'] if following else None,
            following_rest_max_gap_s=following['max_internal_gap_s'] if following else None,
            following_rest_outer_span_s=(following['outer_end_s']-following['outer_start_s'])
                if following and following['outer_start_s'] is not None and following['outer_end_s'] is not None else None,
            following_rest_right_censored=following is None or following['outer_end_s'] is None,
            following_rest_covers_nominal_90_min_with_boundary_bracket=bool(following and following['outer_end_s'] is not None
                and following['outer_end_s']-following['outer_start_s']>=5400),
            cross_instrument_temperature_sequence='unresolved clock alignment; no matched transient sequence declared'))
    preparation=[]
    initial=next((b for b in blocks if b['kind']=='active_other'),None)
    if initial:
        values=electrical[initial['first_index']:initial['last_index']+1]
        for a,b,positive in runs(values[:,2]>0):
            segment=values[a:b]
            preparation.append(dict(native_sign='positive' if positive else 'nonpositive',samples=len(segment),
                first_elapsed_s=float(segment[0,0]),last_elapsed_s=float(segment[-1,0]),
                first_voltage_V=float(segment[0,1]),last_voltage_V=float(segment[-1,1]),
                native_current_A=finite_range(segment[:,2]/1000),
                accounting=electrical_accounting(segment[:,0],segment[:,1],segment[:,2]/1000) if len(segment)>1 else None))
    return dict(evidence_kind='USED DEVELOPMENT; not independent assessment',
        nominal_filename_conditions=dict(cell='LG M50T cell 1',soc_fraction=.5,temperature_degC=20),
        achieved_SOC='unknown: preparation charge is measurable but cell capacity and SOC origin are not independently established',
        temperature_conditions='Base-cooled insulated CCC rig; nominal 20 degC does not mean constant measured cell temperature',
        native_current_polarity=dict(convention='charge positive; discharge negative',
            evidence='Header specifies initial CC/CV charge then 5 A discharge to 2500 mAh. Recorded initial positive segment rises to 4.2 V; subsequent negative segment integrates to about -2.500 Ah.',
            canonical_discharge_positive_conversion='I_discharge_A = -I_native_mA / 1000; originals unchanged'),
        preparation_segments=preparation,pulse_rest_sequences=sequences,
        supported_activity='Recorded bipolar 1 Hz excitation and sampled rests on this fixture only',
        unsupported_transfer=['Sustained unipolar heat generation','Module temperatures or cooling','Thermal safety or design benefit',
            'Independent model validation','Achieved constant SOC','Internal total heat from terminal V*I'],
        model_parameter_fit='not attempted; definitions, calibration, boundary state and clocks insufficient',
        additional_experiments_opened=0)


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
        coverage=coverage_report(electrical,blocks),
        electrical_accounting=electrical_accounting(etime,electrical[:,1],electrical[:,2]*.001),
        alignment=dict(status='unresolved', applied_offset_s=None, resampling_performed=False),
        model_fitted=False, assessment_members_opened=0)


def create_plots(output, thermal, electrical, report):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False})
    fig,axes=plt.subplots(2,1,figsize=(11,6.5),sharex=True,layout='constrained')
    # Display-only one-minute extrema. All original points remain in NPZ and analysis.
    bins=np.floor(electrical[:,0]/60).astype(int)
    starts=np.r_[0,np.flatnonzero(np.diff(bins))+1]
    t=electrical[starts,0]/3600
    for ax,col,scale,label in [(axes[0],2,.001,'Native current (A; charge positive)'),(axes[1],1,1,'Terminal voltage (V)')]:
        values=electrical[:,col]*scale
        low=np.minimum.reduceat(values,starts); high=np.maximum.reduceat(values,starts)
        ax.fill_between(t,low,high,alpha=.6,color='#286d9c',label='One-minute recorded min/max envelope')
        ax.set_ylabel(label);ax.grid(alpha=.2);ax.legend(loc='upper left',fontsize=8)
    axes[1].set_xlabel('Hours since first electrical calendar timestamp (timezone unknown)')
    fig.suptitle('USED DEVELOPMENT: cell 1 test 103 | Electrical record, no thermal-clock alignment')
    fig.supxlabel('Source: M50/Electrical/M50_50SOC_20deg_cell1_test103_CF8.txt',fontsize=8)
    fig.savefig(output/'electrical_record.png',dpi=150);plt.close(fig)
    fig,ax=plt.subplots(figsize=(11,5),layout='constrained')
    for i,label in enumerate(CELL_LABELS):ax.plot(thermal[:,0]/3600,thermal[:,3+i],label=label,lw=.8)
    ax.set(xlabel='Raw thermal elapsed time (h; separate instrument origin)',ylabel='Recorded temperature (degC)')
    ax.grid(alpha=.2);ax.legend(ncol=3,fontsize=9)
    fig.suptitle('USED DEVELOPMENT: raw cell-surface channels | All duplicate timestamps retained')
    fig.supxlabel('Source: M50/M50_50SOC_20deg_cell1_test103.txt; physical mapping from author labels / paper',fontsize=8)
    fig.savefig(output/'thermal_record.png',dpi=150);plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(11,4.8),layout='constrained')
    representation=report['representation']['alternatives']
    for name,marker in [('omit_last_raw_row','o'),('omit_first_raw_row','x')]:
        rows=representation[name]
        axes[0].plot(np.arange(5),[r['range_of_difference_degC'] for r in rows],marker=marker,label=name.replace('_',' '))
    axes[0].set_xticks(np.arange(5),['cap','+ side','middle','- side','base'])
    axes[0].set(ylabel='Range of (processed - raw), degC',title='Representation identity, not clock alignment')
    axes[0].legend(fontsize=8);axes[0].grid(alpha=.2)
    processing=report['author_processing']
    factor=processing['implied_SS_Q_per_fin_deltaT']
    axes[1].scatter(processing['fin_temperature_difference_degC'],factor,color='#995a38')
    axes[1].set(xlabel='Author finH - finC (degC)',ylabel='SS_Q / fin temperature difference\n(native author units per K)',
        title='Implied processing scale; calibration unverified',ylim=(0,.3))
    axes[1].grid(alpha=.2)
    fig.suptitle('USED DEVELOPMENT: raw/MAT mapping and author-field algebra')
    fig.supxlabel('Sources: M50_50SOC_20deg_cell1_test103.txt and .mat | No fit, clock shift or temperature correction applied',fontsize=8)
    fig.savefig(output/'processing_diagnostics.png',dpi=150);plt.close(fig)


def read_and_decode():
    payloads,hashes={},{}
    with ZipFile(ARCHIVE) as archive:
        for member in ALLOW:
            payloads[member]=read_member(archive,member)
            hashes[member]=hashlib.sha256(payloads[member]).hexdigest()
    thermal,tmeta=parse_thermal(payloads[THERMAL])
    electrical,timestamp_text,emeta=parse_electrical(payloads[ELECTRICAL])
    arrays,mmeta=decode_matlab(payloads[MATLAB])
    return thermal,tmeta,electrical,timestamp_text,emeta,arrays,mmeta,hashes


def verify_import(output):
    """Hash check and exact numerical replay from only the three permitted sources."""
    output=Path(output)
    manifest=json.loads((output/'manifest.json').read_text())
    check_sources()
    if manifest['implementation_sha256']!=sha(__file__):raise ValueError('Implementation differs from recorded run')
    if manifest['opened']!=list(ALLOW) or manifest['allowed']!=list(ALLOW):raise ValueError('Source scope differs')
    for name,value in manifest['procedure_sha256'].items():
        if name not in PROCEDURE_NAMES or sha(REPORT/name)!=value:raise ValueError('Procedure changed: '+name)
    if set(manifest['procedure_sha256'])!=set(PROCEDURE_NAMES):raise ValueError('Missing procedure hash')
    required={'started.json','report.json','schema.json','quality.json','coverage.json','imported_arrays.npz',
              'electrical_record.png','thermal_record.png','processing_diagnostics.png'}
    if set(manifest['outputs_sha256'])!=required:raise ValueError('Missing/unexpected output mapping')
    for name,expected in manifest['outputs_sha256'].items():
        if sha(output/name)!=expected:raise ValueError('Output hash mismatch: '+name)
    thermal,tmeta,electrical,timestamps,emeta,arrays,mmeta,hashes=read_and_decode()
    if manifest['source_members_sha256']!=hashes:raise ValueError('Source member hash mismatch')
    replay=summarize(thermal,tmeta,electrical,emeta,arrays,mmeta)
    saved=json.loads((output/'report.json').read_text())
    if saved!=replay:raise ValueError('Diagnostic report differs on replay')
    expected_arrays=dict(thermal=thermal,electrical=electrical,electrical_timestamp_text=timestamps,
        **{'mat_'+k:v for k,v in arrays.items()})
    with np.load(output/'imported_arrays.npz',allow_pickle=False) as saved_arrays:
        if set(saved_arrays.files)!=set(expected_arrays):raise ValueError('Array keys differ')
        for name,expected in expected_arrays.items():
            if not np.array_equal(saved_arrays[name],expected):raise ValueError('Array replay differs: '+name)
    return dict(status='verified',source_member_count=3,assessment_members_opened=0,
        exact_report_and_array_replay=True,output_hashes_checked=len(required),model_fitted=False,
        manifest_sha256=sha(output/'manifest.json'))


PROCEDURE_NAMES=('PROCEDURE.md','FORMAT_ADDENDUM.md','ANALYSIS_DECLARATION.md','procedure_seal.json')


def import_record(output):
    output = Path(output).resolve()
    if output.exists() or not any(output.is_relative_to(ROOT / p) for p in ('tmp', 'data/processed/thermal_m50t')):
        raise ValueError('Choose a fresh local output directory under tmp or data/processed/thermal_m50t')
    check_sources()
    output.mkdir(parents=True)
    opened, hashes = [], {}
    started = dict(started_utc=datetime.now(timezone.utc).isoformat(), implementation_sha256=sha(__file__),
                   procedure_seal_sha256=sha(REPORT / 'procedure_seal.json'), allowed=list(ALLOW),
                   procedure_sha256={name:sha(REPORT/name) for name in PROCEDURE_NAMES})
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
        write_json(output / 'schema.json',dict(thermal=tmeta,electrical=emeta,matlab=mmeta))
        write_json(output / 'quality.json',dict(thermal=report['thermal']['time_quality'],electrical=report['electrical']['time_quality'],
            representation=report['representation'],author_processing=report['author_processing'],alignment=report['alignment']))
        write_json(output / 'coverage.json',report['coverage'])
        create_plots(output,thermal,electrical,report)
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
    mode=p.add_mutually_exclusive_group(required=True)
    mode.add_argument('--out',type=Path,help='Fresh ignored output directory; preserve previous attempts')
    mode.add_argument('--verify',type=Path,help='Hash check and exact replay of an existing completed run')
    args = p.parse_args()
    if args.verify:
        print(json.dumps(verify_import(args.verify)));return
    result = import_record(args.out)
    print(json.dumps(dict(status='imported development record', thermal_rows=result['thermal']['metadata']['rows'],
        electrical_rows=result['electrical']['metadata']['rows'], assessment_members_opened=0, model_fitted=False)))


if __name__ == '__main__':main()
