# VOLT-FORGE v1: local four-cell workbench

26 October 2026. This completes the interrupted `v1-thermal-investigator` build on the existing frozen-v2 electrical backend. It is a working simulation demonstrator. Module-level accuracy, thermal accuracy and repair benefit remain experimentally unvalidated.

27 October UI refinement: a larger focused canvas, optional properties, a designs/components menu, normal load interval forms, four main result values and separate analysis views. Full details remain available through labelled disclosure. See [the updated user guide](EDITOR_GUIDE.md) and [design decisions](DESIGN.md).

## Open it

From this repository on the current Mac:

```bash
PYTHONPATH=src .venv/bin/python scripts/run_editor.py --project workspace/editor_project --port 8792
```

Open **http://127.0.0.1:8792**. The working project persists under the ignored `workspace/` directory. The prepared demonstration contains A0 and a contact-degradation variant C1; both retain their exact inputs, outputs and simulation labels. The reference uses P7/P17/P19/P13 LG M50T cells with the existing fitted models. Its 14.55 A, 360 s load, initial SOC, rail resistances and thermal assumptions are declared demonstration inputs.

The general launch command still defaults to port 8765. The existing `.venv` is ready on this machine. Reproduction elsewhere requires Python 3.12 and the pinned dependencies. No raw Piombo archive is needed for this bounded simulation workflow.

## What works

- Circuit and isometric assembly views share component selection and saved simulation time. Assembly is an SVG display, not a CAD model. Each lumped cell has one temperature color and explicit units.
- Inspect four cells and six exact rail segments. Frozen fitted electrical parameters remain read-only. Edit supported resistance, initial-state, load, numerical, thermal and proposed-limit fields through Preview and Apply.
- Immutable revisions and named variants preserve previous results. A relevant edit marks earlier results outdated. Display layout changes leave physics unchanged.
- Run the existing electrical solver and the one-way four-node thermal model. Temperatures do not feed back into electrical parameters. Entropic heat is omitted. The UI exposes these limitations and parameter sources.
- Engineering screens evaluate configured peak current, active current imbalance and surface-equivalent temperature limits. Missing limits/sources are unconfigured; a clear sampled screen is not an experimental or safety pass. The existing voltage rule remains supported.
- The Failure Investigator searches a finite, budgeted grid of named rail-contact degradation, load and ambient assumptions. It retains coverage, per-requirement rankings, solver stops and separate thermal failures. Cases reopen as variants for ordinary runs.
- Compare completed runs under compatible common operating conditions, including current, voltage, energy, temperature and imbalance. Comparisons are unranked simulations, not measured repairs. Changed load or thermal parameters cannot silently enter a like-for-like comparison.
- Export selected runs as a ZIP with inputs, arrays, sources, software and hashes. Standalone `replay.py` reproduces electrical and available thermal outputs from captured code. No original raw archive is bundled.

The separate P45B measurement viewer retains its existing protected-record and source-access rules.

## A short demonstration

1. Select A0 and a current saved nominal run. Choose Assembly and move the time slider. Select a cell to inspect its saved temperature/current and fitted-model identity.
2. Choose Edit limits, or select Module and choose Engineering limits and enter a proposed upper branch-current target with a textual source. Preview and save. Observe the outdated run, then run the new revision.
3. Open Investigate. Select positive and negative rail segment 1, add `1, 3` mOhm, leave load/ambient blank and choose a five-case budget. The baseline plus four contact changes are evaluated.
4. Open a violating case as a variant and run it. Compare with A0 under the same conditions. The prepared example uses a **proposed 5 A demonstration target**, not a cell rating or a customer requirement.
5. Export both compatible runs. In the extracted folder run `python replay.py RUN_ID` with the recorded environment. Matching trajectories establish software reproduction, not experimental validation.

Changing thermal capacitance/conductance is an assumed model experiment. Visual movement does not create a physical connection or a cooling design.

