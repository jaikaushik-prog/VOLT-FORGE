# Initial-state policy implemented; physical origin and rested reference remain unverified

**Keep the published P45B model and LG v2 frozen. Stop further exploratory
P45B parameter fitting until the preparation/reference linkage is established.**
This bounded no-fit investigation implements an explicit initial-state policy
and identifies the missing evidence. It does not supply a new equilibrium
reference or determine a cell's true starting SOC from voltage.

The published reference closely matches its loaded C/30 source-style record.
It differs from GITT finite-rest voltages, including rests still evolving after
9,000 seconds. A previously used -0.005 SOC-origin sensitivity also makes part
of C/30 mathematically unsupported by the unchanged parameter table. These
observations support explicit limits on initialization and reference use, not
another unconstrained fitting loop.

## Scope, provenance and preserved evidence

The [procedure](PROCEDURE.md), [source allocation](../../configs/ae_p45b_reference_origin_v1.json),
implementation and 26 passing synthetic tests were frozen in **`350a953`**
before numerical analysis. The completed [run_001](run_001/summary.json) needed
no implementation correction, grid expansion or fitted parameter. All complete
previously opened C/30, GITT and 1C discharge records were retained. Four fixed
scenarios combine initial SOC 1 or 0.995 with left-held or trapezoidal current
integration, using nominal 4.5 Ah and the published 25 degC discharge reference.

