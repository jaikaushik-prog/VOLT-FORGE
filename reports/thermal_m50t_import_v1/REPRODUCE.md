# Bounded development import commands

Run from the repository root in PowerShell. Use a new output directory each time;
the importer refuses to overwrite previous runs. Raw `M50.zip` must already be
present at its recorded path and match the pinned SHA-256. No download, network
request, parameter fit or additional characterization access occurs.

```powershell
$env:PYTHONPATH='src;scripts'
& C:/Users/DELL/anaconda3/python.exe -m pytest tests/test_thermal_m50t_development.py -q
& C:/Users/DELL/anaconda3/python.exe scripts/import_thermal_m50t_development.py --out data/processed/thermal_m50t/my_test103_replay
& C:/Users/DELL/anaconda3/python.exe scripts/import_thermal_m50t_development.py --verify data/processed/thermal_m50t/my_test103_replay
```

To verify the completed handoff run locally:

```powershell
& C:/Users/DELL/anaconda3/python.exe scripts/import_thermal_m50t_development.py --verify data/processed/thermal_m50t/import_004
```

`--verify` returns one JSON object with `status: verified`, exact report/array
replay and output hash counts, or raises a specific mismatch error. It rereads only
the same three permitted test-103 members. It checks the implementation and
procedure hashes, retained original-source hashes, all nine output hashes, report
equality, and every preserved numeric/timestamp array. An existing run is not
reused as fresh assessment.

The environment already supplies numpy, pandas, h5py, matplotlib and pytest;
versions are recorded in `verification.json`. No dependency lists were modified.
Historical implementation snapshots are provenance, not alternative entry points.

| Output | Meaning |
|---|---|
| `schema.json` | All raw fields/units; public instrument program; MAT labels and original shapes |
| `quality.json` | Timing quality, representation checks, author-field algebra, unresolved alignment |
| `coverage.json` | Native polarity evidence, preparation, all six pulse/rest coverage boundaries and unsupported transfers |
| `report.json` | Combined schema/quality/coverage, every active/rest region, all endpoint charge/work accounting |
| `imported_arrays.npz` | Local-only full raw arrays, original electrical timestamp strings and unmodified author numeric arrays |
| `*_record.png`, `processing_diagnostics.png` | USED DEVELOPMENT diagnostics; separate instrument origins |
| `started.json` | Implementation/procedure hashes recorded before numerical member reads |
| `manifest.json` | Three opened member hashes, source/allocation hashes and generated output hashes |
| `failure.json` | Created on a failed attempt; no previous outputs are overwritten |

The electrical NPZ array columns are derived elapsed seconds, recorded V,
recorded mA, and the unlabelled field. Its original calendar strings are a separate
array. Thermal columns retain their exact 16-column raw order. MAT arrays retain
HDF5 storage order, with `mat_` prefixes. No units are assigned to unexplained MAT
heat fields. No cold-junction channel is designated ambient. Run plots and public
diagnostic JSON are copied into this report folder; full arrays remain ignored.

`verification.json` uses `artifacts_sha256` for repository-relative handoff files,
`sources_sha256` for raw inputs, `source_members_sha256` for the three allowed
ZIP members, and `local_outputs_sha256` for ignored full-run outputs. Receipt
hashes verify integrity; they are not a statement of experimental model validity.
