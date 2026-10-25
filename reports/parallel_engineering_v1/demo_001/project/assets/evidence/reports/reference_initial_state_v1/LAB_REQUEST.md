# Faculty/lab discussion brief — prepared, not sent

We are developing VOLT-FORGE, a research model of a 1s4p LG M50T NMC module.
We seek help establishing which engineering decisions the model can support,
and access to documented measurements or a suitable supervised test facility.
We are not requesting confirmation of a claimed battery-performance gain.

## Evidence and questions to bring

- The current single-cell model reduces prediction RMSE on its specified
  characterized-cell subset by 55%; full-record errors reach about 97 mV.
  It is not experimentally validated as a module model.
- Absolute initial SOC is confounded with the voltage reference's SOC origin.
  Existing late rests have small final-window drift but substantial voltage
  errors between sparse reference anchors. We need traceable charge preparation,
  capacity/current integration and denser rested-voltage observations, including
  around SOC 0.2 and the eventual load-voltage decision region.
- Independent calculations reproduce opposite-sign current-sum discrepancies:
  mean -1.6833 A on M1 R0 T25 and +1.5479 A on M1 R3 T25. We cannot establish
  whether Hall conversion, the cycler reference or another undocumented issue
  explains them. Both current sources remain uncertain.
- Please help identify the actual load/device minimum voltage, allowed
  excursion duration and consequences of an incorrect clearance. The project
  has used 3.50 V and 25 mV only as illustrative criteria. A 1s4p module is a
  cell-voltage source; any converter requirement must be specified.

## Useful evidence or capabilities

1. **Existing dataset provenance first:** executable Hall conversion/filtering
   code, per-run coefficients and sensor-position mapping; cycler measurement
   versus setpoint definition; range/calibration records and uncertainty;
   time alignment; native schedules and charge/rest preparation logs. The
   [author packet](../reconciliation/AUTHOR_QUESTIONS.md) supplies exact source
   hashes, run identities, row ranges and six focused questions.
2. **If provenance cannot resolve the discrepancy:** calibrated simultaneous
   module and four branch currents, voltage at defined electrical nodes, shared
   timing/trigger information, interconnect/contact characterization and surface
   temperatures. Retain original raw exports and calibration information.
   Neither current channel should be rescaled merely to enforce conservation.
3. **Cell-reference and starting-state observations:** reproducible preparation
   with documented charge termination, rest duration and drift, measured capacity,
   known current uncertainty and repeat observations. Establish whether nominally
   equal starting states are actually comparable between cells and records.
4. **Application coverage:** assess the 14.55 A, 360 s intended waveform and
   justified initial imbalance. Equal sharing is 3.6375 A; a software scenario
   reaches 5.35 A in one branch, beyond the existing approximately 4.85 A
   six-minute plateau. The lab should determine feasible branch dwell coverage
   and headroom after confirming cell specifications, fixture, equipment and
   protection limits. This brief is not a bench operating procedure.

Please indicate whether suitable records, instrumentation and supervision are
available, or suggest a collaborator who can help. Agree the decision and an
uncertainty budget before setting the validation criterion. Preserve complete
sequences for final assessment before fitting to any new measurements.

Attach or share the [current decision](../../REFERENCE_INITIAL_STATE_DECISION.md),
[current reconciliation](../reconciliation/RECONCILIATION.md), and the author
packet. The original dataset is DOI 10.17632/zh58byr53c.2, with attribution and
retrieval instructions in the project README. No contact has yet been selected
and this brief has not been sent.
