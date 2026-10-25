"""Loopback web adapter for the existing project contract. No electrical calculations."""
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import argparse
import json
import math
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
from copilot_contract import handle_request as evidence_request, unique_object, MAX_REQUEST_BYTES
from evidence_context import build_context
from local_assistant import handle_command

ASSETS = ROOT / 'web/editor'
OPERATIONS = {'inspect', 'validate_edit', 'apply_edit', 'create_variant', 'update_display', 'get_run', 'series', 'compare'}
MUTATIONS = {'apply_edit', 'create_variant', 'update_display'}
EVIDENCE_CONTEXT = '/api/evidence/context'
EVIDENCE_REQUEST = '/api/evidence/request'
ASSISTANT_REQUEST = '/api/assistant/request'
STATIC = {'/': 'index.html', '/index.html': 'index.html', '/style.css': 'style.css',
          '/app.js': 'app.js', '/state.mjs': 'state.mjs', '/favicon.svg': 'favicon.svg',
          '/evidence-panel.mjs': 'evidence-panel.mjs', '/evidence-state.mjs': 'evidence-state.mjs',
          '/evidence.css': 'evidence.css',
          '/assistant-panel.mjs': 'assistant-panel.mjs', '/assistant.css': 'assistant.css',
          '/measurements': 'measurements.html', '/measurements.js': 'measurements.js', '/measurements.css': 'measurements.css'}


def error(code, message):
    return {'status': 'error', 'error': {'code': code, 'message': message}}


def evidence_http_status(response):
    if response['status'] == 'ok':
        return 200
    return {'conflict': 409, 'stale_context': 409, 'integrity_error': 409,
            'not_found': 404, 'context_too_large': 413,
            'server_error': 500}.get(response['error']['code'], 400)


def browser_json_equal(supplied, authoritative):
    """Exact JSON value equality across the browser's single numeric type.

    JSON.parse/stringify changes Python's 1.0 to 1. This is not numerical
    tolerance: distinct finite values, booleans and unsafe integers never match.
    """
    numeric = (int, float)
    if type(supplied) in numeric and type(authoritative) in numeric:
        for number in (supplied, authoritative):
            if not math.isfinite(number):
                return False
            if (type(number) is int or number.is_integer()) and abs(number) > 9007199254740991:
                return False
        return supplied == authoritative
    if type(supplied) is not type(authoritative):
        return False
    if isinstance(supplied, dict):
        return (supplied.keys() == authoritative.keys()
                and all(browser_json_equal(value, authoritative[key]) for key, value in supplied.items()))
    if isinstance(supplied, list):
        return len(supplied) == len(authoritative) and all(
            browser_json_equal(left, right) for left, right in zip(supplied, authoritative))
    return supplied == authoritative


def browser_evidence_request(project_path, request):
    """Restore server numeric representation only after checking the full context."""
    if (not isinstance(request, dict) or set(request) != {'operation', 'context', 'arguments'}
            or request.get('operation') not in ('explain', 'preview_edit')):
        return evidence_request(project_path, request)
    supplied = request['context']
    if (not isinstance(supplied, dict) or set(supplied) != {'status', 'result'}
            or supplied.get('status') != 'ok' or not isinstance(supplied.get('result'), dict)):
        return evidence_request(project_path, request)
    selection = supplied['result'].get('selection')
    if (supplied['result'].get('schema') != 'voltforge.evidence_context/1'
            or not isinstance(selection, dict)
            or set(selection) != {'variant_id', 'run_id', 'component_id', 'limit'}):
        return evidence_request(project_path, request)
    fresh = build_context(project_path, **selection)
    if fresh['status'] != 'ok':
        return fresh
    try:
        matches = browser_json_equal(supplied, fresh)
    except (OverflowError, RecursionError):
        matches = False
    if not matches:
        return error('stale_context',
            'Evidence context changed or was modified; rebuild it before reviewing this request')
    # Never pass client-provided evidence values to the frozen contract. Its own
    # independent current-context check remains in force after this bridge.
    return evidence_request(project_path, {**request, 'context': fresh})


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
        self.worker = ThreadPoolExecutor(max_workers=1, thread_name_prefix='voltforge-editor')
        super().__init__(address, Handler)

    def server_close(self):
        self.worker.shutdown(wait=True)
        super().server_close()

    def start_job(self, request):
        if not isinstance(request, dict) or set(request) != {'operation', 'arguments'}:
            return error('invalid_request', 'Expected operation and arguments.'), 400
        op, args = request['operation'], request['arguments']
        if op not in ('run', 'export') or not isinstance(args, dict):
            return error('unsupported_request', 'Only run and export are background jobs.'), 400
        keys = {'variant_id', 'expected_revision', 'scenario_id'} if op == 'run' else {'selections'}
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

    def discard_rejected_body(self):
        # Closing a POST with unread incoming bytes can reset the connection on
        # Windows before a browser receives the 403. Discard bounded bytes only:
        # never parse or execute an untrusted request, and never wait indefinitely.
        try:
            length = int(self.headers.get('Content-Length', '0'))
        except ValueError:
            return
        if not 0 < length <= MAX_REQUEST_BYTES or self.headers.get('Transfer-Encoding'):
            return
        previous_timeout = self.connection.gettimeout()
        try:
            self.connection.settimeout(1.0)
            self.rfile.read(length)
        except OSError:
            pass
        finally:
            self.connection.settimeout(previous_timeout)

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
            self.discard_rejected_body()
            return self.send_json(error('forbidden', 'Reload the local editor to establish a session.'), 403)
        path = urlsplit(self.path).path
        body_limit = MAX_REQUEST_BYTES if path == EVIDENCE_REQUEST else 131072
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= body_limit or self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
                raise ValueError(f'Expected JSON body of at most {body_limit // 1024} KiB.')
            request = json.loads(self.rfile.read(length), object_pairs_hook=unique_object,
                parse_constant=lambda value: (_ for _ in ()).throw(ValueError('Nonfinite JSON')))
        except (ValueError, UnicodeDecodeError, RecursionError) as exc:
            return self.send_json(error('invalid_request', str(exc)), 400)
        if path == ASSISTANT_REQUEST:
            with self.server.gate:
                if self.server.active_job:
                    return self.send_json(error('conflict',
                        'A job is running. Wait before using local commands.'), 409)
                response = handle_command(self.server.project, request)
            return self.send_json(response, evidence_http_status(response))
        if path in (EVIDENCE_CONTEXT, EVIDENCE_REQUEST):
            if path == EVIDENCE_CONTEXT and (not isinstance(request, dict)
                    or set(request) != {'variant_id', 'run_id', 'component_id', 'limit'}):
                return self.send_json(error('invalid_request',
                    'Expected variant_id, run_id, component_id and limit.'), 400)
            # Use the same gate as manual edits and job creation. Holding it for
            # the read prevents a local editor mutation between context refresh
            # and preview/explanation; an executing job is explicitly rejected.
            # The evidence adapters also detect an external project writer lock.
            with self.server.gate:
                if self.server.active_job:
                    return self.send_json(error('conflict',
                        'A job is running. Wait before refreshing evidence or previewing edits.'), 409)
                response = (build_context(self.server.project, **request) if path == EVIDENCE_CONTEXT
                            else browser_evidence_request(self.server.project, request))
            return self.send_json(response, evidence_http_status(response))
        if not isinstance(request, dict) or set(request) != {'operation', 'arguments'}:
            return self.send_json(error('invalid_request', 'Expected operation and arguments.'), 400)
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
