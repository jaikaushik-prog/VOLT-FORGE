# P45B measured-data viewer: declaration before outcome access

Declared 2026-10-25, before decoding any FreeTwinEV measurement rows. The prior
intake inventory remains an immutable record of the earlier header-only stage.

## Evidence allocation

Open the **complete ID01** CSV as development evidence for parser and viewer
implementation. Selection uses the Test_Matrix metadata only: the lowest stated
discharge magnitude (20 A), coolant 25 degC, flow 1.5 L/min, and logged charge /
recovery steps. This does not assert that the trace complies with the protocol.
No model fitting, parameter selection or prediction comparison is planned.

Keep ID02 and ID11 through ID22 outcomes unopened. These 13 complete records are
candidate future assessment evidence, not a finalized model-validation split.
Any later opening requires a new explicit allocation and frozen procedure.
There are no random timestamp splits. ID01 cannot later be described as fresh
independent evidence. Keep every original file unchanged; its XLSX duplicate
remains unopened. Existing nine unused LG cells and frozen outcomes stay sealed.
The accompanying allocation JSON records exact original CSV hashes and paths.

## Implemented scope to target

Use the existing loopback editor server with a separate `/measurements` view.
Retain the existing visual language: record navigation, two prominent electrical
plots, selectable source sensor trace, row inspector and evidence panel. Include
keyboard controls and a narrow-screen layout. Link back to the LG simulator.
Do not mix these traces into saved LG simulation runs or model error metrics.

Read source current unchanged (negative means discharge per protocol); do not
rescale, shift channels, interpolate missing rows or infer four branch currents.
Keep raw timestamp strings and CSV line references. Establish the actual time
encoding only from ID01; expose documentation discrepancies explicitly. Reject
malformed electrical/time records; missing optional readings remain null with
counts. Do not guess ambiguous temperatures or convert them to match setpoints.
Source SOC is a provided channel with an unresolved calculation method.

Return all raw samples in bounded consecutive pages, and an explicitly labelled
extrema-preserving overview for plots. A summary may describe measured ranges
and timing, never model accuracy. Source, allocation and parser hashes accompany
outputs. Backend access checks reject protected records before reading any data.
The catalogue reads metadata only and works without downloaded raw files.

Search primary public sources for the missing Calibration_Table, timing/sense
locations and P45B electrical characterization. Document what was checked and
what remains missing; no outreach. No new cell model, topology or thermal model.

## Checks before delivery

Synthetic parser cases: source polarity, numeric/calendar time, malformed,
missing, nonfinite and nonmonotonic data; explicit unit labels; source hash
mismatch; protected record denial before filesystem access; pagination and
overview extrema; actual HTTP access protections. Exercise the real local view
on desktop and mobile, inspect screenshots, and retain test receipts. Verify raw
and frozen artifact hashes, retaining earlier versions of any living files
needed by old release manifests. Add reproducible CLI and viewing instructions.
