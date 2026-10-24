# VOLT-FORGE modelling and reconciliation decision

24 October 2026. The sprint delivers a **provisional single-cell baseline and
software-verified ladder solver**. Experimental module validation remains
pending. The current discrepancy is reproduced independently and unresolved;
it was not fitted away.

## Decision and evidence

| Workstream | Result | Decision |
|---|---|---|
| Independent conservation calculation | Discharge mean residual -1.6833 A in test 53, +1.5479 A in test 28. Exact agreement with the original audit using separate MAT/XML decoding. | Preserve both sources as uncertain; obtain calibration/reference evidence before module validation. |
| P7, then six other inspected cells | Resistive models frozen; whole cycles reserved before fitting. P7 assessment HPPC RMSE 18.11 mV; seven-cell range 17.36-20.70 mV. | Reproducible baseline with material limitations; no engineering acceptance claim. |
| One-RC candidates | Interior calibration solutions, but development improvements only 7.15-9.23%, below the predeclared 20% rule. | Retain the simpler model for all cells; preserve RC parameters/profiles as diagnostics. |
| Reserved multisine/rest stress checks | RMSE 26.15-37.93 mV; maximum absolute errors 149.95-234.69 mV. Amplitudes exceed the HPPC fitting range. | Retain these errors as evidence of limited transfer to higher currents. |
| Separate ladder solver | Analytical sharing, circulating-current, charge, KCL/KVL and power-balance tests. | Software verified; experimental validation **pending**. |
| Optimizer and repairs | Not implemented or ranked. | Outside this sprint. |

The [reconciliation report](reports/reconciliation/RECONCILIATION.md) separates
observations, tested explanations and unresolved hypotheses. The
[author packet](reports/reconciliation/AUTHOR_QUESTIONS.md) specifies files,
rows, hashes and requested evidence. **No outreach was sent.** Neither current
source was scaled or selected to match expected capacity.

## Method and parameter meaning

The initial model is `V = U_reference(z) - R0 I`, with discharge-positive current.
The optional candidate adds `-v_p`, where `dv_p/dt = (R1 I - v_p)/tau`.
Resistances and tau are constant in this version. P7 was fitted first, then
P4, P10, P13, P16, P17 and P19 using the same method.

`U_reference` is the C/20 **loaded** voltage versus coulomb-counted SOC proxy,
plus a piecewise-linear correction from the final 10 seconds of the four
calibration cycles' pre-pulse rests. It is not independently established
equilibrium OCV. Correction anchors, observed capacity and source rows are
saved per cell. Corrections use constant end extensions outside their anchor
range; hysteresis is not fitted.

SOC starts at an assumed 1 and uses recorded single-cell current and its
separate C/20 observed capacity. This protocol-dependent integral is not a
correction to module or Hall current. Unknown initial SOC, cycler accuracy,
reference error, contacts and unresolved fast dynamics can influence effective
R0. Module reconciliation does not independently calibrate the single-cell rig.

The RC state starts at zero after the recorded approximately one-hour pre-pulse
rest, conditional on the candidate tau range 0.2-300 s. The actual irregular
clock and a left-endpoint current hold drive the pulse/rest calculation. A
right-endpoint sensitivity is saved for development data; it is zero by
construction for the selected resistive models. No measured assessment voltage
is used for state resets or baseline corrections.

