"""Real loopback checks for the read-only evidence and edit-preview routes."""
from concurrent.futures import ThreadPoolExecutor
import copy
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import shutil
import subprocess
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from voltforge.project import Project

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("editor_evidence_server", ROOT / "scripts/run_editor.py")
editor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(editor)

SELECTION = dict(variant_id="A0", run_id=None, component_id="module", limit=2)
EDIT = dict(target="connection", id="rail_p_1", property="resistance", value=.0005,
            unit="ohm", classification="assumed", source="Hypothetical software-test input")


@pytest.fixture
def server(tmp_path):
    server = editor.EditorServer(("127.0.0.1", 0), tmp_path / "project")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server
    server.shutdown()
    server.server_close()
    thread.join()


def http(server, path, payload=None, headers=None, raw=None):
    defaults = {"Content-Type": "application/json", "X-Voltforge-Token": server.token}
    defaults.update(headers or {})
    body = raw if raw is not None else json.dumps(payload).encode("utf-8")
    request = Request(f"http://127.0.0.1:{server.server_port}{path}", data=body, headers=defaults)
    try:
        response = urlopen(request, timeout=30)
    except HTTPError as exc:
        response = exc
    return response.status, json.loads(response.read())


def context(server, **selection):
    status, value = http(server, editor.EVIDENCE_CONTEXT, {**SELECTION, **selection})
    assert status == 200, value
    assert value["status"] == "ok"
    return value


def evidence(server, supplied, operation="explain", **arguments):
    return http(server, editor.EVIDENCE_REQUEST,
                dict(operation=operation, context=supplied, arguments=arguments))


def javascript_roundtrip(value):
    node = shutil.which("node") or str(Path("C:/Program Files/nodejs/node.exe"))
    process = subprocess.run([node, "-e",
        "process.stdout.write(JSON.stringify(JSON.parse(require('node:fs').readFileSync(0,'utf8'))))"],
        input=json.dumps(value), text=True, encoding="utf-8", capture_output=True, check=True)
    return json.loads(process.stdout)


def tree(path):
    return {p.relative_to(path).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in path.rglob("*") if p.is_file()}


def shortened_project(server, current=14.55):
    project = Project(server.project)
    project.apply_edit("A0", {**EDIT, "target": "scenario", "id": "module", "property": "load_profile",
        "value": [dict(start_s=0., end_s=2., current_A=current)], "unit": "A,s"},
        project.inspect()["revision_id"])
    return project


def test_configuration_explanation_and_preview_are_exact_and_read_only(server):
    before = tree(server.project)
    supplied = context(server)
    assert supplied == editor.build_context(server.project, **SELECTION)
    assert supplied["result"]["run"] is None
    assert all(value is None for value in supplied["result"]["project"]["design"]["requirements"].values())
    status, explanation = evidence(server, supplied)
    assert status == 200 and explanation["result"]["status"] == "configuration_only"
    assert explanation["result"]["requirement_check"] is None
    status, preview = evidence(server, supplied, "preview_edit", edit=EDIT)
    assert status == 200
    assert preview["result"]["status"] == "approval_required"
    assert preview["result"]["applied"] is False
    assert preview["result"]["simulation_started"] is False
    assert preview["result"]["predicted_effect"] is None
    assert tree(server.project) == before


def test_evidence_static_assets_keep_explicit_routes_mime_and_csp(server):
    before = tree(server.project)
    for name, mime in [("evidence-panel.mjs", "text/javascript"),
                       ("evidence-state.mjs", "text/javascript"), ("evidence.css", "text/css")]:
        with urlopen(f"http://127.0.0.1:{server.server_port}/{name}", timeout=30) as response:
            assert response.status == 200
            assert response.headers["Content-Type"].startswith(mime)
            assert "script-src 'self'" in response.headers["Content-Security-Policy"]
            assert "style-src 'self'" in response.headers["Content-Security-Policy"]
            assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]
            assert response.headers["X-Content-Type-Options"] == "nosniff"
            assert response.headers["Cache-Control"] == "no-store"
            assert response.read() == (ROOT / "web/editor" / name).read_bytes()
    for path in ["/../evidence-panel.mjs", "/%2e%2e/evidence.css", "/web/editor/evidence-state.mjs",
                 "/evidence-panel.mjs/../app.js", "/../../scripts/evidence_context.py"]:
        request = Request(f"http://127.0.0.1:{server.server_port}{path}")
        with pytest.raises(HTTPError) as failure:
            urlopen(request, timeout=30)
        assert failure.value.code == 404
        assert json.loads(failure.value.read())["error"]["code"] == "not_found"
    assert tree(server.project) == before


