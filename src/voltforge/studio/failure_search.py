"""Finite, reproducible pressure tests of a saved experiment.

These cases do not prove a global failure boundary. A model coverage boundary is
different from a component operating limit or an application target violation.
"""
from copy import deepcopy


SIZING_CLAIM='Smallest qualifying design among the parallel arrangements tested'
SIZING_SCOPE='Nominal conditions for the saved load. The design study adds cell mismatch and sensitivity cases.'


def resize_parallel(graph,count):
    """Rebuild a parallel ladder at another size, keeping models, states and link assumptions."""
    from .network import template
    cells=graph['cells'];ids=[c['id'] for c in cells];n=len(ids);out=graph['output']
    problem=ValueError('Find the smallest design works on a simple parallel battery: each cell linked to the next, positive to positive and negative to negative.')
    links={}
    for w in graph['connections']:
        a,pole_a=w['a'].split(':');b,pole_b=w['b'].split(':')
        if pole_a!=pole_b or abs(ids.index(a)-ids.index(b))!=1:raise problem
        links[(min(ids.index(a),ids.index(b)),pole_a)]=w
    if set(links)!={(i,p) for i in range(n-1) for p in 'pn'}:raise problem
    if not n or out['positive']!=ids[0]+':p' or out['negative'] not in (ids[0]+':n',ids[-1]+':n'):raise problem
    opposite=n>1 and out['negative']==ids[-1]+':n'
    g=deepcopy(graph);kept=deepcopy(cells[:count])
    for k in range(n,count):
        clone=deepcopy(cells[-1]);clone.update(id=f'cell{k+1}',name=f'Cell {k+1}',x=180+(k%4)*210,y=210+(k//4)*260)
        kept.append(clone)
    g['cells']=kept;fresh=template('parallel',2)['connections'][0];wires=[]
    for i in range(count-1):
        for pole in 'pn':
            w=deepcopy(links.get((i,pole)) or links.get((n-2,pole)) or fresh)
            w.update(id=f'wire{len(wires)+1}',a=f'{kept[i]["id"]}:{pole}',b=f'{kept[i+1]["id"]}:{pole}');wires.append(w)
    g['connections']=wires
    g['output']=dict(positive=kept[0]['id']+':p',negative=kept[-1 if opposite else 0]['id']+':n')
    names={c['id'] for c in kept};th=g['thermal']
    th['contacts']=[c for c in th['contacts'] if c['a'] in names and c['b'] in names]
    if 'cell_parameters' in th:
        last=th['cell_parameters'].get(ids[-1])
        th['cell_parameters']={k:v for k,v in th['cell_parameters'].items() if k in names}
        for c in kept[n:]:
            if last:th['cell_parameters'][c['id']]=deepcopy(last)
    return g


def sizing_verdict(result,ready):
    """Keep refused, unsupported and incomplete cases apart from cases that qualify."""
    if result is None:return 'refused' if (ready or {}).get('violation') else 'unsupported'
    summary=result.summary;checks={c['metric']:c['status'] for c in summary['checks']}
    if result.stop:return 'unsupported' if result.stop['reason'] in ('charge_domain','temperature_domain') else 'failed'
    if 'exceeded' in checks.values() or not summary['assessment']['requested_demand_met']:return 'failed'
    if ('min_voltage_V' not in checks or any(s != 'within_target' for s in checks.values())
            or not summary['thermal_available'] or summary['verification'].get('first_law_closed') is not True
            or summary.get('operating_limit_coverage', {}).get('complete') is not True):return 'incomplete'
    return 'qualifies'


def smallest(cases):
    passing=[c for c in cases if c.get('sizing')=='qualifies']
    return min(passing,key=lambda c:c['cell_count'],default=None)


def scenarios(graph,settings,condition):
    if condition=='cell_count':
        resize_parallel(graph,1)
        return [dict(name=f'{k} cell'+('s' if k>1 else ''),factor=1.,ambient_offset=0.,extra_resistance=0.,cell_count=k) for k in range(1,min(16,max(4,len(graph['cells'])))+1)]
    specs=[dict(name='Saved baseline',factor=1.,ambient_offset=0.,extra_resistance=0.)]
    if condition=='load':
        specs += [dict(name=f'{x:g}× battery demand',factor=x,ambient_offset=0.,extra_resistance=0.) for x in (1.25,1.5,2.,3.)
                  if all(abs(p['current_A']*x)<=200 for p in settings['profile'])]
    elif condition=='temperature':
        specs += [dict(name=f'Room {x:g} °C warmer',factor=1.,ambient_offset=x,extra_resistance=0.) for x in (10.,20.,30.,40.) if settings['ambient_C']+x<=100]
    elif condition=='connection':
        if not graph['connections']:raise ValueError('Add an electrical connection before testing contact wear.')
        specs += [dict(name=f'First connection +{x:g} mΩ',factor=1.,ambient_offset=0.,extra_resistance=x) for x in (1.,3.,10.,30.) if graph['connections'][0]['resistance_mohm']+x<=1000]
    else:raise ValueError('Choose higher demand, a warmer room or a poorer connection.')
    if len(specs)<2:raise ValueError('The selected conditions already reach this editor’s input range. Choose another pressure test.')
    return specs


def inputs(graph,settings,spec):
    g=deepcopy(graph);s=deepcopy(settings)
    if spec.get('cell_count'):g=resize_parallel(g,spec['cell_count'])
    for p in s['profile']:p['current_A']*=spec['factor']
    s['ambient_C']+=spec['ambient_offset']
    if spec['extra_resistance']:
        from .conductors import add_contact_resistance
        add_contact_resistance(g['connections'][0],spec['extra_resistance'],'Declared contact-wear pressure test')
    return g,s


def outcome(graph,settings,result=None,preflight=None):
    if result is None:
        issue=(preflight or {}).get('violation',{})
        kind='component_limit' if issue else 'unsupported'
        return dict(kind=kind,label='Cell operating limit exceeded' if issue else 'Outside model support',
                    message=(preflight or {}).get('message','These inputs could not be calculated.'),
                    first_limit=dict(time_s=0.,**issue),affected_cells=[issue['cell']] if issue else [],sample_index=None)
    findings=[]
    units={'temperature_C':'°C','current_A':'A','min_voltage_V':'V','imbalance_pct':'%'}
    labels={'temperature_C':'Cell temperature','current_A':'Cell current','min_voltage_V':'Battery voltage','imbalance_pct':'Current difference'}
    for check in result.summary['checks']:
        if check['status']!='exceeded':continue
        metric=check['metric'];target=check['target']
        for index,row in enumerate(result.rows):
            cell=None
            if metric=='temperature_C':
                values=row['temperature_C'];position=max(range(len(values)),key=lambda i:values[i]);value=values[position];cell=graph['cells'][position]['id']
            elif metric=='current_A':
                values=[abs(v) for v in row['cell_current_A']];position=max(range(len(values)),key=lambda i:values[i]);value=values[position];cell=graph['cells'][position]['id']
            elif metric=='min_voltage_V':value=row['voltage_V']
            else:
                values=row['cell_current_A'];mean=sum(abs(v) for v in values)/len(values)
                if mean<=.01:continue
                value=100*(max(values)-min(values))/mean
            exceeded=value<target if metric=='min_voltage_V' else value>target
            if exceeded:
                findings.append(dict(kind='design_target',cell=cell,time_s=row['time_s'],value=value,target=target,unit=units[metric],metric=metric,sample_index=index,
                                     message=f'{labels[metric]} is {value:.3g} {units[metric]}, beyond the selected {target:g} {units[metric]} target.'))
                break
    control=result.summary.get('protection');service=result.summary.get('service',{})
    if control and control['actuated'] and service.get('unserved_demand_s',0)>0:
        event=control['event']
        index=next((i for i,r in enumerate(result.rows) if r['time_s']>=event['disconnect_time_s'] and r.get('external_disconnected')),len(result.rows)-1)
        findings.append(dict(kind='protection',cell=event['cell'],time_s=event['disconnect_time_s'],sample_index=index,
                             message=f'Virtual protection disconnected the external load; {service["unserved_demand_s"]:g} s of requested demand was not served.',
                             measured_value=event['measured_value'],true_value=event['true_value'],threshold=event['threshold'],unit=event['unit']))
    if result.stop:
        stop=result.stop;kind='model_boundary' if stop['reason'] in ('charge_domain','temperature_domain') else 'component_limit'
        findings.append(dict(kind=kind,**stop,sample_index=len(result.rows)-1))
    if findings:
        first=min(findings,key=lambda f:f['time_s']);kind=first['kind']
        return dict(kind=kind,label={'design_target':'Design target exceeded','model_boundary':'Model coverage reached','component_limit':'Cell operating limit reached','protection':'Protection left demand unserved'}[kind],
                    message=first['message'],first_limit=first,affected_cells=sorted({f['cell'] for f in findings if f.get('cell')}),sample_index=first['sample_index'],findings=findings)
    targeted=bool(result.summary['checks'])
    unavailable=(any(c['status'] in ('not_modeled','not_applicable','inconclusive') for c in result.summary['checks'])
                 or result.summary.get('operating_limit_coverage', {}).get('complete') is not True)
    return dict(kind='within_targets' if targeted and not unavailable else 'unassessed',
                label='Within selected model targets' if targeted and not unavailable else 'Calculated; targets incomplete',
                message='No selected target was exceeded in this calculated case.' if targeted and not unavailable else 'Check application targets and cell operating-limit coverage. Unknown or unmodeled limits are not passes.',
                first_limit=None,affected_cells=[],sample_index=len(result.rows)-1)
