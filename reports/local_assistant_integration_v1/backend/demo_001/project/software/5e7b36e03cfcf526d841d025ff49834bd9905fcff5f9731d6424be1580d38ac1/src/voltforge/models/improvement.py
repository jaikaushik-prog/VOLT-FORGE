"""V2 cell-model development with blind additional-cell assessment.

The three revisions and assessment policy are declared in configs/. V1 is
imported read-only. All fitted quantities are conditional on this single rig.
"""
import argparse
from datetime import datetime, timezone
from io import BytesIO
import json
from pathlib import Path
from zipfile import ZipFile
import numpy as np
import pandas as pd
from scipy.integrate import cumulative_trapezoid
from scipy.interpolate import PchipInterpolator
from scipy.io import loadmat, whosmat
from scipy.optimize import lsq_linear
from . import identification as v1

PLAN=Path('configs/model_improvement_v2.json')
LOCK=Path('configs/model_improvement_v2.lock.json')
OUT=Path('reports/improvement_v2')
METHODS=['baseline','C1_rest_reference_R','C2_rest_reference_RC','C3_rest_reference_SOC_RC']


def now(): return datetime.now(timezone.utc).isoformat()
def read_json(p): return json.loads(Path(p).read_text(encoding='utf-8'))
def save(p,obj): v1.save(Path(p),obj)


def member(z,base):
    names=[n for n in z.namelist() if n.endswith('/'+base)]
    if len(names)!=1: raise ValueError('Missing/ambiguous '+base)
    return names[0]


def reserve():
    if LOCK.exists():
        verify();print('V2 reservation verified; unchanged.',flush=True);return
    plan=read_json(PLAN);v1.verify_inputs()
    protected=[p for p in Path('reports/identification_v1').rglob('*') if p.is_file()]
    protected += [Path('configs/cell_identification_v1.json'),Path('configs/cell_identification_v1.lock.json'),
        Path('configs/splits.json'),Path('configs/splits.lock.json'),Path('src/voltforge/models/identification.py')]
    protected += list(Path('reports').glob('*.json'))
    inventory=read_json('reports/file_inventory.json')
    nmc=sorted({Path(x['basename']).stem.replace('HPPC_MultiSine_','') for x in inventory
        if '/NMC_cells/HPPC_MS/' in x['member']},key=lambda s:int(s[1:]))
    fresh=[c for c in nmc if c not in plan['development_cells']]
    if not set(plan['fresh_cells']).issubset(fresh): raise ValueError('Fresh-cell allocation invalid')
    data=dict(created_utc=now(),plan_sha256=v1.digest(PLAN),plan_document_sha256=v1.digest('MODEL_IMPROVEMENT_PLAN.md'),
        archive_sha256=v1.digest(v1.source_archive()),protected={str(p).replace('\\','/'):v1.digest(p) for p in protected},
        previously_uninspected_nmc_cells=fresh,cells={})
    with ZipFile(v1.source_archive()) as z:
        for cell in plan['development_cells']+plan['fresh_cells']:
            hp=member(z,'HPPC_MultiSine_'+cell+'.mat');lp=member(z,'OCVDis_'+cell+'.mat')
            # Metadata/current only: no voltage or temperature variable requested.
            d=loadmat(BytesIO(z.read(hp)),simplify_cells=True,
                variable_names=['TimeData','CurrentData','CycleIndex','StepIndex'])
            cycles={}
            for c in np.unique(d['CycleIndex']).astype(int):
                ids=np.flatnonzero(d['CycleIndex']==c);steps=sorted(set(d['StepIndex'][ids].astype(int)))
                if not {10,11,12,13,14,15,22}.issubset(steps): raise ValueError('Incomplete source cycle')
                cycles[str(c)]=dict(first_row=int(ids[0]+1),last_row=int(ids[-1]+1),steps=[int(s) for s in steps])
            records={x:next(r for r in inventory if r['member']==n)['sha256'] for x,n in [('hppc',hp),('low_rate',lp)]}
            data['cells'][cell]=dict(hppc_member=hp,low_rate_member=lp,sha256=records,cycles=cycles)
    save(LOCK,data);print('V2 whole-cycle reservation and v1 preservation hashes saved before fitting.',flush=True)


