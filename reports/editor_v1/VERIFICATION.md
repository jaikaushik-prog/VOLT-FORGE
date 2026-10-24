# 2D electrical editor verification

The editor connects to the existing project contract without modifying electrical
source, models, previous runs or data. This release adds interface behaviour and
local transport, not experimental accuracy.

## Checks

- **117 Python tests passed**, including 17 new HTTP integration/guard tests and
  the previous 100 scientific/project checks. See `pytest.xml`. An additional
  targeted partial-result assertion passed in `partial_result_pytest.xml` after
  the full run; it checks that an undefined SOC stops before a complete trajectory.
  The final 17 transport tests were rerun after disabling Windows address reuse;
  `transport_final_pytest.xml` also checks rejection of a duplicate server port.
- **4 JavaScript presentation tests passed**, covering explicit run selection,
  sensitivity/ownership isolation, late-response epochs, escaped user content,
  finite numerical input, chart scales and readable failure messages. See
  `node_tests.txt`.
- **9 real-browser workflow observations passed**, using a separate headless
  Chrome profile and the real local HTTP adapter. No existing browser login was
  accessed. Full 360-second A0 and A1 simulations were run, a 0.5 mΩ p1–p2 edit
  was validated/applied, inherited results stayed outdated, a layout move kept
  physics current, current/voltage samples and rail readouts were inspected,
  negative resistance was rejected, explicit runs were compared, unknown voltage
  requirements stayed blank, and the 390 px layout had no document overflow.
- Both runs in the **browser-downloaded export replayed in separate Python
  processes**, with the existing numerical comparison tolerances. This verifies
  reproducibility, not measurement accuracy.
- A deliberately unsupported **1000 A software fixture** demonstrated a failed
  run at reference support, partial samples and the recorded stop reason. Its
  extreme numerical voltages/currents are unsupported model extrapolation and
  are not battery operating recommendations or physical validation.

The browser caught an HTML pattern syntax issue in Chrome's Unicode regular
expression mode; the escaped identifier pattern was corrected. Visual review
also replaced a long JSON failure banner with its stop time and reason, retaining
full details under Evidence. Desktop charts have labelled cell colours and units;
mobile uses a scrolling circuit plus a selector for all components.
Windows permits ambiguous duplicate listeners when both sockets use SO_REUSEADDR;
the adapter disables it so a second server fails instead of serving another
project from the same address. This transport correction does not change physics.

Final browser evidence is in [browser_acceptance/verification.json](browser_acceptance/verification.json).
Screenshots: [results](browser_acceptance/08_final_desktop.png),
[outdated revision](browser_acceptance/03_outdated_revision.png),
[evidence](browser_acceptance/05_evidence.png),
[comparison](browser_acceptance/06_comparison.png),
[mobile](browser_acceptance/07_mobile.png),
[failed run](browser_acceptance/09_failed_run.png).

## Simulation comparison observed in the interface

Identical nominal operating conditions; A1 changes only the positive p1–p2 rail
from an assumed 1 mΩ to an assumed 0.5 mΩ.

| Simulated quantity | A0 | A1 |
|---|---:|---:|
| Maximum branch current (A) | 4.666864 | 4.526947 |
| Minimum terminal voltage (V) | 3.633225 | 3.637121 |
| Mean delivered power (W) | 53.688737 | 53.744324 |
| Delivered net energy (Wh) | 5.368874 | 5.374432 |
| Rail electrical loss (Wh) | 0.033778 | 0.028614 |
| Device requirement | Not configured | Not configured |
| Engineering acceptance | Insufficient evidence | Insufficient evidence |

These reproduce the previous project demonstration. They are a simulation
comparison, not demonstrated repair benefits or battery-performance gains.

## Preservation and remaining evidence

`scripts/verify_editor_release.py` verifies the 112 baseline protected artifacts,
the original archive hash, the previous module release and product-handoff
manifests, and the unchanged freshness of the sealed A0/A1 demonstration. Exact
previous bytes of the three living documents changed in this sprint are retained
under `previous/`. Prior manifests/test XML were not regenerated or overwritten.
No new measurement outcomes were opened. All nine unused characterization cells
and protected module assessment records remain reserved.

Experimental module validation is **awaiting suitable measurements**. Still
needed: actual load/device voltage and excursion requirements, traceable sensor
mapping/calibration, measured connection resistance, synchronized module/branch
current and defined-location voltage, temperature history and charge/rest
preparation. The module-current discrepancy remains unresolved. No outreach was
sent. Thermal modelling, arbitrary CAD, AI optimization and a measurement-upload
screen remain outside this editor release.

The next milestone is a focused usability review and a guided measurement-import
view over the existing backend, with sensor-location mapping and completeness
checks. Scientific acceptance must wait for suitable external evidence.
