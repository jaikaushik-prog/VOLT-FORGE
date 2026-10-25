"""Read author predictions only for the already-used P45B discharge family."""
import argparse
import csv
import hashlib
import io
import json
import math
from pathlib import Path
from zipfile import ZipFile

import numpy as np

from ae_p45b_intake import AUTHOR_OUTPUTS, EXPERIMENTAL, experimental_rows, header
from ae_p45b_reproduction import ROOT, MEMBER, TABLE_NAME, Table25, sha, write_json, soc_region


def author_rows(data):
    if header(io.BytesIO(data)) != EXPERIMENTAL+AUTHOR_OUTPUTS:
        raise ValueError('Expected experimental plus author-output schema')
    measured = experimental_rows(data)['rows']
    reader = csv.reader(io.StringIO(data.decode('utf-8-sig')), strict=True)
    next(reader)
    combined = []
    for row, raw in zip(measured, reader, strict=True):
        author = {}
        for name, token in zip(AUTHOR_OUTPUTS, raw[4:], strict=True):
            value = None if token.strip() == '' else float(token)
            if value is not None and math.isnan(value):
                value = None
            if value is not None and not math.isfinite(value):
                raise ValueError(f'Infinite author value: {name} at line {row["source_line"]}')
            author['author_'+name] = value
        combined.append(dict(**row, **author))
    return combined


def read_own(data):
    rows = list(csv.DictReader(io.StringIO(data.decode('utf-8-sig'))))
    result = []
    fields = ['time_s','source_current_A','voltage_V','controlled_temperature_degC',
              'predicted_voltage_V','soc','hysteresis','v1_V','v2_V']
    for row in rows:
        item = {k:float(row[k]) for k in fields}
        if not all(math.isfinite(v) for v in item.values()):
            raise ValueError('Nonfinite saved reproduction row')
        item['source_line'] = int(row['source_line'])
        result.append(item)
    return result


def stats(times, values, unit, mask=None):
    """Errors in the explicitly named unit; no bridging missing/grouped points."""
    valid = np.array([v is not None for v in values], dtype=bool)
    if mask is not None:
        valid &= np.array(mask,dtype=bool)
    numeric = np.array([float(v) if v is not None else 0. for v in values])
    if not np.all(np.isfinite(numeric)):
        raise ValueError('Nonfinite statistic input')
    times = np.array(times,dtype=float)
    if len(times) != len(numeric) or not np.all(np.isfinite(times)) or np.any(np.diff(times) <= 0):
        raise ValueError('Invalid statistic time base')
    gap_limit = max(10.,10*float(np.median(np.diff(times)))) if len(times)>1 else 10.
    weights = np.zeros(len(times))
    for i, dt in enumerate(np.diff(times)):
        if valid[i] and valid[i+1] and dt <= gap_limit:
            weights[i] += dt/2; weights[i+1] += dt/2
    duration = float(sum(weights))
    selected = numeric[valid]
    return dict(unit=unit,samples=int(sum(valid)),covered_duration_s=duration,
        sample_rmse=float(np.sqrt(np.mean(selected**2))) if len(selected) else None,
        sample_bias=float(np.mean(selected)) if len(selected) else None,
        max_abs=float(max(abs(selected))) if len(selected) else None,
        time_rmse=float(np.sqrt(np.dot(weights,numeric**2)/duration)) if duration else None,
        time_bias=float(np.dot(weights,numeric)/duration) if duration else None)


def integrate(times, current, initial_soc, mode):
    if mode not in ('left','linear'):
        raise ValueError('Unknown integration convention')
    values = [initial_soc]
    gap_limit = max(10.,10*float(np.median(np.diff(times)))) if len(times)>1 else 10.
    for i, dt in enumerate(np.diff(times)):
        needed = [current[i]] if mode == 'left' else [current[i],current[i+1]]
        if values[-1] is None or any(v is None for v in needed) or dt > gap_limit:
            values.append(None)
        else:
            values.append(values[-1]+sum(needed)/len(needed)*dt/16200)
    return values


