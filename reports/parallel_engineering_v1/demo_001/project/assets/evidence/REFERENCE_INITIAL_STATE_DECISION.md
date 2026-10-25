# Reference and initial-state decision

25 October 2026. **The bounded investigation is complete; keep v2/C2 frozen.**
Reference shape matters, but these records do not independently identify
absolute starting SOC. Do not add circuit elements, promote a diagnostic
alignment correction, consume fresh cells or continue tuning toward 25 mV.
First establish the load's voltage requirement and obtain reference/initial-state
and current-calibration evidence. App, dashboard and optimizer remain paused.

The earlier **55% is a reduction in prediction RMSE**, from 21.22 to 9.55 mV
on the declared fresh-cell subset. It is not an improvement in battery
performance. It combines a better rested-voltage reference, broader fitting
data and voltage-recovery dynamics. The full-record v2 maximum on those fresh
cells remains approximately 97 mV. No new fresh assessment is claimed here.

## What this bounded investigation established

The [plan](REFERENCE_INITIAL_STATE_PLAN.md) was frozen before calculations.
Only already-opened P7/P13/P19 characterization records were used. RC parameters,
capacity, the v2 domain and production model were fixed. The one alternative
reference retains the C/20 loaded curve's shape and adds a linear correction
through the same six calibration-rest anchors as v2. It is not equilibrium OCV.

**Absolute SOC and the reference origin cannot be separated by these voltage
fits alone.** For `z(t) = z0 - discharged_Ah(t)/Q`, shifting both `z0` and every
reference SOC label by the same delta leaves predicted voltage unchanged.
This identity was reproduced within 9e-13 mV. The previous +/-2 percentage-point
SOC sensitivity held the reference fixed; it measures sensitivity to alignment
against that reference, not an independently established uncertainty in absolute
charge. Its approximately 32 mV consequence remains relevant to transfer between
records whose starting states may differ.

**Late-rest window choice does not explain the large between-anchor errors.**
Across the 27 inspected one-hour rests, changing the final-30-s median to the
final-300-s median changes voltage by at most 0.422 mV. Consecutive final
five-minute medians differ by at most 0.958 mV; final-ten-minute slopes range
approximately 0.0085-0.193 mV/min. These are short-term drift observations, not
proof of equilibrium, a voltage-calibration certificate or a temperature law.

In already-used cycle 8, at SOC proxies 0.197/0.188/0.206, the sealed rest
reference underpredicts late-rest voltage by **37.74/46.82/19.84 mV** for
P7/P13/P19. The alternative changes these residuals to **+15.03/+17.03/+15.68 mV**.
At cycle 2, near SOC 0.8, it reduces reference discrepancies from roughly
-10 to -13 mV to less than +0.3 mV. At some other SOCs it worsens them. This
supports a reference-shape problem between sparse anchors; it does not uniquely
identify its electrochemical cause or establish a universally better OCV curve.

**Fitting SOC alignment can compensate for reference/model error.** With the
sealed reference and no voltage offset, calibration selects SOC shifts of
-0.20/-0.15/-0.10 percentage points. All three increase development RMSE.
When a voltage offset is also allowed, the fits move toward about +1.95 to
+2.00 percentage points and -19 to -20 mV, close to or on the declared bounds.
The SOC and constant-voltage sensitivity columns have cosines 0.994-0.996:
their effects are almost indistinguishable in this calibration region.
The 5%-objective support ranges extend to the search boundary and are not
confidence intervals. Widening the search is outside this bounded investigation.

For the sealed reference, jointly fitting those two quantities changes
development RMSE from **9.05/9.15/12.01 mV** to **11.56/12.01/9.18 mV**.
Improvement on one cell alongside worsening on two is not evidence for a
transferable initializer. Neither fitted quantity is adopted as a physical SOC
measurement or sensor correction. All calibration quantities were saved before
development voltage was loaded for scoring.

## Diagnostic comparison, not a new selected model

These values use identical primary-domain rows and the unchanged RC model.
They are used development evidence, not fresh assessment.

| Cell | Frozen v2 sample / time RMSE [mV] | Alternative shape only sample / time RMSE [mV] | Frozen / alternative primary maximum [mV] | Frozen / alternative full-record maximum [mV] |
|---|---:|---:|---:|---:|
| P7 | 9.05 / 9.72 | 7.05 / 8.49 | 38.28 / 35.63 | 66.25 / 54.05 |
| P13 | 9.15 / 9.66 | 6.94 / 8.28 | 38.54 / 37.85 | 65.16 / 54.88 |
| P19 | 12.01 / 12.40 | 10.91 / 11.26 | 37.50 / 36.76 | 64.81 / 56.34 |