## Repairs completed from Claude's interrupted work

The original findings and partial source snapshot are retained under `reports/v1_release/continuation/`.

| Area | Correction | Executed evidence |
|---|---|---|
| Polarization heat | Propagate constant, exp(-t/tau) and exp(-2t/tau) forcing exactly, including temperature integrals | Independent analytic zero/nonzero-current tests, resonant forcing and 30/10/1/0.1 s saved grids |
| Thermal validation | Reject nonfinite/backwards time, invalid steps/losses and nonfinite output/ledger | Parameterized regressions in `test_thermal_v1_engine.py` |
| Charge integration | Integrate contiguous selected blocks without bridging omitted rows | Interrupted-recharge regression; pinned real ratios unchanged |
| Charge interpretation | Retain fault/calibration uncertainty; remove unsupported quantified temperature-capacity bound | Revised diagnostic/addendum; no channel admitted or rescaled |
| Search resources | Budget bounds case construction; list sizes capped | Large requested grid constructs/evaluates one case at budget one |
| Thermal search failure | Preserve electrical metrics/limits/stop and report thermal failure separately | Injected-failure comparison with normal-run behavior |
| Requirement validation | Finite non-boolean numeric limits and nonempty textual sources | Invalid-number/type regressions |
| Sample alignment | Absolute timestamp tolerance and positional thermal assignment | Different-index and 0.05 s late-time mismatch regressions |
| Publication | Validate thermal summary before atomic CSV publication | Failed summary leaves electrical results without an available thermal file |
| Artifact integrity | Derive temperature availability from declared inputs, completed thermal status and the verified run manifest | An injected unregistered 999 C file cannot create legacy or failed-run temperature results |
| Thermal failure isolation | Reject malformed/nonfinite/misaligned output before publication and remove interrupted staging files | Extreme capacity, truncated frame, missing column, nonfinite value, time mismatch and interrupted-write regressions preserve electrical results |
| Replay status | Verify the inner run artifact manifest and refuse full-run certification after an original thermal failure | Missing thermal artifact and failed-original replay regressions |
| Schema and test quality | Require positive heat capacity, sourced configured limits, supported versions and structured type errors | Strict rejection tests; deliberately permissive validator makes the rejection test fail |
| Editor | Temperature/readout, limits, investigation, case variant, comparison and downloaded replay | Live-browser workflow and screenshots |

## Verification and limits

Evidence is under `reports/v1_release/`:

- **Python:** 257 passed, 8 skipped, zero failed. Skips require the absent official raw archive. JUnit: `pytest.xml`.
- **JavaScript:** 23 passed, zero failed, covering state, assembly, panels, load-input binding and overlay contrast.
- **Live browser:** run/edit/stale state, assembly/time/readout, engineering screen, five-case search, case variant, comparison, ZIP download and two standalone electrical/thermal replays passed. A 393 px viewport, draft preservation, normal load forms, field validation, keyboard tabs and the focused analysis views were checked. The full browser workflow has 14 recorded checkpoints. No uncaught exception or error-level browser log was observed. The assembly canvas can scroll horizontally on narrow screens.
- **Protected artifacts:** the reference manifest, 112 protected reference-initial-state files and nine sealed model artifacts retain their expected hashes.

These are numerical/software/workflow checks. No new fit, experimental validation, protected outcome access, safety certification, user study, optimizer, copilot, general CAD or manufacturing export is claimed. Thermal defaults retain their in-sample cooling derivation and assumed heat capacity/contacts. Current inconsistencies still require independent calibration/protocol resolution.

The original thermal and investigator review reports were recovered. Later integration/schema review observations were found in archived sessions, although those raw sessions contain no final-channel report. Their reproducible findings were repaired and regression-tested too. This continuation has not received a new independent cold review. The release record distinguishes executed verification from review status.

Changes remain local on `v1-thermal-investigator`, including Claude's preserved partial work. Review the diff before a future commit or remote handoff.
