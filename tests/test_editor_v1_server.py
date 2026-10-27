"""Real loopback transport tests for the v1 editor additions: static modules, investigation jobs and open_case."""
import importlib.util
import json
from pathlib import Path
import threading
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

spec = importlib.util.spec_from_file_location('editor_server', Path(__file__).parents[1] / 'scripts/run_editor.py')
editor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(editor)


@pytest.fixture
def server(tmp_path):
    srv = editor.EditorServer(('127.0.0.1', 0), tmp_path / 'project')
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    yield srv
    srv.shutdown()
    srv.server_close()
    thread.join()


def http(server, path='/api/request', payload=None, headers=None):
    defaults = {'Content-Type': 'application/json', 'X-Voltforge-Token': server.token}
    defaults.update(headers or {})
    request = Request(f'http://127.0.0.1:{server.server_port}{path}',
                      data=json.dumps(payload).encode() if payload is not None else None, headers=defaults)
    try:
        response = urlopen(request, timeout=30)
    except HTTPError as exc:
        response = exc
    body = response.read()
    return response.status, json.loads(body) if 'application/json' in response.headers['Content-Type'] else body, response.headers


def api(server, operation, **args):
    status, value, _ = http(server, payload={'operation': operation, 'arguments': args})
    assert status == 200, value
    assert value['status'] == 'ok', value
    return value['result']


def job(server, operation, **args):
    status, value, _ = http(server, '/api/jobs', dict(operation=operation, arguments=args))
    assert status == 202, value
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        _, value, _ = http(server, '/api/jobs/' + value['result'].get('job_id', value['result'].get('id')))
        if value['result']['state'] in ('completed', 'failed'):
            return value['result']
        time.sleep(.05)
    pytest.fail('Job did not finish')


def test_static_v1_modules(server):
    status, body, headers = http(server, '/assembly.mjs')
    assert status == 200 and headers['Content-Type'].startswith('text/javascript')
    assert b'export function assemblySVG' in body
    status, body, headers = http(server, '/panels.mjs')
    assert status == 200 and headers['Content-Type'].startswith('text/javascript')
    assert b'export function investigationHTML' in body


def test_investigation_job_and_open_case(server):
    rev = api(server, 'inspect', variant_id='A0')['revision_id']
    # Short software fixture so the two evaluated cases stay quick; production reference remains 360 s.
    shortened = api(server, 'apply_edit', variant_id='A0', expected_revision=rev,
                    edit=dict(target='scenario', id='module', property='load_profile',
                              value=[{'start_s': 0.0, 'end_s': 10.0, 'current_A': 14.55}], unit='A,s',
                              source='test', classification='assumed'))
    new_rev = shortened['revision_id']
    plan = {'rail_segments': ['rail_p_1'], 'added_resistance_ohm': [0.002], 'load_current_A': [], 'ambient_C': [], 'max_cases': 5}
    result = job(server, 'investigate', variant_id='A0', expected_revision=new_rev, plan=plan)
    assert result['state'] == 'completed'
    assert result['response']['result']['coverage']['evaluated'] == 2
    listed = api(server, 'list_investigations')
    assert len(listed) == 1 and listed[0]['investigation_id'] == 'inv_0001'
    record = api(server, 'get_investigation', investigation_id='inv_0001')
    assert len(record['cases']) == 2
    opened = api(server, 'open_case', investigation_id='inv_0001', case_id='case_0002', variant_id='C2', name='Degraded')
    assert opened['variant_id'] == 'C2'


def test_investigate_job_rejects_bad_arguments(server):
    rev = api(server, 'inspect', variant_id='A0')['revision_id']
    plan = {'rail_segments': ['rail_p_1'], 'added_resistance_ohm': [0.002], 'load_current_A': [], 'ambient_C': [], 'max_cases': 5}
    missing_plan = dict(variant_id='A0', expected_revision=rev)
    extra_key = dict(variant_id='A0', expected_revision=rev, plan=plan, scenario_id='nominal')
    for arguments in (missing_plan, extra_key):
        status, value, _ = http(server, '/api/jobs', dict(operation='investigate', arguments=arguments))
        assert status == 400 and value['error']['code'] == 'invalid_request', value
    assert api(server, 'list_investigations') == []  # nothing was started or recorded


def test_open_case_is_a_mutation_refused_while_a_job_runs(server):
    # An explicit busy latch exercises the gate without relying on thread timing.
    with server.gate:
        server.active_job = 'synthetic-test-job'
    assert http(server, payload=dict(operation='open_case', arguments={}))[0] == 409
    assert api(server, 'list_investigations') == []  # read-only investigation operations stay available
