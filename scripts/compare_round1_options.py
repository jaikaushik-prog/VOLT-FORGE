"""Reproducible development study: physical links, route costs and paired scenarios.

Uses existing fitted parameters only. Does not open raw or reserved observations.
Every result is saved through the production Studio transaction/replay path.
"""
from copy import deepcopy
import argparse
import csv
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from voltforge.project.service import Project
from voltforge.studio.store import Studio
from voltforge.studio.network import template,settings_default,digest
from voltforge.studio.cases import BENCHMARK
from voltforge.studio.conductors import copper_reference,apply


def make_inputs(protocol,option,scenario):
    mission=protocol['mission'];graph=template('parallel',4,option['name'])
    settings=settings_default();settings.update(profile=[dict(start_s=0.,end_s=mission['duration_s'],current_A=mission['current_A'])],
                                                ambient_C=mission['ambient_C'],dt_s=mission['dt_s'],case=deepcopy(BENCHMARK))
    settings['limits']['min_voltage_V']=mission['minimum_output_voltage_V']
    for cell in graph['cells']:
        cell.update(charge_pct=mission['initial_charge_pct'],temperature_C=mission['initial_temperature_C'])
    for wire in graph['connections']:
        c=copper_reference();c.update(protocol['link_dimensions'])
        c['assumption_source']=protocol['physical_assumptions']
        if option['key']=='thicker':c['thickness_mm']*=2
        apply(wire,c)
    graph['output_leads']={}
    for pole in ('positive','negative'):
        c=copper_reference();c.update(protocol['output_route']);c['assumption_source']=protocol['physical_assumptions']
        graph['output_leads'][pole]=c
    if option['key']=='opposite':
        graph['output']['negative']='cell4:n';graph['output_leads']['negative']['length_mm']=140.
    kind=scenario['kind']
    if kind=='initial_charge':
        for index,cell in enumerate(graph['cells']):
            if scenario['cell_index'] is None or index==scenario['cell_index']:cell['charge_pct']+=scenario['delta_pp']
    elif kind in ('thermal_pair','cooling'):
        graph['thermal']['ambient_conductance_W_K']*=scenario['factor']
        if kind=='thermal_pair':graph['thermal']['heat_capacity_J_K']*=scenario['factor']
    elif kind=='contact':
        for wire in graph['connections']:
            c=wire['conductor'];c['contact_mohm']*=scenario['factor'];apply(wire,c)
        for c in graph['output_leads'].values():c['contact_mohm']*=scenario['factor']
    elif kind=='ambient':settings['ambient_C']+=scenario['delta_C']
    elif kind=='step':settings['dt_s']*=scenario['factor']
    elif kind!='nominal':raise ValueError('Unknown comparison scenario.')
    return graph,settings