Source: Dickinson et al., About:Energy (2026),
[Molicel P45B release](https://zenodo.org/records/19052626), CC BY 4.0. Original
source lines, timestamps, measured current/voltage and recorded temperature are
preserved in exports. The separate supplied paper's original PDF is not
redistributed. Its already-read methods supply the documentary interpretation.

No measurement family was newly opened. All **48 unused P45B members / 40
families**, the charge-optimized table and validation workbook remain protected.
Nine unused LG cells, 13 FreeTwinEV records and frozen module outcomes are
unchanged. The new verifier checks locked sources and calculations; the root
integration verifier separately checks the historical preservation chain.

## What the existing documentation establishes

| Existing source | Documented fact | What it does not establish |
| --- | --- | --- |
| Supplied paper, PDF pp.9,17 | Nominal capacity is 4.5 Ah; SOC=1 refers to a fresh cell equilibrated in the charging direction at 4.2 V and 25 degC. | That every CSV starts at an independently verified realization of this anchor. |
| PDF p.53 | Discharge reproduction assumes SOC0=1, h0=-1 and nominal setpoint temperature. | A measured starting SOC, hysteresis or internal polarization. |
| PDF p.16 | Reference branches come from loaded C/30 pOCV; the method can lack extended-rest fidelity. | A directly measured equilibrium OCV curve for long rests. |
| PDF p.14 and release README | Representative batch cells supply experiments; the README delegates experimental context to the paper. | Per-file physical cell mapping, complete preparation logs and charge history linking each file to the anchor. |
| Format guide and existing intake | Current is charge-positive; experimental and simulated channels are distinct. | Permission to treat `SOC_sim` or `E_OCV_V` as measured state/reference. |

The authors' choice h0=-1 for discharge reproduces the loaded-reference
construction. Replacing it with a presumed preceding charge state would change
that construction. No such change or voltage-based state adjustment was made.
The constant recorded 25 degC channel is nominal protocol evidence, not a
temperature law or proof of a spatially uniform cell temperature.

## Quantified reference and finite-rest support

These numbers are **reference minus measured voltage**, not dynamic prediction
errors. Loaded 1C voltage contains ohmic/polarization effects, so its reference
difference must not be presented as an ECM error metric.

| Record, primary left-held convention | Samples | Sample RMSE (mV) | Time RMSE (mV) | Sample bias (mV) | Maximum absolute (mV) |
| --- | ---: | ---: | ---: | ---: | ---: |
| Complete C/30, including initial sample | 2,784 | 0.406 | 0.202 | -0.134 | 2.756 |
| Complete GITT, pulses and all rests | 98,426 | 47.669 | 29.802 | +15.343 | 447.626 |
| Complete used 1C | 3,433 | 106.611 | 106.114 | +98.056 | 467.083 |

The earlier C/30 report's 0.402 mV value excluded its initial non-discharge
sample. The current 0.406 mV figure includes every sample as declared. Neither
quantity proves the absolute SOC origin or validates equilibrium OCV; close
agreement with a likely reference-source record is expected.

All 32 complete GITT rests support the declared final 60/300/600-second windows.
Their exact bounds and original source lines are in
[primary_left_rests.json](run_001/primary_left_rests.json). The final-300-second
median exceeds the preceding 300-second median in 31 of 32 rests; the remaining
rest's medians are equal at recorded resolution. No significance or equilibrium
claim follows from this count.

| GITT pair / primary rest-end SOC | Full rest (s) | Final-60-s slope (mV/min) | Final-300-s slope (mV/min) | Final minus preceding 300-s median (mV) |
| --- | ---: | ---: | ---: | ---: |
| 0 / 0.9800 | 1,800.226 | 0.000 | approximately 0 | 0.000 |
| 26 / 0.0989 | 1,800.228 | 0.249 | 0.271 | +1.534 |
| 29 / 0.0421 | 1,800.228 | 0.435 | 0.548 | +3.068 |
| 30 / 0.0251 | 1,800.228 | 0.794 | 0.800 | +4.411 |
| 31 / 0.0154 | 9,000.000 | 0.280 | 0.211 | +1.151 |

The final rest still changes after 2.5 hours. Finite-window slopes and medians
cannot be promoted to equilibrium OCV. Conversely, the first rest's zero slope
does not certify equilibrium: measurement resolution and slower processes are
unquantified. No drift threshold or infinite-time extrapolation was introduced.

Across all pairs, the largest absolute final-60-second mean reference difference
is **41.561 mV** under the primary convention. Using the final 300 or 600 s gives
41.132 and 40.511 mV respectively. The distinction from the preceding report's
41.555 mV median metric is intentional: these are within-window mean residuals,
not the difference between two medians.

The [complete-rest plots](run_001/complete_rests.png) show the entire rests
nearest nominal SOC 0.50, 0.10, 0.04 and the final pair, without truncating
recovery. The [all-pair diagnostic plots](run_001/reference_origin_diagnostics.png)
include window sensitivity, origin sensitivity and C/30 comparison. Both figures
were visually inspected. Exact scenario statistics are in the run summary.

## Origin/integration sensitivity and a mathematical stop

Changing from left-held to trapezoidal integration changes final GITT nominal
SOC from **0.0154389 to 0.0160150**, a difference of 0.0005761. C/30's
corresponding difference is about 0.0000001973. Reporting that distinction is
useful; it does not determine the physical origin.

The table supports nominal SOC **[-0.0057955912, 1.0]** at 25 degC. With the
declared initial-SOC-minus-0.005 sensitivity, C/30 reference evaluation stops at
original **source line 2695** in both integration conventions. Its remaining
**91 measured samples** are retained with undefined-reference flags. SOC
continues to be reported as a charge coordinate and is not clipped. No reference
extension or zero-filled prediction was used.

Over the 2,693 defined shifted-C/30 samples, sample reference-difference RMSE is
**23.968 mV**, versus **0.406 mV** across the full primary record. These cover
different intervals, so they are not a fair model-selection score. The
comparison demonstrates sensitivity and the loss of reference support, not a
reason to choose SOC0 from voltage agreement. The reference table stays fixed;
the shifted scenario changes the record's alignment relative to that table.
It is not a simultaneous relabeling of both the table's SOC axis and the record.

The largest absolute final-60-second GITT mean reference difference becomes
**68.344 mV** under the shifted left-held convention, or **62.644 mV** under
shifted trapezoidal integration. The direction and size of these changes do
not justify selecting a separate SOC offset for each pulse or record.

At the used 1C endpoint, the primary left-held nominal SOC is 0.0461781.
Adjacent C/30 source lines 2239-2240 interpolate to 2.966785 V; adjacent GITT
rest-end lines 83246-85833 interpolate to 2.979426 V. The 1C measured endpoint
is 2.499488 V. These comparisons use a common assumed charge coordinate, with
**unverified cross-record physical-cell and preparation equivalence**.

Shifting all records by the same -0.005 leaves these measured-to-measured
interpolated values unchanged. It changes their numerical SOC labels and the
queried published reference, not the relative alignment of those measured
records. Trapezoidal integration changes the GITT interpolated value to
2.976882 V. Neither operation establishes actual cross-record equivalence.

## Implemented initial-state/reference policy

[`initial_state_policy()`](../../scripts/ae_p45b_reference_origin.py) is a
standalone, synthetic-tested policy evaluator. It does not modify the module
backend or install a P45B component. Exact implemented request/responses are
saved in [policy_examples.json](run_001/policy_examples.json).

| Input mode | Result | Evidence status |
| --- | --- | --- |
| `author_reproduction` with explicit record, discharge and nominal 25 degC | Returns SOC=1, h=-1, RC voltages zero as author assumptions. | `conditional_author_reproduction`; preparation and equilibrium reference unverified. |
| `declared_anchor` with complete anchor-to-initial-time current history, nominal capacity, polarity/convention, source declarations and explicit internal-state assumptions | Integrates current to nominal SOC; rejects gaps, unsupported history or invalid state fields. | `conditional_declared_anchor`; metadata/source strings are declarations, never proof. |
| `unknown`, missing preparation/history, or missing internal-state assumptions | No complete usable initial state. | `insufficient_evidence`, with exact missing fields. |

Every response has `evidence_verified=false` and
`reference_equilibrium_verified=false`. Here `runnable=true` means complete,
explicit **conditional research inputs**, not validated preparation, physical
accuracy or authorization for a design recommendation. The evaluator rejects
unknown calibration fields, voltage-derived SOC, asserted measured/validated
internal states and unsupported charge/temperature routes. A synthetically
documented anchor example is conspicuously labeled synthetic and is never
attached to a real record.

For example, the generated real-record classification uses:

```json
{"mode":"author_reproduction","record_id":"already_opened_25degC_co30","temperature_degC":25,"protocol":"discharge"}
```

Its response declares `status="conditional_author_reproduction"`,
`initial_state={"soc":1.0,"hysteresis":-1.0,"polarization_V":[0.0,0.0]}` and
lists missing preparation/cell identity, independent origin verification and
equilibrium-reference compatibility. The original model is preserved rather
than silently replacing those missing inputs with a fitted answer.

## Exact remaining blocker and minimum external evidence

The available methods define the reference convention but do not trace it to
each released record. The following are needed before treating an initial state
and rested reference as experimentally established:

1. **Per-record identity/preparation:** which physical cell generated each
   C/30, GITT and 1C file; its break-in/cycle state; the preceding charge/rest
   procedure and whether those files share a physical cell or only a batch.
2. **Traceable charge origin:** timestamped charge-to-4.2-V/CV completion and
   rest history, termination criteria, temperature history and all current
   passed between the declared origin and the CSV's first sample, with timing,
   polarity and calibration uncertainty. A label saying "100%" is insufficient.
3. **Reference compatibility:** the exact source/charge-axis processing that
   maps loaded C/30 data into the published reference, and evidence showing
   which rested-voltage behavior that reference is intended to represent.
   A separate rested reference would need its own traceable cell, preparation,
   charge coordinate, recorded rest duration/drift and measurement uncertainty.

These are precise questions for available author documentation or additional
public records; **no outreach was sent**. Existing finite rests cannot be made
equilibrium evidence by changing a label. If the above history/reference
evidence cannot be obtained, the defensible stop is to retain conditional
published-model reproduction and its explicit limits. Do not continue tuning
parameters against the same records to manufacture a unique answer. Suitable
new measurements would be required to establish the unsupported physical claims.

The LG four-cell workspace and backend/evidence UI can continue independently.
Module validation still needs its separate synchronized branch/module currents,
defined voltage locations, calibration and preparation evidence. No P45B origin
policy resolves that current discrepancy. Voltage/excursion requirements remain
**requirement not configured** and affected decisions **insufficient evidence**.

For a student: the starting-charge label is part of the model's coordinate
system. We can reproduce it consistently, but these files do not independently
prove every experiment began at that physical state. Voltage after a long rest
also continues moving. The next action is to obtain the missing history or keep
the model explicitly conditional while completing the product's useful software.

## Verification and reproduction

**26 tests pass** ([receipt](pytest.xml)). Tests cover charge/sign conventions,
gaps and malformed history, conditional versus verified provenance, calibration
field rejection, finite-rest windows, non-equilibrium labeling, domain stops,
source preservation and unsupported interpolation. The
[independent verifier](verification.json) checks **418,572 exported source
samples across the four scenarios** and **384 rest windows**. Independently
recomputed charge coordinates differ by at most **9.42e-14 SOC**. These are
software consistency checks, not experimental module accuracy.

Run from the repository root using fresh output paths and the local locked
downloads. Existing releases cannot be overwritten.

```powershell
$env:OPENBLAS_NUM_THREADS = '1'
$env:OMP_NUM_THREADS = '1'
& C:\Users\DELL\anaconda3\python.exe scripts\ae_p45b_reference_origin.py --out tmp/p45b_reference_origin_trial
& C:\Users\DELL\anaconda3\python.exe -m pytest tests/test_ae_p45b_reference_origin.py -q
& C:\Users\DELL\anaconda3\python.exe scripts\verify_p45b_reference_origin.py --run tmp/p45b_reference_origin_trial --out tmp/p45b_reference_origin_trial_verification.json
```

To verify this release directly:

```powershell
& C:\Users\DELL\anaconda3\python.exe scripts\verify_p45b_reference_origin.py --tests reports/p45b_reference_origin_v1/pytest.xml --out tmp/p45b_reference_origin_release_check.json
```

The run manifest hashes all outputs. CSV.gz files contain every original
measurement row plus the scenario's nominal coordinate, reference difference
and explicit support status. Rest JSON files preserve exact window source
references, slopes, medians and evidence labels; no fitted model is exported.
