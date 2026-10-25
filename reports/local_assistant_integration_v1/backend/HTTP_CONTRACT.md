# Local command mode: HTTP and reproducible workflow

The editor now exposes `POST /api/assistant/request`. It calls
[`handle_command`](../../../scripts/local_assistant.py) using the editor's
existing working project. This is deterministic local command mode: a fixed
grammar delegates to the existing evidence, edit-preview and comparison APIs.
There is no external AI/model provider, open-ended interpretation, automatic
execution, optimizer or new physical model.

## Exact request and response

The request has exactly three fields:

```javascript
const request = {
  message: 'explain this result',
  selection: {
    variant_id: 'A0',
    revision_id: currentInspection.revision_id,
    component_id: 'module',
    run_id: null
  },
  comparison: null
};
```

Use the exact current revision from `inspect`. A null run ID explicitly requests
configuration-only evidence; a saved run must be selected explicitly with the
correct viewed variant. The route does not accept a project path, supplied
physical outputs, cached context or an operation to execute.

For a comparison, `comparison` is exactly:

```javascript
{
  first:  {variant_id: 'A0', run_id: firstSelectedRun.run_id},
  second: {variant_id: 'A1', run_id: secondSelectedRun.run_id}
}
```

The message is `compare selected runs`. Both runs remain identified by their
owners, viewed variants, revisions and snapshots. `Project.compare` determines
whether operating conditions match and supplies all metrics and differences.
No local-command code ranks repairs or estimates a physical outcome from text.

Requests use the same `Content-Type: application/json` and
`X-Voltforge-Token` header as the other editor POSTs. The session token is returned
by `GET /api/session`. Success remains `{"status":"ok","result":...}` and
rejection remains `{"status":"error","error":{"code":...,"message":...}}`.

The result schema is `voltforge.local_assistant/1`:

| Field | Meaning |
|---|---|
| `mode` | Always `local_commands`. |
| `action` | `help`, `explain`, `preview_edit` or `compare`. |
| `selection` | The request's explicit captured variant/revision/component/run selection. |
| `payload` | Help text, unchanged frozen-copilot explanation/preview, or unchanged `Project.compare` output. |
| `context` | Full server-built successful evidence envelope for a preview; otherwise null. It supports later explicit inspector review. |
| `evidence` | Context identity, binding, parsed command/input-unit conversion and, for comparisons, actual source operation references and run ownership headers. |
| `warnings` | Scope and interpretation boundaries. |
| `applied`, `simulation_started` | Both false. No executor exists on this route. |

The service permits only its documented complete commands. Useful examples are:

- `help`
- `explain this result`
- `show evidence`
- `preview change selected rail to 0.5 mOhm`
- `preview change selected cell initial SOC to 70 %`
- `preview change selected polarization to 5 mV`
- `preview change timestep to 0.5 s`
- `compare selected runs`

These numeric examples demonstrate syntax, not measured values or recommended
designs. Select the target first. An explicitly named rail must match the
selection; timestep needs Module. Keywords ignore case, engineering unit symbols
retain their exact supported case, and omitted units or compound instructions
are rejected. Messages are limited to 400 characters. Only explicit input-unit
conversion occurs; the provenance string remains below the inspector's
500-character source limit.

## Consistency and safety boundaries

The endpoint shares the existing loopback Host/Origin/token checks, strict JSON
parser, duplicate-key/nonfinite rejection and no-store/CSP headers. The HTTP body
limit is 128 KiB; the local service additionally limits its canonical request to
16 KiB. The server holds its existing gate during the call and rejects active
jobs. External writer locks and stale design revisions are also rejected.

| HTTP status | Meaning |
|---|---|
| 200 | Command handled; inspect payload execution/freshness separately. |
| 400 | Invalid grammar/shape/units, unsupported command or mismatched selected target, or incompatible comparison conditions. |
| 403 | Host, Origin or session token rejected. |
| 404 | Referenced resource not found. |
| 409 | Active writer/job, changed revision/context, or integrity failure. |
| 413 | Existing context adapter cannot preserve complete evidence within its bound. |

