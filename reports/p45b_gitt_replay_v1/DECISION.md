# P45B complete GITT replay: the low-charge load response remains inadequate

The unchanged published model completes the 19.03-hour pulse/rest replay with
**29.88 mV sample-weighted RMSE**, **22.19 mV time-weighted RMSE**, and **333.37 mV
maximum absolute error**. Near empty, it predicts about **114 mV** of recovery
where the measurement shows **461 mV**. This is now a comparison with a full
transient simulation, replacing the earlier steady-drop scale as the relevant
diagnostic. It does not establish a new model or independent accuracy claim.

The large discrepancy persists under the declared numerical, current-sampling
and supported initial-SOC scenarios. These checks do not identify its unique
physical cause. Keep the published P45B model and LG v2 frozen. Do not use this
P45B reproduction for near-empty voltage-limit or module design decisions.

## Scope, chronology and source

The [procedure](PROCEDURE.md) was committed in `9a40595`; the implementation,
source lock and 13 synthetic checks were frozen in `db2244e` before this replay.
No additional measurement family or author-output field was opened. This uses
the already-opened `MOLICEL_P45B_025degC_GITT_Dch.csv` record, retained in the
[previous diagnosis](../p45b_low_soc_v1/DECISION.md), and the unchanged base table.
These characterization observations are used development evidence and may have
contributed to the authors' parameterization. They are not fresh assessment.

