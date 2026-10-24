# Four-cell simulation and product-handoff readiness

25 October 2026. **The electrical backend and the first product workflow work;
100 tests pass.** The frontend can connect to a versioned Python/JSON interface
for load, inspect, edit, branch, run, time series, comparison and export/replay.
Experimental module validation is **awaiting suitable measurements**. Device
voltage/excursion requirements remain **requirement not configured**; the supplied
runs return **insufficient evidence** for engineering acceptance.

## Actual repository state and what changed

| Workstream | Status after inspection and this sprint |
|---|---|
| Existing dynamic ladder, frozen v2 model, SOC/RC and electrical accounting | Already complete; reused unchanged. No new electrical model or fitting pipeline. |
| Four manual scenarios, 28 sensitivities, coordinate and time-step checks | Already complete; original declarations, outputs and test records retained. |
| Coverage, requirement checks and future-measurement import/comparison | Already complete; reused through the project interface, including synthetic ingestion tests. |
| Shared project state and explicit component/connection graph | Implemented: schema v1, stable IDs, pinned model references, units/provenance, requirements, variants, saved runs and optional display state. |
| Invalidation and immutable run history | Implemented: new design revisions; captured scenario/model/software inputs; owner-variant checks; visual changes excluded; old runs retained. |
| Frontend handoff and reproducible result export | Implemented: Python/JSON API and CLI, exact generated examples, A0/A1 demonstration, source/reference assets and independent-process replay. |
| Visual editor and asynchronous/collaborative application infrastructure | Not built; next bounded product milestone. No general CAD framework was introduced. |
| Experimental module accuracy and requirement acceptance | Blocked by external calibration, preparation, module measurements and missing application requirements. |
| Thermal solver, broad CAD, AI copilot and optimizer | Unavailable; future scope, not incomplete electrical outputs. |

The original downloaded [product vision](VOLT_FORGE_Product_Vision.md) is retained
unchanged. Its concept graphics/specifications and thermal/AI stage descriptions
are not current capabilities. See [MVP_SCOPE.md](MVP_SCOPE.md) for that distinction
and [PRODUCT_INTEGRATION_PLAN.md](PRODUCT_INTEGRATION_PLAN.md) for the inventory and
A0/A1 scenario declaration made before examining the new comparison outputs.

## What the frontend can use

[`voltforge.project`](src/voltforge/project/service.py) wraps the existing
`simulation.workflow`, `simulation.measurements`, `simulation.reporting` and
`models.coupling_v2`. It accepts only the LG M50T NMC cells P7/P17/P19/P13 in a
same-side 1s4p ladder. Cells have stable IDs; six rail connections map to explicit
node pairs, and terminals are fixed at p1/n1. Unknown topology, rewiring, fitted
parameter edits and thermal requests are rejected.

The project stores frozen-model versions/hashes, conditions, load, simulation
settings, explicitly unset requirements, variants, outputs and evidence. Each run
captures a complete immutable design/scenario/model/software snapshot before
execution. Results from another variant are inherited as **outdated**, never
current. A changed physics/requirement revision or software/runtime invalidates
dependent results. Pure positions, camera and selection changes do not create an
electrical revision. No implemented geometry-to-resistance rule exists.

`execution_status` (completed/failed) and `freshness` (current/outdated) are
separate. Domain failures retain exact inputs and supported partial samples.
No SOC clipping, reference extrapolation or invented temperature is introduced.
A synchronous request may return a saved failed run; the UI must display that
status and must select results by variant, scenario, run and snapshot ID.

[FRONTEND_CONTRACT.md](FRONTEND_CONTRACT.md) documents the exact editable properties,
request envelopes, error codes, units, measurement handoff and replay. The
[generated examples](reports/product_integration_v1/FRONTEND_EXAMPLES.md) and
[complete response corpus](reports/product_integration_v1/demo/examples) come from
this implementation. A copied project preserves its state; an export is an
immutable selected-history package rather than a mutable project.

## Declared A0/A1 simulation comparison

Both cases use 14.55 A for 360 seconds, initial relative SOC 0.70 for every cell,
zero polarization, assumed ambient/surface 23 C, and dt 0.25 seconds. A0 has
0.001 ohm per segment on each rail. A1 changes **only positive segment p1-p2 to
0.0005 ohm**, with explicitly hypothetical provenance. This differs from the
older scenario that changed all six segments. No physical feasibility or measured
resistance is established by the edit.

| Simulation | Peak branch current [A] | Minimum cell/terminal [V] | Mean delivered power [W] | Net delivered [Wh] | Cell R0 / rail / R1 losses [Wh] |
|---|---:|---:|---:|---:|---:|
| A0 | 4.666864 | 3.633225 | 53.688737 | 5.368874 | 0.131814 / 0.033778 / 0.099966 |
| A1 | 4.526947 | 3.637121 | 53.744324 | 5.374432 | 0.131656 / 0.028614 / 0.099796 |

Both supply the same requested/delivered 1.455 Ah in the simulation. The minimum
voltage difference is about 3.90 mV. It is **not** an experimentally demonstrated
repair advantage, safety margin or battery-performance improvement. No ranking
is produced. Neither run exceeds the descriptive 4.9 A primary-subset boundary,
but **every branch still carries unsupported module waveform transfer**. Matching
an amplitude band does not validate current sharing or contiguous dwell accuracy.

See [comparison table](reports/product_integration_v1/demo/comparison.csv),
[plot](reports/product_integration_v1/demo/comparison.png),
[exact conditions and flags](reports/product_integration_v1/demo/comparison.json)
and [workflow/replay result](reports/product_integration_v1/demo/demo_result.json).
The demonstration explicitly records A0 inherited by A1 as outdated, reruns A1,
then moves display positions without making its results outdated.

