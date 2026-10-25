"""Local command mode: deterministic grammar, read-only backend delegation.

No LLM, network provider, executor, optimizer or physical calculation is present.
Only explicit input-unit conversion is performed by the parser.
"""
from __future__ import annotations

import argparse
import copy
from decimal import Decimal, InvalidOperation
import json
import math
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
for _path in (ROOT, ROOT / "src"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from scripts.copilot_contract import binding, canonical, current_context, exact, handle_request, require, unique_object
from scripts.evidence_context import build_context
from voltforge.project import Project
from voltforge.project.schema import RequestError

SCHEMA = "voltforge.local_assistant/1"
MAX_MESSAGE_CHARACTERS = 400
MAX_REQUEST_BYTES = 16 * 1024
CONTEXT_SAMPLES = 4
NUMBER = r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)"
PREFIX = r"(?i:preview(?: change)?) "
RAILS = {f"rail_{rail}_{index}" for rail in ("p", "n") for index in range(1, 4)}
CELLS = {f"cell_{index}" for index in range(1, 5)}
COMPONENTS = {"module"} | RAILS | CELLS
COMPARISON_UNITS = {
    "maximum_branch_current_A": "A", "minimum_cell_voltage_V": "V",
    "minimum_terminal_voltage_V": "V", "mean_delivered_power_W": "W",
    "delivered_net_Wh": "Wh", "delivered_charge_Ah": "Ah",
    "cell_R0_loss_Wh": "Wh", "rail_loss_Wh": "Wh", "R1_loss_Wh": "Wh",
    "above_4_9A_cell_seconds": "cell s",
}
RUN_HEADER_FIELDS = ["run_id", "owner_variant_id", "viewed_variant_id", "revision_id",
                     "scenario_id", "snapshot_id", "execution_status", "freshness",
                     "outdated_reasons", "error", "classification"]
WARNINGS = [
    "Local command mode matches a fixed grammar; it is not a language model or open-ended assistant.",
    "No project edit or simulation is executed. Previewed inputs require separate human review.",
    "Experimental module validation is awaiting suitable measurements; no repair ranking or battery-performance gain is established.",
    "Electrical losses do not predict temperature. Thermal simulation and optimization are unavailable.",
]
HELP = {
    "kind": "command_help",
    "description": "Use one complete command. Keywords ignore case; engineering unit symbols keep their exact case.",
    "commands": [
        "help", "show commands", "explain this result", "show evidence",
        "compare selected runs", "compare the selected runs",
        "preview change selected rail to 0.5 mOhm",
        "preview change positive rail 1 to 0.001 ohm",
        "preview negative rail 3 to 1 mΩ",
        "preview change selected cell initial SOC to 70 %",
        "preview selected cell SOC to 69.5%",
        "preview change selected polarization to -5 mV",
        "preview selected cell initial polarization to 0.005 V",
        "preview change timestep to 0.5 s",
        "preview time step to 0.25 s",
    ],
    "notes": [
        "Example numbers are syntax examples, not measured inputs or design recommendations.",
        "Select the target component first. An explicit rail name must match that selection; timestep requires Module.",
        "Select two saved runs explicitly for comparison; only identical operating conditions are accepted.",
        "Decimal notation only. Resistance units: mOhm, mΩ, ohm. SOC: %. Polarization: mV or V. Timestep: s.",
        "No load, topology, cell-identity, fitted-parameter, thermal or requirement edits are inferred from text.",
        "No compound instructions, automatic apply/run, invented outcomes, implicit units or latest-run selection.",
    ],
}


def identifier(value, label):
    require(isinstance(value, str) and re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,47}", value), "Invalid " + label)


def validate_selection(selection):
    exact(selection, ["variant_id", "revision_id", "component_id", "run_id"], "selection")
    identifier(selection["variant_id"], "variant ID")
    require(isinstance(selection["revision_id"], str) and re.fullmatch(r"rev_[0-9a-f]{64}", selection["revision_id"]),
            "An exact current revision ID is required")
    require(isinstance(selection["component_id"], str) and selection["component_id"] in COMPONENTS,
            "Select an implemented four-cell component", "unsupported_request")
    if selection["run_id"] is not None:
        identifier(selection["run_id"], "run ID")


def validate_comparison(comparison):
    if comparison is None:
        return
    exact(comparison, ["first", "second"], "comparison")
    for key in ("first", "second"):
        exact(comparison[key], ["variant_id", "run_id"], "comparison " + key)
        identifier(comparison[key]["variant_id"], "comparison variant ID")
        identifier(comparison[key]["run_id"], "comparison run ID")


