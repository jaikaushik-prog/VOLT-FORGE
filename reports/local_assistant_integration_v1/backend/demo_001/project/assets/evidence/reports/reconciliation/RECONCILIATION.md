# Current reconciliation: confirmed discrepancy, unresolved cause

24 October 2026. Only the already-inspected M1 tests 53 and 28 were opened.
Both module and Hall-derived currents remain potentially uncertain. No trace
was rescaled, offset-corrected, remapped or chosen for capacity agreement.

## Confirmed observations

The [standalone calculation](../../scripts/reconcile_independent.py) decodes
MAT5 tags with `struct`/`zlib` and reads XLSX worksheet XML. It imports neither
the existing audit package nor SciPy/pandas readers, and consumes no normalized
CSV. Its minimal calculation is:

```python
# Source currents are charge-positive. Result is discharge-positive Hall sum minus module.
residual_A = raw_module_current_A - sum(author_branch_current_A)
```

| Observation | Test 53: M1 R0 T25 | Test 28: M1 R3 T25 |
|---|---:|---:|
| Samples | 33,079 | 41,689 |
| Step-5 original Excel Data rows, inclusive | 13,317-18,751 | 22,340-26,563 |
| Discharge residual mean [A] | **-1.6832915321** | **+1.5479236509** |
| Discharge residual RMS [A] | 1.6858798704 | 1.5510595031 |
| Discharge maximum absolute residual [A] | 2.0883674274 | 1.9570073713 |
| Full-record residual RMS [A] | 0.6924719212 | 0.5041632324 |
| Module discharge integral [Ah] | 21.9681044330 | 17.0801792449 |
| Cycler discharge-capacity increment [Ah] | 21.9680966162 | 17.0801419584 |

Both implementations return identical mean/RMS/maximum values at stored double
precision. This confirms a discrepancy in the supplied signals, not which
instrument measures true current. The capacity counter and current integral
come from the same cycler: **not independent current references**.

## Tested explanations

| Check | Result and limit |
|---|---|
| MATLAB decoding/columns | Independent decoding finds 15 labelled module columns. All 11 shared raw/MAT channels match exactly: test/step time, step/cycle index, module current/voltage, four surface temperatures and ambient. Compressed/uncompressed MAT fixtures check storage order and precision. No evidence the existing reader causes the residual. |
| Polarity | Step 5 module and branches are negative in source polarity. Unchanged signs minimize discharge RMS among all 16 branch-sign combinations. Global sign conversion preserves the discrepancy magnitude. |
| Units | `Current(A)` and `CurrentA*` are amperes; elapsed time is seconds. `Aux_Voltage(V)_1..4` are Hall volts. Diagnostic branch factors 0.001/1/1000 favor the declared A units; no factor was applied to delivered measurements. |
| Positions/sensors | Nominal M1 positions 1-4 map to H1-H4; M2 to H5-H8. Article/metadata checks give test 53 cells P7/P17/P19/P13 and test 28 P17/P4/P10/P16 in order. Permuting four branches cannot change their sum. Actual per-run hardware identity still needs author confirmation. |
| Calibration identity | All eight Hall files were decoded and linearly fitted. The full 4-by-8 application-error matrix is retained. Nominal H1-H4 fits differ from test-53 published branch currents by RMS 0.8743/0.6343/0.0773/0.6076 A. Other files sometimes fit closer, but none reproduces a branch exactly. This establishes neither a new mapping nor the authors' method. Earlier supply-aware alternatives also failed. |
| Time alignment | Raw/MAT elapsed arrays are exactly equal. No backward/duplicate times or intervals above the provisional 1.5 s gap screen. Median 1 s; maxima 1.175488/1.176300 s. Full-record shifts -10 through +10 samples minimize RMS at zero in both runs. Analog filtering and sub-sample latency remain untested. |
| Wall clock | Direct Excel serial-day elapsed differences agree with test time within 0.793/1.893 ms. The earlier datetime reader rounds to milliseconds and reported 1.592/2.492 ms. These are serialization comparisons, not clock accuracy. No timezone is assigned. |
| Constant offset | Rest-step means are about -0.013 to -0.019 A and +0.020 to +0.032 A, much smaller than discharge discrepancies. One constant additive offset cannot reconcile both states. |
| Capacity-based reference choice | Not justified: rates, temperatures and initial-state assumptions differ. Agreement with plausible capacity cannot choose the correct current reference. |

## Unresolved hypotheses and blocker

Per-run Hall coefficients, sensor-ID swaps, supply compensation, saturation,
temperature effects or undocumented filtering remain possible. Cycler
range/gain/reference error, shared processing error or an undocumented
measurement-path difference also remain possible. Neither side has a supplied
end-to-end uncertainty budget sufficient to resolve this.

The blocker is the exact processing/calibration chain and independent current
reference evidence. An explanation must reproduce the supplied numbers, or
provide a versioned correction with provenance and uncertainty. Module
current-sharing validation and ranked repairs remain blocked. Single-cell
identification and analytical ladder verification proceeded separately.

Evidence: [numerical checks](independent_results.json),
[test 53 plot](M1_NMC_Unaged_R0_T25_independent.png),
[test 28 plot](M1_NMC_Unaged_R3_T25_independent.png), and corresponding
`*_residual.csv` files with original Excel/MAT rows.
[Author questions](AUTHOR_QUESTIONS.md) are prepared; **no outreach was sent**.

Nominal hardware/protocol source: [Piombo et al., Data in Brief](https://pangea.stanford.edu/ERE/pdf/OnoriPDF/Journals/91.pdf).
The archive is [Mendeley version 2](https://data.mendeley.com/datasets/zh58byr53c/2), distinct from the article's version-1 reference.
