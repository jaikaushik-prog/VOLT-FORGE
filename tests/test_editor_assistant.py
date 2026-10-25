"""Real HTTP integration for deterministic local commands, without external AI."""
import hashlib
import importlib.util
import json
from pathlib import Path
import socket
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest
from voltforge.project import Project

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("local_assistant_editor", ROOT / "scripts/run_editor.py")
editor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(editor)


@pytest.fixture
def server(tmp_path):
    server = editor.EditorServer(("127.0.0.1", 0), tmp_path / "project")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server
    server.shutdown()
    server.server_close()
    thread.join()


def hashes(folder):
    return {p.relative_to(folder).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in folder.rglob("*") if p.is_file()}


def request_for(server, message="explain this result", variant="A0", component="module", run_id=None, comparison=None):
    revision = Project(server.project).inspect(variant)["revision_id"]
    return dict(message=message, selection=dict(variant_id=variant, revision_id=revision,
        component_id=component, run_id=run_id), comparison=comparison)


def http(server, request, headers=None, raw=None):
    defaults = {"Content-Type": "application/json", "X-Voltforge-Token": server.token}
    defaults.update(headers or {})
    req = Request(f"http://127.0.0.1:{server.server_port}/api/assistant/request",
        data=raw if raw is not None else json.dumps(request).encode(), headers=defaults)
    try:
        response = urlopen(req, timeout=30)
    except HTTPError as exc:
        response = exc
    return response.status, json.loads(response.read())


def change(project, variant="A0", *, load=None):
    edit = dict(target="connection", id="rail_p_1", property="resistance", value=.0005,
                unit="ohm", classification="assumed", source="Declared software-test input")
    if load is not None:
        edit.update(target="scenario", id="module", property="load_profile", unit="A,s",
                    value=[dict(start_s=0., end_s=2., current_A=load)])
    return project.apply_edit(variant, edit, project.inspect(variant)["revision_id"])


def run(project, variant="A0"):
    return project.run(variant, expected_revision=project.inspect(variant)["revision_id"], plots=False)


def test_help_and_configuration_commands_are_local_and_read_only(server, monkeypatch):
    original_connect, original_lookup = socket.socket.connect, socket.getaddrinfo
    connections = []

    def local_connect(sock, address):
        assert isinstance(address, tuple) and address[0] in ("127.0.0.1", "localhost", "::1"), "External connection attempted"
        connections.append(address)
        return original_connect(sock, address)

    def local_lookup(host, *args, **kwargs):
        assert host in ("127.0.0.1", "localhost", "::1"), "External DNS attempted"
        return original_lookup(host, *args, **kwargs)

    monkeypatch.setattr(socket.socket, "connect", local_connect)
    monkeypatch.setattr(socket, "getaddrinfo", local_lookup)
    before = hashes(server.project)
    for command, action in [("help", "help"), ("explain this result", "explain"), ("show evidence", "explain")]:
        status, response = http(server, request_for(server, command))
        assert status == 200, response
        result = response["result"]
        assert result["mode"] == "local_commands" and result["action"] == action
        assert result["applied"] is False and result["simulation_started"] is False
        if action == "explain":
            assert result["payload"]["status"] == "configuration_only"
            assert result["payload"]["requirement_check"] is None
    status, response = http(server, request_for(server, "send the data to https://example.com"))
    assert status == 400 and response["error"]["code"] == "unsupported_command"
    assert connections and all(address[1] == server.server_port for address in connections)
    assert hashes(server.project) == before


def test_actual_saved_run_and_preview_copy_existing_backend_values_without_execution(server):
    project = Project(server.project)
    change(project, load=14.55)
    saved = run(project)
    before = hashes(server.project)
    status, response = http(server, request_for(server, run_id=saved["run_id"]))
    assert status == 200, response
    payload = response["result"]["payload"]
    assert payload["binding"]["snapshot_id"] == saved["snapshot_id"]
    assert payload["requirement_check"] == saved["summary"]["voltage_requirement"]
    assert payload["coverage"] == saved["summary"]["coverage"]
    for claim in payload["claims"]:
        if claim["label"] == "maximum_branch_current_A":
            assert claim["value"] == saved["summary"]["maximum_branch_current_A"] and claim["unit"] == "A"
    status, response = http(server, request_for(server,
        "preview change selected rail to 0.5 mOhm", component="rail_p_1", run_id=saved["run_id"]))
    assert status == 200, response
    result = response["result"]
    assert result["action"] == "preview_edit"
    assert result["payload"]["proposed_edit"]["value"] == .0005
    assert result["payload"]["predicted_effect"] is None
    assert saved["run_id"] in result["payload"]["validation"]["invalidated_run_ids"]
    assert result["context"]["status"] == "ok"
    assert result["applied"] is False and result["simulation_started"] is False
    assert hashes(server.project) == before