def verify():
    lock=read_json(LOCK)
    if lock['plan_sha256']!=v1.digest(PLAN) or lock['plan_document_sha256']!=v1.digest('MODEL_IMPROVEMENT_PLAN.md'):
        raise ValueError('Frozen v2 plan changed')
    for p,h in lock['protected'].items():
        if v1.digest(p)!=h: raise ValueError('Preserved v1 artifact changed: '+p)
    if v1.digest(v1.source_archive())!=lock['archive_sha256']: raise ValueError('Source archive changed')
    return lock


def load_cell(cell,allowed_voltage_cycles):
    """Held voltage is erased before any reference, fit, summary or plot access.

    MATLAB compressed vectors must be decoded whole; disallowed entries are
    immediately replaced by NaN, never inspected or used in calibration.
    """
    lock=read_json(LOCK)['cells'][cell]
    with ZipFile(v1.source_archive()) as z:
        low,lp=v1.read_cell(z,cell,'low_rate')
        blob=z.read(lock['hppc_member'])
        import hashlib
        if hashlib.sha256(blob).hexdigest()!=lock['sha256']['hppc'] or lp['sha256']!=lock['sha256']['low_rate']:
            raise ValueError('Cell source hash changed')
        d=loadmat(BytesIO(blob),simplify_cells=True)
    allowed=np.isin(d['CycleIndex'],allowed_voltage_cycles)
    voltage=np.where(allowed,d['VoltageData'],np.nan)
    temp=np.where(allowed,d['TempData'],np.nan)
    q,x,y=v1.loaded_curve(low)
    f=pd.DataFrame(dict(row=np.arange(1,len(d['TimeData'])+1),time_s=d['TimeData'],I_A=-d['CurrentData'],
        V_V=voltage,surface_C=temp,cycle=d['CycleIndex'].astype(int),step=d['StepIndex'].astype(int)))
    if not np.all(np.diff(f.time_s)>0): raise ValueError('Nonmonotone source clock')
    f['soc']=1-cumulative_trapezoid(f.I_A,f.time_s,initial=0)/(3600*q)
    f['loaded_V']=np.interp(f.soc,x,y)
    return low,f,q


def references(f,calibration):
    anchors=[]
    for c in calibration:
        r=f[(f.cycle==c)&(f.step==11)]
        r=r[r.time_s>=r.time_s.iloc[-1]-30]
        if not np.isfinite(r.V_V).all(): raise ValueError('Unpermitted calibration voltage')
        anchors.append(dict(cycle=c,soc=float(r.soc.median()),V=float(r.V_V.median()),
            correction_V=float((r.V_V-r.loaded_V).median()),first_row=int(r.row.iloc[0]),last_row=int(r.row.iloc[-1])))
    r=f[(f.cycle==1)&(f.step==9)];r=r[r.time_s>=r.time_s.iloc[-1]-30]
    anchors.append(dict(cycle=1,soc=float(r.soc.median()),V=float(r.V_V.median()),
        correction_V=float((r.V_V-r.loaded_V).median()),first_row=int(r.row.iloc[0]),last_row=int(r.row.iloc[-1])))
    anchors.sort(key=lambda a:a['soc'])
    if np.any(np.diff([a['V'] for a in anchors])<=0): raise ValueError('Rest reference is not monotone')
    # Baseline preserves v1 reference logic (last 10 s; no added initial anchor).
    old=[]
    for c in calibration:
        r=f[(f.cycle==c)&(f.step==11)];r=r[r.time_s>=r.time_s.iloc[-1]-10]
        old.append(dict(soc=float(r.soc.median()),correction_V=float((r.V_V-r.loaded_V).median())))
    old.sort(key=lambda a:a['soc'])
    return dict(rest=anchors,baseline=old)


def reference(soc,loaded,ref,kind):
    if kind=='baseline':
        a=ref['baseline']
        return np.asarray(loaded)+np.interp(soc,[v['soc'] for v in a],[v['correction_V'] for v in a])
    a=ref['rest']
    return PchipInterpolator([v['soc'] for v in a],[v['V'] for v in a],extrapolate=False)(soc)


def basis(soc,knots):
    return np.column_stack([np.interp(soc,knots,np.eye(len(knots))[j]) for j in range(len(knots))])


