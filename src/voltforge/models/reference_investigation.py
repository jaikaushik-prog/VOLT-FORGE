"""Bounded diagnostics on used records; frozen v2 remains the production baseline."""
import argparse
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.interpolate import PchipInterpolator
from . import improvement as m

PLAN = Path('configs/reference_initial_state_v1.json')
LOCK = Path('configs/reference_initial_state_v1.lock.json')
OUT = Path('reports/reference_initial_state_v1')
DOC = Path('REFERENCE_INITIAL_STATE_PLAN.md')


def reserve():
    if LOCK.exists():
        verify(); return
    m.check_procedure()
    v2 = m.read_json(m.PLAN); plan = m.read_json(PLAN)
    unused = set(m.read_json(m.LOCK)['previously_uninspected_nmc_cells']) - set(v2['fresh_cells'])
    if set(plan['reserved_unused_cells']) != unused or not set(plan['cells']) <= set(v2['development_cells']):
        raise ValueError('Investigation allocation changed or touches unused evidence')
    paths = set(m.read_json(m.LOCK)['protected'])
    for p in m.OUT.rglob('*'):
        if p.is_file() and not (p.suffix == '.csv' and ('predictions' in p.name or 'software_coupling' in p.parts)):
            paths.add(p.as_posix())
    paths.update(['MODEL_IMPROVEMENT_DECISION.md', 'MODEL_IMPROVEMENT_PLAN.md', str(m.PLAN), str(m.LOCK),
                  'src/voltforge/models/improvement.py', 'src/voltforge/models/coupling.py', 'tests/test_improvement.py'])
    paths = {Path(p).as_posix() for p in paths}
    m.save(LOCK, dict(created_utc=m.now(), plan_sha256=m.v1.digest(PLAN), document_sha256=m.v1.digest(DOC),
        implementation_sha256=m.v1.digest(__file__), protected={p:m.v1.digest(p) for p in sorted(paths)},
        reserved_unused_cells=sorted(unused), fresh_voltage_accessed=False,
        note='Regenerable v2 per-sample prediction/coupling CSVs are not hash-bound here; no command writes them.'))
    print('Bounded procedure and durable v2 baseline frozen before diagnostics.', flush=True)


def verify():
    m.check_procedure(); lock = m.read_json(LOCK)
    for p, h in lock['protected'].items():
        if m.v1.digest(p) != h: raise ValueError('Frozen baseline changed: '+p)
    for p, key in [(PLAN,'plan_sha256'), (DOC,'document_sha256'), (__file__,'implementation_sha256')]:
        if m.v1.digest(p) != lock[key]: raise ValueError('Bounded investigation changed: '+str(p))
    return lock


def load_used(cell, cycles, plan):
    if cell not in plan['cells'] or cell in plan['reserved_unused_cells']:
        raise ValueError('Cell outside used-evidence allocation')
    if list(cycles) not in [plan['calibration_cycles'], plan['development_cycles']]:
        raise ValueError('Load complete declared allocation only')
    return m.load_cell(cell, cycles)


def reference_function(model, low, kind, coordinate_shift=0.):
    a = model['reference']['rest']; x = np.array([r['soc'] for r in a]); y = np.array([r['V'] for r in a])
    if kind == 'sealed_rest_pchip':
        return PchipInterpolator(x+coordinate_shift, y, extrapolate=False)
    if kind != 'loaded_shape_same_rest_anchors': raise ValueError('Undeclared reference')
    _, lx, ly = m.v1.loaded_curve(low)
    correction = y-np.interp(x, lx, ly)
    def evaluate(z):
        z = np.asarray(z)-coordinate_shift
        v = np.interp(z, lx, ly)+np.interp(z, x, correction)
        return np.where((z>=max(x[0],lx[0]))&(z<=min(x[-1],lx[-1])), v, np.nan)
    return evaluate


def alignment_profile(soc, target_V, weights, ref, deltas, bound_V, support_factor=1.05):
    """target = measured voltage + frozen dynamic drop; no development data."""
    z, target, w = map(np.asarray, (soc, target_V, weights))
    if np.any(w<0) or w.sum()<=0: raise ValueError('Invalid objective weights')
    w = w/w.sum(); rows = []
    for delta in deltas:
        error = np.asarray(ref(z+delta))-target
        if not np.isfinite(error).all(): raise ValueError('Profile must use common supported rows')
        offset = float(np.clip(-w@error, -bound_V, bound_V))
        rows.append(dict(delta_soc=float(delta), offset_V=offset,
            mse_no_offset_V2=float(w@(error**2)), mse_joint_V2=float(w@((error+offset)**2))))
    table = pd.DataFrame(rows); results = {}
    for name,col in [('delta_only','mse_no_offset_V2'),('delta_and_offset','mse_joint_V2')]:
        k = int(table[col].idxmin()); row = table.iloc[k]; best = float(row[col])
        support = table[table[col] <= best*support_factor+1e-20]
        offset = float(row.offset_V) if name == 'delta_and_offset' else 0.
        results[name] = dict(delta_soc=float(row.delta_soc), offset_V=offset, objective_rmse_mV=float(np.sqrt(best)*1000),
            delta_support=[float(support.delta_soc.min()),float(support.delta_soc.max())],
            delta_on_boundary=k in [0,len(table)-1], offset_on_boundary=abs(offset)>=bound_V*(1-1e-9),
            note='Descriptive profile of calibration alignment; not physical SOC or a confidence interval.')
    # Cosine between the local SOC and constant-voltage sensitivity columns.
    delta = results['delta_and_offset']['delta_soc']; eps = 1e-6
    slope = (ref(z+delta+eps)-ref(z+delta-eps))/(2*eps)
    cosine = float((w@slope)/np.sqrt(w@(slope*slope)))
    results['sensitivity_column_cosine'] = cosine
    return table, results


