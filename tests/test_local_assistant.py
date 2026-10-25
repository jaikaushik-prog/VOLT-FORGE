"""Predeclared grammar and read-only integration tests; no experimental validation."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import local_assistant as assistant
from scripts.copilot_contract import handle_request, value_at
from scripts.evidence_context import build_context
from voltforge.project import Project, dispatch
from voltforge.project.schema import RequestError

EVALUATION = json.loads((ROOT / "configs/local_assistant_eval_v1.json").read_text(encoding="utf-8"))


def hashes(folder):
    return {p.relative_to(folder).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in folder.rglob("*") if p.is_file()}


def change(value=0.0005, **fields):
    result = dict(target="connection", id="rail_p_1", property="resistance", value=value, unit="ohm",
                  source="Synthetic local-command software-test input", classification="assumed")
    result.update(fields)
    return result


def apply(project, edit, variant="A0"):
    return project.apply_edit(variant, edit, project.inspect(variant)["revision_id"])


def run(project, variant="A0"):
    return project.run(variant, expected_revision=project.inspect(variant)["revision_id"], plots=False)


def request(project, message="show evidence", component="module", variant="A0", run_id=None, comparison=None):
    return dict(message=message, selection=dict(variant_id=variant, revision_id=project.inspect(variant)["revision_id"],
                                               component_id=component, run_id=run_id), comparison=comparison)


def ok(response):
    assert response["status"] == "ok", response
    return response["result"]


@pytest.fixture
def project(tmp_path):
    project = Project.create_reference(tmp_path / "project")
    apply(project, change(target="scenario", id="module", property="load_profile", unit="A,s",
                          value=[dict(start_s=0., end_s=2., current_A=14.55)]))
    return project


@pytest.mark.parametrize("case", EVALUATION["accepted"], ids=lambda case: case["message"])
def test_predeclared_accepted_grammar_and_explicit_unit_conversions(case):
    parsed = assistant.parse_command(case["message"], case["component_id"])
    assert parsed["action"] == case["action"]
    if "edit" in case:
        assert {key: parsed["edit"][key] for key in case["edit"]} == case["edit"]
        assert parsed["edit"]["classification"] == "assumed"
        assert parsed["edit"]["source"] == "User-proposed local command: " + case["message"]
        assert parsed["input_conversion"]["normalized_value"] == parsed["edit"]["value"]
        assert "Explicit input-unit conversion only" in parsed["input_conversion"]["rule"]


@pytest.mark.parametrize("case", EVALUATION["rejected"], ids=lambda case: case["message"])
def test_predeclared_rejections_do_not_guess_intent_or_units(case):
    with pytest.raises(RequestError) as exc:
        assistant.parse_command(case["message"], case["component_id"])
    assert exc.value.code == case["code"]


def test_help_and_configuration_explanation_are_local_and_do_not_pick_newest_run(project, monkeypatch):
    saved = run(project)
    before = hashes(project.path)
    def forbidden(*args, **kwargs):
        pytest.fail("Local command mode must not execute project actions")
    monkeypatch.setattr(Project, "run", forbidden)
    monkeypatch.setattr(Project, "apply_edit", forbidden)
    monkeypatch.setattr(Project, "create_reference", forbidden)
    help_result = ok(assistant.handle_command(project.path, request(project, "help")))
    assert help_result["schema"] == "voltforge.local_assistant/1"
    assert help_result["mode"] == "local_commands"
    assert help_result["payload"]["kind"] == "command_help"
    assert help_result["applied"] is help_result["simulation_started"] is False
    explain = ok(assistant.handle_command(project.path, request(project)))
    assert explain["payload"]["status"] == "configuration_only"
    assert explain["evidence"]["binding"]["run_id"] is None
    assert saved["run_id"] not in [claim["source"].get("run_id") for claim in explain["payload"]["claims"]]
    assert explain["context"] is None
    assert hashes(project.path) == before


@pytest.mark.parametrize("case", [case for case in EVALUATION["accepted"] if case["action"] == "preview_edit"], ids=lambda case: case["message"])
def test_supported_previews_delegate_exactly_and_preserve_project(project, case, monkeypatch):
    body = request(project, case["message"], component=case["component_id"])
    before = hashes(project.path)
    def forbidden(*args, **kwargs):
        pytest.fail("A preview cannot apply or run")
    monkeypatch.setattr(Project, "apply_edit", forbidden)
    monkeypatch.setattr(Project, "run", forbidden)
    result = ok(assistant.handle_command(project.path, body))
    assert result["selection"] == body["selection"]
    assert result["action"] == "preview_edit"
    assert result["payload"]["status"] == "approval_required"
    parsed = assistant.parse_command(body["message"], body["selection"]["component_id"])
    expected = ok(handle_request(project.path, dict(operation="preview_edit", context=result["context"], arguments={"edit": parsed["edit"]})))
    assert result["payload"] == expected
    assert result["payload"]["predicted_effect"] is None
    assert result["applied"] is result["simulation_started"] is False
    assert hashes(project.path) == before


@pytest.mark.parametrize("message,component", [
    ("preview selected rail to -1 ohm", "rail_p_1"),
    ("preview selected cell SOC to 101 %", "cell_1"),
    ("preview timestep to 0 s", "module"),
])
def test_mathematical_bounds_are_decided_by_existing_validator(project, message, component):
    before = hashes(project.path)
    response = assistant.handle_command(project.path, request(project, message, component))
    assert response["status"] == "error" and response["error"]["code"] == "invalid_request"
    assert hashes(project.path) == before


def test_current_explanation_preserves_frozen_claims_units_and_unset_requirements(project):
    saved = run(project)
    body = request(project, "explain this result", component="cell_2", run_id=saved["run_id"])
    before = hashes(project.path)
    result = ok(assistant.handle_command(project.path, body))
    context = build_context(project.path, variant_id="A0", run_id=saved["run_id"], component_id="cell_2", limit=4)
    assert result["payload"] == ok(handle_request(project.path, dict(operation="explain", context=context, arguments={})))
    assert result["payload"]["requirement_check"]["status"] == "requirement not configured"
    assert result["payload"]["decision"] == "insufficient evidence"
    for claim in result["payload"]["claims"]:
        source = claim["source"]
        actual = dispatch(project.path, {key: source[key] for key in ("operation", "arguments")})
        assert claim["value"] == value_at(actual, source["source_pointer"])
    assert hashes(project.path) == before


def test_historical_and_failed_evidence_retains_exact_status(project):
    saved = run(project)
    project.create_variant("A0", "A1", "Synthetic inherited evidence", project.inspect()["revision_id"])
    historical = ok(assistant.handle_command(project.path, request(project, variant="A1", run_id=saved["run_id"])))
    assert historical["payload"]["run_status"]["freshness"] == "outdated"
    assert historical["payload"]["binding"]["variant_id"] == "A1"
    apply(project, change(target="scenario", id="module", property="load_profile", unit="A,s",
                          value=[dict(start_s=0., end_s=2., current_A=100000.)]), "A1")
    failed = run(project, "A1")
    before = hashes(project.path)
    result = ok(assistant.handle_command(project.path, request(project, variant="A1", run_id=failed["run_id"])))
    assert result["payload"]["run_status"]["execution_status"] == "failed"
    assert result["payload"]["run_status"]["error"] == failed["error"]
    assert result["payload"]["coverage"] == failed["summary"]["coverage"]
    assert result["payload"]["decision"] == "insufficient evidence"
    assert hashes(project.path) == before


def test_stale_selected_revision_rejected_and_visual_movement_does_not_stale_it(project):
    body = request(project)
    project.update_display(dict(positions={"cell_1": [7, 8]}, camera={}, selection=["cell_1"]))
    assert assistant.handle_command(project.path, body)["status"] == "ok"
    apply(project, change())
    before = hashes(project.path)
    response = assistant.handle_command(project.path, body)
    assert response["error"]["code"] == "stale_context"
    assert hashes(project.path) == before


def comparison(first_variant, first, second_variant, second):
    return dict(first=dict(variant_id=first_variant, run_id=first["run_id"]),
                second=dict(variant_id=second_variant, run_id=second["run_id"]))


def test_comparison_copies_backend_values_and_cites_both_owners_and_snapshots(project, monkeypatch):
    first = run(project)
    project.create_variant("A0", "A1", "Synthetic explicit comparison", project.inspect()["revision_id"])
    apply(project, change(), "A1")
    second = run(project, "A1")
    pair = comparison("A0", first, "A1", second)
    body = request(project, "compare selected runs", run_id=first["run_id"], comparison=pair)
    before = hashes(project.path)
    def forbidden(*args, **kwargs):
        pytest.fail("A command comparison must not run or apply")
    monkeypatch.setattr(Project, "run", forbidden)
    monkeypatch.setattr(Project, "apply_edit", forbidden)
    result = ok(assistant.handle_command(project.path, body))
    assert result["payload"] == project.compare([pair["first"], pair["second"]])
    metadata = result["evidence"]["comparison"]
    assert [run["owner_variant_id"] for run in metadata["runs"]] == ["A0", "A1"]
    assert [run["snapshot_id"] for run in metadata["runs"]] == [first["snapshot_id"], second["snapshot_id"]]
    assert metadata["units"]["minimum_terminal_voltage_V"] == "V"
    assert all(row["requirement"] == "requirement not configured" for row in result["payload"]["ordered_results"])
    for source in metadata["source_references"]:
        actual = dispatch(project.path, {key: source[key] for key in ("operation", "arguments")})
        assert value_at(result["payload"], source["payload_pointer"]) == value_at(actual, source["source_pointer"])
    for header in metadata["runs"]:
        actual = ok(dispatch(project.path, {key: header["source"][key] for key in ("operation", "arguments")}))
        assert {key: header[key] for key in assistant.RUN_HEADER_FIELDS} == {key: actual[key] for key in assistant.RUN_HEADER_FIELDS}
    assert hashes(project.path) == before


def test_inherited_comparison_never_relabels_the_original_run_owner(project):
    saved = run(project)
    project.create_variant("A0", "A1", "Synthetic inherited comparison", project.inspect()["revision_id"])
    pair = comparison("A0", saved, "A1", saved)
    result = ok(assistant.handle_command(project.path, request(project, "compare selected runs", comparison=pair)))
    assert result["payload"]["historical_results"] is True
    headers = result["evidence"]["comparison"]["runs"]
    assert [item["owner_variant_id"] for item in headers] == ["A0", "A0"]
    assert [item["viewed_variant_id"] for item in headers] == ["A0", "A1"]
    assert headers[1]["freshness"] == "outdated"
    assert any("same saved run" in warning for warning in result["warnings"])


def test_comparison_requires_explicit_entries_and_identical_conditions(project):
    missing = assistant.handle_command(project.path, request(project, "compare selected runs"))
    assert missing["error"]["code"] == "invalid_request"
    first = run(project)
    same = comparison("A0", first, "A0", first)
    assert assistant.handle_command(project.path, request(project, "compare selected runs", comparison=same))["error"]["code"] == "invalid_request"
    project.create_variant("A0", "A1", "Synthetic reduced service", project.inspect()["revision_id"])
    apply(project, change(target="scenario", id="module", property="load_profile", unit="A,s",
                          value=[dict(start_s=0., end_s=2., current_A=12.)]), "A1")
    second = run(project, "A1")
    before = hashes(project.path)
    response = assistant.handle_command(project.path, request(project, "compare selected runs", comparison=comparison("A0", first, "A1", second)))
    assert response["error"]["code"] == "unsupported_request"
    assert "identical operating conditions" in response["error"]["message"]
    assert hashes(project.path) == before


def test_comparison_of_failed_runs_is_not_an_available_accuracy_comparison(project):
    first = run(project)
    apply(project, change(target="scenario", id="module", property="load_profile", unit="A,s",
                          value=[dict(start_s=0., end_s=2., current_A=100000.)]))
    failed = run(project)
    before = hashes(project.path)
    response = assistant.handle_command(project.path, request(project, "compare selected runs", comparison=comparison("A0", first, "A0", failed)))
    assert response["error"]["code"] == "unsupported_request"
    assert "incomplete run" in response["error"]["message"]
    assert hashes(project.path) == before


@pytest.mark.parametrize("mutation", ["unknown_request", "unknown_selection", "missing_comparison", "bad_revision", "empty_run", "bad_component", "bad_comparison", "numeric_message"])
def test_malformed_requests_rejected_without_project_mutation(project, mutation):
    body = request(project)
    if mutation == "unknown_request": body["predicted_voltage_V"] = 9
    if mutation == "unknown_selection": body["selection"]["predicted_voltage_V"] = 9
    if mutation == "missing_comparison": del body["comparison"]
    if mutation == "bad_revision": body["selection"]["revision_id"] = "latest"
    if mutation == "empty_run": body["selection"]["run_id"] = ""
    if mutation == "bad_component": body["selection"]["component_id"] = "cell_5"
    if mutation == "bad_comparison": body["comparison"] = {"first": "latest", "second": "best"}
    if mutation == "numeric_message": body["message"] = 1.0
    before = hashes(project.path)
    assert assistant.handle_command(project.path, body)["status"] == "error"
    assert hashes(project.path) == before


def test_command_length_controls_and_overflow_are_bounded():
    command = "preview selected rail to 0.5 mOhm"
    padded = command + " " * (400 - len(command))
    parsed = assistant.parse_command(padded, "rail_p_1")
    assert len(parsed["edit"]["source"]) <= 500
    for message in [padded + " ", " ", "show\tevidence", "help\x00", "preview selected rail to " + "9" * 340 + " ohm"]:
        with pytest.raises(RequestError):
            assistant.parse_command(message, "rail_p_1")


def test_context_change_during_read_only_delegation_rejects_result(project, monkeypatch):
    original = assistant.handle_request
    def race(path, body):
        response = original(path, body)
        apply(project, change())  # explicit test-injected external writer
        return response
    monkeypatch.setattr(assistant, "handle_request", race)
    response = assistant.handle_command(project.path, request(project))
    assert response["error"]["code"] == "stale_context"


def test_cli_agrees_with_service_and_rejects_duplicate_fields(project, tmp_path):
    body = request(project, "help")
    source = tmp_path / "command.json"
    source.write_text(json.dumps(body), encoding="utf-8")
    cmd = [sys.executable, str(ROOT / "scripts/local_assistant.py"), "--project", str(project.path), "--request", str(source)]
    before = hashes(project.path)
    completed = subprocess.run(cmd, check=True, capture_output=True, text=True)
    assert json.loads(completed.stdout) == assistant.handle_command(project.path, body)
    source.write_text('{"message":"help","message":"run"}', encoding="utf-8")
    rejected = subprocess.run(cmd, capture_output=True, text=True)
    assert rejected.returncode == 2
    assert "Duplicate JSON field" in json.loads(rejected.stdout)["error"]["message"]
    assert hashes(project.path) == before
