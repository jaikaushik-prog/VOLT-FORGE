# Sealed single-cell results

Generated from frozen model artifacts and reserved-cycle predictions. These are provisional within-cell checks on the same cells and rig; **not independent module validation**.

| Cell | Q [Ah] | Effective R0 [mOhm] | Conditional 2.5-97.5% [mOhm] | Calibration / development / assessment HPPC RMSE [mV] |
|---|---:|---:|---:|---:|
| P7 | 4.8486 | 31.32 | 29.62-33.91 | 5.61 / 18.59 / 18.11 |
| P4 | 4.8346 | 31.84 | 30.04-34.65 | 5.77 / 20.29 / 19.96 |
| P10 | 4.8320 | 31.92 | 30.09-34.74 | 5.79 / 20.22 / 20.51 |
| P13 | 4.7981 | 30.74 | 28.79-33.87 | 6.08 / 21.74 / 20.70 |
| P16 | 4.9022 | 30.72 | 29.18-32.89 | 5.39 / 16.20 / 17.48 |
| P17 | 4.8444 | 32.20 | 30.55-34.67 | 5.57 / 19.22 / 19.12 |
| P19 | 4.9040 | 30.30 | 28.87-32.23 | 5.28 / 16.14 / 17.36 |

R0 is an effective resistance conditional on the loaded/rest reference; unresolved fast dynamics and contacts can contribute. Q is an observed C/20 current integral, not a fitted nominal capacity. The bootstrap resamples only four calibration cycles; curve, capacity, SOC convention and rest anchors stay fixed. These intervals omit systematic instrument and reference-curve uncertainty.

| Cell | Reserved HPPC bias / max [mV] | Reserved multisine + rest RMSE / bias / max [mV] | Recorded assessment surface [C] |
|---|---:|---:|---:|
| P7 | 11.78 / 45.51 | 29.02 / 11.26 / 171.44 | 23.11-23.92 |
| P4 | 13.17 / 48.94 | 37.93 / 12.11 / 234.69 | 22.46-22.85 |
| P10 | 13.64 / 49.91 | 31.75 / 12.87 / 184.07 | 22.12-22.86 |
| P13 | 13.58 / 50.21 | 28.98 / 12.82 / 158.77 | 22.82-23.63 |
| P16 | 11.60 / 43.94 | 29.26 / 10.95 / 175.51 | 22.43-22.93 |
| P17 | 12.60 / 47.26 | 30.48 / 11.80 / 179.91 | 22.85-23.49 |
| P19 | 11.60 / 44.01 | 26.15 / 10.97 / 149.95 | 22.82-23.38 |

Errors are predicted minus measured. RMSE here weights recorded samples equally; `summary.json` and `assessment.json` also report time-weighted RMSE, per-cycle errors, current ranges and worst-error source rows. Mixed logging rates make these weightings different.

| Cell | Candidate R0 / R1 [mOhm] | Candidate tau [s] | 5%-SSE support [s] | Normalized sensitivity condition | Development HPPC improvement [%] |
|---|---:|---:|---:|---:|---:|
| P7 | 30.35 / 37.86 | 83.4 | 48.2-135.8 | 4.85 | 8.18 |
| P4 | 30.85 / 38.58 | 83.4 | 48.2-135.8 | 4.85 | 7.56 |
| P10 | 30.88 / 36.94 | 78.5 | 48.2-135.8 | 4.79 | 7.27 |
| P13 | 29.78 / 41.42 | 88.7 | 48.2-153.5 | 4.91 | 7.15 |
| P16 | 29.61 / 32.29 | 69.5 | 42.7-106.5 | 4.67 | 8.97 |
| P17 | 31.23 / 37.84 | 83.4 | 51.2-135.8 | 4.85 | 7.88 |
| P19 | 29.25 / 33.48 | 73.9 | 45.4-113.1 | 4.73 | 9.23 |

All selected models are resistive: the candidate RC models fail the predeclared 20% development-improvement rule. This does not establish an absence of polarization. Candidate RC conditional bootstrap intervals are in each `*_model.json`; the profile support is a descriptive identifiability screen, not a confidence interval. No assessment result was used to alter this choice.

Calibration cycles: 1, 4, 5, 9. Development: 2, 7. Reserved assessment: 3, 6, 8. Every source cycle stays in one allocation. HPPC predictions include both pulses, all intervening/following rests and the last 10 s of the preceding rest. The subsequent multisine and final rest are simulated without resetting to measured voltage. The preceding SOC-setting discharge and long rest are reserved with their cycles but not scored as identified dynamics.

The calibration HPPC currents are approximately -2.00 to +2.66 A. Reserved multisine inputs reach about -6.73 to +17.88 A, beyond that fitting amplitude. Large errors in those sequences are retained as limits of this baseline. The nominal chamber setting is 23 C; recorded surface excursions are not a temperature-identification experiment. No 10-40 C parameter law or core-temperature model is inferred.

[Identification and uncertainty plot](identifiability.png) · [Assessment summary](assessment_summary.png) · [P7 reference curve](P7_loaded_reference.png)

Measured/predicted figures: [P7](P7_assessment.png) · [P4](P4_assessment.png) · [P10](P10_assessment.png) · [P13](P13_assessment.png) · [P16](P16_assessment.png) · [P17](P17_assessment.png) · [P19](P19_assessment.png)

Per-sample predictions and error/source-row references: `*_assessment_predictions.csv`. The plan, input lock and model seal are under `configs/` and this directory. Reproduction commands are in the root README.