def compare(table, source, own):
    if len(source) != len(own) or not source:
        raise ValueError('Source/reproduction length mismatch')
    rows = []
    for source_row, our in zip(source,own):
        for k in ('source_line','time_s','source_current_A','voltage_V','controlled_temperature_degC'):
            if source_row[k] != our[k]:
                raise ValueError('Source/reproduction alignment or measured-value mismatch: '+k)
        row = dict(source_row)
        row.update({f'ours_{k}':our[k] for k in ('predicted_voltage_V','soc','hysteresis','v1_V','v2_V')})
        row['soc_region'] = soc_region(our['soc'])
        row['ours_minus_measured_mV'] = 1000*(our['predicted_voltage_V']-source_row['voltage_V'])
        va = source_row['author_V_sim_V']
        row['author_minus_measured_mV'] = 1000*(va-source_row['voltage_V']) if va is not None else None
        row['ours_minus_author_mV'] = 1000*(our['predicted_voltage_V']-va) if va is not None else None
        p, _ = table.query(our['soc'])
        ours_ref = (1+our['hysteresis'])/2*p.ocv_charge_V+(1-our['hysteresis'])/2*p.ocv_discharge_V
        row['ours_reference_V'] = float(ours_ref)
        row['ours_ohmic_V'] = float(our['source_current_A']*p.r0_Ohm)
        row['ours_polarization_total_V'] = our['v1_V']+our['v2_V']
        components = ['table_discharge_at_author_soc_V','author_polarization_inferred_V',
            'reference_difference_mV','ohmic_difference_mV','polarization_difference_mV',
            'decomposition_closure_mV','reference_soc_coordinate_difference_mV',
            'reference_same_soc_branch_difference_mV']
        row.update({k:None for k in components})
        row['decomposition_status'] = 'missing author state or output'
        names = ['author_SOC_sim','author_E_OCV_V','author_I_sim_A','author_V_sim_V','author_T_sim_degC']
        if all(row[k] is not None for k in names):
            if row['author_T_sim_degC'] != 25:
                row['decomposition_status'] = 'author temperature unsupported by exact-25-degC lookup'
            else:
                try:
                    pa, _ = table.query(row['author_SOC_sim'])
                except ValueError:
                    row['decomposition_status'] = 'author SOC outside published reference; no extension'
                else:
                    author_ohmic = row['author_I_sim_A']*pa.r0_Ohm
                    remainder = va-row['author_E_OCV_V']-author_ohmic
                    ref_diff = ours_ref-row['author_E_OCV_V']
                    ohmic_diff = row['ours_ohmic_V']-author_ohmic
                    polarization_diff = row['ours_polarization_total_V']-remainder
                    row.update(table_discharge_at_author_soc_V=float(pa.ocv_discharge_V),
                        author_polarization_inferred_V=float(remainder),
                        reference_difference_mV=float(1000*ref_diff),
                        ohmic_difference_mV=float(1000*ohmic_diff),
                        polarization_difference_mV=float(1000*polarization_diff),
                        decomposition_closure_mV=float(row['ours_minus_author_mV']-1000*(ref_diff+ohmic_diff+polarization_diff)),
                        reference_soc_coordinate_difference_mV=float(1000*(ours_ref-pa.ocv_discharge_V)),
                        reference_same_soc_branch_difference_mV=float(1000*(pa.ocv_discharge_V-row['author_E_OCV_V'])),
                        decomposition_status='defined; author polarization is algebraic inferred remainder')
        rows.append(row)
    times = [r['time_s'] for r in rows]
    measurements = [r['source_current_A'] for r in rows]
    author_current = [r['author_I_sim_A'] for r in rows]
    own_soc0 = rows[0]['ours_soc']
    author_soc0 = rows[0]['author_SOC_sim']
    soc_checks = {}
    for channel,current,origin in [('measured_current',measurements,own_soc0),('author_current',author_current,author_soc0)]:
        for mode in ('left','linear'):
            calculated = integrate(times,current,origin,mode)
            errors = [r['author_SOC_sim']-z if r['author_SOC_sim'] is not None and z is not None else None for r,z in zip(rows,calculated)]
            key = f'author_SOC_minus_{channel}_{mode}_integral'
            soc_checks[key] = stats(times,errors,'SOC fraction')
            for row,z,error in zip(rows,calculated,errors):
                row[key] = error
                row[f'{channel}_{mode}_integrated_soc'] = z
    voltage_keys = ['ours_minus_measured_mV','author_minus_measured_mV','ours_minus_author_mV']
    common = [all(r[k] is not None for k in voltage_keys) for r in rows]
    voltage = {k:dict(all_available=stats(times,[r[k] for r in rows],'mV'),
        identical_common_samples=stats(times,[r[k] for r in rows],'mV',common)) for k in voltage_keys}
    by_soc = {region:{k:stats(times,[r[k] for r in rows],'mV',[c and r['soc_region']==region for c,r in zip(common,rows)]) for k in voltage_keys}
        for region in sorted({r['soc_region'] for r in rows})}
    component_stats = {k:stats(times,[r[k] for r in rows],'mV') for k in components if k.endswith('_mV')}
    diagnostics = {}
    for name,a,b,unit in [('current_difference','source_current_A','author_I_sim_A','A'),
        ('soc_difference','ours_soc','author_SOC_sim','SOC fraction'),
        ('temperature_difference','controlled_temperature_degC','author_T_sim_degC','degC')]:
        diagnostics[name] = stats(times,[r[a]-r[b] if r[b] is not None else None for r in rows],unit)
    power_errors = [r['author_Q_sim_W']-r['author_I_sim_A']*r['author_V_sim_V']
        if all(r[k] is not None for k in ['author_Q_sim_W','author_I_sim_A','author_V_sim_V']) else None for r in rows]
    diagnostics['author_power_minus_current_times_voltage'] = stats(times,power_errors,'W')
    crossings = {}
    for key in ('voltage_V','ours_predicted_voltage_V','author_V_sim_V'):
        crossing = next((r for r in rows if r[key] is not None and r[key] <= 2.5),None)
        crossings[key] = dict(source_line=crossing['source_line'],time_s=crossing['time_s'],voltage_V=crossing[key]) if crossing else None
    summary = dict(evidence_class='same development record; comparison of predictions, not independent validation',
        rows=len(rows), author_missing_counts={k:sum(r['author_'+k] is None for r in rows) for k in AUTHOR_OUTPUTS},
        voltage_comparisons=voltage,by_unchanged_ours_soc=by_soc,
        state_diagnostics=diagnostics,soc_integral_checks=soc_checks,
        voltage_decomposition=component_stats,
        decomposition_status_counts={s:sum(r['decomposition_status']==s for r in rows) for s in sorted({r['decomposition_status'] for r in rows})},
        protocol_cutoff_V=2.5,protocol_crossings=crossings,requirement_status='requirement not configured',
        first_row=rows[0],last_row=rows[-1],parameters_or_initial_states_changed=False,
        unused_archive_members=50,validation_workbook_opened=False,
        author_polarization_status='inferred algebraic remainder; not measured or separately disclosed RC states')
    return rows,summary


