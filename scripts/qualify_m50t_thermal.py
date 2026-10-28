"""Qualify one allocated calibration record, without reading the Cell 2 holdout.

Research-only dependencies: numpy and h5py. This script never changes installed
cell parameters or grants a thermal accuracy claim.
"""
from pathlib import Path
import argparse
import hashlib
import io
import json
import zipfile

import h5py
import numpy as np

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--archive',type=Path,default=ROOT/'data/raw/imperial_m50t_thermal/M50.zip')
    parser.add_argument('--allocation',type=Path,default=ROOT/'configs/m50t_thermal_allocation_v1.json')
    parser.add_argument('--out',type=Path,default=ROOT/'reports/round1_source_qualification')
    args=parser.parse_args();args.out.mkdir(parents=True,exist_ok=True)
    allocation=json.loads(args.allocation.read_text());raw=args.archive.read_bytes()
    if hashlib.md5(raw).hexdigest()!=allocation['source']['publisher_md5'] or len(raw)!=allocation['source']['bytes']:
        raise ValueError('Archive does not match the publisher metadata.')
    records=[(key,r) for key,r in allocation['records'].items() if r['role']=='calibration']
    if len(records)!=1:raise ValueError('This source-qualification procedure expects one allocated calibration record.')
    key,record=records[0]
    allowed={m['name'] for m in record['members']}
    ledger=[];signals={}
    with zipfile.ZipFile(args.archive) as archive:
        for member in record['members']:
            name=member['name']
            if name not in allowed:raise ValueError('Unallocated observation access.')
            payload=archive.read(name)
            ledger.append(dict(record=key,role='calibration',member=name,sha256=hashlib.sha256(payload).hexdigest(),
                               access='Calibration parser/channel qualification. Numeric calibration channels may be inspected; Cell 2 observations remain unopened.'))
            # Persist access before parsing, including a failed parsing attempt.
            (args.out/'thermal_calibration_access.json').write_text(json.dumps(ledger,indent=2)+'\n')
            signals[member['format']]=payload
    text=signals['raw_thermal_text'].replace(b'\x00',b'').decode('cp1252')
    header,units,*_=text.splitlines()[:3]
    thermal=np.loadtxt(io.StringIO(text),delimiter='\t',skiprows=2)
    if thermal.shape[1]!=16 or len(header.split('\t'))!=16:raise ValueError('Thermal logger channel layout changed.')
    time=thermal[:,0]
    if not np.isfinite(thermal).all() or np.any(np.diff(time)<0):raise ValueError('Invalid thermal clock or signal values.')
    with h5py.File(io.BytesIO(signals['processed_thermal_mat']),'r') as f:
        data=f['data'];processed=np.asarray(data['celltemps'],float).T
        labels=[''.join(chr(int(v)) for v in np.asarray(f[ref]).ravel()) for ref in np.asarray(data['templabels']).ravel()]
        candidates=[]
        for offset in (0,1):
            aligned=thermal[offset:offset+len(processed),3:8]
            if aligned.shape==processed.shape:candidates.append((float(np.max(abs(aligned-processed))),offset))
        if not candidates:raise ValueError('Processed/raw thermal sample counts cannot be reconciled.')
        difference,offset=min(candidates)
        channel_difference=processed-thermal[offset:offset+len(processed),3:8]
        channel_offsets=np.median(channel_difference,axis=0)
        residual_after_offsets=float(np.max(abs(channel_difference-channel_offsets)))
        delta_temperature=np.asarray(data['SS_delT'],float).ravel()
        author_heat_flow=np.asarray(data['SS_Q'],float).ravel()
        X=np.column_stack([delta_temperature,np.ones(len(delta_temperature))])
        conductance,heat_offset=np.linalg.lstsq(X,author_heat_flow,rcond=None)[0]
        steady_residual=author_heat_flow-X@np.array([conductance,heat_offset])
        source_error_scalars={name:np.asarray(data[name],float).tolist() for name in ('errQ','errdelT')}
        layout={name:dict(shape=list(obj.shape),dtype=str(obj.dtype)) for name,obj in data.items() if isinstance(obj,h5py.Dataset)}
    electrical=signals['raw_electrical_text'].decode('cp1252').splitlines()
    count=int(electrical[1].split(':')[1]);electrical_header=electrical[count-1].split('\t')
    first_electrical_time=electrical[count].split('\t')[0]
    contract=dict(version='voltforge.m50t-thermal-source-qualification/1',classification='Calibration data qualification; no model accuracy result',
        source=allocation['source'],archive_sha256=hashlib.sha256(raw).hexdigest(),allocation_sha256=hashlib.sha256(args.allocation.read_bytes()).hexdigest(),
        allocated_roles={role:sum(r['role']==role for r in allocation['records'].values()) for role in ('calibration','development_validation','final_assessment_reserved')},
        calibration_record=key,holdout_observations_decoded=False,
        thermal=dict(rows=len(time),raw_column_count=16,start_s=float(time[0]),end_s=float(time[-1]),median_sample_interval_s=float(np.median(np.diff(time))),
                     duplicate_timestamps=int(np.sum(np.diff(time)==0)),largest_logged_interval_s=float(np.max(np.diff(time))),
                     clock_policy='Keep logged order and duplicate timestamps. A nominal 1 s logging interval is not a promise of a perfectly uniform clock.',
                     units='Time in seconds and thermocouple channels in degrees Celsius, from the raw units row.',
                     processed_labels=labels,processed_layout=layout,processed_raw_cell_temperature_offset_rows=offset,
                     maximum_processed_raw_difference_C=difference,
                     author_constant_temperature_adjustments_C=channel_offsets.tolist(),
                     maximum_difference_after_constant_adjustments_C=residual_after_offsets,
                     adjustment_provenance='Constant per-channel shifts inferred by exact raw/processed reconciliation on the calibration record. Their physical calibration procedure is not yet verified.',
                     raw_sensor_map={'hot_positive_cap':3,'can_near_positive':4,'can_middle':5,'can_near_negative':6,'cold_base':7,'fin_cold':10,'fin_hot':11},
                     auxiliary_references={'first_cold_junction':1,'second_cold_junction':15},
                     mapping_basis='Dataset README gives the first 15 columns including time; the raw logger adds a second cold-junction reference at column 16. Cell-temperature mapping is cross-checked against the author-processed calibration array.'),
        electrical=dict(header_fields=electrical_header,first_time_field=first_electrical_time,current_unit='mA',voltage_unit='V',
                        time_representation='Date-time strings under a time/s column heading; do not parse this column as floating-point seconds.',
                        clock_alignment='Unresolved: the thermal clock is elapsed seconds; no thermal absolute start timestamp was verified. Do not fit an offset against held-out temperature.'),
        fixture=dict(boundary='Insulated cylindrical M50T with controlled base cooling, not free convection around a module.',
                     rod_diameter_mm=6.,rod_length_mm=100.,fin_thermocouple_spacing_mm=60.,contact_load_N=4.9,
                     can_thermocouple_axial_positions_mm=[10.,35.,60.],interface_layers_mm=[.5,.5],
                     interface_conductivity_W_m_K=12.,positive_cap_to_cold_base_sensors=[1,5],
                     pulse_frequency_Hz=1.,pulse_set_duration_s=21600.,inter_set_rest_s=5400.,
                     temperature_conditions_C=[10.,20.,30.],current_amplitudes_A=[3.75,5.,6.25,7.5,8.75,10.],
                     reduced_soc_conditions='25 and 75 percent SOC: four amplitudes 3.75, 5, 6.25, 7.5 A at 20 C, from the blue cells in Table 1.',
                     source_locator='Primary paper page 4, Figure 3 and Table 1, visually inspected.'),
        steady_calibration=dict(points=len(delta_temperature),quantity='Fin heat flow versus positive-cap minus cold-base temperature',
                     conductance_W_K=float(conductance),heat_flow_intercept_W=float(heat_offset),
                     heat_flow_fit_rmse_W=float(np.sqrt(np.mean(steady_residual**2))),
                     heat_flow_fit_max_residual_W=float(np.max(abs(steady_residual))),
                     method='Ordinary least squares with an intercept, following the paper Q versus delta-T construction. Author-processed steady heat/temperature points from the allocated calibration record.',
                     source_error_scalars=source_error_scalars,
                     scope='In-sample steady base-cooling relationship only. This does not identify heat capacity, free-convection cooling, dynamic accuracy or electrical heat-generation accuracy.'),
        next_calculation='Reconcile input/output clocks or obtain an author-supplied alignment. Then identify a fixture-specific thermal response from Cell 1; freeze it before assessing Cell 2.',
        physical_model_constraints=['The reported steady cell cooling coefficient is not ambient convection or heat capacity.',
            'Spatial cap/can/base temperatures require an explicit observation map; one temperature cannot represent them all.',
            'The 1 Hz pulse frequency differs from the 1 s thermal logging interval.',
            'A temperature response driven by measured heat is distinct from a fully coupled electrical/thermal forecast.',
            'No source-specific heat capacity or convection parameter has been promoted to the application.'])
    if residual_after_offsets>1e-8:contract['thermal']['mapping_status']='Raw/processed temperature mismatch needs investigation'
    else:contract['thermal']['mapping_status']='Same cell-temperature channels and order, with fixed author-processed temperature corrections; numeric reconciliation verified.'
    (args.out/'m50t_thermal_qualification.json').write_text(json.dumps(contract,indent=2,allow_nan=False)+'\n')
    print(json.dumps(dict(thermal_rows=len(time),thermal_seconds=float(time[-1]),processed_raw_max_difference_C=difference,
                         processed_offset_rows=offset,holdout_observations_decoded=False,clock_alignment='unresolved'),indent=2))


if __name__=='__main__':main()
