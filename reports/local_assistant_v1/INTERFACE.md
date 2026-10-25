# Local command mode interface

This is a deterministic command interface, **not an LLM**. It recognizes a small
declared grammar and delegates to existing read-only engineering APIs. It uses
no external provider, credentials or network calls. It cannot apply edits, run
the model, optimize a design, invent physical results or send outreach.

Implementation: [local_assistant.py](../../scripts/local_assistant.py).
The [procedure](PROCEDURE.md) and [evaluation cases](../../configs/local_assistant_eval_v1.json)
were declared before implementation and evaluation. This release adds no model
parameters and opens no new characterization or protected assessment outcomes.

## Request and response

```python
from scripts.local_assistant import handle_command

response = handle_command(project_path, {
    "message": "show evidence",
    "selection": {
        "variant_id": "A0",
        "revision_id": current_inspection["revision_id"],
        "component_id": "module",
        "run_id": selected_saved_run_id  # null/None explicitly means no run
    },
    "comparison": None
})
```

The request has exactly those three top-level fields. `selection` has exactly
the four shown fields. `comparison` is null or exactly:

```json
{
  "first": {"variant_id": "A0", "run_id": "run_0001"},
  "second": {"variant_id": "A1", "run_id": "run_0002"}
}
```

These are illustrative IDs; use actual explicitly selected saved entries. The
service never chooses the latest run, infers a target from unrelated history,
or silently redirects an explicit rail name to a different selection.

A successful envelope is `{"status":"ok","result":...}` with these fields:

| Field | Meaning |
| --- | --- |
| `schema` | `voltforge.local_assistant/1` |
| `mode` | `local_commands` |
| `action` | `help`, `explain`, `preview_edit`, or `compare` |
| `selection` | Exact captured request selection, checked against the authoritative current revision |
| `payload` | Help text, an unchanged frozen copilot result, or an unchanged `Project.compare` result |
| `context` | Complete authoritative evidence-context envelope for `preview_edit`; null otherwise |
| `evidence.context_id`, `evidence.binding` | Context, current design and selected run/snapshot identifiers |
| `evidence.command` | Original message, normalized message, and explicit input-unit conversion metadata when applicable |
| `evidence.comparison` | Null except for comparison; contains explicit selections, both original run owners and snapshots, units, and source references |
| `warnings` | Mode and scientific limitations; historical/same-run comparison warnings where applicable |
| `applied`, `simulation_started` | Always false |

An error envelope is `{"status":"error","error":{"code":...,"message":...}}`.
Common codes are `unsupported_command`, `selection_mismatch`, `stale_context`,
and `invalid_request`; existing backend errors such as `unsupported_request`,
`not_found`, `integrity_error` and `conflict` are preserved. A successful request
may explain a **failed simulation**. Read the payload's execution/freshness
fields, not merely the transport envelope.

## Exact accepted language

Keyword matching ignores case. Outer ASCII spaces are trimmed and repeated
internal ASCII spaces are collapsed. Engineering units remain case-sensitive:
`mOhm` and `mΩ` mean milliohm; `MOhm` is rejected rather than interpreted as
milliohm. A number and its explicit unit may be adjacent or separated by spaces.
Only ordinary signed decimal notation is accepted; no exponent, expression,
comma decimal, NaN, infinity, control character or additional instruction.

| Command form | Required selection and interpretation |
| --- | --- |
| `help` / `show commands` | Any supported component; returns syntax guidance |
| `explain this result` / `show evidence` | Exact selected saved run, or configuration only when run is null |
| `compare selected runs` / `compare the selected runs` | Two explicitly supplied run/variant entries |
| `preview [change] selected rail to NUMBER UNIT` | Selected rail; UNIT is `mOhm`, `mΩ` or `ohm` |
| `preview [change] positive rail N to NUMBER UNIT` | The selected component must be exactly positive rail N, N=1..3 |
| `preview [change] negative rail N to NUMBER UNIT` | The selected component must be exactly negative rail N, N=1..3 |
| `preview [change] selected cell [initial] SOC to NUMBER %` | Selected cell; percent converted to a fraction relative to its fixed reference |
| `preview [change] selected polarization to NUMBER UNIT` | Selected cell; UNIT is `mV` or `V` |
| `preview [change] selected cell initial polarization to NUMBER UNIT` | Same supported cell-polarization edit |
| `preview [change] timestep to NUMBER s` | Module selected; `time step` is also accepted |

