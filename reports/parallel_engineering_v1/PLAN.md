# Parallel engineering sprint: disjoint work, shared evidence rules

User-authorized parallel work on 25 October 2026. Start from commit `e7d8400`.
The product remains a visual engineering workspace; this sprint progresses
electrical research and the backend/AI handoff while frontend redesign stays
deferred. The AI optimizer remains unavailable.

## Ownership and scope

| Role | Owned additions | Bounded outcome |
| --- | --- | --- |
| Electrical engineer | `scripts/ae_p45b_local_dynamics.py`, associated new verification/plot helpers, `tests/test_ae_p45b_local_dynamics.py`, `configs/ae_p45b_local_dynamics_v1.json`, `reports/p45b_local_dynamics_v1/` | Conditional local complete-pulse/rest identifiability investigation of resistance shape versus recovery time scale. Procedure and implementation frozen before fitting. No deployable model adoption. |
| Backend engineer | `scripts/evidence_context.py`, `tests/test_evidence_context.py`, `reports/backend_context_v1/` | Read-only, bounded, content-hashed context built from the existing project API, preserving provenance, units, run ownership/freshness, coverage and requirement state. |
| AI engineer | `scripts/copilot_contract.py`, `tests/test_copilot_contract.py`, `reports/copilot_contract_v1/` | Deterministic structured-edit preview and evidence-cited explanations; no language-model/API call, natural-language understanding, execution, optimizer or invented physical output. |
| Orchestrator | This sprint directory, new integration demonstration/verifier, living README, Git commits and repository update | Review boundaries, freeze procedures, exercise the combined workflow, verify preservation, summarize capability and scientific limitations. |

Agents share the workspace and must not change another owner's files without
coordination. They must not stage/commit while another lane is writing; only the
orchestrator performs scoped Git operations. New code goes outside `src/voltforge`
because its Python sources contribute to the frozen solver fingerprint. No
dependency or source-solver change is needed for this sprint.

## Scientific boundary

Keep published P45B and LG v2 unchanged. Use only already-opened saved GITT,
1C and reference evidence. Preserve all 48 unused P45B members / 40 families,
nine unused LG cells, 13 unused FreeTwinEV records, protected module outcomes,
raw downloads and prior provenance. No current rescaling or reference extension.
The reserved 25 degC 3C family stays unopened.

Local diagnostic fits must distinguish the assumed starting polarization,
nominal SOC/reference origin, SOC variation within a pulse, time-scale bounds
and conditioning. Use complete sequences, not random timestamp splits. A lower
in-sample error does not establish parameter uniqueness or a deployable SOC law.
No model is promoted merely because its local fit improves.

## Backend/AI boundary

The existing `voltforge.project` interface remains authoritative. The context
adapter does not create a missing project or choose the latest run globally.
Read-only result explanations cite actual fields and distinguish current,
outdated, failed, partial, simulated and unsupported evidence. Unknown application
requirements remain `requirement not configured`; module acceptance remains
`insufficient evidence` pending suitable measurements.

Structured proposals are drafts bound to variant/revision/context. Existing edit
validation produces the preview. Proposals do not apply edits or run the solver.
Human approval/execution and a future language-model provider require a later
scoped implementation. Client-supplied claimed numerical outcomes cannot replace
backend values. No free-text imitation of a working AI assistant is introduced.

## Integration demonstration and release checks

Use a new temporary reference project to show:

1. Configuration-only context before any run, with unset requirements.
2. An actual LG A0 run and evidence-bound explanation with units and provenance.
3. A structured hypothetical rail-resistance edit, validated without mutation.
4. Rejection of stale/mismatched context and unsupported physical operations.
5. Variant isolation and historical result labels; no inherited result becomes
   a current result of the new variant.

Project edits/runs used to demonstrate staleness are explicit orchestrator test
operations, never AI-autonomous execution. Save generated request/response
examples, source/implementation hashes, meaningful test receipts and the final
readiness report. Use new output directories and preserve incomplete attempts.
Verify the preceding release's artifact hashes before committing the new results.

The deliverable is tested parallel progress with an integration handoff. It is
not a fully autonomous copilot, replacement cell model, experimental module
validation or battery-performance improvement. Do not send outreach.
