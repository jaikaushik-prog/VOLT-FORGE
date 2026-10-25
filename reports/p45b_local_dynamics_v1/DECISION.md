# Local flexibility explains part of the mismatch, but time scales remain uncertain

**Do not adopt a new P45B model. Keep the published model and LG v2 frozen.**
Local resistance fits describe the already-opened low-SOC pulses much better
than the published baseline, but these fits use each pulse's own voltage. The
additional benefit from adjusting two recovery time scales is smaller and
depends strongly on the assumed SOC/reference origin. This investigation does
not identify a deployable SOC law or a uniquely established physical mechanism.

The bounded study is complete. It opened no new measurement family and made no
changes to the four-cell model, frontend, thermal capabilities or optimizer.
Experimental module validation remains **awaiting suitable measurements**.

## Frozen procedure and evidence

[Procedure](PROCEDURE.md), [source allocation](../../configs/ae_p45b_local_dynamics_v1.json),
implementation and **18 passing synthetic tests** were frozen in commit
`ebfbaf5` before the fits ran. No grid expansion or implementation correction
was needed. The completed release is [run_001](run_001/summary.json).

The source is Dickinson et al., About:Energy (2026),
[Molicel P45B public release](https://zenodo.org/records/19052626), CC BY 4.0.
Only saved, previously opened 25 degC GITT measurements and published discharge
parameters were used. Eleven whole pulse/rest pairs, indices 21-31, retain all
**36,897 samples**, source lines **61531-98427**, including the final long rest.
Selection came from the preceding nominal-SOC allocation, not this study's
voltage errors. Source rows, current polarity, temperatures and voltage values
are preserved in the new exports.

The record uses charge-positive current, nominal 4.5 Ah capacity and nominal
25 degC. Primary record-start assumptions are SOC=1, hysteresis=-1 and zero RC
voltages. Local pairs inherit the published model's continuously propagated RC
states. Those states are assumptions, not measured polarization. Each whole
pair then propagates continuously without a pulse-to-rest reset. Other pairs'
local fits are not connected into a full-run model.

The 1C record remains previously used contextual evidence; no prediction was
made from these local parameters because no global SOC transfer rule exists.
All **48 unused P45B members / 40 families**, the charge table and validation
workbook remain unopened. The reserved 3C family remains reserved; nine LG
characterization cells, 13 FreeTwinEV records and protected module outcomes
remain protected. [Verification](verification.json) checks the previous chain,
including 49 preceding artifacts and 112 protected LG artifacts.

## What was compared

| Description | Resistance and time scales | Interpretation |
| --- | --- | --- |
| B0 | Unchanged published, SOC-dependent model | Frozen continuous replay. |
| L0 | Published values at the pair's loaded-end SOC, held constant locally | Checks the local-constant approximation. |
| LR | Three bounded local resistance fits; published local time scales | Removes the previously imposed shared linear SOC dependence. |
| LRT | Three bounded local resistance fits at each point of the declared two-dimensional tau grid | Tests descriptive benefit from alternative recovery rates. |

All retain the frozen, time-varying reference/hysteresis voltage. The objective
gives each pair equal weight and its full pulse and rest equal weight; samples
within each phase receive trapezoidal time weights. LRT uses only multipliers
0.25, 0.5, 1, 2, 4, 8 and 16 with tau1 < tau2. Resistance bounds are exploratory,
not measured limits. Every grid point is reported, including poor ones.

LR has separate fitted parameters for every pair; LRT has still more local
flexibility. Therefore a smaller error here is an **in-sample diagnostic fit**,
not an improved prediction on unseen measurements. SOC-dependent resistance
within a pulse, reference uncertainty and recovery dynamics remain confounded.

## Observed errors

All values below are mV, prediction/description minus measurement. These are
the selected low-SOC pairs only, not whole-record or module accuracy.

| Primary description | Equal-pair/phase objective RMSE | Pooled sample RMSE | Pooled time RMSE | Sample bias | Maximum absolute error |
| --- | ---: | ---: | ---: | ---: | ---: |
| B0 | 73.001 | 48.190 | 34.009 | +4.205 | 333.367 |
| L0 | 73.147 | 48.329 | 34.062 | +3.972 | 333.367 |
| LR | 18.782 | 26.087 | 25.733 | -8.853 | 166.210 |
| LRT | 17.233 | 22.816 | 22.651 | -9.277 | 166.023 |

Pooled sample quantities weight each pair by sample count; time quantities
weight each pair's full-pair metrics by its duration, without adding intervals
between pairs. Exact per-pair full/pulse/rest RMSE, bias, maxima, loaded-end
errors and finite-rest errors are in
[primary_pairs.json](run_001/primary_pairs.json).

L0 remains close to B0 in aggregate, so using a constant local approximation
alone does not explain the improvement. Allowing local resistance amplitudes
greatly reduces many low-SOC load errors. Allowing the grid of time scales then
reduces the primary objective from 18.782 to 17.233 mV, about **8.2%**. This does
not establish that time scales are uniquely identified, nor that resistance
really follows the fitted pair-by-pair values.

The worst absolute loaded-end error is 333.358 mV for B0, 46.765 mV for LR and
52.619 mV for LRT: the extra time-scale flexibility does not improve every
quantity. Maximum errors around other timestamps still reach approximately
166 mV for both local fits. The worst absolute final-60-second rest median
error remains **41.555 mV** for all four descriptions. More flexible load
dynamics cannot automatically resolve the long-rest voltage level.

The [complete-pair plots](run_001/complete_pairs.png) show pairs nearest nominal
SOC 0.10, 0.04 and the final pair, chosen by the procedure. All eleven pairs
appear in [local diagnostics](run_001/local_diagnostics.png) and
[time-scale profiles](run_001/tau_profiles.png). Plots were visually inspected;
the final long rest and both current-transition sides remain present.

## Recovery evidence and origin sensitivity

Subtracting each trace's own final-60-second rest median gives a centered-rest
shape diagnostic. It removes a constant offset for this calculation, but the
finite-rest median is not asserted to be equilibrium OCV. It was not a separate
fitting objective.

| Pair / primary loaded SOC | LR centered-rest time RMSE | LRT centered-rest time RMSE | Primary LRT tau1 / tau2 (s) | LRT tau1 / tau2 with SOC origin -0.005 (s) |
| --- | ---: | ---: | ---: | ---: |
| 26 / 0.0989 | 8.33 | 10.40 | 1.03 / 13.42 | 8.20 / 13.45 |
| 29 / 0.0421 | 23.85 | 19.87 | 32.62 / 214.24 | 32.62 / 53.56 |
| 30 / 0.0251 | 24.10 | 10.93 | 32.62 / 428.47 | 32.62 / 53.56 |
| 31 / 0.0154 | 39.86 | 33.76 | 65.24 / 428.47 | 65.24 / 428.47 |

Rounded time constants come from the published local values multiplied by the
declared grid; they are not continuous optimum estimates. At pair 30 the
primary fit has a useful descriptive slow-recovery contribution, but its slow
time scale changes by a factor of eight under the linked SOC-origin sensitivity.
That sensitivity's centered-rest RMSE is **23.54 mV**, so the primary gain is
not stable to the reference/origin assumption. Pair 26's centered-rest shape
actually worsens despite a lower fitting objective.

At SOC origin -0.005 the equal-pair/phase objective is **65.052 mV (B0),
26.531 mV (LR), 25.866 mV (LRT)**. The incremental LRT benefit is only about
2.5%. The worst late-rest median error becomes **68.439 mV**. The origin was
not chosen by fit quality; reference and SOC shift together through the saved
replay. These are sensitivity scenarios, not independent uncertainty sources
or confidence bounds. Full results are in
[initial_soc_minus_0p005_pairs.json](run_001/initial_soc_minus_0p005_pairs.json).

## Identifiability and initial polarization

The primary three-resistance normalized condition numbers range from **8.31
to 146.31**. All those three-column problems have numerical rank three, but
rank alone does not identify physical mechanisms. At pair 21, the near-optimal
finite-grid slow-time-constant range spans approximately **10.3-656.7 s**.
Pairs 21-26 have wide/flat profiles for both time scales, often with an RC
resistance at its lower floor. A time constant attached to a negligible fitted
branch is particularly weak evidence. These conditional bands are reported
within 1% of objective RMSE; they are not confidence intervals.

At the last pair, primary LRT reaches the maximum allowed fast-tau multiplier
16 and the 0.20 ohm slow-resistance bound. The bounded search is retained as
declared. Contact with a chosen bound is a limitation, not a reason to expand
the search after seeing the data. No nonlinear global optimality is asserted.

For the selected local fits, the largest remaining memory fraction across the
preceding rest is about **0.01497**, conditional on holding the fitted tau
through that rest. Propagating each pair's local parameters through the entire
prior current history, without voltage calibration or refitting, changes the
within-pair voltage by at most **1.696 mV** (primary) or **1.139 mV** (shifted
origin). Pair 30's primary objective changes from 11.516 to 11.685 mV under this
initial-polarization sensitivity. This check does not explain the much larger
reference/origin sensitivity. Its past-SOC constant-parameter assumption is
unsupported, so it is neither a measured initial state nor a real-error bound.

## Interpretation and next engineering action

Confirmed observations are the local amplitude benefit, incomplete recovery
description, persistent finite-rest voltage offsets, broad/bound-limited
profiles and strong sensitivity of some fitted time scales to reference origin.
The mechanism behind them is unresolved. Possible contributions include a
different SOC dependence of resistance, uncertain nominal-SOC/reference
alignment, dynamics changing within a pulse and a finite rest still evolving.
This study does not separate those causes sufficiently to choose a global model.

Do not add a third RC or interpolate these local fits into a replacement table.
Before another deployable candidate, specify how its reference/origin will be
fixed from documented preparation and how its limited SOC parameterization will
be assessed on complete sequences. The existing opened data can support that
procedure design. Author processing/calibration information or suitable rested
reference evidence would help resolve the origin ambiguity; the present fits
cannot manufacture it. Preserve the unused measurements until that procedure
is frozen. Sustained-current transfer would still need a separate check.

The LG four-cell workflow stays usable within its documented scope. A P45B
local diagnostic does not resolve the module-current discrepancy. Module
validation still needs synchronized module/branch currents, voltage locations,
temperature/preparation history and calibration evidence, or suitable replacement
measurements. Device minimum voltage and allowed excursion duration remain
**requirement not configured**; design decisions requiring those limits remain
**insufficient evidence**. No lab outreach or automatic repair ranking occurred.

For a student: letting every pulse have its own resistances makes its curve
easier to fit, but that does not tell us what an unseen load will do. Changing
the assumed charge origin also changes the recovery speed inferred from the
same measurements. The next physics task is to settle that reference/state
handling before fitting a portable model; backend integration can continue
without pretending those unknowns are solved.

## Checks and reproduction

**135 focused tests pass**, including the previous 117 plus 18 new synthetic
checks ([receipt](pytest.xml)). The independent verifier checks every selected
pair in both scenarios, original measured channels, all grid fits' box-constrained
optimality conditions, source hashes, equations and metrics. The maximum
independent equation closure is **3.997e-15 V**. Synthetic checks include exact
pulse/rest solutions, charge/discharge sign, the existing electrical kernel,
time-subdivision invariance, known-grid recovery, complete-phase weighting,
flat/rank-deficient cases, source-lock failure and independent metric checks.
These establish software consistency, not experimental accuracy.

Run from the repository root with the existing environment and downloaded
hash-locked source files. Choose fresh output names; existing outputs are never
overwritten. The study takes approximately a minute on the current machine;
verification also checks the preceding evidence chain.

```powershell
$env:OPENBLAS_NUM_THREADS = '1'
$env:OMP_NUM_THREADS = '1'
& C:\Users\DELL\anaconda3\python.exe scripts\ae_p45b_local_dynamics.py --out tmp/p45b_local_dynamics_trial
& C:\Users\DELL\anaconda3\python.exe -m pytest tests/test_ae_p45b_local_dynamics.py tests/test_ae_p45b_identifiability.py tests/test_p45b_identifiability_verifier.py tests/test_ae_p45b_gitt_replay.py tests/test_ae_p45b_low_soc.py tests/test_ae_p45b_author_comparison.py tests/test_ae_p45b_reproduction.py tests/test_ae_p45b_equations.py tests/test_ae_p45b_intake.py -q
& C:\Users\DELL\anaconda3\python.exe scripts\verify_p45b_local_dynamics.py --run tmp/p45b_local_dynamics_trial --out tmp/p45b_local_dynamics_trial_verification.json
```

Verify the committed release directly:

```powershell
& C:\Users\DELL\anaconda3\python.exe scripts\verify_p45b_local_dynamics.py --tests reports/p45b_local_dynamics_v1/pytest.xml --out tmp/p45b_local_dynamics_release_check.json
```

Each CSV.gz preserves all selected original samples, source lines and phases,
adding reference, nominal SOC, descriptions, weights and the initial-state
sensitivity. Pair JSON files include every grid point, conditional profiles,
metrics and assumptions; [manifest.json](run_001/manifest.json) hashes all run
artifacts. No fitted values are installed into a product component library.