def parse_command(message, component_id):
    """Complete-string parsing and unit conversion only; no model inference."""
    require(isinstance(message, str) and 0 < len(message) <= MAX_MESSAGE_CHARACTERS,
            "Enter one command of 1 to 400 characters")
    require(not any(ord(char) < 32 or ord(char) == 127 for char in message),
            "Use one line without control characters")
    normalized = re.sub(r" +", " ", message.strip(" "))
    require(bool(normalized), "Enter a command")
    require(isinstance(component_id, str) and component_id in COMPONENTS, "Select an implemented component", "unsupported_request")
    words = normalized.casefold()
    simple = {"help": "help", "show commands": "help", "explain this result": "explain",
              "show evidence": "explain", "compare selected runs": "compare", "compare the selected runs": "compare"}
    if words in simple:
        return {"action": simple[words], "normalized_message": normalized, "input_conversion": None}

    match = re.fullmatch(PREFIX + r"(?P<target>(?i:selected rail|positive rail [1-3]|negative rail [1-3])) (?i:to) "
                         + rf"(?P<number>{NUMBER}) *(?P<unit>mOhm|mΩ|ohm)", normalized)
    if match:
        target_name = match["target"].casefold()
        target_id = component_id if target_name == "selected rail" else "rail_" + ("p" if target_name.startswith("positive") else "n") + "_" + target_name[-1]
        require(target_id in RAILS and target_id == component_id,
                "Select the requested rail first, then repeat the command; targets are never changed implicitly", "selection_mismatch")
        target, prop, unit = "connection", "resistance", "ohm"
        divisor = 1000 if match["unit"] in ("mOhm", "mΩ") else 1
    else:
        match = re.fullmatch(PREFIX + r"(?i:selected cell (?:initial )?soc to) " + rf"(?P<number>{NUMBER}) *(?P<unit>%)", normalized)
        if match:
            require(component_id in CELLS, "Select a cell before previewing its initial SOC", "selection_mismatch")
            target_id, target, prop, unit, divisor = component_id, "cell", "initial_soc", "fraction", 100
        else:
            match = re.fullmatch(PREFIX + r"(?i:selected (?:cell initial )?polarization to) "
                                 + rf"(?P<number>{NUMBER}) *(?P<unit>mV|V)", normalized)
            if match:
                require(component_id in CELLS, "Select a cell before previewing its initial polarization", "selection_mismatch")
                target_id, target, prop, unit = component_id, "cell", "initial_polarization", "V"
                divisor = 1000 if match["unit"] == "mV" else 1
            else:
                match = re.fullmatch(PREFIX + r"(?i:time ?step to) " + rf"(?P<number>{NUMBER}) *(?P<unit>s)", normalized)
                require(match is not None,
                        "Command not supported. Type help for complete supported phrases and explicit units; no compound instructions are accepted",
                        "unsupported_command")
                require(component_id == "module", "Select Module before previewing the timestep", "selection_mismatch")
                target_id, target, prop, unit, divisor = "module", "simulation", "dt_s", "s", 1
    value = float(Decimal(match["number"]) / Decimal(divisor))
    require(math.isfinite(value), "The requested numeric input is not finite")
    change = dict(target=target, id=target_id, property=prop, value=value, unit=unit,
                  source="User-proposed local command: " + message, classification="assumed")
    return dict(action="preview_edit", normalized_message=normalized, edit=change,
                input_conversion=dict(entered_value=match["number"], entered_unit=match["unit"],
                                      normalized_value=value, normalized_unit=unit,
                                      rule="Explicit input-unit conversion only; divide entered value by " + str(divisor)))


def successful(envelope):
    if envelope["status"] != "ok":
        raise RequestError(envelope["error"]["code"], envelope["error"]["message"])
    return envelope["result"]


def selected_context(project_path, selection):
    context = build_context(project_path, variant_id=selection["variant_id"], run_id=selection["run_id"],
                            component_id=selection["component_id"], limit=CONTEXT_SAMPLES)
    data = successful(context)
    require(data["project"]["revision_id"] == selection["revision_id"],
            "The selected design revision changed; reload the current selection before issuing a command", "stale_context")
    return context


