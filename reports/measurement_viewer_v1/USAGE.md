# Read-only P45B measurement workflow

From the repository root in PowerShell:

```powershell
& C:\Users\DELL\anaconda3\python.exe scripts\run_editor.py --open
```

Open **http://127.0.0.1:8765/measurements**, or click **Measurements** in the LG
editor. An already-running older server must be stopped and restarted to load
new routes. ID01 opens automatically; other tests are disabled. Inspect current,
voltage and any source sensor, move the sample slider or enter a sample index,
and export the summary/provenance or original CSV. No prediction is displayed.
The original download must be extracted as `1s4p Battery Module Measurement/`
under the repo root. Missing or changed source files produce explicit errors.
Raw files stay ignored by Git; download them from DOI 10.5281/zenodo.18405243.

Reproducible commands (choose new output files to preserve earlier receipts):

```powershell
& C:\Users\DELL\anaconda3\python.exe scripts\measurement_viewer.py catalogue
& C:\Users\DELL\anaconda3\python.exe scripts\measurement_viewer.py summary --record ID01 --out tmp\p45b_summary.json
& C:\Users\DELL\anaconda3\python.exe scripts\measurement_viewer.py rows --record ID01 --offset 600 --limit 1 --out tmp\p45b_row600.json
$env:PYTHONPATH = 'src'
& C:\Users\DELL\anaconda3\python.exe -m pytest tests\test_measurement_viewer.py tests\test_editor_server.py tests\test_freetwinev_inventory.py -q
& C:\Users\DELL\anaconda3\python.exe scripts\check_measurement_browser.py --out tmp\p45b_browser
& C:\Users\DELL\anaconda3\python.exe scripts\verify_measurement_release.py --out tmp\p45b_release_check.json
```

Browser verification needs local Chrome and the optional `websocket-client`
package already available in the development environment. Runtime adds no new
dependency. Synthetic tests do not open the actual measurements; the browser
script reads the explicitly allocated ID01 only. The preservation command hashes
raw/protected files without decoding their outcomes.

## Additive HTTP interface

Same local-only host/origin policy as the editor. GET responses have
`{"status":"ok","result":...}` or
`{"status":"error","error":{"code":"...","message":"..."}}`.
No arbitrary file path or raw-data upload endpoint is exposed.

| Request | Response |
|---|---|
| `GET /api/measurements` | Metadata-only catalogue, allocation hash, access statuses and limitations |
| `GET /api/measurements/ID01?view=summary` | Ranges, sampling diagnostics, units, limitations and source/parser/allocation hashes |
| `GET /api/measurements/ID01?view=overview&bins=250` | Summary plus per-channel plot points `[elapsed_s,value,source_line,segment]` |
| `GET /api/measurements/ID01?view=rows&offset=600&limit=1` | Exact consecutive source rows; offset is zero-based; next_offset supports paging |
| `GET /api/measurements/ID01/original` | Original byte-exact CSV attachment |
| `GET /api/measurements/ID02` | HTTP 403, `protected_record`; also enforced on original download |

`view` defaults to `overview`; `offset>=0`, `limit=1..1000`, `bins=10..1000`.
Duplicate/unknown query parameters are rejected. Unknown IDs return 404;
changed source/allocation hashes return 409; missing original returns 404 with
download instructions. Source parsing errors return 400. Numeric calendar-date
conversion, guessed units and missing-data imputation are deliberately unsupported.

`ID01_summary.json` and `ID01_row600.json` in this report directory are generated
from these methods, not handwritten examples. The row contains source values,
source line and raw timestamp text. All channel values retain source units; only
elapsed time and summary/plot-selection metadata are derived. Complete original
CSV bytes are available through the download endpoint.

These routes are separate from `voltforge.project.compare_measurements`.
That comparator's required LG sensor/channel contract remains unchanged. Saved
simulation runs, freshness, physics hashes and fitted artifacts are unaffected.