def weights_for_profiles(pred, v2plan):
    w = np.zeros(len(pred))
    for _, g in pred.groupby('cycle', sort=False):
        w[g.index] = m.fit_weights(g, 'C2_rest_reference_RC')
    return w * m.primary_mask(pred,v2plan).to_numpy()


def diagnostic_prediction(base, ref, delta=0., offset=0.):
    f = base.copy()
    drop = base.reference_V-base.predicted_V
    f['reference_V'] = ref(base.soc.to_numpy()+delta)+offset
    f['predicted_V'] = f.reference_V-drop
    f['error_V'] = f.predicted_V-f.V_V
    f['supported_reference'] = np.isfinite(f.predicted_V)
    # SOC column stays nominal: all reported primary-domain masks are fixed.
    return f


def rest_evidence(frame, model, low, role):
    records = []; refs = {kind:reference_function(model,low,kind) for kind in m.read_json(PLAN)['references']}
    for c, g in frame[np.isfinite(frame.V_V)&(frame.step==11)].groupby('cycle'):
        end = g.time_s.iloc[-1]; last = g[g.time_s>=end-30]
        late = g[g.time_s>=end-300]; prior = g[(g.time_s>=end-600)&(g.time_s<end-300)]
        tail = g[g.time_s>=end-600]
        slope = np.polyfit(tail.time_s-tail.time_s.iloc[0],tail.V_V,1)[0]*60000
        z = float(last.soc.median()); voltage = float(last.V_V.median())
        r = dict(role=role,cycle=int(c),first_row=int(g.row.iloc[0]),last_row=int(g.row.iloc[-1]),
            rest_span_s=float(end-g.time_s.iloc[0]),soc=z,rest_V=voltage,
            surface_min_C=float(tail.surface_C.min()),surface_max_C=float(tail.surface_C.max()),
            last600_slope_mV_per_min=float(slope),last300_minus_previous300_mV=float((late.V_V.median()-prior.V_V.median())*1000),
            last30_minus_last300_mV=float((voltage-late.V_V.median())*1000))
        for kind,ref in refs.items():
            value = float(ref([z])[0]);r[kind+'_error_mV'] = (value-voltage)*1000 if np.isfinite(value) else None
        records.append(r)
    return records


def plot_cell(cell, frames, tables, rests):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes = plt.subplots(2,2,figsize=(13,8),layout='constrained')
    colors = ['#0072B2','#D55E00']; baseline=frames['frozen_v2']; c=baseline[baseline.cycle==8]
    start=c.time_s.iloc[0]; t=(c.time_s-start)/60
    axes[0,0].plot(t,c.V_V,color='black',label='Measured',lw=1)
    names=['frozen_v2']+[k for k in frames if k.endswith('/delta_and_offset')]
    for name,color in zip(names,['#777777']+colors):
        g=frames[name];g=g[g.cycle==8];label=name.replace('sealed_rest_pchip','rest').replace('loaded_shape_same_rest_anchors','C/20 shape')
        axes[0,0].plot((g.time_s-start)/60,g.predicted_V,label=label,color=color,lw=.8)
        axes[1,0].plot((g.time_s-start)/60,g.error_V*1000,color=color,lw=.8)
    axes[0,0].set(title=f'Used cycle 8, source rows {int(c.row.iloc[0])}-{int(c.row.iloc[-1])}',ylabel='Voltage [V]')
    axes[0,0].legend(fontsize=7); axes[1,0].set(ylabel='Predicted - measured [mV]',xlabel='Cycle time [min]')
    axes[1,0].axhline(0,color='black',lw=.5)
    for (kind,table),color in zip(tables.items(),colors):
        label='Rest PCHIP' if kind=='sealed_rest_pchip' else 'C/20 shape + same anchors'
        axes[0,1].plot(table.delta_soc*100,np.sqrt(table.mse_joint_V2)*1000,color=color,label=label+'; offset allowed')
        axes[0,1].plot(table.delta_soc*100,np.sqrt(table.mse_no_offset_V2)*1000,color=color,ls='--',alpha=.6)
        r=pd.DataFrame(rests);r=r[r.role=='used_development']
        axes[1,1].plot(r.soc,r[kind+'_error_mV'],'o-',color=color,label=label)
    axes[0,1].set(xlabel='SOC alignment delta [percentage points]',ylabel='Calibration objective RMS [mV]',title='Dashed: no voltage offset; fixed RC')
    axes[0,1].legend(fontsize=7)
    axes[1,1].set(xlabel='Nominal SOC proxy',ylabel='Reference - late-rest voltage [mV]',title='Already-opened development rests; no refit')
    axes[1,1].axhline(0,color='black',lw=.5)
    for ax in axes.flat: ax.grid(alpha=.2)
    fig.suptitle(f'{cell} HPPC_MultiSine_{cell}.mat | diagnostics only; v2 unchanged')
    fig.savefig(OUT/f'{cell}_diagnostics.png',dpi=140);plt.close(fig)


