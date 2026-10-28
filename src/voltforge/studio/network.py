"""Modified nodal analysis for the circuit the engineer actually draws.

Currents are positive out of a cell's positive terminal. Resistive links and
explicit thermal contacts are separate graphs. No physical connection is
inferred from where a component happens to be drawn.
"""
from copy import deepcopy
from dataclasses import dataclass
from collections import OrderedDict
import hashlib
import json
import math
import re

import numpy as np
from scipy.linalg import lu_factor, lu_solve
from voltforge.models.coupling_v2 import VoltageReference, rc_interval, validate_profile
from voltforge.models.thermal_v1 import rc_propagator
from voltforge.models.cell_catalogue import ALL_KEYS, KIND as TEMPERATURE_MODEL_KIND

VERSION = 'studio.graph.1'
MODEL_KEYS = ('P7', 'P17', 'P19', 'P13')
ID = re.compile(r'^[a-zA-Z][a-zA-Z0-9_-]{0,47}$')


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def number(value, label, low=None, high=None):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f'{label} needs a finite number.')
    if low is not None and value < low or high is not None and value > high:
        raise ValueError(f'{label} must be between {low} and {high}.' if high is not None else f'{label} must be at least {low}.')
    return float(value)


def physics(graph):
    """Drawing positions and names do not invalidate an otherwise identical test."""
    g = deepcopy(graph)
    g.pop('name', None)
    for c in g['cells']:
        for k in ('x', 'y', 'name'):
            c.pop(k, None)
    for w in g['connections']:
        w.pop('name', None)
    return g


