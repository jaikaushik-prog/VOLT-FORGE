# VOLT-FORGE v2 model-improvement decision

24 October 2026. **Select C2: a calibration-rest voltage reference plus one
constant-parameter RC model.** It is a substantial improvement, including on
three additional characterized cells. It does **not** yet meet the proposed
voltage-decision error budget. Continue one focused reference/initial-state
iteration and obtain additional measurements; experimental module validation
remains blocked by the separate current-reference discrepancy.

## 1. What improved

The comparison below uses identical evaluation rows and the v1 **method**
recalibrated using the same permitted v2 calibration cycles. It is not a
comparison of different sample populations. Actual sealed v1 outputs are
preserved and separately reproduced to within 1e-11 V.

| Fresh characterized cell | Baseline sample / time RMSE [mV] | Selected C2 sample / time RMSE [mV] | C2 bias [mV] | C2 maximum [mV] |
|---|---:|---:|---:|---:|
| P2 | 20.74 / 26.12 | 9.00 / 9.69 | -1.66 | 40.95 |
| P5 | 20.93 / 26.36 | 8.87 / 9.54 | -1.70 | 35.39 |
| P8 | 22.00 / 27.79 | 10.77 / 11.24 | -0.93 | 44.65 |

These are the prespecified primary domain: SOC proxy 0.2-0.8, rest/discharge
0-4.9 A, measured surface 22-28 C in the nominal-23 C protocol. A -0.01 A lower
mask tolerance treats tiny zero-current noise as rest. Across fresh cells,
macro-average sample RMSE falls **21.22 to 9.55 mV (55.0%)** and time-weighted
RMSE **26.75 to 10.16 mV (62.0%)**. Maximum error across these cells falls from
149.94 to 44.65 mV. These improvements do not establish an engineering pass.

Long rests must not hide load errors. Within the primary domain, the 4.85 A
discharge-only sample RMSE falls from **78.87/79.76/85.10 mV** to
**13.82/12.78/13.41 mV** for P2/P5/P8. Its maxima remain
30.31/25.61/31.82 mV. See [load-only comparisons](reports/improvement_v2/LOAD_ERRORS.md).
Full evaluation records, including lower SOC and high-current multisines, have
C2 maxima **68.33/63.94/96.94 mV**; primary-domain numbers must not be generalized
to those conditions.

All baseline/candidate results, sample/time RMSE, bias, maxima, sequence and
SOC/current/temperature/transition-time bins are in the
[results report](reports/improvement_v2/RESULTS.md) and its linked JSON/CSVs.
Figures retain source rows and show complete records, discharge details and
continuous pulse/rest/multisine predictions.

## 2. Which model was selected, and why

The [plan](MODEL_IMPROVEMENT_PLAN.md) and
[machine-readable procedure](configs/model_improvement_v2.json) were frozen
before fitting. Exactly three revisions were evaluated:

| Revision | Change | Development primary sample / time RMSE [mV] |
|---|---|---:|
| Baseline method | C/20 loaded curve + linear rest correction; HPPC-only constant R | 21.07 / 26.27 |
| C1 | Monotone PCHIP through permitted long-rest anchors; constant R fitted over expanded protocol | 15.26 / 16.56 |
| **C2** | Same reference plus one positive R0/R1/tau polarization model | **10.00 / 10.57** |
| C3 | Same RC model, R0/R1 linear over three SOC knots; shared tau | 10.19 / 10.84 |

C2 gives materially better development errors than C1. C3 adds four dynamic
coefficients and does not improve the prespecified score. The selection rule
required >=20% improvement in both RMSE weightings, no increase in maximum error,
interior parameters and conditional identifiability, then selected the simplest
eligible model within 10% of the best combined score. No fresh assessment result
was used to change this decision.