def run():
    verify();plan=m.read_json(PLAN);v2plan=m.read_json(m.PLAN);all_results={};all_rests=[];summary=[]
    OUT.mkdir(parents=True,exist_ok=True)
    deltas=np.linspace(*plan['soc_delta_bounds'],plan['soc_delta_grid_points'])
    for cell in plan['cells']:
        low,cal,_=load_used(cell,plan['calibration_cycles'],plan)
        model=m.read_json(m.OUT/'development'/f'{cell}_models.json')[plan['model']]
        pred=m.predictions(cal,model,plan['calibration_cycles']); w=weights_for_profiles(pred,v2plan)
        refs={kind:reference_function(model,low,kind) for kind in plan['references']}
        common=np.isfinite(pred.predicted_V)&(w>0)
        for ref in refs.values():
            for d in deltas: common &= np.isfinite(ref(pred.soc.to_numpy()+d))
        z=pred.soc.to_numpy()[common];drop=(pred.reference_V-pred.predicted_V).to_numpy()
        target=(pred.V_V.to_numpy()+drop)[common]
        tables={};profile_results={}
        for kind,ref in refs.items():
            tables[kind],profile_results[kind]=alignment_profile(z,target,w[common],ref,deltas,
                plan['voltage_offset_bound_V'],plan['profile_relative_support'])
            tables[kind].to_csv(OUT/f'{cell}_{kind}_profile.csv',index=False)
        # Save the calibration quantities before development voltage is loaded.
        m.save(OUT/f'{cell}_calibration_profiles.json',dict(profiles=profile_results,
            calibration_source_rows=pred.loc[common,'row'].astype(int).tolist(),
            excluded_from_primary_profile_n=int(((w>0)&~common).sum()),development_voltage_used=False))
        _,dev,_=load_used(cell,plan['development_cycles'],plan)
        base=m.predictions(dev,model,plan['development_cycles']);frames={'frozen_v2':base}
        for kind,ref in refs.items():
            if kind!='sealed_rest_pchip': frames[kind+'/unaligned']=diagnostic_prediction(base,ref)
            for mode in ['delta_only','delta_and_offset']:
                p=profile_results[kind][mode]
                frames[kind+'/'+mode]=diagnostic_prediction(base,ref,p['delta_soc'],p['offset_V'])
        scores={name:m.score(f,v2plan) for name,f in frames.items()}
        for name,score in scores.items(): summary.append(dict(cell=cell,diagnostic=name,**score['primary'],full_max_abs_mV=score['full']['max_abs_mV']))
        rests=rest_evidence(cal,model,low,'calibration')+rest_evidence(dev,model,low,'used_development')
        for r in rests:r['cell']=cell
        all_rests.extend(rests)
        gauge={}
        for d in [-.02,.02]:
            shifted=reference_function(model,low,'sealed_rest_pchip',coordinate_shift=d)
            gauge[str(d)]=float(np.max(abs(shifted(base.soc.to_numpy()+d)-refs['sealed_rest_pchip'](base.soc.to_numpy())))*1000)
        zgrid=np.linspace(.2,.8,601);slope=refs['sealed_rest_pchip'].derivative()(zgrid)
        resolution={str(b):float(b/1000/np.max(abs(slope))*100) for b in [5,10,25]}
        all_results[cell]=dict(profiles=profile_results,development_scores=scores,gauge_max_prediction_change_mV=gauge,
            maximum_reference_slope_V_per_SOC=float(np.max(abs(slope))),
            illustrative_SOC_percentage_points_for_voltage_allowance_mV=resolution,
            note='Resolution is local first-order sensitivity, not a measurement specification or validated error bound.')
        plot_cell(cell,frames,tables,rests)
        print(cell,'bounded diagnostics complete; no model replacement',flush=True)
    pd.DataFrame(all_rests).to_csv(OUT/'rest_evidence.csv',index=False)
    pd.DataFrame(summary).to_csv(OUT/'comparison.csv',index=False)
    m.save(OUT/'results.json',dict(created_utc=m.now(),cells=all_results,new_assessment_cells_opened=[],
        preserved_unused_cells=plan['reserved_unused_cells'],selected_production_model='unchanged: frozen v2 C2'))
    verify();print('Baseline preservation verified after investigation.',flush=True)


def main():
    p=argparse.ArgumentParser(__doc__);p.add_argument('command',choices=['reserve','run','verify']);args=p.parse_args()
    {'reserve':reserve,'run':run,'verify':verify}[args.command]()


if __name__=='__main__':main()
