"""Additive studio documents. The earlier project and all of its results stay intact."""
from copy import deepcopy
from datetime import datetime, timezone
import csv
import io
import fcntl
import json
import os
from pathlib import Path
import secrets
import threading
import zipfile

from voltforge.project.service import Project
from .network import (MODEL_KEYS, digest, physics, readiness, settings_default,
                      simulate, template, validate_graph, validate_settings)


def utc():
    return datetime.now(timezone.utc).isoformat()


def write(path, data):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_name(path.name+'.'+secrets.token_hex(6)+'.tmp')
    try:
        with tmp.open('x') as f:
            json.dump(data,f,indent=2,allow_nan=False); f.flush(); os.fsync(f.fileno())
        os.replace(tmp,path)
    finally:
        if tmp.exists(): tmp.unlink()


def read(path):
    return json.loads(Path(path).read_text())


class FileLock:
    """Reentrant thread lock plus an OS advisory lock for another local editor process."""
    def __init__(self,path):
        self.path=path;self.guard=threading.RLock();self.depth=0;self.handle=None

    def __enter__(self):
        self.guard.acquire()
        try:
            if not self.depth:
                self.path.parent.mkdir(parents=True,exist_ok=True)
                self.handle=self.path.open('a+')
                fcntl.flock(self.handle,fcntl.LOCK_EX)
            self.depth+=1
        except BaseException:
            self.guard.release();raise
        return self

    def __exit__(self,*_):
        self.depth-=1
        if not self.depth:
            fcntl.flock(self.handle,fcntl.LOCK_UN);self.handle.close();self.handle=None
        self.guard.release()