The reference is **rested voltage, not proven equilibrium OCV**. Calibration
anchors are the last 30 s of step 11 in cycles 1/3/5/7/9 plus the initial
cycle-1 rest. C/20 supplies observed capacity; initial SOC is assumed 1.
Reference values outside the anchor domain are unsupported rather than silently
extended. This excludes 3,689 calibration samples for P7 in the final cycle's
low-SOC pulse/MS tail; counts are saved for every fit. All fresh evaluation
rows have reference support, but only the prespecified subset is in the primary
operating domain.

Candidate fitting uses the 4.85 A approximately six-minute discharges, their
long rests, HPPC and multisine/rest sequences. Each calibration cycle/phase has
equal objective weight, with time-quadrature weights within phases. The baseline
retains its HPPC-only fitting rule. Thus the improvement includes better
excitation coverage and reference treatment as well as dynamics; it is not an
isolated estimate of the benefit of adding one RC.

P7's selected R0/R1/tau are **24.48 mOhm / 26.16 mOhm / 62.50 s**.
Leaving one calibration cycle out gives R0 24.32-24.66 mOhm,
R1 24.91-27.37 mOhm, tau 54.20-72.08 s. Its normalized sensitivity condition is
4.16; 5%-SSE tau-profile support is 54.20-72.08 s. Fresh-cell estimates are
interior and pass the same screen. These are conditional identifiability and
stability diagnostics with reference anchors held fixed, **not** confidence
intervals covering instrument, SOC, thermal or model-form uncertainty. Tau is
searched on a declared 41-point logarithmic grid.

## 3. Evidence and operating case

| Category | Scope and limits |
|---|---|
| Intended application | P7/P17/P19/P13 LG M50T NMC, 1s4p same-side ladder, nominal 1 mOhm per segment on each rail; 14.55 A for 360 s after rest, starting SOC proxies 0.3-0.8, nominal 23 C ambient. Outputs: terminal/cell voltage, branch current, SOC and voltage-alarm proximity. Physical contacts, equilibration and initial state need confirmation. |
| Measurements available | Single-cell C/20 and nine complete discharge/rest/HPPC/MS cycles. About 4.85 A for 360 s; other pulse/charge/multisine amplitudes and durations differ. Module tests exist, but their current references conflict. |
| Fitting | Complete source cycles 1/3/5/7/9 for each cell; expanded current protocol for candidates. High current peaks are short; their existence does not validate arbitrary sustained loads. Exact coverage and contiguous dwell spans are in `calibration_coverage.json`. |
| Development evidence | P7/P4/P10/P13/P16/P17/P19, evaluation cycles 2/4/6/8. These cells and v1 assessment are already-used evidence. |
| Fresh assessment | P2/P5/P8, cycles 2/4/6/8, after their own permitted calibration cycles and C/20 characterization. Same rig/protocol, not zero-shot unknown-cell prediction and not independent module validation. |
| Unsupported transfer | Different temperatures or thermal histories; aged/different chemistry; arbitrary sustained high-current waveforms; unmeasured contacts/initial imbalance; independent module current/voltage accuracy; design or repair recommendations. |

The narrower deliverable is explicitly **single-cell voltage reconstruction on
the recorded protocol**. The 14.55 A module requirement has not been reduced.
Equal sharing would require 3.6375 A per cell; v1's 2.66 A discharge fitting was
inadequate. V2 adds relevant 4.85 A duration evidence, but measured 3.64 A
steady-load validation is still missing. The actual calibration rows contain
only two samples per cell in the 3.4-3.9 A band, spanning about 0.1 s. The
4.85 A plateau spans about 359 s between its first and last included samples;
contiguous excursions above 4.9 A last at most about 9.9 s. These are observed
dwell spans, not additional imposed test schedules. See the
[fitting coverage](reports/improvement_v2/calibration_coverage.json).

