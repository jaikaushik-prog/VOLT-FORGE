"""Limited dynamic ladder coupling for software verification, not validation."""
import numpy as np
import pandas as pd
from .ladder import solve_ladder
from .improvement import reference, basis


def simulate(models,initial_soc,module_A,duration_s,dt_s,rail_ohm=.001):
    n=len(models);soc=np.asarray(initial_soc,float).copy();vp=np.zeros(n)
    if soc.shape!=(n,) or dt_s<=0 or duration_s<=0: raise ValueError('Invalid integration domain')
    q=np.array([m['capacity_Ah'] for m in models]);start=soc.copy();rows=[];clock=0.
    while True:
        u=[];r0=[];r1=[];tau=[]
        for k,m in enumerate(models):
            u.append(float(reference([soc[k]],[0.],m['reference'],'rest')[0]))
            p=m['parameters_ohm'];b=basis([soc[k]],m['soc_knots'])[0]
            if m['kind']=='C3_rest_reference_SOC_RC': r0.append(float(b@p[:3]));r1.append(float(b@p[3:]))
            else: r0.append(p[0]);r1.append(p[1] if len(p)>1 else 0.)
            tau.append(m['tau_s'])
        if not np.isfinite(u).all(): raise ValueError('Coupling left supported reference domain')
        sol=solve_ladder(np.asarray(u)-vp,r0,[rail_ohm]*(n-1),[rail_ohm]*(n-1),module_A)
        row=dict(time_s=clock,terminal_V=sol.terminal_V,kcl_residual_A=sol.kcl_residual_A,
            electrical_energy_residual_W=sol.energy_residual_W,
            total_charge_balance_As=float(np.sum(q*(start-soc))*3600-module_A*clock))
        for k in range(n): row.update({f'I{k+1}_A':sol.branch_A[k],f'SOC{k+1}':soc[k],f'V{k+1}_V':sol.cell_terminal_V[k]})
        rows.append(row)
        if clock>=duration_s: break
        step=min(dt_s,duration_s-clock)
        soc-=sol.branch_A*step/(3600*q)
        a=np.exp(-step/np.asarray(tau));vp=a*vp+(1-a)*np.asarray(r1)*sol.branch_A
        clock=min(clock+step,duration_s)
    return pd.DataFrame(rows)
