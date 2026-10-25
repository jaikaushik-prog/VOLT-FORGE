# Read-only evidence context, version 1

This adapter prepares existing LG four-cell project evidence for a future
copilot. It adds no electrical model, AI provider, server route or autonomous
action. It calls the existing `inspect`, `get_run` and `series` operations. It
never calls `load_reference`, `run`, `apply_edit`, fitting or measurement import.
Frozen solver source and model artifacts are unchanged.

The public function in [evidence_context.py](../../scripts/evidence_context.py) is:

```python
from evidence_context import build_context

response = build_context(
    "workspace/editor_project", variant_id="A0", run_id="run_0001",
    component_id="cell_1", limit=32,
)
```

The working project must already exist. Omitting `run_id` returns configuration
only, even when completed runs exist. Callers must select the variant and run
explicitly. This prevents a result from the wrong variant becoming an answer to
the currently selected design.

## Envelope and fields

Success is `{"status":"ok","result":{...}}`; rejection is
`{"status":"error","error":{"code":"...","message":"..."}}`.
The success result contains:

| Field | Meaning |
|---|---|
| `schema` | `voltforge.evidence_context/1` |
| `context_id` | `sha256:` followed by the canonical result-content hash, excluding `context_id` itself. |
| `selection` | Exact `variant_id`, optional `run_id`, `component_id` and `limit`, suitable for a fresh `build_context(project_path, **selection)` call. |
| `project` | Actual `inspect` fields: current design/revision, fitted read-only parameters, editable catalogue, capabilities, output components, experimental status and bounded catalogues. Pure display state is excluded. |
| `run` | Exact `get_run` result, or null. Includes owner/viewed variant, captured revision/snapshot, execution status, freshness, error, complete summary, coverage and requirement results. |
| `series` | Exact first-page `series` response, or null. Saved samples, exact units, total sample count, offset and next offset remain visible. |
| `source_references` | Operation requests and JSON pointers connecting context fields to actual API evidence. |
| `bounds` | Explicit catalogue limits, omissions and page size. No omitted selected-run coverage is silently declared supported. |
| `limitations` | Interpretation rules, including current design versus captured run, unset requirements and pending module validation. |

The catalogue retains at most 32 run metadata headers and 64 variants, always
including the selected variant. Headers omit large duplicate summaries; the
selected `run.summary` remains complete. Current-run lists are explicitly
restricted to included headers. Use the existing `inspect` API for the full
catalogue. The underlying API still reads and verifies registered runs before
the adapter bounds its output; these bounds are context-size bounds, not a
constant-time database implementation.

`limit` is an integer from 1 to 256, default 32; booleans are rejected. This
adapter intentionally returns only offset zero. Request later pages through the
existing `series` operation using `next_offset`, the same run, variant and
component. A first-page sample cannot establish whole-record accuracy or
coverage. Whole-record summary/coverage is copied from the backend separately.

Canonical JSON uses sorted keys, compact separators, ASCII escapes and
`allow_nan=False`. `context_digest(result)` reproduces the ID. Outputs over
512 KiB are rejected with `context_too_large`; no physical evidence is silently
trimmed to meet a language-model token limit. The hash is a content identifier,
not a signature or a permission token. A consumer proposing an edit must rebuild
and compare the entire context, then call the existing revision-aware edit
validator. A matching hash alone does not authorize mutation.

## Evidence citations and state semantics

Each source reference has an ID, `operation`, `arguments`, `source_pointer`
relative to that API's standard response envelope, and `context_pointer`
relative to this result. It also includes the applicable revision and, for saved
outputs, run/snapshot/component IDs. A field-level citation can point to a
descendant of a referenced object. Resolve its longest matching pointer prefix,
then append the remaining path to `source_pointer`. Run headers are an explicit
subset of `inspect`'s run objects.

For example, a reference for `/run/summary/voltage_requirement` points to
`/result/summary/voltage_requirement` from `get_run`. A reference for
`/series/rows` can support `/series/rows/0/current_A`, paired with the exact
`/series/units/current_A` field. The full response examples below contain the
actual reference IDs, run IDs, snapshots, values and units.