Across these cells, actual candidate fitting currents span approximately
-6.73 to +19.36 A, and recorded surface temperatures span 22.06-28.69 C.
P8 reaches 28.69 C during calibration; the prespecified primary assessment
mask remains 22-28 C, with full-record metrics reported separately. The nominal
23 C characterization is neither isothermal nor evidence for a broad temperature
law. High-current fitting samples do not establish sustained-current accuracy.

Software coupling at 14.55 A, equal initial SOC and the stated rails gives a
maximum branch current about **4.67 A**, within the measured 4.85 A plateau's
amplitude. With assumed SOCs **0.72/0.70/0.68/0.70**, the P7 branch reaches
**5.35 A**. Short higher-current multisines do not establish six-minute accuracy
there. Branch coverage depends on initialization; module-average current is
insufficient to declare the application supported.

The [coupling records](reports/improvement_v2/software_coupling/results.json)
and [imbalance case](reports/improvement_v2/software_coupling/initial_soc_imbalance.json)
are **synthetic software verification**, not measurements. Maximum KCL residual
is about 1.8e-15 A; total coulomb-accounting residual below 8e-11 A s.
Reducing the step from 1 s to 0.25 s changes terminal voltage by under 0.006 mV
in the equal-initial-SOC cases. This checks numerical consistency, not physical
accuracy. No temperature prediction is attached to these simulations.

## 4. Error budget, diagnosis and remaining limitations

Before fitting, the plan proposed sample/time RMSE <=10 mV, |bias| <=5 mV and
maximum error <=25 mV. A **proposed** 50 mV guard around a **proposed 3.50 V
operational alarm** allocates 25 mV to model error, 10 mV to measurement/reference,
10 mV to initialization and 5 mV to temperature transfer. These are research
decision criteria, not manufacturer limits or established application safety
requirements. The latter three allocations remain unverified.

**None of the fresh cells meets the complete proposed model budget.** Each
exceeds the maximum-error allowance; P8 also exceeds both RMSE limits. Within
0.10 V of the alarm, selected-model primary sample RMSE is 17.3-18.3 mV, with
positive bias about 10.0-14.9 mV. At the unguarded 3.50 V threshold, there are
11/8/4 samples where P2/P5/P8 are predicted above the alarm but measured below it.
No guarded false clearances were observed with the proposed 50 mV band, but
correlated samples and an unverified uncertainty budget cannot certify that
rule or establish a rare-event rate.

Observed v1 patterns were a persistent low-SOC reference bias, errors growing
during sustained discharge, and residual relaxation after current transitions.
Timestamp/sign tests, independent analytical response tests, actual v1 prediction
reproduction and consistent source-row mappings found no implementation error
that explains these patterns. Left/right versus trapezoidal SOC integration
changes P7 SOC by less than 0.000268; raw timestamp issues are not a sufficient
explanation. V2 bin metrics explicitly avoid integrating across excluded samples
or cycle gaps.

Reference sparsity and missing dynamics are supported explanations of error
structure, not uniquely identified electrochemical causes. Some low-SOC errors
remain or worsen: the rest PCHIP misses curvature between anchors near SOC 0.2.
P7's full cycle-8 plot shows a persistent negative bias below the primary domain.
All full-record errors are retained; a hard SOC-domain boundary does not imply
a physical accuracy discontinuity just across it.

Declared sensitivity tests are substantial. For P7, +/-0.02 initial SOC changes
predictions by up to about **32 mV** and increases primary RMSE from 9.05 mV to
18.91-21.09 mV. +/-1% capacity changes predictions by up to 12.6 mV;
right-endpoint RC integration changes them by about 2.1 mV. Replacing the rest
reference by the already-declared loaded/rest reference changes predictions by
up to 49.2 mV (up to 57.7 mV on P8). That sensitivity happens to improve some
RMS scores; it was **not promoted to a fourth candidate or selected after fresh
assessment**. It is evidence for a future preregistered reference investigation.

