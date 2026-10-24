# Prepared author questions and evidence — not sent

Purpose: reproduce current conversion and uncertainty for tests 53 and 28,
without presuming whether Hall branches or the cycler reference is correct.
Please identify the applicable version and any corrected files. Our input is
DOI **10.17632/zh58byr53c.2**, 758,227,888-byte Download All ZIP, SHA-256
`1a2b578859bc83bf71a32f5ad0df8841001ec8cb5c2b2c810818cbe746c20fa1`.

## Questions requiring source evidence

1. **What exact processing produces `CurrentA_Cell_1..4` from the raw Hall
   channels for each test?** Please provide executable MATLAB scripts,
   coefficients/units, calibration-file IDs/dates, reference instrument, fit
   domains, intercept handling, supply and temperature compensation, filtering,
   clipping and alignment. Could you reproduce one complete step-5 segment and
   a rest-to-load edge? Nominal H1-H4 linear reconstructions do not reproduce the
   supplied currents; our matrix checks H1-H8 without assigning substitutes.

2. **Which physical sensor and acquisition channel occupied each position?**
   Please supply run logs or a labelled map connecting `Aux_Voltage(V)_1..5`,
   H1-H8, `CurrentA_Cell_1..4`, cell IDs and thermocouples. Confirm the Hall supply
   channel, directions, replacements, and module-current measurement location
   relative to rails/auxiliary paths. Nominal M1 mapping is H1-H4; values alone
   cannot verify file-to-hardware identity.

3. **What establishes the module-current reference and its uncertainty?**
   Please identify cycler model/channel/range, firmware, calibration certificate,
   gain/offset/range switching and uncertainty around 6.47 A charge and 14.55 A
   discharge. Confirm whether exported current is measured or setpoint, and the
   timing convention. Do `Current(A)` and `Discharge_Capacity(Ah)` use the same
   ADC/reference? Is an independent calibrated shunt trace available? The counter
   agrees with its own current integral but does not establish absolute accuracy.

4. **What explains the opposite-sign current-sum discrepancies?** Test 53,
   Data rows 13317-18751: discharge-positive Hall sum minus module mean
   -1.6832915321 A, RMS 1.6858798704 A. Test 28, rows 22340-26563: mean
   +1.5479236509 A, RMS 1.5510595031 A. Rest means are near zero. A separate
   MAT/XML calculation reproduces the earlier audit. Sign, units, permutation
   and +/-10-sample shift checks do not resolve this. Please provide a
   reproducing explanation or versioned correction, rather than normalization
   to expected capacity.

5. **What schedules and initial-state conditions were actually used?** Please
   provide native schedule files and completion/abort logs. Tests 53/28 have
   initial rests about 30/240 min, post-discharge rests about 45 min and CV
   endpoints about 1 A, differing from the article's 90/60 min and 0.2 A.
   Confirm termination reasons, previous charging and thermal equilibration.
   For OCVDis and HPPC/MS, confirm initial SOC preparation, current/voltage
   calibration, temperature-sensor placement and any equilibrium criterion.
   We currently treat OCVDis as C/20 loaded voltage, not equilibrium OCV.

6. **Separately, was test 32's fourth cell actually Y1?** The Unaged label and
   P20/P11/P17/Y1 metadata conflict. Please supply a placement log or erratum.
   This run stays quarantined and is not used to explain tests 53/28.

## Evidence prepared for a future authorized message

- `RECONCILIATION.md`: confirmed observations, tests and unresolved hypotheses.
- `independent_results.json`: full member paths/hashes, shared-channel comparisons,
  step statistics, sign/unit/shift checks, calibration coefficients and candidate
  sensor matrix.
- Both `*_residual.csv` files: original Excel/MAT row, elapsed seconds, module
  current, Hall sum and residual; no fitted correction.
- Both `*_independent.png` figures and `scripts/reconcile_independent.py`.
- Original `reports/module_audit.json` and `hall_calibration_audit.json` for
  protocol and supply-aware reconstruction checks.

| File | SHA-256 |
|---|---|
| M1_NMC_Unaged_R0_T25.xlsx | `4596d3fed65277b548176bca7dd3dfa9efcd0bd2167722effc87ac38975c24bc` |
| M1_NMC_Unaged_R0_T25.mat | `fa9e2344a40bf796fbb5aadec0aaf61885472ac16798023604f9dc3e45650f84` |
| M1_NMC_Unaged_R3_T25.xlsx | `8356496b3fd5c8519165f597959e103fd1247e1a9cf4db36deb14776c66568d1` |
| M1_NMC_Unaged_R3_T25.mat | `85076072c6057d11e3ddb793b5ae47d8d0065d3148fbd208de968f65a4a6cb1b` |

This is local preparation only. No email, external message or upload was
performed. No response or external explanation is currently available.
