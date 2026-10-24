"""Versioned extension of frozen coupling.py; electrical software evidence only.

Reuse its Kirchhoff solver. Retain its left-held branch-current state convention,
with explicit event boundaries and additional node, loss and energy accounting.
"""
from dataclasses import dataclass
import numpy as np
import pandas as pd
from . import coupling as legacy
from .reference_investigation import reference_function


class VoltageReference:
    def __init__(self, model, kind='sealed_rest_pchip', loaded_curve=None, origin_shift=0.):
        a=model['reference']['rest']; self.origin=float(origin_shift)
        x=np.array([r['soc'] for r in a]); y=np.array([r['V'] for r in a])
        self.bounds=(float(x[0]+self.origin),float(x[-1]+self.origin));self.kind=kind
        if kind=='sealed_rest_pchip':
            self.curve=reference_function(model,None,kind,self.origin)
            self.integral=self.curve.antiderivative()
        elif kind=='loaded_shape_same_rest_anchors':
            if loaded_curve is None: raise ValueError('Loaded-shape sensitivity requires attributed C/20 data')
            lx,ly=map(np.asarray,loaded_curve)
            if len(lx)<2 or lx.shape!=ly.shape or np.any(np.diff(lx)<=0) or not np.isfinite(ly).all():
                raise ValueError('Invalid loaded reference data')
            self.bounds=(max(x[0],lx[0])+self.origin,min(x[-1],lx[-1])+self.origin)
            self.x=np.unique(np.r_[x,lx[(lx>=x[0])&(lx<=x[-1])]])
            self.y=np.interp(self.x,lx,ly)+np.interp(self.x,x,y-np.interp(x,lx,ly))
            self.slope=np.diff(self.y)/np.diff(self.x)
            self.area=np.r_[0,np.cumsum(np.diff(self.x)*(self.y[:-1]+self.y[1:])/2)]
        else: raise ValueError('Unknown reference choice')

    def supported(self,z):
        return bool(np.isfinite(z) and self.bounds[0]<=z<=self.bounds[1] and 0<=z-self.origin<=1)

    def value(self,z):
        if not self.supported(z): raise ValueError('Reference/SOC domain exceeded; no extrapolation')
        if self.kind=='sealed_rest_pchip': return float(self.curve(z))
        return float(np.interp(z-self.origin,self.x,self.y))

    def primitive(self,z):
        if not self.supported(z): raise ValueError('Source-work integral left reference domain')
        if self.kind=='sealed_rest_pchip': return float(self.integral(z))
        q=z-self.origin;k=min(np.searchsorted(self.x,q,side='right')-1,len(self.x)-2)
        dx=q-self.x[k]
        return float(self.area[k]+self.y[k]*dx+.5*self.slope[k]*dx*dx)


@dataclass
class DynamicResult:
    frame: pd.DataFrame
    status: str
    stop: dict | None


def validate_profile(profile):
    if not profile: raise ValueError('A load profile is required')
    end=0.
    for p in profile:
        if not np.isfinite([p['start_s'],p['end_s'],p['current_A']]).all(): raise ValueError('Nonfinite load')
        if abs(p['start_s']-end)>1e-10 or p['end_s']<=p['start_s']: raise ValueError('Load must cover contiguous intervals from zero')
        end=p['end_s']
    return float(end)


def rc_interval(vp,current,r1,tau,h):
    """Exact held-current RC state and resistor energy, including initial storage."""
    a=np.exp(-h/tau);one=-np.expm1(-h/tau);two=-np.expm1(-2*h/tau)
    b=r1*current;d=vp-b
    end=b+d*a
    loss=(b*b*h+2*b*d*tau*one+d*d*tau*two/2)/r1
    work=current*(b*h+d*tau*one)
    return end,loss,work


