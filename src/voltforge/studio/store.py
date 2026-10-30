"""Additive studio documents. The earlier project and all of its results stay intact."""
from copy import deepcopy
from datetime import datetime, timezone
import csv
import io
try:
    import fcntl
except ImportError:  # Native Windows uses its own advisory lock API.
    fcntl=None
import json
import os
from pathlib import Path
import secrets
import threading
import zipfile

from voltforge.project.service import Project
from voltforge.models.cell_catalogue import CellModel, load_additional, public_model
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
        sync_directory(path.parent)
    finally:
        if tmp.exists(): tmp.unlink()


def sync_directory(path):
    # Persist directory entries after replace/unlink on POSIX filesystems.
    if os.name=='posix':
        fd=os.open(path,os.O_RDONLY)
        try:os.fsync(fd)
        finally:os.close(fd)


def read(path):
    return json.loads(Path(path).read_text())


class FileLock:
    """Reentrant thread lock plus an OS advisory lock for another local editor process."""
    def __init__(self,path,on_acquire=None):
        self.path=path;self.guard=threading.RLock();self.depth=0;self.handle=None;self.on_acquire=on_acquire

    def __enter__(self):
        self.guard.acquire()
        try:
            if not self.depth:
                self.path.parent.mkdir(parents=True,exist_ok=True)
                self.handle=self.path.open('a+b')
                if fcntl is not None:fcntl.flock(self.handle,fcntl.LOCK_EX)
                else:
                    import msvcrt
                    if self.path.stat().st_size==0:self.handle.write(b'0');self.handle.flush()
                    self.handle.seek(0);msvcrt.locking(self.handle.fileno(),msvcrt.LK_LOCK,1)
                if self.on_acquire:self.on_acquire()
            self.depth+=1
        except BaseException:
            if self.handle is not None and not self.depth:self.handle.close();self.handle=None
            self.guard.release();raise
        return self

    def __exit__(self,*_):
        self.depth-=1
        if not self.depth:
            if fcntl is not None:fcntl.flock(self.handle,fcntl.LOCK_UN)
            else:
                import msvcrt
                self.handle.seek(0);msvcrt.locking(self.handle.fileno(),msvcrt.LK_UNLCK,1)
            self.handle.close();self.handle=None
        self.guard.release()