def compare_runs(project_path, comparison):
    require(comparison is not None, "Select the first and second saved runs explicitly before comparing", "invalid_request")
    selections = [copy.deepcopy(comparison[key]) for key in ("first", "second")]
    require(selections[0] != selections[1], "Select two distinct run/variant entries", "invalid_request")
    contexts = [build_context(project_path, **item, component_id="module", limit=1) for item in selections]
    views = [successful(context)["run"] for context in contexts]
    payload = Project(project_path).compare(selections)
    headers = []
    for index, (item, context, view) in enumerate(zip(selections, contexts, views)):
        row = payload["ordered_results"][index]
        require(row["run_id"] == view["run_id"] and row["snapshot_id"] == view["snapshot_id"]
                and row["freshness"] == view["freshness"], "Comparison evidence changed while being collected", "conflict")
        current_context(project_path, context)
        headers.append({**{key: copy.deepcopy(view[key]) for key in RUN_HEADER_FIELDS},
                        "source": dict(operation="get_run", arguments=item, source_pointer="/result",
                                       context_id=context["result"]["context_id"])})
    reference = dict(operation="compare", arguments={"selections": copy.deepcopy(selections)})
    references = [dict(**reference, source_pointer="/result", payload_pointer="")]
    for index, view in enumerate(views):
        references.append(dict(**reference, source_pointer=f"/result/ordered_results/{index}",
                               payload_pointer=f"/ordered_results/{index}", run_id=view["run_id"],
                               snapshot_id=view["snapshot_id"], revision_id=view["revision_id"],
                               owner_variant_id=view["owner_variant_id"], viewed_variant_id=view["viewed_variant_id"]))
    references.append(dict(**reference, source_pointer="/result/deltas_vs_first/0", payload_pointer="/deltas_vs_first/0",
                           compared_run_ids=[view["run_id"] for view in views],
                           compared_snapshot_ids=[view["snapshot_id"] for view in views]))
    metadata = dict(selections=selections, runs=headers, units=copy.deepcopy(COMPARISON_UNITS),
                    units_source="Existing Project.compare metric schema; these units are metadata, not calculated values",
                    source_references=references)
    return payload, metadata, contexts


def handle_command(project_path, request):
    """Read-only service. Mutation and physics operations are not in its grammar."""
    try:
        require(len(canonical(request)) <= MAX_REQUEST_BYTES, "Command request exceeds 16 KiB")
        exact(request, ["message", "selection", "comparison"], "local command request")
        validate_selection(request["selection"])
        validate_comparison(request["comparison"])
        parsed = parse_command(request["message"], request["selection"]["component_id"])
        context = selected_context(project_path, request["selection"])
        action = parsed["action"]
        comparison, compared_contexts = None, []
        if action == "help":
            payload = copy.deepcopy(HELP)
        elif action == "compare":
            payload, comparison, compared_contexts = compare_runs(project_path, request["comparison"])
        else:
            payload = successful(handle_request(project_path, dict(operation=action, context=context,
                arguments={"edit": parsed["edit"]} if action == "preview_edit" else {})))
        # The evidence and comparison calls are read-only but not a transactional
        # snapshot. Recheck every context, including the selected design, before
        # returning; applying later still requires the separate existing API.
        for checked in [context, *compared_contexts]:
            current_context(project_path, checked)
        evidence = dict(context_id=context["result"]["context_id"], binding=binding(context["result"]),
                        command=dict(message=request["message"], normalized_message=parsed["normalized_message"],
                                     input_conversion=parsed["input_conversion"]), comparison=comparison)
        warnings = copy.deepcopy(WARNINGS)
        if action == "compare" and payload["historical_results"]:
            warnings.append("This comparison includes historical/outdated saved results; both original owners and snapshots are retained.")
        if action == "compare" and comparison["runs"][0]["run_id"] == comparison["runs"][1]["run_id"]:
            warnings.append("Both selected entries refer to the same saved run viewed from different variants; no new simulation was performed.")
        return dict(status="ok", result=dict(schema=SCHEMA, mode="local_commands", action=action,
            selection=copy.deepcopy(request["selection"]), payload=payload,
            context=context if action == "preview_edit" else None, evidence=evidence, warnings=warnings,
            applied=False, simulation_started=False))
    except RequestError as exc:
        return dict(status="error", error=dict(code=exc.code, message=str(exc)))
    except (ValueError, TypeError, KeyError, OSError, OverflowError, InvalidOperation, RecursionError) as exc:
        return dict(status="error", error=dict(code="invalid_request", message=str(exc)))


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
        require(len(content) <= MAX_REQUEST_BYTES, "Command request exceeds 16 KiB")
        request = json.loads(content.decode("utf-8-sig"), object_pairs_hook=unique_object)
        response = handle_command(args.project, request)
    except (ValueError, OSError, UnicodeError) as exc:
        response = dict(status="error", error=dict(code="invalid_request", message=str(exc)))
    print(json.dumps(response, indent=2, allow_nan=False))
    return 0 if response["status"] == "ok" else 2


if __name__ == "__main__":
    raise SystemExit(main())
