"""Provisional, within-cell electrical identification with whole-cycle splits.

Models use a low-rate LOADED voltage curve plus a correction learned only from
calibration pre-pulse rests. Neither curve is asserted to be equilibrium OCV.
No Hall or module currents are used to identify these single-cell models.
"""
import argparse
import hashlib
from io import BytesIO
import itertools
import json
from pathlib import Path
from zipfile import ZipFile

import numpy as np
import pandas as pd
from scipy.integrate import cumulative_trapezoid
from scipy.io import loadmat
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

PLAN = Path("configs/cell_identification_v1.json")
LOCK = Path("configs/cell_identification_v1.lock.json")
OUT = Path("reports/identification_v1")


def digest(path):
    h = hashlib.sha256()
    with open(path,"rb") as f:
        for b in iter(lambda:f.read(1024*1024), b""):
            h.update(b)
    return h.hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value,indent=2,allow_nan=False)+"\n",encoding="utf-8")


def source_archive():
    candidates = list(Path.cwd().glob("Full factorial*.zip")) + list(Path("data/raw").glob("*.zip"))
    if len(candidates)!=1:
        raise ValueError("Place exactly one official dataset ZIP in root or data/raw")
    return candidates[0]


def read_cell(z, cell, protocol):
    base = ("OCVDis_" if protocol=="low_rate" else "HPPC_MultiSine_")+cell+".mat"
    names = [n for n in z.namelist() if n.endswith("/"+base)]
    if len(names)!=1:
        raise ValueError("Missing/ambiguous cell record: "+base)
    blob = z.read(names[0])
    d = loadmat(BytesIO(blob),simplify_cells=True)
    voltage = "OCV" if protocol=="low_rate" else "VoltageData"
    f = pd.DataFrame({"row":np.arange(1,len(d["TimeData"])+1),"time_s":d["TimeData"],
        "I_A":-d["CurrentData"],"V_V":d[voltage],"surface_C":d["TempData"]})
    if protocol!="low_rate":
        f["step"] = d["StepIndex"].astype(int); f["cycle"] = d["CycleIndex"].astype(int)
    if not np.isfinite(f.to_numpy()).all() or not np.all(np.diff(f.time_s)>0):
        raise ValueError("Nonfinite or nonmonotone characterization")
    return f,dict(member=names[0],sha256=hashlib.sha256(blob).hexdigest())


def reserve():
    plan = json.loads(PLAN.read_text())
    groups = [plan[k] for k in ["calibration_cycles","development_cycles","assessment_cycles"]]
    flat = sum(groups,[])
    if len(flat)!=len(set(flat)) or set(flat)!=set(range(1,10)):
        raise ValueError("Expected disjoint complete cycle allocation")
    archive = source_archive()
    provenance = json.loads(Path("reports/provenance.json").read_text())
    archive_hash = digest(archive)
    if archive_hash != provenance["sha256"]:
        raise ValueError("Original archive changed")
    protected_paths = [Path("configs/splits.json"),Path("configs/splits.lock.json")]
    protected_paths += [p for p in Path("reports").glob("*.json")]
    frozen = dict(plan_sha256=digest(PLAN),archive_sha256=archive_hash,
                  protected_existing={str(p).replace("\\","/"):digest(p) for p in protected_paths}, cells={})
    with ZipFile(archive) as z:
        for cell in plan["cells"]:
            low,lp = read_cell(z,cell,"low_rate")
            f,hp = read_cell(z,cell,"hppc")
            cycles = {}
            for cyc,g in f.groupby("cycle"):
                expected = {10,11,12,13,14,15,22}
                if not expected.issubset(set(g.step)):
                    raise ValueError("Incomplete pulse/rest cycle")
                cycles[str(cyc)] = {"source_first_row":int(g.row.iloc[0]),"source_last_row":int(g.row.iloc[-1]),
                    "steps":sorted(int(v) for v in g.step.unique())}
            frozen["cells"][cell] = dict(low_rate=lp,hppc_ms=hp,cycles=cycles)
    if LOCK.exists() and json.loads(LOCK.read_text()) != frozen:
        raise ValueError("Reserved inputs or allocation changed; preserve v1 and create a new reviewed version")
    save(LOCK,frozen)
    print("Reserved complete cycles before fitting; protected module manifests unchanged",flush=True)


