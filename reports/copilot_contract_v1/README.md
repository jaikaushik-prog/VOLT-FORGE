# Offline copilot contract foundation

The implementation is a **deterministic, read-only interface for a future
assistant**. It accepts already structured JSON edits, produces a reviewable
preview using the existing backend validator, and copies saved engineering
evidence into cited explanation objects. It is not a language model, an AI
optimizer, or a new electrical solver.

The frozen LG M50T v2 models, raw measurements, protected assessment outcomes and
unused cells are unchanged. P45B model research remains a separate workstream;
no P45B revision is adopted into the four-cell project by this interface.

## Implemented boundary

Source: [copilot_contract.py](../../scripts/copilot_contract.py).
Input evidence: [backend context interface](../backend_context_v1/INTERFACE.md).
Underlying authority: [existing frontend contract](../../FRONTEND_CONTRACT.md).

```text
Existing project -> read-only evidence context -> structured user proposal
                                                -> validate_edit -> preview
                                                -> saved evidence -> claims

Human review / apply / simulation: outside this adapter
```

There are exactly two operations:

| Operation | Arguments | Result |
| --- | --- | --- |
| `preview_edit` | `{ "edit": <existing seven-field edit object> }` | `approval_required`, exact old input and proposed edit, variant/revision/context binding, invalidated runs, warnings and provenance. No prediction or action. |
| `explain` | `{}` | Cited configuration/fitted-value claims and, only when an explicit saved run is selected, actual summary/sample/evidence claims. |

The top-level request has exactly `operation`, `context`, and `arguments`.
`context` is the complete successful envelope returned by `build_context`.
Unknown fields, proposed numerical outcomes, natural-language commands,
nonfinite numbers, numeric strings where numbers are required, unsupported
topologies/outputs and attempts to apply or run are rejected.

Each request rebuilds its context from the project and requires exact canonical
agreement with the supplied context. A caller cannot replace a voltage result
and make it trusted by recomputing the hash. Preview validation rereads context
again to detect a concurrent change. Context identity is not an authentication
token; this local interface provides no hosted authorization system.

## Python and CLI usage

```python
from scripts.evidence_context import build_context
from scripts.copilot_contract import handle_request

context = build_context("tmp/copilot_trial", variant_id="A0")
preview = handle_request("tmp/copilot_trial", {
    "operation": "preview_edit",
    "context": context,
    "arguments": {"edit": {
        "target": "connection", "id": "rail_p_1", "property": "resistance",
        "value": 0.0005, "unit": "ohm", "classification": "assumed",
        "source": "Manually proposed effective resistance; physical feasibility unverified"
    }}
})
assert preview["result"]["status"] == "approval_required"
assert preview["result"]["predicted_effect"] is None
assert preview["result"]["applied"] is False
```

That resistance is an illustrative proposed input, not a measured repair or
recommendation. An existing editable property is validated using
`Project.validate_edit`; fitted parameters, identity and topology remain sealed.
The adapter does not interpret an `approved` field or provide an execute route.
A future human-approved executor must separately recheck the current revision,
apply the reviewed change through the existing project API and request a solver
run. No result can be predicted merely from the preview.

From the repository root, this creates a **new configuration-only trial project**
and makes an exact JSON request without reading raw measurement archives:

```powershell
$env:PYTHONPATH = 'src'
@'
import json
from pathlib import Path
from voltforge.project import Project
from scripts.evidence_context import build_context
Project.create_reference("tmp/copilot_trial")
context = build_context("tmp/copilot_trial", variant_id="A0")
request = {"operation": "explain", "context": context, "arguments": {}}
Path("tmp/copilot_request.json").write_text(json.dumps(request), encoding="utf-8")
'@ | & C:\Users\DELL\anaconda3\python.exe -
& C:\Users\DELL\anaconda3\python.exe scripts/copilot_contract.py --project tmp/copilot_trial --request tmp/copilot_request.json
```

Use a new project path if `tmp/copilot_trial` already exists. The adapter itself
never creates projects. Request files may be UTF-8 with or without BOM; stdin
is also supported. Duplicate JSON keys and requests over 1 MiB are rejected.
Responses go to stdout; exit 0 means a handled operation, exit 2 a rejection.
An `ok` explanation may still describe a failed or outdated run.

