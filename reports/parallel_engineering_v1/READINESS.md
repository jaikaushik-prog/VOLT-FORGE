# Parallel engineering handoff

Three user-authorized agents worked in separate files while the orchestrator
reviewed the electrical procedure, froze it before fitting, integrated the two
software interfaces and verified preservation. The frozen LG/P45B models are
unchanged. The sprint adds a tested backend-to-assistant boundary and a bounded
electrical diagnosis; it does not establish experimental module accuracy.

## Completed work

| Owner | Delivered | Evidence and limitation |
| --- | --- | --- |
| Electrical engineer | Local complete-pulse/rest two-RC diagnostics, fixed finite tau grid, reference/SOC-origin and inherited-state sensitivities, plots and independent equation/fit verifier. | [Decision](../p45b_local_dynamics_v1/DECISION.md). All eleven low-SOC pairs were already used development evidence; no fresh assessment or product-model adoption. Procedure/code frozen at `ebfbaf5` before fitting. |
| Backend engineer | Read-only, bounded, content-hashed project context with units, component IDs, revisions, snapshots, citations, requirements, coverage and run freshness. | [Interface and exact examples](../backend_context_v1/INTERFACE.md); 11 focused integration tests. No missing-project creation or physical calculations. |
| AI engineer | Deterministic structured-edit preview and evidence-cited explanation objects; current-context revalidation and strict request validation. | [Contract](../copilot_contract_v1/README.md); 37 focused tests. No natural-language understanding, model provider, action executor or optimizer. |
| Orchestrator | Actual A0 run, combined handoff, variant/edit/layout checks, preservation verification, documentation and repository update. | [Executed result](demo_001/result.json), [exact request/response examples](demo_001/examples), [combined tests](pytest.xml). 224 focused Python tests and [four editor-state checks](editor_tests.txt) passed. |

The 11 and 37 focused adapter tests are included in the 224-test combined run;
they are not additional tests. The electrical agent's separate 135-test receipt
also overlaps that combined suite. Tests verify software and numerical behavior,
not physical module accuracy.

## Electrical finding and decision

The earlier shared low-SOC resistance revisions did not justify adoption. The
new local investigation removes that imposed SOC shape separately for each
complete pulse/rest pair. Its equal-pair, equal-phase in-sample objective is
73.00 mV for frozen replay, 18.78 mV with local resistances at the published time
constants, and 17.23 mV when allowing the predeclared time-constant grid. These
figures describe increasingly flexible fits on used evidence. They are neither
held-out prediction accuracy nor a battery-performance improvement.

The local fits do not define a continuous deployable parameter table. Time
constants depend strongly on the linked SOC/reference-origin assumption, and
late-rest voltage mismatch remains. No new RC branch, broad temperature law,
free voltage offset or installed parameter revision was introduced. Read the
[electrical decision](../p45b_local_dynamics_v1/DECISION.md) for sample/time errors,
phase diagnostics, bounds and uncertainty. Unused characterization outcomes
remain reserved for a frozen procedure that can make actual predictions.

## What the frontend teammate can connect next

The stable Python entry points are:

```python
from scripts.evidence_context import build_context
from scripts.copilot_contract import handle_request

ctx = build_context(existing_project_path, variant_id="A0",
                    run_id=selected_run_id, component_id="cell_1", limit=32)
reply = handle_request(existing_project_path, {
    "operation": "explain", "context": ctx, "arguments": {}
})
```

The two contract operations are `explain` and `preview_edit`. Exact seven-field
edit examples come from the existing editable-property catalogue. Preview
returns the current value, proposed input, invalidated run IDs, warnings and
`approval_required`. It returns `predicted_effect: null`, `applied: false` and
`simulation_started: false`. The name describes a product review state; the
adapter itself cannot accept approval or execute anything.

Evidence explanations copy values from the backend and cite their original
operation, JSON pointer, revision and saved-run snapshot. They distinguish
assumed inputs, fitted artifacts and simulated outputs. Missing requirements
remain `requirement not configured`; module acceptance remains `insufficient
evidence`. Initial series pages retain their pagination limits and do not stand
in for whole-record coverage.

The next software milestone is a small editor evidence/preview panel using
these interfaces, followed by a separately scoped human-approved executor and
language-model integration. A later assistant may propose supported structured
edits and explain returned evidence. The electrical solver remains the only
source of simulated physical outcomes. There is no need for a new general CAD
framework or another solver to connect this panel.

## Executed integration checks

The demonstration creates a new copied reference project and runs the existing
14.55 A / 360 s A0 case. It checks **172 claims** against live backend fields and
then checks the saved claims again against their full contexts. Before/after
hashes establish that every context, preview and explanation call preserves
all project files. Twelve invariants cover:

