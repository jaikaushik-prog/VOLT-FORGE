# Frozen-model GITT transient diagnosis: declared procedure

This follows the completed low-SOC diagnosis. Its C/30, GITT and 1C observations
are already used development evidence. Open no additional measurement family,
author-output channel, charge-optimized table or validation-workbook outcome.
Reuse the hash-pinned saved GITT experimental samples and segment/pair inventory
from `reports/p45b_low_soc_v1/run_001`, and the unchanged base parameter table.
Keep all 48 other archive members / 40 filename families protected.

## Model and five declared scenarios

Call the existing frozen `ae_p45b_reproduction.simulate` and its two-RC/hysteresis
kernel. Do not implement a second solver or modify frozen files. Retain capacity
4.5 Ah, isothermal 25 degC, discharge hysteresis -1, zero initial RC voltages,
and first recorded timestamp as the origin. Apply measured current open loop.
No initial state, parameter, voltage offset, capacity or time shift is fitted.
Output all original timestamps, including rests and measurements after a stop.
No clipping, curve extension, rest resets or stopping at a voltage threshold.

1. `primary`: initial SOC=1; left-held current; maximum substep 0.25 s.
2. `fine_step`: otherwise identical; maximum substep 0.0625 s.
3. `linear_current_sensitivity`: initial SOC=1; piecewise linear current with
   substep-midpoint evaluation; maximum substep 0.25 s.
4. `initial_soc_minus_0p005`: primary settings, initial SOC=0.995.
5. `initial_soc_plus_0p005`: primary settings, initial SOC=1.005.

The last two are declared exploratory perturbations of half a percentage point,
not a measured uncertainty range, probability interval or calibrated bound. Do
not select whichever fits better. Use a constant SOC-coordinate adapter around
the unchanged table/solver: query the table at integrated SOC plus the fixed
initial offset, then report that physical nominal coordinate in outputs. This
is equivalent to changing the integration origin at fixed capacity, which will
be tested with an independent analytic case. Stop a scenario if its shifted
origin or later state is outside table support; preserve unpredicted rows and
report the limitation instead of extending the table.

The baseline acquisition-gap rule stays max(10 s, 10 times the median positive
sample interval). This is compatible with this already-inventoried 1 s GITT
record. Do not silently substitute the broader C/30 diagnostic gap threshold.
Compare primary versus fine at common timestamps with the earlier proposed
0.1 mV numerical-convergence criterion. A miss means convergence outstanding,
not permission to tune until a model-accuracy criterion passes. Report sampling
and origin sensitivities separately; none is a replacement model candidate.

## Diagnostics fixed before calculating predictions

Use the complete previously retained 65 segments and 32 pulse/rest pairs. Check
their source rows and contiguity; do not select sequences by prediction error.
Report residual = prediction minus measurement, sample and adjacent-interval
time RMSE/bias, maximum absolute error, row counts and covered durations:

- Full record; discharge and rest separately; each complete segment.
- SOC bins <0, 0-0.2, 0.2-0.8, 0.8-1, >1 and unpredicted.
- Current ranges 0-0.5, 0.5-3, 3-5 and >5 A; temperature evidence.
- Within rest: 0-1, 1-10, 10-60, 60-600 and >600 s from the segment's first
  sample. Segment-relative time differs from the older >=0.1 A transition flag.

For every pair, compare last loaded voltage, first rest voltage, last-60-s
median and slope, loaded-to-late-rest recovery, and late-rest model polarization.
Keep pulse/rest durations, source lines and sample separation. This now uses a
full transient prediction, unlike the earlier steady-drop diagnostic. Neither
finite-rest voltage nor its median is relabelled equilibrium OCV.

Decompose each predicted voltage into blended reference, immediate I*R0 and
the two polarization voltages. Check algebraic closure. At fixed SOC history,
give conservative remaining fractions of initial RC-state influence using the
maximum table time constant for each RC branch: exp(-elapsed/tau_max). Also
bound initial hysteresis-memory fraction by exp(-gamma_min*integral(abs(I))/Q).
These are conditional sensitivities of this model, not bounds on real voltage
error; they exclude initial-SOC/reference uncertainty. Do not infer a new
physical process just because a finite-dimensional model loses initial memory.

Make whole-record measured/predicted and residual plots; per-pair loaded and
late-rest residual/recovery plots across SOC; and sequence panels selected by
SOC only: first pair, closest loaded endpoint to 0.5, 0.1, 0.04, and last pair.
Show both pulse and rest for each, including long tails. Source references and
the already-used development status must be visible in the report.

## Deliver and stop

Freeze procedure, source lock, implementation and synthetic tests before this
new replay. Save complete per-scenario predictions as deterministic CSV.gz,
per-segment and per-pair CSVs, machine-readable summaries, plots and hashes.
Verify SOC integration, solver reuse, exact source alignment, pair recovery,
metric weighting, stop behavior and initial-origin adaptation with meaningful
synthetic tests. Recompute key metrics independently after the real run and
verify all earlier frozen releases; preserve the living README before updating it.

Separate observations from causal hypotheses. No fitting, reference replacement,
new RC element, fresh-assessment claim or adoption into the LG editor/backend.
Application requirements remain `requirement not configured`; experimental
module validation remains `awaiting suitable measurements`. The module-current
discrepancy and `Q_sim_W` definition are separate blockers. Stop after this
declared diagnosis and propose a bounded next engineering action from its results.