To explain an existing saved run, explicitly pass its actual `run_id` and a
supported `component_id` to `build_context`, then call `explain`. No run is
selected automatically. Source pointers in each claim refer to the original
`inspect`, `get_run` or `series` response, with run/snapshot/component IDs where
applicable. Claim values are direct copies; they are not newly calculated
physical outcomes. Series excerpts retain units and pagination and cannot stand
in for complete-record assessment.

## Evidence and state rules

- Configured assumptions, declared requirements, fitted electrical parameters,
  derived capacity, model artifact references and simulated outputs have distinct
  claim kinds. A user-entered source string remains unverified provenance data.
- `execution_status` and `freshness` remain separate. Failed runs retain the
  exact error and partial samples when present; missing coverage is not support.
  An inherited A0 result remains outdated when viewed from A1.
- Current configuration claims identify the current revision. Historical output
  claims identify the captured run revision and snapshot. They are not presented
  as results of the current inputs.
- Missing voltage requirements stay null / **requirement not configured**.
  A configured simulated requirement screen is never experimental acceptance.
- Full selected-run coverage is retained. An in-range current amplitude does not
  establish support for its duration or waveform. Electrical loss is not a
  predicted temperature.
- Every explanation retains **insufficient evidence** for experimental module
  decisions. Neither a lower simulated loss nor a smaller model error is reported
  as a demonstrated battery-performance improvement.

These constraints follow the [product vision's copilot boundary](../../VOLT_FORGE_Product_Vision.md#10-ai-engineering-copilot),
[reference/initial-state decision](../../REFERENCE_INITIAL_STATE_DECISION.md),
[module readiness](../../SIMULATION_READINESS.md) and
[current reconciliation](../reconciliation/RECONCILIATION.md). Improved cell
fitting does not resolve the module-current reference discrepancy.

## Checks and next handoff

The [focused tests](../../tests/test_copilot_contract.py) use temporary reference
projects and explicitly synthetic load/failure cases. They check:

- No adapter path invokes `apply_edit` or `run`, and read-only calls preserve
  every project file byte-for-byte.
- Each generated claim resolves to exactly the cited backend field.
- Modified values, recomputed forged hashes, snapshot/owner mismatches, changed
  revisions and unsupported actions are rejected.
- Pure visual layout updates keep context valid; physical edits make old context
  stale. A concurrent edit during validation also rejects the preview.
- Failed, partial, historical and unconfigured-requirement states remain explicit.
- The CLI agrees with the Python API and rejects ambiguous duplicate JSON fields.

```powershell
$env:PYTHONPATH = 'src'
& C:\Users\DELL\anaconda3\python.exe -m pytest tests/test_copilot_contract.py -q
& C:\Users\DELL\anaconda3\python.exe -m pytest tests/test_evidence_context.py tests/test_copilot_contract.py -q
```

The focused [JUnit receipt](tests.xml) and [machine-readable receipt](verification.json)
record **37 passing software checks**, with zero failures, errors or skips.
The orchestrated [integration demonstration](../parallel_engineering_v1/demo_001/result.json)
passed 12 invariants and checked 172 claims against actual backend fields while
preserving project bytes during every read-only call. It uses a saved simulation,
not new experimental observations. Its complete generated examples include:

- [Configuration-only explanation](../parallel_engineering_v1/demo_001/examples/02_configuration_explanation_request_response.json).
- [Completed A0 explanation with units and coverage](../parallel_engineering_v1/demo_001/examples/05_saved_run_explanation_request_response.json).
- [Exact structured edit preview](../parallel_engineering_v1/demo_001/examples/06_structured_preview_request_response.json).
- [Rehashed fabricated outcome rejection](../parallel_engineering_v1/demo_001/examples/07_fabricated_result_rejected_request_response.json).
- [Historical A0 output viewed from changed A1](../parallel_engineering_v1/demo_001/examples/15_A1_historical_explanation_request_response.json).

To rerun the complete demonstration or verify its saved artifacts:

```powershell
& C:\Users\DELL\anaconda3\python.exe scripts/demonstrate_copilot_handoff.py
```

An existing completed demonstration is verified without replacing its evidence.
Use a fresh `--out` directory to generate another complete run.

Unavailable in this release: language parsing, external model/API providers,
automatic action execution, chat UI, optimization, repair ranking, thermal
prediction and new model fitting. The next AI implementation milestone would be
a separately scoped proposal parser plus a human-review interface, using this
strict boundary and evidence citations. It does not require giving the AI
authority to invent or calculate physical outcomes.
