"""Serve the app's requests in the browser with the same Studio and Copilot as the local server."""
import base64
import json
import shutil
import sys
import traceback
import types
from pathlib import Path
from unittest.mock import MagicMock

# Only the exported report draws plots, so the real library loads on the first export.
plots = MagicMock(); plots.__version__ = 'not loaded in the browser'
sys.modules['matplotlib'] = plots; sys.modules['matplotlib.pyplot'] = MagicMock()

import voltforge.studio.store as store
from voltforge.studio.copilot import Copilot

store.fcntl = types.SimpleNamespace(flock=lambda *_: None, LOCK_EX=0, LOCK_UN=0)  # One tab, one user.
HOME = Path('/home/pyodide/volt')
PROJECT = HOME/'workspace'
shutil.copytree(HOME/'project', PROJECT)
JSON = 'application/json'


class NeedAI(BaseException):
    """Raised to hand the prompt to the worker, which alone can make the web request."""


class WebCopilot(Copilot):
    def __init__(self, studio):
        super().__init__(studio); self.provider = 'Gemini'; self.reply = None

    def _infer(self, prompt):
        if self.reply is None: raise NeedAI(prompt)
        reply, self.reply = self.reply, None
        if reply.get('error'): raise ValueError(reply['error'])
        response = json.loads(reply['text'])
        if not isinstance(response, dict) or set(response) != {'message', 'actions'} or not isinstance(response['message'], str) or not isinstance(response['actions'], list):
            raise ValueError('The AI returned an incomplete answer. Please try again.')
        if not 0 < len(response['message']) <= 12000 or len(response['actions']) > 24:
            raise ValueError('The AI answer was too long. Try a more specific change.')
        return response


studio = store.Studio(PROJECT)
copilot = WebCopilot(studio)
METHODS = dict(create=studio.create, open=studio.document, save=studio.save, run=studio.run, test=studio.test, investigate=studio.investigate, compare=studio.compare,
               chat=copilot.chat, apply_proposal=copilot.apply, create_cell=studio.create_cell, begin_investigation=studio.begin_investigation, investigation=studio.investigation,
               investigate_case=studio.investigate_case, open_investigation_case=studio.open_investigation_case)


def real_plots():
    for name in [m for m in sys.modules if m == 'matplotlib' or m.startswith('matplotlib.')]:
        if isinstance(sys.modules[name], MagicMock): del sys.modules[name]


def reply(status, value):
    return json.dumps(dict(status=status, type=JSON, body=json.dumps(value, allow_nan=False), binary=False))


def fail(status, code, message):
    return reply(status, dict(status='error', error=dict(code=code, message=message)))


def request(body):
    call = json.loads(body); operation, arguments = call['operation'], call['arguments']
    if operation not in METHODS or not isinstance(arguments, dict): return fail(400, 'invalid_request', 'Choose an available studio action.')
    try:
        return reply(200, dict(status='ok', result=METHODS[operation](**arguments)))
    except TypeError:
        return fail(400, 'invalid_request', 'This action has missing or unsupported inputs.')
    except ValueError as exc:
        return fail(400, 'invalid_request', str(exc))


def handle(path, method, body, answer):
    copilot.reply = json.loads(answer) if answer else None
    try:
        if path == '/api/session': return reply(200, dict(status='ok', result=dict(token='browser', project='browser', adapter_version='voltforge.editor/1', active_job=None)))
        if path == '/api/studio' and method == 'GET': return reply(200, dict(status='ok', result=dict(**studio.catalog(), copilot=copilot.status())))
        if path == '/api/studio': return request(body)
        if path.startswith('/api/studio/export/'):
            data = studio.export(path.rsplit('/', 1)[-1])
            return json.dumps(dict(status=200, type='application/zip', body=base64.b64encode(data).decode(), binary=True))
        return fail(404, 'not_found', 'Resource not found.')
    except NeedAI as need:
        return json.dumps(dict(ai_prompt=str(need)))
    except Exception:
        traceback.print_exc()
        return fail(500, 'server_error', 'This action could not finish. Reopen the design to check its saved state before retrying.')