def verify_inputs(check_archive=True):
    lock = json.loads(LOCK.read_text())
    if lock["plan_sha256"]!=digest(PLAN):
        raise ValueError("Identification plan changed after reservation")
    for path,sha in lock["protected_existing"].items():
        if digest(path)!=sha:
            raise ValueError("Protected provenance/split/audit changed: "+path)
    if check_archive and digest(source_archive())!=lock["archive_sha256"]:
        raise ValueError("Archive changed")
    return lock


def loaded_curve(low):
    q = cumulative_trapezoid(low.I_A,low.time_s,initial=0)/3600
    if np.any(np.diff(q)<=0) or q[-1]<=0:
        raise ValueError("Low-rate capacity curve is not a complete discharge")
    # Reverse monotone SOC order only for interpolation; no voltage smoothing.
    return float(q[-1]), (1-q/q[-1])[::-1], low.V_V.to_numpy()[::-1]


def prepare(low, f, calibration_cycles):
    capacity,x,y = loaded_curve(low)
    f = f.copy()
    f["soc_proxy"] = 1-cumulative_trapezoid(f.I_A,f.time_s,initial=0)/(3600*capacity)
    if f.soc_proxy.min()<0 or f.soc_proxy.max()>1.000001:
        raise ValueError("SOC proxy outside low-rate characterization; no silent clipping")
    f["loaded_V"] = np.interp(f.soc_proxy,x,y)
    anchors = []
    for cyc in calibration_cycles:
        rest = f[(f.cycle==cyc)&(f.step==11)]
        rest = rest[rest.time_s>=rest.time_s.iloc[-1]-10.]
        anchors.append({"cycle":cyc,"soc":float(rest.soc_proxy.median()),
            "correction_V":float((rest.V_V-rest.loaded_V).median()),
            "source_first_row":int(rest.row.iloc[0]),"source_last_row":int(rest.row.iloc[-1])})
    anchors.sort(key=lambda a:a["soc"])
    f["reference_V"] = f.loaded_V + np.interp(f.soc_proxy,[a["soc"] for a in anchors],[a["correction_V"] for a in anchors])
    sequences = {}
    for cyc,g in f.groupby("cycle"):
        end_rest = g[g.step==11].time_s.iloc[-1]
        seq = g[g.time_s>=end_rest-10.].copy().reset_index(drop=True)
        if np.max(np.diff(seq.time_s))>1.5:
            raise ValueError("Sequence has a missing interval")
        sequences[int(cyc)] = seq
    # Numerical integration sensitivity is not a measurement confidence interval.
    dt = np.diff(low.time_s)
    numerical = {"trapezoid_Ah":capacity,"left_Ah":float(np.dot(low.I_A.to_numpy()[:-1],dt)/3600),
                 "right_Ah":float(np.dot(low.I_A.to_numpy()[1:],dt)/3600)}
    return capacity,anchors,sequences,numerical


def unit_rc(time_s, current_A, tau_s, hold="left"):
    t,i = np.asarray(time_s),np.asarray(current_A)
    if tau_s<=0 or not np.isfinite(tau_s) or len(t)!=len(i) or np.any(np.diff(t)<=0):
        raise ValueError("Invalid RC inputs")
    if hold not in ("left","right"):
        raise ValueError("Declare input hold")
    a = np.exp(-np.diff(t)/tau_s)
    out = np.zeros(len(t))
    drive = i[:-1] if hold=="left" else i[1:]
    for k in range(1,len(t)):
        out[k] = a[k-1]*out[k-1]+(1-a[k-1])*drive[k-1]
    return out


def bounded_two(G, b, lower, upper):
    """Exact 2-variable box-constrained quadratic minimizer, including edges."""
    candidates = []
    try:
        p = np.linalg.solve(G,b)
        if np.all(p>=lower) and np.all(p<=upper):
            candidates.append(p)
    except np.linalg.LinAlgError:
        pass
    for k in range(2):
        j=1-k
        for edge in [lower[k],upper[k]]:
            v=np.zeros(2);v[k]=edge
            v[j]=np.clip((b[j]-G[j,k]*edge)/G[j,j],lower[j],upper[j]) if G[j,j]>0 else lower[j]
            candidates.append(v)
    return min(candidates,key=lambda p:float(p@G@p-2*b@p))