- Configuration-only context before simulation, with no invented prediction.
- Completed/current A0 evidence and unset requirements without a passing claim.
- Exact rail-resistance preview, declared invalidation, no apply or prediction.
- Rejection of fabricated results even when their context hash is recomputed.
- Rejection of unsupported thermal execution.
- Context and physics remaining current after a purely visual move.
- Stale-context rejection after an explicit physical edit.
- Inherited A0 output remaining outdated when viewed from A1.
- A1 edits leaving A0's saved run unchanged and current for A0.

Project creation, the A0 run and A1 setup edits are explicit operations by the
demonstration script. They are not autonomous copilot actions. A1 is not run in
this handoff demonstration and no changed performance is claimed. Earlier
[A0/A1 simulation comparison](../product_integration_v1/demo/comparison.json)
remains a separate preserved workflow.

Useful exact examples:

- [Current saved-run explanation](demo_001/examples/05_saved_run_explanation_request_response.json)
- [Structured rail edit preview](demo_001/examples/06_structured_preview_request_response.json)
- [Fabricated numerical result rejection](demo_001/examples/07_fabricated_result_rejected_request_response.json)
- [Stale context rejection](demo_001/examples/13_stale_context_rejected_request_response.json)
- [Historical A0 result viewed from A1](demo_001/examples/15_A1_historical_explanation_request_response.json)

## Reproduce from the repository root

Verify the saved complete integration demonstration without rerunning it:

```powershell
& C:\Users\DELL\anaconda3\python.exe -B scripts\demonstrate_copilot_handoff.py
```

Create a fresh demonstration (choose a new path if it already exists):

```powershell
& C:\Users\DELL\anaconda3\python.exe -B scripts\demonstrate_copilot_handoff.py --out tmp/copilot_handoff_fresh
```

This uses the frozen reference assets; it needs no raw measurement archive.
The saved examples carry specific context hashes and revision IDs. Rebuild
context from your own current project before making a request; copying a stale
example into a changed project is expected to fail.

Reproduce the focused combined suite:

```powershell
$env:PYTHONPATH = 'src;scripts'
$env:OPENBLAS_NUM_THREADS = '1'
$env:OMP_NUM_THREADS = '1'
& C:\Users\DELL\anaconda3\python.exe -B -m pytest -q tests/test_evidence_context.py tests/test_copilot_contract.py tests/test_project_workflow.py tests/test_editor_server.py tests/test_module_dynamics.py tests/test_module_workflow.py tests/test_ladder.py tests/test_ae_p45b_equations.py tests/test_ae_p45b_reproduction.py tests/test_ae_p45b_author_comparison.py tests/test_ae_p45b_low_soc.py tests/test_ae_p45b_gitt_replay.py tests/test_ae_p45b_identifiability.py tests/test_p45b_identifiability_verifier.py tests/test_ae_p45b_local_dynamics.py --junitxml=tmp/parallel_engineering_fresh_tests.xml
& 'C:\Program Files\nodejs\node.exe' --test tests/editor_state.test.mjs
```

Verify the electrical calculations, prior preservation chain, adapter receipts
and recorded integration together, writing to a new receipt path:

```powershell
& C:\Users\DELL\anaconda3\python.exe -B scripts\verify_parallel_engineering.py --out tmp/parallel_engineering_verification.json
```

Full electrical reproduction needs the original parameter table/raw downloads
used by the existing preservation chain. See its [commands](../p45b_local_dynamics_v1/DECISION.md).
An unavailable original source is a preservation-check blocker, never permission
to replace its hash or read reserved evidence.

## Remaining engineering limits

The four-cell editor still uses frozen LG M50T v2; this study has not converted
it into a validated P45B module. The module-current versus summed-branch-current
discrepancy remains unresolved. Source calibration/processing evidence or a
suitable synchronized module dataset with defined measurement locations,
preparation and calibration remains necessary for experimental validation.
Actual device voltage limits and permitted excursion duration remain unset.

The published P45B model reproduces its declared author case closely but still
misses measured low-SOC behavior. Local fitted resistances and recovery times
are development diagnostics, not trustworthy voltage-limit settings. The next
physics step must specify a continuous parameter/reference/state procedure
before using reserved data; repeated local fits cannot establish transfer.

No frozen model, raw source or prior outcome was replaced. The old living
README is preserved byte-for-byte in [previous/README.md](previous/README.md)
so previous receipt hashes remain verifiable. Nine unused LG cells, 48 unused
P45B members in 40 families and 13 unused FreeTwinEV records remain reserved.
No lab request was sent. Frontend redesign, thermal modelling and optimization
remain deferred.

For a student: the software can now show exactly which saved calculation an
explanation comes from and safely preview a supported change. The physics work
helps locate why the model misses low-charge behavior, but does not yet tell us
which physical module change is best. Next, connect the evidence panel and
define a predictive model procedure that can be tested on untouched records.