def test_saved_run_units_requirements_and_preview_invalidation_remain_backend_values(server):
    project = shortened_project(server)
    saved = project.run(expected_revision=project.inspect()["revision_id"], plots=False)
    before = tree(server.project)
    supplied = context(server, run_id=saved["run_id"], component_id="cell_1")
    assert supplied["result"]["series"] == project.series("A0", saved["run_id"], "cell_1", limit=2)
    assert supplied["result"]["series"]["units"]["current_A"] == "A"
    status, response = evidence(server, supplied)
    assert status == 200
    assert response["result"]["requirement_check"]["status"] == "requirement not configured"
    assert response["result"]["coverage"] == saved["summary"]["coverage"]
    assert response["result"]["decision"] == "insufficient evidence"
    status, preview = evidence(server, supplied, "preview_edit", edit=EDIT)
    assert status == 200 and saved["run_id"] in preview["result"]["validation"]["invalidated_run_ids"]
    assert tree(server.project) == before


def test_forged_and_stale_context_return_conflict_without_mutation(server):
    supplied = context(server)
    forged = copy.deepcopy(supplied)
    forged["result"]["project"]["design"]["connections"]["rail_p_1"]["resistance"]["value"] = .9
    from scripts.evidence_context import context_digest
    forged["result"]["context_id"] = context_digest(forged["result"])
    before = tree(server.project)
    for operation, args in [("explain", {}), ("preview_edit", {"edit": EDIT})]:
        status, response = evidence(server, forged, operation, **args)
        assert status == 409 and response["error"]["code"] == "stale_context"
    assert tree(server.project) == before
    project = Project(server.project)
    project.apply_edit("A0", EDIT, project.inspect()["revision_id"])
    before = tree(server.project)
    status, response = evidence(server, supplied)
    assert status == 409 and response["error"]["code"] == "stale_context"
    assert tree(server.project) == before


def test_javascript_numeric_roundtrip_reaches_unchanged_contract_with_authoritative_context(server):
    project = shortened_project(server)
    saved = project.run(expected_revision=project.inspect()["revision_id"], plots=False)
    supplied = context(server, run_id=saved["run_id"])
    transported = javascript_roundtrip(supplied)
    assert json.dumps(transported, sort_keys=True) != json.dumps(supplied, sort_keys=True)
    assert transported["result"]["context_id"] == supplied["result"]["context_id"]
    # Demonstrate the original strict Python contract remains unchanged: browser
    # numeric spelling needs the HTTP bridge, not a weakened canonical check.
    strict = editor.evidence_request(server.project,
        dict(operation="explain", context=transported, arguments={}))
    assert strict["error"]["code"] == "stale_context"
    before = tree(server.project)
    for operation, args in [("explain", {}), ("preview_edit", {"edit": EDIT})]:
        status, response = evidence(server, transported, operation, **args)
        assert status == 200
        assert response["result"]["binding"]["context_id"] == supplied["result"]["context_id"]
    assert tree(server.project) == before


