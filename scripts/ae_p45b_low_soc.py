"""Two-record low-SOC diagnosis; no fitting, reference extension or model revision."""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
from zipfile import ZipFile

import numpy as np

from ae_p45b_intake import experimental_rows
from ae_p45b_reproduction import ROOT, TABLE_NAME, Table25, sha, write_json, soc_region

MEMBERS={'co30':'MOLICEL_P45B_025degC_Co30_Dch.csv',
         'gitt':'MOLICEL_P45B_025degC_GITT_Dch.csv'}


def phase(current):
    return 'rest' if abs(current)<=.05 else ('discharge' if current<0 else 'charge')


def error_stats(rows,mask):
    selected=np.array([bool(m) and r['reference_minus_measured_mV'] is not None for m,r in zip(mask,rows)])
    error=np.array([r['reference_minus_measured_mV'] or 0. for r in rows])
    weights=np.zeros(len(rows))
    for i in range(len(rows)-1):
        if selected[i] and selected[i+1] and not rows[i+1]['gap_before']:
            dt=rows[i+1]['time_s']-rows[i]['time_s'];weights[i]+=dt/2;weights[i+1]+=dt/2
    values=error[selected];duration=float(sum(weights))
    return dict(samples=int(sum(selected)),covered_duration_s=duration,
        sample_rmse_mV=float(np.sqrt(np.mean(values**2))) if len(values) else None,
        sample_bias_mV=float(np.mean(values)) if len(values) else None,
        max_abs_mV=float(max(abs(values))) if len(values) else None,
        time_rmse_mV=float(np.sqrt(np.dot(weights,error**2)/duration)) if duration else None,
        time_bias_mV=float(np.dot(weights,error)/duration) if duration else None,
        interpretation='table discharge reference minus measured voltage; NOT dynamic prediction error')


def annotate(table,source):
    if len(source)<2:raise ValueError('Need at least two measured samples')
    t=np.array([r['time_s'] for r in source]);current=np.array([r['source_current_A'] for r in source])
    dt=np.diff(t)
    if not np.all(np.isfinite(t)) or np.any(dt<=0):raise ValueError('Invalid measurement time base')
    limit=max(120.,10*float(np.median(dt)))
    gaps=np.r_[False,dt>limit]
    soc=left=1.
    rows=[];segment_id=0
    for index,row in enumerate(source):
        if index:
            if gaps[index] or soc is None:soc=left=None
            else:
                soc+=(current[index-1]+current[index])/2*dt[index-1]/16200
                left+=current[index-1]*dt[index-1]/16200
            if gaps[index] or phase(current[index])!=rows[-1]['phase']:segment_id+=1
        item=dict(**row,phase=phase(current[index]),segment_id=segment_id,gap_before=bool(gaps[index]),
            nominal_soc_linear=float(soc) if soc is not None else None,
            nominal_soc_left=float(left) if left is not None else None,
            soc_region=soc_region(soc),reference_discharge_V=None,reference_charge_V=None,
            reference_minus_measured_mV=None,
            reference_status='unknown SOC after possible acquisition gap',
            temperature_evidence='within 1.5 degC of nominal' if abs(row['controlled_temperature_degC']-25)<=1.5 else 'outside 1.5 degC of nominal')
        if soc is not None:
            try:p,_=table.query(float(soc))
            except ValueError:item['reference_status']='outside lookup support; no extension'
            else:
                item.update(reference_discharge_V=float(p.ocv_discharge_V),reference_charge_V=float(p.ocv_charge_V),
                    reference_minus_measured_mV=float(1000*(p.ocv_discharge_V-row['voltage_V'])),
                    reference_status='defined at assumed nominal SOC and 25 degC; no equilibrium claim')
        rows.append(item)
    cross=next((r for r in rows if r['phase']=='discharge' and r['voltage_V']<=2.5),None)
    known=[r for r in rows if r['nominal_soc_linear'] is not None]
    summary=dict(samples=len(rows),duration_s=float(t[-1]-t[0]),time_interval_s=dict(min=float(min(dt)),
        median=float(np.median(dt)),p95=float(np.percentile(dt,95)),max=float(max(dt))),
        possible_gap_limit_s=limit,possible_gaps=int(sum(gaps)),
        current_charge_positive_A=[float(min(current)),float(max(current))],
        measured_voltage_V=[min(r['voltage_V'] for r in rows),max(r['voltage_V'] for r in rows)],
        recorded_temperature_degC=[min(r['controlled_temperature_degC'] for r in rows),max(r['controlled_temperature_degC'] for r in rows)],
        initial_state='nominal SOC=1 at first sample assumed, not fitted',nominal_capacity_Ah=4.5,
        final_soc_linear=rows[-1]['nominal_soc_linear'],final_soc_left=rows[-1]['nominal_soc_left'],
        integrated_discharge_Ah_linear=4.5*(1-rows[-1]['nominal_soc_linear']) if soc is not None else None,
        max_soc_integration_convention_difference=float(max(abs(r['nominal_soc_linear']-r['nominal_soc_left']) for r in known)),
        unknown_soc_rows=sum(r['nominal_soc_linear'] is None for r in rows),
        unsupported_reference_rows=sum(r['reference_discharge_V'] is None for r in rows),
        temperature_deviation_rows=sum(r['temperature_evidence'].startswith('outside') for r in rows),
        first_protocol_2p5V_crossing={k:cross[k] for k in ['source_line','time_s','voltage_V','nominal_soc_linear']} if cross else None,
        reference_errors_by_phase={p:error_stats(rows,[r['phase']==p for r in rows]) for p in sorted({r['phase'] for r in rows})},
        discharge_reference_errors_by_soc={z:error_stats(rows,[r['phase']=='discharge' and r['soc_region']==z for r in rows]) for z in sorted({r['soc_region'] for r in rows})})
    return rows,summary


