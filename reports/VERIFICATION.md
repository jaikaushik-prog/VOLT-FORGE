# Verification completed 24 October 2026

## Executed checks

```powershell
$env:PYTHONPATH = 'src'
& C:\Users\DELL\anaconda3\python.exe -m voltforge.data.cli all
& C:\Users\DELL\anaconda3\python.exe -m pytest -q
& C:\Users\DELL\anaconda3\python.exe -m compileall -q src tests
```

- Full pipeline completed successfully with the supplied archive, and completed
  again after adding charge-throughput diagnostics and per-member source metadata.
- All 194 members passed ZIP CRC reads and received SHA-256 hashes. The original
  archive hash was checked again by the audit guard; original bytes were unchanged.
- Metadata decoding succeeded for all 54 experiments; all 18 NMC cell lists
  match the article's independently transcribed Table 5.
- Raw/processed equality checks passed for both audited runs for all shared
  physical channels, time and flags. Published branch amperes are distinct from
  raw Hall voltages and are not claimed to have passed a calibration check.
- **14 tests passed, zero failures, zero skips**, in 22.38 s on the final
  scientific-check run. This includes real-data integration tests using the
  archive, not just synthetic fixtures.
- Python source compilation completed without errors.
- Six measured-data PNGs were generated and visually inspected: full cycle,
  discharge and current-conservation residual for each of the two runs.
- Local links in the README and data-readiness report were checked.
- Frozen split assignments are disjoint by whole experiment, including the
  quarantine; archive/config hashes are enforced. The final-assessment traces
  remain outside the signal-audit scope.

## Meaning and limits

These results establish executable ingestion, source traceability, inspected
schema agreement, unit/sign behaviour, timestamp diagnostics and reproducible
plots. They do **not** establish accuracy of the supplied sensors or a battery
model. Current conservation, calibration reproduction and nominal protocol
agreement remain unresolved scientific findings, documented without forcing
them to pass an invented acceptance threshold.

The MATLAB table adapter deliberately supports the observed version-2 layout
and uses SciPy 1.13.1's private reader. Future SciPy or archive schema changes
need renewed integration checks. A fresh online dependency installation was not
tested; the pinned versions were verified in the existing Anaconda environment.

The archive was supplied manually through the official website because direct
network retrieval was blocked. No publisher-signed checksum, calibration
processing scripts, experiment schedule files, or complete sensor uncertainty
budget were available in the archive. No model fitting, deployment, external
outreach or repair ranking was performed.
