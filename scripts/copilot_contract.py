"""Offline, deterministic preview/explanation contract; never executes an action.

This is a future assistant integration boundary, not an AI assistant. All numbers
come from the current project API. Supplied text is data, never a solver result.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
for _path in (ROOT, ROOT / "src"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from scripts.evidence_context import build_context
from voltforge.project import Project
from voltforge.project.schema import RequestError

SCHEMA = "voltforge.copilot_contract/1"
CONTEXT_SCHEMA = "voltforge.evidence_context/1"
MAX_REQUEST_BYTES = 1048576
UNAVAILABLE = ["natural_language_parsing", "external_model_provider", "automatic_action_execution",
               "run_simulation", "optimizer", "repair_ranking", "thermal_prediction", "chat_ui"]
SUMMARY_UNITS = {
    "maximum_branch_current_A": "A", "minimum_branch_current_A": "A",
    "minimum_cell_voltage_V": "V", "minimum_terminal_voltage_V": "V",
    "delivered_net_Wh": "Wh", "delivered_positive_Wh": "Wh", "received_Wh": "Wh",
    "mean_delivered_power_W": "W", "delivered_charge_Ah": "Ah",
    "cell_R0_loss_Wh": "Wh", "rail_loss_Wh": "Wh", "R1_loss_Wh": "Wh",
    "max_kcl_residual_A": "A", "max_charge_balance_As": "A s",
}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def require(condition, message, code="invalid_request"):
    if not condition:
        raise RequestError(code, message)


def exact(value, names, label):
    require(isinstance(value, dict) and set(value) == set(names),
            "Unexpected or missing fields: " + label)


def pointer_part(value):
    return str(value).replace("~", "~0").replace("/", "~1")


def value_at(value, pointer):
    """Resolve a local JSON pointer without eval, expressions, or file access."""
    require(isinstance(pointer, str) and (not pointer or pointer.startswith("/")), "Invalid evidence pointer")
    for part in pointer.split("/")[1:]:
        part = part.replace("~1", "/").replace("~0", "~")
        value = value[int(part)] if isinstance(value, list) else value[part]
    return value


def current_context(project_path, supplied):
    """The hash binds dependencies; rereading prevents trusting a forged payload.

    No authentication claim is made: hashes are content identities, not signatures.
    Only a byte-equivalent current result is consumed, never user-supplied values.
    """
    exact(supplied, ["status", "result"], "successful context envelope")
    require(supplied["status"] == "ok", "An error context cannot be used")
    context = supplied["result"]
    require(isinstance(context, dict) and context.get("schema") == CONTEXT_SCHEMA,
            "Unsupported evidence context schema", "unsupported_request")
    exact(context.get("selection"), ["variant_id", "run_id", "component_id", "limit"], "context selection")
    fresh = build_context(project_path, **context["selection"])
    if fresh["status"] != "ok":
        raise RequestError(fresh["error"]["code"], fresh["error"]["message"])
    require(canonical(fresh["result"]) == canonical(context),
            "Evidence context changed or was modified; rebuild it before reviewing this request", "stale_context")
    return fresh["result"]


def binding(context):
    run = context["run"]
    return dict(context_id=context["context_id"], variant_id=context["selection"]["variant_id"],
                current_revision_id=context["project"]["revision_id"],
                component_id=context["selection"]["component_id"],
                run_id=None if run is None else run["run_id"],
                snapshot_id=None if run is None else run["snapshot_id"],
                run_revision_id=None if run is None else run["revision_id"])


def citation(context, pointer, component_id=None):
    refs = [r for r in context["source_references"] if pointer == r["context_pointer"]
            or pointer.startswith(r["context_pointer"].rstrip("/") + "/")]
    require(bool(refs), "No backend provenance for " + pointer, "integrity_error")
    source = max(refs, key=lambda r: len(r["context_pointer"]))
    suffix = pointer[len(source["context_pointer"]):]
    result = dict(context_id=context["context_id"], context_pointer=pointer,
                  reference_id=source["id"], operation=source["operation"],
                  arguments=copy.deepcopy(source["arguments"]),
                  source_pointer=source["source_pointer"] + suffix,
                  revision_id=source["revision_id"])
    for key in ["run_id", "snapshot_id", "component_id"]:
        if key in source:
            result[key] = source[key]
    if component_id is not None:
        result["component_id"] = component_id
    return result


def claim(context, pointer, kind, label, unit=None, component_id=None):
    result = dict(kind=kind, label=label, value=copy.deepcopy(value_at(context, pointer)),
                  source=citation(context, pointer, component_id))
    if unit is not None:
        result["unit"] = unit
    return result


def edit_pointer(edit):
    target, prop = edit["target"], edit["property"]
    prefix = "/project/design/"
    if target in ("cell", "connection"):
        return prefix + ("cells/" if target == "cell" else "connections/") + pointer_part(edit["id"]) + "/" + pointer_part(prop)
    if target == "requirements":
        return prefix + "requirements"
    return prefix + pointer_part(target) + "/" + pointer_part(prop)


def preview(project_path, context, edit):
    exact(edit, ["target", "id", "property", "value", "unit", "source", "classification"], "edit")
    variant = context["selection"]["variant_id"]
    revision = context["project"]["revision_id"]
    validation = Project(project_path).validate_edit(variant, edit, revision)
    # Reading and validation are separate backend calls. Detect a changed design
    # or run context during either call; no action token/executor is issued.
    current_context(project_path, {"status": "ok", "result": context})
    pointer = edit_pointer(edit)
    payload = dict(binding=binding(context), proposed_edit=copy.deepcopy(edit))
    return dict(schema=SCHEMA, operation="preview_edit", status="approval_required",
                preview_id="sha256:" + hashlib.sha256(canonical(payload)).hexdigest(),
                **payload, before=claim(context, pointer, "existing_input", "Current configured input", component_id=edit["id"]),
                validation=validation, proposed_input_classification=edit["classification"],
                supplied_source_text=dict(value=edit["source"], classification="unverified user-supplied provenance text"),
                predicted_effect=None, prediction_status="not calculated; a later approved edit and solver run are required",
                applied=False, simulation_started=False,
                approval_scope="Human review of this exact preview; this adapter cannot accept approval or execute actions",
                decision="insufficient evidence", unavailable_capabilities=UNAVAILABLE,
                limitations=copy.deepcopy(context["limitations"]))


def input_claims(context):
    result = []
    selected = context["selection"]["component_id"]
    design = context["project"]["design"]
    cell_ids = list(design["cells"]) if selected == "module" else [selected] if selected in design["cells"] else []
    connection_ids = list(design["connections"]) if selected == "module" else [selected] if selected in design["connections"] else []
    for cid in cell_ids:
        base = "/project/design/cells/" + pointer_part(cid)
        result.append(claim(context, base + "/identity", "component_identity", "Dataset cell identity", component_id=cid))
        result.append(claim(context, base + "/model", "fitted_artifact_reference", "Frozen model provenance", component_id=cid))
        for prop in ("initial_soc", "initial_polarization"):
            item = design["cells"][cid][prop]
            result.append(claim(context, base + "/" + prop, "configured_input", prop.replace("_", " "), item["unit"], cid))
        fit_base = "/project/fitted_parameters/" + pointer_part(cid)
        for key, unit in [("R0_ohm", "ohm"), ("R1_ohm", "ohm"), ("tau_s", "s"), ("capacity_Ah", "Ah")]:
            result.append(claim(context, fit_base + "/" + key, "derived_capacity" if key == "capacity_Ah" else "fitted_parameter", key, unit, cid))
    for cid in connection_ids:
        result.append(claim(context, "/project/design/connections/" + pointer_part(cid) + "/resistance",
                            "configured_input", "Effective connection resistance", "ohm", cid))
    for suffix, label, unit in [("load_profile", "Configured load intervals", "A,s"),
                                ("temperature", "Temperature assumptions; no thermal prediction", "degC")]:
        result.append(claim(context, "/project/design/scenario/" + suffix, "configured_input", label, unit, "module"))
    return result


def explain(context):
    run, series = context["run"], context["series"]
    claims = input_claims(context)
    claims.append(claim(context, "/project/design/requirements", "configured_requirements", "Current design requirements", component_id="module"))
    claims.append(claim(context, "/project/experimental_validation", "experimental_evidence_status", "Experimental module validation"))
    if run is None:
        return dict(schema=SCHEMA, operation="explain", status="configuration_only", binding=binding(context),
                    claims=claims, run_status=None, requirement_check=None, coverage=None,
                    explanation="This context contains configuration and fitted values only; no saved run was selected.",
                    decision="insufficient evidence", unavailable_capabilities=UNAVAILABLE,
                    limitations=copy.deepcopy(context["limitations"]))
    summary = run["summary"]
    run_status = {key: copy.deepcopy(run[key]) for key in ("execution_status", "freshness", "outdated_reasons", "error")}
    for key, unit in SUMMARY_UNITS.items():
        if key in summary:
            claims.append(claim(context, "/run/summary/" + key, "simulated_output", key, unit, "module"))
    for key in ("decision", "decision_reasons", "experimental_validation", "voltage_requirement", "coverage"):
        if key in summary:
            claims.append(claim(context, "/run/summary/" + key, "solver_evidence_status", key))
    # Values are exact stored samples, not interpolation or an AI prediction.
    if series is not None and series["rows"]:
        indices = sorted({0, len(series["rows"]) - 1})
        for index in indices:
            claims.append(claim(context, f"/series/rows/{index}", "simulated_sample", "Stored sample with field units",
                                component_id=series["component_id"]))
        claims.append(claim(context, "/series/units", "units", "Units of stored sample fields", component_id=series["component_id"]))
    requirement = copy.deepcopy(summary.get("voltage_requirement"))
    notes = ["All numerical output claims are copied from saved solver evidence; no physical outcome was calculated here."]
    if run["execution_status"] != "completed":
        notes.append("The selected run failed; retained samples and summary describe partial execution, not completed service.")
    if run["freshness"] != "current":
        notes.append("The selected run is outdated for this variant; configuration claims describe its current revision, while output claims identify the historical run and snapshot.")
    if requirement is None:
        notes.append("No requirement-check result is available; this is not a pass.")
    elif requirement.get("status") == "requirement not configured":
        notes.append("The voltage requirement is not configured; no pass is asserted.")
    else:
        notes.append("The requirement screen is a simulation result only; it does not establish experimental acceptance.")
    notes.append("Electrical losses do not predict temperature. Current module evidence is insufficient for a validated repair or battery-performance gain.")
    return dict(schema=SCHEMA, operation="explain", status="evidence_explanation", binding=binding(context),
                claims=claims, run_status=run_status, requirement_check=requirement,
                coverage=copy.deepcopy(summary.get("coverage")),
                evidence_pagination=None if series is None else {k: series[k] for k in ("offset", "total_samples", "next_offset")},
                explanation=" ".join(notes), decision="insufficient evidence",
                unavailable_capabilities=UNAVAILABLE, limitations=copy.deepcopy(context["limitations"]))


def handle_request(project_path, request):
    """Return a JSON envelope; the only allowed actions are read-only operations."""
    try:
        require(len(canonical(request)) <= MAX_REQUEST_BYTES, "Request is too large")
        exact(request, ["operation", "context", "arguments"], "copilot request")
        operation = request["operation"]
        require(isinstance(operation, str) and operation in ("preview_edit", "explain"),
                "Only structured edit previews and evidence explanations are available", "unsupported_request")
        args = request["arguments"]
        exact(args, ["edit"] if operation == "preview_edit" else [], "arguments")
        context = current_context(project_path, request["context"])
        result = preview(project_path, context, args["edit"]) if operation == "preview_edit" else explain(context)
        return dict(status="ok", result=result)
    except RequestError as exc:
        return dict(status="error", error=dict(code=exc.code, message=str(exc)))
    except (ValueError, TypeError, KeyError, OSError, OverflowError, RecursionError) as exc:
        return dict(status="error", error=dict(code="invalid_request", message=str(exc)))


def unique_object(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError("Duplicate JSON field: " + key)
        obj[key] = value
    return obj


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--request", type=Path, help="JSON request file; stdin if omitted")
    args = parser.parse_args(argv)
    try:
        if args.request:
            with args.request.open("rb") as stream:
                content = stream.read(MAX_REQUEST_BYTES + 1)
        else:
            content = sys.stdin.buffer.read(MAX_REQUEST_BYTES + 1)
        require(len(content) <= MAX_REQUEST_BYTES, "Request is too large")
        request = json.loads(content.decode("utf-8-sig"), object_pairs_hook=unique_object)
        response = handle_request(args.project, request)
    except (ValueError, OSError, UnicodeError) as exc:
        response = dict(status="error", error=dict(code="invalid_request", message=str(exc)))
    print(json.dumps(response, indent=2, allow_nan=False))
    return 0 if response["status"] == "ok" else 2


if __name__ == "__main__":
    raise SystemExit(main())