def segments(table,rows):
    result=[];start=0
    for end in range(1,len(rows)+1):
        if end<len(rows) and rows[end]['segment_id']==rows[start]['segment_id']:continue
        group=rows[start:end];first,last=group[0],group[-1]
        seg=dict(segment_id=first['segment_id'],phase=first['phase'],start_index=start,end_index=end-1,
            first_source_line=first['source_line'],last_source_line=last['source_line'],samples=len(group),
            start_time_s=first['time_s'],end_time_s=last['time_s'],duration_s=last['time_s']-first['time_s'],
            gap_before=first['gap_before'],initial_soc=first['nominal_soc_linear'],final_soc=last['nominal_soc_linear'],
            first_voltage_V=first['voltage_V'],last_voltage_V=last['voltage_V'],
            first_current_A=first['source_current_A'],last_current_A=last['source_current_A'],
            current_min_A=min(r['source_current_A'] for r in group),current_max_A=max(r['source_current_A'] for r in group),
            late_window_samples=None,late_window_span_s=None,late_rest_median_V=None,
            late_rest_slope_mV_per_min=None,late_window_first_source_line=None,
            reference_discharge_V=last['reference_discharge_V'],reference_charge_V=last['reference_charge_V'],
            reference_minus_late_rest_mV=None)
        if first['phase']=='rest':
            late=[r for r in group if r['time_s']>=last['time_s']-60]
            span=late[-1]['time_s']-late[0]['time_s'];median=float(np.median([r['voltage_V'] for r in late]))
            slope=None
            if len(late)>=3 and span>=30:
                x=np.array([r['time_s']-late[0]['time_s'] for r in late]);y=np.array([r['voltage_V'] for r in late])
                slope=float(np.dot(x-x.mean(),y-y.mean())/np.dot(x-x.mean(),x-x.mean())*60000)
            seg.update(late_window_samples=len(late),late_window_span_s=span,late_rest_median_V=median,
                late_rest_slope_mV_per_min=slope,late_window_first_source_line=late[0]['source_line'],
                reference_minus_late_rest_mV=1000*(last['reference_discharge_V']-median) if last['reference_discharge_V'] is not None else None)
        result.append(seg);start=end
    pairs=[]
    for a,b in zip(result,result[1:]):
        if a['phase']!='discharge' or b['phase']!='rest' or b['gap_before']:continue
        delta_i=b['first_current_A']-a['last_current_A'];delta_t=b['start_time_s']-a['end_time_s']
        pair=dict(pair_index=len(pairs),pulse_segment_id=a['segment_id'],rest_segment_id=b['segment_id'],
            contiguous_with_previous_pair=bool(pairs and pairs[-1]['rest_segment_id']+1==a['segment_id']),
            pulse_last_source_line=a['last_source_line'],rest_first_source_line=b['first_source_line'],rest_last_source_line=b['last_source_line'],
            pulse_duration_s=a['duration_s'],rest_duration_s=b['duration_s'],transition_sample_separation_s=delta_t,
            loaded_endpoint_soc=a['final_soc'],rest_endpoint_soc=b['final_soc'],loaded_voltage_V=a['last_voltage_V'],
            first_rest_voltage_V=b['first_voltage_V'],late_rest_median_V=b['late_rest_median_V'],
            late_rest_slope_mV_per_min=b['late_rest_slope_mV_per_min'],
            loaded_to_late_rest_recovery_mV=1000*(b['late_rest_median_V']-a['last_voltage_V']),
            pulse_endpoint_current_A=a['last_current_A'],
            apparent_transition_resistance_Ohm=(b['first_voltage_V']-a['last_voltage_V'])/delta_i if abs(delta_i)>=.1 and delta_t<=1 else None,
            table_r0_Ohm=None,table_r1_plus_r2_Ohm=None,table_tau1_s=None,table_tau2_s=None,
            table_steady_drop_scale_mV=None,observed_recovery_minus_steady_scale_mV=None,
            cross_record_endpoint_eligible=bool(b['duration_s']>=600 and b['final_soc'] is not None),
            interpretation='finite-rest recovery; steady drop scale is not a transient prediction')
        if a['final_soc'] is not None:
            try:p,_=table.query(a['final_soc'])
            except ValueError:pass
            else:
                scale=abs(a['last_current_A'])*(p.r0_Ohm+p.r1_Ohm+p.r2_Ohm)*1000
                pair.update(table_r0_Ohm=float(p.r0_Ohm),table_r1_plus_r2_Ohm=float(p.r1_Ohm+p.r2_Ohm),
                    table_tau1_s=float(p.r1_Ohm*p.c1_F),table_tau2_s=float(p.r2_Ohm*p.c2_F),
                    table_steady_drop_scale_mV=float(scale),observed_recovery_minus_steady_scale_mV=float(pair['loaded_to_late_rest_recovery_mV']-scale))
        pairs.append(pair)
    return result,pairs