class Studio:
    def __init__(self, project):
        self.legacy=Project(project); self.root=Path(project)/'studio'
        self.journal_path=self.root/'pending_commit.json'
        self.lock=FileLock(self.root/'write.lock',self._refresh)
        self.index_path=self.root/'index.json'
        self.base, _=self.legacy._inputs(self.legacy._state())
        self.models=dict(zip(MODEL_KEYS,self.base['models']))
        self.models.update(load_additional(Path(__file__).resolve().parents[3]))
        self.model_hash=digest(self.models)
        src=Path(__file__).resolve().parents[1]
        self.software_files={str(p.relative_to(src)):p.read_bytes() for folder in ('studio','models') for p in sorted((src/folder).glob('*.py'))}
        self.software_hash=self._software_hash()
        from .parts import load_prices
        self.prices=load_prices(Path(__file__).resolve().parents[3])
        self._ensure()
        with self.lock:self._load_custom_models()

    def _refresh(self):
        self._recover()
        if hasattr(self,'models') and self.index_path.exists():self._load_custom_models()

    def _load_custom_models(self):
        for key in read(self.index_path).get('models',{}):
            record=read(self.root/'custom_models'/f'{key}.json')
            if digest(record)!=read(self.index_path)['models'][key]['hash']:
                raise ValueError('A custom cell definition was modified. Restore its saved version before opening this project.')
            CellModel(record);self.models[key]=record
        self.model_hash=digest(self.models)

    def create_cell(self,definition=None,csv_text=None,metadata=None,parent_key=None):
        from voltforge.models.custom_cells import normalize, csv_definition
        with self.lock:
            self._load_custom_models()
            if parent_key and (parent_key not in self.models or self.models[parent_key].get('origin')!='user'):
                raise ValueError('Choose a custom cell to create a new version.')
            if csv_text is not None:
                if definition is not None:raise ValueError('Import a JSON definition or CSV, one at a time.')
                definition=csv_definition(csv_text,metadata)
            key='custom_'+secrets.token_hex(10)
            revision=self.models[parent_key]['revision']+1 if parent_key else 1
            record=normalize(definition,key,revision,parent_key)
            index=read(self.index_path);index.setdefault('models',{})[key]=dict(hash=digest(record),name=record['name'],revision=revision)
            self._commit({'custom_models/'+key+'.json':record},index)
            self.models[key]=record;self.model_hash=digest(self.models)
            return public_model(key,record)

    @staticmethod
    def _software_hash():
        src=Path(__file__).resolve().parents[1]
        paths=[p for d in ('studio','models') for p in (src/d).glob('*.py')]
        return digest({str(p.relative_to(src)):__import__('hashlib').sha256(p.read_bytes()).hexdigest() for p in sorted(paths)})

    def _ensure(self):
        with self.lock:
            if self.index_path.exists(): return
            index=dict(version=1,documents={},tests={});entries={}
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
                entries['documents/'+doc['id']+'.json']=doc
                index['documents'][doc['id']]=self._brief(doc)
            self._commit(entries,index)

    def _recover(self):
        """The durable journal is the commit point; replay is idempotent."""
        if not self.journal_path.exists():return
        journal=read(self.journal_path);payload=journal.get('payload')
        if not isinstance(payload,dict) or digest(payload)!=journal.get('hash'):
            raise ValueError('A saved change needs recovery, but its journal was modified. Restore the project backup.')
        for name,value in payload['entries'].items():
            relative=Path(name)
            if relative.is_absolute() or '..' in relative.parts or relative.parts[0] not in ('documents','tests','revisions','custom_models','investigations'):
                raise ValueError('The pending change contains an invalid destination.')
            write(self.root/relative,value)
        write(self.index_path,payload['index'])
        self.journal_path.unlink()
        sync_directory(self.root)

    def _commit(self,entries,index):
        payload=dict(entries=entries,index=index)
        try:
            write(self.journal_path,dict(payload=payload,hash=digest(payload)))
            self._recover()
        except OSError as exc:
            if self.journal_path.exists():
                raise ValueError('The change is recorded for recovery. Reopen the project to finish saving it; do not repeat the edit.') from exc
            raise ValueError('The change could not be saved. Your previous saved version is unchanged.') from exc

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
        used={c['model']:self.models[c['model']] for c in graph['cells']}
        return digest(dict(graph=physics(graph),settings=settings,models=digest(used),software=self.software_hash))

    def document(self, design_id):
        with self.lock:
            doc=self._doc(design_id)
            signature=self._signature(doc['graph'],doc['settings'])
            tests=[]
            index=read(self.index_path)
            for tid in reversed(doc['tests']):
                brief=deepcopy(index['tests'][tid]); brief['current']=brief['signature']==signature
                tests.append(brief)
            ready=self.preflight(doc['graph'],doc['settings'])
            from .loads import application_view
            from .parts import estimate
            return dict(**doc,readiness=ready,history=tests,application=application_view(doc['settings']),parts=estimate(doc['graph'],self.models,self.prices))

    def preflight(self,graph,settings):
        ready=readiness(graph,self.models)
        ready.update(structural_ready=ready['ready'],model_supported=None,operating_within_limits=None,
                     physical_validation=False)
        if not ready['ready']:return ready
        try:
            validate_settings(settings)
            self.validate_cell_states(graph)
            ready['model_supported']=True
            from .network import Circuit
            import numpy as np
            models=[CellModel(self.models[c['model']]) for c in graph['cells']]
            if settings.get('protection') and settings['protection']['temperature_max_C'] is not None and not all(m.has_thermal for m in models):
                raise ValueError('Temperature-based protection needs a thermal model for every cell. Add thermal properties or disable that threshold.')
            values=[m.parameters(c['charge_pct']/100,c['temperature_C']) for c,m in zip(graph['cells'],models)]
            solution=Circuit(graph,self.models).solve(np.array([v[0]-c['polarization_V'] for v,c in zip(values,graph['cells'])]),
                                          np.array([v[1] for v in values]),settings['profile'][0]['current_A'])
            for i,(cell,model) in enumerate(zip(graph['cells'],models)):
                problem=model.operating_error(cell['temperature_C'],solution['current'][i],solution['voltage'][i])
                if problem:
                    ready['operating_within_limits']=False
                    ready['violation']=dict(reason=problem[0],cell=cell['id'],current_A=float(solution['current'][i]),
                                            voltage_V=float(solution['voltage'][i]),temperature_C=cell['temperature_C'],model=cell['model'])
                    raise ValueError(cell['name']+': '+problem[1])
            ready['operating_within_limits']=True
            from .design_rules import review
            ready['warnings']=review(graph,self.models)
        except ValueError as exc:
            ready.update(ready=False,message=str(exc))
            if ready['model_supported'] is None:ready['model_supported']=False
        return ready

    def validate_cell_states(self,graph):
        for cell in graph['cells']:
            if cell['model'] not in self.models: raise ValueError('That battery model is not installed.')
            model=CellModel(self.models[cell['model']])
            if not model.supported(cell['charge_pct']/100,cell['temperature_C']):
                raise ValueError(cell['name']+': starting charge or cell temperature is outside this model’s recorded range.')

    def catalog(self):
        from .conductors import copper_reference
        with self.lock:
            self._load_custom_models()
            index=read(self.index_path)
            return dict(designs=sorted(index['documents'].values(),key=lambda x:x['updated_utc'],reverse=True),
                        investigations=[dict(id=k,**v) for k,v in index.get('investigations',{}).items()],
                        library=[public_model(k,v) for k,v in self.models.items()],
                        conductor_reference=copper_reference(),
                        science=dict(status='Simulation estimates',
                                     electrical='Cell-specific voltage, resistance and relaxation models. Temperature-dependent models feed cell temperature back into the circuit.',
                                     thermal='Heat is calculated from electrical losses, explicit cell contacts and declared cooling settings.',
                                     calibration='Model source, operating range and assessment status are recorded per cell type. Independent module and fixture validation remain required.'))

    def create(self, kind='parallel', count=4, name=None, copy_id=None, mission=None):
        with self.lock:
            if copy_id:
                old=self._doc(copy_id); graph=deepcopy(old['graph']); graph['name']=name or old['graph']['name']+' copy'
                settings=deepcopy(old['settings']); origin=dict(kind='copy',design=copy_id)
            else:
                graph=template(kind,count,name); settings=settings_default(); origin=dict(kind='template',template=kind)
                if 'LG_M50T_ECN' in self.models:
                    for cell in graph['cells']: cell['model']='LG_M50T_ECN'
                settings['profile'][0]['current_A']=3. if kind in ('series','blank') else 6. if kind=='mixed' else 12.
                if kind=='parallel' and count==4:
                    from .cases import BENCHMARK
                    settings['case']=deepcopy(BENCHMARK);settings['limits']['min_voltage_V']=3.3
                if mission is not None:
                    from .loads import apply_mission,build_mission
                    if not isinstance(mission,dict):raise ValueError('Choose a test type and a load.')
                    apply_mission(settings,build_mission(**mission))
            validate_graph(graph,self.models); doc=self._document(graph,settings,origin)
            index=read(self.index_path); index['documents'][doc['id']]=self._brief(doc)
            self._commit({'documents/'+doc['id']+'.json':doc},index)
            return self.document(doc['id'])

    def save(self, design_id, version, graph, settings):
        with self.lock:
            validate_graph(graph,self.models); validate_settings(settings)
            if any(c['model'] not in self.models for c in graph['cells']): raise ValueError('That battery model is not installed.')
            doc=self._doc(design_id)
            if version != doc['version']: raise ValueError('This design changed in another window. Reopen it before saving.')
            if graph != doc['graph'] or settings != doc['settings']:
                # Content-addressed old revisions are retained before advancing the document.
                write(self.root/'revisions'/f'{digest(doc)}.json',doc)
                doc.update(graph=deepcopy(graph),settings=deepcopy(settings),version=doc['version']+1,updated_utc=utc())
                index=read(self.index_path); index['documents'][design_id]=self._brief(doc)
                self._commit({'documents/'+design_id+'.json':doc},index)
            return self.document(design_id)

    def create_from_graph(self,graph,settings,origin=None,source_id=None,source_version=None):
        """Create a complete new draft in one commit, without an empty interim design."""
        with self.lock:
            validate_graph(graph,self.models);validate_settings(settings)
            if source_id and self._doc(source_id)['version']!=source_version:
                raise ValueError('The source design changed. Ask for an updated proposal.')
            doc=self._document(deepcopy(graph),deepcopy(settings),origin)
            index=read(self.index_path);index['documents'][doc['id']]=self._brief(doc)
            self._commit({'documents/'+doc['id']+'.json':doc},index)
            return self.document(doc['id'])

    def run(self, design_id, version, settings=None, title=None):
        if self._software_hash()!=self.software_hash:
            raise ValueError('The workspace code has been updated. Restart the local editor before running a new test.')
        with self.lock:
            doc=self._doc(design_id)
            if doc['version'] != version: raise ValueError('The design changed. Save your latest edits before testing.')
            g=deepcopy(doc['graph']); s=deepcopy(settings or doc['settings']); validate_settings(s)
            models=deepcopy({c['model']:self.models[c['model']] for c in g['cells']})
            model_hash=digest(models)
        result=simulate(g,s,models)
        # The calculation has its own immutable snapshot, even if another tab edits meanwhile.
        tid='test_'+secrets.token_hex(8)
        current=s['profile'][0]['current_A']; duration=s['profile'][-1]['end_s']
        generated=f'{duration/60:g} min · '+('changing load' if len(s['profile'])>1 else f'{round(abs(current),2):g} A '+('charge' if current<0 else 'discharge' if current>0 else 'rest'))
        title=title.strip() if isinstance(title,str) and title.strip() else generated
        if len(title)>120: raise ValueError('Keep the test name under 120 characters.')
        record=dict(id=tid,design_id=design_id,name=title,created_utc=utc(),design_name=g['name'],
                    signature=self._signature(g,s),graph=g,settings=s,model_hash=model_hash,software_hash=self.software_hash,
                    status=result.status,stop=result.stop,summary=result.summary,rows=result.rows)
        record['model_cards']={key:public_model(key,models[key]) for key in models}
        record['case']=deepcopy(result.summary['case'])
        from .parts import estimate
        record['parts']=estimate(g,models,self.prices)
        import platform, numpy, scipy, pandas, matplotlib
        record['runtime']=dict(python=platform.python_version(),numpy=numpy.__version__,scipy=scipy.__version__,pandas=pandas.__version__,matplotlib=matplotlib.__version__)
        record['payload_hash']=digest(record)
        with self.lock:
            # Store exact model/software inputs once for independent replay.
            bundle=self.root/'models'/f'{model_hash}.json'
            if not bundle.exists(): write(bundle,models)
            software=self.root/'software'/self.software_hash
            for relative,content in self.software_files.items():
                target=software/'voltforge'/relative
                if not target.exists(): target.parent.mkdir(parents=True,exist_ok=True); target.write_bytes(content)
            init=software/'voltforge/__init__.py'
            if not init.exists(): init.write_text('')
            brief={k:record[k] for k in ('id','design_id','name','created_utc','design_name','signature','status','summary')}
            brief['payload_hash']=record['payload_hash']
            index=read(self.index_path); index['tests'][tid]=brief
            latest=self._doc(design_id); latest['tests'].append(tid)
            index['documents'][design_id]=self._brief(latest)
            self._commit({'tests/'+tid+'.json':record,'documents/'+design_id+'.json':latest},index)
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

    def investigate(self, design_id, version, scenario, magnitude=None, baseline_test_id=None):
        doc=self.document(design_id)
        if version != doc['version']: raise ValueError('The design changed. Save before trying a what-if test.')
        baseline=self.test(baseline_test_id) if baseline_test_id else None
        if baseline:
            if baseline['design_id']!=design_id:raise ValueError('Choose a baseline test belonging to this design.')
            used={c['model']:self.models[c['model']] for c in baseline['graph']['cells']}
            if baseline['software_hash']!=self.software_hash or baseline['model_hash']!=digest(used):
                raise ValueError('Run a baseline with the installed model and solver before comparing this change.')
        graph=deepcopy(baseline['graph'] if baseline else doc['graph'])
        settings=deepcopy(baseline['settings'] if baseline else doc['settings'])
        initial=deepcopy(graph);initial_settings=deepcopy(settings)
        if scenario=='load':
            factor=number_positive(magnitude or 1.5,1,5,'Load multiplier')
            for p in settings['profile']: p['current_A']*=factor
            name=f'{factor:g}× load'
        elif scenario=='connection':
            if not graph['connections']: raise ValueError('Add a connection before testing connection wear.')
            extra=number_positive(magnitude or 3,0.01,100,'Added resistance')
            from .conductors import add_contact_resistance
            add_contact_resistance(graph['connections'][0],extra,'What-if assumption: added end-contact resistance')
            name=f'First connection +{extra:g} mΩ'
        elif scenario=='charge':
            if not graph['cells']: raise ValueError('Add a cell first.')
            delta=number_positive(magnitude or 10,1,50,'Charge difference')
            graph['cells'][0]['charge_pct']=max(15,graph['cells'][0]['charge_pct']-delta)
            name=f'First cell starts {delta:g}% lower'
        elif scenario=='takeoff':
            if len(graph['cells'])<2 or any(w['a'].split(':')[1]!=w['b'].split(':')[1] for w in graph['connections']):
                raise ValueError('Try opposite-end collection on a parallel layout with at least two cells.')
            graph['output']['negative']=graph['cells'][-1]['id']+':n'
            name='Opposite-end output connection'
        else: raise ValueError('Choose higher load, connection wear, opposite-end output or an uneven starting charge.')
        # A what-if is a real named design with its own inputs, never an invisible overwrite.
        with self.lock:
            if self._doc(design_id)['version']!=version:raise ValueError('The design changed. Retry from the saved baseline.')
            graph['name']=name
            origin=dict(kind='investigation',design=design_id,baseline_test_id=baseline_test_id,
                        baseline_payload_hash=baseline.get('payload_hash') if baseline else None,
                        scenario=scenario,changes=input_changes(initial,graph),settings_changes=input_changes(initial_settings,settings))
            created=self._document(graph,settings,origin)
            index=read(self.index_path);index['documents'][created['id']]=self._brief(created)
            self._commit({'documents/'+created['id']+'.json':created},index)
            copy=self.document(created['id'])
        test=self.run(copy['id'],copy['version'],title=name)
        return dict(design=copy,test=test)

    def compare(self, test_ids):
        if not isinstance(test_ids,list) or len(test_ids)!=2 or test_ids[0]==test_ids[1]: raise ValueError('Choose two different tests.')
        tests=[self.test(t) for t in test_ids]
        # Same external test conditions. Initial cell states may deliberately be the design variable.
        same=tests[0]['settings']==tests[1]['settings']
        metric=tests[0]['summary']['metrics']; other=tests[1]['summary']['metrics']
        deltas={k:other[k]-v for k,v in metric.items() if isinstance(v,(int,float)) and isinstance(other.get(k),(int,float))}
        changes=input_changes(physics(tests[0]['graph']),physics(tests[1]['graph']))
        numeric_changes=[c for c in changes if not c['path'].endswith('.source')]
        return dict(tests=tests,identical_test_conditions=same,deltas=deltas,
                    design_changes=changes,settings_changes=input_changes(tests[0]['settings'],tests[1]['settings']),model_versions_match=tests[0]['model_hash']==tests[1]['model_hash'],
                    solver_versions_match=tests[0]['software_hash']==tests[1]['software_hash'],
                    single_factor_comparison=same and len(numeric_changes)==1 and tests[0]['model_hash']==tests[1]['model_hash'] and tests[0]['software_hash']==tests[1]['software_hash'],
                    comparable_duration=abs(metric['duration_s']-other['duration_s'])<1e-9,
                    requirements_match=tests[0].get('case',{}).get('requirements_fingerprint')==tests[1].get('case',{}).get('requirements_fingerprint'),
                    note='Same test settings' if same else 'Different test settings. Change one factor at a time before attributing a difference to the design.')

    def begin_investigation(self,design_id,version,baseline_test_id,condition='load'):
        from .failure_search import scenarios
        with self.lock:
            doc=self._doc(design_id);baseline=self.test(baseline_test_id)
            if version!=doc['version'] or baseline['design_id']!=design_id:
                raise ValueError('Choose a saved baseline test from this design.')
            used={c['model']:self.models[c['model']] for c in baseline['graph']['cells']}
            if baseline['software_hash']!=self.software_hash or baseline['model_hash']!=digest(used):
                raise ValueError('Run a baseline test with the installed solver and models before investigating its limits.')
            specs=scenarios(baseline['graph'],baseline['settings'],condition)
            from .network import integration_grid
            if len(specs)*(len(integration_grid(baseline['settings']))-1)>250000:
                raise ValueError('Use a larger time step or shorter mission before starting this pressure test.')
            record=dict(id='investigation_'+secrets.token_hex(8),design_id=design_id,baseline_test_id=baseline_test_id,
                        baseline_payload_hash=baseline['payload_hash'],created_utc=utc(),condition=condition,
                        graph=deepcopy(baseline['graph']),settings=deepcopy(baseline['settings']),model_hash=baseline['model_hash'],
                        software_hash=baseline['software_hash'],model_cards=baseline.get('model_cards',{}),planned=specs,cases=[],complete=False,
                        scope='Finite one-factor pressure tests of this saved baseline. Model coverage is not a hardware failure boundary.')
            self._save_investigation(record)
            return self.investigation(record['id'])

    def _save_investigation(self,record):
        record=deepcopy(record);record.pop('payload_hash',None);record['payload_hash']=digest(record)
        index=read(self.index_path);index.setdefault('investigations',{})[record['id']]=dict(design_id=record['design_id'],
            baseline_test_id=record['baseline_test_id'],condition=record['condition'],completed=len(record['cases']),
            total=len(record['planned']),payload_hash=record['payload_hash'])
        self._commit({'investigations/'+record['id']+'.json':record},index)

    def investigation(self,investigation_id,include_rows=False):
        with self.lock:
            index=read(self.index_path)
            if not isinstance(investigation_id,str) or investigation_id not in index.get('investigations',{}):
                raise ValueError('That saved investigation could not be found.')
            record=read(self.root/'investigations'/f'{investigation_id}.json');saved=record.pop('payload_hash')
            if digest(record)!=saved or index['investigations'][investigation_id]['payload_hash']!=saved:
                raise ValueError('The saved investigation was modified. Create a new investigation from the baseline.')
            record['payload_hash']=saved
            if not include_rows:
                if record['condition']=='cell_count':
                    from .failure_search import SIZING_CLAIM,SIZING_SCOPE,smallest
                    best=smallest(record['cases']) if record['complete'] else None
                    record['sizing']=dict(claim=SIZING_CLAIM,scope=SIZING_SCOPE,smallest_cell_count=best['cell_count'] if best else None)
                for case in record['cases']:
                    rows=case.pop('rows');position=case['outcome'].get('sample_index')
                    case['sample_row']=rows[position] if rows and position is not None else None
            return record

    def investigate_case(self,investigation_id,case_index):
        from .failure_search import inputs,outcome,sizing_verdict
        with self.lock:
            record=self.investigation(investigation_id,include_rows=True)
            if isinstance(case_index,bool) or not isinstance(case_index,int) or not 0<=case_index<len(record['planned']):
                raise ValueError('Choose an allocated pressure-test case.')
            if case_index<len(record['cases']):return self.investigation(investigation_id)
            if case_index!=len(record['cases']):raise ValueError('Calculate the pressure tests in their declared order.')
            if self._software_hash()!=self.software_hash or record['software_hash']!=self.software_hash:
                raise ValueError('The solver changed. Run a new baseline and start a new investigation.')
            models=read(self.root/'models'/f'{record["model_hash"]}.json')
            if digest(models)!=record['model_hash']:raise ValueError('The saved model bundle changed. Restore it before investigating.')
            graph,settings=inputs(record['graph'],record['settings'],record['planned'][case_index]);ready=self.preflight(graph,settings)
        result=simulate(graph,settings,models) if ready['ready'] else None
        case=dict(index=case_index,name=record['planned'][case_index]['name'],graph=graph,settings=settings,
                  outcome=outcome(graph,settings,result,ready),status=result.status if result else 'not_started',
                  stop=result.stop if result else None,summary=result.summary if result else None,rows=result.rows if result else [],
                  affected_connections=[graph['connections'][0]['id']] if record['planned'][case_index]['extra_resistance'] else [])
        if record['planned'][case_index].get('cell_count'):
            from .parts import estimate
            case.update(cell_count=record['planned'][case_index]['cell_count'],sizing=sizing_verdict(result,ready),parts=estimate(graph,models,self.prices))
        with self.lock:
            latest=self.investigation(investigation_id,include_rows=True)
            if len(latest['cases'])==case_index:
                latest['cases'].append(case);latest['complete']=len(latest['cases'])==len(latest['planned']);self._save_investigation(latest)
            return self.investigation(investigation_id)

    def open_investigation_case(self,investigation_id,case_index):
        record=self.investigation(investigation_id)
        if isinstance(case_index,bool) or not isinstance(case_index,int) or not 0<=case_index<len(record['cases']):
            raise ValueError('Calculate this pressure-test case before opening it.')
        used={c['model']:self.models[c['model']] for c in record['graph']['cells']}
        if record['software_hash']!=self.software_hash or record['model_hash']!=digest(used):
            raise ValueError('Keep this earlier investigation as evidence. Run a new baseline before opening a current editable test.')
        case=record['cases'][case_index];graph=deepcopy(case['graph']);graph['name']=case['name']
        doc=self.create_from_graph(graph,case['settings'],origin=dict(kind='failure_case',investigation=investigation_id,case_index=case_index))
        test=self.run(doc['id'],doc['version'],title=case['name']) if doc['readiness']['ready'] else None
        return dict(design=self.document(doc['id']),test=test,baseline_test_id=record['baseline_test_id'],outcome=case['outcome'])

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
                     ('Energy delivered (Wh)','delivered_positive_Wh'),('Energy received (Wh)','received_energy_Wh'),('Event side','event_side'),
                     ('Requested current (A)','requested_current_A'),('External disconnect open','external_disconnected'),('Event kind','event_kind')]
            scalars += [('Cell-side output voltage (V)','cell_side_voltage_V'),('Output conductor loss (W)','output_route_loss_W')]
            columns=[label for label,_ in scalars]
            columns += [f'{c["name"]} {metric}' for c in record['graph']['cells'] for metric in ('current_A','voltage_V','charge_pct','temperature_C')]
            stream=io.StringIO(); writer=csv.writer(stream); writer.writerow(columns)
            for r in record['rows']:
                values=[r.get(key,'') for _,key in scalars]
                values.extend(r[k][i] for i in range(len(record['graph']['cells'])) for k in ('cell_current_A','cell_voltage_V','charge_pct','temperature_C'))
                writer.writerow(values)
            z.writestr('results.csv',stream.getvalue())
            z.writestr('replay.py',REPLAY)
            z.writestr('evidence.json',json.dumps(dict(model_cards=record.get('model_cards',{}),
                models={k:{field:v for field,v in m.items() if field in ('source','evidence_status','operating_limits','thermal_defaults','thermal_provenance','development_assessment','reference','kind')} for k,m in models.items()},
                coverage=record['summary'].get('coverage'),assessment=record['summary'].get('assessment'),
                current_convention='Positive current discharges the cell or battery.',
                classification='Numerical model reproduction; independent physical assessment is separate.'),indent=2))
            z.writestr('requirements.txt','\n'.join(k+'=='+v for k,v in record.get('runtime',{}).items() if k!='python')+'\n')
            z.writestr('README.txt','Install requirements.txt, then run python replay.py. The included source and model inputs reproduce this numerical experiment. Open report.html to read the results. Simulation verification is not experimental validation.\n')
        return out.getvalue()


