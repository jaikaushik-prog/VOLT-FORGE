# Product handoff implementation plan

25 October 2026. Read the downloaded `VOLT_FORGE_Product_Vision.md` and retain
its original bytes in the repository. The current user instruction limits this
sprint to the electrical backend and frontend handoff; the concept's thermal,
CAD and AI features are future work.

## Repository inventory before changes

- Complete: frozen v2/C2 models; four-cell dynamic ladder; SOC/RC, node, charge,
  power and loss accounting; support stops; four declared scenarios and 28
  sensitivities; numerical checks; strict measurement importer and diagnostic
  comparison; 75 passing tests. Reuse `simulation.workflow`, `measurements` and
  `reporting`, and `models.coupling_v2` without refitting or duplicating physics.
- Missing: shared project schema, explicit editor connection mapping, immutable
  design/run history, reliable per-variant freshness, structured edit validation,
  a frontend contract and a self-contained reproducible export.
- Blocked externally: experimental module accuracy, current-channel calibration
  reconciliation, actual device voltage/excursion requirements, measured initial
  states/interconnects and thermal history. Software work does not depend on these.

## Implementation and predeclared demonstration

Use a synchronous Python API with JSON-compatible requests/responses; no web
server or frontend infrastructure. Persist versioned project/revision/run files.
Only the existing LG M50T P7/P17/P19/P13 same-side 1s4p ladder is supported.
Represent eight nodes, four cell branches, six rail edges and terminals at p1/n1.
Keep visual positions/camera/selection outside the physics fingerprint.

Runs bind their variant, design revision, complete effective inputs, model and
reference assets, source-code hashes and runtime versions. Preserve old runs.
Every edit validates the proposed full design; unknown properties/topologies
are rejected. Fit parameters stay read-only. The already-declared seven
sensitivities remain explicitly exploratory scenario overrides.

Demo A0 uses existing equal-SOC inputs: 14.55 A, 360 s, SOC 0.70, polarization
0 V, 23 C assumptions, 1 mOhm per rail segment, dt 0.25 s, voltage requirements
unset. A1 changes only positive rail segment p1-p2 from 0.001 to 0.0005 ohm,
with manual hypothetical provenance. Declare the edit before running A0/A1;
show inherited results as outdated, then run and compare at identical conditions.
Do not select or rank designs from these outputs.

Test persistence/reload, edit validation, topology rejection, stale results,
variant isolation, visual-only changes, immutability/tamper detection, numerical
equivalence to the existing backend, domain failures, mismatch comparison,
sensitivity labels, synthetic ingestion and clean export replay. Preserve the
old 75-test record and release manifest; record this sprint separately. The old
readiness document is copied byte-for-byte to
`reports/product_integration_v1/SIMULATION_READINESS_previous.md` before updating
the requested living report. No raw archive decoding or unused data is needed.
