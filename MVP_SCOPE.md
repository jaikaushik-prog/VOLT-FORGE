# VOLT-FORGE first product workflow

The [product vision](VOLT_FORGE_Product_Vision.md) is the direction: a visual
battery-engineering workspace connecting design choices, simulation and evidence.
Its concept mockups and broader stage descriptions are not implemented features.
The source Markdown was found in Downloads and copied unchanged; its referenced
mockup image assets are not bundled in this repository.

The immediate workflow is now executable: **load A0 → inspect → validate/edit →
create A1 revision → run → inspect current/voltage → compare → export/replay**.
No frontend screens were built in this sprint.

## Implemented

- LG M50T NMC P7/P17/P19/P13 only; explicit same-side 1s4p ladder with eight nodes,
  four cell branches, six independently specified rail resistances, p1/n1 terminals.
- Frozen v2 rested-reference/one-RC electrical dynamics through the existing solver.
  Current sharing, voltage, SOC/polarization, rail drops, charge, delivered service
  and electrical resistor dissipation; no predicted temperature.
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

The exact editable properties and output channels are in
[FRONTEND_CONTRACT.md](FRONTEND_CONTRACT.md). Temperature changes are assumptions
used in coverage metadata only; they do not activate a temperature law.
Capacity/reference changes are predeclared exploratory sensitivities, not new fits.

## Next implementation milestone

Build a small **2D four-cell workspace** on this contract: select one of the ten
components, show its actual supported fields and evidence, preview an edit, create
a variant, run the backend in a worker, and bind time-series plots/overlays to an
explicit current run. Show outdated/failed/unsupported states and missing
requirements. Allow export of the selected experiment. Test the complete workflow
with a frontend teammate before considering a broader editor.

This milestone does not require new measurements to demonstrate software. A usable
engineering acceptance decision does: obtain actual load requirements, traceable
current calibration, measured contacts and synchronized module observations with
documented charge/rest preparation. Preserve complete prospective assessment
sequences before any further fitting or selection.

## Future, unavailable now

General 3D CAD/assembly; arbitrary cell placement/rewiring/topologies/chemistries;
geometry-to-resistance rules; thermal/contact/cooling models; current-density or
stress fields; component cost/manufacturing feasibility; failure-case search;
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
