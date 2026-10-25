# Low-SOC resistance revisions improve some errors but are not adopted

**Keep the published P45B model and LG v2 frozen.** Two predeclared resistance
revisions lowered aggregate GITT prediction error, but neither passed the
complete-sequence development screen. The more flexible revision worsened
relaxation error and increased RMSE on the already-used sustained 1C record.
This is evidence against adopting these particular revisions, not proof that
resistance or the existing two-RC structure cannot represent the cell.

The next step is another bounded cell-model investigation. Experimental module
validation remains **awaiting suitable measurements**. The four-cell editor,
frontend redesign, thermal capabilities and optimizer are unchanged.

## Procedure, evidence and preservation

The [procedure](PROCEDURE.md) was committed in `4fb44ac`, the initial code and
14 synthetic tests in `4c1353e`, and a JSON-only export correction plus a 15th
test in `bd84c6c`. The [correction record](IMPLEMENTATION_CORRECTION.md) explains
the incomplete `run_001`, retained without deletion. The completed release is
**[run_002](run_002/summary.json)**. Its physical equations, fitting allocation,
bounds and decision criteria follow the original procedure unchanged.

Source: Dickinson, Zor, Doyle, Pilling, Lukow, O'Regan and White, About:Energy
(2026), [Molicel P45B public release](https://zenodo.org/records/19052626),
CC BY 4.0. Derived exports retain measured channels and original source-line
references, adding predictions and diagnostics. The original downloads and
published parameter table are unchanged. This work reuses previously opened
characterization evidence that may also have contributed to the authors' model.

| Evidence/input | Role in this investigation |
| --- | --- |
| Complete 25 degC GITT discharge, 98,426 samples / 68,515.68 s | Used development evidence; all timestamps retained. |
| Eleven complete pulse/rest pairs, indices 21–31, source lines 61531–98427 | Fitting and leave-one-complete-pair-out diagnostics, selected by integrated nominal SOC below 0.20. |
| Complete 25 degC 1C discharge, 3,433 samples | Previously used record, excluded from fitting and selection; transfer diagnostic, not fresh assessment. |
| Published reference, capacity 4.5 Ah, hysteresis and time constants | Held fixed; no reference offset, capacity fit, current rescaling or timing fit. |
| Initial SOC=1, hysteresis=-1, zero RC voltages | Explicit reproduction assumptions; no pulse/rest resets. |
| Nominal 25 degC | Isothermal assumption; the constant recorded temperature column does not establish thermal dynamics. |
| Complete 25 degC 3C discharge family | Reserved using filename metadata only, still unopened. Future use would test higher-current transfer. |

All **48 other P45B members / 40 families**, the charge-optimized table and
validation workbook remain numerically unopened. Nine LG characterization cells,
13 FreeTwinEV records and protected module outcomes remain unused/protected.
The [source lock](../../configs/ae_p45b_identifiability_v1.json) and
[verification receipt](verification.json) retain the evidence chain. The former
root README is preserved in `previous/README.md` before the living index update.

## The two implemented revisions

Inside existing reference support, define `b(z)=max(0,(0.20-z)/0.20)` and
`Rk_new(z)=Rk_published(z)+delta_Rk*b(z)`. This linear low-SOC shape is a proposed
parameterization, not a measured law. Each increment is constrained to
[0, 0.20] ohm. RC capacitance is adjusted to preserve the published time constant
at each SOC query. No additional circuit element or temperature law is added.

- **C1:** one allowed increment, R0. Fit: **34.506 mOhm** times `b(z)`.
- **C2:** three allowed increments, R0/R1/R2. Fit: **0 / 0 / 79.357 mOhm** times
  `b(z)`. The two zero increments are active lower bounds, not measurements that
  the underlying physical resistances are zero.

The frozen integrator remains the sole physical solver. With fixed time
constants and measured current, voltage is affine in these increments; verified
basis responses allow bounded linear fitting without repeated nonlinear search.
Each selected pair has equal total objective weight, split equally between its
complete pulse and rest; each phase is internally time-weighted. No random
timestamp splitting or deletion of long rests is used.

## Full-record results

Errors are prediction minus measurement, in mV. These are development results
under fixed assumptions, not independent module accuracy or battery improvement.

| GITT model | Sample RMSE | Time RMSE | Sample bias | Time bias | Maximum absolute |
| --- | ---: | ---: | ---: | ---: | ---: |
| B0 published baseline | 29.884 | 22.190 | +0.852 | -3.298 | 333.367 |
| C1 R0 revision | 25.614 | 20.610 | -1.581 | -3.992 | 290.095 |
| C2 R0/R1/R2 revision | 24.415 | 19.870 | -4.369 | -4.900 | 170.151 |

C2's whole-record sample RMSE is about 18.3% lower, but that average masks
errors of opposite signs at different SOCs. Near nominal SOC 0.099, its extra
load drop overcorrects a sequence the baseline already described much better.
Near SOC 0.042 it still underestimates the drop and recovery. See the
[complete selected sequences](run_002/complete_sequences.png), chosen by SOC
rather than by prediction error, and [whole GITT trace](run_002/gitt_comparison.png).

| Previously used sustained 1C record | Sample RMSE | Time RMSE | Sample bias | Time bias | Maximum absolute |
| --- | ---: | ---: | ---: | ---: | ---: |
| B0 | 35.860 | 35.034 | +19.071 | +18.910 | 336.039 |
| C1 | 29.472 | 29.062 | +9.386 | +9.280 | 216.614 |
| C2 | 43.683 | 43.652 | +0.543 | +0.499 | 164.916 |

C2 reduces the worst error but **increases 1C sample RMSE by about 21.8%**.
Its near-zero mean bias reflects cancellation, not uniform accuracy. This used
record was excluded from fitting/selection and supplies a caution about protocol
transfer; it is not a new independent test. The
[1C comparison](diagnostics/used_1C_comparison.png) shows the overcorrection before
the final voltage fall.

## Complete-pair cross-checks and screening decision

Each excluded pair's voltage was removed from fitting. Its current history was
still propagated continuously; there was no calibrated state reset. All these
observations were previously opened, so this is development cross-checking.

| Low-SOC diagnostic | B0 | C1, excluded pairs | C2, excluded pairs |
| --- | ---: | ---: | ---: |
| Equal-pair, equal-phase objective RMSE (mV) | 73.001 | 59.989 | 54.607 |
| Pulse time RMSE (mV) | 105.331 | 85.267 | 74.463 |
| Rest time RMSE (mV) | 28.032 | 28.032 | 28.344 |
| Rest sample RMSE (mV) | 30.395 | 30.395 | 33.509 |
| Maximum loaded-end absolute error (mV) | 333.358 | 233.418 | 182.329 |
| Maximum late-rest median absolute error (mV) | 41.555 | 41.555 | 41.555 |

**C1 fails the predeclared 20% objective-improvement screen.** Its excluded-pair
objective improves about 17.8%. The machine-readable strict no-worsening rest
flag is also false, but the increase is only approximately **4e-8 mV** in time
RMSE: effectively unchanged, not evidence of a meaningful relaxation degradation.
The objective failure and remaining recovery error are the substantive issues.

**C2 improves that objective about 25.2% but fails the rest no-worsening screen.**
The rest time RMSE rises by 0.312 mV and rest sample RMSE by 3.113 mV. No
statistical significance or calibrated uncertainty is asserted for these changes.
The fixed criterion is not relaxed after the result; the poor sustained-record
transfer and large SOC-dependent residuals provide additional reasons not to
adopt the revision. The 20%/5 mV screens are proposed development criteria, not
manufacturer, competition or application acceptance limits.

The [per-pair errors](diagnostics/pair_errors.png) preserve both fit and excluded
pair results. At the previously highlighted nominal SOC 0.0421 pair:

| Quantity | Measured | B0 | C1 fitted | C2 fitted |
| --- | ---: | ---: | ---: | ---: |
| Loaded-to-late-rest recovery (mV) | 461.038 | 114.117 | 236.708 | 296.010 |
| Loaded voltage error (mV) | — | +333.358 | +210.767 | +151.465 |
| Late-rest median error (mV) | — | -13.563 | -13.563 | -13.563 |

Extra resistance helps this particular pulse, but the fixed time constants still
recover too quickly and the imposed SOC shape overcorrects other pulses.
Finite-rest medians and slopes are not established equilibrium OCV.

## Conditional identifiability and starting-state sensitivity

The three-column weighted sensitivity matrix has rank 3 and normalized condition
number **17.62**, so this numerical problem is not rank-deficient. However, the
R0/R1 column cosine is **0.9875**, showing strongly similar voltage effects for
this protocol. A full-rank fit does not identify unique physical mechanisms in
the presence of model discrepancy, uncertain origin and correlated observations.
Time constants were held fixed; their identifiability was not established here.

| Quantity | C1 delta R0 | C2 delta R2 |
| --- | ---: | ---: |
| Primary fit (mOhm) | 34.506 | 79.357 |
| Leave-pair-out range (mOhm) | 28.130–38.930 | 65.892–89.467 |
| Grid-supported band within 1% of objective RMSE (mOhm) | 30–40 | 65–87.5 |
| Conditional refit with initial SOC=0.995 (mOhm) | 24.580 | 58.937 |

C2's corresponding profile bands are 0–5 mOhm for delta R0 and 0–7.5 mOhm
for delta R1, with both optima at zero. These are finite-grid objective-sensitivity
bands conditional on the chosen reference, capacity, time constants and basis;
**they are not confidence intervals**. See [parameter profiles](run_002/parameter_profiles.png).

Changing the assumed initial SOC by -0.005 while holding the primary fitted
increments fixed shifts predictions by up to **49.799 mV (C1)** and
**50.903 mV (C2)**. Conditional refits change the increments materially, by about
29% and 26%, respectively. No origin was selected for better voltage agreement.
The reference stays fixed, so this is one linked coordinate/origin sensitivity,
not an independent distribution for SOC plus reference uncertainty. The earlier
unsupported SOC=1.005 case remains unsupported. No calibrated error bounds result.

## What has been checked and what remains unsupported

The **117 focused tests pass** ([receipt](pytest_02.xml)), including the 99
earlier P45B checks. New tests cover physical sign, unchanged RC time constants,
analytic rest decay, exact superposition, known-parameter recovery, complete-pair
weighting, exclusion of held-pair voltage, rank deficiency, parameter bounds and
independent optimality/metric checks. The export regression is included.

Direct frozen-solver predictions agree with the affine fits within
**4.0e-15 V**. Reducing maximum step from 0.25 to 0.0625 s changes voltage by at
most **0.03961 mV (C1)** and **0.06477 mV (C2)**, both below the previously
proposed 0.1 mV numerical check. The independent verifier checks constrained-fit
optimality, source alignment, SOC integration, weights, excluded-pair predictions,
voltage decomposition, recovery metrics and the previous preservation chain.
These establish software consistency, not experimental accuracy.

Neither fitted artifact is promoted to the component library or four-cell solver.
The supported claim is a **conditional development comparison on one nominal
25 degC P45B discharge GITT record**, plus a previously used 1C transfer check.
Arbitrary waveforms, charge, other temperatures/cells and four-cell module
current sharing remain unsupported by this work. Nominal cell SOC is not a
newly established absolute charge origin. The fixed v2 LG module's limitations,
including the 14.55 A case and unresolved current discrepancy, are unchanged.

Device minimum voltage and excursion duration remain **requirement not configured**;
voltage-limit design decisions remain **insufficient evidence**. Neither the
illustrative 3.50 V alarm nor 25 mV budget is reinstated. No module current was
rescaled, no lab request was sent, and no thermal or repair-ranking claim is made.

## Next engineering action

Use the already-opened complete sequences to separate two remaining issues:
the imposed linear SOC dependence and the fixed relaxation time scales. Declare
a bounded local resistance/time-constant identifiability study before fitting
another revision, using both load and full recovery. Compare sensitivity to the
reference/origin assumptions; do not add a third RC element or freely tune every
SOC point merely to reduce residuals. A future candidate must improve both phases
and show credible protocol transfer before consuming reserved confirmation data.

This cell-model work can continue with available online measurements. Separate
experimental module validation still needs synchronized branch currents,
defined voltage locations, preparation and calibration evidence that resolve
the existing current-source disagreement, or suitable replacement measurements.
The reserved 3C single-cell family cannot supply that module evidence.

For a student: we made two small changes and checked what each fixed and broke.
One average error became smaller while other predictions became worse. Keeping
the previous model frozen is therefore the defensible decision. The next task
is to identify how voltage recovery changes with charge level before connecting
a revised P45B model to the product.

## Reproduce

Use the existing pinned Python environment and local source downloads required
by the hash chain. Run from the repository root. Choose fresh output paths;
never overwrite release artifacts or historical test receipts.

```powershell
$env:OPENBLAS_NUM_THREADS = '1'
$env:OMP_NUM_THREADS = '1'
& C:\Users\DELL\anaconda3\python.exe scripts\ae_p45b_identifiability.py --out tmp/p45b_identifiability_trial
& C:\Users\DELL\anaconda3\python.exe scripts\plot_p45b_identifiability.py --run tmp/p45b_identifiability_trial --out tmp/p45b_identifiability_plots
& C:\Users\DELL\anaconda3\python.exe -m pytest tests/test_ae_p45b_identifiability.py tests/test_p45b_identifiability_verifier.py tests/test_ae_p45b_gitt_replay.py tests/test_ae_p45b_low_soc.py tests/test_ae_p45b_author_comparison.py tests/test_ae_p45b_reproduction.py tests/test_ae_p45b_equations.py tests/test_ae_p45b_intake.py -q
& C:\Users\DELL\anaconda3\python.exe scripts\verify_p45b_identifiability.py --run tmp/p45b_identifiability_trial --out tmp/p45b_identifiability_verification.json
```

To verify the checked-in completed release directly:

```powershell
& C:\Users\DELL\anaconda3\python.exe scripts\verify_p45b_identifiability.py --tests reports/p45b_identifiability_v1/pytest_02.xml --out tmp/p45b_identifiability_release_check.json
```

`summary.json` contains full/grouped metrics, parameter profiles, fold parameters,
screening outcomes and sensitivity results. CSV.gz files preserve every timestamp
and source line; `.npz` files retain the basis responses and fitting weights for
independent recomputation. These are versioned experimental candidate results,
not replacement parameters for the frozen model.