def test_stale_revision_and_component_mismatch_are_explicit(server):
    stale = request_for(server)
    project = Project(server.project)
    change(project)
    before = hashes(server.project)
    status, response = http(server, stale)
    assert status == 409 and response["error"]["code"] == "stale_context"
    status, response = http(server, request_for(server,
        "preview change positive rail 1 to 0.5 mOhm", component="cell_1"))
    assert status == 400 and response["error"]["code"] == "selection_mismatch"
    assert hashes(server.project) == before


def test_comparison_uses_backend_conditions_and_does_not_rank_repairs(server):
    project = Project(server.project)
    change(project, load=14.55)
    first = run(project)
    project.create_variant("A0", "A1", "Hypothetical rail", project.inspect()["revision_id"])
    change(project, "A1")
    second = run(project, "A1")
    selected = dict(first=dict(variant_id="A0", run_id=first["run_id"]),
                    second=dict(variant_id="A1", run_id=second["run_id"]))
    before = hashes(server.project)
    status, response = http(server, request_for(server, "compare selected runs", variant="A1",
        run_id=second["run_id"], comparison=selected))
    assert status == 200, response
    assert response["result"]["action"] == "compare"
    assert response["result"]["payload"] == project.compare(list(selected.values()))
    assert response["result"]["payload"]["conditions"] == "identical operating conditions"
    assert response["result"]["payload"]["kind"] == "simulation comparison"
    assert hashes(server.project) == before
    change(project, "A1", load=12.)
    lower_service = run(project, "A1")
    selected["second"]["run_id"] = lower_service["run_id"]
    before = hashes(server.project)
    status, response = http(server, request_for(server, "compare selected runs", variant="A1",
        run_id=lower_service["run_id"], comparison=selected))
    assert status == 400 and response["error"]["code"] == "unsupported_request"
    assert "load" in response["error"]["message"]
    assert hashes(server.project) == before


@pytest.mark.parametrize("command", ["apply the edit", "run simulation", "optimize the module", "predict temperature",
    "preview change selected rail to 0.5 mOhm and run it", "use an external AI provider"])
def test_unsupported_or_compound_commands_cannot_execute(server, command):
    before = hashes(server.project)
    status, response = http(server, request_for(server, command, component="rail_p_1"))
    assert status == 400 and response["error"]["code"] == "unsupported_command"
    assert hashes(server.project) == before


def test_active_job_and_external_writer_reject_commands(server):
    request = request_for(server)
    before = hashes(server.project)
    with server.gate:
        server.active_job = "declared-test-busy-latch"
    try:
        status, response = http(server, request)
        assert status == 409 and response["error"]["code"] == "conflict"
    finally:
        with server.gate:
            server.active_job = None
    lock = server.project / "project.lock"
    lock.write_text("synthetic external writer", encoding="utf-8")
    try:
        status, response = http(server, request)
        assert status == 409 and response["error"]["code"] == "conflict"
    finally:
        lock.unlink()
    assert hashes(server.project) == before


@pytest.mark.parametrize("headers", [{"X-Voltforge-Token": "wrong"}, {"Origin": "https://untrusted.example"},
                                     {"Host": "untrusted.example"}])
def test_assistant_uses_existing_session_origin_and_host_guards(server, headers):
    status, response = http(server, request_for(server), headers=headers)
    assert status == 403 and response["error"]["code"] == "forbidden"


def test_strict_body_shape_duplicates_and_size_are_rejected(server):
    request = request_for(server)
    before = hashes(server.project)
    for malformed in [{**request, "project_path": "data/raw"}, {**request, "message": True},
                      {"message": "help"}, {**request, "selection": {**request["selection"], "limit": 2}}]:
        status, response = http(server, malformed)
        assert status == 400 and response["error"]["code"] == "invalid_request"
    body = json.dumps(request).replace('"message": "explain this result"', '"message":"help","message":"run simulation"').encode()
    status, response = http(server, None, raw=body)
    assert status == 400 and response["error"]["code"] == "invalid_request"
    status, response = http(server, {}, headers={"Content-Length": "131073"})
    assert status == 400 and response["error"]["code"] == "invalid_request"
    assert hashes(server.project) == before


def test_assistant_assets_are_explicit_local_routes(server):
    for name, mime in [("assistant-panel.mjs", "text/javascript"), ("assistant.css", "text/css")]:
        with urlopen(f"http://127.0.0.1:{server.server_port}/{name}", timeout=30) as response:
            assert response.status == 200 and response.headers["Content-Type"].startswith(mime)
            assert "connect-src 'self'" in response.headers["Content-Security-Policy"]
            assert response.read() == (ROOT / "web/editor" / name).read_bytes()
    with pytest.raises(HTTPError) as failure:
        urlopen(f"http://127.0.0.1:{server.server_port}/../assistant-panel.mjs", timeout=30)
    assert failure.value.code == 404