def simulate(models,initial_soc,initial_polarization_V,profile,dt_s,positive_rail_ohm,negative_rail_ohm,
             *,capacity_factor=1.,reference_kind='sealed_rest_pchip',loaded_curves=None,origin_shift=0.):
    n=len(models);z=np.asarray(initial_soc,float).copy();vp=np.asarray(initial_polarization_V,float).copy()
    if n<1 or z.shape!=(n,) or vp.shape!=(n,) or not np.isfinite(np.r_[z,vp,dt_s,capacity_factor,origin_shift]).all():
        raise ValueError('Invalid initial states')
    if dt_s<=0 or capacity_factor<=0: raise ValueError('Positive dt and capacity required')
    if any(m['kind']!='C2_rest_reference_RC' for m in models): raise ValueError('This backend requires frozen constant one-RC models')
    q=np.array([m['capacity_Ah'] for m in models])*capacity_factor
    r0=np.array([m['parameters_ohm'][0] for m in models]);r1=np.array([m['parameters_ohm'][1] for m in models])
    tau=np.array([m['tau_s'] for m in models]);cap=tau/r1
    if not np.isfinite(np.r_[q,r0,r1,tau]).all() or np.any(np.r_[q,r0,r1,tau]<=0): raise ValueError('Invalid frozen parameters')
    refs=[VoltageReference(m,reference_kind,None if loaded_curves is None else loaded_curves[k],origin_shift) for k,m in enumerate(models)]
    rp=np.asarray(positive_rail_ohm,float);rn=np.asarray(negative_rail_ohm,float)
    duration=validate_profile(profile)
    if duration/dt_s>1000000: raise ValueError('More than one million steps; choose a coarser step or shorter run')
    # Include every load transition; twelve decimal places remove duplicate float-grid boundaries.
    grid=np.unique(np.round(np.r_[np.arange(0,duration,dt_s),[p['end_s'] for p in profile],duration],12))
    if len(grid)>1000001: raise ValueError('More than one million steps; choose a coarser step or shorter run')
    starts=np.array([p['start_s'] for p in profile]);z0=z.copy();initial_storage=float(.5*np.dot(cap,vp*vp))
    charge=0.;branch_charge=np.zeros(n);energy=np.zeros(6);rows=[]

    def solve(state,polar,current):
        u=np.array([refs[k].value(state[k]) for k in range(n)])
        return u,legacy.solve_ladder(u-polar,r0,rp,rn,current)

    for j,t in enumerate(grid):
        bad=[k for k in range(n) if not refs[k].supported(z[k])]
        if bad:
            return DynamicResult(pd.DataFrame(rows),'stopped: mathematically undefined',dict(time_s=float(t),cells=[k+1 for k in bad],SOC=z.tolist(),reason='SOC/reference domain'))
        load=profile[min(np.searchsorted(starts,t,side='right')-1,len(profile)-1)]['current_A']
        u,s=solve(z,vp,load);storage=float(.5*np.dot(cap,vp*vp));pr1=float(np.sum(vp*vp/r1))
        storage_rate=float(np.sum(vp*(s.branch_A-vp/r1)));p=float(s.terminal_V*load)
        row=dict(time_s=float(t),step_s=0.,module_current_A=float(load),terminal_V=s.terminal_V,terminal_power_W=p,
            reference_source_power_W=float(u@s.branch_A),cell_R0_loss_W=s.ohmic_cell_loss_W,polarization_R1_loss_W=pr1,
            rail_loss_W=s.rail_loss_W,capacitor_energy_J=storage,capacitor_storage_rate_W=storage_rate,
            kcl_residual_A=s.kcl_residual_A,network_power_residual_W=s.energy_residual_W,
            complete_power_residual_W=float(u@s.branch_A-p-s.ohmic_cell_loss_W-s.rail_loss_W-pr1-storage_rate),
            charge_balance_As=float(np.dot(q,z0-z)*3600-charge),module_charge_As=float(charge),
            reference_source_work_Wh=float(energy[0]/3600),delivered_net_Wh=float(energy[1]/3600),
            delivered_positive_Wh=float(energy[2]/3600),received_Wh=float(energy[3]/3600),
            R0_and_rail_loss_Wh=float(energy[4]/3600),R1_loss_Wh=float(energy[5]/3600),
            energy_balance_residual_Wh=float((energy[0]-energy[1]-energy[4]-energy[5]-(storage-initial_storage))/3600))
        for k in range(n):
            row.update({f'I{k+1}_A':float(s.branch_A[k]),f'SOC{k+1}':float(z[k]),f'polarization{k+1}_V':float(vp[k]),
                f'reference{k+1}_V':float(u[k]),f'V{k+1}_V':float(s.cell_terminal_V[k]),
                f'positive_node{k+1}_V':float(s.positive_nodes_V[k]),f'negative_node{k+1}_V':float(s.negative_nodes_V[k]),
                f'R0_loss{k+1}_W':float(r0[k]*s.branch_A[k]**2),f'R1_loss{k+1}_W':float(vp[k]**2/r1[k]),
                f'charge_balance{k+1}_As':float(3600*q[k]*(z0[k]-z[k])-branch_charge[k])})
        for k in range(n-1):
            row.update({f'rail{k+1}_current_A':float(s.rail_downstream_A[k]),
                f'positive_rail{k+1}_drop_V':float(rp[k]*s.rail_downstream_A[k]),
                f'negative_rail{k+1}_drop_V':float(rn[k]*s.rail_downstream_A[k]),
                f'positive_rail{k+1}_loss_W':float(rp[k]*s.rail_downstream_A[k]**2),
                f'negative_rail{k+1}_loss_W':float(rn[k]*s.rail_downstream_A[k]**2)})
        row['interval_end_terminal_V']=s.terminal_V
        for k in range(n):
            row[f'interval_end_I{k+1}_A']=float(s.branch_A[k])
            row[f'interval_end_V{k+1}_V']=float(s.cell_terminal_V[k])
        rows.append(row)
        if j==len(grid)-1: break
        h=float(grid[j+1]-t);next_z=z-s.branch_A*h/(3600*q)
        bad=[k for k in range(n) if not refs[k].supported(next_z[k])]
        if bad:
            crossings=[]
            for k in bad:
                bound=refs[k].bounds[0 if next_z[k]<z[k] else 1]
                crossings.append(float(t+h*(bound-z[k])/(next_z[k]-z[k])))
            return DynamicResult(pd.DataFrame(rows),'stopped: mathematically undefined',dict(last_valid_time_s=float(t),
                attempted_time_s=float(grid[j+1]),first_reference_boundary_time_s=min(crossings),cells=[k+1 for k in bad],
                attempted_SOC=next_z.tolist(),reason='Step would leave SOC/reference support; no clipping or extrapolation'))
        next_vp,r1_loss,_=rc_interval(vp,s.branch_A,r1,tau,h)
        _,end_s=solve(next_z,next_vp,load)  # old load at interval end, before any switch
        row['interval_end_terminal_V']=end_s.terminal_V
        for k in range(n):
            row[f'interval_end_I{k+1}_A']=float(end_s.branch_A[k])
            row[f'interval_end_V{k+1}_V']=float(end_s.cell_terminal_V[k])
        end_p=end_s.terminal_V*load
        work=sum(3600*q[k]*(refs[k].primitive(z[k])-refs[k].primitive(next_z[k])) for k in range(n))
        energy+=np.array([work,h*(p+end_p)/2,h*(max(p,0)+max(end_p,0))/2,
            h*(max(-p,0)+max(-end_p,0))/2,h*(s.ohmic_cell_loss_W+s.rail_loss_W),float(r1_loss.sum())])
        charge+=load*h;branch_charge+=s.branch_A*h;row['step_s']=h
        z,vp=next_z,next_vp
    return DynamicResult(pd.DataFrame(rows),'completed',None)
