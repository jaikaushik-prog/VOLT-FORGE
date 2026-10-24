# V2 baseline-versus-candidate results

All v1 cells are used development evidence. P2/P5/P8 assessment follows the frozen procedure and their own allowed calibration; it is not zero-shot prediction or independent module validation.

Primary domain: SOC proxy 0.2-0.8, rest/discharge -0.01 to 4.9 A (small negative threshold is a zero-current tolerance), surface 22-28 C under this nominal-23 C protocol. Values below are per-cell, on identical rows.

| Role / cell | Model | Sample / time RMSE [mV] | Bias [mV] | Max [mV] | Proposed criteria met? |
|---|---|---:|---:|---:|---|
| development / P7 | v1 method | 20.93 / 26.38 | 5.33 | 129.27 | No |
| development / P7 | C1: rest + R | 14.87 / 16.40 | -0.79 | 128.73 | No |
| development / P7 | C2: rest + RC | 9.05 / 9.72 | -1.76 | 38.28 | No |
| development / P7 | C3: SOC + RC | 9.21 / 9.95 | -1.65 | 34.65 | No |
| development / P4 | v1 method | 20.93 / 26.39 | 5.28 | 131.35 | No |
| development / P4 | C1: rest + R | 15.10 / 16.76 | -0.60 | 129.08 | No |
| development / P4 | C2: rest + RC | 9.59 / 10.25 | -1.66 | 51.68 | No |
| development / P4 | C3: SOC + RC | 9.72 / 10.43 | -1.55 | 40.17 | No |
| development / P10 | v1 method | 20.82 / 26.24 | 5.34 | 130.38 | No |
| development / P10 | C1: rest + R | 14.80 / 16.34 | -0.72 | 128.86 | No |
| development / P10 | C2: rest + RC | 8.99 / 9.70 | -1.69 | 40.39 | No |
| development / P10 | C3: SOC + RC | 9.15 / 9.90 | -1.57 | 34.43 | No |
| development / P13 | v1 method | 19.89 / 24.95 | 4.79 | 124.52 | No |
| development / P13 | C1: rest + R | 14.55 / 15.73 | -1.44 | 123.86 | No |
| development / P13 | C2: rest + RC | 9.15 / 9.66 | -2.52 | 38.54 | No |
| development / P13 | C3: SOC + RC | 9.26 / 9.80 | -2.36 | 33.50 | No |
| development / P16 | v1 method | 22.11 / 26.94 | 10.01 | 133.39 | No |
| development / P16 | C1: rest + R | 16.41 / 17.30 | -3.09 | 123.64 | No |
| development / P16 | C2: rest + RC | 12.14 / 12.56 | -4.15 | 41.05 | No |
| development / P16 | C3: SOC + RC | 12.45 / 13.00 | -3.81 | 52.40 | No |
| development / P17 | v1 method | 20.84 / 26.26 | 5.37 | 129.02 | No |
| development / P17 | C1: rest + R | 14.81 / 16.34 | -0.72 | 128.15 | No |
| development / P17 | C2: rest + RC | 9.04 / 9.74 | -1.69 | 40.38 | No |
| development / P17 | C3: SOC + RC | 9.20 / 9.95 | -1.58 | 34.62 | No |
| development / P19 | v1 method | 21.95 / 26.73 | 9.99 | 131.00 | No |
| development / P19 | C1: rest + R | 16.26 / 17.05 | -3.23 | 122.42 | No |
| development / P19 | C2: rest + RC | 12.01 / 12.40 | -4.24 | 37.50 | No |
| development / P19 | C3: SOC + RC | 12.31 / 12.87 | -4.09 | 50.09 | No |
| fresh / P2 | v1 method | 20.74 / 26.12 | 5.32 | 129.78 | No |
| fresh / P2 | C1: rest + R | 14.71 / 16.22 | -0.70 | 127.48 | No |
| fresh / P2 | C2: rest + RC | 9.00 / 9.69 | -1.66 | 40.95 | No |
| fresh / P2 | C3: SOC + RC | 9.14 / 9.89 | -1.55 | 34.13 | No |
| fresh / P5 | v1 method | 20.93 / 26.36 | 5.35 | 129.55 | No |
| fresh / P5 | C1: rest + R | 14.74 / 16.20 | -0.77 | 128.43 | No |
| fresh / P5 | C2: rest + RC | 8.87 / 9.54 | -1.70 | 35.39 | No |
| fresh / P5 | C3: SOC + RC | 9.04 / 9.78 | -1.60 | 35.00 | No |
| fresh / P8 | v1 method | 22.00 / 27.79 | 6.99 | 149.94 | No |
| fresh / P8 | C1: rest + R | 15.67 / 17.17 | -0.08 | 127.47 | No |
| fresh / P8 | C2: rest + RC | 10.77 / 11.24 | -0.93 | 44.65 | No |
| fresh / P8 | C3: SOC + RC | 10.89 / 11.44 | -0.83 | 40.04 | No |

