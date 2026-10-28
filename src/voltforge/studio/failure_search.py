"""Finite, reproducible pressure tests of a saved experiment.

These cases do not prove a global failure boundary. A model coverage boundary is
different from a component operating limit or an application target violation.
"""
from copy import deepcopy


def scenarios(graph,settings,condition):
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
    unavailable=any(c['status'] in ('not_modeled','not_applicable','inconclusive') for c in result.summary['checks'])
    return dict(kind='within_targets' if targeted and not unavailable else 'unassessed',
                label='Within selected model targets' if targeted and not unavailable else 'Calculated; targets incomplete',
                message='No selected target was exceeded in this calculated case.' if targeted and not unavailable else 'Add design targets to judge this case. Unknown or unmodeled limits are not passes.',
                first_limit=None,affected_cells=[],sample_index=len(result.rows)-1)