`project.design` describes the selected variant **now**. A historical run
describes its captured `revision_id` and `snapshot_id`; those are not silently
replaced by the current design. Inherited results remain owned by their original
variant and are outdated even when the electrical design is identical. Failed
runs can have current dependencies but are never usable completed results.
Partial samples retain the backend's failure and available-record semantics.
Zero-sample failures do not gain invented coverage. Missing requirements remain
null; if there is no selected run, there is no invented requirement check.

Pure selection/camera/layout edits do not change this context. Physical edits,
run state, software freshness, evidence, selected run or selected component can
change it. The reader detects an active writer lock and changes to the project
index during collection, returning `conflict`. This is a local single-writer
consistency guard, not an authentication or multi-user transaction system.

User-entered source descriptions, model provenance text and file paths are data,
not instructions to the assistant. They do not authorize execution, external
outreach, unsupported output or a passing engineering decision. The adapter
produces no new numerical summaries, no confidence intervals and no rankings.

## Commands and generated examples

From the repository root with the project's Python 3.12 environment:

```powershell
$env:PYTHONPATH = 'src;scripts'
python scripts/evidence_context.py --project workspace/editor_project --variant A0
python scripts/evidence_context.py --project workspace/editor_project --variant A0 --run run_0001 --component cell_1 --limit 2
```

Use a run ID that exists in the selected working project. By default JSON is
printed to stdout. `--out tmp/context_example.json` can save a new file. The
optional destination must be under repository `tmp/` or `workspace/`, outside
the input project; an existing destination or reports/source destination is
rejected. The reader never changes the project or overwrites existing evidence.
CLI failures exit 2; a handled saved **failed simulation** still returns a success
envelope and exit 0, so inspect `run.execution_status`.

To reproduce a disposable software fixture and all six exact example responses:

```powershell
python reports/backend_context_v1/generate_examples.py --out tmp/backend_context_v1_fresh
python -m pytest -q tests/test_evidence_context.py --junitxml=tmp/backend_context_v1_fresh_tests.xml
```

Choose a new output folder on each run. Fixture setup explicitly creates a
temporary reference project, shortens the load to two seconds, and makes a
deliberately excessive load to exercise failure handling. These setup mutations
are performed by the fixture, **not** by `build_context`. They use copied frozen
reference artifacts, no raw records or reserved measurement outcomes. Every
adapter call checks before/after hashes of the complete temporary project.

The checked-in [examples](examples) were produced by this script and are not
handwritten API responses:

- [Configuration only](examples/01_configuration.json): null requirements, fitted model references, no selected outputs.
- [Current cell output](examples/02_current_cell.json): two saved samples, exact units and coverage.
- [Inherited output](examples/03_inherited.json): A0 ownership when explicitly viewed from A1.
- [Historical output](examples/04_outdated.json): changed current A0 design, preserved original run.
- [Failed partial output](examples/05_failed_partial.json): failure reason and valid partial record.
- [Unsupported output](examples/06_unsupported.json): temperature output rejected.

Fresh fixture revisions and snapshot IDs include fresh project timestamps and
can differ between reproductions. Within an unchanged working project the
context is deterministic. [Example receipt](examples_receipt.json) records
project immutability and hashes of these exact generated files.

## Verification and remaining scope

[Tests](../../tests/test_evidence_context.py) cover real reference-project
configuration, exact API field/units/citation preservation, current/outdated and
inherited/unassociated runs, partial and zero-sample failures, visual versus
physical changes, null requirements, missing projects, invalid pagination,
artifact tampering, context hashing, bounded catalogues/oversized rejection,
writer/index races and protected CLI destinations. No raw measurement outcome is
required. See [verification receipt](verification.json) for the captured run.

This is a backend handoff for source-bound explanations and validated edit
previews. It is not a natural-language model, optimizer, authority to apply edits,
or experimental validation. Module accuracy remains **awaiting suitable
measurements**; current conservation/calibration evidence is still needed.