@pytest.mark.parametrize("change", ["bool_to_number", "number_to_bool", "tiny_numeric", "context_hash", "unsafe_integer", "unsafe_float"])
def test_browser_bridge_rejects_non_roundtrip_changes_without_mutation(server, change):
    supplied = javascript_roundtrip(context(server))
    if change == "bool_to_number":
        supplied["result"]["project"]["capabilities"]["electrical"] = 1
    elif change == "number_to_bool":
        supplied["result"]["project"]["design"]["cells"]["cell_1"]["initial_polarization"]["value"] = False
    elif change == "tiny_numeric":
        resistance = supplied["result"]["project"]["design"]["connections"]["rail_p_1"]["resistance"]
        resistance["value"] = math.nextafter(resistance["value"], math.inf)
    elif change == "context_hash":
        supplied["result"]["context_id"] = "sha256:" + "0" * 64
    else:
        resistance = supplied["result"]["project"]["design"]["connections"]["rail_p_1"]["resistance"]
        resistance["value"] = 9007199254740992 if change == "unsafe_integer" else float(9007199254740992)
    before = tree(server.project)
    status, response = evidence(server, supplied)
    assert status == 409 and response["error"]["code"] == "stale_context"
    assert tree(server.project) == before


def test_browser_bridge_rejects_matching_unsafe_integer_in_authoritative_context(server):
    project = Project(server.project)
    project.apply_edit("A0", {**EDIT, "value": 9007199254740992}, project.inspect()["revision_id"])
    supplied = javascript_roundtrip(context(server))
    before = tree(server.project)
    status, response = evidence(server, supplied)
    assert status == 409 and response["error"]["code"] == "stale_context"
    assert tree(server.project) == before


def test_inherited_and_failed_runs_keep_statuses_separate_from_http_success(server):
    project = shortened_project(server)
    saved = project.run(expected_revision=project.inspect()["revision_id"], plots=False)
    project.create_variant("A0", "A1", "Inherited evidence", project.inspect()["revision_id"])
    inherited = context(server, variant_id="A1", run_id=saved["run_id"])
    status, explained = evidence(server, inherited)
    assert status == 200 and explained["result"]["run_status"]["freshness"] == "outdated"
    assert inherited["result"]["run"]["owner_variant_id"] == "A0"
    project = shortened_project(server, 100000.)
    failed = project.run(expected_revision=project.inspect()["revision_id"], plots=False)
    supplied = context(server, run_id=failed["run_id"])
    before = tree(server.project)
    status, explained = evidence(server, supplied)
    assert status == 200
    assert explained["result"]["run_status"]["execution_status"] == "failed"
    assert explained["result"]["run_status"]["freshness"] == "current"
    assert supplied["result"]["series"]["total_samples"] < 9
    assert tree(server.project) == before


def test_busy_jobs_and_external_writer_are_conflicts_on_both_routes(server):
    supplied = context(server)
    before = tree(server.project)
    with server.gate:
        server.active_job = "declared-test-busy-latch"
    try:
        for path, request in [(editor.EVIDENCE_CONTEXT, SELECTION),
                (editor.EVIDENCE_REQUEST, dict(operation="explain", context=supplied, arguments={}))]:
            status, response = http(server, path, request)
            assert status == 409 and response["error"]["code"] == "conflict"
    finally:
        with server.gate:
            server.active_job = None
    assert tree(server.project) == before
    lock = server.project / "project.lock"
    lock.write_text("synthetic external writer", encoding="utf-8")
    try:
        status, response = http(server, editor.EVIDENCE_CONTEXT, SELECTION)
        assert status == 409 and response["error"]["code"] == "conflict"
        status, response = evidence(server, supplied)
        assert status == 409 and response["error"]["code"] == "conflict"
    finally:
        lock.unlink()
    assert tree(server.project) == before


