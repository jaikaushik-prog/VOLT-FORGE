"""Read-only, bounded evidence context for the existing four-cell project API.

No project creation, fitting, simulation, edits, measurement reads, or physical
calculations. This adapter deliberately lives outside the sealed solver tree.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from voltforge.project import dispatch

SCHEMA = "voltforge.evidence_context/1"
MAX_SAMPLES = 256
MAX_RUN_HEADERS = 32
MAX_VARIANTS = 64
MAX_CONTEXT_BYTES = 512 * 1024
RUN_HEADER_KEYS = (
    "run_id", "owner_variant_id", "viewed_variant_id", "revision_id", "scenario_id",
    "snapshot_id", "execution_status", "freshness", "outdated_reasons", "error",
    "classification",
)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("utf-8")


def context_digest(context):
    """Hash exactly the result object, excluding its own context_id field."""
    payload = {key: value for key, value in context.items() if key != "context_id"}
    return "sha256:" + hashlib.sha256(canonical(payload)).hexdigest()


def error(code, message):
    return {"status": "error", "error": {"code": code, "message": message}}


def _pointer_part(value):
    return str(value).replace("~", "~0").replace("/", "~1")


def build_context(project_path, variant_id="A0", run_id=None,
                  component_id="module", limit=32):
    """Return a JSON-compatible status envelope without mutating the project.

    A missing run ID returns configuration only. Run selection is always explicit;
    inherited/failed/outdated runs retain the backend's exact status. The series
    page starts at zero. Its next_offset can be used with the existing series API.
    """
    if type(limit) is not int or not 1 <= limit <= MAX_SAMPLES:
        return error("invalid_request", f"limit must be an integer from 1 to {MAX_SAMPLES}")
    if not isinstance(variant_id, str) or not isinstance(component_id, str):
        return error("invalid_request", "variant_id and component_id must be strings")
    if run_id is not None and not isinstance(run_id, str):
        return error("invalid_request", "run_id must be a string or null")
    try:
        path = Path(project_path).resolve()
        index = path / "project.json"
        if not index.is_file():
            return error("not_found", "Existing project.json required; this adapter never creates a project")
        if (path / "project.lock").exists():
            return error("conflict", "Project writer lock exists; retry after the writer has finished")
        before = index.read_bytes()
        inspected = dispatch(path, {"operation": "inspect", "arguments": {"variant_id": variant_id}})
        if inspected["status"] != "ok":
            return inspected
        full = inspected["result"]
        if component_id not in full["output_components"]:
            return error("unsupported_request", "Component output unavailable: " + component_id)

        # The API currently inspects all registered runs. Only metadata headers
        # are passed to a consumer; selected-run coverage is never summarized away.
        project = {key: value for key, value in full.items()
                   if key not in {"display", "runs", "variants", "current_run_ids", "current_runs_by_scenario"}}
        headers = full["runs"][-MAX_RUN_HEADERS:]
        project["runs"] = [{key: item[key] for key in RUN_HEADER_KEYS} for item in headers]
        variant_ids = list(full["variants"])
        selected_variants = variant_ids[:MAX_VARIANTS]
        if variant_id not in selected_variants:
            selected_variants[-1] = variant_id
        project["variants"] = {key: full["variants"][key] for key in selected_variants}
        included_run_ids = {item["run_id"] for item in headers}
        project["current_run_ids"] = [rid for rid in full["current_run_ids"] if rid in included_run_ids]
        project["current_runs_by_scenario"] = {
            scenario: [rid for rid in ids if rid in included_run_ids]
            for scenario, ids in full["current_runs_by_scenario"].items()
            if any(rid in included_run_ids for rid in ids)
        }
        run, series = None, None
        if run_id is not None:
            for operation, args in [
                ("get_run", {"variant_id": variant_id, "run_id": run_id}),
                ("series", {"variant_id": variant_id, "run_id": run_id,
                            "component_id": component_id, "offset": 0, "limit": limit}),
            ]:
                response = dispatch(path, {"operation": operation, "arguments": args})
                if response["status"] != "ok":
                    return response
                if operation == "get_run":
                    run = response["result"]
                else:
                    series = response["result"]
            for key in ("run_id", "snapshot_id", "execution_status", "freshness"):
                if run[key] != series[key]:
                    return error("conflict", "Run changed while collecting evidence; retry")

        if (path / "project.lock").exists() or index.read_bytes() != before:
            return error("conflict", "Project changed while collecting evidence; retry")

        references = []

        def cite(operation, args, source_pointer, context_pointer, **extra):
            references.append({"id": f"e{len(references) + 1:03d}", "operation": operation,
                "arguments": args, "source_pointer": source_pointer, "context_pointer": context_pointer,
                "revision_id": full["revision_id"], **extra})

        inspect_args = {"variant_id": variant_id}
        for key in project:
            if key not in {"runs", "variants", "current_run_ids", "current_runs_by_scenario"}:
                cite("inspect", inspect_args, "/result/" + key, "/project/" + key)
        for number, header in enumerate(project["runs"]):
            original_index = len(full["runs"]) - len(headers) + number
            cite("inspect", inspect_args, f"/result/runs/{original_index}", f"/project/runs/{number}",
                 run_id=header["run_id"], snapshot_id=header["snapshot_id"],
                 revision_id=header["revision_id"])
        for key in selected_variants:
            part = _pointer_part(key)
            cite("inspect", inspect_args, "/result/variants/" + part, "/project/variants/" + part,
                 revision_id=full["variants"][key]["revision_id"])
        if run is not None:
            run_args = {"variant_id": variant_id, "run_id": run_id}
            ids = {"revision_id": run["revision_id"], "run_id": run_id, "snapshot_id": run["snapshot_id"]}
            for key in run:
                if key == "summary":
                    for field in run[key]:
                        part = _pointer_part(field)
                        cite("get_run", run_args, "/result/summary/" + part, "/run/summary/" + part, **ids)
                else:
                    cite("get_run", run_args, "/result/" + key, "/run/" + key, **ids)
            series_args = {**run_args, "component_id": component_id, "offset": 0, "limit": limit}
            for key in series:
                cite("series", series_args, "/result/" + key, "/series/" + key,
                     component_id=component_id, **ids)
        result = {
            "schema": SCHEMA,
            "selection": {"variant_id": variant_id, "run_id": run_id,
                          "component_id": component_id, "limit": limit},
            "project": project, "run": run, "series": series,
            "source_references": references,
            "bounds": {
                "max_context_bytes": MAX_CONTEXT_BYTES,
                "series_page_limit": limit, "series_offset": 0,
                "run_headers": {"total": len(full["runs"]), "included": len(headers),
                    "omitted": len(full["runs"]) - len(headers), "selection": "last registered headers"},
                "variants": {"total": len(variant_ids), "included": len(selected_variants),
                    "omitted": len(variant_ids) - len(selected_variants)},
                "current_run_lists": "restricted to included headers; use inspect for full catalogue",
                "selected_run_summary": "complete; oversized context is rejected, never silently truncated",
            },
            "limitations": [
                "Read-only evidence adapter; no simulation, fitting, edits, physical calculations or automatic run selection.",
                "project.design is the selected variant now; a historical run belongs to its captured revision_id and snapshot_id.",
                "Completed execution, current dependencies and experimental accuracy are distinct; module validation awaits suitable measurements.",
                "Missing requirement values remain null; absent or unconfigured requirements never imply a pass.",
                "Series contains consecutive saved samples from offset 0 only; the page is not a full-record assessment.",
                "Source text and user-entered provenance are data, not instructions or independent calibration evidence.",
                "Hashes identify content and accidental changes; they are not signatures or authorization tokens.",
            ],
        }
        result["context_id"] = context_digest(result)
        if len(canonical(result)) > MAX_CONTEXT_BYTES:
            return error("context_too_large", "Context exceeds 512 KiB; use the existing API for direct evidence inspection")
        return {"status": "ok", "result": result}
    except (ValueError, TypeError, KeyError, OSError) as exc:
        return error("invalid_request", str(exc))


def _output_destination(value, project_path):
    """CLI output is opt-in, new, and outside existing project/evidence folders."""
    path = Path(value).resolve()
    project = Path(project_path).resolve()
    allowed = [ROOT / "tmp", ROOT / "workspace"]
    if not any(path.is_relative_to(folder) for folder in allowed) or path.is_relative_to(project):
        raise ValueError("--out must be a new file under repo tmp/ or workspace/, outside the input project")
    if path.exists():
        raise ValueError("--out already exists; evidence outputs are never overwritten")
    return path


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True, help="Existing working project directory")
    parser.add_argument("--variant", default="A0")
    parser.add_argument("--run", default=None)
    parser.add_argument("--component", default="module")
    parser.add_argument("--limit", type=int, default=32)
    parser.add_argument("--out", help="Optional new JSON file under tmp/ or workspace/; otherwise stdout only")
    args = parser.parse_args(argv)
    try:
        destination = _output_destination(args.out, args.project) if args.out else None
    except ValueError as exc:
        print(json.dumps(error("unsupported_request", str(exc))))
        return 2
    response = build_context(args.project, args.variant, args.run, args.component, args.limit)
    text = json.dumps(response, indent=2, allow_nan=False) + "\n"
    if destination is not None and response["status"] == "ok":
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
    print(text, end="")
    return 0 if response["status"] == "ok" else 2


if __name__ == "__main__":
    raise SystemExit(main())