class Studio:
    def __init__(self, project):
        self.legacy=Project(project); self.root=Path(project)/'studio'; self.lock=FileLock(self.root/'write.lock')
        self.index_path=self.root/'index.json'
        self.base, _=self.legacy._inputs(self.legacy._state())
        self.models=dict(zip(MODEL_KEYS,self.base['models']))
        self.model_hash=digest(self.models)
        self.software_hash=self._software_hash()
        self._ensure()

    @staticmethod
    def _software_hash():
        src=Path(__file__).resolve().parents[1]
        paths=[p for d in ('studio','models') for p in (src/d).glob('*.py')]
        return digest({str(p.relative_to(src)):__import__('hashlib').sha256(p.read_bytes()).hexdigest() for p in sorted(paths)})

    def _ensure(self):
        with self.lock:
            if self.index_path.exists(): return
            index=dict(version=1,documents={},tests={})
            # Import configurations only. No rewriting, reinterpreting or relabelling old results.
            state=self.legacy._state()
            for i,(vid,variant) in enumerate(state['variants'].items()):
                _,record=self.legacy._revision(state,vid); old=record['design']
                name=variant['name']
                if name=='Reference A0': name='Original four-cell design'
                elif name.startswith('case_'): name='Connection experiment '+str(i)
                g=template('parallel',4,name)
                for k,c in enumerate(g['cells'],1):
                    previous=old['cells'][f'cell_{k}']; c['charge_pct']=100*previous['initial_soc']['value']
                    c['polarization_V']=previous['initial_polarization']['value']
                scenario=old['scenario']
                settings=settings_default()
                settings['profile']=deepcopy(scenario['load_profile'])
                settings['ambient_C']=scenario['temperature']['assumed_ambient_C']
                for c,v in zip(g['cells'],scenario['temperature']['assumed_surface_C']): c['temperature_C']=v
                # Legacy order p1,n1,p2,n2,p3,n3 matches the editable graph template.
                for k,w in enumerate(g['connections']):
                    pole='p' if k%2==0 else 'n'; j=k//2+1
                    w['resistance_mohm']=1000*old['connections'][f'rail_{pole}_{j}']['resistance']['value']
                settings['dt_s']=self.base['dt_s']
                thermal=old.get('thermal')
                if thermal:
                    for source,target in [('heat_capacity_J_per_K','heat_capacity_J_K'),('ambient_conductance_W_per_K','ambient_conductance_W_K')]:
                        values=thermal[source]['value']
                        g['thermal'][target]=values[0]
                        if len(set(values))>1:
                            for k,value in enumerate(values):g['thermal'].setdefault('cell_parameters',{}).setdefault(f'cell{k+1}',{})[target]=value
                    g['thermal']['wire_heat_fraction']=thermal['rail_heat_to_cells_fraction']['value']
                    g['thermal']['contacts']=[dict(a=f'cell{k+1}',b=f'cell{k+2}',conductance_W_K=v) for k,v in enumerate(thermal['neighbour_conductance_W_per_K']['value']) if v]
                requirements=old.get('engineering_requirements',{})
                for source,target in [('peak_branch_current_A','current_A'),('peak_cell_temperature_C','temperature_C'),('current_imbalance_pct','imbalance_pct')]:
                    if requirements.get(source,{}).get('documented_source'):settings['limits'][target]=requirements[source]['limit']
                requirements=old.get('voltage_requirement',{})
                if requirements.get('documented_source'):settings['limits']['min_voltage_V']=requirements.get('minimum_terminal_voltage_V')
                doc=self._document(g,settings,origin=dict(kind='previous_project',variant=vid,revision=state['variants'][vid]['revision_id'],
                                    original_design=deepcopy(old)))
                write(self.root/'documents'/f'{doc["id"]}.json',doc)
                index['documents'][doc['id']]=self._brief(doc)
            write(self.index_path,index)

    def _document(self, graph, settings=None, origin=None):
        return dict(id='design_'+secrets.token_hex(8),graph=graph,settings=settings or settings_default(),
                    version=1,created_utc=utc(),updated_utc=utc(),origin=origin,tests=[])

    @staticmethod
    def _brief(doc):
        return dict(id=doc['id'],name=doc['graph']['name'],cells=len(doc['graph']['cells']),
                    updated_utc=doc['updated_utc'],tests=len(doc['tests']),origin=doc['origin'])

    def _doc(self, design_id):
        if not isinstance(design_id,str) or design_id not in read(self.index_path)['documents']:
            raise ValueError('That design could not be found. Return to your designs and open it again.')
        return read(self.root/'documents'/f'{design_id}.json')

    def _signature(self, graph, settings):
        return digest(dict(graph=physics(graph),settings=settings,models=self.model_hash,software=self.software_hash))

    def document(self, design_id):
        with self.lock:
            doc=self._doc(design_id)
            signature=self._signature(doc['graph'],doc['settings'])
            tests=[]
            index=read(self.index_path)
            for tid in reversed(doc['tests']):
                brief=deepcopy(index['tests'][tid]); brief['current']=brief['signature']==signature
                tests.append(brief)
            return dict(**doc,readiness=readiness(doc['graph']),history=tests)

    def catalog(self):
        with self.lock:
            index=read(self.index_path)
            return dict(designs=sorted(index['documents'].values(),key=lambda x:x['updated_utc'],reverse=True),
                        library=[dict(key=k,name=f'LG M50T · sample {i+1}',capacity_Ah=m['capacity_Ah'],
                                      resistance_mohm=1000*m['parameters_ohm'][0],minimum_charge_pct=100*min(r['soc'] for r in m['reference']['rest']),
                                      source='Piombo et al., parallel-connected module experimental campaign, v2',
                                      source_url='https://data.mendeley.com/datasets/zh58byr53c/2',classification='Fitted from measured cell data') for i,(k,m) in enumerate(self.models.items())],
                        science=dict(status='Simulation estimates',temperature_range_C=[22,28],
                                     electrical='Each cell has a measured-data fitted voltage, resistance and relaxation model.',
                                     thermal='Heat is calculated from electrical losses, explicit cell contacts and declared cooling settings.',
                                     calibration='Temperature-dependent electrical calibration and independent module validation are required before engineering sign-off.'))

    def create(self, kind='parallel', count=4, name=None, copy_id=None):
        with self.lock:
            if copy_id:
                old=self._doc(copy_id); graph=deepcopy(old['graph']); graph['name']=name or old['graph']['name']+' copy'
                settings=deepcopy(old['settings']); origin=dict(kind='copy',design=copy_id)
            else:
                graph=template(kind,count,name); settings=settings_default(); origin=dict(kind='template',template=kind)
                settings['profile'][0]['current_A']=3. if kind in ('series','blank') else 6. if kind=='mixed' else 12.
            validate_graph(graph); doc=self._document(graph,settings,origin)
            write(self.root/'documents'/f'{doc["id"]}.json',doc)
            index=read(self.index_path); index['documents'][doc['id']]=self._brief(doc); write(self.index_path,index)
            return self.document(doc['id'])

    def save(self, design_id, version, graph, settings):
        validate_graph(graph); validate_settings(settings)
        with self.lock:
            doc=self._doc(design_id)
            if version != doc['version']: raise ValueError('This design changed in another window. Reopen it before saving.')
            if graph != doc['graph'] or settings != doc['settings']:
                # Content-addressed old revisions are retained before advancing the document.
                write(self.root/'revisions'/f'{digest(doc)}.json',doc)
                doc.update(graph=deepcopy(graph),settings=deepcopy(settings),version=doc['version']+1,updated_utc=utc())
                write(self.root/'documents'/f'{design_id}.json',doc)
                index=read(self.index_path); index['documents'][design_id]=self._brief(doc); write(self.index_path,index)
            return self.document(design_id)

    def run(self, design_id, version, settings=None, title=None):
        with self.lock:
            doc=self._doc(design_id)
            if doc['version'] != version: raise ValueError('The design changed. Save your latest edits before testing.')
            g=deepcopy(doc['graph']); s=deepcopy(settings or doc['settings']); validate_settings(s)
        result=simulate(g,s,self.models)
        # The calculation has its own immutable snapshot, even if another tab edits meanwhile.
        tid='test_'+secrets.token_hex(8)
        current=s['profile'][0]['current_A']; duration=s['profile'][-1]['end_s']
        generated=f'{duration/60:g} min · {abs(current):g} A '+('charge' if current<0 else 'discharge' if current>0 else 'rest')
        title=title.strip() if isinstance(title,str) and title.strip() else generated
        if len(title)>120: raise ValueError('Keep the test name under 120 characters.')
        record=dict(id=tid,design_id=design_id,name=title,created_utc=utc(),design_name=g['name'],
                    signature=self._signature(g,s),graph=g,settings=s,model_hash=self.model_hash,software_hash=self.software_hash,
                    status=result.status,stop=result.stop,summary=result.summary,rows=result.rows)
        import platform, numpy, scipy, pandas, matplotlib
        record['runtime']=dict(python=platform.python_version(),numpy=numpy.__version__,scipy=scipy.__version__,pandas=pandas.__version__,matplotlib=matplotlib.__version__)
        record['payload_hash']=digest(record)
        with self.lock:
            write(self.root/'tests'/f'{tid}.json',record)
            # Store exact model/software inputs once for independent replay.
            bundle=self.root/'models'/f'{self.model_hash}.json'
            if not bundle.exists(): write(bundle,self.models)
            software=self.root/'software'/self.software_hash
            for folder in ('studio','models'):
                for src in (Path(__file__).resolve().parents[1]/folder).glob('*.py'):
                    target=software/'voltforge'/folder/src.name
                    if not target.exists(): target.parent.mkdir(parents=True,exist_ok=True); target.write_bytes(src.read_bytes())
            init=software/'voltforge/__init__.py'
            if not init.exists(): init.write_text('')
            brief={k:record[k] for k in ('id','design_id','name','created_utc','design_name','signature','status','summary')}
            brief['payload_hash']=record['payload_hash']
            index=read(self.index_path); index['tests'][tid]=brief
            latest=self._doc(design_id); latest['tests'].append(tid)
            write(self.root/'documents'/f'{design_id}.json',latest)
            index['documents'][design_id]=self._brief(latest); write(self.index_path,index)
        return self.test(tid)

    def test(self, test_id):
        with self.lock:
            index=read(self.index_path)
            if not isinstance(test_id,str) or test_id not in index['tests']: raise ValueError('That test could not be found.')
            record=read(self.root/'tests'/f'{test_id}.json')
            payload=record.pop('payload_hash')
            if digest(record) != payload or index['tests'][test_id]['payload_hash'] != payload:
                raise ValueError('This test record was modified. Run a new test from the design.')
            record['payload_hash']=payload
            doc=self._doc(record['design_id'])
            record['current']=record['signature']==self._signature(doc['graph'],doc['settings'])
            return record

    def investigate(self, design_id, version, scenario, magnitude=None):
        doc=self.document(design_id)
        if version != doc['version']: raise ValueError('The design changed. Save before trying a what-if test.')
        graph=deepcopy(doc['graph']); settings=deepcopy(doc['settings'])
        if scenario=='load':
            factor=number_positive(magnitude or 1.5,1,5,'Load multiplier')
            for p in settings['profile']: p['current_A']*=factor
            name=f'{factor:g}× load'
        elif scenario=='connection':
            if not graph['connections']: raise ValueError('Add a connection before testing connection wear.')
            extra=number_positive(magnitude or 3,0.01,100,'Added resistance')
            graph['connections'][0]['resistance_mohm']+=extra
            graph['connections'][0]['source']='What-if assumption: added connection resistance'
            name=f'First connection +{extra:g} mΩ'
        elif scenario=='charge':
            if not graph['cells']: raise ValueError('Add a cell first.')
            delta=number_positive(magnitude or 10,1,50,'Charge difference')
            graph['cells'][0]['charge_pct']=max(15,graph['cells'][0]['charge_pct']-delta)
            name=f'First cell starts {delta:g}% lower'
        else: raise ValueError('Choose higher load, connection wear or an uneven starting charge.')
        # A what-if is a real named design with its own inputs, never an invisible overwrite.
        copy=self.create(copy_id=design_id,name=name)
        copy=self.save(copy['id'],copy['version'],graph | {'name':name},settings)
        test=self.run(copy['id'],copy['version'],title=name)
        return dict(design=copy,test=test)

    def compare(self, test_ids):
        if not isinstance(test_ids,list) or len(test_ids)!=2 or test_ids[0]==test_ids[1]: raise ValueError('Choose two different tests.')
        tests=[self.test(t) for t in test_ids]
        # Same external test conditions. Initial cell states may deliberately be the design variable.
        same=tests[0]['settings']==tests[1]['settings']
        metric=tests[0]['summary']['metrics']; other=tests[1]['summary']['metrics']
        deltas={k:other[k]-v for k,v in metric.items() if isinstance(v,(int,float)) and isinstance(other.get(k),(int,float))}
        return dict(tests=tests,identical_test_conditions=same,deltas=deltas,
                    comparable_duration=abs(metric['duration_s']-other['duration_s'])<1e-9,
                    note='Same test settings' if same else 'Different test settings. Change one factor at a time before attributing a difference to the design.')

    def export(self, test_id):
        record=self.test(test_id); out=io.BytesIO()
        models=read(self.root/'models'/f'{record["model_hash"]}.json')
        if digest(models)!=record['model_hash']:raise ValueError('The stored model bundle was modified. Restore it before exporting.')
        software=self.root/'software'/record['software_hash']
        files={str(p.relative_to(software/'voltforge')):__import__('hashlib').sha256(p.read_bytes()).hexdigest()
               for folder in ('studio','models') for p in (software/'voltforge'/folder).glob('*.py')}
        if digest(files)!=record['software_hash']:raise ValueError('The stored solver source was modified. Restore it before exporting.')
        with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
            z.writestr('experiment.json',json.dumps(record,indent=2,allow_nan=False))
            z.writestr('models.json',(self.root/'models'/f'{record["model_hash"]}.json').read_bytes())
            for p in software.rglob('*.py'): z.write(p,'software/'+str(p.relative_to(software)))
            from .report import html_report
            z.writestr('report.html',html_report(record))
            scalars=[('Time (s)','time_s'),('Battery current (A)','current_A'),('Battery voltage (V)','voltage_V'),
                     ('Battery power (W)','power_W'),('Net output energy (Wh)','delivered_energy_Wh'),
                     ('Energy delivered (Wh)','delivered_positive_Wh'),('Energy received (Wh)','received_energy_Wh')]
            columns=[label for label,_ in scalars]
            columns += [f'{c["name"]} {metric}' for c in record['graph']['cells'] for metric in ('current_A','voltage_V','charge_pct','temperature_C')]
            stream=io.StringIO(); writer=csv.writer(stream); writer.writerow(columns)
            for r in record['rows']:
                values=[r.get(key,'') for _,key in scalars]
                values.extend(r[k][i] for i in range(len(record['graph']['cells'])) for k in ('cell_current_A','cell_voltage_V','charge_pct','temperature_C'))
                writer.writerow(values)
            z.writestr('results.csv',stream.getvalue())
            z.writestr('replay.py',REPLAY)
            z.writestr('requirements.txt','\n'.join(k+'=='+v for k,v in record.get('runtime',{}).items() if k!='python')+'\n')
            z.writestr('README.txt','Install requirements.txt, then run python replay.py. The included source and model inputs reproduce this numerical experiment. Open report.html to read the results. Simulation verification is not experimental validation.\n')
        return out.getvalue()