def rc_basis(t,drive,tau,hold='left',initial=None):
    """Exact variable-step linear RC recurrence; drive may contain SOC bases."""
    t=np.asarray(t);drive=np.asarray(drive,float)
    if drive.ndim==1: drive=drive[:,None]
    if tau<=0 or np.any(np.diff(t)<=0) or hold not in ('left','right'): raise ValueError('Invalid RC input')
    state=np.zeros_like(drive)
    if initial is not None: state[0]=initial
    a=np.exp(-np.diff(t)/tau);which=0 if hold=='right' else -1
    for k in range(1,len(t)): state[k]=a[k-1]*state[k-1]+(1-a[k-1])*drive[k+which]
    return state


def design(g,kind,tau,knots,hold='left'):
    b=basis(g.soc,knots) if kind==METHODS[3] else np.ones((len(g),1))
    ohmic=b*g.I_A.to_numpy()[:,None]
    if kind in ['baseline',METHODS[1]]: return ohmic
    return np.column_stack([ohmic,rc_basis(g.time_s,ohmic,tau,hold)])


def quadrature(t):
    t=np.asarray(t);w=np.zeros(len(t))
    if len(t)>1:
        d=np.diff(t);w[:-1]+=d/2;w[1:]+=d/2
    return w


def phase(step):
    step=np.asarray(step)
    return np.where(step==10,'long_load',np.where(step==11,'long_rest',np.where(step<=15,'hppc','multisine_rest')))


def fit_weights(g,kind):
    if kind=='baseline':
        end=g[g.step==11].time_s.iloc[-1]
        return ((g.step<=15)&(g.time_s>=end-10)).to_numpy().astype(float)
    w=np.zeros(len(g));ph=phase(g.step)
    for name in np.unique(ph):
        ids=np.flatnonzero(ph==name);part=quadrature(g.time_s.to_numpy()[ids])
        if part.sum()>0: w[ids]=part/part.sum()
    return w


def box_solve(G,b,lo,hi):
    # Cholesky transforms the small sufficient-statistics system into bounded LS.
    L=np.linalg.cholesky(G)
    target=np.linalg.solve(L,b)
    return lsq_linear(L.T,target,bounds=(lo,hi),tol=1e-11).x


def fit_model(f,ref,kind,plan):
    bounds=plan['bounds'];knots=bounds['soc_knots']
    tau_grid=np.geomspace(*bounds['tau_s'],bounds['tau_grid_points']) if 'RC' in kind else np.array([1.])
    n0=3 if kind==METHODS[3] else 1;n=n0*(2 if 'RC' in kind else 1)
    lo=np.r_[np.full(n0,bounds['R0'][0]),np.full(n-n0,bounds['R1'][0])]
    hi=np.r_[np.full(n0,bounds['R0'][1]),np.full(n-n0,bounds['R1'][1])]
    grams=[];rhs=[];ys=[];excluded={}
    groups=[]
    for c in plan['calibration_cycles']:
        g=f[(f.cycle==c)&(f.step>=10)].copy()
        u=reference(g.soc,g.loaded_V,ref,'baseline' if kind=='baseline' else 'rest')
        w=fit_weights(g,kind);valid=np.isfinite(u)&np.isfinite(g.V_V.to_numpy())&(w>0)
        excluded[str(c)]=int(np.sum((w>0)&~valid));w[~valid]=0
        target=np.where(valid,u-g.V_V.to_numpy(),0)
        groups.append((g,w,target));cg=[];cb=[];cy=[]
        for tau in tau_grid:
            X=design(g,kind,tau,knots);cg.append(X.T@(w[:,None]*X));cb.append(X.T@(w*target));cy.append(float(w@(target**2)))
        grams.append(cg);rhs.append(cb);ys.append(cy)
    grams=np.asarray(grams);rhs=np.asarray(rhs);ys=np.asarray(ys)
    def solve(use):
        G=grams[use].sum(axis=0);b=rhs[use].sum(axis=0);y=ys[use].sum(axis=0)
        pars=[];ss=[]
        for k in range(len(tau_grid)):
            p=box_solve(G[k],b[k],lo,hi);pars.append(p)
            ss.append(max(0.,float(y[k]-2*b[k]@p+p@G[k]@p)))
        best=int(np.argmin(ss))
        return pars[best],float(tau_grid[best]),ss,G[best]
    pars,tau,profile,G=solve(np.arange(len(groups)))
    support=tau_grid[np.asarray(profile)<=min(profile)*1.05]
    stability=[]
    for omit,c in enumerate(plan['calibration_cycles']):
        pp,tt,_,_=solve([i for i in range(len(groups)) if i!=omit])
        stability.append(dict(omitted_cycle=c,parameters_ohm=pp.tolist(),tau_s=tt))
    # Include log-tau sensitivity, conditional on the fixed reference and SOC.
    js=[]
    for g,w,target in groups:
        X=design(g,kind,tau,knots)
        if 'RC' in kind:
            derivative=(design(g,kind,tau*1.001,knots)@pars-design(g,kind,tau*.999,knots)@pars)/.002
            X=np.column_stack([X,derivative])
        js.append(np.sqrt(w)[:,None]*X)
    J=np.vstack(js);norm=np.linalg.norm(J,axis=0)
    condition=float(np.linalg.cond(J/norm)) if np.all(norm>0) else 1e99
    interior=bool(np.all(pars>lo*1.001)&np.all(pars<hi*.999))
    identifiable=interior and condition<1000
    if 'RC' in kind: identifiable=identifiable and support[0]>tau_grid[0] and support[-1]<tau_grid[-1]
    return dict(kind=kind,parameters_ohm=pars.tolist(),tau_s=tau,soc_knots=knots,
        reference=ref,tau_grid_s=tau_grid.tolist(),profile_sse=profile,profile_5percent_support_s=[float(support[0]),float(support[-1])],
        normalized_sensitivity_condition=condition,identifiable=bool(identifiable),interior_parameters=interior,
        leave_one_calibration_cycle_out=stability,fit_unsupported_reference_rows=excluded,
        uncertainty_note='Conditional stability only: fixed calibration reference; no measurement/population confidence interval')


