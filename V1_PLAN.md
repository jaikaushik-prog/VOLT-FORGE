# VOLT-FORGE v1 plan: thermal, constraints, failure investigation and assembly view

25 October 2026. Plan written before implementation, following this repository's habit of
declaring scope first. v1 builds on the existing frozen-v2 electrical backend and 2D editor.
It does not refit cell models, open protected module outcomes or change sealed files
(`models/coupling.py`, `models/coupling_v2.py`, `models/improvement.py`,
`simulation/workflow.py` and the other release-hashed artifacts).

## Why these four additions

The product vision's Stage 1 ("credible working demonstrator") asks for:

- an electrical **and thermal** solver;
- current **and temperature** outputs on the assembly;
- basic failure/constraint checks and saved variants.

The repository already provides the electrical solver, saved variants, freshness, comparison and
reproducible export. v1 adds what is missing, at demonstrator fidelity, with every assumption
visible.

## Scope

1. **Lumped thermal model (one-way coupled)** in a new module, `models/thermal_v1.py`.
   - **Structure:** four cell nodes and an ambient boundary.
   - **Heat sources:** per-cell R0 loss, exact per-interval R1 loss and allocated rail-segment loss, all taken from the saved electrical trajectory.
   - **Integration:** exact exponential discretization under the solver's held-input convention. A thermal energy ledger is checked on every run.
   - **No feedback.** The frozen electrical models have no temperature law, so temperature does not change electrical parameters. Reversible (entropic) heat is omitted and the run states this.
   - **Declared default parameters:**
     - Cth = nominal mass (69.25 g, Piombo Table 1) × an assumed cp of 1000 J/(kg K).
     - Cell-to-environment conductance = Cth/τ, with τ fitted to the measured post-discharge cooling of already-opened Piombo test 53 (see `scripts/derive_thermal_defaults.py`). This is in-sample, fixture- and chamber-specific, and not validated.
     - Neighbour conductance and the rail-heat split are labelled assumptions.
   - **Labels and editing:** outputs are labelled *simulated, declared thermal parameters, not validated*. All parameters can be edited with provenance.
2. **Engineering constraint checks.** Optional limits for:
   - peak branch current;
   - active current-sharing imbalance (active-current floor 0.5 A);
   - peak cell temperature;
   - the existing minimum terminal voltage / excursion rule.

   A missing limit or source remains **requirement not configured**. Configured limits return a signed margin, the worst time and component, and the first crossing. No "pass" wording is used, and no safety claim is made.
3. **Failure Investigator v1.**
   - **Search:** a deterministic finite grid over permitted perturbations: added resistance on one named rail segment (contact degradation), constant load current and ambient temperature. It uses the same electrical and thermal engine as a normal run.
   - **Results:** per-requirement cases sorted by margin, coverage counts and solver stops kept as stops, never passes.
   - **Saving:** the record is immutable, and any case opens as a named variant (explicit edits with provenance) for a normal, replayable run.
   - **Not included:** optimizer, ranking across requirements, and automatic repair claims.
4. **Assembly view.** A dependency-free isometric SVG view of the 1s4p fixture: cylinders, both copper bars and the position-1 terminals. It colours each cell by temperature or current at the selected saved time, with a fixed legend and units. Display only: moving or viewing never changes physics.

**Also included:** a cycle charge-balance diagnostic for the two already-opened runs (tests 53 and 28), added to the reconciliation evidence. It uses only data already in the repository and decides nothing. The channel comparisons and separate C/20 characterization support investigating the cycler's discharge record, but do not identify the faulty direction, establish absolute Hall calibration or admit a channel. A quantitative matched-protocol uncertainty bound remains unavailable.

## Compatibility

- New projects use `voltforge.project/2` and `voltforge.design/2`. The latter adds `thermal` and `engineering_requirements` blocks.
- Existing `voltforge.project/1` projects still open and run. They are electrical only, their thermal output is "unavailable", and nothing is silently migrated.
- Electrical trajectories and their replay are byte-for-byte unchanged. Thermal output is a separate `thermal.csv`, which replay recomputes and compares.

## Acceptance

- **Thermal tests:**
  - analytic one-node step response;
  - a passive two-node exchange conserves energy;
  - insulated linear heating;
  - rail allocation weights sum to one;
  - zero heat at ambient stays at ambient;
  - the ledger closes to 1e-9 relative.
- **Requirement tests:** unconfigured, violated and non-violated cases; signed margins; imbalance suppressed below the active floor.
- **Investigator tests:**
  - the grid count is deterministic;
  - a known violation is found;
  - coverage counts add up;
  - a case opens as a variant whose run reproduces the case's metrics.
- **Regression:** the existing suite keeps passing, apart from the two assertions that encoded "no thermal capability". Those are updated deliberately and recorded.
- **Browser check:** the editor workflow runs with thermal overlay, assembly view, constraint results and the investigator. Screenshots are kept under `reports/v1_release/`.

## Not claimed

Experimental module validation; a thermal model validated against held-out data; core temperature;
safety certification; repair benefit; optimization; 3D CAD; a natural-language copilot.
