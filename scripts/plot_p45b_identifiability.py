"""Additional views of saved outputs only; no fitting or source access."""
import argparse
import csv
import gzip
import json
from pathlib import Path

import numpy as np

from ae_p45b_reproduction import ROOT, sha, write_json


def read(path):
    with gzip.open(path,'rt',encoding='utf-8',newline='') if path.suffix=='.gz' else path.open(encoding='utf-8',newline='') as f:
        return list(csv.DictReader(f))


def array(rows,key):
    return np.array([float(r[key]) if r[key] else np.nan for r in rows])


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',type=Path,required=True); parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args(); out=args.out.resolve()
    if not any(out.is_relative_to(ROOT/n) for n in ['reports','tmp','workspace']): raise SystemExit('Use reports/, tmp/ or workspace/.')
    if out.exists(): raise SystemExit('Use a new output directory.')
    for name,expected in json.loads((args.run/'manifest.json').read_text()).items():
        if sha(args.run/name)!=expected: raise ValueError('Saved output changed: '+name)
    out.mkdir(parents=True)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    colors={'B0':'#667582','C1_R0':'#ce8730','C2_R0_R1_R2':'#197e8c'}
    one=read(args.run/'used_1C_transfer.csv.gz'); t=array(one,'time_s')/60; measured=array(one,'voltage_V')
    fig,axes=plt.subplots(3,1,figsize=(11,8),sharex=True,constrained_layout=True)
    axes[0].plot(t,measured,color='#252d34',label='Measured',lw=1.5)
    for name,color in colors.items():
        y=array(one,name+'_V')
        axes[0].plot(t,y,color=color,label=name,lw=1)
        axes[1].plot(t,1000*(y-measured),color=color,lw=1)
    axes[2].plot(t,array(one,'source_current_A'),color='#252d34')
    for ax,label in zip(axes,['Voltage (V)','Prediction - measured (mV)','Current (A), charge positive']):
        ax.set_ylabel(label); ax.grid(alpha=.2)
    axes[0].legend(); axes[-1].set_xlabel('Recorded time (min)')
    fig.suptitle('P45B 25 degC complete 1C record: used-evidence transfer check\nExcluded from fitting; already opened earlier, so NOT fresh assessment')
    fig.savefig(out/'used_1C_comparison.png',dpi=150); plt.close(fig)
    fig,axes=plt.subplots(3,1,figsize=(11,10),sharex=True,constrained_layout=True)
    keys=['loaded_error_mV','late_median_difference_mV','recovery_difference_mV']
    for name,color in colors.items():
        for suffix,style,label in [('_pairs.csv','-',name+' fit'),('_leave_pair_out_pairs.csv','--',name+' leave-pair-out')]:
            if name=='B0' and 'leave' in suffix: continue
            if name=='B0': label='B0 frozen'
            rows=read(args.run/(name+suffix)); good=[r for r in rows if r['complete_prediction']=='True']
            z=array(good,'nominal_soc_loaded')
            for ax,key in zip(axes,keys): ax.plot(z,array(good,key),style,marker='.',color=color,label=label,lw=1)
    for ax,label in zip(axes,['Loaded endpoint error (mV)','Late-rest median error (mV)','Recovery error (mV)']):
        ax.set_ylabel(label); ax.grid(alpha=.2); ax.axhline(0,color='#888',lw=.5)
    axes[0].legend(fontsize=8); axes[-1].set_xlabel('Assumed nominal SOC at loaded endpoint')
    fig.suptitle('GITT full-sequence fits and excluded-pair predictions\nUsed development evidence; finite-rest medians are not equilibrium OCV')
    fig.savefig(out/'pair_errors.png',dpi=150); plt.close(fig)
    write_json(out/'manifest.json',dict(source_run_manifest_sha256=sha(args.run/'manifest.json'),
        implementation_sha256=sha(Path(__file__)),outputs={p.name:sha(p) for p in out.iterdir() if p.is_file()}))


if __name__=='__main__': main()
