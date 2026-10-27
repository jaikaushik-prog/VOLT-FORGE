"""Synchronous, single-writer project API. No fitting, HTTP server, or new solver."""
import copy
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import re
import shutil
import sys

import numpy as np
import pandas as pd

from voltforge.simulation import workflow as w
from voltforge.models import thermal_v1
from . import schema as s
from . import engineering

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_REFERENCE = ROOT / 'reports/module_simulation_v1'
THERMAL_CONFIG = ROOT / 'configs/thermal_v1.json'


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_once(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(value, indent=2, allow_nan=False) + '\n'
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(data)


def now():
    return datetime.now(timezone.utc).isoformat()


def destination(path):
    path = Path(path).resolve()
    protected = [ROOT / p for p in ['.git', '.codex', '.agents', 'data', 'src', 'configs', 'tests', 'scripts',
        'reports/identification_v1', 'reports/improvement_v2', 'reports/reference_initial_state_v1', 'reports/module_simulation_v1']]
    s.require(path != ROOT and path not in ROOT.parents and not any(path == p or p in path.parents for p in protected),
        'Destination is a protected/source directory', 'unsupported_request')
    return path


def verify_files(folder, hashes):
    folder = Path(folder).resolve()
    for name, expected in hashes.items():
        p = (folder / name).resolve()
        s.require(p.is_relative_to(folder) and p.is_file() and file_hash(p) == expected,
            'Artifact integrity check failed: ' + name, 'integrity_error')


def software():
    paths = sorted((ROOT / 'src/voltforge').rglob('*.py')) + [ROOT / 'requirements.txt', ROOT / 'pyproject.toml']
    files = {p.relative_to(ROOT).as_posix(): file_hash(p) for p in paths}
    versions = {name: importlib.metadata.version(name) for name in ['numpy', 'scipy', 'pandas', 'matplotlib']}
    versions['python'] = '.'.join(map(str, sys.version_info[:3]))
    record = dict(files=files, runtime=versions, solver='voltforge.models.coupling_v2', adapter='voltforge.project/1')
    return dict(id=digest(record), **record)


def valid_id(value):
    s.require(isinstance(value, str) and re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]{0,47}', value), 'Invalid identifier')
    return value


class Project:
    """Load from disk on every call; mutations are exclusive and revisions immutable."""
    def __init__(self, path):
        self.path = Path(path).resolve()
        self._state()

    @classmethod
    def create_reference(cls, path, reference_workspace=DEFAULT_REFERENCE):
        path = destination(path)
        s.require(not path.exists(), 'Project directory already exists; open it or choose a new path', 'conflict')
        ref = Path(reference_workspace).resolve()
        manifest = read(ref / 'manifest.json')
        verify_files(ref, manifest['artifacts'])
        verify_files(ROOT, manifest['declared_inputs'])
        lock = read(ROOT / 'configs/reference_initial_state_v1.lock.json')
        verify_files(ROOT, lock['protected'])
        seal = read(ROOT / 'reports/improvement_v2/procedure_seal.json')
        base = read(ref / 'configured/equal_soc.json')
        s.require(base['cell_order'] == s.CELLS and base['topology'] == s.TOPOLOGY, 'Reference module is unsupported', 'unsupported_request')
        for i, cell in enumerate(s.CELLS):
            source = manifest['model_sources'][cell]
            s.require(file_hash(ROOT / source['path']) == source['sha256'] == seal['artifacts'][source['path']], 'Frozen model seal mismatch', 'integrity_error')
            model = read(ROOT / source['path'])['C2_rest_reference_RC']
            s.require(base['models'][i] == {k: model[k] for k in base['models'][i]}, 'Configured model differs from sealed fit', 'integrity_error')
        thermal = read(THERMAL_CONFIG)
        design = s.reference_design(base, manifest, 2, thermal)
        s.validate_design(design, base, manifest)
        path.mkdir(parents=True)
        assets = path / 'assets'
        assets.mkdir()
        copies = {'base_case.json': ref / 'configured/equal_soc.json', 'source_manifest.json': ref / 'manifest.json',
            'reference_sensitivity.npz': ref / 'reference_sensitivity.npz', 'scenario_plan.json': ref / 'scenario_plan.json'}
        for cell in s.CELLS:
            copies[f'models/{cell}.json'] = ROOT / manifest['model_sources'][cell]['path']
        for name in ['ATTRIBUTION.md', 'MODEL_IMPROVEMENT_DECISION.md', 'REFERENCE_INITIAL_STATE_DECISION.md',
                     'MEASUREMENT_IMPORT_SPEC.md', 'reports/reconciliation/RECONCILIATION.md',
                     'reports/reference_initial_state_v1/LAB_REQUEST.md']:
            copies['evidence/' + name] = ROOT / name
        copies['thermal_v1.json'] = THERMAL_CONFIG
        copies['evidence/reports/thermal_v1/cooling_derivation.json'] = ROOT / 'reports/thermal_v1/cooling_derivation.json'
        copies['evidence/reports/reconciliation/cycle_balance/CYCLE_BALANCE.md'] = ROOT / 'reports/reconciliation/cycle_balance/CYCLE_BALANCE.md'
        for name, original in copies.items():
            target = assets / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(original, target)
        record = dict(design=design, parent=None, change={'kind': 'reference_template'}, created_utc=now())
        revision_id = 'rev_' + digest(record)
        write_once(path / 'revisions' / (revision_id + '.json'), record)
        state = dict(schema_version=s.SCHEMA_V2, project_id='four_cell_reference', created_utc=now(),
            assets={name: file_hash(assets / name) for name in copies},
            variants={'A0': dict(name='Reference A0', revision_id=revision_id, run_ids=[], inherited_run_ids=[])},
            runs={}, measurements={}, display=dict(positions={}, camera={}, selection=[]),
            capabilities=dict(electrical=True, thermal=True, engineering_screen=True, failure_investigator=True, general_cad=False, optimizer=False, ai_physics=False),
            evidence_status='awaiting suitable measurements', thermal_status='lumped four-node surface-equivalent model; declared parameters; one-way coupled; not validated')
        write_once(path / 'project.json', state)
        return cls(path)

    def _state(self):
        p = read(self.path / 'project.json')
        s.require(p.get('schema_version') in s.PROJECT_SCHEMAS, 'Unsupported project schema; no implicit migration', 'unsupported_request')
        return p

    def _save(self, state):
        target = self.path / 'project.json'
        temp = self.path / 'project.next.json'
        with temp.open('w', encoding='utf-8', newline='\n') as stream:
            json.dump(state, stream, indent=2, allow_nan=False)
            stream.write('\n')
        os.replace(temp, target)

    @contextmanager
    def _writer(self):
        destination(self.path)
        lock = self.path / 'project.lock'
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError as exc:
            raise s.RequestError('conflict', 'Another writer is active, or a crashed writer left project.lock; inspect before removing') from exc
        try:
            os.close(fd)
            yield self._state()
        finally:
            lock.unlink()

    def _inputs(self, state):
        verify_files(self.path / 'assets', state['assets'])
        return read(self.path / 'assets/base_case.json'), read(self.path / 'assets/source_manifest.json')

    def _revision(self, state, variant_id):
        valid_id(variant_id)
        s.require(variant_id in state['variants'], 'Unknown variant', 'not_found')
        rid = state['variants'][variant_id]['revision_id']
        s.require(re.fullmatch('rev_[0-9a-f]{64}', rid), 'Invalid revision reference', 'integrity_error')
        record = read(self.path / 'revisions' / (rid + '.json'))
        s.require(rid == 'rev_' + digest(record), 'Revision was modified', 'integrity_error')
        base, manifest = self._inputs(state)
        s.validate_design(record['design'], base, manifest)
        return rid, record

    def _expected(self, state, variant_id, expected_revision):
        rid, record = self._revision(state, variant_id)
        s.require(rid == expected_revision, 'Design changed since inspection; reload before applying the edit', 'conflict')
        return rid, record

    def inspect(self, variant_id='A0'):
        state = self._state()
        rid, revision = self._revision(state, variant_id)
        base, _ = self._inputs(state)
        v = state['variants'][variant_id]
        runs = [self.get_run(variant_id, run_id) for run_id in dict.fromkeys(v['run_ids'] + v['inherited_run_ids'])]
        current_by_scenario = {}
        for item in runs:
            if item['freshness'] == 'current' and item['execution_status'] == 'completed':
                current_by_scenario.setdefault(item['scenario_id'], []).append(item['run_id'])
        return dict(schema_version=state.get('schema_version', s.SCHEMA), variant_id=variant_id, name=v['name'], revision_id=rid,
            design=revision['design'], display=state['display'], editable_properties=copy.deepcopy(s.editable_catalogue(revision['design'])),
            fitted_parameters={f'cell_{k}': dict(R0_ohm=m['parameters_ohm'][0], R1_ohm=m['parameters_ohm'][1], tau_s=m['tau_s'],
                capacity_Ah=m['capacity_Ah'], classification='R0/R1/tau fitted; capacity derived from recorded C/20 integration; all read-only') for k, m in enumerate(base['models'], 1)},
            output_components=['module'] + list(revision['design']['cells']) + list(revision['design']['connections']),
            variants={k: {'name': x['name'], 'revision_id': x['revision_id']} for k, x in state['variants'].items()},
            runs=runs, current_run_ids=[x['run_id'] for x in runs if x['freshness'] == 'current' and x['execution_status'] == 'completed'],
            current_runs_by_scenario=current_by_scenario,
            capabilities=state['capabilities'], experimental_validation=state['evidence_status'], thermal_parameters=s.thermal_parameters(revision['design']))

    def validate_edit(self, variant_id, edit, expected_revision):
        state = self._state()
        rid, record = self._expected(state, variant_id, expected_revision)
        base, manifest = self._inputs(state)
        proposed = s.edited(record['design'], edit, base, manifest)
        changed = proposed != record['design']
        return dict(valid=True, physics_changed=changed, expected_revision=rid,
            invalidated_run_ids=list(state['variants'][variant_id]['run_ids']) if changed else [],
            classification='exploratory edit; does not modify fitted artifacts',
            warnings=['Module accuracy unvalidated', 'A user-declared measurement is not independently verified'])

    def apply_edit(self, variant_id, edit, expected_revision):
        with self._writer() as state:
            rid, record = self._expected(state, variant_id, expected_revision)
            base, manifest = self._inputs(state)
            proposed = s.edited(record['design'], edit, base, manifest)
            if proposed != record['design']:
                new = dict(design=proposed, parent=rid, change=copy.deepcopy(edit), created_utc=now())
                next_id = 'rev_' + digest(new)
                write_once(self.path / 'revisions' / (next_id + '.json'), new)
                state['variants'][variant_id]['revision_id'] = next_id
                self._save(state)
        return self.inspect(variant_id)

    def create_variant(self, source_variant, variant_id, name, expected_revision):
        valid_id(variant_id)
        s.require(isinstance(name, str) and bool(name.strip()), 'Variant name required')
        with self._writer() as state:
            rid, _ = self._expected(state, source_variant, expected_revision)
            s.require(variant_id.casefold() not in {k.casefold() for k in state['variants']}, 'Variant already exists', 'conflict')
            source = state['variants'][source_variant]
            state['variants'][variant_id] = dict(name=name, revision_id=rid, run_ids=[],
                inherited_run_ids=list(dict.fromkeys(source['run_ids'] + source['inherited_run_ids'])))
            self._save(state)
        return self.inspect(variant_id)

    def update_display(self, display):
        s.keys(display, ['positions', 'camera', 'selection'], 'display')
        ids = {'module'} | {f'cell_{k}' for k in range(1, 5)} | {f'rail_{p}_{k}' for p in ['p', 'n'] for k in range(1, 4)}
        s.require(isinstance(display['positions'], dict) and set(display['positions']) <= ids, 'Unknown display component')
        for point in display['positions'].values():
            s.require(isinstance(point, list) and len(point) in (2, 3) and all(s.finite(x) for x in point), 'Display positions require two or three finite coordinates')
        s.require(isinstance(display['camera'], dict) and isinstance(display['selection'], list) and all(x in ids for x in display['selection']), 'Invalid camera/selection')
        canonical(display)  # reject non-JSON/nonfinite metadata
        with self._writer() as state:
            state['display'] = copy.deepcopy(display)
            self._save(state)
        return dict(display=display, physics_changed=False, invalidated_run_ids=[], units='arbitrary display coordinates; no physical geometry rule')

    def _capture_software(self, record):
        folder = self.path / 'software' / record['id']
        if folder.exists():
            verify_files(folder, record['files'])
            return
        for rel in record['files']:
            target = folder / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / rel, target)
        verify_files(folder, record['files'])
        write_once(folder / 'manifest.json', record)

    def run(self, variant_id='A0', scenario_id='nominal', expected_revision=None, plots=True):
        with self._writer() as state:
            rid, revision = self._revision(state, variant_id)
            s.require(expected_revision is not None and rid == expected_revision, 'Run requires the current expected_revision', 'conflict')
            base, _ = self._inputs(state)
            plan = read(self.path / 'assets/scenario_plan.json')
            case = s.to_case(revision['design'], base, scenario_id, plan['sensitivity_scenarios'])
            w.check_case(case)
            code = software()
            self._capture_software(code)
            run_id = f'run_{len(state["runs"])+1:04d}'
            folder = self.path / 'runs' / run_id
            s.require(not folder.exists(), 'Unregistered run folder exists; inspect interrupted write before retrying', 'conflict')
            snapshot = dict(schema_version=1, variant_id=variant_id, revision_id=rid, design=revision['design'],
                scenario_id=scenario_id, effective_case=case, assets=state['assets'], software=code,
                classification='simulated; experimental module validation pending',
                sensitivity_note='Sensitivity scenarios are not confidence intervals; SOC/reference origins are correlated')
            params = s.thermal_parameters(revision['design'])
            temperature = revision['design']['scenario']['temperature']
            if params is None:
                snapshot['thermal'] = None
            else:
                snapshot['thermal'] = dict(parameters=params, initial_C=temperature['assumed_surface_C'], ambient_C=temperature['assumed_ambient_C'], model=thermal_v1.VERSION)
            snapshot['snapshot_id'] = digest(snapshot)
            write_once(folder / 'snapshot.json', snapshot)
            write_once(folder / 'configuration.json', case)  # existing importer contract
            status, error = 'failed', None
            try:
                with np.load(self.path / 'assets/reference_sensitivity.npz', allow_pickle=False) as npz:
                    curves = [(npz[c+'_soc'].copy(), npz[c+'_V'].copy()) for c in s.CELLS]
                result = w.execute_case(case, curves)
                (result.frame if len(result.frame) else pd.DataFrame(columns=['time_s', 'step_s'])).to_csv(folder / 'trajectory.csv', index=False)
                summary = w.summarize(result, case)
                status = 'completed' if result.status == 'completed' else 'failed'
                error = result.stop
                thermal_frame = None
                if params is None:
                    summary['thermal'] = {'status': 'unavailable', 'reason': 'Electrical-only v1 design'}
                elif not len(result.frame):
                    summary['thermal'] = {'status': 'unavailable', 'reason': 'No electrical samples'}
                else:
                    try:
                        thermal_frame = thermal_v1.simulate(result.frame, case['models'], params, temperature['assumed_surface_C'], temperature['assumed_ambient_C'])
                        thermal_v1.validate_output(thermal_frame, result.frame)
                        thermal_summary = thermal_v1.summarize(thermal_frame, params)
                        staged_thermal = folder / 'thermal.csv.tmp'
                        try:
                            thermal_frame.to_csv(staged_thermal, index=False)
                            staged_thermal.replace(folder / 'thermal.csv')
                        finally:
                            if staged_thermal.exists():
                                staged_thermal.unlink()
                        summary['thermal'] = dict(status='completed', **thermal_summary)
                    except Exception as exc:
                        thermal_frame = None
                        summary['thermal'] = {'status': 'failed', 'error': {'type': type(exc).__name__, 'message': str(exc)}}
                summary['engineering'] = engineering.screen(result.frame, thermal_frame, revision['design'].get('engineering_requirements'), completed=result.status == 'completed')
                write_once(folder / 'summary.json', summary)
                if plots and len(result.frame):
                    from voltforge.simulation.reporting import electrical_plots
                    electrical_plots(folder, case)
            except Exception as exc:
                # Preserve a failed run and its exact inputs; never substitute success.
                status = 'failed'
                error = dict(type=type(exc).__name__, message=str(exc))
                if not (folder / 'summary.json').exists():
                    write_once(folder / 'summary.json', dict(status='failed', error=error,
                        voltage_requirement={'status': 'insufficient simulation'}, decision='insufficient evidence',
                        experimental_validation='awaiting suitable measurements'))
            record = dict(run_id=run_id, variant_id=variant_id, revision_id=rid, scenario_id=scenario_id,
                snapshot_id=snapshot['snapshot_id'], software_id=code['id'], execution_status=status, error=error,
                created_utc=now(), artifacts={p.name: file_hash(p) for p in sorted(folder.iterdir()) if p.is_file()})
            write_once(folder / 'run.json', record)
            state['runs'][run_id] = dict(variant_id=variant_id, manifest_sha256=file_hash(folder / 'run.json'))
            state['variants'][variant_id]['run_ids'].append(run_id)
            self._save(state)
        return self.get_run(variant_id, run_id)

    def _run_record(self, state, run_id):
        valid_id(run_id)
        s.require(run_id in state['runs'], 'Unknown run', 'not_found')
        folder = self.path / 'runs' / run_id
        s.require(file_hash(folder / 'run.json') == state['runs'][run_id]['manifest_sha256'], 'Run manifest changed', 'integrity_error')
        record = read(folder / 'run.json')
        verify_files(folder, record['artifacts'])
        snapshot = read(folder / 'snapshot.json')
        payload = {k: v for k, v in snapshot.items() if k != 'snapshot_id'}
        s.require(snapshot['snapshot_id'] == digest(payload) == record['snapshot_id'], 'Snapshot changed', 'integrity_error')
        return folder, record, snapshot

    def get_run(self, variant_id, run_id):
        state = self._state()
        rid, _ = self._revision(state, variant_id)
        v = state['variants'][variant_id]
        s.require(run_id in v['run_ids'] + v['inherited_run_ids'], 'Run is not associated with this variant', 'unsupported_request')
        folder, record, snapshot = self._run_record(state, run_id)
        reasons = []
        if record['variant_id'] != variant_id:
            reasons.append('inherited from another variant; never current for this variant')
        if record['revision_id'] != rid:
            reasons.append('design revision changed')
        if snapshot['software']['id'] != software()['id']:
            reasons.append('software/runtime changed')
        summary = read(folder / 'summary.json')
        thermal_summary = summary.get('thermal') or {}
        s.require(isinstance(thermal_summary, dict), 'Malformed thermal summary', 'integrity_error')
        completed_thermal = thermal_summary.get('status') == 'completed'
        declared_thermal = snapshot.get('thermal') is not None
        recorded_thermal = 'thermal.csv' in record['artifacts']
        s.require(not completed_thermal or (declared_thermal and recorded_thermal),
            'Completed thermal result has no declared inputs or verified artifact', 'integrity_error')
        thermal_output = 'available' if completed_thermal and declared_thermal and recorded_thermal else 'unavailable'
        return dict(run_id=run_id, owner_variant_id=record['variant_id'], viewed_variant_id=variant_id,
            revision_id=record['revision_id'], scenario_id=record['scenario_id'], snapshot_id=record['snapshot_id'],
            execution_status=record['execution_status'], freshness='outdated' if reasons else 'current',
            outdated_reasons=reasons, error=record['error'], summary=summary,
            thermal_output=thermal_output, classification='simulated', artifact_paths=list(record['artifacts']))

    def series(self, variant_id, run_id, component_id='module', offset=0, limit=256):
        view = self.get_run(variant_id, run_id)
        s.require(type(offset) is int and offset >= 0 and type(limit) is int and 1 <= limit <= 5000, 'Invalid pagination')
        mapping = s.output_channels(component_id)
        path = self.path / 'runs' / run_id / 'trajectory.csv'
        frame = pd.read_csv(path) if path.exists() else pd.DataFrame()
        rows = frame.iloc[offset:offset+limit]
        data = [] if not len(rows) else rows[[a for a, _ in mapping.values()]].rename(columns={a: name for name, (a, _) in mapping.items()}).to_dict('records')
        units = {k: unit for k, (_, unit) in mapping.items()}
        tpath = self.path / 'runs' / run_id / 'thermal.csv'
        if view['thermal_output'] == 'available' and (component_id == 'module' or component_id in [f'cell_{k}' for k in range(1, 5)]):
            tframe = pd.read_csv(tpath)
            try:
                thermal_v1.validate_output(tframe, frame)
            except (ValueError, KeyError) as exc:
                raise s.RequestError('integrity_error', 'Invalid saved thermal output: ' + str(exc)) from exc
            trows = tframe.iloc[offset:offset+limit]
            if len(data) == len(trows):
                if component_id == 'module':
                    for i, tr in enumerate(trows.itertuples(index=False)):
                        data[i]['ambient_C'] = float(tr.ambient_C)
                        data[i]['heat_to_cells_W'] = float(tr.heat_to_cells_W)
                        data[i]['thermal_ledger_residual_J'] = float(tr.ledger_residual_J)
                    units['ambient_C'] = 'degC'
                    units['heat_to_cells_W'] = 'W'
                    units['thermal_ledger_residual_J'] = 'J'
                elif component_id in [f'cell_{k}' for k in range(1, 5)]:
                    k = int(component_id.split('_')[1])
                    for i, tr in enumerate(trows.itertuples(index=False)):
                        data[i]['temperature_C'] = float(getattr(tr, f'T{k}_C'))
                        data[i]['heat_W'] = float(getattr(tr, f'heat{k}_W'))
                    units['temperature_C'] = 'degC'
                    units['heat_W'] = 'W'
        return dict(run_id=run_id, variant_id=variant_id, component_id=component_id, snapshot_id=view['snapshot_id'],
            execution_status=view['execution_status'], freshness=view['freshness'], units=units,
            classification='simulated', total_samples=len(frame), offset=offset, rows=data,
            next_offset=offset+len(data) if offset+len(data) < len(frame) else None)

    def compare(self, selections):
        s.require(isinstance(selections, list) and len(selections) >= 2, 'Select at least two runs')
        state = self._state()
        snapshots, views = [], []
        for item in selections:
            s.keys(item, ['variant_id', 'run_id'], 'run selection')
            view = self.get_run(**item)
            s.require(view['execution_status'] == 'completed', 'Cannot compare an incomplete run', 'unsupported_request')
            views.append(view)
            snapshots.append(self._run_record(state, item['run_id'])[2])
        common = s.operating_conditions(snapshots[0]['effective_case'])
        differences = []
        for snapshot in snapshots[1:]:
            other = s.operating_conditions(snapshot['effective_case'])
            differences += [k for k in common if common[k] != other[k]]
            if snapshot['software']['id'] != snapshots[0]['software']['id']:
                differences.append('software/runtime')
            if snapshot.get('design', {}).get('thermal') != snapshots[0].get('design', {}).get('thermal'):
                differences.append('thermal parameters')
        s.require(not differences, 'Comparison requires identical operating conditions; differ: ' + ', '.join(sorted(set(differences))), 'unsupported_request')
        metrics = ['maximum_branch_current_A', 'minimum_cell_voltage_V', 'minimum_terminal_voltage_V', 'mean_delivered_power_W',
            'delivered_net_Wh', 'delivered_charge_Ah', 'cell_R0_loss_Wh', 'rail_loss_Wh', 'R1_loss_Wh', 'above_4_9A_cell_seconds']
        rows = []
        for view in views:
            summary = view['summary']
            thermal_m = summary.get('thermal', {})
            eng_m = summary.get('engineering', {}).get('metrics', {})
            eng_req = summary.get('engineering', {}).get('requirements', {}) or {}
            eng_req_map = {name: r.get('status') for name, r in eng_req.items()} if isinstance(eng_req, dict) else {}
            row = dict(variant_id=view['viewed_variant_id'], run_id=view['run_id'], snapshot_id=view['snapshot_id'],
                freshness=view['freshness'], **{k: summary[k] for k in metrics},
                requirement=summary['voltage_requirement']['status'], decision='insufficient evidence',
                peak_cell_temperature_C=thermal_m.get('peak_cell_temperature_C') if isinstance(thermal_m, dict) else None,
                maximum_temperature_spread_K=thermal_m.get('maximum_spread_K') if isinstance(thermal_m, dict) else None,
                current_imbalance_pct=(eng_m.get('current_imbalance_pct') or {}).get('value') if isinstance(eng_m.get('current_imbalance_pct'), dict) else None,
                engineering_requirements=eng_req_map)
            rows.append(row)
        return dict(kind='simulation comparison', conditions='identical operating conditions',
            condition_sha256=digest(common), ordered_results=rows,
            deltas_vs_first=[dict(run_id=r['run_id'], **{k: (r[k]-rows[0][k]) if (r[k] is not None and rows[0][k] is not None) else None for k in metrics + ['peak_cell_temperature_C', 'maximum_temperature_spread_K', 'current_imbalance_pct']}) for r in rows[1:]],
            evidence='Experimental validation awaiting suitable measurements; hypothetical changes, no repair ranking',
            historical_results=any(x['freshness'] == 'outdated' for x in views))

    def run_sensitivities(self, variant_id, expected_revision, plots=False):
        plan = read(self.path / 'assets/scenario_plan.json')
        # Persist the declaration before executing any sensitivity, then retain each full run.
        return dict(classification='sensitivity scenarios; not confidence intervals',
            declaration=plan['sensitivity_application'],
            runs=[self.run(variant_id, x['id'], expected_revision, plots) for x in plan['sensitivity_scenarios']])

    def compare_measurements(self, variant_id, run_id, source):
        from voltforge.simulation.measurements import compare_measurements
        view = self.get_run(variant_id, run_id)
        with self._writer() as state:
            mid = f'measurement_{len(state["measurements"])+1:04d}'
            folder = self.path / 'measurements' / mid
            s.require(not folder.exists(), 'Measurement destination already exists', 'conflict')
            result = compare_measurements(self.path / 'runs' / run_id, Path(source), folder)
            files = {p.relative_to(folder).as_posix(): file_hash(p) for p in folder.rglob('*') if p.is_file()}
            state['measurements'][mid] = dict(run_id=run_id, snapshot_id=view['snapshot_id'], artifacts=files)
            self._save(state)
        return dict(measurement_id=mid, run_id=run_id, freshness=view['freshness'], result=result)

    def investigate(self, variant_id, expected_revision, plan):
        from . import investigate
        return investigate.run(self, variant_id, expected_revision, plan)

    def get_investigation(self, investigation_id):
        from . import investigate
        return investigate.get(self, investigation_id)

    def list_investigations(self):
        state = self._state()
        return [dict(investigation_id=k, **v) for k, v in sorted(state.get('investigations', {}).items())]

    def open_case(self, investigation_id, case_id, variant_id, name):
        from . import investigate
        return investigate.open_case(self, investigation_id, case_id, variant_id, name)

    def export(self, selections, out):
        from .package import export_package
        return export_package(self, selections, out)


