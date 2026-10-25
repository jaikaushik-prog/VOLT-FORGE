"""Actual solver evidence -> deterministic explanation/preview, never AI execution."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
for folder in (ROOT, ROOT / "src"):
    sys.path.insert(0, str(folder))

from scripts.copilot_contract import handle_request, value_at
from scripts.evidence_context import build_context, context_digest
from voltforge.project import Project, dispatch
from voltforge.project.service import destination, software

DEFAULT_OUT = ROOT / "reports/parallel_engineering_v1/demo_001"
EDIT = dict(target="connection", id="rail_p_1", property="resistance", value=0.0005,
            unit="ohm", classification="assumed",
            source="Predeclared hypothetical p1-p2 rail edit; physical feasibility and resistance unmeasured")
IMPLEMENTATION = ["scripts/demonstrate_copilot_handoff.py", "scripts/copilot_contract.py",
                  "scripts/evidence_context.py"]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def hashes(folder):
    return {p.relative_to(folder).as_posix(): sha(p) for p in sorted(folder.rglob("*"))
            if p.is_file() and "__pycache__" not in p.parts}


def write(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(obj, stream, indent=2, allow_nan=False)
        stream.write("\n")


def require(condition, detail):
    if not condition:
        raise ValueError(detail)


def result(response):
    require(response.get("status") == "ok", str(response))
    return response["result"]


def verify_saved(out):
    out = Path(out)
    manifest = json.loads((out / "manifest.json").read_text())
    for name, expected in manifest["artifacts"].items():
        require(sha(out / name) == expected, "Changed demonstration artifact: " + name)
    for name, expected in manifest["implementation"].items():
        require(sha(ROOT / name) == expected, "Changed implementation; use a new output directory: " + name)
    require(software() == manifest["solver_software"], "Solver/runtime changed; use a new output directory")
    summary = json.loads((out / "result.json").read_text())
    require(all(item["unchanged"] for item in summary["read_only_checks"]), "Project mutated during read-only call")
    require(all(summary["checks"].values()), "A demonstration check failed")
    # Independently resolve every explanation/preview claim against the saved
    # complete context, including old contexts deliberately rejected as stale.
    claim_count = 0
    for path in sorted((out / "examples").glob("*_request_response.json")):
        pair = json.loads(path.read_text())
        response = pair["response"]
        if response["status"] != "ok":
            continue
        context = pair["request"]["context"]["result"]
        require(context_digest(context) == context["context_id"], "Context hash mismatch")
        claims = response["result"].get("claims", [])
        if "before" in response["result"]:
            claims = claims + [response["result"]["before"]]
        for claim in claims:
            source = claim["source"]
            require(source["context_id"] == context["context_id"], "Cross-context citation")
            require(claim["value"] == value_at(context, source["context_pointer"]), "Claim differs from saved evidence")
            claim_count += 1
    require(claim_count == summary["claims_checked_against_live_backend"], "Claim count changed")
    return dict(status="verified", claim_count=claim_count, checks=summary["checks"],
                experimental_validation="awaiting suitable measurements",
                assistant_capability="deterministic structured contract only; no language model or executor")


def demo(out=DEFAULT_OUT):
    out = destination(out)
    if (out / "manifest.json").is_file():
        return verify_saved(out)
    require(not out.exists(), "Destination exists without a completion manifest; preserve it and choose a fresh --out")
    out.mkdir(parents=True)
    write(out / "declaration.json", dict(
        baseline="Frozen LG M50T v2 A0, 1s4p same-side ladder, 14.55 A for 360 s, dt=0.25 s",
        preview=EDIT, requirements="Application minimum voltage and excursion duration remain unset",
        operations="Only the orchestrator creates the reference, runs A0, moves layout and edits A1 as explicit test setup",
        adapter_actions="Read-only context, explanation and preview; no automatic apply or solver execution",
        scope="Software integration demonstration; not experimental validation, repair ranking or battery-performance gain"))
    project_path = out / "project"
    project = Project.create_reference(project_path)
    checks, calls = {}, []
    claim_count = 0

    def readonly(name, function):
        before = hashes(project_path)
        response = function()
        after = hashes(project_path)
        require(before == after, "Read-only operation mutated project: " + name)
        calls.append(dict(operation=name, unchanged=True, files_checked=len(before),
                          project_index_sha256=before["project.json"]))
        return response

    def context(name, variant="A0", run_id=None, component="module"):
        response = readonly(name, lambda: build_context(project_path, variant, run_id, component, 3))
        result(response)
        write(out / "examples" / (name + "_context.json"), response)
        return response

    def call(name, ctx, operation="explain", arguments=None):
        nonlocal claim_count
        request = dict(operation=operation, context=ctx, arguments=arguments or {})
        response = readonly(name, lambda: handle_request(project_path, request))
        if response["status"] == "ok":
            claims = response["result"].get("claims", [])
            if "before" in response["result"]:
                claims = claims + [response["result"]["before"]]
            for item in claims:
                source = item["source"]
                live = dispatch(project_path, {k: source[k] for k in ("operation", "arguments")})
                require(item["value"] == value_at(live, source["source_pointer"]), "Claim differs from backend")
                require(item["value"] == value_at(ctx["result"], source["context_pointer"]), "Claim differs from context")
                claim_count += 1
        write(out / "examples" / (name + "_request_response.json"), dict(request=request, response=response))
        return response

    config = context("01_configuration")
    explanation = result(call("02_configuration_explanation", config))
    checks["configuration_is_not_a_prediction"] = explanation["status"] == "configuration_only" and explanation["requirement_check"] is None
    write(out / "examples/03_orchestrator_run.json", dict(
        operation="run", arguments=dict(variant_id="A0", expected_revision=config["result"]["project"]["revision_id"], plots=False),
        classification="Explicit demonstration setup; not a copilot action"))
    saved = project.run("A0", expected_revision=config["result"]["project"]["revision_id"], plots=False)
    write(out / "examples/03_run_result.json", saved)
    require(saved["execution_status"] == "completed", "A0 demonstration simulation failed")
    ctx = context("04_saved_A0", run_id=saved["run_id"])
    explanation = result(call("05_saved_run_explanation", ctx))
    checks["actual_run_current"] = explanation["run_status"]["execution_status"] == "completed" and explanation["run_status"]["freshness"] == "current"
    checks["unset_requirement_not_pass"] = explanation["requirement_check"]["status"] == "requirement not configured"
    checks["simulation_not_experimental_acceptance"] = explanation["decision"] == "insufficient evidence"
    preview = result(call("06_structured_preview", ctx, "preview_edit", dict(edit=EDIT)))
    checks["preview_does_not_apply_or_predict"] = preview["status"] == "approval_required" and preview["applied"] is False and preview["simulation_started"] is False and preview["predicted_effect"] is None
    checks["preview_declares_invalidation"] = saved["run_id"] in preview["validation"]["invalidated_run_ids"]

    forged = copy.deepcopy(ctx)
    forged["result"]["run"]["summary"]["maximum_branch_current_A"] = 999.0
    forged["result"]["context_id"] = context_digest(forged["result"])
    rejection = call("07_fabricated_result_rejected", forged)
    checks["rehashed_fabrication_rejected"] = rejection.get("error", {}).get("code") == "stale_context"
    rejection = call("08_thermal_request_rejected", ctx, "run_thermal")
    checks["unavailable_operation_rejected"] = rejection.get("error", {}).get("code") == "unsupported_request"

    # Pure layout changes are deliberately outside this evidence context.
    display = dict(positions={"cell_1": [20, 50]}, camera={"zoom": 1.2}, selection=["cell_1"])
    project.update_display(display)
    moved = context("09_after_visual_move", run_id=saved["run_id"])
    checks["visual_move_keeps_context_and_physics_current"] = moved == ctx
    result(call("10_preview_after_visual_move", ctx, "preview_edit", dict(edit=EDIT)))

    # These are explicit test setup actions through the existing project API.
    # The copilot contract has no execution route or approval token.
    a1 = project.create_variant("A0", "A1", "Hypothetical rail edit for context isolation", project.inspect("A0")["revision_id"])
    inherited_before = context("11_A1_before_edit", variant="A1", run_id=saved["run_id"])
    a1 = project.apply_edit("A1", EDIT, a1["revision_id"])
    write(out / "examples/12_orchestrator_A1_edit.json", dict(edit=EDIT, revision_id=a1["revision_id"],
          classification="Explicit setup to test stale context; A1 was not run and no repair outcome is claimed"))
    rejected = call("13_stale_context_rejected", inherited_before, "preview_edit", dict(edit=EDIT))
    checks["edited_revision_rejects_old_context"] = rejected.get("error", {}).get("code") == "stale_context"
    inherited = context("14_A1_historical_run", variant="A1", run_id=saved["run_id"])
    explanation = result(call("15_A1_historical_explanation", inherited))
    checks["inherited_run_is_outdated"] = explanation["run_status"]["freshness"] == "outdated" and explanation["binding"]["run_revision_id"] != explanation["binding"]["current_revision_id"]
    a0_now = context("16_A0_still_current", run_id=saved["run_id"])
    checks["A1_edit_does_not_change_A0_run"] = a0_now["result"]["run"]["freshness"] == "current" and a0_now["result"]["run"]["summary"] == ctx["result"]["run"]["summary"]
    require(all(checks.values()), "Demonstration invariant failed: " + str(checks))
    write(out / "result.json", dict(checks=checks, read_only_checks=calls,
          claims_checked_against_live_backend=claim_count,
          A0_run_id=saved["run_id"], A0_snapshot_id=saved["snapshot_id"],
          application_requirement_status="requirement not configured",
          experimental_validation="awaiting suitable measurements",
          unavailable=["natural-language assistant", "model provider", "automatic edit execution", "optimizer", "thermal prediction"]))
    write(out / "manifest.json", dict(artifacts=hashes(out), solver_software=software(),
          implementation={name: sha(ROOT / name) for name in IMPLEMENTATION}))
    return verify_saved(out)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    print(json.dumps(demo(args.out), indent=2))


if __name__ == "__main__":
    main()