def predictions(f,model,cycles,*,soc_offset=0.,capacity_factor=1.,hold='left',alternate_reference=False,initial_polarization_V=0.):
    frames=[]
    for c in cycles:
        g=f[(f.cycle==c)&(f.step>=10)].copy()
        g['soc']=1-(1-g.soc)/capacity_factor+soc_offset
        kind=model['kind']
        refkind='baseline' if kind=='baseline' or alternate_reference else 'rest'
        u=reference(g.soc,g.loaded_V,model['reference'],refkind)
        X=design(g,kind,model['tau_s'],model['soc_knots'],hold)
        p=u-X@np.asarray(model['parameters_ohm'])
        if 'RC' in kind: p-=initial_polarization_V*np.exp(-(g.time_s-g.time_s.iloc[0])/model['tau_s'])
        g['reference_V']=u;g['predicted_V']=p;g['error_V']=p-g.V_V
        g['supported_reference']=np.isfinite(p);g['phase']=phase(g.step)
        transition=np.r_[True,np.abs(np.diff(g.I_A))>.5]
        starts=np.maximum.accumulate(np.where(transition,g.time_s,-np.inf));g['since_transition_s']=g.time_s-starts
        frames.append(g)
    return pd.concat(frames,ignore_index=True)


def aggregate(f,mask=None):
    # Weight only intervals whose two endpoints belong to the same requested bin.
    good=np.isfinite(f.error_V.to_numpy());requested=np.ones(len(f),bool) if mask is None else np.asarray(mask,bool)
    selected=good&requested;err=f.error_V.to_numpy()[selected]*1000
    if not len(err): return dict(n=0,unsupported_n=int(np.sum(requested&~good)),sample_rmse_mV=None,time_rmse_mV=None,bias_mV=None,max_abs_mV=None)
    energy=duration=0.
    for _,g in f.assign(_selected=selected).groupby('cycle',sort=False):
        ok=g._selected.to_numpy();dt=np.diff(g.time_s);e=g.error_V.to_numpy()*1000
        use=ok[:-1]&ok[1:];energy+=float(np.sum(dt[use]*(e[:-1][use]**2+e[1:][use]**2)/2));duration+=float(dt[use].sum())
    worst=f.loc[selected].iloc[int(np.argmax(abs(err)))]
    return dict(n=len(err),unsupported_n=int(np.sum(requested&~good)),sample_rmse_mV=float(np.sqrt(np.mean(err**2))),
        time_rmse_mV=float(np.sqrt(energy/duration)) if duration>0 else None,bias_mV=float(np.mean(err)),
        max_abs_mV=float(max(abs(err))),worst_source_row=int(worst.row),worst_cycle=int(worst.cycle),duration_s=duration)