Selection was **C2, rest reference + constant one-RC**, before fresh outcomes. C3 has more parameters and does not improve the primary development score. Passing the complexity selection rule does not mean passing the engineering error budget.

Complete-sequence and phase/cycle/SOC/current/temperature/time-since-transition metrics (sample RMSE, time RMSE, bias, maxima, worst source row) are in `development/scores.json` and `fresh/scores.json`. Full-record metrics are also in `comparison_summary.csv`. Unsupported reference rows are counted explicitly; the reference never silently extrapolates.

[Fresh comparison](fresh_comparison.png) | [Reference/identifiability](reference_and_identifiability.png) | [V1 diagnosis](diagnosis/P7_residual_diagnosis.png)

Plots contain original source rows; CSVs retain row, time, current, SOC, measured temperature, reference, prediction and residual. The long discharge and later pulse/rest/MS views are both shown.

development: [P7 comparison](development/P7_comparison.png) / [pulse detail](development/P7_pulse_detail.png) | [P4 comparison](development/P4_comparison.png) / [pulse detail](development/P4_pulse_detail.png) | [P10 comparison](development/P10_comparison.png) / [pulse detail](development/P10_pulse_detail.png) | [P13 comparison](development/P13_comparison.png) / [pulse detail](development/P13_pulse_detail.png) | [P16 comparison](development/P16_comparison.png) / [pulse detail](development/P16_pulse_detail.png) | [P17 comparison](development/P17_comparison.png) / [pulse detail](development/P17_pulse_detail.png) | [P19 comparison](development/P19_comparison.png) / [pulse detail](development/P19_pulse_detail.png)

fresh: [P2 comparison](fresh/P2_comparison.png) / [pulse detail](fresh/P2_pulse_detail.png) | [P5 comparison](fresh/P5_comparison.png) / [pulse detail](fresh/P5_pulse_detail.png) | [P8 comparison](fresh/P8_comparison.png) / [pulse detail](fresh/P8_pulse_detail.png)

`parameter_stability.json` reports conditional leave-one-calibration-cycle-out ranges and normalized sensitivity conditioning for every baseline/candidate/cell. Reference anchors are held fixed, so these are stability diagnostics, not measurement uncertainty intervals. `assumption_sensitivity.json` covers all four models on P7 and all three fresh cells; masks stay fixed at nominal-domain rows.

`threshold_diagnostics.json` distinguishes unguarded classification changes, guarded false clearances and ambiguous results. Zero observed guarded false clearances does not validate the unmeasured instrumentation/initial-condition budget or establish a rare-event rate.

`software_coupling/results.json` gives per-branch current coverage, SOC balance, current conservation and dt sensitivity for the specified 14.55 A application. These are synthetic model predictions for software verification, not new experimental results.

The raw archive and all preserved v1 artifacts remain unchanged. The root decision report states the supported domain and outstanding gates.