def fit_candidates(sequences, calibration, plan, hold="left"):
    tau_grid = np.geomspace(*plan["parameter_bounds"]["tau_s"],121)
    lo=np.array([plan["parameter_bounds"]["R0_ohm"][0],plan["parameter_bounds"]["R1_ohm"][0]])
    hi=np.array([plan["parameter_bounds"]["R0_ohm"][1],plan["parameter_bounds"]["R1_ohm"][1]])
    # Sufficient statistics per whole calibration sequence, never assessment.
    grams=np.zeros((len(calibration),len(tau_grid),2,2)); rhs=np.zeros((len(calibration),len(tau_grid),2)); yy=[]
    for j,cyc in enumerate(calibration):
        seq=sequences[cyc]; f=seq[seq.step<=15]
        target=(f.reference_V-f.V_V).to_numpy(); i=f.I_A.to_numpy(); yy.append(float(target@target))
        for k,tau in enumerate(tau_grid):
            x=unit_rc(f.time_s,i,tau,hold)
            X=np.column_stack([i,x]); grams[j,k]=X.T@X; rhs[j,k]=X.T@target
    def fit_weights(weights):
        G=np.einsum("c,ctij->tij",weights,grams);b=np.einsum("c,cti->ti",weights,rhs);y2=float(np.dot(weights,yy))
        profile=[];pars=[]
        for k in range(len(tau_grid)):
            par=bounded_two(G[k],b[k],lo,hi);pars.append(par)
            profile.append(max(0.,float(y2-2*b[k]@par+par@G[k]@par)))
        best=int(np.argmin(profile));r0=float(np.clip(b[0,0]/G[0,0,0],lo[0],hi[0]))
        return dict(R0_ohm=float(pars[best][0]),R1_ohm=float(pars[best][1]),tau_s=float(tau_grid[best])),profile,r0
    rc,profile,r0=fit_weights(np.ones(len(calibration)))
    # Deterministic whole-cycle bootstrap. All ordered draws are equally weighted.
    boot=[];cache={}
    for draw in itertools.product(range(len(calibration)),repeat=len(calibration)):
        counts=tuple(draw.count(j) for j in range(len(calibration)))
        if counts not in cache:
            fit,_,br0=fit_weights(counts);cache[counts]=[fit["R0_ohm"],fit["R1_ohm"],fit["tau_s"],br0]
        boot.append(cache[counts])
    intervals=np.quantile(boot,[.025,.975],axis=0)
    support=[float(t) for t,s in zip(tau_grid,profile) if s <= min(profile)*1.05]
    interior=bool(lo[0]<rc["R0_ohm"]<hi[0] and lo[1]<rc["R1_ohm"]<hi[1]
                  and tau_grid[0]<rc["tau_s"]<tau_grid[-1] and support[0]>tau_grid[0] and support[-1]<tau_grid[-1])
    jac=[]
    for cyc in calibration:
        f=sequences[cyc];f=f[f.step<=15];i=f.I_A.to_numpy();t=f.time_s.to_numpy();tau=rc["tau_s"]
        x=unit_rc(t,i,tau,hold);dx=(unit_rc(t,i,tau*1.001,hold)-unit_rc(t,i,tau*.999,hold))/.002
        jac.append(np.column_stack([i,x,rc["R1_ohm"]*dx]))
    J=np.vstack(jac);norms=np.linalg.norm(J,axis=0)
    if np.any(norms==0):
        raise ValueError("Insufficient excitation for RC identification")
    normal=J/norms
    return dict(resistive={"R0_ohm":r0,"R1_ohm":0.,"tau_s":1.},one_rc=rc,
        bootstrap_intervals={n:{"p2_5":float(intervals[0,k]),"p97_5":float(intervals[1,k])}
            for k,n in enumerate(["R0_ohm","R1_ohm","tau_s","resistive_R0_ohm"])},
        bootstrap_draws=len(boot),uncertainty_note="Conditional cycle bootstrap with loaded curve, capacity, SOC convention and calibration rest-reference anchors fixed; not a metrological or population interval.",
        tau_grid_s=tau_grid.tolist(),profile_sse_V2=profile,profile_5percent_support_s=[min(support),max(support)],
        normalized_sensitivity_condition=float(np.linalg.cond(normal)),interior_identifiability_screen=interior)


