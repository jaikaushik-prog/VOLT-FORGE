"""Loopback web adapter for the existing project contract. No electrical calculations."""
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import argparse
import json
import mimetypes
import secrets
import shutil
import sys
import threading
import time
from urllib.parse import urlsplit, parse_qs
import webbrowser

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'scripts'))
from voltforge.project import Project, dispatch
from measurement_viewer import MeasurementStore, MeasurementError
from voltforge.studio.store import Studio
from voltforge.studio.copilot import Copilot

ASSETS = ROOT / 'web/editor'
OPERATIONS = {'inspect', 'validate_edit', 'apply_edit', 'create_variant', 'update_display', 'get_run', 'series', 'compare',
              'get_investigation', 'list_investigations', 'open_case'}
MUTATIONS = {'apply_edit', 'create_variant', 'update_display', 'open_case'}
STATIC = {'/': 'index.html', '/index.html': 'index.html', '/style.css': 'style.css',
          '/app.js': 'app.js', '/state.mjs': 'state.mjs', '/assembly.mjs': 'assembly.mjs', '/panels.mjs': 'panels.mjs', '/workspace.mjs': 'workspace.mjs', '/favicon.svg': 'favicon.svg',
          '/measurements': 'measurements.html', '/measurements.js': 'measurements.js', '/measurements.css': 'measurements.css'}
STATIC.update({'/studio.js':'studio.js','/studio.css':'studio.css','/studio-canvas.mjs':'studio-canvas.mjs','/studio-walkthrough.mjs':'studio-walkthrough.mjs','/studio-cells.mjs':'studio-cells.mjs','/studio-protection.mjs':'studio-protection.mjs','/studio-conductors.mjs':'studio-conductors.mjs','/custom-cell-format.md':'custom-cell-format.md',
               '/studio-charts.mjs':'studio-charts.mjs','/studio-state.mjs':'studio-state.mjs'})


def error(code, message):
    return {'status': 'error', 'error': {'code': code, 'message': message}}


def project_destination(path):
    path = Path(path).resolve()
    protected = ['reports', 'src', 'scripts', 'tests', 'web', 'configs', 'data', '.git', '.codex', '.agents', 'github-upload', '1s4p Battery Module Measurement']
    if path == ROOT or path in ROOT.parents or any(path.is_relative_to(ROOT / p) for p in protected):
        raise ValueError('Choose a working project outside source, data and reports (default: workspace/editor_project).')
    return path