Brackets in this table denote optional words; they are not typed literally.
Physical and mathematical bounds are delegated to the existing validator. For
example, parsing a negative resistance never makes it an acceptable edit.
No load, chemistry, topology, fitted-model, thermal or requirement editing is
available through this grammar.

Messages are limited to **400 characters** and the Python/CLI request to **16
KiB**. The command provenance prefix plus original message fits within the
editor's 500-character source field. Every parsed edit is classified `assumed`:
command text is not a measurement or calibration certificate.

## Evidence and human review

The service rebuilds the current evidence context and rejects an old selected
revision. Explanation and preview use the existing frozen copilot contract;
all returned input/fitted/output distinctions, values, units, claim citations,
coverage, failure details, historical ownership and missing requirements remain
unchanged. The stored `context` in a preview allows the existing UI to revalidate
that exact context before a separate explicit human Apply action. It is not an
authorization token and this service has no execute route.

Comparison is a direct `Project.compare` call. Its equal-condition checks still
reject different load, initial states, temperature assumptions, requirements,
time step or model/software. Both original owners and viewed variants remain in
`evidence.comparison.runs`; an inherited A0 run viewed from A1 is still owned by
A0 and outdated for A1. Comparing the same saved run from different explicitly
selected variants is labelled as such. A duplicate identical entry is rejected.

Comparison references use the same `operation`, `arguments`, and `source_pointer`
shape as the existing contract, plus `payload_pointer` for the copied comparison
field. The full-payload reference covers all copied values; row/delta references
add run/snapshot identities. Run headers carry their `get_run` source. Metric
units are explicit schema metadata. The parser computes no comparison metric,
delta, physical response, confidence bound or repair ranking.

All contexts are rechecked before returning. These are consistency checks over
read-only operations, not a database transaction or a promise that another
writer cannot change a project after the response. Subsequent actions must use
the existing expected-revision and context checks.

Null requirements remain **requirement not configured**, not a pass. Current
dependencies and completed execution remain distinct from experimental accuracy.
Experimental module validation remains **awaiting suitable measurements**.

## Reproduce a configuration-only command

Run from the repository root; use a new trial path if this one already exists:

```powershell
$env:PYTHONPATH = 'src'
@'
import json
from pathlib import Path
from voltforge.project import Project
project = Project.create_reference("tmp/local_command_trial")
info = project.inspect("A0")
request = {
    "message": "show evidence",
    "selection": {"variant_id": "A0", "revision_id": info["revision_id"],
                  "component_id": "module", "run_id": None},
    "comparison": None
}
Path("tmp/local_command_request.json").write_text(json.dumps(request), encoding="utf-8")
'@ | & C:\Users\DELL\anaconda3\python.exe -
& C:\Users\DELL\anaconda3\python.exe scripts/local_assistant.py --project tmp/local_command_trial --request tmp/local_command_request.json
```

The first command explicitly creates a trial project as setup. The command
service itself only reads existing projects. Omit `--request` to use stdin.
Duplicate JSON fields and nonfinite JSON values are rejected. CLI exit 0 means
the command was handled; exit 2 means it was rejected. Output is JSON on stdout.

```powershell
$env:PYTHONPATH = 'src'
& C:\Users\DELL\anaconda3\python.exe -m pytest tests/test_local_assistant.py -q
```

The focused suite passed **73 checks**. [JUnit](tests.xml) and the
[verification receipt](verification.json) record software evidence, not fresh
cell assessment or experimental module validation.

The successful [end-to-end demonstration](../local_assistant_integration_v1/backend/demo_002/result.json)
checked 133 claims/references against actual source APIs, including comparison
ownership and snapshots. Both complete 360-second simulations were exported and
replayed. Exact generated command request/response examples are:

- [Configuration-only command](../local_assistant_integration_v1/backend/demo_002/examples/01_configuration_command.json).
- [Saved A0 explanation](../local_assistant_integration_v1/backend/demo_002/examples/03_A0_explanation_command.json).
- [A1 edit preview](../local_assistant_integration_v1/backend/demo_002/examples/05_A1_preview_command.json).
- [Stale selection rejected](../local_assistant_integration_v1/backend/demo_002/examples/07_old_selection_rejected_command.json).
- [Explicit same-condition comparison](../local_assistant_integration_v1/backend/demo_002/examples/09_compare_selected_command.json).
- [Execution command refused](../local_assistant_integration_v1/backend/demo_002/examples/10_execution_refused_command.json).

Project creation, manual apply and simulation are separate explicit demonstration
setup steps. None is an action of the local command service. These are simulation
comparisons and software checks, not demonstrated repairs or battery gains.