def number_positive(value,low,high,label):
    from .network import number
    return number(value,label,low,high)


REPLAY='''from pathlib import Path
import json, sys
import numpy as np
sys.path.insert(0,str(Path(__file__).parent/'software'))
from voltforge.studio.network import simulate, digest
root=Path(__file__).parent
record=json.loads((root/'experiment.json').read_text())
expected_hash=record.pop('payload_hash'); record.pop('current',None)
assert digest(record)==expected_hash, 'Experiment manifest was modified'
models=json.loads((root/'models.json').read_text())
assert digest(models)==record['model_hash'], 'Model inputs were modified'
import hashlib
software=root/'software/voltforge'
files={str(p.relative_to(software)):hashlib.sha256(p.read_bytes()).hexdigest() for folder in ('studio','models') for p in (software/folder).glob('*.py')}
assert digest(files)==record['software_hash'], 'Solver source was modified'
result=simulate(record['graph'],record['settings'],models)
assert len(result.rows)==len(record['rows'])
for actual,expected in zip(result.rows,record['rows']):
    for key in actual:
        a,b=actual[key],expected[key]
        if isinstance(a,list) and any(v is None for v in a):
            assert len(a)==len(b) and all(x is y if x is None or y is None else np.isclose(x,y,rtol=1e-9,atol=1e-9) for x,y in zip(a,b)), key
        else: assert np.allclose(a,b,rtol=1e-9,atol=1e-9), key
assert result.status==record['status']
print('Reproduced',len(result.rows),'samples. Numerical reproduction only; physical accuracy requires independent measurements.')
'''