def plot(rows,out):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    t=np.array([r['time_s'] for r in rows])/60
    fig,axes=plt.subplots(3,1,figsize=(11,9),sharex=True,constrained_layout=True)
    for key,label,color in [('voltage_V','Measured','#172d39'),('ours_predicted_voltage_V','VOLT-FORGE reproduction','#167c91'),('author_V_sim_V','Authors\' prediction','#bb6636')]:
        axes[0].plot(t,[r[key] for r in rows],label=label,color=color,lw=1.5)
    for key,label,color in [('ours_minus_measured_mV','VOLT-FORGE - measured','#167c91'),('author_minus_measured_mV','Authors - measured','#bb6636'),('ours_minus_author_mV','VOLT-FORGE - authors','#80648f')]:
        axes[1].plot(t,[r[key] for r in rows],label=label,color=color,lw=1)
    for key,label in [('reference_difference_mV','Reference contribution'),('ohmic_difference_mV','Ohmic contribution'),('polarization_difference_mV','Inferred polarization contribution')]:
        axes[2].plot(t,[r[key] for r in rows],label=label,lw=1)
    for ax,label in zip(axes,['Voltage (V)','Voltage differences (mV)','Ours - authors contributions (mV)']):
        ax.set_ylabel(label);ax.grid(alpha=.2);ax.legend(fontsize=8)
    axes[2].set_xlabel('Recorded time (min)')
    fig.suptitle('P45B 25 degC 1C discharge: same-record author comparison\nPublished author outputs are predictions, not additional measurements')
    fig.savefig(out/'author_voltage_comparison.png',dpi=160);plt.close(fig)
    fig,axes=plt.subplots(3,1,figsize=(11,9),sharex=True,constrained_layout=True)
    for key,label in [('ours_soc','VOLT-FORGE SOC'),('author_SOC_sim','Author simulated SOC')]:
        axes[0].plot(t,[r[key] for r in rows],label=label)
    axes[1].plot(t,[r['ours_soc']-r['author_SOC_sim'] if r['author_SOC_sim'] is not None else np.nan for r in rows],label='VOLT-FORGE - author SOC')
    for key,label in [('ours_reference_V','Reference at our SOC'),('table_discharge_at_author_soc_V','Table discharge branch at author SOC'),('author_E_OCV_V','Author reference output')]:
        axes[2].plot(t,[r[key] for r in rows],label=label)
    for ax,label in zip(axes,['SOC fraction','SOC difference','Reference voltage (V)']):
        ax.set_ylabel(label);ax.grid(alpha=.2);ax.legend(fontsize=8)
    axes[2].set_xlabel('Recorded time (min)')
    fig.suptitle('SOC and reference diagnostics: simulated states and loaded-pOCV model references')
    fig.savefig(out/'author_state_comparison.png',dpi=160);plt.close(fig)