Nominal chamber characterization is 23 C. Whole characterization files contain
surface temperatures roughly 22.06-27.93 C; scored assessment windows span
22.12-23.92 C across cells. Surface measurements do not identify core temperature
or a 10-40 C law. The [source article](https://pangea.stanford.edu/ERE/pdf/OnoriPDF/Journals/91.pdf)
describes nominal protocols; implementation follows the recorded currents and
step indices. Transfer to other module temperatures remains unsupported.

## Reservation, assessment and uncertainty

[Plan](configs/cell_identification_v1.json) and
[input lock](configs/cell_identification_v1.lock.json) were saved before fitting.
Calibration cycles are 1/4/5/9, development 2/7, **assessment 3/6/8**. Complete
source cycles stay in one allocation, including the SOC-setting discharge,
long rest, both HPPC pulses, subsequent rests and multisine section. There is
no random timestamp split. The identified sequence begins at the final 10 s
of the pre-pulse rest; preceding SOC-setting discharge/long rest are reserved
but not scored as identified dynamics. Multisine and final rest continue without
resetting the predicted state to measured voltage.

The [model seal](reports/identification_v1/model_seal.json) binds implementation,
input lock and seven fitted artifacts before assessment scoring. Reruns refuse
to refit a sealed model. Assessment current/timestamps are simulation inputs;
their voltage never enters fitting, reference anchors or selection. A test
adds 1000 V to non-calibration observations and confirms that calibration
frames, reference curves and fitted parameters are unchanged.

The [results report](reports/identification_v1/RESULTS.md) includes parameter
tables, uncertainty, bias, RMS/maximum errors and all seven measured/predicted
figures. P7 effective R0 is 31.32 mOhm; its conditional bootstrap 2.5-97.5
percentile interval is 29.62-33.91 mOhm. Its candidate RC has R1 37.86 mOhm and
tau 83.4 s, with conditional tau interval 42.7-127.8 s. The separate 5%-SSE
profile support is 48.2-135.8 s; it is not a confidence interval. Normalized
sensitivity condition numbers are about 4.7-4.9 and depend on column scaling.

All 256 ordered whole-cycle bootstrap draws of four calibration cycles are
enumerated. Loaded curve, capacity, SOC convention and rest anchors stay fixed.
These conditional intervals omit systematic sensor/reference uncertainty and
do not establish new-cell population coverage. Calibration HPPC RMSE is about
5.3-6.1 mV, substantially below held-sequence errors. P7 cycle 8 shows persistent
reference bias and unresolved relaxation; their unique physical causes are not
identified. No parameters were changed after assessment.

Calibration HPPC currents are approximately -2.00 to +2.66 A; reserved multisine
peaks reach about -6.73 to +17.88 A. Their larger errors are retained. JSON
reports both sample-weighted and time-weighted RMSE because mixed logging
rates change weighting. Per-cycle statistics and worst source rows accompany
per-sample CSV predictions.

These are **within-cell held-sequence checks on the same cells and rig**, using
a separate low-rate characterization input. They are not independent module
validation or unseen-cell generalization. There is no measurement-derived
engineering acceptance budget; the 20% complexity rule is a provisional model
selection screen, not a battery-performance tolerance.

## Ladder implementation and analytical checks

[ladder.py](src/voltforge/models/ladder.py) solves the static same-side-terminal
parallel ladder. Each rail has separate nonnegative interconnect resistances;
position 1 is nearest the terminals. With `S[j,i]=1` for cells downstream of
segment j, the equations are:

```text
Z = diag(R0) + S.T diag(r_positive + r_negative) S
Z I + 1 V_terminal = E
1.T I = I_module
E = effective cell source, potentially U - v_p in a future coupled simulation
```

Rail currents are downstream sums. Outputs include node/terminal voltages,
cell and rail losses, KCL residual and power-balance residual. The identity is
`E.T I = V_terminal I_module + sum(R0 I^2) + sum((rp+rn) (S I)^2)`.
Both rails are counted once. The topology follows the shared-rail relation in
[Fasolato et al., section 2.2](https://pangea.stanford.edu/ERE/pdf/OnoriPDF/Journals/109.pdf).

Independent analytical cases include identical cells sharing 12 A as 3 A each
at 3.64 V; a two-cell ladder sharing 10 A as 7.5/2.5 A at 2.95 V; and unequal
source voltages producing +/-2/3 A circulating current at zero load. The
two-cell example uses distinct 0.12/0.08 ohm rails to exercise shared paths.
Tests also check charge, asymmetric KVL/energy and invalid inputs. Numerical
tolerances express software precision, not sensor accuracy. This is a direct
linear solve, with no coupled-model time-step convergence claim.
**Experimental ladder validation is pending.**

## Preservation and remaining blocker

The raw ZIP still matches its original SHA-256. Eleven original provenance,
inventory/audit JSON and module-split artifacts match the lock byte for byte.
Original module final-assessment signals were not scored, plotted or used for
decisions in this sprint. Existing audit outputs remain; new results occupy
separate directories.

The external blocker is reproducible Hall/cycler processing and calibration,
supported by hardware mapping and independent reference uncertainty. Obtain
that evidence before fitting or validating module sharing. A future revised
cell reference, SOC-dependent dynamics or temperature model needs a new version
and fresh assessment evidence: the opened v1 assessment is now used evidence.

Commands are in [README.md](README.md). Numerical preservation, exact residual
agreement and analytical examples are saved in
[sprint verification](reports/sprint_verification/results.json).

Verification: **34 tests passed**, including the original real-data checks,
independent decoding, analytical parameter recovery, leakage/immutability guards
and nine ladder tests. The full result is retained in
[pytest.xml](reports/sprint_verification/pytest.xml). Frozen-model replay also
completed without refitting. Software-test success does not change the
experimental-validation limits above.
