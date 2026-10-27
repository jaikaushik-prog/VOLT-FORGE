"""Real loopback transport tests; all measurements remain synthetic/unused."""
import importlib.util
import io
import json
from pathlib import Path
import threading
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen
import zipfile

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


def edit(value, target='connection', id='rail_p_1', property='resistance', unit='ohm'):
    return dict(target=target, id=id, property=property, value=value, unit=unit,
                source='Synthetic software integration test assumption', classification='assumed')


def test_http_complete_revision_run_compare_and_download(server):
    a0 = api(server, 'inspect')
    # Short software fixture; production reference remains 360 s.
    a0 = api(server, 'apply_edit', variant_id='A0', expected_revision=a0['revision_id'],
             edit=edit([dict(start_s=0, end_s=2, current_A=14.55)], 'scenario', 'module', 'load_profile', 'A,s'))
    r0 = job(server, 'run', variant_id='A0', expected_revision=a0['revision_id'])
    assert r0['state'] == 'completed'
    r0 = r0['response']['result']
    assert r0['summary']['voltage_requirement']['status'] == 'requirement not configured'
    a1 = api(server, 'create_variant', source_variant='A0', variant_id='A1', name='One rail change', expected_revision=a0['revision_id'])
    assert not a1['current_run_ids'] and a1['runs'][0]['freshness'] == 'outdated'
    args = dict(variant_id='A1', expected_revision=a1['revision_id'], edit=edit(.0005))
    assert api(server, 'validate_edit', **args)['physics_changed']
    a1 = api(server, 'apply_edit', **args)
    r1 = job(server, 'run', variant_id='A1', expected_revision=a1['revision_id'])['response']['result']
    series = api(server, 'series', variant_id='A1', run_id=r1['run_id'], component_id='cell_2', limit=2)
    assert series['units']['current_A'] == 'A' and series['next_offset'] == 2
    assert series['freshness'] == 'current' and len(series['rows']) == 2
    display = api(server, 'update_display', display=dict(positions={'cell_2':[301,151]}, camera={}, selection=['cell_2']))
    assert display['physics_changed'] is False
    assert api(server, 'get_run', variant_id='A1', run_id=r1['run_id'])['freshness'] == 'current'
    selections = [dict(variant_id='A0', run_id=r0['run_id']), dict(variant_id='A1', run_id=r1['run_id'])]
    comparison = api(server, 'compare', selections=selections)
    assert comparison['conditions'] == 'identical operating conditions'
    assert comparison['deltas_vs_first'][0]['maximum_branch_current_A'] != 0
    exported = job(server, 'export', selections=selections)
    assert exported['state'] == 'completed'
    status, archive, headers = http(server, exported['response']['result']['download_url'])
    assert status == 200 and 'attachment' in headers['Content-Disposition']
    with zipfile.ZipFile(io.BytesIO(archive)) as z:
        assert {'replay.py', 'export_manifest.json', 'comparison.json'} <= set(z.namelist())
        assert not any('data/raw' in name for name in z.namelist())
    # Changing the owned design invalidates its prior result, but never A0.
    api(server, 'apply_edit', variant_id='A1', expected_revision=a1['revision_id'], edit=edit(.0006))
    assert api(server, 'get_run', variant_id='A1', run_id=r1['run_id'])['freshness'] == 'outdated'
    assert api(server, 'get_run', variant_id='A0', run_id=r0['run_id'])['freshness'] == 'current'


@pytest.mark.parametrize('path,payload,headers,code', [
    ('/api/request', {'operation':'inspect','arguments':{}}, {'X-Voltforge-Token':'wrong'}, 403),
    ('/api/request', {'operation':'inspect','arguments':{}}, {'Origin':'https://untrusted.example'}, 403),
    ('/api/session', None, {'Host':'untrusted.example'}, 403),
    ('/api/request', {'operation':'export','arguments':{'out':'reports'}}, {}, 400),
    ('/api/jobs', {'operation':'export','arguments':{'out':'reports','selections':[]}}, {}, 400),
    ('/api/jobs', {'operation':'run','arguments':{'variant_id':'A0'}}, {}, 400),
    ('/api/request', {'operation':'compare_measurements','arguments':{'source':'data/raw'}}, {}, 400),
    ('/api/request', [], {}, 400),
    ('/../../configs/reference_initial_state_v1.lock.json', None, {}, 404),
])
def test_rejects_untrusted_and_out_of_scope_requests(server,path,payload,headers,code):
    assert http(server,path,payload,headers)[0] == code


def test_static_session_and_busy_mutations(server):
    with pytest.raises(OSError):
        editor.EditorServer(('127.0.0.1', server.server_port), server.project)
    status, body, headers = http(server, '/')
    assert status == 200 and b'Battery workspace' in body
    assert "frame-ancestors 'none'" in headers['Content-Security-Policy']
    assert http(server, '/state.mjs')[2]['Content-Type'].startswith('text/javascript')
    module_status, module_body, module_headers = http(server, '/workspace.mjs')
    assert module_status == 200 and b'export function loadProfile' in module_body
    assert module_headers['Content-Type'].startswith('text/javascript')
    assert http(server, '/api/session')[1]['result']['token'] == server.token
    # An explicit busy latch exercises the gate without relying on thread timing.
    with server.gate:
        server.active_job = 'synthetic-test-job'
    assert http(server, payload=dict(operation='update_display',arguments={}))[0] == 409
    assert http(server, '/api/jobs',dict(operation='run',arguments={'variant_id':'A0','expected_revision':'x'}))[0] == 409
    assert api(server, 'inspect')['variant_id'] == 'A0'


def test_failed_run_is_distinct_from_successful_transport(server):
    a0 = api(server, 'inspect')
    a0 = api(server, 'apply_edit', variant_id='A0', expected_revision=a0['revision_id'],
             edit=edit([dict(start_s=0,end_s=360,current_A=1000)], 'scenario','module','load_profile','A,s'))
    result = job(server,'run',variant_id='A0',expected_revision=a0['revision_id'])
    assert result['state'] == 'failed'
    assert result['response']['status'] == 'ok'
    assert result['response']['result']['execution_status'] == 'failed'
    partial = api(server, 'series', variant_id='A0', run_id=result['response']['result']['run_id'])
    assert partial['execution_status'] == 'failed'
    assert partial['total_samples'] < 1441  # Stop at undefined SOC, never invent the remaining trajectory.


@pytest.mark.parametrize('name',['reports/editor_v1/project','reports/product_integration_v1/demo/project','src/new','configs/new','.git/new'])
def test_editor_cannot_mutate_source_or_recorded_reports(name):
    with pytest.raises(ValueError,match='working project'):
        editor.project_destination(editor.ROOT / name)
