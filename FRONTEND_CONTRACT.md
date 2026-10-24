# Four-cell frontend contract — version 1

The local 2D editor now implements this contract. Start with
`python scripts/run_editor.py --open`; see [EDITOR_GUIDE.md](EDITOR_GUIDE.md) for
controls and the thin loopback HTTP/job adapter. The underlying Python interface,
schemas and electrical solver are unchanged. Original handoff document bytes are
preserved in `reports/editor_v1/previous/FRONTEND_CONTRACT.md`.

A separate **read-only P45B measurement profile** is available at `/measurements`.
Its additive GET routes, exact generated responses, access allocation and errors
are documented in [measurement usage](reports/measurement_viewer_v1/USAGE.md).
These routes do not change this LG project schema, physics hash or validation
import contract. Measured records cannot be selected as simulated LG runs.

The frontend connects to `voltforge.project.Project` or the JSON-compatible
`voltforge.project.dispatch(project_path, request)` function. This is a synchronous
local Python interface, with a JSON CLI adapter. It calls the existing electrical
backend; it does not fit models or invent outputs. Use Python 3.12 with the pinned
repository requirements. Run the Python examples from the repository root with
`PYTHONPATH=src`. No HTTP server or frontend framework is required.

The supported module is LG M50T NMC P7/P17/P19/P13, in that position order, in a
same-side-terminal 1s4p ladder. A0 is a proposed simulation case using fitted cell
models and assumed connections/initial states, not an experimentally validated
module reconstruction. Other topologies, rewiring, cell substitution, thermal
simulation, CAD-derived resistance and optimization return `unsupported_request`.

## Shared state and electrical mapping

`project.json` uses schema `voltforge.project/1`. Strict design validation and the
editor-to-solver mapping are implemented in
[`schema.py`](src/voltforge/project/schema.py); `voltforge.design/1` is the design
schema. Unknown design fields/units, missing connections and unsupported models
are rejected. Unknown project schema versions require an explicit future migration.

| Stored object | Fields and meaning |
|---|---|
| Project index | Schema/project ID; asset hashes; named `variants`; saved `runs`; measurement evidence; capabilities; display state. |
| Variant | Stable variant ID, user-facing name, immutable `revision_id`, owned run IDs, inherited run IDs. Variant IDs are case-insensitively unique. |
| Design revision | `design`, parent revision ID, exact edit/provenance, UTC creation time. The filename is the SHA-256 of the complete revision record. Never updated in place. |
| Cell | Stable `cell_1`…`cell_4` ID; dataset identity; LG M50T/NMC; positive and negative nodes; frozen-v2 fitted artifact path/key/hash/version; initial SOC/polarization quantities with units and provenance. |
| Connection | Stable `rail_p_1`…`rail_p_3`, `rail_n_1`…`rail_n_3`; explicit node pair; rail identity; resistance `{value, unit, classification, source}`. |
| Scenario | Explicit load intervals and units/polarity; load provenance; assumed ambient and four surface temperatures; evidence and disabled thermal/scaling flags. |
| Simulation settings | Maximum step `dt_s`; extrapolation forbidden; explicit unvalidated-waveform investigation permission; thermal model disabled. |
| Requirements | `minimum_terminal_voltage_V`, `maximum_contiguous_excursion_s`, `documented_source`, each initially null. Missing any required item means **requirement not configured**. |
| Display | Optional component positions in arbitrary display coordinates, camera metadata and selected component IDs. Never part of a design revision or solver input. |
| Run | Unique ID, owner variant, revision/scenario/snapshot IDs, captured code/runtime version, immutable execution status/error, hashes of saved outputs. |
| Snapshot | Entire design, effective solver case including actual model values, scenario overrides, source/asset hashes and software/runtime dependencies. Recorded before execution. |

The eight electrical nodes are `p1..p4` and `n1..n4`. Cell k connects pk to nk.
Positive rail edge k joins pk to p(k+1); negative edge k joins nk to n(k+1).
The module's positive terminal is p1, negative terminal and potential reference
are n1. There are no modeled external leads. Cell voltage is pk minus nk.
Positive rail current is reported toward the module terminal (p(k+1) to pk);
negative rail current is reported outward (nk to n(k+1)). Positive rail drop is
p(k+1)-pk; negative drop is nk-n(k+1), matching the stored solver channels.

A rendered wire must use one of these connection IDs/node pairs. Touching or
moving a shape changes no connection, length, resistance or thermal boundary.
Display coordinates are not millimetres and do not imply physical feasibility.

## Exact editor properties

`inspect` returns the same editable-property catalogue used by validation:

| Target / property | IDs | Unit | Supported change |
|---|---|---|---|
| `connection / resistance` | Six rail IDs | `ohm` | Finite nonnegative effective segment resistance; explicit provenance. Zero is an idealized numerical connection, not a measured perfect conductor. |
| `cell / initial_soc` | Four cell IDs | `fraction` | SOC relative to the fixed cell reference, inside its mathematical support and [0,1]. |
| `cell / initial_polarization` | Four cell IDs | `V` | Finite initial one-RC state assumption. |
| `scenario / load_profile` | `module` | `A,s` | Array of `{start_s,end_s,current_A}` intervals, contiguous from zero. Current is discharge-positive. |
| `scenario / temperature` | `module` | `degC` | Complete assumed ambient/surface metadata object. `thermal_model` and `parameter_temperature_scaling` must stay false. This changes evidence applicability, not resistance via a temperature law. |
| `simulation / dt_s` | `module` | `s` | Finite step >=1e-6, <=1,000,000 nominal steps per run. A numerical bound, not an accuracy guarantee. |
| `requirements / voltage_requirement` | `module` | `V,s` | Complete three-field requirement object. Nulls permitted and explicitly unconfigured; sources are never inferred. |

Every edit includes `target`, `id`, `property`, `value`, `unit`, `source`, and
`classification`. Classifications allowed for supplied values are `assumed`,
`proposed_requirement`, or `user_declared_measurement`. The latter is the user's
provenance assertion, not independently verified calibration. Fitted R0/R1/tau,
cell identity, reference anchors and model versions are read-only. Capacity is
derived from recorded C/20 integration and is also read-only in the editor.

The seven existing sensitivity scenarios are available through
`run_sensitivities` or a specific `run(..., scenario_id=...)`: `soc_minus_2pp`,
`soc_plus_2pp`, `capacity_minus_1pct`, `capacity_plus_1pct`,
`polarization_minus_5mV`, `polarization_plus_5mV`, `loaded_reference_shape`.
Each changes the effective run snapshot only; it never replaces the fitted model
or design. These are common four-cell, one-at-a-time scenarios, not independent
uncertainty distributions, confidence intervals or validated error bounds.
SOC perturbations hold the reference fixed; no new absolute SOC origin is inferred.
The old CLI retains paired coordinate checks and time-step sensitivity.

## Operations and response semantics

Every JSON request has exactly `operation` and `arguments`. Success is
`{"status":"ok","result":...}`. Request rejection is
`{"status":"error","error":{"code":...,"message":...}}`.
`invalid_request`, `unsupported_request`, `conflict`, `not_found` and
`integrity_error` are distinct error codes. A completed API call can contain a
**failed simulation**; always inspect `execution_status`.

| Operation | Arguments | Returned content |
|---|---|---|
| `load_reference` | `{}` | Create A0 in a new project directory, or open the existing project; inspect A0. Uses configured frozen artifacts, no raw archive access. |
| `inspect` | `variant_id` (default A0) | Full design, fitted read-only values, editable catalogue, variants, runs, capabilities, display state, current run IDs grouped by scenario. |
| `validate_edit` | `variant_id, edit, expected_revision` | Side-effect-free validation, proposed invalidation and evidence warnings. |
| `apply_edit` | Same | Apply only if the expected revision still matches; return inspected new revision. A no-op creates no revision. |
| `create_variant` | `source_variant, variant_id, name, expected_revision` | Named branch sharing the starting revision; old runs inherited for viewing only. |
| `update_display` | `display={positions,camera,selection}` | Updated display, `physics_changed:false`, no invalidated run IDs. |
| `run` | `variant_id, expected_revision`, optional `scenario_id="nominal", plots=true` | Saved run, summary, coverage and requirement screen, immutable execution status and computed freshness. |
| `get_run` | `variant_id, run_id` | Same run view, recomputing freshness rather than trusting a cached UI flag. |
| `series` | `variant_id, run_id`, optional `component_id="module", offset=0, limit=256` | Units, simulated label, rows, total sample count, next offset, snapshot/status/freshness. Limit 1–5000. |
| `compare` | `selections=[{variant_id,run_id},...]` | Unranked ordered metrics and differences from first selection; explicit common-condition hash. At least two completed runs required. |
| `run_sensitivities` | `variant_id, expected_revision`, optional `plots=false` | All seven declared full-sequence scenario runs and their labels. No random splitting or fitting. |
| `compare_measurements` | `variant_id, run_id, source` | Existing importer/comparison results, saved original measurements, metadata/hashes, calibration and alignment issues, current-conservation residuals. |
| `export` | `selections, out` | Immutable export directory, manifest hash, selected run IDs and pending-validation status. Destination must be new. |

Python methods have the same names/signatures. `Project.create_reference(path)`
is the constructor operation; `Project(path)` opens an existing project.
All mutations reload state, use an exclusive writer lock and atomically replace
the project index. The interface is synchronous and single-writer: a frontend
should call it in a worker and handle `conflict`, not invent a background job
status. Interrupted operations may leave an unregistered folder or `project.lock`;
inspect/recover these explicitly rather than overwriting evidence. HTTP hosting,
authentication, cancellation and collaboration are not implemented here.