def dispatch(project_path, request):
    """JSON transport envelope; use directly in Python or through the CLI adapter."""
    try:
        s.keys(request, ['operation', 'arguments'], 'request')
        operation, args = request['operation'], request['arguments']
        s.require(isinstance(args, dict), 'arguments must be an object')
        if operation == 'load_reference':
            s.require(not args, 'load_reference takes no arguments')
            project = Project(project_path) if (Path(project_path) / 'project.json').exists() else Project.create_reference(project_path)
            result = project.inspect()
        else:
            allowed = {'inspect', 'validate_edit', 'apply_edit', 'create_variant', 'update_display', 'run', 'get_run',
                       'series', 'compare', 'run_sensitivities', 'compare_measurements', 'export',
                       'investigate', 'get_investigation', 'list_investigations', 'open_case'}
            s.require(isinstance(operation, str) and operation in allowed, 'Operation unavailable: ' + str(operation), 'unsupported_request')
            project = Project(project_path)
            result = getattr(project, operation)(**args)
        return dict(status='ok', result=result)
    except s.RequestError as exc:
        return dict(status='error', error=dict(code=exc.code, message=str(exc)))
    except (ValueError, TypeError, KeyError, OSError) as exc:
        return dict(status='error', error=dict(code='invalid_request', message=str(exc)))
