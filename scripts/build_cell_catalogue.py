"""Import published M50T surfaces and fit Samsung calibration files only.

Never decodes a validation/assessment member. Raw downloads remain ignored.
The generated candidate is not promoted automatically to the application.
"""
from pathlib import Path
import hashlib
import io
import json
import sys
import zipfile

import numpy as np
from scipy.io import loadmat
from scipy.optimize import lsq_linear, isotonic_regression

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT/'data/raw/model_upgrade_sources'
OUT = ROOT/'reports/model_catalogue_v1'


def sha(data): return hashlib.sha256(data).hexdigest()


def m50t_thermal_reference():
    raw=(ROOT/'configs/thermal_sources_v1.json').read_bytes();sources=json.loads(raw)
    heat=sources['m50t_heat_capacity'];cooling=sources['m50t_fixture_cooling']
    defaults=dict(heat_capacity_J_K=heat['reference']['heat_capacity_J_K'],
                  ambient_conductance_W_K=cooling['ambient_conductance_W_K'],
                  status='Literature heat capacity and a fixture-specific cooling estimate')
    provenance=dict(version='lg_m50t_lumped_reference/1',status='Literature heat capacity; fixture cooling estimate',
        source='Steinhardt et al. 2021, Table A.14, supplies the whole-cell heat capacity. Cooling is a development estimate from the recorded chamber temperature and mean cooling of one Piombo four-cell fixture.',
        source_registry_sha256=sha(raw),
        parameter_sources=dict(heat_capacity_J_K='58.5 J/K at 298 K and approximately 71% charge, DOI 10.1016/j.est.2021.103065, Table A.14. Held constant as a lumped approximation.',
            ambient_conductance_W_K='0.15249 W/K, joint fit to previously exposed Piombo test 53 rest steps 4 and 6 with measured ambient forcing. Transfer to a new arrangement is assumed.'),
        parameter_classification=dict(heat_capacity_J_K='published_reference_parameter',ambient_conductance_W_K='fixture_calibration_estimate'),
        limitations=[heat['implementation'],heat['fixture'],*cooling['limitations']],
        current_fixture_accuracy='Not independently assessed')
    return defaults,provenance


def imported_m50t():
    p = RAW/'pyecn/pyecn/Input_LUTs/Cylindrical_Cell1'
    temps = [15., 25., 35., 45., 55.]
    tables = {k: [] for k in ('ocv_V', 'r0_ohm', 'r_ohm', 'tau_s')}
    z = None
    for temp in temps:
        arrays = {k: np.loadtxt(p/f'{k}-SoC-T{temp:g}.csv', delimiter=',', skiprows=1)[::-1] for k in ('OCV', 'R0', 'Ri', 'Ci')}
        if z is None: z = arrays['OCV'][:, 0]
        if any(not np.array_equal(a[:, 0], z) for a in arrays.values()): raise ValueError('Published table coordinates differ.')
        tables['ocv_V'].append(arrays['OCV'][:, 1].tolist())
        tables['r0_ohm'].append(arrays['R0'][:, 1].tolist())
        tables['r_ohm'].append(arrays['Ri'][:, 1:].tolist())
        tables['tau_s'].append((arrays['Ri'][:, 1:]*arrays['Ci'][:, 1:]).tolist())
    entropy = np.loadtxt(p/'dVdT-SoC.csv', delimiter=',', skiprows=1)[::-1]
    thermal,thermal_provenance=m50t_thermal_reference()
    return dict(kind='temperature_dependent_ecm/1', key='LG_M50T_ECN', name='LG M50T', family='LG M50T',
                capacity_Ah=5., nominal_capacity_Ah=5., nrc=3, soc=z.tolist(), temperature_C=temps, **tables,
                entropy=dict(soc=entropy[:, 0].tolist(), dOCV_dT_V_K=entropy[:, 1].tolist(), status='Published PyECN lookup; independently unvalidated here'),
                geometry=dict(form='cylindrical', diameter_mm=21.44, height_mm=70.8, mass_kg=.070, status='Manufacturer maximum dimensions and mass, draft Rev 0'),
                operating_limits=dict(voltage_V=[2.5, 4.2], max_discharge_A=7.275, max_charge_A=3.395,
                    source_url='https://mytyva.com/wp-content/uploads/2023/05/M50T-LG-CHEM-.pdf', source_revision='2018-07-16 Rev 0 draft; temperature-dependent current limits in sections 4.2.3 and 4.2.4'),
                thermal_defaults=thermal,thermal_provenance=thermal_provenance,
                source=dict(url='https://github.com/ImperialCollegeLondon/PyECN', commit='32540fe0819bfc4d099bcd601d1ab0625cb524a3',
                    path='pyecn/Input_LUTs/Cylindrical_Cell1', licence='BSD-3-Clause', paper='https://doi.org/10.31224/2972',
                    interpretation='Unscaled whole-cell resistance/capacitance tables. No 4680 electrode-area or module scaling. Capacity_rated0=18000 coulombs is 5 Ah.'),
                evidence_status='Published temperature-dependent model; independent experimental assessment pending',
                limitations=['Same-cell-type parameter import does not establish batch-specific accuracy.', 'A constant published heat capacity and used-fixture cooling estimate do not establish a new assembly temperature forecast.', 'No ageing model or core-temperature validation.'])