def interpolate_adjacent(points,queries):
    """Points keep original order and nulls: no bridging exclusions or reversals."""
    results=[]
    for query in queries:
        candidates=[]
        for a,b in zip(points,points[1:]):
            if a is None or b is None:continue
            za,va,la=a;zb,vb,lb=b
            if za>zb and zb<=query<=za:
                f=(za-query)/(za-zb);candidates.append((va+(vb-va)*f,la,lb))
        if not candidates:results.append(dict(value_V=None,status='outside contiguous overlap',source_line_a=None,source_line_b=None))
        elif len(candidates)>1 and max(c[0] for c in candidates)-min(c[0] for c in candidates)>1e-10:
            results.append(dict(value_V=None,status='ambiguous repeated SOC interval',source_line_a=None,source_line_b=None))
        else:
            v,a,b=candidates[0];results.append(dict(value_V=float(v),status='interpolated at assumed shared nominal SOC',source_line_a=a,source_line_b=b))
    return results


def cross_record(co30,gitt_pairs,own):
    # A gap marker also suppresses the following interval conservatively; no bridging.
    slow=[(r['nominal_soc_linear'],r['voltage_V'],r['source_line']) if r['phase']=='discharge' and r['nominal_soc_linear'] is not None and not r['gap_before'] else None for r in co30]
    rests=[]
    for p in gitt_pairs:
        if rests and not p['contiguous_with_previous_pair']:rests.append(None)
        rests.append((p['rest_endpoint_soc'],p['late_rest_median_V'],p['rest_last_source_line']) if p['cross_record_endpoint_eligible'] else None)
    queries=[r['soc'] for r in own]
    aa=interpolate_adjacent(slow,queries);bb=interpolate_adjacent(rests,queries)
    rows=[]
    for r,a,b in zip(own,aa,bb):
        item=dict(oneC_source_line=r['source_line'],oneC_time_s=r['time_s'],oneC_nominal_soc=r['soc'],
            oneC_measured_voltage_V=r['voltage_V'],oneC_predicted_voltage_V=r['predicted_voltage_V'])
        for prefix,value in [('co30_loaded',a),('gitt_late_rest',b)]:
            item.update({prefix+'_'+k:v for k,v in value.items()})
            item[prefix+'_minus_oneC_loaded_mV']=1000*(value['value_V']-r['voltage_V']) if value['value_V'] is not None else None
        rows.append(item)
    return rows


