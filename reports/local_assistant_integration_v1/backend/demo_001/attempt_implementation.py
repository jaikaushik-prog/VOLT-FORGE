"""Reproduce local-command read-only help inside an explicitly orchestrated workflow."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
for folder in (ROOT, ROOT / "src", ROOT / "scripts"):
    sys.path.insert(0, str(folder))

from local_assistant import handle_command
from scripts.copilot_contract import value_at
from voltforge.project import Project, dispatch
from voltforge.project.service import software

DEFAULT_OUT = ROOT / "reports/local_assistant_integration_v1/backend/demo_001"
IMPLEMENTATION = ["scripts/demonstrate_local_assistant.py", "scripts/local_assistant.py",
                  "scripts/copilot_contract.py", "scripts/evidence_context.py"]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def hashes(folder):
    return {p.relative_to(folder).as_posix(): sha(p) for p in sorted(folder.rglob("*"))
            if p.is_file() and "__pycache__" not in p.parts}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")


def result(response):
    require(response.get("status") == "ok", str(response))
    return response["result"]


def verify_saved(out):
    out = Path(out).resolve()
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    for name, expected in manifest["artifacts"].items():
        require(sha(out / name) == expected, "Changed local-command demonstration artifact: " + name)
    for name, expected in manifest["implementation"].items():
        require(sha(ROOT / name) == expected, "Implementation changed; choose a new demonstration path: " + name)
    require(software() == manifest["solver_software"], "Solver/runtime changed")
    summary = json.loads((out / "result.json").read_text(encoding="utf-8"))
    require(all(summary["checks"].values()), "A demonstration check failed")
    require(all(item["unchanged"] for item in summary["read_only_checks"]), "A local command mutated the project")
    claims = 0
    for path in sorted((out / "examples").glob("*_command.json")):
        pair = json.loads(path.read_text(encoding="utf-8"))
        for item in pair["verified_claims"]:
            response = pair["source_responses"][item["source_key"]]["response"]
            require(item["value"] == value_at(response, item["source_pointer"]), "Claim differs from saved API evidence")
            claims += 1
        if pair["response"]["status"] == "ok" and pair["response"]["result"]["action"] == "compare":
            require(pair["response"]["result"]["payload"] == pair["comparison_source"]["response"]["result"],
                    "Comparison differs from actual backend result")
    require(claims == summary["claims_checked_against_backend"], "Citation count changed")
    return dict(status="verified", checks=summary["checks"], claims_checked=claims,
        mode="local_commands", experimental_module_validation="awaiting suitable measurements",
        scope="Simulation comparison and deterministic local commands; no external AI, automatic execution or repair ranking")


def demo(out=DEFAULT_OUT):
    out = Path(out).resolve()
    require(any(out.is_relative_to(ROOT / path) for path in ("tmp", "reports/local_assistant_integration_v1/backend")),
            "Choose a new path under tmp/ or reports/local_assistant_integration_v1/backend/")
    if (out / "manifest.json").is_file():
        return verify_saved(out)
    require(not out.exists(), "Destination exists without completion manifest; preserve it and use a new path")
    out.mkdir(parents=True)
    write(out / "declaration.json", dict(
        baseline="Frozen LG M50T v2 A0, four cells, same-side 1s4p ladder, 14.55 A for 360 s",
        alternative="A1: explicitly proposed positive rail 1 resistance 0.5 mOhm; all operating conditions unchanged",
        requirements="Minimum voltage, excursion duration and documented application source remain unset",
        preparation="Only the orchestration script creates variants, applies edits, runs simulations and exports",
        command_mode="Deterministic exact commands; explain/preview/compare read existing backend evidence",
        interpretation="Simulation comparison, not validated repair, module accuracy or battery-performance gain"))
    project = Project.create_reference(out / "project")
    checks, read_only, claim_count = {}, [], 0

    def selection(variant="A0", component="module", run_id=None):
        return dict(variant_id=variant, revision_id=project.inspect(variant)["revision_id"],
                    component_id=component, run_id=run_id)

    def manual(name, operation, **arguments):
        request = dict(operation=operation, arguments=arguments)
        response = dispatch(project.path, request)
        write(out / "examples" / (name + "_manual_action.json"), dict(
            classification="Explicit orchestration step standing in for a separate manual UI action; never a command execution",
            request=request, response=response))
        return result(response)

    def command(name, message, selected, comparison=None):
        nonlocal claim_count
        request = dict(message=message, selection=selected, comparison=comparison)
        before = hashes(project.path)
        response = handle_command(project.path, request)
        require(hashes(project.path) == before, "Command mutated project: " + name)
        read_only.append(dict(command=name, unchanged=True, files_checked=len(before),
                              project_index_sha256=before["project.json"]))
        sources, verified = {}, []
        comparison_source = None

        def source_response(source):
            require(source["operation"] in ("inspect", "get_run", "series", "compare"), "Citation attempted a mutating operation")
            api_request = {key: source[key] for key in ("operation", "arguments")}
            key = hashlib.sha256(json.dumps(api_request, sort_keys=True).encode()).hexdigest()
            if key not in sources:
                sources[key] = dict(request=api_request, response=dispatch(project.path, api_request))
                result(sources[key]["response"])
            return key, sources[key]["response"]

        if response["status"] == "ok":
            answer = response["result"]
            require(answer["applied"] is False and answer["simulation_started"] is False, "Command claims execution")
            payload = answer["payload"]
            claims = list(payload.get("claims", []))
            if "before" in payload:
                claims.append(payload["before"])
            for claim in claims:
                source = claim["source"]
                key, api_response = source_response(source)
                require(claim["value"] == value_at(api_response, source["source_pointer"]), "Claim differs from backend")
                verified.append(dict(source_key=key, source_pointer=source["source_pointer"], value=claim["value"]))
                claim_count += 1
            if answer["action"] == "compare":
                api_request = dict(operation="compare", arguments=dict(selections=list(comparison.values())))
                comparison_source = dict(request=api_request, response=dispatch(project.path, api_request))
                require(payload == result(comparison_source["response"]), "Local comparison differs from Project.compare")
                evidence = answer["evidence"]["comparison"]
                for source in evidence["source_references"]:
                    key, api_response = source_response(source)
                    value = value_at(payload, source["payload_pointer"])
                    require(value == value_at(api_response, source["source_pointer"]), "Comparison citation differs from backend")
                    verified.append(dict(source_key=key, source_pointer=source["source_pointer"], value=value))
                    claim_count += 1
                for header in evidence["runs"]:
                    key, api_response = source_response(header["source"])
                    for field, value in header.items():
                        if field == "source":
                            continue
                        pointer = header["source"]["source_pointer"] + "/" + field
                        require(value == value_at(api_response, pointer), "Comparison ownership/header differs from backend")
                        verified.append(dict(source_key=key, source_pointer=pointer, value=value))
                        claim_count += 1
        write(out / "examples" / (name + "_command.json"), dict(request=request, response=response,
            source_responses=sources, verified_claims=verified, comparison_source=comparison_source))
        return response

    configuration = result(command("01_configuration", "explain this result", selection()))
    checks["configuration_has_no_predicted_result"] = configuration["payload"]["status"] == "configuration_only"
    first = manual("02_A0_run", "run", variant_id="A0", expected_revision=selection()["revision_id"], plots=False)
    require(first["execution_status"] == "completed", "A0 simulation failed")
    explanation = result(command("03_A0_explanation", "explain this result", selection(run_id=first["run_id"])))
    checks["unset_requirement_not_pass"] = explanation["payload"]["requirement_check"]["status"] == "requirement not configured"
    checks["run_binding_matches_snapshot"] = explanation["payload"]["binding"]["snapshot_id"] == first["snapshot_id"]

    manual("04_create_A1", "create_variant", source_variant="A0", variant_id="A1",
           name="Hypothetical positive rail 1 alternative", expected_revision=selection()["revision_id"])
    preview_selection = selection("A1", "rail_p_1", first["run_id"])
    preview = result(command("05_A1_preview", "preview change selected rail to 0.5 mOhm", preview_selection))
    checks["preview_is_not_execution_or_prediction"] = (preview["action"] == "preview_edit"
        and preview["payload"]["predicted_effect"] is None and preview["applied"] is False
        and preview["simulation_started"] is False)
    proposed = preview["payload"]["proposed_edit"]
    checks["preview_matches_declared_edit"] = (proposed["id"] == "rail_p_1"
        and proposed["value"] == .0005 and proposed["unit"] == "ohm")
    a1 = manual("06_apply_A1_separately", "apply_edit", variant_id="A1",
                expected_revision=preview_selection["revision_id"], edit=proposed)
    stale = command("07_old_selection_rejected", "show evidence", preview_selection)
    checks["changed_revision_rejects_old_selection"] = stale.get("error", {}).get("code") == "stale_context"
    second = manual("08_A1_run_separately", "run", variant_id="A1", expected_revision=a1["revision_id"], plots=False)
    require(second["execution_status"] == "completed", "A1 simulation failed")
    pair = dict(first=dict(variant_id="A0", run_id=first["run_id"]),
                second=dict(variant_id="A1", run_id=second["run_id"]))
    comparison = result(command("09_compare_selected", "compare selected runs", selection("A1", run_id=second["run_id"]), pair))
    checks["comparison_uses_same_conditions"] = comparison["payload"]["conditions"] == "identical operating conditions"
    checks["comparison_is_unranked_simulation"] = comparison["payload"]["kind"] == "simulation comparison"
    refused = command("10_execution_refused", "run simulation", selection("A1", run_id=second["run_id"]))
    checks["command_cannot_run_simulation"] = refused.get("error", {}).get("code") == "unsupported_command"
    exported = manual("11_export_separately", "export", selections=list(pair.values()), out=str(out / "export"))
    checks["export_keeps_validation_pending"] = exported["experimental_validation"] == "awaiting suitable measurements"
    replays = []
    for saved in (first, second):
        replay = subprocess.run([sys.executable, "-B", str(out / "export/replay.py"), saved["run_id"]],
            cwd=out, capture_output=True, text=True, encoding="utf-8")
        require(replay.returncode == 0, replay.stderr)
        replays.append(json.loads(replay.stdout))
    write(out / "replay_results.json", replays)
    checks["both_exported_runs_reproduce"] = all(item["reproduced"] for item in replays)
    checks["A0_remains_current"] = project.get_run("A0", first["run_id"])["freshness"] == "current"
    require(all(checks.values()), "Demonstration check failed: " + str(checks))
    write(out / "result.json", dict(checks=checks, read_only_checks=read_only,
        claims_checked_against_backend=claim_count, comparison=comparison["payload"],
        experimental_module_validation="awaiting suitable measurements", mode="local_commands",
        assistant_executes_actions=False, physical_outcomes_source="existing electrical solver only"))
    write(out / "manifest.json", dict(artifacts=hashes(out), solver_software=software(),
          implementation={name: sha(ROOT / name) for name in IMPLEMENTATION}))
    return verify_saved(out)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    print(json.dumps(demo(parser.parse_args().out), indent=2))