class EditorServer(ThreadingHTTPServer):
    daemon_threads = True
    # Windows SO_REUSEADDR can let two processes serve different projects on one port.
    allow_reuse_address = False

    def __init__(self, address, project):
        if address[0] != '127.0.0.1':
            raise ValueError('The editor only binds to 127.0.0.1.')
        self.project = project_destination(project)
        response = dispatch(self.project, {'operation': 'load_reference', 'arguments': {}})
        if response['status'] != 'ok':
            raise ValueError(response['error']['message'])
        self.token = secrets.token_urlsafe(32)
        self.jobs = {}
        self.downloads = {}
        self.gate = threading.Lock()
        self.active_job = None
        self.studio = Studio(self.project)
        self.copilot = Copilot(self.studio)
        self.worker = ThreadPoolExecutor(max_workers=1, thread_name_prefix='voltforge-editor')
        super().__init__(address, Handler)

    def server_close(self):
        self.worker.shutdown(wait=True)
        super().server_close()

    def start_job(self, request):
        if not isinstance(request, dict) or set(request) != {'operation', 'arguments'}:
            return error('invalid_request', 'Expected operation and arguments.'), 400
        op, args = request['operation'], request['arguments']
        if op not in ('run', 'export', 'investigate') or not isinstance(args, dict):
            return error('unsupported_request', 'Only run, export and investigate are background jobs.'), 400
        keys = {'run': {'variant_id', 'expected_revision', 'scenario_id'}, 'export': {'selections'},
                'investigate': {'variant_id', 'expected_revision', 'plan'}}[op]
        required = {'variant_id', 'expected_revision'} if op == 'run' else keys
        if set(args) - keys or not required <= set(args):
            return error('invalid_request', 'Invalid job arguments.'), 400
        with self.gate:
            if self.active_job:
                return error('conflict', 'A job is running. Wait before starting another job.'), 409
            jid = secrets.token_hex(12)
            self.jobs[jid] = dict(id=jid, operation=op, state='queued', started_at=time.time(), response=None)
            self.active_job = jid
            self.worker.submit(self.execute_job, jid, op, args)
        return {'status': 'ok', 'result': {'job_id': jid}}, 202

    def execute_job(self, jid, op, args):
        with self.gate:
            self.jobs[jid]['state'] = 'running'
        try:
            if op == 'run':
                response = dispatch(self.project, dict(operation='run', arguments={**args, 'plots': False}))
            elif op == 'investigate':
                response = dispatch(self.project, dict(operation='investigate', arguments=args))
            else:
                folder = self.project.parent / 'editor_exports' / jid
                response = dispatch(self.project, dict(operation='export', arguments={**args, 'out': str(folder)}))
                if response['status'] == 'ok':
                    archive = Path(shutil.make_archive(str(folder), 'zip', folder))
                    with self.gate:
                        self.downloads[jid] = archive
                    response['result']['download_url'] = '/api/download/' + jid
            failed_run = response.get('result', {}).get('execution_status') == 'failed'
            state = 'failed' if response['status'] == 'error' or failed_run else 'completed'
        except Exception as exc:
            response = error('server_error', f'{type(exc).__name__}: {exc}')
            state = 'failed'
        with self.gate:
            self.jobs[jid].update(state=state, response=response, finished_at=time.time())
            self.active_job = None


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass  # No request bodies or tokens in logs.

    def trusted_origin(self):
        allowed = {f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}'}
        host = self.headers.get('Host', '')
        origin = self.headers.get('Origin')
        return host in allowed and (origin is None or origin == 'http://' + host)

    def send_bytes(self, body, content_type, status=200, download=None):
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        if download:
            self.send_header('Content-Disposition', f'attachment; filename="{download}"')
        self.end_headers()
        self.wfile.write(body)

    def send_json(self, value, status=200):
        self.send_bytes(json.dumps(value, allow_nan=False).encode(), 'application/json; charset=utf-8', status)

    def do_GET(self):
        if not self.trusted_origin():
            return self.send_json(error('forbidden', 'Use the local editor address.'), 403)
        path = urlsplit(self.path).path
        if path in STATIC:
            file = ASSETS / STATIC[path]
            mime = {'.js': 'text/javascript', '.mjs': 'text/javascript', '.svg': 'image/svg+xml'}.get(file.suffix, mimetypes.guess_type(file.name)[0])
            return self.send_bytes(file.read_bytes(), (mime or 'application/octet-stream') + '; charset=utf-8')
        if path == '/api/measurements' or path.startswith('/api/measurements/'):
            try:
                store = MeasurementStore()
                if path == '/api/measurements':
                    return self.send_json(dict(status='ok', result=store.catalogue()))
                parts = path.split('/')[3:]
                if len(parts) == 2 and parts[1] == 'original':
                    record, data = store.original(parts[0])
                    return self.send_bytes(data, 'text/csv; charset=utf-8', download=Path(record['csv']).name)
                if len(parts) != 1:
                    raise MeasurementError('not_found', 'Unknown measurement resource.')
                query = parse_qs(urlsplit(self.path).query, keep_blank_values=True, strict_parsing=True)
                if set(query)-{'view','offset','limit','bins'} or any(len(v)!=1 for v in query.values()):
                    raise MeasurementError('invalid_request', 'Unknown or repeated measurement query parameter.')
                args = {k:(v[0] if k=='view' else int(v[0])) for k,v in query.items()}
                return self.send_json(dict(status='ok', result=store.read(parts[0], **args)))
            except MeasurementError as exc:
                status = {'protected_record':403, 'not_found':404, 'source_missing':404, 'integrity_error':409}.get(exc.code,400)
                return self.send_json(error(exc.code, str(exc)),status)
            except (ValueError, FileNotFoundError) as exc:
                return self.send_json(error('invalid_request', str(exc)),400)
        if path == '/api/session':
            with self.server.gate:
                active = self.server.active_job
            return self.send_json(dict(status='ok', result=dict(token=self.server.token, project=str(self.server.project),
                adapter_version='voltforge.editor/1', active_job=active)))
        if path == '/api/studio':
            return self.send_json(dict(status='ok',result=dict(**self.server.studio.catalog(),copilot=self.server.copilot.status())))
        if path.startswith('/api/studio/export/'):
            try:
                body=self.server.studio.export(path.rsplit('/',1)[-1])
                return self.send_bytes(body,'application/zip',download='volt-forge-experiment.zip')
            except ValueError as exc:
                return self.send_json(error('invalid_request',str(exc)),400)
        if path.startswith('/api/jobs/'):
            with self.server.gate:
                job = dict(self.server.jobs.get(path.rsplit('/', 1)[-1], {}))
            if job:
                return self.send_json({'status': 'ok', 'result': job})
        if path.startswith('/api/download/'):
            with self.server.gate:
                file = self.server.downloads.get(path.rsplit('/', 1)[-1])
            if file:
                return self.send_bytes(file.read_bytes(), 'application/zip', download='volt-forge-result-package.zip')
        self.send_json(error('not_found', 'Resource not found.'), 404)

    def do_POST(self):
        if not self.trusted_origin() or not secrets.compare_digest(self.headers.get('X-Voltforge-Token', ''), self.server.token):
            return self.send_json(error('forbidden', 'Reload the local editor to establish a session.'), 403)
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 131072 or self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
                raise ValueError('Expected JSON body of at most 128 KiB.')
            request = json.loads(self.rfile.read(length), parse_constant=lambda value: (_ for _ in ()).throw(ValueError('Nonfinite JSON')))
            if not isinstance(request, dict) or set(request) != {'operation', 'arguments'}:
                raise ValueError('Expected operation and arguments.')
        except (ValueError, UnicodeDecodeError) as exc:
            return self.send_json(error('invalid_request', str(exc)), 400)
        path = urlsplit(self.path).path
        if path == '/api/studio':
            return self.studio_request(request)
        if path == '/api/jobs':
            response, status = self.server.start_job(request)
            return self.send_json(response, status)
        if path != '/api/request':
            return self.send_json(error('not_found', 'Resource not found.'), 404)
        op = request['operation']
        if not isinstance(op, str) or op not in OPERATIONS:
            return self.send_json(error('unsupported_request', 'Operation is unavailable in the 2D editor.'), 400)
        if op in MUTATIONS:
            with self.server.gate:
                if self.server.active_job:
                    return self.send_json(error('conflict', 'A job is running. Wait before editing.'), 409)
                response = dispatch(self.server.project, request)
        else:
            response = dispatch(self.server.project, request)
        self.send_json(response, 200 if response['status'] == 'ok' else 400)

    def studio_request(self, request):
        op,args=request['operation'],request['arguments']
        methods={'create':self.server.studio.create,'open':self.server.studio.document,
                 'save':self.server.studio.save,'run':self.server.studio.run,'test':self.server.studio.test,
                 'investigate':self.server.studio.investigate,'compare':self.server.studio.compare,
                 'chat':self.server.copilot.chat,'apply_proposal':self.server.copilot.apply,
                 'create_cell':self.server.studio.create_cell,
                 'begin_investigation':self.server.studio.begin_investigation,'investigation':self.server.studio.investigation,
                 'investigate_case':self.server.studio.investigate_case,'open_investigation_case':self.server.studio.open_investigation_case}
        if not isinstance(op,str) or op not in methods or not isinstance(args,dict):
            return self.send_json(error('invalid_request','Choose an available studio action.'),400)
        try:
            response=methods[op](**args)
            return self.send_json(dict(status='ok',result=response))
        except TypeError:
            return self.send_json(error('invalid_request','This action has missing or unsupported inputs.'),400)
        except ValueError as exc:
            return self.send_json(error('invalid_request',str(exc)),400)
        except Exception:
            return self.send_json(error('server_error','This action could not finish. Reopen the design to check its saved state before retrying.'),500)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--project', type=Path, default=ROOT / 'workspace/editor_project')
    parser.add_argument('--open', action='store_true', help='Open the editor in your default browser')
    args = parser.parse_args()
    server = EditorServer(('127.0.0.1', args.port), args.project)
    url = f'http://127.0.0.1:{server.server_port}'
    print(f'VOLT-FORGE editor: {url}\nWorking project: {server.project}\nCtrl+C to stop.', flush=True)
    if args.open:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