The SOC coordinate and reference are jointly conditional on initial-SOC and
capacity conventions; absolute SOC is not independently identified. Starting
RC polarization at zero after the preceding rest is also an assumption, tested
with +/-5 mV initial-polarization perturbations. Source temperature correlates
with load, elapsed time and SOC; its residual correlation cannot identify a
temperature law. No 10-40 C law or core-temperature model was inferred.

## 5. Evaluation integrity, module blocker and next action

The [input lock](configs/model_improvement_v2.lock.json) inventories 12 previously
uninspected NMC cells by metadata; P2/P5/P8 were allocated by identifiers before
their voltage outcomes were examined. The remaining nine are unconsumed
characterization evidence. Complete cycles, not random timestamps, are split.
Compressed MATLAB voltage vectors must be decoded as vectors; disallowed voltage
and temperature entries are immediately masked before any calibration/reference
operation. Tests verify that held values cannot affect those operations.

The [procedure seal](reports/improvement_v2/procedure_seal.json) was written at
17:47:15 UTC, before fresh-cell calibration. The
[fresh-model seal](reports/improvement_v2/fresh_model_seal.json) was written at
17:50:06 UTC before assessment scoring at 17:50:30 UTC. Parameters, procedure and
selection were not changed afterward. All 51 protected original/v1 artifacts
and the original archive hash remain unchanged. Reserved module **outcomes**
were not examined, scored or used for decisions.

A new [archive structural review](reports/improvement_v2/diagnosis/archive_metadata_evidence.json)
checked all 194 member names and variable/workbook headers for overlooked
processing evidence. The archive has 140 MAT and 54 XLSX files, no separately
packaged scripts or schedules, no hidden worksheets or embedded/external macro
parts. Worksheets are visible `Global_Info` and `Data`; defined names only set
print titles. MAT headers expose measurement/table variables, not a separate
coefficient/script artifact. The MCOS workspace is serialization, not recovered
processing code. This review did not inspect final module signal outcomes and
does not prove no undocumented information exists elsewhere.

The module discrepancy is therefore **unresolved**. Both uncertain current
sources remain untouched. Exact external evidence remains: per-run Hall
conversion scripts/coefficients and sensor assignments; cycler measured-current
range/gain/calibration and uncertainty; filtering/time alignment; actual
schedules; and an independent synchronized current reference. The
[author question packet](reports/reconciliation/AUTHOR_QUESTIONS.md) remains
prepared and unsent. A better cell model cannot resolve this metrology problem.

Next engineering action: obtain that provenance or perform a controlled test
with calibrated simultaneous module/branch currents and voltage, known initial
SOC/rest preparation and measured surface temperatures. Exercise the intended
14.55 A module waveform, including initial imbalance; characterize relevant
branch dwell loads through approximately 5.35 A with suitable headroom, rather
than inferring sustained accuracy from brief peaks. Add denser rested-voltage
evidence around the observed low-SOC curvature and the voltage-alarm region.
Agree the measurement/error budget before validation. A different dataset is
an alternative only if it documents those references and covers the required
chemistry, topology, temperatures and branch waveforms.

The next model iteration should focus on reference/initial-state evidence, not
automatically add more circuit elements. The fresh v2 assessment is now used
evidence; future selection needs a new allocation and fresh confirmation.
Proceed with controlled model development and measurement planning. **Do not
proceed to module-validation claims, optimizer decisions or ranked repairs.**

Reproduction commands are in [README.md](README.md). Tests and diagnostics cover
analytical parameter recovery, reference-domain handling, voltage masking,
metrics, contiguous current coverage, conservation and charge accounting.
**All 46 tests passed.** The full test record is
[pytest.xml](reports/improvement_v2/pytest.xml).

For a student: the model now predicts the main voltage drop and recovery of
these characterized cells much better on the tested protocol. It can still be
wrong enough near a voltage alarm to change the decision, and it cannot yet
validate the four-cell module. The next step is a calibrated measurement of the
intended load case and better voltage-reference/initial-SOC evidence.
