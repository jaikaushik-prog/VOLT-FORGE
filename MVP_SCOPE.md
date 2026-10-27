# VOLT-FORGE first product workflow

**Current local release, 26 October 2026:** [V1_RELEASE.md](V1_RELEASE.md)
records the completed thermal, engineering-screen, investigator and assembly extension.
The scientific and future-capability boundaries below remain explicit.

The [product vision](VOLT_FORGE_Product_Vision.md) is the direction: a visual
battery-engineering workspace connecting design choices, simulation and evidence.
Its concept mockups and broader stage descriptions are not implemented features.
The source Markdown was found in Downloads and copied unchanged; its referenced
mockup image assets are not bundled in this repository.

The immediate workflow is now executable: **load A0 → inspect → validate/edit →
create A1 revision → run → inspect current/voltage → compare → export/replay**.
The local 2D editor now connects this workflow to a schematic, inspector, result
plots, evidence view and explicit run comparison. See [EDITOR_GUIDE.md](EDITOR_GUIDE.md).

## Implemented

- Separate P45B measured-data viewer for predeclared FreeTwinEV ID01, exact source
  samples/units, provenance, plots and exports; 13 complete records protected.
  No P45B model or current-sharing validation. See
  [measurement scope](reports/measurement_viewer_v1/DECISION.md). The next evidence
  milestone is an inventory/allocation for newly found public P45B cell data.

- LG M50T NMC P7/P17/P19/P13 only; explicit same-side 1s4p ladder with eight nodes,
  four cell branches, six independently specified rail resistances, p1/n1 terminals.
- Frozen v2 rested-reference/one-RC electrical dynamics through the existing solver.
  Current sharing, voltage, SOC/polarization, rail drops, charge, delivered service
  and electrical resistor dissipation. New schema-2 projects add a separate,
  declared-parameter, unvalidated surface-equivalent thermal trajectory.
- One shared versioned project, named variants, immutable design revisions and run
  snapshots, code/model/runtime hashes, explicit provenance and units.
- Whitelisted resistance, initial-state, load, temperature-assumption, numerical
  step and sourced-requirement edits; sealed fitted parameters stay read-only.
- Reliable freshness and variant ownership. Pure layout/camera/selection edits
  cannot change physics or invalidate outputs. Historical results remain visible.
- Existing four manual scenarios, seven sensitivity types, coordinate and time-step
  checks retained. Sensitivity runs are labelled and separated from nominal results.
- JSON-compatible Python interface and CLI, generated real request/response
  examples, paginated time series and capability flags for frontend handoff.
- Like-for-like unranked comparison, original-data-preserving future measurement
  importer, calibration/alignment/current-sum checks, reproducible standalone export.
- Automated tests including software equivalence, lifecycle/invalidation, failure
  preservation, synthetic ingestion and replay in a separate process.

The original editable properties and output channels are in
[FRONTEND_CONTRACT.md](FRONTEND_CONTRACT.md), with the schema-2 extension documented
in [V1_RELEASE.md](V1_RELEASE.md). Temperature changes are declared initial/ambient
conditions for the one-way thermal model; they do not activate an electrical temperature law.
Capacity/reference changes are predeclared exploratory sensitivities, not new fits.

## Next implementation milestone

The **2D four-cell workspace is implemented**: four selectable cells, six exact
rail edges, module inspector, preview/apply, variants, asynchronous local runs,
current/voltage plots, saved-sample inspection, evidence, comparison and download.
Pure layout changes leave physics current. The browser shows inherited/outdated,
failed/partial and unsupported states. Production dependencies are unchanged.

Next, conduct a student/engineering usability review of this bounded workflow and
add a guided measurement-import screen over the existing importer, with explicit
sensor-location mapping and calibration completeness. Keep the current supported
topology until another model and its evidence justify broadening the editor.
Measured traces cannot be shown or validated until suitable observations arrive.

This milestone does not require new measurements to demonstrate software. A usable
engineering acceptance decision does: obtain actual load requirements, traceable
current calibration, measured contacts and synchronized module observations with
documented charge/rest preparation. Preserve complete prospective assessment
sequences before any further fitting or selection.

## Future, unavailable now

General 3D CAD; arbitrary cell placement/rewiring/topologies/chemistries;
geometry-to-resistance rules; new cooling geometries and validated thermal/contact models; current-density or
stress fields; component cost/manufacturing feasibility; advanced failure-case search;
ranked repairs and optimization; natural-language copilot; collaborative editing;
CAD/PDF manufacturing exports; pack-scale validation.

These require their own implemented models, numerical checks, source-backed inputs
and, where engineering accuracy is claimed, experimental evidence. Moving a shape
must never secretly change an unimplemented physical parameter. The future AI
assistant proposes structured edits and explains backend results; the electrical
solver remains responsible for physical calculations.

## Decision boundaries

A0/A1 are **simulation comparisons**, not validated repairs or battery-performance
gains. The current-channel discrepancy remains unresolved. Nominal 23 C cell
characterization does not validate module thermal behaviour or arbitrary sustained
branch loads. The actual device minimum voltage and allowable excursion duration
remain null; the old 3.50 V/25 mV examples are not application requirements.
The improved cell model, nine unused characterization cells, protected module
outcomes, original archive and existing provenance remain preserved.