def write_csv(path,rows):
    if not rows:
        path.write_text('no_records\n',encoding='utf-8');return
    with path.open('x',newline='',encoding='utf-8') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)


def load_sources():
    lock=json.loads((ROOT/'configs/ae_p45b_low_soc_v1.json').read_text())
    if lock['allowed_members']!=MEMBERS:raise ValueError('Unexpected allocation')
    for name,expected in lock['preaccess_files'].items():
        if sha(ROOT/name)!=expected:raise ValueError('Source or frozen-file mismatch: '+name)
    sources={}
    with ZipFile(ROOT/'molicel_p45b_data.zip') as archive:
        for key,name in MEMBERS.items():
            data=archive.read(name)
            if hashlib.sha256(data).hexdigest()!=lock['member_sha256'][key]:raise ValueError('Member checksum mismatch')
            normalized=experimental_rows(data)
            if normalized['excluded_author_fields']:raise ValueError('Expected experimental-only characterization')
            sources[key]=normalized['rows']
    with (ROOT/lock['oneC_saved_trace']).open(newline='',encoding='utf-8') as stream:
        own=[dict(source_line=int(r['source_line']),**{k:float(r[k]) for k in ['time_s','soc','voltage_V','predicted_voltage_V']}) for r in csv.DictReader(stream)]
    return Table25((ROOT/TABLE_NAME).read_bytes()),sources,own,lock