def predict(sequence, parameters, hold="left"):
    state=unit_rc(sequence.time_s.to_numpy(),sequence.I_A.to_numpy(),parameters["tau_s"],hold)
    return sequence.reference_V.to_numpy()-parameters["R0_ohm"]*sequence.I_A.to_numpy()-parameters["R1_ohm"]*state


def metrics(error,t):
    error=np.asarray(error);t=np.asarray(t)
    return dict(n=len(error),rmse_mV=float(np.sqrt(np.mean(error**2))*1000),bias_mV=float(np.mean(error)*1000),
                max_abs_mV=float(np.max(abs(error))*1000),
                time_weighted_rmse_mV=float(np.sqrt(np.trapz(error**2,t)/(t[-1]-t[0]))*1000))


def evaluate(sequences,cycles,parameters,hold="left"):
    scores={};errors=[]
    for cyc in cycles:
        seq=sequences[cyc];pred=predict(seq,parameters,hold);err=pred-seq.V_V.to_numpy()
        score={}
        for name,mask in [("hppc",seq.step<=15),("multisine_and_rest",seq.step>=17),("full_sequence",np.ones(len(seq),dtype=bool))]:
            score[name]=metrics(err[mask],seq.time_s.to_numpy()[mask])
            part=seq[mask];worst=int(np.argmax(abs(err[mask])))
            score[name]["current_A_range"]=[float(part.I_A.min()),float(part.I_A.max())]
            score[name]["max_error_source_row"]=int(part.row.iloc[worst])
            score[name]["max_error_step"]=int(part.step.iloc[worst])
        score["surface_C_range"]=[float(seq.surface_C.min()),float(seq.surface_C.max())]
        score["soc_proxy_range"]=[float(seq.soc_proxy.min()),float(seq.soc_proxy.max())]
        scores[str(cyc)]=score;errors.extend(err[seq.step<=15])
    return {"cycles":scores,"hppc_pooled_rmse_mV":float(np.sqrt(np.mean(np.square(errors)))*1000)}


def plot_sequences(cell,sequences,cycles,parameters,split):
    fig,axes=plt.subplots(len(cycles),2,figsize=(12,3*len(cycles)),layout="constrained",squeeze=False)
    for row,cyc in enumerate(cycles):
        s=sequences[cyc];t=s.time_s-s.time_s.iloc[0];pv=predict(s,parameters);e=1000*(pv-s.V_V)
        axes[row,0].plot(t,s.V_V,label="Measured",color="black",lw=1)
        axes[row,0].plot(t,pv,label="Provisional prediction",color="#0072B2",lw=.8)
        axes[row,0].set(ylabel="Cell voltage [V]",title=f"{cell}, cycle {cyc}, {split}")
        axes[row,1].plot(t,e,color="#a13d2d",lw=.8);axes[row,1].axhline(0,color="black",lw=.5)
        axes[row,1].set(ylabel="Predicted - measured [mV]",title="Full pulse/rest + multisine/rest; no voltage reset")
        for ax in axes[row]: ax.set_xlabel("Time since pre-pulse window start [s]");ax.grid(alpha=.2)
    axes[0,0].legend(fontsize=8)
    fig.savefig(OUT/f"{cell}_{split}.png",dpi=150);plt.close(fig)


def load_prepared(cell,plan):
    with ZipFile(source_archive()) as z:
        low,lp=read_cell(z,cell,"low_rate");f,hp=read_cell(z,cell,"hppc")
    lock=json.loads(LOCK.read_text())["cells"][cell]
    if lp!=lock["low_rate"] or hp!=lock["hppc_ms"]:
        raise ValueError("Characterization source changed")
    return prepare(low,f,plan["calibration_cycles"])


