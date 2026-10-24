# Local 2D four-cell workspace

The editor runs the existing frozen-v2 project backend. It is a local, single-user
electrical workbench, not experimental module validation. No new production
dependencies, frontend build step or internet connection are required after the
repository's Python requirements are installed.

## Start

The **Measurements** link opens a separate P45B source-data viewer at
`/measurements`. It reads allocated ID01 only and does not run the LG model on
P45B measurements. See [measurement guide](reports/measurement_viewer_v1/USAGE.md)
for source-folder setup, sensor/sample controls, exports and access restrictions.

From the repository root, using its existing Python environment:

```powershell
& C:\Users\DELL\anaconda3\python.exe scripts\run_editor.py --open
```

Or, with an equivalent Python 3.12 environment, `python scripts/run_editor.py --open`.
Open **http://127.0.0.1:8765**. Stop the server with Ctrl+C. Change the port with
`--port 8766` if needed. The default project is `workspace/editor_project`, which
is ignored by Git. Restarting reopens it. To start another working project:

```powershell
& C:\Users\DELL\anaconda3\python.exe scripts\run_editor.py --project workspace\another_project --port 8766 --open
```

The editor rejects working destinations inside reports, raw data or source
directories. It never edits the recorded A0/A1 demonstration. Do not use the same
working project concurrently from another process. A crashed process can leave
the backend's exclusive writer lock: inspect the project and confirm no writer
remains before recovering it; the editor does not silently remove locks.

## Complete the first workflow

1. Run A0. The supplied proposed case is 14.55 A for 360 s, equal initial SOC,
   assumed 23 °C conditions and six assumed 1 mΩ rail segments. Read the exact
   module/cell properties and their provenance in the inspector.
2. Create A1 with the plus button beside Design variants. Its inherited run is
   explicitly outdated. It will not automatically appear as a current result.
3. Select Positive rail 1. Enter **0.5 mΩ**, keep the classification as assumed,
   and record the reason. Preview change, then Apply revision. The preview sends
   0.0005 ohm to the backend. This is a hypothetical connection, not a repair claim.
4. Run A1. Inspect current sharing and cell/module voltage. The time slider uses
   actual saved solver samples. Select a cell for SOC and polarization or a rail
   for current, voltage drop and electrical resistor loss.
5. Open Evidence for requirement results, reference coverage, current ranges,
   fitting and assessment records, contiguous intervals and unsupported transfer.
6. Compare explicitly selected A0/A1 runs. The backend checks equal operating
   conditions; only connection changes qualify for this comparison. Different
   load or initial-state cases can be inspected/exported individually. No
   automatically ranked winner is provided.
7. Export results, select one or both comparable runs, then Prepare download.
   Download the ZIP containing immutable configurations, output CSVs, provenance,
   source snapshots, evidence and replay code. Unzip and run
   `python replay.py run_0001` (use a run ID actually listed in that package).

The run picker includes owner, scenario, completion and freshness. The results
banner and circuit caption label historical or partial results explicitly.
Switching variants automatically chooses only an owned, current run for the
selected scenario. Selecting a sensitivity for the *next* run does not relabel
the displayed old run. A failure retains its error and valid partial samples.

## Exact controls and boundaries

| Component | Editable inputs | Read-only / interpretation |
|---|---|---|
| Six rails | Segment resistance in mΩ; source/classification | Exact node pairs. Geometry does not infer resistance. |
| Four cells | Initial SOC in %, initial polarization in mV; source/classification | LG M50T P7/P17/P19/P13 identities, frozen v2 R0/R1/tau, capacity and voltage reference. |
| Module | Contiguous piecewise load JSON (A, s); ambient/four surface temperature assumptions; dt (s); sourced voltage/excursion requirements | Discharge positive. Temperature does not scale parameters or predict heating. |
| Next simulation | Nominal or one of seven already declared sensitivities | Assumption scenarios, not confidence intervals or replacement models. |
| Display | Select and drag cells; arrow keys move a focused cell; reset layout | Arbitrary coordinates only. Same fixed electrical graph, same revision and freshness. |

Missing minimum voltage, permitted excursion or documented source remains
**requirement not configured**. The illustrative 3.50 V alarm and 25 mV criterion
are not defaults. Engineering acceptance remains **insufficient evidence**.

Plots show up to 5,000 consecutive saved samples per window, with explicit sample
indices and Previous/Next controls. They do not interpolate new physical outcomes
or hide unsupported intervals. Metrics are the backend's whole-record metrics;
failed-run metrics cover only the available partial record. Export contains the
full saved trajectory. Chart colours also have cell identity labels. Keyboard
selection, tab navigation, labelled controls and visible focus are provided.
Narrow screens stack the inspector below results; the schematic scrolls sideways
and a component selector provides access to all cells, rails and the module.

No thermal solver, general rewiring, cell substitution, broad CAD, AI calculation,
optimizer, multi-user service or measurement-upload screen is included. The
existing measurement-import CLI/API remains available under its documented
provenance and calibration rules. No protected outcomes are opened by the editor.

## Local HTTP adapter

The adapter lives in `scripts/run_editor.py`, outside the solver source tree.
UI changes therefore do not change captured electrical software IDs. The
browser uses the unchanged `voltforge.project/1` contract:

- `GET /api/session`: per-process token, working-project location and active job.
- `POST /api/request`: `inspect`, `validate_edit`, `apply_edit`, `create_variant`,
  `update_display`, `get_run`, `series`, `compare` with the existing JSON envelope.
- `POST /api/jobs`: `run` with variant, expected revision and optional scenario;
  or `export` with explicit selections. Returns `{status:"ok",result:{job_id}}`.
- `GET /api/jobs/<id>`: queued/running/completed/failed plus the exact backend
  response. A successful transport can still contain a failed simulation.
- `GET /api/download/<id>`: the generated reproducible ZIP. Destination paths
  are server-selected, never browser-supplied. Job/download IDs are session-local;
  saved runs and generated exports persist on disk after restart.

POST requests require JSON and `X-Voltforge-Token` from the session response.
The server binds only to 127.0.0.1, rejects foreign Host/Origin and arbitrary file
routes, has no CORS, uses a self-only content security policy and one job worker.
This is not an authentication system or deployment architecture. Do not expose
the server through a public proxy. Other same-machine processes are trusted.

## Reproduce checks

Use fresh output paths to preserve release evidence:

```powershell
$env:PYTHONPATH = 'src'
& C:\Users\DELL\anaconda3\python.exe -m pytest -q --junitxml=tmp\editor_pytest.xml
& 'C:\Program Files\nodejs\node.exe' --test tests\editor_state.test.mjs
& C:\Users\DELL\anaconda3\python.exe scripts\check_editor_browser.py --out tmp\editor_browser_check
& C:\Users\DELL\anaconda3\python.exe scripts\verify_editor_release.py --out tmp\editor_verification.json
```

The optional browser check uses installed Chrome and the development-only
`websocket-client` package. It launches an isolated headless profile, exercises
the real DOM/HTTP workflow, captures desktop/mobile screenshots, rejects invalid
edits and replays both downloaded full-duration runs. It never accesses an
existing browser account. Set `--chrome PATH` if Chrome is elsewhere. Node is
needed only for the four presentation-state tests, not to serve the application.