def load_sources():
    lock=json.loads((ROOT/'configs/ae_p45b_author_comparison_v1.json').read_text())
    for name,expected in lock['preaccess_files'].items():
        if sha(ROOT/name)!=expected:raise ValueError('Source or frozen-artifact mismatch: '+name)
    if lock['allowed_member']!=MEMBER:raise ValueError('Unallocated archive member')
    with ZipFile(ROOT/'molicel_p45b_data.zip') as archive:data=archive.read(MEMBER)
    if hashlib.sha256(data).hexdigest()!=lock['member_sha256']:raise ValueError('Member hash mismatch')
    return Table25((ROOT/TABLE_NAME).read_bytes()),author_rows(data),read_own((ROOT/lock['own_prediction']).read_bytes()),lock


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args();out=args.out.resolve()
    if not any(out.is_relative_to(ROOT/n) for n in ('reports','tmp','workspace')):raise SystemExit('Write under reports/, tmp/ or workspace/.')
    if out.exists():raise SystemExit('Use a new directory; preserve prior results.')
    table,source,own,lock=load_sources()
    rows,summary=compare(table,source,own)
    summary.update(schema_version='voltforge.ae_p45b_author_comparison/1',source_lock=lock,
        implementation_sha256={n:sha(ROOT/n) for n in ['scripts/ae_p45b_author_comparison.py','scripts/ae_p45b_reproduction.py','scripts/ae_p45b_equations.py','scripts/ae_p45b_intake.py']})
    out.mkdir(parents=True)
    with (out/'comparison.csv').open('x',encoding='utf-8',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    write_json(out/'summary.json',summary);plot(rows,out)
    write_json(out/'manifest.json',{p.name:sha(p) for p in sorted(out.iterdir()) if p.is_file()})
    print(json.dumps(summary['voltage_comparisons'],indent=2))
    print(json.dumps(summary['state_diagnostics'],indent=2))


if __name__=='__main__':main()