Source: Dickinson, Zor, Doyle, Pilling, Lukow, O'Regan and White, About:Energy
(2026), [Molicel P45B release](https://zenodo.org/records/19052626), CC BY 4.0.
The derived exports retain source line numbers and measured channels, adding
model predictions and diagnostics. Original downloads remain unchanged and
local. See the [source lock](../../configs/ae_p45b_gitt_replay_v1.json),
[run manifest](run_001/manifest.json), and
[independent checks/preservation receipt](verification.json).

The sole integrator is the existing frozen `ae_p45b_reproduction.simulate`,
using its original two-RC/hysteresis kernel. New code supplies diagnostic
bookkeeping and a tested constant SOC-coordinate adapter for exploratory origin
changes. It does not implement a replacement solver or edit fitted parameters.
All 98,426 timestamps, 65 segments and 32 pulse/rest pairs are retained. The
initial states are assumptions: SOC=1, discharge hysteresis=-1 and zero RC
polarization, at the first timestamp. Capacity remains 4.5 Ah. Source current is
charge-positive. No per-pulse reset, voltage offset, time shift or capacity fit
was permitted. Temperature is assumed isothermal at 25 degC; the recorded
constant temperature column does not establish cell-temperature dynamics.

## Five declared scenarios

Errors below are prediction minus measurement, in mV. Defined scenarios cover
all 98,426 samples and 68,515.68 s; no reference extension or acquisition gap was
used. Metrics for a stopped scenario are unavailable, not zero.

| Scenario | Sample RMSE | Time RMSE | Sample bias | Time bias | Max absolute | Status |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| Primary: SOC=1, left-held current, 0.25 s | 29.884 | 22.190 | +0.852 | -3.298 | 333.367 | Complete |
| Fine step: 0.0625 s | 29.884 | 22.190 | +0.851 | -3.298 | 333.367 | Complete |
| Linear-current sensitivity | 30.461 | 22.613 | +1.906 | -2.086 | 335.996 | Complete |
| Initial SOC=0.995 sensitivity | 30.557 | 27.978 | -11.206 | -16.885 | 308.327 | Complete |
| Initial SOC=1.005 sensitivity | unavailable | unavailable | unavailable | unavailable | unavailable | Stopped at first sample: outside reference support |

Primary versus fine differs by at most **0.03961 mV** (difference RMSE
0.00311 mV), satisfying the predeclared 0.1 mV numerical check. That criterion is
not an experimental accuracy or application requirement. Linear interpolation
of current changes voltage by at most **5.049 mV** (difference RMSE 1.813 mV).
The SOC=0.995 scenario changes voltage by up to **48.839 mV** (difference RMSE
18.276 mV), worsens time-weighted error and does not resolve the recovery miss.
It is not selected as a calibration. The +/-0.005 SOC perturbations are explicit
exploratory assumptions, not measured uncertainty, confidence intervals or
guaranteed bounds. The unsupported positive scenario is preserved with every
measurement and blank predictions; it was not clipped back to SOC=1.

The complete [summary](run_001/summary.json) includes errors by current range,
recorded temperature, SOC, direction and time from a current transition. Every
scenario also has separate per-segment and per-pair CSV results.

## Where the primary errors occur

| Subset | Samples | Sample RMSE (mV) | Time RMSE (mV) | Sample bias (mV) | Max absolute (mV) |
| --- | ---: | ---: | ---: | ---: | ---: |
| Discharge | 18,618 | 55.323 | 55.204 | +19.563 | 333.367 |
| Rest | 79,808 | 19.682 | 18.599 | -3.514 | 290.095 |
| Nominal SOC 0-0.2 | 36,013 | 48.757 | 34.109 | +4.470 | 333.367 |
| Nominal SOC 0.2-0.8 | 38,235 | 6.994 | 6.840 | -0.651 | 22.535 |
| Nominal SOC 0.8-1 | 24,178 | 4.153 | 3.815 | -2.161 | 14.848 |

The middle-SOC result is promising development evidence for this particular
25 degC protocol, not a newly validated operating envelope. Long rests and
nonuniform sampling make the whole-record mean a poor description of the
near-empty pulse error. Source current includes brief overshoots; amplitude
coverage does not establish accuracy for a sustained module-branch waveform.

Rest-window sample RMSE is 66.35 mV in the first second, 40.10 mV from 1-10 s,
27.45 mV from 10-60 s, 19.98 mV from 60-600 s and 16.17 mV after 600 s. Windows
are measured from each rest segment's first sample; time weighting never bridges
excluded intervals. The initial two-sample rest is retained. Early and late
errors have different causes potentially; these averages cannot isolate them.

For the low-SOC example, original source line 83549 is the last loaded sample,
83550 the first rest sample, and 85833 the end of the 1,800.228 s rest. The pulse
lasts 60.074 s at about -4.5 A. The primary's nominal loaded endpoint SOC is
0.042104; linear-current integration gives 0.042652, consistent with the previous
diagnostic's coordinate. These conventions remain explicit rather than aligned
to improve voltage agreement.

| Observation at this pair | Measurement | Primary model |
| --- | ---: | ---: |
| Last loaded voltage | 2.499846 V | 2.833204 V |
| Last-60-s rest median | 2.960884 V | 2.947321 V |
| Recovery between those values | 461.038 mV | 114.117 mV |
| Last-60-s rest slope | +0.43477 mV/min | -0.0000393 mV/min |

Thus the loaded error is **+333.358 mV**, the late-median difference is
**-13.563 mV**, and predicted recovery is **346.921 mV too small**. The
linear-current scenario's recovery deficit is 346.850 mV; initial SOC=0.995
gives 347.041 mV. This large change in voltage under load and through recovery
is not repaired by the tested origin or sampling changes.

Across subsequent low-charge pairs, the same pattern persists: at nominal SOC
0.0251 and 0.0154, measured recoveries are 352.68 and 295.72 mV while the model
predicts 61.51 and 31.02 mV. Late-rest slopes remain nonzero, including after
the final 9,000 s rest. These medians are not established equilibrium OCV.

The measurement first crosses the protocol's 2.5 V level at source line 83548;
the primary prediction never crosses it during the supplied record. This
illustrates a practical voltage-decision discrepancy. **2.5 V here is a
characterization-protocol reference, not the application's minimum voltage.**
Actual device voltage and excursion requirements remain unset.

## Tested explanations, remaining ambiguity and next action

- **Numerical step size:** the measured miss is far larger than the tested
  0.040 mV numerical difference. Step refinement does not resolve it.
- **Current-sampling convention:** changes SOC and voltage modestly, while the
  large low-charge recovery error persists. No current was rescaled.
- **Initial SOC:** a declared half-percentage-point decrease changes absolute
  voltage materially but barely changes the low-charge recovery deficit. This
  is a one-sided supported test, not a proof that all SOC/reference uncertainty
  is irrelevant. The positive perturbation is outside the table.
- **Initial RC/hysteresis memory inside this model:** maximum interpolated time
  constants are 4.5874 and 80.6440 s, including interior extrema of R*C between
  knots. At the highlighted pair, the conservative remaining initial slow-RC
  influence fraction is about 1.9e-300 and hysteresis-memory fraction about
  4.9e-20. These conditional model sensitivities make finite initial RC-state
  errors an implausible explanation of a late-record miss within this model.
  They do not bound real-cell error or initial-SOC/reference uncertainty.
- **Inadequate low-charge load response:** strongly supported as the issue to
  address, because the model misses both loaded voltage and recovery while
  reaching a much closer finite-rest voltage. The present data do not uniquely
  separate R0, polarization resistance/time scales, rate dependence, reference
  bias, SOC-origin/capacity error, or effects not represented by this ECM.

No parameter identifiability or confidence interval is claimed from this
unfitted replay. The next bounded action is to test identifiability of a small
low-SOC revision within the existing two-RC structure using joint complete
pulse/rest sequences. Freeze a candidate procedure and any allowed calibration
before fitting; reserve a genuinely unused complete family before confirmation.
Do not add a third RC element merely because the current model misses the tail.
An acceptable candidate must address pulse and relaxation behavior together,
not just lower the whole-record mean error or move the voltage reference.

That cell-model work can continue with available online data. Separate module
validation still needs suitable calibration, preparation, sense-location and
current/branch evidence; see the existing reconciliation/lab-request and
FreeTwinEV reports. This replay does not resolve the module-current discrepancy
or the author `Q_sim_W` definition, and no outreach was sent.

## Artifacts, checks and reproduction

- [Complete measured/predicted voltage, residual and current](run_001/complete_replay.png).
- [All-pair error and recovery comparisons](run_001/pair_diagnostics.png).
- [Complete selected sequences with source lines](run_001/selected_sequences.png):
  first, closest to nominal SOC 0.5/0.1/0.04, and last; selection was fixed by
  SOC rather than prediction error. The full long rests are visible.
- Five deterministic `*.csv.gz` files retain every timestamp, measured voltage
  and current, predictions, states, voltage decomposition and support status.
  Five `*_segments.csv` and five `*_pairs.csv` files expose complete-sequence
  diagnostics. Unpredicted values are blank. No original observation is deleted.
- [Machine-readable interpretation](INTERPRETATION.json) and the
  [99-test receipt](pytest.xml). Tests cover exact solver reuse, analytic RC
  pulse/rest evolution, initial-origin transformation, source locks, gaps,
  unsupported origins, complete exports, weighting and conditional memory bounds.
  The verifier independently recomputes metrics, charge coordinates, source
  alignment and each pair's recovery, and verifies the prior artifact chain.

All frozen models, raw sources and protected assessment artifacts are preserved.
The remaining 48 P45B members / 40 families, charge-optimized table, validation
workbook, nine unused LG cells and 13 unused FreeTwinEV records stay protected.
The editor, thermal capabilities and optimizer are unchanged. Module validation
status is **awaiting suitable measurements**; voltage-limit design status is
**insufficient evidence**, with **requirement not configured** for unknown limits.

From the repository root, with local source downloads required by the hash chain:

```powershell
& C:\Users\DELL\anaconda3\python.exe scripts\ae_p45b_gitt_replay.py --out tmp/p45b_gitt_replay
& C:\Users\DELL\anaconda3\python.exe -m pytest tests/test_ae_p45b_gitt_replay.py tests/test_ae_p45b_low_soc.py tests/test_ae_p45b_author_comparison.py tests/test_ae_p45b_reproduction.py tests/test_ae_p45b_equations.py tests/test_ae_p45b_intake.py -q
& C:\Users\DELL\anaconda3\python.exe scripts\verify_p45b_gitt_replay.py --out tmp/p45b_gitt_verification.json
```

Use a fresh output path for each replay or receipt. To read a compressed export,
use Python `gzip.open(path, 'rt', newline='')` with `csv.DictReader`, or
`pandas.read_csv(path)`; compression is storage only, without downsampling.