The shape-only diagnostic improves averages here, but its primary bias is
+5.63 mV on P19, and maximum errors remain substantial. Both references share
the uncertain SOC/capacity convention. No fresh data were opened to select it.
The full [comparison table](reports/reference_initial_state_v1/comparison.csv)
also reports delta-only and joint-alignment cases, bias and unsupported counts.
The [results JSON](reports/reference_initial_state_v1/results.json) retains all
sequence, phase, threshold-region and full-record metrics, including failures.

Plots show measured/predicted voltage, residuals, calibration profiles and
between-anchor rest errors with source file/row references:
[P7](reports/reference_initial_state_v1/P7_diagnostics.png),
[P13](reports/reference_initial_state_v1/P13_diagnostics.png),
[P19](reports/reference_initial_state_v1/P19_diagnostics.png).
The displayed full cycle 8 includes values outside the primary SOC subset;
it is not silently restricted to the headline score. Source rows, rest durations
and temperatures are in [rest evidence](reports/reference_initial_state_v1/rest_evidence.csv).

## Establish a decision tolerance before another fitting sprint

The prospective engineering decision remains: **can the specified 1s4p module
serve 14.55 A for 360 s while maintaining the actual load's required voltage?**
A four-cell parallel group operates at cell-level voltage. Any converter and
its input-voltage requirement must be specified separately if the application
uses a higher-voltage output.

The actual load/device minimum input voltage, allowable excursion duration,
false-clearance consequence and measurement/initial-state uncertainty have not
been supplied. These are requirements inputs, not fit parameters. The 3.50 V
example and 25 mV model allowance remain historical **proposed project criteria**;
they are neither competition requirements nor manufacturer limits. V2's failure
against that proposal remains recorded. The proposal has not been relaxed.

For an independently established voltage margin M, a conservative model-error
allowance is at most `M - B_other`, where B_other covers the remaining applicable
uncertainty. The comparison must include the relevant transient duration.
Define the decision, margin and uncertainty accounting before validation;
do not choose them from the model's observed errors. RMSE is not a worst-case
bound. Do not count reference/SOC errors twice if they are already included in
the residual envelope, or combine correlated uncertainties as independent.

As an illustration only, maximum local reference slopes in SOC 0.2-0.8 are
1.46-1.57 V per unit SOC. A separately justified **10 mV** initialization
allowance would correspond to about **0.64-0.68 percentage points** of relative
SOC alignment by first-order sensitivity, before reference and other errors.
This is not a new accepted tolerance, certified error bound or claim that SOC
can currently be measured that accurately.

## Measurement work, preserved evidence and stopping decision

The four-cell application is still unvalidated. Equal sharing requires 3.6375 A;
the existing imbalance simulation reaches 5.35 A on one branch. About 4.85 A is
covered for six minutes, while excursions above 4.9 A are brief. Those amplitude
and duration facts have not changed. The module-current versus summed-branch
discrepancy remains a separate unresolved metrology problem; neither source was
rescaled or chosen to match expected capacity.

The [faculty/lab request brief](reports/reference_initial_state_v1/LAB_REQUEST.md)
lists the decision inputs, traceable calibration/processing evidence and
measurement capabilities needed. It links the existing precise
[author questions](reports/reconciliation/AUTHOR_QUESTIONS.md). No outreach has
been sent. A named contact, access to suitable instrumentation or author-held
calibration records, and the actual load requirement remain external dependencies.

The new [preservation lock](configs/reference_initial_state_v1.lock.json) binds
112 original/v1/v2 artifacts, including the existing decision, models and plots.
It also binds this investigation's plan and implementation. All checks pass;
the source archive is unchanged. Reproducible per-sample v2 CSVs remain untouched
but are excluded from this additional lock and upload bundle. All nine unused
cells **P3/P6/P9/P11/P12/P14/P15/P18/P20** remain unconsumed. No reserved module
outcomes were opened. The full suite passes **52 tests**, with the separate
[test record](reports/reference_initial_state_v1/pytest.xml) leaving v2's test
record unchanged.

Reproduce from the repository root with the official archive present:

```powershell
$env:PYTHONPATH = 'src'
& C:\Users\DELL\anaconda3\python.exe -m voltforge.models.reference_investigation verify
& C:\Users\DELL\anaconda3\python.exe -m voltforge.models.reference_investigation run
& C:\Users\DELL\anaconda3\python.exe -m pytest -q
```

The original stage order was `reference_investigation reserve` then `run`.
Do not replace the lock to change a completed investigation. A later reference
revision needs its own plan, allowed calibration procedure and fresh allocation.

**Stop this investigation here.** Obtain the decision requirements and the
missing measurement evidence before deciding whether another model revision is
worth assessing. The current model is useful for studying voltage drop/recovery
on characterized cells, but cannot yet certify the module load or rank repairs.