### Freshness is separate from execution

- `execution_status="completed"`: the electrical solver reached requested end time.
- `execution_status="failed"`: a domain stop or execution error occurred; exact
  snapshot/error and any supported partial samples are retained.
- `freshness="outdated"`: viewed variant differs from run ownership, its design
  revision changed, or captured software/runtime differs from the current version.
- `freshness="current"` says only that dependencies still match. A failed run
  can be current; it is never listed as a usable current result.
- `unsupported_request` rejects an unavailable edit/topology/operation before a run.

Never choose the latest run globally. Use `current_runs_by_scenario` for the
selected variant and scenario, and bind every overlay to `run_id`, `snapshot_id`
and `component_id`. Even a physically identical cloned variant cannot call an
inherited run current. Visual edits retain revision and freshness. Changing a
requirement also creates a revision because the requirement screen is part of
the result. Changed software is conservatively invalidating, including adapters.

Historical completed runs can be compared explicitly, with outdated labels.
Like-for-like comparison rejects different load, starting state, temperature
assumptions, model/reference/capacity choices, requirements, time step or software.
The first workflow compares changed connections under identical conditions; the
existing scenario CLI separately reports reduced service for different loads.

## Outputs the frontend may display

Module series expose current, terminal voltage, power, positive/net delivered and
received energy, module charge, R0/rail/R1 losses, KCL and charge residuals.
Cell series expose branch current, cell voltage, relative SOC, polarization,
reference voltage, positive/negative node potentials and R0/R1 dissipation.
Rail series expose segment current, signed voltage drop and loss. Each `series`
response includes exact field units. No temperature, current-density field,
mechanical stress, cost, safety certification or optimized repair is produced.

`get_run.result.summary.coverage.cells` separates fitting and assessment evidence,
observed current directions/amplitudes/durations, reference/SOC support and
unsupported module transfer. Coverage absence on a failed zero-sample run does
not imply support: show the stop reason and initial snapshot. Module outputs are
**simulated**, never labelled experimentally validated. The importer separately
labels actual versus synthetic measurements; no rescaling is performed.

The 3.50 V alarm and 25 mV allowance are not defaults. An unset requirement is
not a pass; even a fully supplied requirement only enables a finite-step
simulated excursion screen with insufficient evidence for experimental acceptance.

## Usable Python and CLI examples

```python
from voltforge.project import dispatch

path = "tmp/frontend_trial"
loaded = dispatch(path, {"operation": "load_reference", "arguments": {}})
revision = loaded["result"]["revision_id"]
run = dispatch(path, {"operation": "run", "arguments": {
    "variant_id": "A0", "expected_revision": revision, "plots": False}})
series = dispatch(path, {"operation": "series", "arguments": {
    "variant_id": "A0", "run_id": run["result"]["run_id"],
    "component_id": "cell_1", "limit": 2}})
```

```powershell
$env:PYTHONPATH = 'src'
'{"operation":"load_reference","arguments":{}}' | & C:\Users\DELL\anaconda3\python.exe -m voltforge.project --project tmp/frontend_trial
& C:\Users\DELL\anaconda3\python.exe -m voltforge.project --project tmp/frontend_trial --request request.json
& C:\Users\DELL\anaconda3\python.exe scripts\demonstrate_product_workflow.py
```

CLI exit 0 means the request was handled; inspect the response for failed run or
outdated status. Rejected requests exit 2. The demo captures complete **actual**
request/response pairs in [examples](reports/product_integration_v1/demo/examples),
including edit validation, stale inherited results, A1's completed run, visual
invariance, series, comparison, export and unsupported/invalid requests. These
are generated by calling this implementation, not handwritten mock responses.
The [generated excerpts](reports/product_integration_v1/FRONTEND_EXAMPLES.md)
include full compact response examples ready for a teammate to inspect.

## Export and replay

Each package includes exact design ancestry, run snapshots/configuration, time
series, summaries/coverage, plots when requested, frozen model/reference assets,
evidence documents, source and runtime versions, comparison and a hash manifest.
Associated imported measurement originals are retained when present. The demo
exports only simulations; no protected assessment measurements are opened.

```powershell
& C:\Users\DELL\anaconda3\python.exe reports\product_integration_v1\demo\export\replay.py run_0001
& C:\Users\DELL\anaconda3\python.exe reports\product_integration_v1\demo\export\replay.py run_0002
```

Replay uses the captured implementation, checks versions and hashes, and compares
all numerical trajectory columns (rtol/atol 1e-10) without raw data or refitting.
Hashes detect accidental changes; they are not signatures. A different dependency
version requires an explicit reproduction review. Physics/software errors and
domain stops remain distinct from experimental uncertainty.

The future AI copilot may propose these same structured edits and explain returned
run IDs and evidence. It must not calculate physical outcomes or label its own
text as solver results. Approval UX, the editor and copilot are later milestones.
