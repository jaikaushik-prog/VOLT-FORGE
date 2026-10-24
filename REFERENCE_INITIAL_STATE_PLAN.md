# Bounded reference and initial-state investigation

25 October 2026. This investigation preserves C2/v2 as the current model.
The reported 55% is a reduction in prediction RMSE on the declared test subset,
not an improvement in battery capacity, energy, power, life or efficiency.

## Scope fixed before calculations

Use P7 first and P13/P19 as replication on already-opened records. Reuse whole
calibration cycles 1/3/5/7/9 and development cycles 2/4/6/8. All these outcomes
are used evidence. Do not open any remaining unused cell or reserved module
outcomes. Preserve P3/P6/P9/P11/P12/P14/P15/P18/P20 for a future allocation.
No fresh assessment is needed to answer this diagnostic question.

Freeze all v2 artifacts, original protected inputs and the current decision
report by hash. The archive remains unchanged. Keep the v2 R0, R1, tau and
capacity fixed: no new circuit elements, thermal law, dynamic refit or production
model replacement. Stop after the following three diagnostics, even if errors
miss the historical proposed budget.

1. **SOC/reference identifiability.** Demonstrate the exact coordinate symmetry:
   z'=z+d and U'(z')=U(z'-d) produce the same voltage. Compare it with the
   fixed-reference +/-0.02 sensitivity. A good voltage fit cannot independently
   establish absolute SOC when the reference's SOC origin is also unknown.
2. **Rest-reference evidence.** Report source rows, elapsed rest time, recorded
   temperature, last-600-s drift slope and changes between the preceding 300 s
   and final 300 s, and between final-300-s and final-30-s medians. Do not convert
   small drift into proof of equilibrium. Compare the sealed rest PCHIP with
   exactly one diagnostic alternative: retain the C/20 curve's shape and add a
   linear correction through the same six 30-s rest anchors, including the
   initial rest. C/20 is loaded voltage; this alternative is not equilibrium OCV.
3. **Bounded alignment profiles.** For each reference, profile one global SOC
   alignment delta over [-0.02,+0.02], 81 fixed points, with and without a global
   voltage offset bounded to +/-20 mV. Estimate these diagnostic calibration
   quantities on permitted calibration voltage only, with frozen RC parameters.
   Use the unchanged v2 primary-domain mask and fixed rows supported throughout
   the delta range. Apply v2 cycle/phase time weights, normalized overall.
   Then score complete used development sequences with continuous within-cycle
   state. The delta/offset are not an independently measured SOC or sensor
   calibration. Report broad profiles, boundary optima and local sensitivity
   correlation; do not expand bounds, add references or promote a winner.

Keep nominal-domain masks fixed for comparisons. Report sample/time RMSE, bias,
maximum error, near-threshold errors, all-record errors and unsupported rows.
Report profile ranges within 5% of minimum objective as descriptive support,
not statistical confidence intervals. Include measured/predicted and residual
plots with source file/row references. Label all alternative results diagnostic
and already-used evidence. Preserve complete state histories; never randomize
timestamp splits or initialize state using development voltage.

## Engineering decision comes before an acceptance requirement

The intended case remains 14.55 A for 360 s in the defined 1s4p module. The
prospective decision is whether that load can be served without crossing the
actual load/device minimum voltage for longer than permitted. The true minimum,
allowable transient duration, consequences of false clearance, and instrument/
initial-state uncertainty are not established in the available project evidence.
Ask for them; continue diagnostics while they are unavailable.

For an agreed minimum Vmin, a conservative clearance requires the predicted
voltage margin to exceed a justified total error bound throughout the relevant
duration. If a decision margin M and other uncertainty allowance B_other are
established independently, the remaining model allowance cannot exceed
M-B_other. Neither RMSE alone nor a margin chosen after seeing test errors
supplies that bound. Avoid double-counting reference/initial-state uncertainty
already represented in model residuals; document dependence before combining
uncertainties statistically.

Keep the historical 25 mV model criterion and 3.50 V example visible as proposed
project criteria. Do not reinterpret them as competition/manufacturer limits,
relax them because v2 missed them, or repeatedly tune toward them without an
application basis. This investigation succeeds by identifying what additional
evidence the decision requires, not by meeting a newly chosen score.

## Parallel measurement work and stopping rule

Prepare a concise faculty/lab brief and refer to the existing author evidence
packet. Do not send outreach. Seek traceable current conversion/calibration,
synchronized module/branch measurements, initial-state preparation and denser
rest-reference evidence. A lab must establish suitable equipment, protection
and permissible cell operating limits before selecting a measurement protocol.
The 5.35 A branch result is a software prediction requiring coverage, not a
validated current requirement or an authorized bench procedure.

Finish with an evidence/decision report, reproducible command, tests, and the
unchanged baseline hash check. If the diagnostics cannot separate physical SOC,
reference error and residual model error, stop there and state the needed
measurement. App, dashboard, optimizer and repair ranking remain paused.