def primary_mask(f,plan):
    d=plan['primary_domain']
    return f.soc.between(d['soc_min'],d['soc_max']) & f.I_A.between(d['current_min_A'],d['current_max_A']) & f.surface_C.between(d['surface_min_C'],d['surface_max_C'])


def score(f,plan):
    primary=primary_mask(f,plan);crit=plan['provisional_criterion'];threshold=crit['operational_voltage_threshold_V'];guard=crit['total_guard_V']
    groups={}
    for label,col,bins in [
        ('SOC','soc',[-np.inf,.2,.4,.6,.8,np.inf]),('current_A','I_A',[-np.inf,-.01,.01,2.7,4.9,10,np.inf]),
        ('surface_C','surface_C',[-np.inf,22,24,26,28,np.inf]),('since_transition_s','since_transition_s',[0,1,10,60,600,np.inf])]:
        groups[label]={f'{a:g}..{b:g}':aggregate(f,(f[col]>=a)&(f[col]<b)) for a,b in zip(bins[:-1],bins[1:])}
    groups['phase']={p:aggregate(f,f.phase==p) for p in f.phase.unique()}
    groups['cycle']={str(c):aggregate(f,f.cycle==c) for c in f.cycle.unique()}
    groups['pulse_vs_rest']={'loaded':aggregate(f,abs(f.I_A)>.01),'rest':aggregate(f,abs(f.I_A)<=.01)}
    near=abs(f.V_V-threshold)<=crit['near_threshold_halfwidth_V']
    p=aggregate(f,primary)
    passed=bool(p['n'] and p['unsupported_n']==0 and p['sample_rmse_mV']<=crit['sample_rmse_mV']
        and p['time_rmse_mV']<=crit['time_rmse_mV'] and abs(p['bias_mV'])<=crit['abs_bias_mV'] and p['max_abs_mV']<=crit['maximum_abs_mV'])
    return dict(full=aggregate(f),primary=p,primary_criteria_pass=passed,by=groups,
        near_threshold=aggregate(f,near),primary_near_threshold=aggregate(f,near&primary),
        threshold_diagnostics=dict(threshold_V=threshold,guard_V=guard,
            false_clearance_samples=int(((f.predicted_V>=threshold+guard)&(f.V_V<threshold)&primary).sum()),
            false_low_samples=int(((f.predicted_V<=threshold-guard)&(f.V_V>=threshold)&primary).sum()),
            undecided_samples=int((abs(f.predicted_V-threshold)<guard).sum()),
            note='Diagnostic counts on correlated samples; instrumentation/initialization budget unverified'))


def calibrate(cell,plan):
    low,f,q=load_cell(cell,plan['calibration_cycles'])
    ref=references(f,plan['calibration_cycles']);models={}
    for kind in METHODS:
        models[kind]=fit_model(f,ref,kind,plan)
        models[kind]['capacity_Ah']=q
        print(cell,kind,'tau',models[kind]['tau_s'],'parameters',models[kind]['parameters_ohm'],flush=True)
    return models


