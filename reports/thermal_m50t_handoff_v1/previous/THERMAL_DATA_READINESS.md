# Thermal data readiness

The [M50T intake decision](reports/thermal_m50t_intake_v1/DECISION.md) records the
current status after the public archive download. It supersedes the earlier
"metadata lead only" status without altering the sealed synthetic study.

- Verified archive: 11 experiments, each with three related measurement files.
- Test 103 on cell 1 is used development evidence after a bounded schema probe.
- Four cell-1 experiments remain unused development reserves; all six cell-2
  experiments remain unopened assessment reserves.
- Processed heat-flow fields exist. Calibration, processing definitions, sensor
  mapping and synchronization still need verification before physical fitting.
- The supplement reports a faulty setup and inconsistent temperature labels;
  raw test IDs have not been linked to that fault.
- No fitted thermal model or module temperature prediction has been adopted.

Next: build the bounded test-103 importer and establish the heat-flow conversion
and preparation/clock definitions. If those are not recoverable locally, obtain
the authors' processing/calibration files or another suitable public dataset.
No lab outreach or external AI calls were made.

The [decision report](reports/thermal_m50t_intake_v1/DECISION.md) contains the
allocation, evidence gaps, test results and exact reproduction commands.