def analyze(protocol,records):
    by={(r['scenario'],r['option']):r for r in records};baseline='baseline'
    metrics=list(protocol['decision']['numerical_resolution_budgets'])+['conductor_mass_g']
    paired=[]
    for scenario in protocol['scenarios']:
        base=by[scenario['key'],baseline]
        for option in protocol['options'][1:]:
            other=by[scenario['key'],option['key']]
            paired.append(dict(scenario=scenario['key'],option=option['key'],
                equal_requested_duty=base['settings']['profile']==other['settings']['profile'],
                complete_service=all(r['status']=='completed' and r['summary']['assessment']['requested_demand_met'] for r in (base,other)),
                both_within_declared_targets=all(r['summary']['checks'] and all(c['status']=='within_target' for c in r['summary']['checks']) for r in (base,other)),
                delta={k:other['summary']['metrics'][k]-base['summary']['metrics'][k] for k in metrics
                       if base['summary']['metrics'].get(k) is not None and other['summary']['metrics'].get(k) is not None}))
    reversals=[]
    for metric in ('peak_cell_current_A','peak_temperature_C'):
        nominal=by['nominal','thicker']['summary']['metrics'][metric]-by['nominal','opposite']['summary']['metrics'][metric]
        for scenario in protocol['scenarios']:
            a=by[scenario['key'],'thicker'];b=by[scenario['key'],'opposite']
            delta=a['summary']['metrics'][metric]-b['summary']['metrics'][metric]
            if a['status']==b['status']=='completed' and nominal*delta<0:
                reversals.append(dict(metric=metric,scenario=scenario['key'],nominal_thicker_minus_opposite=nominal,scenario_thicker_minus_opposite=delta))
    convergence=[]
    for option in protocol['options']:
        original=by['nominal',option['key']]['summary']['metrics'];refined=by['quarter_step',option['key']]['summary']['metrics']
        for metric,budget in protocol['decision']['numerical_resolution_budgets'].items():
            error=abs(refined[metric]-original[metric])
            convergence.append(dict(option=option['key'],metric=metric,nominal_step_to_quarter_step_difference=error,
                                    comparison_resolution=budget,within_declared_numerical_budget=error<=budget))
    return dict(paired_changes=paired,ordering_reversals=reversals,nominal_step_refinement=convergence,
                empirical_validation=False,robust_physical_winner=None,
                conclusion='Choice depends on preparation, conductor/routing assumptions and the priority between cell stress, energy and material. Review the recorded paired cases; measured model and fixture accuracy are still required for a physical recommendation.')


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--protocol',type=Path,default=ROOT/'configs/round1_comparison_protocol_v1.json')
    args=parser.parse_args();out=args.out.resolve()
    if out.exists() and any(out.iterdir()):raise SystemExit('Choose a new empty output directory so existing evidence stays intact.')
    out.mkdir(parents=True,exist_ok=True);raw=args.protocol.read_bytes();protocol=json.loads(raw)
    if protocol['version']!='voltforge.round1-comparison/1':raise SystemExit('Unsupported comparison protocol.')
    (out/'protocol.json').write_bytes(raw)
    Project.create_reference(out/'workspace');studio=Studio(out/'workspace')
    manifest=dict(protocol_sha256=hashlib.sha256(raw).hexdigest(),driver_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  software_hash=studio.software_hash,classification=protocol['status'],raw_observations_accessed=False)
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2))
    records=[];table=[]
    for scenario in protocol['scenarios']:
        for option in protocol['options']:
            graph,settings=make_inputs(protocol,option,scenario)
            doc=studio.create_from_graph(graph,settings,origin=dict(kind='declared_three_option_study',protocol_sha256=manifest['protocol_sha256'],
                option=option['key'],intervention=option['intervention'],scenario=scenario))
            record=studio.run(doc['id'],doc['version'],title=scenario['name'])
            records.append(dict(option=option['key'],scenario=scenario['key'],**record))
            row=dict(scenario=scenario['name'],design=option['name'],status=record['status'],**record['summary']['metrics'])
            table.append(row)
            if scenario['kind']=='nominal':(out/(option['key']+'.zip')).write_bytes(studio.export(record['id']))
            (out/'progress.json').write_text(json.dumps(dict(completed=len(records),total=len(protocol['scenarios'])*len(protocol['options'])),indent=2))
            print(f'{len(records)}/{len(protocol["scenarios"])*len(protocol["options"])} {scenario["key"]}: {option["key"]} {record["status"]}',flush=True)
    analysis=analyze(protocol,records)
    (out/'comparison.json').write_text(json.dumps(dict(manifest=manifest,analysis=analysis,
         experiments=[dict(option=r['option'],scenario=r['scenario'],id=r['id'],payload_hash=r['payload_hash'],
         graph=r['graph'],settings=r['settings'],model_hash=r['model_hash'],software_hash=r['software_hash'],summary=r['summary'],status=r['status'],stop=r['stop']) for r in records]),indent=2,allow_nan=False))
    with (out/'comparison.csv').open('w') as f:
        writer=csv.DictWriter(f,fieldnames=table[0]);writer.writeheader();writer.writerows(table)
    lines=['# Three-option development comparison','',protocol['scope'],'',protocol['physical_assumptions'],'',
           '| Design | Peak cell current (A) | Peak temperature (°C) | Delivered energy (Wh) | Specified conductor mass (g) |',
           '| --- | ---: | ---: | ---: | ---: |']
    for row in table[:3]:lines.append(f'| {row["design"]} | {row["peak_cell_current_A"]:.4f} | {row["peak_temperature_C"]:.3f} | {row["delivered_energy_Wh"]:.5f} | {row["conductor_mass_g"]:.4f} |')
    lines+=['',analysis['conclusion'],'',f'{len(analysis["ordering_reversals"])} peak-current/temperature ordering reversals were observed across the declared scenarios.',
            '',protocol['scenario_basis'],'',protocol['decision']['budget_meaning'],'',
            'Open the three ZIP reports or reproduce them with their captured source and model files. All scenario records are in the isolated workspace. This study establishes conditional numerical comparisons, not measured hardware benefits.']
    (out/'READ_ME.md').write_text('\n'.join(lines)+'\n')


if __name__=='__main__':main()