def plot(table,records,pairs,cross,out):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(2,1,figsize=(11,9),constrained_layout=True)
    for ax in axes:
        ax.plot(table.soc,[p[1] for p in table.values],label='Published discharge reference',color='#2a6e83')
        ax.plot([r['nominal_soc_linear'] for r in records['co30'] if r['phase']=='discharge'],[r['voltage_V'] for r in records['co30'] if r['phase']=='discharge'],label='C/30 loaded voltage',color='#bf793c')
        eligible=[p for p in pairs if p['cross_record_endpoint_eligible']]
        ax.scatter([p['rest_endpoint_soc'] for p in eligible],[p['late_rest_median_V'] for p in eligible],label='GITT late-rest median (rest >=600 s)',s=18,color='#648352')
        ax.plot([r['oneC_nominal_soc'] for r in cross],[r['oneC_measured_voltage_V'] for r in cross],label='1C measured loaded voltage',color='#25323b')
        ax.set_xlabel('Nominal SOC: assumed origin and 4.5 Ah');ax.set_ylabel('Voltage (V)');ax.grid(alpha=.2);ax.legend(fontsize=8)
    axes[1].set_xlim(-.025,.22)
    fig.suptitle('P45B 25 degC: loaded reference and finite-rest observations\nCross-record cell identity and preparation equivalence are unverified')
    fig.savefig(out/'reference_comparison.png',dpi=160);plt.close(fig)
    fig,axes=plt.subplots(3,1,figsize=(11,9),sharex=True,constrained_layout=True)
    rows=records['gitt'];t=np.array([r['time_s'] for r in rows])/3600
    axes[0].plot(t,[r['voltage_V'] for r in rows],lw=.7);axes[0].set_ylabel('Measured voltage (V)')
    axes[1].plot(t,[r['source_current_A'] for r in rows],lw=.7);axes[1].set_ylabel('Current (A)\ncharge positive')
    axes[2].plot(t,[r['controlled_temperature_degC'] for r in rows]);axes[2].set_ylabel('Recorded temperature (degC)');axes[2].set_xlabel('Recorded time (h)')
    for ax in axes:ax.grid(alpha=.2)
    fig.suptitle('Complete GITT discharge record; all pulse/rest segments retained')
    fig.savefig(out/'gitt_sequence.png',dpi=160);plt.close(fig)
    fig,axes=plt.subplots(2,1,figsize=(11,8),sharex=True,constrained_layout=True)
    axes[0].plot([p['loaded_endpoint_soc'] for p in pairs],[p['loaded_to_late_rest_recovery_mV'] for p in pairs],'o-',label='Observed recovery to late-rest median')
    axes[0].plot([p['loaded_endpoint_soc'] for p in pairs],[p['table_steady_drop_scale_mV'] for p in pairs],'o-',label='Unchanged table |I|*(R0+R1+R2)')
    axes[0].set_ylabel('Voltage difference (mV)');axes[0].legend(fontsize=8)
    axes[1].plot([p['rest_endpoint_soc'] for p in pairs],[p['late_rest_slope_mV_per_min'] for p in pairs],'o-')
    axes[1].set_ylabel('Last 60 s slope (mV/min)');axes[1].set_xlabel('Assumed nominal SOC')
    for ax in axes:ax.grid(alpha=.2)
    fig.suptitle('GITT recovery diagnostics: steady drop scale is not a transient prediction\nA small late-rest slope does not prove equilibrium')
    fig.savefig(out/'gitt_recovery.png',dpi=160);plt.close(fig)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args();out=args.out.resolve()
    if not any(out.is_relative_to(ROOT/n) for n in ('reports','tmp','workspace')):raise SystemExit('Write under reports/, tmp/ or workspace/.')
    if out.exists():raise SystemExit('Use a new directory; preserve earlier outputs.')
    table,sources,own,lock=load_sources()
    results={};summaries={};all_pairs={};all_segments={}
    for key,source in sources.items():
        results[key],summaries[key]=annotate(table,source)
        all_segments[key],all_pairs[key]=segments(table,results[key])
        summaries[key].update(segments=len(all_segments[key]),pulse_rest_pairs=len(all_pairs[key]))
    cross=cross_record(results['co30'],all_pairs['gitt'],own)
    summary=dict(schema_version='voltforge.ae_p45b_low_soc_diagnosis/1',source_lock=lock,records=summaries,
        cross_record_oneC_final_sample=cross[-1],
        cross_record_covered_oneC_samples={k:sum(r[k+'_value_V'] is not None for r in cross) for k in ['co30_loaded','gitt_late_rest']},
        reference_comparisons_are_terminal_prediction_errors=False,
        cross_record_same_cell_and_preparation_verified=False,late_rest_is_equilibrium_OCV=False,
        model_parameters_changed=False,initial_states_fitted=False,remaining_unopened_members=48,
        validation_workbook_opened=False,requirement_status='requirement not configured',
        implementation_sha256={n:sha(ROOT/n) for n in ['scripts/ae_p45b_low_soc.py','scripts/ae_p45b_reproduction.py','scripts/ae_p45b_intake.py']})
    out.mkdir(parents=True)
    for key in results:
        write_csv(out/(key+'_samples.csv'),results[key]);write_csv(out/(key+'_segments.csv'),all_segments[key]);write_csv(out/(key+'_pairs.csv'),all_pairs[key])
    write_csv(out/'cross_record.csv',cross);write_json(out/'summary.json',summary)
    plot(table,results,all_pairs['gitt'],cross,out)
    write_json(out/'manifest.json',{p.name:sha(p) for p in sorted(out.iterdir()) if p.is_file()})
    print(json.dumps(summaries,indent=2));print(json.dumps(summary['cross_record_oneC_final_sample'],indent=2))


if __name__=='__main__':main()
