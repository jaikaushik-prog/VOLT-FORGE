# Bounded low-SOC resistance investigation: procedure before fitting

25 October 2026. Continue the completed GITT replay using already-opened
development evidence. Preserve the published P45B table, LG v2, all prior
outcomes and raw downloads. This is a conditional identifiability investigation,
not model adoption or experimental module validation.

## Evidence allocation

Use only the saved complete 25 degC GITT discharge samples, segments and pairs
from `p45b_low_soc_v1`, the frozen GITT replay, and the previously opened 1C
discharge trace. GITT supplies fitting/development diagnostics. The complete 1C
trace is a used-record transfer check, excluded from fitting and selection.
Its existing errors have already informed development; it is not independent.

Reserve the complete `MOLICEL_P45B_025degC_3C_Dch` family for a future, separately
declared confirmation/transfer study. This choice uses filename metadata only;
do not open its outcomes in this sprint. Its 3C protocol is outside this GITT
fitting amplitude and would test transfer, not automatically confirm 1C pulses.
All remaining 48 members / 40 families stay numerically unopened, including
this reservation. The charge-optimized table and validation workbook remain
protected. Nine LG cells and 13 FreeTwinEV records remain unused.

## Two candidates, fixed before fitting

Retain baseline B0 unchanged. Hold references, 4.5 Ah capacity, hysteresis law,
published SOC-dependent time constants and nominal 25 degC fixed. No voltage
offset, time alignment, initial-state or capacity fitting is allowed. Initial
SOC=1, hysteresis=-1, zero RC states; no resets at pulse/rest boundaries.
Use the frozen simulator, left-held measured current and 0.25 s maximum step.
Stop on reference-domain violations or the existing acquisition-gap rule.

Define the dimensionless basis `b(z)=max(0,(0.20-z)/0.20)` inside the existing
table support. This is an explicitly proposed linear low-SOC shape, not a
measured law. It is zero at/above 20% nominal SOC and is not clipped below zero
SOC; the table's support policy still governs. Modify parameters after the
published interpolation, so `Rk_new(z)=Rk_old(z)+delta_Rk*b(z)`.

- C1: fit only nonnegative `delta_R0` (one parameter).
- C2: fit nonnegative `delta_R0, delta_R1, delta_R2` (three parameters).

For RC branches set `Ck_new=tau_k_old/Rk_new`, preserving each published time
constant at every query. Reject attempts to activate a zero-time-constant branch.
All increments have fixed exploratory bounds [0, 0.20] ohm. This broad search
box is not a manufacturer limit; report boundary contact as a limitation. Do not
increase it or add a new candidate after seeing results. No extra RC element.

With fixed time constants and open-loop measured current, voltage is affine in
these resistance increments. Obtain the ohmic basis directly as `I*b(z)` and
the two polarization bases by frozen-solver runs with a 0.01 ohm increment,
subtracting baseline and dividing by 0.01 ohm. Fit by bounded linear least
squares. Verify superposition against a direct frozen-solver candidate replay;
this is an acceleration of parameter estimation, not a second physical solver.

## Allocation and objective within used development evidence

Include every complete GITT pulse/rest pair whose baseline loaded-end nominal
SOC is below 0.20, selected from current integration, not voltage errors. Keep
each full pulse and following rest, including pre-20% samples in a crossing
pair. Other pairs supply full-record diagnostics, not fitting targets.

Give each selected pair equal total weight, split equally between its pulse and
rest. Within a phase use trapezoidal time weights normalized by that phase's
observed duration; do not bridge phase boundaries. This avoids a long rest or
denser sampling dominating the fit. Report ordinary sample/time metrics as well
as this declared fitting objective. Never discard an inconvenient sequence.

Fit each candidate to all selected pairs. Also leave one complete selected pair
out at a time, fit on the remaining pairs and predict the excluded pair with
continuous states from the full measured-current history. Do not fit to the
excluded pair's voltage or reset its states. These are development cross-checks
within an already-used record, not fresh independent assessment. Keep the
fitting-pair allocation fixed for all sensitivity scenarios.

## Identifiability and sensitivity

Report the weighted design singular values, column-normalized condition number,
column correlations, active bounds and leave-pair-out parameter ranges. Profile
each fitted parameter on 81 fixed values over its allowed interval plus its
optimum, reoptimizing other parameters. Report the grid-supported parameter band
within 1% of the optimum objective RMSE, explicitly as an objective-sensitivity
band, not a calibrated confidence interval. Do not use iid residual covariance
to imply uncertainty with strongly correlated samples and model discrepancy.

Repeat the basis and fit at assumed initial SOC=0.995, the already justified
exploratory sensitivity. Show both unchanged-primary-parameter transfer and a
conditional refit; do not select the origin by voltage fit. Keep the reference
fixed, so this is a coordinate/origin sensitivity, not independent reference
and SOC uncertainty. The previously unsupported SOC=1.005 is not clipped or
refitted. Reference and absolute-SOC uncertainty remain unresolved.

Check both candidates at 0.0625 s without refitting. Compare direct versus
affine predictions at 1e-8 V; use the existing proposed 0.1 mV time-step check.
Neither is an experimental accuracy requirement. Use analytic/synthetic tests
for sign, RC decay, preserved tau, superposition, complete-pair weights,
parameter recovery, rank deficiency and excluded-pair voltage isolation.

## Reporting and stop rule

Export every original GITT and used 1C timestamp with source lines, measured
values, candidate predictions and residuals. Report sample/time RMSE, bias and
maximum error, per sequence, direction, current, SOC and rest elapsed time.
Compare loaded-end error, finite-rest median and loaded-to-late-rest recovery;
finite rests are not established equilibrium OCV. Plot whole records, complete
sequences selected by SOC (near 0.1, 0.04 and the last pair), residuals and
parameter/objective sensitivity. Include all fits, including poor candidates.

A candidate is worth a future confirmation proposal only if leave-pair-out
phase-balanced RMSE improves by at least 20%, pulse and rest time RMSE each do
not worsen, low-SOC loaded-end maximum error improves by at least 20%, and the
worst absolute late-rest-median error increases by no more than 5 mV. These are
proposed development screens based on the observed load/recovery miss, not
application acceptance limits. Flag weak separation or unstable/bound-limited
parameters even if predictive screens pass; no parameter-identification claim
follows from lower RMSE alone. Prefer C1 if both pass; otherwise report C2's
additional complexity. No automatic adoption or fresh-data access follows.

If the fixed forms fail, finish the investigation and recommend a bounded next
step from residuals. Do not keep expanding the model until it fits. Device
requirements remain `requirement not configured`; voltage-limit decisions are
`insufficient evidence`; module validation is `awaiting suitable measurements`.
The module-current discrepancy and author `Q_sim_W` definition stay separate.

Freeze this procedure, source allocation, implementation and synthetic tests
before fitting. Save a reproducible command, new verification receipt and
decision report; do not rewrite previous manifests or their reports.
