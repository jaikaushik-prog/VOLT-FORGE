# Addendum: cycle charge balance of the module-current records

25 October 2026. Revised after independent review. An addendum to
[RECONCILIATION.md](../RECONCILIATION.md), which is unchanged. Inputs:

- the two residual CSVs already in this repository (tests 53 and 28);
- the per-cell C/20 capacities in the frozen v2 models.

No new archive member is opened, no trace is rescaled and no channel is admitted.

## The check

Each run contains a discharge to cutoff (step 5), rest and recharge (steps 7–8).
The charge-balance interpretation assumes equivalent initial/final full states from the
nominal charge protocol. Endpoint equivalence has not been independently established here.
Under that assumption the ideal discharged/recharged bound is <=1. Measurement uncertainty,
protocol differences and state preparation must be resolved before using it as an admission test.

Each channel is compared **with itself**:

- A common gain error cancels in the ratio.
- A direction-dependent error (discharge versus charge) does not.

Reproduce with `python scripts/cycle_balance.py`; the output is [results.json](results.json).

| Run | Channel | Mean discharge current [A] | Discharged [Ah] | Recharged [Ah] | Ratio |
|---|---|---:|---:|---:|---:|
| Test 53, M1 R0 T25 | Cycler module current | 14.554 | 21.968 | 19.195 | 1.1445 |
| Test 53, M1 R0 T25 | Hall branch sum | 12.871 | 19.427 | 19.461 | 0.9983 |
| Test 28, M1 R3 T25 | Cycler module current | 14.561 | 17.080 | 18.575 | 0.9195 |
| Test 28, M1 R3 T25 | Hall branch sum | 16.109 | 18.896 | 18.816 | 1.0042 |

## What the numbers establish

- **The two channel groups give different discharge/recharge ratios.** The cycler's ratios differ from unity by +14.5 % and -8.0 %. Test 53 exceeds the ideal <=1 bound under the equivalent-endpoint assumption; test 28's 0.9195 does not violate that bound. The observations motivate directional calibration/protocol checks, not a unique fault assignment.
- **The Hall sums are consistent between directions, to within about 0.5 %.** No uncertainty budget was declared before looking, so that tolerance is descriptive, not a test.
- **In the charge steps, the cycler and Hall readings agree to within about 1.5 %** in both runs.

## Which record is wrong: a supported hypothesis, not a proof

The ratios alone cannot tell which direction is wrong. Two explanations fit them equally:

- **A:** the cycler's discharge record is wrong.
- **B:** both the cycler's charge record and the Hall gain are wrong by similar amounts.

The independent reviewer's counterexample for B reproduces the test-53 totals. An independent
reference is therefore needed.

**Independent comparison: the cells' own C/20 characterization capacities.** These were
measured separately on the single-cell cycler. The sums below provide useful corroborating
evidence, but this work has not established a matched-protocol absolute capacity bound or
a quantitative allowance for the different rate, temperature, endpoints and instruments.
Do not infer a maximum temperature-capacity correction from these two runs.

| Run | Sum of the four cells' C/20 capacities | Hall discharge | Cycler discharge |
|---|---:|---:|---:|
| Test 53 (P7, P17, P19, P13) | 19.395 Ah | 19.427 Ah (+0.2 %) | 21.968 Ah (+13.3 %) |
| Test 28 (P17, P4, P10, P16) | 19.413 Ah | 18.896 Ah (−2.7 %) | 17.080 Ah (−12.0 %) |

- **Test 53:** the cycler discharge is 13.3 % above the separate characterization sum, while the Hall sum is close. This supports investigation of the cycler channel but does not by itself establish absolute Hall gain or rule out every calibration/protocol alternative.
- **Test 28:** both values are below the characterization sum; this comparison does not identify the faulty direction.
- **Across both runs:** cycler discharge error is a plausible working explanation. Its relative likelihood has not been quantified, and independent directional calibration and endpoint checks remain required.

**Conclusion: cycler discharge error remains a working hypothesis, not an established fault diagnosis.** "Hall sum" figures are what those sensors reported, not verified true currents. The ratios do not admit either channel for validation.

## Not established

- **No absolute Hall gain.** A common gain error cancels in the ratio.
- **No root cause** (cycler range calibration, measurement path, processing).
- **No admission** of any channel for validation.

## Consequence for planning

- **Load input.** Do not use the cycler's discharge record as the load input or energy reference for a reconstruction without an explanation.
- **Next steps.**
  - Reconstruct branch currents from the raw `Aux_Voltage` channels with the published Hall calibrations and a declared rest-offset procedure.
  - Run this balance on further runs once they are deliberately opened.
  - Ask the authors about the cycler's discharge range.
- **Labelling.** Any choice of load reference is a declared, pre-fit decision and must be labelled as such.
