# Local two-RC diagnostics: procedure before fitting

25 October 2026. This bounded investigation reuses opened development evidence.
It diagnoses local SOC-shape and recovery-time mismatch; it does not fit a
deployable SOC-dependent model, adopt parameters or establish fresh validation.

## Evidence allocation and preservation

Use the eleven complete GITT pulse/rest pairs 21-31 from the preceding frozen
allocation, selected there by integrated nominal loaded-end SOC below 0.20.
Retain every sample in each selected pulse and its following rest. Source lines
and original measured channels accompany exports. Load only saved GITT samples,
segments, pairs and the primary / initial-SOC-minus-0.005 frozen replays, plus
the already-opened discharge parameter table. Never read unused outcomes.

The already-opened 1C record remains contextual evidence from the previous
report, not a fitting input. A collection of local pair fits has no defined
transfer rule to 1C, so it must not be used to predict that record. All 48 unused
P45B members / 40 families, including the reserved 3C family, nine LG cells,
13 FreeTwinEV records, charge table, validation workbook and protected module
outcomes stay protected. Existing files and models remain unchanged.

## Four diagnostic descriptions, not candidate product models

For each complete pair and each predeclared origin scenario:

1. **B0:** retain the frozen continuously propagated published prediction.
2. **L0:** hold R0, R1, R2 and the two time constants at their published values
   queried at that pair's loaded-end nominal SOC. Use the frozen time-varying
   reference/hysteresis voltage. This exposes the local-constant approximation.
3. **LR:** fit three constant local resistances at those same published time
   constants, with R0 in [0, 0.20] ohm and R1/R2 in [0.000001, 0.20] ohm.
4. **LRT:** repeat that bounded linear resistance fit for the fixed Cartesian
   grid of time-constant multipliers [0.25, 0.5, 1, 2, 4, 8, 16] on each branch.
   Retain only tau1 < tau2 to prevent branch-label exchange. Report every grid
   point; select the minimum declared objective for descriptive local plots.
   Ties follow increasing tau1 multiplier then increasing tau2 multiplier.

These are exploratory finite bounds, not measured physical limits. Do not widen
them or refine the grid after seeing outcomes. Report boundary contact. The
positive RC-resistance floor keeps C=tau/R defined; a floor-contact branch is
effectively unresolved, not a measured tiny resistor. No third RC, reference
offset, capacity fit, timestamp fit, current scaling or temperature law.

Local initial RC voltages are fixed to the continuously propagated frozen
replay states at the first pulse sample, independently of its measured voltage.
The local model is then propagated continuously through that complete pulse
and rest, without resetting at the transition. Each pair has a fresh diagnostic
initialization from B0; the fitted parameters are not stitched into a global
model. This conditional initialization is explicitly not a predictive full-run
candidate. Report its inherited states and full-pair SOC change.
SOC-varying resistance during a pulse is confounded with apparent recovery
time scales in this local approximation; neither is a uniquely identified
physical mechanism.

For each selected LRT fit, report the decay fraction exp(-previous_rest/tau)
for the preceding complete rest. A slow fitted tau may retain memory that the
published model neglects. Also propagate that pair's fitted constant R/tau
through the entire preceding measured-current history, starting from zero RC
states, then replay the pair without refitting. Label this a **conditional
initial-polarization sensitivity**: assuming local parameters at earlier SOCs
is unsupported, but no measured voltage calibrates those alternative states.
Report the maximum voltage shift and objective change. Neither initialization
is measured, and the sensitivity is not a confidence bound.

Use the measured charge-positive current, left held between timestamps. For
constant tau the exact recurrence is x_next = exp(-dt/tau)*x +
I*R*(1-exp(-dt/tau)). The reference follows the saved frozen SOC/hysteresis
trajectory at each original timestamp. Thus the electrical contribution is
affine in resistance with a known decaying initial-state term. No time step
approximation is introduced in this local constant-parameter recurrence.
Stop on invalid times, nonfinite values, failed source hashes or reference-domain
violations. Preserve the source acquisition pattern and transition interval.

## Objective and identifiability

Within each pair give the whole pulse and whole rest equal objective weight.
Within each phase use normalized trapezoidal time weights, never bridging the
phase boundary. Fit bounded linear least squares at each grid point. Report
sample/time RMSE, bias and maximum error by pair and phase as well as the balanced
objective. These are all in-sample conditional descriptive fits, not held-out
predictions. Lower fitting error is expected with added flexibility.

Report loaded-end error, final-60-second rest median error and rest error after
subtracting each trace's own final-60-second median. The centered-rest diagnostic
isolates shape from a constant voltage-level discrepancy but does not prove
equilibrium OCV or identify a physical mechanism. It is a reported diagnostic,
not an additional fitting objective. Show measured versus fitted entire pairs.

Report normalized sensitivity condition/rank/cosines for the three resistances,
their active bounds, and grid-supported tau ranges within 1% of the best
objective RMSE. Profile each tau by minimizing over the other tau and refitting
resistances. These are finite-grid conditional objective-sensitivity bands,
not confidence intervals; correlated residuals and model mismatch remain.
Do not claim nonlinear global optimality from a finite grid.

Compare LR versus B0/L0 to ask whether removing the imposed shared linear
low-SOC resistance shape helps locally. Compare LRT versus LR and centered-rest
errors to ask whether the fixed recovery time scales constrain the local fit.
Do not treat either comparison as causal proof or a deployable model. Relate
fitted parameters to SOC only descriptively; do not interpolate a new table.

## Linked reference / origin sensitivity and reporting

Repeat the identical allocation, bounds and grid using the already-saved
initial SOC=0.995 replay (primary is 1.000). Keep 4.5 Ah, nominal 25 degC,
hysteresis=-1 and the original record-start zero RC assumptions unchanged.
Use each replay's corresponding reference, SOC and inherited local RC states.
This is one linked origin/reference-coordinate sensitivity, not two independent
uncertainties. Do not choose an origin because it fits voltage better. No
assessment voltage calibrates an initial state. The known unsupported 1.005
case remains excluded rather than clipped.

Freeze this procedure, source hashes, code and synthetic checks before real
fitting. Tests must cover exact analytic rest and pulse behavior, charge/discharge
sign, agreement with the existing kernel, complete-phase weighting, known-grid
recovery, rank deficiency, nonfinite/bounds rejection, source isolation and
JSON-safe export. An independent verifier checks conserved original channels,
source hashes, equations, metrics and bounded-fit optimality. Plot all pairs'
parameters/objectives and complete examples chosen by SOC proximity to 0.10,
0.04 and the final pair, without cherry-picking voltage error.

The decision report must separate observations from physical hypotheses and
state whether time-scale evidence survives the origin sensitivity. No adoption
criterion, automatic next-data opening or voltage-limit acceptance follows.
Device requirements remain `requirement not configured`, module decisions
`insufficient evidence`, and module validation `awaiting suitable measurements`.
Preserve all negative results. If local flexibility still fails, finish this
bounded investigation without expanding the search.