def develop():
    verify();plan=read_json(PLAN)
    if (OUT/'procedure_seal.json').exists(): raise ValueError('Procedure already frozen; do not retune')
    scores={}
    for cell in plan['development_cells']:
        models=calibrate(cell,plan);save(OUT/'development'/f'{cell}_models.json',models)
        _,f,_=load_cell(cell,list(range(1,10)))
        scores[cell]={}
        for kind,m in models.items():
            pred=predictions(f,m,plan['evaluation_cycles']);scores[cell][kind]=score(pred,plan)
            pred.to_csv(OUT/'development'/f'{cell}_{kind}_predictions.csv',index=False)
        print(cell,'development primary RMSE', {k:round(v['primary']['sample_rmse_mV'],3) for k,v in scores[cell].items()},flush=True)
    save(OUT/'development'/'scores.json',scores)
    macro={}
    for kind in METHODS:
        macro[kind]={k:float(np.mean([scores[c][kind]['primary'][k] for c in scores])) for k in ['sample_rmse_mV','time_rmse_mV']}
        macro[kind]['max_abs_mV']=max(scores[c][kind]['primary']['max_abs_mV'] for c in scores)
        macro[kind]['identifiable_all']=all(read_json(OUT/'development'/f'{c}_models.json')[kind]['identifiable'] for c in scores)
    b=macro['baseline'];eligible=[]
    for k in METHODS[1:]:
        m=macro[k];m['eligible']=bool(m['sample_rmse_mV']<=.8*b['sample_rmse_mV'] and m['time_rmse_mV']<=.8*b['time_rmse_mV'] and m['max_abs_mV']<=b['max_abs_mV'] and m['identifiable_all'])
        if m['eligible']: eligible.append(k)
    selected='baseline'
    if eligible:
        value=lambda k:(macro[k]['sample_rmse_mV']+macro[k]['time_rmse_mV'])/2
        best=min(value(k) for k in eligible)
        selected=next(k for k in eligible if value(k)<=1.1*best)
    save(OUT/'selection.json',dict(selected=selected,macro_development=macro,
        evidence='All development cells and old v1 assessment are already-used evidence. Selection precedes fresh-cell voltage access.'))
    files=list((OUT/'development').glob('*_models.json'))+[OUT/'development'/'scores.json',OUT/'selection.json']
    save(OUT/'procedure_seal.json',dict(created_utc=now(),implementation_sha256=v1.digest(__file__),plan_sha256=v1.digest(PLAN),
        lock_sha256=v1.digest(LOCK),artifacts={str(p).replace('\\','/'):v1.digest(p) for p in files},selected=selected,
        fresh_calibration_voltage_accessed=False,fresh_assessment_voltage_accessed=False))
    print('PROCEDURE FROZEN. Selected',selected,flush=True)


def check_procedure():
    verify();seal=read_json(OUT/'procedure_seal.json')
    if seal['implementation_sha256']!=v1.digest(__file__) or seal['lock_sha256']!=v1.digest(LOCK): raise ValueError('Frozen procedure changed')
    for p,h in seal['artifacts'].items():
        if v1.digest(p)!=h: raise ValueError('Frozen development artifact changed')
    return seal


def fresh_calibration():
    check_procedure();plan=read_json(PLAN)
    if (OUT/'fresh_model_seal.json').exists(): print('Fresh models already sealed; no refit.',flush=True);return
    files=[]
    for cell in plan['fresh_cells']:
        models=calibrate(cell,plan);path=OUT/'fresh'/f'{cell}_models.json';save(path,models);files.append(path)
    save(OUT/'fresh_model_seal.json',dict(created_utc=now(),procedure_seal_sha256=v1.digest(OUT/'procedure_seal.json'),
        artifacts={str(p).replace('\\','/'):v1.digest(p) for p in files},fresh_assessment_voltage_accessed=False))


def assess():
    check_procedure();plan=read_json(PLAN);seal=read_json(OUT/'fresh_model_seal.json')
    if seal['procedure_seal_sha256']!=v1.digest(OUT/'procedure_seal.json'): raise ValueError('Procedure binding changed')
    for p,h in seal['artifacts'].items():
        if v1.digest(p)!=h: raise ValueError('Frozen fresh parameters changed')
    scores={}
    for cell in plan['fresh_cells']:
        models=read_json(OUT/'fresh'/f'{cell}_models.json');_,f,_=load_cell(cell,plan['evaluation_cycles'])
        scores[cell]={}
        for kind,m in models.items():
            pred=predictions(f,m,plan['evaluation_cycles']);scores[cell][kind]=score(pred,plan)
            pred.to_csv(OUT/'fresh'/f'{cell}_{kind}_predictions.csv',index=False)
        print(cell,'fresh primary RMSE',{k:round(v['primary']['sample_rmse_mV'],3) for k,v in scores[cell].items()},flush=True)
    save(OUT/'fresh'/'scores.json',dict(created_utc=now(),fresh_model_seal_sha256=v1.digest(OUT/'fresh_model_seal.json'),
        interpretation='Additional characterized cells after own permitted calibration; same rig, not zero-shot or independent module validation',cells=scores))


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('command',choices=['reserve','develop','calibrate-fresh','assess','verify']);a=p.parse_args()
    if a.command=='reserve': reserve()
    elif a.command=='develop': develop()
    elif a.command=='calibrate-fresh': fresh_calibration()
    elif a.command=='assess': assess()
    else: verify();print('All preserved inputs and v1 artifacts unchanged.')


if __name__=='__main__': main()