def test_gate_serializes_manual_editor_mutation_after_evidence_collection(server, monkeypatch):
    entered = threading.Event()
    release = threading.Event()
    manual_dispatched = threading.Event()
    original_context, original_dispatch = editor.build_context, editor.dispatch

    def held_context(*args, **kwargs):
        entered.set()
        assert release.wait(10), "test did not release evidence gate"
        return original_context(*args, **kwargs)

    def traced_dispatch(path, request):
        if request.get("operation") == "update_display":
            manual_dispatched.set()
        return original_dispatch(path, request)

    monkeypatch.setattr(editor, "build_context", held_context)
    monkeypatch.setattr(editor, "dispatch", traced_dispatch)
    with ThreadPoolExecutor(max_workers=2) as pool:
        evidence_future = pool.submit(context, server)
        assert entered.wait(10)
        manual_future = pool.submit(http, server, "/api/request", dict(operation="update_display",
            arguments=dict(display=dict(positions={}, camera={"zoom": 2}, selection=[]))))
        try:
            assert not manual_dispatched.wait(.15)
        finally:
            release.set()
        assert evidence_future.result(timeout=10)["status"] == "ok"
        assert manual_future.result(timeout=10)[0] == 200
    assert manual_dispatched.is_set()


@pytest.mark.parametrize("operation", ["apply_edit", "run", "export", "approve", "run_thermal", "optimize"])
def test_no_executor_or_unknown_operation_is_exposed(server, operation):
    supplied = context(server)
    before = tree(server.project)
    status, response = evidence(server, supplied, operation)
    assert status == 400 and response["error"]["code"] == "unsupported_request"
    assert tree(server.project) == before


@pytest.mark.parametrize("path", ["/api/evidence/context", "/api/evidence/request"])
@pytest.mark.parametrize("headers", [{"X-Voltforge-Token": "wrong"}, {"Origin": "https://untrusted.example"},
                                     {"Host": "untrusted.example"}])
def test_session_origin_and_host_guards_are_shared(server, path, headers):
    status, response = http(server, path, SELECTION, headers=headers)
    assert status == 403 and response["error"]["code"] == "forbidden"


def test_strict_json_and_selection_validation_reject_ambiguous_requests(server):
    before = tree(server.project)
    malformed = [
        b'{"variant_id":"A0","variant_id":"A1","run_id":null,"component_id":"module","limit":2}',
        b'{"variant_id":"A0","run_id":null,"component_id":"module","limit":NaN}',
        b'[' * 1500 + b'0' + b']' * 1500,
    ]
    for body in malformed:
        status, response = http(server, editor.EVIDENCE_CONTEXT, raw=body)
        assert status == 400 and response["error"]["code"] == "invalid_request"
    for request in [{**SELECTION, "project_path": "data/raw"}, {"variant_id": "A0"},
                    {**SELECTION, "limit": True}]:
        status, response = http(server, editor.EVIDENCE_CONTEXT, request)
        assert status == 400 and response["error"]["code"] == "invalid_request"
    status, response = http(server, editor.EVIDENCE_CONTEXT, {**SELECTION, "variant_id": "MISSING"})
    assert status == 404 and response["error"]["code"] == "not_found"
    status, response = http(server, editor.EVIDENCE_CONTEXT, {**SELECTION, "component_id": "temperature"})
    assert status == 400 and response["error"]["code"] == "unsupported_request"
    assert tree(server.project) == before


def test_full_context_request_allows_1mib_while_legacy_limit_stays_128kib(server):
    project = Project(server.project)
    project.apply_edit("A0", {**EDIT, "source": "x" * 140000}, project.inspect()["revision_id"])
    supplied = context(server)
    request = dict(operation="explain", context=supplied, arguments={})
    assert 131072 < len(json.dumps(request).encode()) < editor.MAX_REQUEST_BYTES
    before = tree(server.project)
    status, response = http(server, editor.EVIDENCE_REQUEST, request)
    assert status == 200 and response["result"]["status"] == "configuration_only"
    for path, length in [(editor.EVIDENCE_REQUEST, editor.MAX_REQUEST_BYTES + 1),
                         (editor.EVIDENCE_CONTEXT, 131073), ("/api/request", 131073)]:
        status, response = http(server, path, {}, headers={"Content-Length": str(length)})
        assert status == 400 and response["error"]["code"] == "invalid_request"
    # Valid legacy requests and manual apply remain their existing independent route.
    status, response = http(server, "/api/request", dict(operation="inspect", arguments={}))
    assert status == 200 and response["result"]["variant_id"] == "A0"
    assert tree(server.project) == before
