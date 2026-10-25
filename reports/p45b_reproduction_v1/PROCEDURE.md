# Frozen procedure: one P45B discharge reproduction

Declared before numerical parameter rows or this development record were opened.
This is a reproduction using published fitted parameters, not new identification
or an independent validation of those parameters. No parameter selection or
calibration against measured voltage is permitted in this stage.

## Access allocation

Release only the base `Molicel_INR-21700-P45B_ECM.csv` parameter table and the
complete `MOLICEL_P45B_025degC_1C_Dch.csv` development family in the verified source
archive. Use only the four experimental columns in that record. Do not interpret
its six author-output fields. Preserve original bytes, hashes and source lines.
The other 50 archive members, charge-optimized table and validation workbook stay
unopened. The old allocation remains an immutable intake record; this procedure
is the versioned allocation change for this single family. All protected LG and
FreeTwinEV outcomes remain protected.

## Operating case and assumptions

One characterized Molicel P45B at nominal controlled surface temperature 25 degC,
with the measured current as open-loop input. Use the published base parameters
without alteration. Nominal capacity 4.5 Ah, initial SOC=1, hysteresis=-1,
polarization voltages=0, taken from the paper's discharge-reproduction convention.
Initialize at the first recorded timestamp, without moving the origin to improve
agreement. No voltage offset, initial-SOC fit, current rescaling or time shift.
Temperature remains constant 25 degC; retain recorded temperature as evidence
and flag deviations over 1.5 degC. No thermal model or temperature correction.
The loaded pOCV branches are used as published, not relabelled as measured
long-rest equilibrium OCV. Starting-state assumptions and fitted values remain
distinct from measured channels.

## Table and numerical rules

Validate finite numbers, unique (temperature,SOC) keys, increasing SOC after
explicitly sorting lookup knots only, positive references, nonnegative gamma and
resistances, and positive capacitances for active RC pairs. Preserve row references.
Audit Q_Ah versus nominal-capacity SOC; Q_Ah is metadata and will not replace
explicit 4.5 Ah capacity or be used as an outcome-derived state correction.
Audit grid ranges, monotonic reference branches and RC time-constant ordering;
report violations instead of rearranging states or repairing values.

This bounded implementation supports **only an exact 25 degC table slice** and
piecewise linear interpolation of each published electrical parameter in SOC.
Do not invent a temperature-interpolation law in this first case. Retain all
table temperatures in the audit; numerical use of other temperatures is unsupported.

Use the already tested constant-parameter exponential RC/hysteresis update, with
parameters queried at each substep's left SOC. Check reference support at both
ends. Advance SOC with charge-positive source current and 3600 s/h conversion.
Default current is left-held on [t_i,t_(i+1)); terminal voltage at t_i uses I_i
immediately. Output at every measured timestamp; no voltage-driven alignment.
Maximum substep 0.25 s, subdividing intervals equally. Do not clip SOC or silently
extend references. A gap greater than max(10 s, 10 times median positive sample
interval) stops further simulation, without restarting or deleting observations.

Predeclared runs (no winner selected from these diagnostics):

1. **primary**: left-held current, 0.25 s maximum substep, stop outside reference.
2. **fine_step**: same assumptions, 0.0625 s maximum substep. Report max prediction
   difference on common timestamps. 0.1 mV is a proposed numerical convergence
   check, not experimental accuracy or a device requirement. If exceeded, report
   numerical convergence outstanding rather than changing the accepted result.
3. **linear_current_sensitivity**: piecewise linear current, evaluated at substep
   midpoint (exact SOC integral for linear current), otherwise primary settings.
   This probes acquisition/integration convention uncertainty, not model fitting.
4. **nearest_extension_sensitivity**: primary settings but opt-in nearest-boundary
   lookup outside SOC support, with every affected output/interval flagged. SOC
   itself remains unchanged. Never substitute this run for supported predictions.

All runs stop on nonfinite/undefined inputs, invalid parameters or acquisition
gaps. Retain the whole supplied record and explicitly mark unpredicted rows. For
diagnosis, calculate across the full mathematically defined interval, without
truncating at voltage limits; mark predicted and measured crossings of the paper's
2.5 V discharge protocol cutoff. Also report the common prefix ending before the
first measured or predicted cutoff crossing. This is a protocol diagnostic,
**not** an application acceptance requirement. No illustrative 3.50 V/25 mV default.

## Metrics, diagnostics and interpretation

Residual = predicted minus measured voltage. Report sample RMSE/bias/max absolute
error and trapezoidal time-weighted RMSE/bias. Use only adjacent, predicted samples
within a group for time weighting; never bridge excluded samples or stopped gaps.
Give row count and covered duration for each metric, with unavailable time metrics
if fewer than two adjacent samples exist. Use standard squared-residual RMSE.

Report by SOC (<0, 0-0.2, 0.2-0.8, 0.8-1, >1), source current direction
(rest abs(I)<=0.05 A), magnitude (0-0.5, 0.5-3, 3-5, >5 A), temperature deviation,
and time since a >=0.1 A sample transition (0-10, 10-60, >60 s). Treat the first
sample as a sequence start. These are descriptive bins, not new support claims.
Keep complete-record plots of voltage/current/temperature and residuals with
source member/hash/row references. Publish derived comparison data with licence
and attribution; original downloads stay local and unchanged.

State sample timing, gap count, current range/direction and contiguous duration,
temperature range, SOC and table support, protocol crossings and excluded rows.
No calibrated confidence intervals or parameter-identifiability claims can be
derived from reusing a fitted table on a single constant-current record. Report
parameter ranges and conditional numerical/sampling sensitivity instead. Raw
author simulation channels and workbook errors remain unopened, so this is an
equation-based reproduction comparison against measurements, not a claim of
bitwise agreement with the authors' solver or their headline metric.

Keep the four-cell LG backend unchanged. These results cannot establish P45B
module current-sharing accuracy, branch waveform coverage or a repair benefit.
Application voltage/duration requirements remain unset. Stop once this declared
development comparison, tests, plots and preservation receipt are complete;
additional families require a subsequent declared procedure.
