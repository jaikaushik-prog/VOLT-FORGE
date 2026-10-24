# Sprint verification

24 October 2026. Executed with the existing CPython 3.12.3 / pinned scientific
environment described in the root README.

- `python -m pytest -q --junitxml=reports/sprint_verification/pytest.xml`:
  **34 passed**, no skipped tests, in 45.93 seconds. Includes 14 original tests,
  7 identification/guard tests, 4 separate-reader tests and 9 ladder tests.
- `scripts/reconcile_independent.py`: completed for the two open M1 runs and
  all eight Hall calibration records. Separate residual mean/RMS/max exactly
  reproduce the original audit. No signal correction or data substitution.
- Identification `reserve`, `fit`, `assess`: completed for P7 first, then six
  other inspected cells. Allocation/input hashes precede fitting; fitted models
  and implementation were sealed before assessment scoring.
- Identification `all` replay: existing seal prevented refitting and reproduced
  held HPPC errors. The assessment command checks the implementation, source
  inputs and frozen model hashes.
- `scripts/summarize_sprint.py`: checks raw ZIP hash and 11 protected artifacts,
  compares the two residual calculations, checks per-sample CSV aggregate
  agreement, reproduces analytical ladder examples and regenerates summaries.
- Plots visually inspected: both model behavior and errors for P7 and the
  worst-error cell P4, current-conservation diagnostic, parameter/profile plot,
  aggregate errors and loaded/reference-voltage distinction. Axes carry units;
  whole reserved pulse/rest windows remain visible.

See [results.json](results.json) for preservation/residual/analytical values
and [pytest.xml](pytest.xml) for individual checks. Numeric solver tolerances
are floating-point verification tolerances, not measurement uncertainty.
Experimental ladder/module validation remains pending; the current-reference
blocker and cell-model limitations are documented in the root decision report.