def template(kind='parallel', count=4, name=None):
    if kind not in ('parallel', 'series', 'mixed', 'blank'):
        raise ValueError('Choose parallel, series, mixed or blank.')
    if kind != 'blank':
        value=number(count,'Cell count',1,16)
        if value!=int(value):raise ValueError('Choose a whole number of cells.')
        count=int(value)
    else:count=0
    if kind == 'mixed' and count % 2:
        raise ValueError('Use an even number of cells for pairs in series.')
    g = dict(version=VERSION, name=name or ('New design' if not count else {'parallel':'Shared-load design', 'series':'Higher-voltage design', 'mixed':'Two-pair design'}[kind]),
             cells=[], connections=[], output={'positive':None, 'negative':None},
             thermal=dict(heat_capacity_J_K=69.25, ambient_conductance_W_K=0.148629,
                          wire_heat_fraction=0.5, contacts=[]))
    for i in range(count):
        g['cells'].append(dict(id=f'cell{i+1}', name=f'Cell {i+1}', model=MODEL_KEYS[i % 4],
                               x=180+(i % 4)*210, y=210+(i // 4)*260,
                               charge_pct=70., temperature_C=23., polarization_V=0.))
    def wire(a, b):
        g['connections'].append(dict(id=f'wire{len(g["connections"])+1}', a=a, b=b,
                                      resistance_mohm=1., source='User design assumption'))
    if count:
        g['output'] = dict(positive='cell1:p', negative=f'cell{count if kind == "series" else (2 if kind == "mixed" else 1)}:n')
    if kind == 'parallel':
        for i in range(1, count):
            for pole in ('p', 'n'):
                wire(f'cell{i}:{pole}', f'cell{i+1}:{pole}')
    elif kind == 'series':
        for i in range(1, count):
            wire(f'cell{i}:n', f'cell{i+1}:p')
    elif kind == 'mixed':
        for i in range(1, count, 2):
            wire(f'cell{i}:n', f'cell{i+1}:p')
        for i in range(1, count-2, 2):
            wire(f'cell{i}:p', f'cell{i+2}:p')
            wire(f'cell{i+1}:n', f'cell{i+3}:n')
    return g


def validate_graph(g, model_keys=None):
    if not isinstance(g, dict) or set(g)-{'output_leads'} != {'version','name','cells','connections','output','thermal'} or g['version'] != VERSION:
        raise ValueError('This design format is not supported.')
    if not isinstance(g['name'], str) or not 1 <= len(g['name'].strip()) <= 100:
        raise ValueError('Give the design a name of 1 to 100 characters.')
    if not isinstance(g['cells'], list) or len(g['cells']) > 16 or not isinstance(g['connections'], list) or len(g['connections']) > 80:
        raise ValueError('Use up to 16 cells and 80 connections in this studio.')
    ids, terminals = set(), set()
    for c in g['cells']:
        if not isinstance(c, dict) or set(c) != {'id','name','model','x','y','charge_pct','temperature_C','polarization_V'}:
            raise ValueError('A cell has missing or unsupported properties.')
        if not isinstance(c['id'], str) or not ID.fullmatch(c['id']) or c['id'] in ids:
            raise ValueError('Each cell needs a unique identity.')
        ids.add(c['id']); terminals.update((c['id']+':p', c['id']+':n'))
        if not isinstance(c['name'], str) or not 1 <= len(c['name'].strip()) <= 60 or c['model'] not in (model_keys if model_keys is not None else ALL_KEYS):
            raise ValueError('Choose a name and an available cell model.')
        number(c['x'], 'Horizontal position', 0, 3000); number(c['y'], 'Vertical position', 0, 2400)
        number(c['charge_pct'], 'Starting charge', 0, 100)
        number(c['temperature_C'], 'Starting temperature', -40, 100)
        number(c['polarization_V'], 'Initial relaxation voltage', -1, 1)
    wire_ids, pairs = set(), set()
    for w in g['connections']:
        if not isinstance(w, dict) or set(w)-{'conductor'} != {'id','a','b','resistance_mohm','source'}:
            raise ValueError('A connection has missing or unsupported properties.')
        if not isinstance(w['id'], str) or not ID.fullmatch(w['id']) or w['id'] in wire_ids or w['id'] in ids:
            raise ValueError('Each connection needs a unique identity.')
        wire_ids.add(w['id'])
        if w['a'] not in terminals or w['b'] not in terminals or w['a'] == w['b']:
            raise ValueError('Connect two different cell terminals.')
        pair = tuple(sorted((w['a'], w['b'])))
        if pair in pairs:
            raise ValueError('These terminals are already connected. Edit the existing connection.')
        pairs.add(pair)
        number(w['resistance_mohm'], 'Connection resistance', 0, 1000)
        from .conductors import validate_wire
        validate_wire(w)
        if not isinstance(w['source'], str) or not 1 <= len(w['source']) <= 500:
            raise ValueError('Record where the connection value came from.')
    if not isinstance(g['output'], dict) or set(g['output']) != {'positive','negative'} or any(v is not None and v not in terminals for v in g['output'].values()):
        raise ValueError('Choose existing cell terminals as the battery output.')
    leads=g.get('output_leads',{})
    if not isinstance(leads,dict) or set(leads)-{'positive','negative'}:
        raise ValueError('Output conductor routes must belong to the positive or negative battery output.')
    from .conductors import calculate
    for definition in leads.values():calculate(definition)
    th = g['thermal']
    if not isinstance(th, dict) or set(th)-{'cell_parameters'} != {'heat_capacity_J_K','ambient_conductance_W_K','wire_heat_fraction','contacts'}:
        raise ValueError('Unsupported heat-transfer settings.')
    number(th['heat_capacity_J_K'], 'Heat capacity', 1, 10000)
    number(th['ambient_conductance_W_K'], 'Cooling conductance', 0, 100)
    number(th['wire_heat_fraction'], 'Connection heat fraction', 0, 1)
    overrides=th.get('cell_parameters',{})
    if not isinstance(overrides,dict) or set(overrides)-ids:raise ValueError('Thermal properties must belong to existing cells.')
    for cell_id,parameters in overrides.items():
        if not isinstance(parameters,dict) or set(parameters)-{'heat_capacity_J_K','ambient_conductance_W_K'}:raise ValueError('Unsupported cell heat-transfer property.')
        for key,value in parameters.items():number(value,key,1 if key=='heat_capacity_J_K' else 0,10000 if key=='heat_capacity_J_K' else 100)
    if not isinstance(th['contacts'], list) or len(th['contacts']) > 120:
        raise ValueError('Too many thermal contacts.')
    pairs = set()
    for c in th['contacts']:
        if not isinstance(c, dict) or set(c) != {'a','b','conductance_W_K'} or c['a'] not in ids or c['b'] not in ids or c['a'] == c['b']:
            raise ValueError('A thermal contact must join two different cells.')
        pair = tuple(sorted((c['a'], c['b'])))
        if pair in pairs: raise ValueError('A thermal contact is duplicated.')
        pairs.add(pair); number(c['conductance_W_K'], 'Thermal contact conductance', 0, 100)
    return g


class Circuit:
    def __init__(self, graph, model_keys=None):
        validate_graph(graph,model_keys)
        self.graph = graph; self.cells = graph['cells']; self.wires = graph['connections']
        from .conductors import calculate
        self.output_resistance=sum(calculate(c)['resistance_mohm']/1000 for c in graph.get('output_leads',{}).values())
        if not self.cells: raise ValueError('Add a cell to start your battery.')
        out = graph['output']
        if not out['positive'] or not out['negative']:
            raise ValueError('Choose the positive and negative battery outputs. Select a terminal, then “Use as output”.')
        terminals = [c['id']+':'+p for c in self.cells for p in ('p','n')]
        parent = {t:t for t in terminals}
        def root(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]; x = parent[x]
            return x
        for w in self.wires:
            if w['resistance_mohm'] == 0: parent[root(w['a'])] = root(w['b'])
        roots = {t:root(t) for t in terminals}
        if roots[out['positive']] == roots[out['negative']]:
            raise ValueError('The battery outputs are shorted together. Remove the connection between them.')
        for c in self.cells:
            if roots[c['id']+':p'] == roots[c['id']+':n']:
                raise ValueError(f'{c["name"]} has a short circuit. Remove the link joining its two terminals.')
        edges = {r:set() for r in roots.values()}
        used = set(out.values())
        for w in self.wires:
            a,b = roots[w['a']], roots[w['b']]; edges[a].add(b); edges[b].add(a)
            used.update((w['a'],w['b']))
        for c in self.cells:
            a,b = roots[c['id']+':p'], roots[c['id']+':n']; edges[a].add(b); edges[b].add(a)
            if c['id']+':p' not in used or c['id']+':n' not in used:
                raise ValueError(f'Finish connecting both ends of {c["name"]}, or remove it before testing.')
        seen, stack = set(), [roots[out['negative']]]
        while stack:
            node = stack.pop()
            if node not in seen: seen.add(node); stack.extend(edges[node]-seen)
        if seen != set(edges): raise ValueError('Part of the circuit is disconnected. Connect it to the battery or remove it before testing.')
        ground = roots[out['negative']]
        nodes = sorted(set(roots.values())-{ground}); index = {v:i for i,v in enumerate(nodes)}
        self.roots, self.index, self.ground = roots, index, ground
        n, nc = len(nodes), len(self.cells)
        self.B = np.zeros((n,nc)); self.G = np.zeros((n,n)); self.port = np.zeros(n)
        self.port[index[roots[out['positive']]]] = -1
        for k,c in enumerate(self.cells):
            for pole,sgn in (('p',1),('n',-1)):
                r=roots[c['id']+':'+pole]
                if r != ground: self.B[index[r],k] += sgn
        self.W = np.zeros((len(self.wires),n)); self.conductance = np.zeros(len(self.wires))
        for k,w in enumerate(self.wires):
            a,b = roots[w['a']],roots[w['b']]
            for r,sgn in ((a,1),(b,-1)):
                if r != ground: self.W[k,index[r]] += sgn
            if w['resistance_mohm'] > 0:
                self.conductance[k] = 1000/w['resistance_mohm']
        self.G = self.W.T @ np.diag(self.conductance) @ self.W
        self.n = n
        self.factorizations = OrderedDict()

    def solve(self, emf, resistance, load):
        key=tuple(resistance)
        try:
            if key not in self.factorizations:
                matrix=np.block([[self.G,-self.B],[self.B.T,np.diag(resistance)]])
                self.factorizations[key]=lu_factor(matrix,check_finite=False)
                if len(self.factorizations) > 32:
                    self.factorizations.popitem(last=False)
            self.factorizations.move_to_end(key)
            answer=lu_solve(self.factorizations[key],np.r_[self.port*load,emf],check_finite=False)
        except np.linalg.LinAlgError: raise ValueError('This circuit cannot be solved. Check for disconnected terminals or a short circuit.') from None
        v, current = answer[:self.n], answer[self.n:]
        wire_i = (self.W@v)*self.conductance
        wire_loss = wire_i**2 * np.array([w['resistance_mohm']/1000 for w in self.wires])
        kcl = float(np.max(np.abs(self.G@v-self.B@current-self.port*load)))
        kvl = float(np.max(np.abs(self.B.T@v+resistance*current-emf)))
        internal_terminal = float(-self.port@v)
        terminal=internal_terminal-self.output_resistance*load
        output_loss=self.output_resistance*load**2
        residual = float(emf@current-terminal*load-np.dot(resistance,current**2)-wire_loss.sum()-output_loss)
        if not np.isfinite(answer).all() or kcl > 1e-7*max(1,abs(load),np.max(np.abs(current))) or kvl > 1e-8:
            raise ValueError('The circuit is numerically ill-conditioned. Check very small connection resistances.')
        return dict(current=current, voltage=self.B.T@v, terminal=terminal, wire_current=wire_i, wire_loss=wire_loss,
                    output_loss_W=output_loss,cell_side_voltage_V=internal_terminal,
                    kcl=kcl, kvl=kvl, power_residual=residual)


def readiness(graph, model_keys=None):
    try:
        Circuit(graph,model_keys)
        return dict(ready=True, message='Ready to test')
    except ValueError as exc:
        return dict(ready=False, message=str(exc))


def settings_default():
    return dict(profile=[dict(start_s=0.,end_s=600.,current_A=12.)], ambient_C=23., dt_s=0.5,
                limits=dict(temperature_C=None,current_A=None,min_voltage_V=None,imbalance_pct=None))


def integration_grid(s):
    """Include every requested-load, sensor-sampling and delayed-action event."""
    from .protection import VirtualProtection
    duration=s['profile'][-1]['end_s']
    controller=VirtualProtection(s.get('protection'),duration)
    return np.unique(np.round(np.r_[np.arange(0,duration,s['dt_s']),
                                   [p['end_s'] for p in s['profile']],controller.grid_times(),duration],10))


def validate_settings(s):
    if not isinstance(s, dict) or set(s)-{'profile','ambient_C','dt_s','limits','case','protection'} or not {'profile','ambient_C','dt_s','limits'}<=set(s):
        raise ValueError('Unsupported test settings.')
    if 'case' in s:
        from .cases import validate_case
        validate_case(s['case'])
    if not isinstance(s['profile'],list) or not 1 <= len(s['profile']) <= 48 or any(not isinstance(p,dict) or set(p) != {'start_s','end_s','current_A'} for p in s['profile']):
        raise ValueError('Use between 1 and 48 load intervals.')
    for p in s['profile']:
        for k in ('start_s','end_s','current_A'): number(p[k],k)
        number(p['current_A'], 'Battery current', -200, 200)
    duration=validate_profile(s['profile'])
    from .protection import validate as validate_protection
    validate_protection(s.get('protection'),duration)
    number(duration,'Duration',.1,86400); number(s['dt_s'],'Solver step',.01,10)
    if duration/s['dt_s'] > 50000: raise ValueError('For this duration, increase the solver step to keep the test below 50,000 samples.')
    if len(integration_grid(s))>50001:
        raise ValueError('Increase the solver step or sensor sample interval to keep all solver and control events below 50,000 intervals.')
    number(s['ambient_C'],'Room temperature',-40,100)
    lim=s['limits']
    if not isinstance(lim,dict) or set(lim) != {'temperature_C','current_A','min_voltage_V','imbalance_pct'}:
        raise ValueError('Unsupported test targets.')
    for k,v in lim.items():
        if v is not None: number(v,k,-40 if k=='temperature_C' else 0,1000)
    return duration


@dataclass
class Result:
    rows: list
    summary: dict
    status: str
    stop: dict | None


def simulate(graph, settings, model_bank):
    from .temperature_engine import simulate as simulate_temperature
    return simulate_temperature(graph, settings, model_bank)


def simulate_legacy_nominal(graph, settings, model_bank):
    """Historical numerical reference, retained for explicit regression checks."""
    if graph.get('output_leads') or settings.get('protection'):
        raise ValueError('Use the current engine for physical output routes and virtual protection.')
    circuit=Circuit(graph); duration=validate_settings(settings)
    cells=graph['cells']; n=len(cells); models=[model_bank[c['model']] for c in cells]
    refs=[VoltageReference(m) for m in models]
    q=np.array([m['capacity_Ah'] for m in models]); r0=np.array([m['parameters_ohm'][0] for m in models])
    r1=np.array([m['parameters_ohm'][1] for m in models]); tau=np.array([m['tau_s'] for m in models]); cap=tau/r1
    if not np.isfinite(np.r_[q,r0,r1,tau]).all() or np.any(np.r_[q,r0,r1,tau] <= 0): raise ValueError('The cell model contains invalid parameters.')
    z=np.array([c['charge_pct']/100 for c in cells]); vp=np.array([c['polarization_V'] for c in cells])
    temperature=np.array([c['temperature_C'] for c in cells]); z0=z.copy(); t0=temperature.copy()
    bad=[cells[k]['name'] for k in range(n) if not refs[k].supported(z[k])]
    if bad: raise ValueError('Starting charge is outside the available model data for '+', '.join(bad)+'. Use a charge level between 15% and 95%.')
    # This is an enforced applicability gate, not a banner over an unsupported prediction.
    if not 22 <= settings['ambient_C'] <= 28 or np.any((temperature < 22)|(temperature > 28)):
        raise ValueError('These cell models support 22–28 °C. Choose a temperature in that range. Wider temperature tests need a temperature-calibrated model.')
    th=graph['thermal']; overrides=th.get('cell_parameters',{})
    C=np.array([overrides.get(c['id'],{}).get('heat_capacity_J_K',th['heat_capacity_J_K']) for c in cells])
    G=np.array([overrides.get(c['id'],{}).get('ambient_conductance_W_K',th['ambient_conductance_W_K']) for c in cells])
    K=np.diag(G); ids={c['id']:i for i,c in enumerate(cells)}
    for c in th['contacts']:
        a,b=ids[c['a']],ids[c['b']]; g=c['conductance_W_K']
        K[a,a]+=g; K[b,b]+=g; K[a,b]-=g; K[b,a]-=g
    rate=-K/C[:,None]; fraction=th['wire_heat_fraction']; heat_share=np.zeros((n,len(graph['connections'])))
    for k,w in enumerate(graph['connections']):
        heat_share[ids[w['a'].split(':')[0]],k]+=fraction/2
        heat_share[ids[w['b'].split(':')[0]],k]+=fraction/2
    profile=settings['profile']; starts=np.array([p['start_s'] for p in profile]); dt=settings['dt_s']
    grid=np.unique(np.round(np.r_[np.arange(0,duration,dt),[p['end_s'] for p in profile],duration],10))
    energy=np.zeros(6); charges=np.zeros(n); generated=exchanged=0.; cache={}; rows=[]; stop=None
    initial_storage=.5*np.dot(cap,vp**2)
    for j,t in enumerate(grid):
        load=profile[min(np.searchsorted(starts,t,side='right')-1,len(profile)-1)]['current_A']
        u=np.array([ref.value(z[k]) for k,ref in enumerate(refs)])
        s=circuit.solve(u-vp,r0,load); current=s['current']; p=s['terminal']*load
        storage=.5*np.dot(cap,vp**2); pr1=np.sum(vp**2/r1); stored_rate=np.sum(vp*(current-vp/r1))
        row=dict(time_s=float(t),current_A=float(load),voltage_V=s['terminal'],power_W=float(p),
                 cell_current_A=current.tolist(),cell_voltage_V=s['voltage'].tolist(),charge_pct=(100*z).tolist(),
                 temperature_C=temperature.tolist(),wire_current_A=[float(v) if w['resistance_mohm']>0 else None for v,w in zip(s['wire_current'],graph['connections'])],wire_loss_W=s['wire_loss'].tolist(),
                 kcl_residual_A=s['kcl'],kvl_residual_V=s['kvl'],
                 power_residual_W=float(u@current-p-np.dot(r0,current**2)-s['wire_loss'].sum()-pr1-stored_rate),
                 cell_charge_residual_As=(3600*q*(z0-z)-charges).tolist(),
                 source_energy_Wh=float(energy[0]/3600),delivered_energy_Wh=float(energy[1]/3600),
                 delivered_positive_Wh=float(energy[4]/3600),received_energy_Wh=float(energy[5]/3600),
                 loss_energy_Wh=float((energy[2]+energy[3])/3600),
                 energy_residual_Wh=float((energy[0]-energy[1]-energy[2]-energy[3]-(storage-initial_storage))/3600),
                 thermal_residual_J=float(np.dot(C,temperature-t0)-(generated-exchanged)))
        rows.append(row)
        if j==len(grid)-1: break
        h=float(grid[j+1]-t); next_z=z-current*h/(3600*q)
        if any(not refs[k].supported(next_z[k]) for k in range(n)):
            stop=dict(reason='charge_domain',time_s=float(t),message='A cell reached the end of its measured charge range. Shorten the test, lower the load, or change its starting charge.')
            break
        end_vp,r1energy,_=rc_interval(vp,current,r1,tau,h)
        b=r1*current; d=vp-b
        const=(r0*current**2+heat_share@s['wire_loss']+b*b/r1+G*settings['ambient_C'])/C
        f1=(2*b*d/r1)/C; f2=(d*d/r1)/C
        if h not in cache: cache[h]=rc_propagator(rate,tau,h)
        propagated=cache[h]@np.r_[temperature,np.zeros(n),const,f1,f2]
        next_temperature=propagated[:n]
        if np.any((next_temperature<22)|(next_temperature>28)):
            stop=dict(reason='temperature_domain',time_s=float(t),message='A cell reached the temperature range supported by its model. Use a lighter load, shorter test or a temperature-calibrated model.')
            break
        end_u=np.array([ref.value(next_z[k]) for k,ref in enumerate(refs)])
        end=circuit.solve(end_u-end_vp,r0,load)
        energy[0]+=sum(3600*q[k]*(refs[k].primitive(z[k])-refs[k].primitive(next_z[k])) for k in range(n))
        energy[1]+=.5*(p+end['terminal']*load)*h
        end_power=end['terminal']*load
        energy[4]+=.5*(max(p,0)+max(end_power,0))*h
        energy[5]+=.5*(max(-p,0)+max(-end_power,0))*h
        energy[2]+=(np.dot(r0,current**2)+s['wire_loss'].sum())*h
        energy[3]+=r1energy.sum()
        generated+=(np.dot(r0,current**2)+(heat_share@s['wire_loss']).sum())*h+r1energy.sum()
        exchanged+=float(G@(propagated[n:]-h*settings['ambient_C']))
        charges+=current*h; z=next_z; vp=end_vp; temperature=next_temperature
    summary=summarize(rows,graph,settings,completed=stop is None)
    return Result(rows,summary,'stopped' if stop else 'completed',stop)


def summarize(rows,graph,settings,*,completed=True,service_met=True):
    from .cases import case_record
    t=np.array([r['time_s'] for r in rows]); ii=np.array([r['cell_current_A'] for r in rows])
    thermal_available=all(v is not None for r in rows for v in r['temperature_C'])
    tt=np.array([r['temperature_C'] for r in rows],float) if thermal_available else None
    voltage=np.array([r['voltage_V'] for r in rows]); load=np.array([r['current_A'] for r in rows])
    hot=np.unravel_index(np.argmax(tt),tt.shape) if thermal_available else None
    peak=np.unravel_index(np.argmax(np.abs(ii)),ii.shape)
    # Only comparable for parallel branches. Never label a series circuit as imbalanced.
    all_same_ends = all(w['a'].split(':')[1] == w['b'].split(':')[1] for w in graph['connections'])
    mean=np.mean(np.abs(ii),axis=1); spread=np.ptp(ii,axis=1)
    imbalance=100*spread/np.maximum(mean,1e-12)
    imax=float(np.max(imbalance[mean>0.01])) if all_same_ends and np.any(mean>0.01) and len(graph['cells'])>1 else None
    metrics=dict(peak_temperature_C=float(tt[hot]) if hot else None,warmest_cell=graph['cells'][hot[1]]['id'] if hot else None,warmest_time_s=float(t[hot[0]]) if hot else None,
                 peak_cell_current_A=float(abs(ii[peak])),busiest_cell=graph['cells'][peak[1]]['id'],
                 minimum_voltage_V=float(voltage.min()),final_voltage_V=float(voltage[-1]),
                 delivered_energy_Wh=rows[-1]['delivered_positive_Wh'],received_energy_Wh=rows[-1]['received_energy_Wh'],
                 net_energy_Wh=rows[-1]['delivered_energy_Wh'],duration_s=float(t[-1]),
                 maximum_temperature_spread_C=float(np.ptp(tt,axis=1).max()) if thermal_available else None,imbalance_pct=imax,
                 current_gap_A=float(spread.max()) if all_same_ends else None)
    checks=[]
    for key,value in [('temperature_C',metrics['peak_temperature_C']),('current_A',metrics['peak_cell_current_A']),('min_voltage_V',metrics['minimum_voltage_V']),('imbalance_pct',imax)]:
        target=settings['limits'][key]
        if target is None: continue
        violation=value is not None and (value<target if key=='min_voltage_V' else value>target)
        checks.append(dict(metric=key,value=value,target=target,status=('not_modeled' if key=='temperature_C' else 'not_applicable') if value is None else ('exceeded' if violation else ('within_target' if completed and service_met else 'inconclusive'))))
    names={c['id']:c['name'] for c in graph['cells']}
    insights=[f'{names[metrics["warmest_cell"]]} is warmest at {metrics["peak_temperature_C"]:.1f} °C.' if thermal_available else 'Temperature is not modeled: this is an electrical estimate at the starting cell temperatures.',
              f'{names[metrics["busiest_cell"]]} carries the largest current: {metrics["peak_cell_current_A"]:.2f} A.']
    if imax is not None: insights.append(f'The largest difference between cells is {metrics["current_gap_A"]:.2f} A. Lower-resistance paths can carry more of the load.')
    else: insights.append(f'Battery voltage ends at {metrics["final_voltage_V"]:.2f} V for this connection layout.')
    verification=dict(max_kcl_A=max(abs(r['kcl_residual_A']) for r in rows),max_kvl_V=max(abs(r['kvl_residual_V']) for r in rows),
                      max_power_residual_W=max(abs(r['power_residual_W']) for r in rows),
                      max_cell_charge_residual_As=max(max(abs(v) for v in r['cell_charge_residual_As']) for r in rows),
                      final_energy_residual_Wh=rows[-1]['energy_residual_Wh'],max_thermal_residual_J=max(abs(r['thermal_residual_J']) for r in rows) if thermal_available else None)
    return dict(metrics=metrics,checks=checks,insights=insights,verification=verification,case=case_record(graph,settings),
                coverage=dict(requested_duration_s=float(settings['profile'][-1]['end_s']),completed_duration_s=float(t[-1]),complete=bool(completed)),
                assessment=dict(execution='completed' if completed else 'stopped',
                                target_basis='Calculated samples, interval endpoints and both sides of load events',
                                requested_demand_met=bool(service_met),
                                physical_clearance=False),
                thermal_available=thermal_available,
                classification='simulation',model='Measured-data fitted electrical cells; declared lumped heat-transfer network',
                temperature_range_C=[22,28],experimental_validation=False)