## Mathematical/software evidence

The earlier 75-test release covered analytical RC and network cases, conservation,
charge/discharge conventions, node/rail accounting, domain stops, importer timing
and current conservation. Its full report is preserved byte-for-byte as
[previous readiness](reports/product_integration_v1/SIMULATION_READINESS_previous.md).
For the earlier four 360-second cases, KCL residual was below 1.8e-15 A and
charge-accounting residual below 2.1e-10 A s. Changing dt from 1 to 0.25 s changed
terminal voltage by at most 0.00792 mV. These are numerical checks, not accuracy
bounds. [Original verification](reports/module_simulation_v1/software_verification.json)
remains unchanged.

The current suite has **100 passed, zero failed, zero skipped**:
[JUnit record](reports/product_integration_v1/pytest.xml). Its 25 additional checks
cover explicit topology and frozen identities, invalid edits/units, optimistic
revision conflicts, single-writer exclusion, variant isolation, visual invariance,
software-version invalidation, artifact tampering, partial and empty domain stops,
backend exceptions, output mapping, changed-service comparison rejection, all
seven sensitivity scenarios, synthetic importer reuse and standalone export replay.
The project path reproduces the existing solver's numerical trajectory rather
than introducing a second implementation. The exported A0/A1 runs each replay
1,441 samples with all numeric columns agreeing within rtol/atol 1e-10.

[Integration verification](reports/product_integration_v1/integration_verification.json)
checks all 112 protected baseline artifacts, the original archive hash, the prior
145 release artifacts and the new handoff. The living root readiness report was
explicitly updated as requested; its original hash is verified against the
preserved previous-readiness copy. Previous release manifests, assessment outcomes,
fitted artifacts and test XML are not rewritten. Nine unused characterization
cells remain unconsumed. No raw measurements were decoded for this product layer.

## Experimental support and unresolved decisions

The frozen v2 cell model retains its original evidence and limits. Its 9.55 mV
headline was the specified single-cell SOC/current/temperature subset; full-record
maximum errors reached about 97 mV. It is not a module error bound. The rested
voltage curve is not proven equilibrium OCV. Initial SOC/reference-origin
uncertainty and sparse reference coverage remain; no replacement was adopted.

The baseline assumes temperature and initial states. It has no thermal prediction,
no broad temperature law and no independent module-current accuracy evidence.
The approximately 4.85 A sustained cell plateau and brief higher-current records
do not establish arbitrary branch waveform validity. Old sensitivity results and
the seven available project sensitivity scenarios are exploratory, not confidence
intervals or guarantees. SOC-origin and reference uncertainty are not treated as
independent calibrated errors.

The measured module-versus-branch-current discrepancy remains unresolved. Neither
source is rescaled or selected for capacity agreement. The importer preserves
original bytes and requires timing, channel locations, units, polarity, sensor
mapping, calibration and preparation metadata. The current integration test uses
an explicitly synthetic fixture with a known +10 mV voltage offset, recovering
-10 mV prediction-minus-fixture bias; this checks plumbing only.

Actual device minimum voltage, allowed excursion duration and a documented source
remain null. **3.50 V and 25 mV are not defaults or authoritative requirements.**
A supplied requirement enables only the existing finite-step screen and cannot
turn missing module validation into an experimental pass.

Minimum external evidence needed next:

1. Actual load/converter voltage and excursion requirements, with sources and
   consequences of a wrong decision; establish an uncertainty budget prospectively.
2. Traceable Hall/cycler calibration and processing, sensor-position assignment,
   alignment/filtering evidence and an independent current reference resolving the
   disagreement, or suitable replacement controlled measurements.
3. Measured contacts/rail resistances and physical feasibility, documented charge
   and rest preparation, synchronized module/four-branch currents, defined-node
   voltages and temperatures for the intended waveform and relevant imbalance.
4. A prospective allocation of complete measurement sequences before any further
   fitting, model selection or module-accuracy assessment.

The [author questions](reports/reconciliation/AUTHOR_QUESTIONS.md) and
[lab request](reports/reference_initial_state_v1/LAB_REQUEST.md) remain unsent.

## Reproduce and hand off

From the repository root, with the existing pinned environment:

```powershell
$env:PYTHONPATH = 'src'
& C:\Users\DELL\anaconda3\python.exe scripts\demonstrate_product_workflow.py
& C:\Users\DELL\anaconda3\python.exe -m pytest -q --junitxml=reports/product_integration_v1/pytest.xml
& C:\Users\DELL\anaconda3\python.exe scripts\verify_product_integration.py
```

The first command verifies an existing completed demonstration without overwriting
it. For a fresh full reproduction, use `--out tmp/product_demo_fresh` (a new path).
The demo loads A0, runs it, validates/applies the declared A1 edit, demonstrates
invalidation, reruns, compares, exports, replays and writes exact frontend examples.
It uses the configured reference assets already in the repository and does not
need the raw archive. The full historical test/preservation suite separately
requires that original archive; it is still excluded from GitHub.

The original `python -m voltforge.simulation configure/simulate/compare/validate`
workflow remains available. Use new output directories for new investigations;
do not overwrite old release outputs or regenerate their historical test XML.
For the handoff, prefer the versioned project interface and its immutable runs.

The next implementation milestone is a small 2D four-cell editor/inspector and
results view using this contract. A student can now change one supported input,
see the computed current/voltage consequences, track assumptions and export a
reproducible comparison. Whether a physical module actually meets its load's
requirements still requires the missing calibrated measurements.