A preview is a source-bound proposal for separate review. It cannot apply itself,
start a run, approve an action or export. The existing manual inspector and run/
export controls retain those roles. An unset voltage requirement remains
`requirement not configured`; a successful HTTP request is never experimental
module acceptance. Historical/inherited results retain their ownership and
outdated labels. Electrical losses are not temperature predictions.

The route request contains strings and selection IDs rather than client-replayed
numeric evidence. It therefore needs no new browser-number normalization. A
preview returns the full server-built context, compatible with the existing
evidence panel's separately tested exact numeric transport bridge.

Static assets are explicitly allowlisted as `/assistant-panel.mjs`
(`text/javascript`) and `/assistant.css` (`text/css`). Arbitrary file paths and
traversal forms remain unavailable. The CSP still allows only same-origin
connections; no provider endpoint or credentials have been introduced.

## Reproduce the complete demonstration

From the repository root with its Python environment:

```powershell
$env:PYTHONPATH = 'src'
python scripts/demonstrate_local_assistant.py --out tmp/local_assistant_demo_fresh
python -m pytest -q tests/test_editor_assistant.py tests/test_editor_evidence.py tests/test_editor_server.py --junitxml=tmp/local_assistant_backend_fresh.xml
```

Use a new output path to produce a demonstration. Reusing a completed path
verifies its saved artifacts and implementation hashes; incomplete paths are
preserved and refused. The default checked-in example path is
[demo_002](demo_002), whose exact requests/responses, source API evidence,
comparison, immutable export and numerical replay results are generated by
[the demonstration script](../../../scripts/demonstrate_local_assistant.py).

The declaration is saved before running the proposed 14.55 A, 360 s LG M50T
four-cell case. The explicit sequence is:

1. Explain configuration, then separately run A0 using the project API.
2. Explain A0's saved solver result and verify every cited claim against its
   actual source API response.
3. Separately create A1; request a preview bound to A1 for positive rail 1 at
   0.5 mOhm. An A0 preview is never silently transferred to A1.
4. Separately apply the exact proposed edit through the revision-aware project
   API, and demonstrate rejection of the old selected revision.
5. Separately run A1, then request the local comparison of the two explicit runs.
6. Verify the returned comparison equals `Project.compare`, including source
   references, ownership and identical-condition checks. Reject a command to
   run a simulation.
7. Separately export the configurations/results and replay both exported
   trajectories with the captured solver.

The script acts as an explicit stand-in for manual create/apply/run/export
actions and records each as a separate operation. Those actions never pass
through `handle_command`. Before/after hashes cover the complete temporary
project for each local command; existing raw or reserved measurement outcomes
are not needed. This is a simulation comparison, not a validated repair or a
battery-performance improvement.

## Tests and preservation

The new HTTP tests cover configuration/help, actual saved-run values, preview
without execution, full-project immutability, stale revisions, selected-target
mismatch, comparisons under matching/mismatching loads, refused execution and
compound commands, active jobs/external writers, session checks, strict request
shape and size, local assets and traversal rejection. A network guard exercises
commands while permitting only the test's own loopback connection and DNS;
external connection attempts fail the test. Existing evidence/server tests are
run alongside them.

See [tests.junit.xml](tests.junit.xml) and [verification.json](verification.json)
for the actual test receipt and final file hashes. The preceding server is
preserved in
[assistant_thermal_v1/previous/scripts/run_editor.py](../../assistant_thermal_v1/previous/scripts/run_editor.py)
and recorded in that sprint's
[preservation map](../../assistant_thermal_v1/preservation_map.json).
Frozen context/copilot implementations, `src/voltforge`, fitted models and
dependency files remain unchanged.

The initial [demo_001](demo_001/incomplete_attempt.json) is preserved as an
incomplete software attempt: the demonstration's step-label argument collided
with `create_variant`'s `name` argument after A0 had completed. The orchestration
helper was corrected and the full workflow rerun in the new `demo_002` directory;
no previous run was overwritten and no solver/command-service change was needed.