def fit():
    verify_inputs()
    if (OUT/"model_seal.json").exists():
        print("Existing frozen model seal found; no refitting. Use a reviewed v2 for changes.",flush=True)
        return
    plan=json.loads(PLAN.read_text());models={}
    for cell in plan["cells"]:
        capacity,anchors,seq,numerical=load_prepared(cell,plan)
        candidates=fit_candidates(seq,plan["calibration_cycles"],plan)
        dev={name:evaluate(seq,plan["development_cycles"],candidates[name]) for name in ["resistive","one_rc"]}
        ratio=dev["one_rc"]["hppc_pooled_rmse_mV"]/dev["resistive"]["hppc_pooled_rmse_mV"]
        chosen="one_rc" if ratio<=.8 and candidates["interior_identifiability_screen"] else "resistive"
        model=dict(cell=cell,selected=chosen,parameters=candidates[chosen],capacity_Ah=capacity,
            rest_reference_anchors=anchors,capacity_quadrature=numerical,candidates=candidates,development=dev,
            development_rc_over_resistive_rmse_ratio=ratio,
            status="provisional within-cell model; equilibrium OCV and temperature law not identified",
            calibration=evaluate(seq,plan["calibration_cycles"],candidates[chosen]),
            right_hold_sensitivity_development=evaluate(seq,plan["development_cycles"],candidates[chosen],hold="right"))
        save(OUT/f"{cell}_model.json",model);models[cell]=digest(OUT/f"{cell}_model.json")
        plot_sequences(cell,seq,plan["development_cycles"],candidates[chosen],"development")
        print(cell,chosen,candidates[chosen],"dev HPPC mV",dev[chosen]["hppc_pooled_rmse_mV"],flush=True)
        # A usable resistive baseline is also a legitimate result: do not require
        # an RC model merely to extend the same method to another inspected cell.
    save(OUT/"model_seal.json",dict(lock_sha256=digest(LOCK),plan_sha256=digest(PLAN),
        implementation_sha256=digest(Path(__file__)),model_files_sha256=models,
        assessment_voltage_used_for_fitting_or_selection=False))


def assess():
    verify_inputs();plan=json.loads(PLAN.read_text());seal=json.loads((OUT/"model_seal.json").read_text())
    if seal["lock_sha256"]!=digest(LOCK) or seal["implementation_sha256"]!=digest(Path(__file__)):
        raise ValueError("Frozen model implementation/inputs changed; do not tune on v1 assessment")
    scores={}
    for cell,sha in seal["model_files_sha256"].items():
        path=OUT/f"{cell}_model.json"
        if digest(path)!=sha: raise ValueError("Frozen parameters changed")
        model=json.loads(path.read_text());_,anchors,seq,_=load_prepared(cell,plan)
        if anchors!=model["rest_reference_anchors"]: raise ValueError("Calibration reference changed")
        # No assessment voltage contributes to parameters, anchors or model choice.
        scores[cell]=evaluate(seq,plan["assessment_cycles"],model["parameters"])
        plot_sequences(cell,seq,plan["assessment_cycles"],model["parameters"],"assessment")
        frames=[]
        for cyc in plan["assessment_cycles"]:
            f=seq[cyc].copy();f["predicted_V"]=predict(f,model["parameters"]);f["error_V"]=f.predicted_V-f.V_V;frames.append(f)
        pd.concat(frames).to_csv(OUT/f"{cell}_assessment_predictions.csv",index=False)
        print(cell,"assessment HPPC mV",scores[cell]["hppc_pooled_rmse_mV"],flush=True)
    save(OUT/"assessment.json",dict(model_seal_sha256=digest(OUT/"model_seal.json"),
        interpretation="Held complete sequences of the same cells/rig; not independent module validation",cells=scores))


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("command",choices=["reserve","fit","assess","all"])
    args=p.parse_args()
    if args.command in ("reserve","all"): reserve()
    if args.command in ("fit","all"): fit()
    if args.command in ("assess","all"): assess()


if __name__=="__main__": main()
