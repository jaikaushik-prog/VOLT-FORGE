"""Two real complex designs for the slide. Built through the product's own Studio API."""
import json
from pathlib import Path
from voltforge.project import Project
from voltforge.studio.store import Studio
from voltforge.studio.network import template, settings_default
from voltforge.studio.loads import apply_mission, build_mission

path=Path('workspace/demo');Project.create_reference(path);st=Studio(path)

def module(name,parallel,offset=0.):
    """Two parallel banks in series, with several series ties and unequal link resistance."""
    g=template('blank',name=name)
    step=1320/parallel;count=2*parallel
    for row in range(2):
        for i in range(parallel):
            k=row*parallel+i
            g['cells'].append(dict(id=f'cell{k+1}',name=f'Cell {k+1}',model='LG_M50T_ECN',x=110+i*step,y=190+row*330,
                                   charge_pct=70.,temperature_C=23.,polarization_V=0.))
    def wire(a,b,mohm):
        g['connections'].append(dict(id=f'wire{len(g["connections"])+1}',a=a,b=b,resistance_mohm=round(mohm,2),source='Declared design assumption'))
    for row in range(2):
        for i in range(parallel-1):
            a,b=row*parallel+i+1,row*parallel+i+2
            base=.8+.15*i+offset
            wire(f'cell{a}:p',f'cell{b}:p',base)
            wire(f'cell{a}:n',f'cell{b}:n',base+.2)
    for i in range(parallel):
        wire(f'cell{i+1}:n',f'cell{parallel+i+1}:p',.6+.1*(i%3))
    g['output']=dict(positive='cell1:p',negative=f'cell{count}:n')
    return g

def create(graph,current):
    s=settings_default();s['profile']=[dict(start_s=0.,end_s=600.,current_A=current)]
    s['limits']['min_voltage_V']=6.6
    doc=st.create_from_graph(graph,s,origin=dict(kind='template',template='demo'))
    print(doc['graph']['name'],len(graph['cells']),'cells',len(graph['connections']),'links',doc['readiness']['message'],doc['readiness'].get('warnings'))
    return doc

a=create(module('16-cell backup module',8),16.);b=create(module('12-cell backup module',6,.1),16.)
ta=st.run(a['id'],a['version'],title='16 A for 10 min');tb=st.run(b['id'],b['version'],title='16 A for 10 min')
for t in (ta,tb):
    m=t['summary']['metrics'];print(t['design_name'],t['status'],round(m['minimum_voltage_V'],2),round(m['peak_cell_current_A'],2),round(m['peak_temperature_C'],1),t['parts']['subtotals'],t['summary']['design_warnings'])
c=st.compare([ta['id'],tb['id']]);print('same conditions',c['identical_test_conditions'],len(c['design_changes']))
json.dump(dict(a=a['id'],b=b['id'],ta=ta['id'],tb=tb['id']),open('tmp/demo_ids.json','w'))
