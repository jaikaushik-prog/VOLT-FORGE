# Reproducible electrical simulation package

These are simulations, not validated repairs or battery-performance gains.
The frozen cell models and reference arrays are included; no raw archive is needed.
Voltage requirements may be unset. Read each run's summary and coverage evidence.

Use Python 3.12 and the pinned requirements under `software/<id>/requirements.txt`.
Run `python replay.py RUN_ID` from any working directory. The launcher imports the
captured source version for that run. It checks all exported bytes and dependency
versions, reruns the existing electrical backend, and compares every numeric
trajectory column with the saved run (rtol=1e-10, atol=1e-10).
It prints a software reproduction result and never overwrites saved outputs.
Matching calculations do not establish experimental accuracy.

The export manifest hashes every included file except itself. These are integrity
checks, not cryptographic signatures. Source/calibration references are metadata,
not a bundled copy of the original measurements. Inspect `assets/evidence` and
the original source-manifest hashes for experimental limitations and attribution.
