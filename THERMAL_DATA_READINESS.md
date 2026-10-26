# Thermal data readiness

The dedicated electrothermal engineer has implemented a bounded importer for
the already designated **cell-1 test-103 development experiment**. The
[engineering decision](reports/thermal_m50t_import_v1/DECISION.md) records its
findings; the [original intake](reports/thermal_m50t_intake_v1/DECISION.md)
and all frozen models remain preserved.

The importer reads the three related thermal/electrical/MATLAB files with
explicit units, exact channel checks and original timestamp preservation.
The author-processed cell temperatures can be related to the raw measurements,
including fixed offsets. Those transformations are processing evidence, not
independent sensor calibration.

The recorded current profile contains six roughly eight-hour bipolar blocks.
Five following rests last about 90 minutes; the final rest is cut short by the
end of the record. These are development coverage findings, not an assessment
of a predictive model. The two instruments' clock alignment remains unresolved.

**No physical thermal parameters have been fitted or adopted.** Author-derived
heat fields exist, but their calibration and processing definitions are not
fully established. Heat rejected by the fin cannot automatically be used as
transient cell heat generation. The synthetic heat-balance prototype and frozen
electrical model remain unchanged; module thermal prediction is unavailable.

Four cell-1 experiments remain unused development reserves, and all six cell-2
experiments remain unopened assessment reserves. No current module validation,
temperature safety margin, battery-performance gain or repair ranking follows
from this work. Application temperature/error requirements remain unset.

Next: resolve the heat/temperature processing definitions, calibration and clock
provenance before physically scaled thermal identification. If the necessary
evidence cannot be recovered from public documentation or the designated
development record, obtain the authors' processing/calibration files or another
public dataset with a supported heat input. No outreach was sent.

See the [engineering decision](reports/thermal_m50t_import_v1/DECISION.md) for
reproducible commands, diagnostic plots and the precise remaining questions.
The [reviewed handoff](reports/thermal_m50t_handoff_v1/READINESS.md) records
the 89 passing focused tests and the combined replay/preservation check.