def number_positive(value,low,high,label):
    from .network import number
    return number(value,label,low,high)


def input_changes(before,after,path=''):
    """Typed explicit differences, used by interventions and approval previews."""
    if isinstance(before,dict) and isinstance(after,dict):
        return [change for key in sorted(set(before)|set(after))
                for change in input_changes(before.get(key),after.get(key),path+'.'+key if path else key)]
    if isinstance(before,list) and isinstance(after,list):
        if all(isinstance(x,dict) and 'id' in x for x in before+after):
            return input_changes({x['id']:x for x in before},{x['id']:x for x in after},path)
        if len(before)==len(after):
            return [change for i,(a,b) in enumerate(zip(before,after)) for change in input_changes(a,b,f'{path}[{i}]')]
    return [] if before==after else [dict(path=path,before=before,after=after)]


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
def compare(a,b,path='result'):
    if isinstance(a,dict):
        assert set(a)==set(b), path
        for key in a:compare(a[key],b[key],path+'.'+key)
    elif isinstance(a,list):
        assert len(a)==len(b),path
        for i,(x,y) in enumerate(zip(a,b)):compare(x,y,path+str(i))
    elif a is None or isinstance(a,(str,bool)):
        assert a==b,path
    else:assert np.isclose(a,b,rtol=1e-9,atol=1e-9),path
compare(result.rows,record['rows'])
compare(result.summary,record['summary'],'summary')
compare(result.stop,record['stop'],'stop')
assert result.status==record['status']
print('Reproduced',len(result.rows),'samples. Numerical reproduction only; physical accuracy requires independent measurements.')
'''