def read_calibration(z, name, plan):
    if name not in plan['calibration']: raise ValueError('Attempt to decode an unallocated source experiment.')
    d = loadmat(io.BytesIO(z.read(name)), simplify_cells=True)['meas']
    a = {k: np.asarray(d[k], float) for k in ('Time', 'Voltage', 'Current', 'Ah', 'Battery_Temp_degC')}
    n = len(a['Time'])
    if any(v.shape != (n,) or not np.isfinite(v).all() for v in a.values()): raise ValueError('Invalid calibration channel.')
    if np.any(np.diff(a['Time']) < 0): raise ValueError('Nonmonotonic calibration clock.')
    # Equal-time measurements are retained as zero-duration electrical events.
    a['Current'] *= -1
    return a


def rc_basis(time, current, tau):
    values = np.zeros((len(time), len(tau)))
    for i, h in enumerate(np.diff(time)):
        e = np.exp(-h/tau)
        values[i+1] = values[i]*e + current[i]*(1-e)
    return values


def samsung():
    plan = json.loads((ROOT/'configs/model_catalogue_upgrade_v1.plan.json').read_text())
    archive = RAW/'samsung30t-v2.zip'
    if sha(archive.read_bytes()) != plan['archive_sha256']: raise ValueError('Source archive changed.')
    nominal = [-20, -10, 0, 10, 25, 40]
    soc = np.r_[np.arange(.15, 1., .05), 1.]
    taus = np.array([2., 30., 300.])
    tables = {k: [] for k in ('ocv_V', 'r0_ohm', 'r_ohm', 'tau_s')}
    temperatures = []; diagnostics = []
    with zipfile.ZipFile(archive) as z:
        n25 = next(n for n in plan['calibration'] if 'C20DisCh_25degC' in n)
        c25 = read_calibration(z, n25, plan)
        end25 = np.flatnonzero(c25['Current'] < -.05)[0]
        capacity = float(-c25['Ah'][:end25].min())
        for temp in nominal:
            c_name = next(n for n in plan['calibration'] if f'C20DisCh_{temp}degC' in n)
            h_name = next(n for n in plan['calibration'] if f'HPPC_{temp}degC' in n)
            c = read_calibration(z, c_name, plan); h = read_calibration(z, h_name, plan)
            end = np.flatnonzero(c['Current'] < -.05)[0]
            keep = c['Current'][:end] > .05
            cz = 1+c['Ah'][:end][keep]/capacity; cv = c['Voltage'][:end][keep]
            order = np.argsort(cz); cz, cv = cz[order], cv[order]
            flags = h['Current'] < -1.5
            edges = np.flatnonzero(np.diff(np.r_[False, flags, False]))
            bulk = next((a for a, b in zip(edges[::2], edges[1::2]) if h['Time'][b-1]-h['Time'][a] > 60), len(flags))
            time, current, voltage, temperature, counter = (h[k][:bulk] for k in ('Time', 'Current', 'Voltage', 'Battery_Temp_degC', 'Ah'))
            # Each pulse is followed by a charge-return procedure. The source
            # capacity counter changes convention during those procedures, so
            # it is not used as a global SOC trajectory for the HPPC record.
            # Infer the initial pulse state from the pre-pulse rest voltage and
            # the separate C/20 curve; count charge only within that short pulse.
            conditioned = np.abs(temperature-temp) <= 5
            rest = conditioned & (abs(current) < .05)
            temperature_coordinate = float(np.median(temperature[rest]))
            temperatures.append(temperature_coordinate)
            pulse_flags = current > .1
            pulse_edges = np.flatnonzero(np.diff(np.r_[False, pulse_flags, False]))
            pulses = []
            for start, finish in zip(pulse_edges[::2], pulse_edges[1::2]):
                width = time[finish-1]-time[start]
                if not 2 <= width <= 4000 or not conditioned[start:finish].all():
                    continue
                pre = np.flatnonzero((time[:start] >= time[start]-10) & (abs(current[:start]) < .05))
                if len(pre) < 3: continue
                later = np.flatnonzero(abs(current[finish:]) > .05)
                endpulse = finish+int(later[0]) if len(later) else len(time)
                endpulse = min(endpulse, int(np.searchsorted(time, time[finish-1]+600)))
                if endpulse <= finish+2: continue
                left = int(pre[0]); indexes = np.arange(left, endpulse)
                reference_voltage = float(np.median(voltage[pre[-min(len(pre),20):]]))
                # Known fully charged initial preparation supplies the missing
                # zero-current endpoint of the C/20 loaded curve.
                base_z = np.r_[cz, 1.]; base_v = np.r_[cv, float(np.median(voltage[:max(start,1)]))]
                order2 = np.argsort(base_z); base_z, base_v = base_z[order2], base_v[order2]
                base_v = isotonic_regression(base_v).x
                initial_state = float(np.interp(reference_voltage, base_v, base_z))
                local_time, local_i = time[indexes], current[indexes]
                charge = np.r_[0., np.cumsum(local_i[:-1]*np.diff(local_time))]/3600
                local_soc = initial_state-charge/capacity
                baseline = reference_voltage + np.interp(local_soc, base_z, base_v)-np.interp(initial_state, base_z, base_v)
                x = np.c_[local_i, rc_basis(local_time, local_i, taus), np.ones(len(indexes))]
                y = baseline-voltage[indexes]
                fit = lsq_linear(x,y,bounds=([.0001,.000001,.000001,.000001,-.03],[.3,.3,.3,.3,.03]),method='bvls')
                if not fit.success: raise ValueError('Pulse calibration failed.')
                err = y-x@fit.x
                pulses.append(dict(soc=float(initial_state-charge[-1]/(2*capacity)), temperature_C=float(np.median(temperature[pre])),
                                   current_A=float(np.median(current[start:finish])), width_s=float(width),
                                   samples=len(indexes), parameters=fit.x[:4].tolist(),
                                   voltage_rmse_V=float(np.sqrt(np.mean(err**2))),bias_V=float(fit.x[4]),
                                   source_start_row=int(start+1),source_end_row=int(endpulse),
                                   observed_temperature_range_C=[float(temperature[indexes].min()),float(temperature[indexes].max())]))
            if len(pulses) < 12: raise ValueError('Insufficient independent pulse windows.')
            points = np.array([r['soc'] for r in pulses]); parameters = np.array([r['parameters'] for r in pulses])
            amplitudes = np.array([r['current_A'] for r in pulses])
            widths = np.array([r['width_s'] for r in pulses])
            fitted = []
            for state in soc:
                weights = np.exp(-.5*((points-state)/.055)**2)*np.where(amplitudes<=6.1,1.,.25)
                if weights.sum() < 1e-8: raise ValueError('Missing pulse support for a SOC knot.')
                row=np.average(parameters,axis=0,weights=weights)
                slow_weights=weights*np.clip(widths/30,.1,20)
                row[1:]=np.average(parameters[:,1:],axis=0,weights=slow_weights)
                fitted.append(row)
            fitted = np.asarray(fitted)
            low_current = float(np.median(c['Current'][:end][keep]))
            ocv = np.interp(soc,cz,cv)+low_current*fitted.sum(axis=1)
            # The known fully charged, rested preparation supplies the top knot.
            first_rest = np.flatnonzero((abs(current)<.05)&(time<time[pulse_edges[0]]))
            if len(first_rest): ocv[-1] = float(np.median(voltage[first_rest]))
            monotonic = isotonic_regression(ocv).x
            tables['ocv_V'].append(monotonic.tolist()); tables['r0_ohm'].append(fitted[:,0].tolist())
            tables['r_ohm'].append(fitted[:,1:].tolist()); tables['tau_s'].append(np.tile(taus,(len(soc),1)).tolist())
            diagnostics.append(dict(nominal_chamber_C=temp,model_temperature_C=temperature_coordinate,source_hppc=h_name,
                                    source_c20=c_name,pulse_windows=pulses,
                                    pulse_soc_range=[float(points.min()),float(points.max())],
                                    capacity_counter_policy='HPPC charge-return counters are not assumed to be a conserved SOC coordinate.',
                                    duplicate_time_events=int(np.sum(np.diff(time)==0)),
                                    maximum_ocv_monotonic_adjustment_V=float(np.max(abs(monotonic-ocv)))))
    common_low=max(r['pulse_soc_range'][0] for r in diagnostics if r['nominal_chamber_C']>=0)
    lower=max(float(soc[0]),np.ceil(common_low*100)/100)
    retained=np.r_[lower,soc[soc>lower]]
    for key in tables:
        if key in ('ocv_V','r0_ohm'):
            tables[key]=[np.interp(retained,soc,row).tolist() for row in tables[key]]
        else:
            tables[key]=[np.column_stack([np.interp(retained,soc,np.asarray(row)[:,k]) for k in range(3)]).tolist() for row in tables[key]]
    soc=retained
    observed_low=min(v['observed_temperature_range_C'][0] for r in diagnostics for v in r['pulse_windows'])
    observed_high=max(v['observed_temperature_range_C'][1] for r in diagnostics for v in r['pulse_windows'])
    original_temperature_coordinates=temperatures.copy()
    for edge,at_start in [(observed_low,True),(observed_high,False)]:
        if (at_start and edge>=temperatures[0]) or (not at_start and edge<=temperatures[-1]):continue
        a,b=(0,1) if at_start else (-2,-1)
        weight=(edge-temperatures[a])/(temperatures[b]-temperatures[a])
        for key,values in tables.items():
            first=np.asarray(values[a]);second=np.asarray(values[b])
            value=first+weight*(second-first) if key=='ocv_V' else np.exp(np.log(first)+weight*(np.log(second)-np.log(first)))
            if at_start:values.insert(0,value.tolist())
            else:values.append(value.tolist())
        if at_start:temperatures.insert(0,float(edge))
        else:temperatures.append(float(edge))
    warm_observations=[v for d in diagnostics if d['nominal_chamber_C']>=0 for v in d['pulse_windows']]
    deployment_low=min(v['observed_temperature_range_C'][0] for v in warm_observations)
    model = dict(kind='temperature_dependent_ecm/1', key='SAMSUNG_30T', name='Samsung 30T', family='Samsung 30T',
                 deployment_domain=dict(temperature_C=[float(deployment_low),float(observed_high)],soc=[float(soc[0]),1.]),
                 nominal_capacity_Ah=3., capacity_Ah=capacity, nrc=3, soc=soc.tolist(), temperature_C=temperatures, **tables, entropy=None,
                 geometry=dict(form='cylindrical', diameter_mm=21.22, height_mm=70.3, mass_kg=.069, status='Manufacturer maximum dimensions and mass'),
                 operating_limits=dict(voltage_V=[2.5, 4.2], max_discharge_A=6., max_charge_A=4.,
                     manufacturer_max_discharge_A_at_25C=35., source_url='https://www.tme.eu/Document/d6147ab6f2b82f7e0b98d79910473d06/samsung-INR21700-30t-datasheet.pdf',
                     status='6 A prototype modelling limit; 35 A manufacturer rating applies at 25 C and is not a blanket model-accuracy claim'),
                 thermal_defaults=dict(heat_capacity_J_K=69., ambient_conductance_W_K=.148629,
                     status='Assumed 1000 J/kg/K specific heat and declared fixture conductance; not independently identified'),
                 source=dict(url='https://data.mendeley.com/datasets/9xyvy2njj3/2', doi='10.17632/9xyvy2njj3.2', licence='CC BY 4.0',
                     archive_sha256=plan['archive_sha256'], contributors=['Phillip Kollmeyer', 'Michael Skells'],
                     calibration_files=plan['calibration'], representative_temperature_coordinates_C=original_temperature_coordinates,
                     boundary_policy='Regression trends extend from condition means to the measured calibration-temperature extrema; no extension beyond those observations. These fitted boundary parameters are estimates, not extra measurements.', current_convention='Original positive charge converted to positive discharge',
                     procedure='IR-corrected C/20 reference; isolated discharge-pulse and sustained conditioning/rest 3-RC regressions with fixed 2/30/300 s time constants and positive resistances. Pulse SOC is inferred from pre-pulse rest against C/20 reference. Measured cell-temperature coordinates.'),
                 evidence_status='Calibration model; independent whole-test assessment pending',
                 limitations=['C/20 voltage is not measured equilibrium OCV.', 'Capacity is referenced to the C/20 discharge counter. Pulse starting SOC is inferred and inherits pseudo-OCV uncertainty; HPPC charge-return counters are not integrated as one global SOC trajectory.',
                              'Fixed time constants and SOC-local regression are approximations.', 'Temperature sensor accuracy is stated as +/-1 C; voltage/current accuracy is 0.1 percent of channel full scale.',
                              'Reversible heat is omitted because no independently sourced entropy coefficient is supplied.', 'Below the near-zero-temperature calibration condition, this model failed the development voltage budget; colder operation is not enabled.', 'No ageing, batch variability or module/thermal validation.'])
    return model, diagnostics


def main():
    sys.path.insert(0, str(ROOT/'src'))
    from voltforge.models.cell_catalogue import CellModel
    a = imported_m50t(); b, fit = samsung()
    for model in (a, b): CellModel(model)
    output = dict(version='voltforge.cell-catalogue/1', models={a['key']: a, b['key']: b})
    OUT.mkdir(exist_ok=True, parents=True)
    (OUT/'candidate_catalogue.json').write_text(json.dumps(output, indent=2, allow_nan=False)+'\n')
    (OUT/'samsung_calibration.json').write_text(json.dumps(fit, indent=2, allow_nan=False)+'\n')
    print(json.dumps({m['key']: dict(temperature_C=[m['temperature_C'][0], m['temperature_C'][-1]], capacity_Ah=m['capacity_Ah']) for m in (a, b)}))


if __name__ == '__main__': main()
