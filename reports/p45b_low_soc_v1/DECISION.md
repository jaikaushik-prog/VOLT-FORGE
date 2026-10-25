# P45B low-charge reference and recovery diagnosis

The published discharge reference closely reproduces the measured C/30 loaded
curve. The large near-empty 1C error therefore is not explained by a gross
mismatch between that reference and its low-rate characterization record under
the declared SOC convention. GITT observations show much larger voltage recovery
at low charge than the table's steady-current voltage-drop scale. This warrants
a full transient diagnosis; it does not yet identify a unique physical cause.
**No fitted parameter, initial condition or model was changed.**

This stage follows the [pre-access procedure](PROCEDURE.md), committed in
`cda4833`. The implementation and 12 synthetic tests were frozen in `58eaf86`
before opening the two allocated records. Both are development characterization
evidence and may have contributed to the authors' parameterization. They cannot
be presented as fresh independent assessment of that model.

## Evidence and conventions

Source: Dickinson, Zor, Doyle, Pilling, Lukow, O'Regan and White, About:Energy
(2026), [Molicel P45B public release](https://zenodo.org/records/19052626),
CC BY 4.0. The derived CSVs retain measured values and original source line
numbers, add diagnostics, and do not replace the original files. The source
archive/member/table hashes are pinned in
[the allocation](../../configs/ae_p45b_low_soc_v1.json). The supplied paper's
methods describe the references as coming from low-rate loaded measurements;
see the preserved [paper review](../p45b_paper_v1/DECISION.md).

Only `MOLICEL_P45B_025degC_Co30_Dch.csv` and
`MOLICEL_P45B_025degC_GITT_Dch.csv` were newly opened. The earlier 1C result was
reused unchanged. Source current is charge-positive; nominal SOC starts at an
assumed 1 and uses 4.5 Ah. New-record primary SOC uses trapezoidal current
integration; left-held integration is a declared sensitivity. No initial SOC,
capacity, offset or time alignment was fitted to voltage.

| Record | Samples | Duration | Integrated discharge | Final nominal SOC |
| --- | ---: | ---: | ---: | ---: |
| C/30 discharge | 2,784 | 30.1645 h | 4.52467 Ah | -0.005481 |
| GITT discharge | 98,426 | 19.0321 h | 4.42793 Ah | 0.016015 |

Negative nominal SOC is reported, not clipped; the C/30 endpoint remains inside
the published table's support. Different integrated charges under different
protocols are not substituted for nominal capacity. Cross-record cell identity
and preparation equivalence remain unverified.

Neither record contains a gap under the declared diagnostic rule, unknown SOC,
or a lookup outside table support. This does not prove acquisition completeness.
The temperature column is exactly 25 degC throughout both records: it supports
the nominal test condition, not a measured cell-temperature transient or thermal
law. GITT includes brief current overshoots to -5.282 A; these do not establish
sustained performance at that current.

## Confirmed observations

**Reference consistency.** Across 2,783 C/30 discharge samples, table reference
minus measured loaded voltage has sample-weighted RMSE **0.402 mV**, time-weighted
RMSE **0.202 mV**, mean bias **-0.132 mV** and maximum absolute difference
**1.963 mV**. This is consistency with a likely reference-source record, not
terminal-voltage predictive accuracy or equilibrium OCV validation.

**Finite-rest recovery.** The complete GITT record contains 65 direction
segments and 32 discharge/rest pairs. Most following rests last about 1,800 s;
the last lasts 9,000 s. Selected observations below are drawn from the complete
[pair output](run_001/gitt_pairs.csv), not filtered before analysis.

| Loaded endpoint nominal SOC | Pulse-end current magnitude (A) | Pulse duration (s) | Recovery to late-rest median (mV) | Table steady drop scale (mV) | Last-60-s rest slope (mV/min) |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 0.9800 | 4.500 | 72.009 | 70.38 | 65.73 | 0.000 |
| 0.0994 | 4.500 | 72.009 | 143.45 | 147.74 | 0.249 |
| 0.0594 | 4.500 | 72.009 | 279.23 | 127.97 | 0.394 |
| 0.0427 | 4.500 | 60.074 | 461.04 | 128.40 | 0.435 |
| 0.0256 | 2.250 | 122.370 | 352.68 | 63.82 | 0.794 |
| 0.0160 | 1.125 | 138.404 | 295.72 | 31.91 | 0.280 |

The steady drop scale is `abs(I_end)*(R0+R1+R2)` at the loaded endpoint. It is
**not a transient model prediction**, measured resistance, or independent error
metric. The 60.074 s pulse at SOC 0.0427 has table time constants about 4.08 s and
53.56 s; it is only about one slow time constant long and SOC is changing.

For that pair, original GITT source line 83549 is the last loaded sample
(2.499846 V), line 83550 the first rest sample (2.575599 V), and line 85833 the
end of the following 1,800.228 s rest. Its last-60-s median is 2.960884 V. The
0.107 s transition gives an apparent resistance of 16.83 mOhm versus table R0
7.26 mOhm. That sampled jump includes unresolved fast dynamics and cannot by
itself identify R0. A nonzero late-rest slope, including after the final 9,000 s
rest, prevents treating these endpoints as established equilibrium OCV.

**Same assumed charge coordinate.** At the saved 1C final sample, nominal SOC is
0.046178, measured voltage 2.499488 V and predicted voltage 2.835526 V. Adjacent
source samples bracket a C/30 loaded value of 2.966784 V (source lines 2239-2240)
and a GITT late-rest value of 2.976900 V (rest-end lines 83246-85833). These are
467.30 and 477.41 mV above the 1C loaded voltage. The published reference there
is about 2.966570 V, and the frozen prediction's load drop is about 131.04 mV.
This pattern is consistent with inadequate low-charge load response under the
assumed alignment, while cell/preparation and SOC-origin uncertainty remain.
Interpolation covers 3,431 of 3,433 1C coordinates for C/30 and 3,359 for GITT;
unsupported overlap is left blank rather than extended.

## Tested explanations and unresolved hypotheses

| Explanation | What this stage establishes |
| --- | --- |
| Gross misreading of the published discharge reference | Not supported by its close correspondence to loaded C/30 data under the declared origin and capacity. This is not an independent calibration check. |
| Current-integration convention | Maximum SOC difference between left-held and trapezoidal integration is 0.0000201 percentage points for C/30 and 0.05761 percentage points for GITT. Convention is visible; it does not establish the true initial state. |
| Missing rest data or unnoticed lookup extension | No flagged gap or lookup extension in these two records. All 32 pulse/rest pairs are retained. |
| Low-charge load response inadequately represented | Supported as a priority for investigation by the large measured recovery relative to the table's steady drop scale, and the shared 1C error. Full transient reproduction on GITT is still needed. |
| Incorrect R0, an additional slow process, reference bias or capacity/SOC-origin shift | Not uniquely identified. The sampled transition, finite rests and cross-record assumptions cannot separate these causes. No extra circuit element is justified by this stage alone. |

The original 1C sample RMSE **35.86 mV** and maximum absolute error **336.04 mV**
remain unchanged. Our reproduction and the authors' prediction already agree
closely on that record; see the [same-record comparison](../p45b_author_comparison_v1/DECISION.md).
No new assessment error has been claimed here.

## Plots, checks and next decision

- [Full and low-SOC reference comparison](run_001/reference_comparison.png):
  published table, C/30 loaded voltage, finite-rest GITT medians and 1C data.
- [Complete GITT measured sequence](run_001/gitt_sequence.png): source voltage,
  current and recorded temperature without removing pulses or rests.
- [Recovery and late-rest drift](run_001/gitt_recovery.png): observed recovery
  versus steady drop scale, with the non-equilibrium limitation explicit.
- [Machine-readable summary](run_001/summary.json), [interpretation flags](INTERPRETATION.json)
  and [preservation/independent-check receipt](verification.json).

The 12 pre-access synthetic tests exercise integration, gaps, complete segments,
rest windows, transition timing, interpolation exclusions, weighted metrics and
the exact two-member ingestion workflow. All **86 focused P45B tests** pass.
The separate verifier recomputes charge coordinates, reference residual metrics
and every pair's recovery from saved source-valued samples, and checks frozen
artifact hashes. These are software and diagnostic consistency checks.

The next bounded engineering action is to declare a complete GITT replay using
the unchanged two-RC model and inspect pulse and rest residuals, sampling
sensitivity and initial-state assumptions before fitting a revision. GITT and
C/30 are now used development evidence; future confirmation needs a separately
declared allocation from the remaining **48 members / 40 filename families**.
The charge-optimized table and validation workbook remain numerically unopened.
Nine unused LG cells, 13 unused FreeTwinEV records and sealed outcomes remain
protected. No P45B model is adopted into the editor or module backend.

Device voltage/excursion requirements are **requirement not configured**.
Low-charge voltage-limit decisions return **insufficient evidence**. Experimental
module validation is **awaiting suitable measurements**; the module current
discrepancy and author `Q_sim_W` definition remain separate unresolved issues.
No outreach was sent. This online data supports the next cell-model diagnostic
without lab access; it does not replace missing module calibration and branch
measurement evidence.

## Reproduce locally

From the repository root, with the hash-pinned source downloads present:

```powershell
& C:\Users\DELL\anaconda3\python.exe scripts\ae_p45b_low_soc.py --out tmp/p45b_low_soc_replay
& C:\Users\DELL\anaconda3\python.exe -m pytest tests/test_ae_p45b_low_soc.py tests/test_ae_p45b_author_comparison.py tests/test_ae_p45b_reproduction.py tests/test_ae_p45b_equations.py tests/test_ae_p45b_intake.py -q
& C:\Users\DELL\anaconda3\python.exe scripts\verify_p45b_low_soc.py --out tmp/p45b_low_soc_verification.json
```

Choose a new output path for each replay; completed results are never overwritten.
The verifier also requires the local originals used by the earlier preservation
chain. Raw downloads and the supplied paper are not redistributed in Git.
