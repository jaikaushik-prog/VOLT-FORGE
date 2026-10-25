"""Integration checks against actual saved LG project runs, never raw records."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest

from voltforge.project import Project

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("backend_evidence_context", ROOT / "scripts/evidence_context.py")
context = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(context)


def tree_hashes(path):
    return {p.relative_to(path).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in path.rglob("*") if p.is_file()}


def edit(p, target="connection", cid="rail_p_1", prop="resistance", value=.0005, unit="ohm", variant="A0"):
    request = dict(target=target, id=cid, property=prop, value=value, unit=unit,
                   source="Declared software-test assumption", classification="assumed")
    return p.apply_edit(variant, request, p.inspect(variant)["revision_id"])


@pytest.fixture
def project(tmp_path):
    project = Project.create_reference(tmp_path / "working_project")
    edit(project, "scenario", "module", "load_profile",
         [{"start_s": 0., "end_s": 2., "current_A": 14.55}], "A,s")
    return project


def run(p, variant="A0", **kwargs):
    return p.run(variant, expected_revision=p.inspect(variant)["revision_id"], plots=False, **kwargs)


def pointer(value, path):
    for key in path.split("/")[1:]:
        key = key.replace("~1", "/").replace("~0", "~")
        value = value[int(key)] if isinstance(value, list) else value[key]
    return value


def test_configuration_only_retains_null_requirements_model_sources_and_catalogue(project):
    # An existing run does not cause an implicit latest-run selection.
    run(project)
    before = tree_hashes(project.path)
    response = context.build_context(project.path)
    assert response["status"] == "ok"
    result = response["result"]
    inspected = project.inspect()
    assert result["schema"] == "voltforge.evidence_context/1"
    assert result["run"] is None and result["series"] is None
    assert result["project"]["design"]["requirements"] == inspected["design"]["requirements"]
    assert all(v is None for v in result["project"]["design"]["requirements"].values())
    assert result["project"]["editable_properties"] == inspected["editable_properties"]
    assert result["project"]["fitted_parameters"] == inspected["fitted_parameters"]
    assert result["project"]["design"]["cells"]["cell_1"]["model"]["version"] == "frozen-v2"
    assert result["project"]["experimental_validation"] == "awaiting suitable measurements"
    assert "display" not in result["project"]
    assert result["context_id"] == context.context_digest(result)
    assert tree_hashes(project.path) == before


def test_current_run_preserves_exact_outputs_units_coverage_and_citations(project):
    recorded = run(project)
    before = tree_hashes(project.path)
    response = context.build_context(project.path, run_id=recorded["run_id"], component_id="cell_1", limit=2)
    result = response["result"]
    assert result["run"] == project.get_run("A0", recorded["run_id"])
    assert result["run"]["execution_status"] == "completed"
    assert result["run"]["freshness"] == "current"
    assert result["run"]["summary"]["voltage_requirement"]["status"] == "requirement not configured"
    assert result["run"]["summary"]["coverage"]["cells"]
    assert result["series"] == project.series("A0", recorded["run_id"], "cell_1", limit=2)
    assert result["series"]["units"]["current_A"] == "A"
    assert len(result["series"]["rows"]) == result["series"]["next_offset"] == 2
    assert result["series"]["total_samples"] > 2
    # Every citation resolves to actual API evidence. Run-header citations are
    # deliberate field subsets of inspect's otherwise large run objects.
    cache = {}
    for reference in result["source_references"]:
        key = json.dumps([reference["operation"], reference["arguments"]], sort_keys=True)
        if key not in cache:
            cache[key] = context.dispatch(project.path, {"operation": reference["operation"],
                                                        "arguments": reference["arguments"]})
        actual = pointer(cache[key], reference["source_pointer"])
        provided = pointer(result, reference["context_pointer"])
        if reference["context_pointer"].startswith("/project/runs/"):
            assert provided == {key: actual[key] for key in provided}
        else:
            assert actual == provided
    assert tree_hashes(project.path) == before


def test_visual_changes_preserve_context_but_physics_changes_make_run_historical(project):
    recorded = run(project)
    first = context.build_context(project.path, run_id=recorded["run_id"])["result"]
    project.update_display({"positions": {"cell_1": [9., 4., 2.]}, "camera": {"zoom": 2}, "selection": ["cell_1"]})
    assert context.build_context(project.path, run_id=recorded["run_id"])["result"] == first
    edit(project)
    historical = context.build_context(project.path, run_id=recorded["run_id"])["result"]
    assert historical["run"]["freshness"] == "outdated"
    assert "design revision changed" in historical["run"]["outdated_reasons"]
    assert historical["run"]["revision_id"] != historical["project"]["revision_id"]
    assert historical["context_id"] != first["context_id"]
    assert historical["project"]["current_run_ids"] == []


def test_variants_cannot_claim_inherited_or_unassociated_results(project):
    a0 = run(project)
    project.create_variant("A0", "A1", "Connection alternative", project.inspect()["revision_id"])
    inherited = context.build_context(project.path, "A1", a0["run_id"])["result"]
    assert inherited["run"]["owner_variant_id"] == "A0"
    assert inherited["run"]["viewed_variant_id"] == "A1"
    assert inherited["run"]["freshness"] == "outdated"
    assert inherited["project"]["current_run_ids"] == []
    a1 = run(project, "A1")
    rejected = context.build_context(project.path, "A0", a1["run_id"])
    assert rejected["error"]["code"] == "unsupported_request"
    edit(project)
    separated = context.build_context(project.path)["result"]
    variant_reference = next(ref for ref in separated["source_references"]
                             if ref["context_pointer"] == "/project/variants/A1")
    assert variant_reference["revision_id"] == separated["project"]["variants"]["A1"]["revision_id"]
    assert variant_reference["revision_id"] != separated["project"]["revision_id"]


def test_failed_run_keeps_partial_samples_and_never_becomes_usable_current(project):
    edit(project, "scenario", "module", "load_profile",
         [{"start_s": 0., "end_s": 2., "current_A": 100000.}], "A,s")
    failed = run(project)
    result = context.build_context(project.path, run_id=failed["run_id"])["result"]
    assert result["run"]["execution_status"] == "failed"
    assert result["run"]["freshness"] == "current"
    assert result["run"]["error"] == failed["error"]
    assert result["run"]["summary"]["decision"] == "insufficient evidence"
    assert result["project"]["current_run_ids"] == []
    assert 0 < result["series"]["total_samples"] < 9


def test_zero_sample_failure_does_not_invent_coverage(project):
    edit(project, "cell", "cell_1", "initial_soc", .999, "fraction")
    failed = run(project, scenario_id="soc_plus_2pp")
    result = context.build_context(project.path, run_id=failed["run_id"])["result"]
    assert result["run"]["execution_status"] == "failed"
    assert result["series"]["rows"] == []
    assert result["series"]["total_samples"] == 0
    assert result["run"]["summary"] == failed["summary"]


def test_missing_project_invalid_component_and_bad_pagination_never_write(tmp_path, project):
    missing = tmp_path / "does_not_exist"
    assert context.build_context(missing)["error"]["code"] == "not_found"
    assert not missing.exists()
    before = tree_hashes(project.path)
    assert context.build_context(project.path, component_id="temperature")["error"]["code"] == "unsupported_request"
    for limit in (0, 257, True, 1.5):
        assert context.build_context(project.path, limit=limit)["error"]["code"] == "invalid_request"
    assert tree_hashes(project.path) == before


def test_concurrent_writer_or_index_change_is_explicit_conflict(project, monkeypatch):
    lock = project.path / "project.lock"
    lock.write_text("synthetic writer lock", encoding="utf-8")
    assert context.build_context(project.path)["error"]["code"] == "conflict"
    lock.unlink()
    original = context.dispatch

    def changed_after_read(path, request):
        response = original(path, request)
        project.update_display({"positions": {}, "camera": {"race": True}, "selection": []})
        return response

    monkeypatch.setattr(context, "dispatch", changed_after_read)
    assert context.build_context(project.path)["error"]["code"] == "conflict"


def test_bounded_catalogue_and_oversized_context_are_explicit(project, monkeypatch):
    records = [run(project) for _ in range(3)]
    monkeypatch.setattr(context, "MAX_RUN_HEADERS", 2)
    result = context.build_context(project.path, run_id=records[0]["run_id"])["result"]
    assert result["bounds"]["run_headers"]["omitted"] == 1
    assert len(result["project"]["runs"]) == 2
    assert result["run"]["run_id"] == records[0]["run_id"]  # explicit older selection still works
    monkeypatch.setattr(context, "MAX_CONTEXT_BYTES", 64)
    assert context.build_context(project.path)["error"]["code"] == "context_too_large"


def test_tampered_artifact_and_context_are_detected(project):
    recorded = run(project)
    result = context.build_context(project.path, run_id=recorded["run_id"])["result"]
    altered = copy.deepcopy(result)
    altered["series"]["rows"][0]["terminal_V"] += .1
    assert altered["context_id"] != context.context_digest(altered)
    trajectory = project.path / "runs" / recorded["run_id"] / "trajectory.csv"
    trajectory.write_text("tampered", encoding="utf-8")
    assert context.build_context(project.path, run_id=recorded["run_id"])["error"]["code"] == "integrity_error"


def test_cli_rejects_protected_destinations_and_creates_no_project(tmp_path, project):
    protected = ROOT / "reports/backend_context_v1/do_not_create.json"
    process = subprocess.run([sys.executable, str(ROOT / "scripts/evidence_context.py"),
        "--project", str(project.path), "--out", str(protected)], capture_output=True, text=True)
    assert process.returncode == 2
    assert json.loads(process.stdout)["error"]["code"] == "unsupported_request"
    assert not protected.exists()
    missing = tmp_path / "missing_cli_project"
    process = subprocess.run([sys.executable, str(ROOT / "scripts/evidence_context.py"),
        "--project", str(missing)], capture_output=True, text=True)
    assert process.returncode == 2 and json.loads(process.stdout)["error"]["code"] == "not_found"
    assert not missing.exists()
