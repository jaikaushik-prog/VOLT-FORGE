"""Comparisons in declared order, without optimization or ranking."""
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from .workflow import read,save,load_configuration


def electrical_plots(folder,case):
    f=pd.read_csv(folder/'trajectory.csv')
    if not len(f):return
    colors=['#0072B2','#D55E00','#009E73','#CC79A7'];fig,axes=plt.subplots(2,2,figsize=(12,8),layout='constrained')
    axes[0,0].plot(f.time_s,f.terminal_V,color='black',lw=2,label='Module terminal')
    for k,(cell,color) in enumerate(zip(case['cell_order'],colors),1):
        axes[0,0].plot(f.time_s,f[f'V{k}_V'],color=color,lw=.8,label=cell+' cell nodes')
        axes[0,1].plot(f.time_s,f[f'I{k}_A'],color=color,label=cell)
        axes[1,0].plot(f.time_s,f[f'SOC{k}'],color=color,label=cell)
    axes[0,0].set(ylabel='Voltage [V]',title='Defined terminal and cell-node voltages');axes[0,0].legend(fontsize=7)
    axes[0,1].axhline(4.9,color='#777777',ls='--',label='4.9 A primary-subset edge, not a limit')
    axes[0,1].set(ylabel='Discharge-positive current [A]',title='Branch current');axes[0,1].legend(fontsize=7)
    axes[1,0].set(ylabel='SOC proxy',title='Initial state and capacity are assumptions')
    for col,label in [('cell_R0_loss_W','Cell R0'),('polarization_R1_loss_W','Polarization R1'),('rail_loss_W','Both rails')]:
        axes[1,1].plot(f.time_s,f[col],label=label)
    axes[1,1].set(ylabel='Calculated electrical loss [W]',title='Resistor dissipation, not temperature');axes[1,1].legend(fontsize=8)
    for ax in axes.flat:ax.set_xlabel('Time [s]');ax.grid(alpha=.2)
    fig.suptitle(case['id']+' | synthetic simulation; experimental validation pending')
    fig.savefig(folder/'electrical.png',dpi=140);plt.close(fig)
    fig,axes=plt.subplots(2,2,figsize=(12,7),layout='constrained')
    for k,(cell,color) in enumerate(zip(case['cell_order'],colors),1):
        axes[0,0].plot(f.time_s,f[f'positive_node{k}_V'],color=color,label=f'p{k}: {cell}')
        axes[0,1].plot(f.time_s,f[f'negative_node{k}_V']*1000,color=color,label=f'n{k}: {cell}')
    for k in range(1,4):
        axes[1,0].plot(f.time_s,f[f'positive_rail{k}_drop_V']*1000,label=f'positive segment {k}')
        axes[1,0].plot(f.time_s,f[f'negative_rail{k}_drop_V']*1000,ls='--',label=f'negative segment {k}')
    axes[1,1].plot(f.time_s,f.terminal_power_W,color='black',label='Delivered terminal power')
    axes[0,0].set(ylabel='Positive node voltage [V]',title='All potentials relative to n1 = 0 V')
    axes[0,1].set(ylabel='Negative node voltage [mV]',title='Shared return-rail potentials')
    axes[1,0].set(ylabel='Signed segment drop [mV]',title='Solid positive rail; dashed negative rail')
    axes[1,1].set(ylabel='Power [W]',title=f'Net service: {f.delivered_net_Wh.iloc[-1]:.4f} Wh')
    for ax in axes.flat:ax.set_xlabel('Time [s]');ax.grid(alpha=.2);ax.legend(fontsize=7)
    fig.suptitle(case['id']+' | model node/power outputs; hypothetical interconnects')
    fig.savefig(folder/'nodes_and_power.png',dpi=140);plt.close(fig)


