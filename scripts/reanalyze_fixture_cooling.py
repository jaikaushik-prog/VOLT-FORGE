"""Revisit one used cooling record with its measured ambient forcing.

This is parameter development, not independent assessment. The whole test was
already exposed. No discharge or reserved observations enter this calculation.
One effective state cannot identify spatial contacts or prove cell temperatures.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

import numpy as np
from scipy.optimize import least_squares

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
from derive_thermal_defaults import read_sheet


def propagate(time, ambient, initial, rate, offset, heat_W=0., capacity=58.5, heat_decay_s=120.):
    """Exact single-state response to linearly varying ambient and decaying heat.

    offset is the unknown constant sensor/fixture equilibrium difference. It is
    fitted, not silently removed. The assumed decaying-heat scenarios are not
    measurements of internal circulation or relaxation heat.
    """
    result = np.empty(len(time)); result[0] = initial
    for i, h in enumerate(np.diff(time)):
        if h == 0:
            result[i+1] = result[i]
            continue
        x = rate*h; decay = np.exp(-x); one = -np.expm1(-x)
        ramp = x/2-x*x/6+x**3/24-x**4/120 if x < 1e-4 else 1-one/x
        heat_rate = 1/heat_decay_s
        difference = rate-heat_rate
        forcing = h*np.exp(-rate*h) if abs(difference*h)<1e-8 else (np.exp(-heat_rate*h)-decay)/difference
        result[i+1] = decay*result[i]+one*(ambient[i]+offset)+(ambient[i+1]-ambient[i])*ramp
        result[i+1] += heat_W*np.exp(-(time[i]-time[0])*heat_rate)*forcing/capacity
    return result


def fit(segments, capacity, heat_W=0.):
    def residual(parameters):
        rate, offset = np.exp(parameters[0]), parameters[1]
        return np.concatenate([propagate(s['time'],s['ambient'],s['mean'][0],rate,offset,
                                          heat_W if s['step']==6 else 0.,capacity)-s['mean'] for s in segments])
    # Broad optimizer bounds are not statements of sensor accuracy or hardware limits.
    solved=least_squares(residual,[np.log(1/466),-.3],bounds=([np.log(1e-5),-3.],[np.log(.1),3.]),
                         xtol=1e-11,ftol=1e-11,gtol=1e-11)
    if not solved.success:raise ValueError('Cooling parameter fit did not converge.')
    rate=float(np.exp(solved.x[0])); offset=float(solved.x[1])
    return dict(rate_per_s=rate,time_constant_s=1/rate,heat_capacity_J_K=capacity,
                ambient_conductance_W_K=capacity*rate,equilibrium_offset_C=offset,
                fit_rmse_C=float(np.sqrt(np.mean(solved.fun**2))),max_abs_residual_C=float(np.max(abs(solved.fun))),
                assumed_initial_decaying_heat_W_per_cell=heat_W,
                jacobian_condition_number=float(np.linalg.cond(solved.jac)),
                optimizer_bounds_meaning='Numerical search limits only; no calibration or confidence interval is inferred.')


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--xlsx',type=Path,required=True);parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args();allocation=json.loads((ROOT/'configs/thermal_fixture_reanalysis_v1.json').read_text())
    if hashlib.sha256(args.xlsx.read_bytes()).hexdigest()!=allocation['source']['sha256']:
        raise SystemExit('The raw file differs from the allocated, previously exposed source.')
    out=args.out.resolve()
    if out.exists() and any(out.iterdir()):raise SystemExit('Choose a new empty result directory.')
    out.mkdir(parents=True,exist_ok=True)
    (out/'access.json').write_text(json.dumps(dict(access_utc=datetime.now(timezone.utc).isoformat(),
        role=allocation['role'],source=allocation['source'],reserved_observations_accessed=False),indent=2)+'\n')
    header,rows=read_sheet(args.xlsx)
    get=lambda name:np.array([r.get(header[name],np.nan) for r in rows],float)
    channels=sorted([k for k in header if k.startswith(allocation['channels']['temperature_prefix'])],
                    key=lambda s:int(s.rsplit('_',1)[1]))
    if len(channels)!=5 or [int(n.rsplit('_',1)[1]) for n in channels]!=[1,2,3,4,5]:
        raise ValueError('Unexpected raw temperature-channel map.')
    time=get(allocation['channels']['time']);step=get(allocation['channels']['step'])
    temperatures=np.array([get(c) for c in channels]);segments=[]
    for chosen in allocation['allowed_steps']:
        keep=np.flatnonzero(step==chosen);t=time[keep]-time[keep[0]]
        if not np.isfinite(temperatures[:,keep]).all() or np.any(np.diff(t)<0):raise ValueError('Invalid allocated temperature/clock values.')
        segments.append(dict(step=chosen,time=t,ambient=temperatures[4,keep],mean=temperatures[:4,keep].mean(axis=0)))
    source=json.loads((ROOT/'configs/thermal_sources_v1.json').read_text())['m50t_heat_capacity']
    capacity=source['reference']['heat_capacity_J_K'];cases=[]
    for selected in ([segments[0]],[segments[1]],segments):
        for heat in (0.,.05,.2) if len(selected)>1 or selected[0]['step']==6 else (0.,):
            result=fit(selected,capacity,heat);result['fit_steps']=[s['step'] for s in selected];cases.append(result)
    # A separate already-exposed segment checks transfer, not independent prediction.
    pre=cases[0];post=segments[1]
    prediction=propagate(post['time'],post['ambient'],post['mean'][0],pre['rate_per_s'],pre['equilibrium_offset_C'])
    error=prediction-post['mean']
    result=dict(version='voltforge.used-fixture-reanalysis/1',classification=allocation['role'],source=allocation['source'],
        source_capacity=source['source'],heat_capacity_J_K=capacity,channels=channels,
        boundary='Observed chamber temperature through the complete selected rests, not a fixed setpoint',
        segment_metadata=[dict(step=s['step'],samples=len(s['time']),duration_s=float(s['time'][-1]),
                              ambient_min_C=float(s['ambient'].min()),ambient_max_C=float(s['ambient'].max())) for s in segments],
        parameter_cases=cases,pre_rest_parameter_transfer=dict(rmse_C=float(np.sqrt(np.mean(error**2))),
            maximum_abs_error_C=float(np.max(abs(error))),scope='Already-exposed step 6; first observed module-mean temperature supplies its initializer.'),
        production_promoted=False,experimental_validation=False,
        limitations=['One previously exposed fixture, one effective mean state; no independent assessment.',
          'A fitted equilibrium offset cannot separate sensor calibration, fixture gradients and constant internal heating.',
          'Assumed residual-heat amplitudes are sensitivity scenarios, not measured heat input.',
          'Mutual cell contacts cancel from an equal-capacity mean; no individual contact or core temperature is identified.',
          'Heat capacity transfers from a different exact-model specimen; source and fixture uncertainty remain.'])
    (out/'identification.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps(result,indent=2,allow_nan=False))


if __name__=='__main__':main()