def compare(out):
    out=Path(out);manifest=load_configuration(out);plan=read(out/'scenario_plan.json');rows=[];sens=[]
    metrics=['maximum_branch_current_A','minimum_cell_voltage_V','minimum_terminal_voltage_V','mean_delivered_power_W',
        'delivered_net_Wh','delivered_charge_Ah','cell_R0_loss_Wh','rail_loss_Wh','R1_loss_Wh','above_4_9A_cell_seconds']
    for name in manifest['scenarios']:
        folder=out/'runs'/name;s=read(folder/'summary.json');c=read(folder/'configuration.json')
        rows.append(dict(scenario=name,**{k:s.get(k) for k in metrics},requirement=s['voltage_requirement']['status'],decision=s['decision'],status=s['status']))
        electrical_plots(folder,c)
        for variant in ['nominal']+[v['id'] for v in plan['sensitivity_scenarios']]:
            p=folder/'summary.json' if variant=='nominal' else out/'runs'/f'{name}__{variant}'/'summary.json'
            if p.exists():
                score=read(p);sens.append(dict(scenario=name,sensitivity=variant,**{k:score.get(k) for k in metrics},decision=score['decision']))
    table=pd.DataFrame(rows);table.to_csv(out/'comparison.csv',index=False)
    sensitivity=pd.DataFrame(sens);sensitivity.to_csv(out/'sensitivity_comparison.csv',index=False)
    contrasts={}
    for name in manifest['scenarios'][1:]:
        a=sensitivity[sensitivity.scenario==name].set_index('sensitivity')
        b=sensitivity[sensitivity.scenario=='equal_soc'].set_index('sensitivity');common=a.index.intersection(b.index)
        contrasts[name]={}
        for col in metrics:
            values=a.loc[common,col]-b.loc[common,col]
            contrasts[name][col]=dict(minimum_delta_vs_equal_soc=float(values.min()),maximum_delta_vs_equal_soc=float(values.max()),
                delta_changes_sign=bool(values.min()<0<values.max()))
    save(out/'sensitivity_contrasts.json',dict(comparisons=contrasts,note='Matched one-at-a-time sensitivity scenarios, not confidence intervals, independent uncertainty bounds, repair ranks or experimental gains.',
        decision='insufficient evidence in every scenario'))
    fig,axes=plt.subplots(2,2,figsize=(12,7),layout='constrained')
    for ax,col,label in zip(axes.flat,['maximum_branch_current_A','minimum_terminal_voltage_V','delivered_net_Wh','rail_loss_Wh'],
        ['Maximum branch current [A]','Minimum terminal voltage [V]','Delivered net energy [Wh]','Rail resistive loss [Wh]']):
        for k,name in enumerate(manifest['scenarios']):
            values=sensitivity[sensitivity.scenario==name]
            ax.scatter(k+np.linspace(-.15,.15,len(values)),values[col],s=22,color='#0072B2',alpha=.7)
            ax.scatter(k,values[values.sensitivity=='nominal'][col],color='black',marker='x',s=65)
        ax.set(xticks=range(4),xticklabels=['Equal SOC','SOC imbalance','Hypothetical rails','Reduced load'],ylabel=label)
        ax.grid(axis='y',alpha=.2)
    fig.suptitle('Sensitivity scenarios: black x = nominal; blue = one-at-a-time cases (not confidence intervals)')
    fig.savefig(out/'sensitivity_scenarios.png',dpi=140);plt.close(fig)
    lines=['# Predeclared electrical simulation comparison','',
        '**Synthetic simulation, not experimental validation. No automatic ranking.** All voltage requirements are unconfigured in the supplied case. All engineering decisions remain insufficient evidence.','',
        '| Manual scenario | Max branch [A] | Min cell / terminal [V] | Mean delivered power [W] | Delivered [Wh] | R0 / rail / R1 loss [Wh] | >4.9 A [cell s] |',
        '|---|---:|---:|---:|---:|---:|---:|']
    for r in rows:
        if r['status']!='completed':lines.append(f"| {r['scenario']} | stopped: see run summary | | | | | |");continue
        lines.append(f"| {r['scenario']} | {r['maximum_branch_current_A']:.4f} | {r['minimum_cell_voltage_V']:.4f} / {r['minimum_terminal_voltage_V']:.4f} | {r['mean_delivered_power_W']:.3f} | {r['delivered_net_Wh']:.4f} | {r['cell_R0_loss_Wh']:.4f} / {r['rail_loss_Wh']:.4f} / {r['R1_loss_Wh']:.4f} | {r['above_4_9A_cell_seconds']:.2f} |")
    lines+=['','Cell seconds sum duration across cells; they are descriptive coverage flags, not safety limits.',
        'Every cell waveform remains an unsupported module transfer even where all amplitudes fall inside fitting or assessment ranges.',
        'Reduced load requests less service. Its voltage/loss differences must be read together with delivered current, power and energy.',
        'Reference source work and equivalent-RC storage are model bookkeeping, not measured chemical energy or efficiency.','',
        '[Sensitivity plot](sensitivity_scenarios.png), [matched sensitivity contrasts](sensitivity_contrasts.json), [time-step checks](software_verification.json).','']
    for name in manifest['scenarios']:lines.append(f'- {name}: [electrical](runs/{name}/electrical.png), [nodes/power](runs/{name}/nodes_and_power.png), [coverage and status](runs/{name}/summary.json).')
    (out/'COMPARISON.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(table[['scenario','maximum_branch_current_A','minimum_terminal_voltage_V','delivered_net_Wh','decision']].to_string(index=False))
    return table
