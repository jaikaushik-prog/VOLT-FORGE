# VOLT-FORGE local workspace

27 October 2026. The workspace connects a four-cell battery design to its simulated current, voltage and surface-equivalent temperature. It uses the existing frozen electrical models and declared one-way thermal assumptions. Experimental module and thermal validation remain pending.

## Open the application

On the current Mac, from the repository root:

```bash
PYTHONPATH=src .venv/bin/python scripts/run_editor.py --project workspace/editor_project --port 8792
```

Open **http://127.0.0.1:8792**. The project persists under `workspace/editor_project`, which Git ignores. Stop the server with Ctrl+C. A new working project can use another `--project workspace/name` and `--port` value. The general launcher defaults to port 8765. Python 3.12 and the pinned requirements are needed; there is no frontend build step or runtime internet dependency.

The Measurements link opens the separate P45B source viewer. It does not run the LG model against P45B data. Its existing scope and source-access allocation remain in [the measurement guide](reports/measurement_viewer_v1/USAGE.md).

## Work through an experiment

1. **Set the operating conditions.** The properties pane starts with current and duration. Add intervals for a changing load or rest. Positive current discharges, negative current charges and zero current rests. Starting temperatures, limits and advanced model settings are available under Configure.
2. **Preview and save a change.** Preview shows the proposed input and which results become outdated. Exact units, provenance and evidence notes are available underneath. Save creates the revision. A visible unsaved edit cannot become a simulation input; Run remains disabled until it is saved or discarded. Component selection retains a local draft, and leaving the page warns about unsaved drafts.
3. **Run the selected design.** Whole-run extrema and delivered energy appear below the assembly. The assembly opens at the final saved time so you can see the calculated differences immediately. The time slider and selected-component readout show a specific saved instant. Four summary values lead; additional metrics and one selected chart are under Explore charts.
4. **Inspect a component.** Select it in the assembly/circuit or Designs & components menu. A cell exposes starting charge/polarization and its read-only fitted model. A connection exposes effective resistance in mΩ. Geometry is illustrative and moving the circuit drawing changes no physical parameter.
5. **Investigate conditions.** Configure a sourced limit, then open Investigate. Select connections and resistance additions. The preview states the real case count and budget. Load and ambient variations are under advanced conditions. Ambient tests also start all cells at the selected ambient. Results apply to the finite evaluated set. Open a case as a variant to run it normally.
6. **Compare designs.** Select completed saved runs under common operating conditions. Six main metrics show alternative minus reference; power, losses, requirements and exact evidence are available below. Changed load, initial state, thermal parameters or software cannot silently enter a like-for-like comparison.
7. **Export results.** Choose explicit saved runs, prepare the package and download it. It includes the recorded inputs, outputs, model/source references, source snapshot and replay code. In the extracted folder run `python replay.py RUN_ID` with the recorded Python environment. Reproduction verifies software output, not experimental accuracy.

Designs & components also creates a separate variant. Inherited runs stay historical; they never become current owned results automatically. Closing Properties gives the canvas more width. On narrower screens the pane moves below the workspace; Edit operating conditions and selecting a component bring it into view. The assembly can scroll sideways without forcing the page to overflow.

## Read results correctly

- **Current** means the selected design, scenario and captured software still match. It does not establish validation or acceptance.
- **Outdated** results are retained and explicitly labelled. Rerun for the edited design.
- **Stopped/partial** simulations preserve available samples and their error. They do not become successful results because the HTTP request succeeded.
- **No sampled exceedance** is a finite simulated screen, not a safety pass. A limit needs a documented source. Missing voltage requirements remain unconfigured too.
- **Thermal output** is one surface-equivalent node per cell, with declared heat capacity, ambient/neighbour conductances and rail-loss allocation. It omits reversible heat and temperature feedback to electrical parameters. It is not a prediction of internal temperature gradients.
- Model & evidence contains the selected run's coverage, thermal assumptions, detailed accounting and exact identity. The footer keeps the experimental-validation status visible.

Charts and the assembly use saved solver samples. Large runs page through at most 5,000 samples per window; exports contain the entire saved trajectory. Channel colours have cell identity labels, and overlay text has at least 4.5:1 contrast throughout the current and temperature palettes.

## Supported inputs

| Selection | Editable inputs | Fixed meaning |
|---|---|---|
| Module | Current/duration intervals; ambient and four starting surface temperatures; sourced current, imbalance, temperature and voltage limits; thermal assumptions; solver step | Four fixed LG M50T cells in parallel. Electrical and thermal assumptions stay explicit. |
| Cell | Starting state of charge and polarization, with classification/source | Cell identity, fitted R0/R1/tau, capacity and reference remain read-only. |
| Connection | Effective segment resistance in mΩ, with classification/source | The exact node pair stays fixed. Visual geometry does not infer resistance. |
| Sensitivity experiment | Nominal or a declared sensitivity for the next run | Changes only the effective snapshot. It does not refit the model or create a confidence interval. |
| Display | Assembly/circuit, overlay, selected time, component, optional properties and circuit arrangement | Selection, viewing and layout do not invalidate physics. |

General rewiring, cell substitution, free-form CAD, AI calculation, optimization, multiplayer editing and manufacturing export are outside this demonstrator. Existing schema-1 projects remain electrical-only without silent migration.

## Local adapter and checks

The loopback adapter is `scripts/run_editor.py`. It preserves the existing operation envelope and immutable project records. UI files live outside the solver source tree and do not change captured electrical software IDs.

- `GET /api/session` returns the local process token, project location and current job.
- `POST /api/request` carries inspection, edit preview/save, variants, series, comparison and investigation-record operations.
- `POST /api/jobs` queues a run, finite investigation or export; the client polls `GET /api/jobs/<id>`.
- `GET /api/download/<id>` returns a prepared package. The server chooses export destinations.

POST requires JSON and the session token. The adapter retains loopback binding, foreign Host/Origin rejection, no CORS, self-only CSP and a single writer/worker. It does not remove interrupted-write evidence or locks automatically.

Executed verification is in `reports/v1_release/release_verification.json`. The redesign's browser proof is also copied to `reports/ui_cleanup/verification.json`. Run:

```bash
PYTHONPATH=src .venv/bin/python -m pytest -q --junitxml=reports/v1_release/pytest.xml
node --test tests/editor_state.test.mjs tests/assembly.test.mjs tests/panels.test.mjs tests/workspace.test.mjs
.venv/bin/python scripts/verify_v1_release.py
```

The full browser check is `scripts/check_v1_browser.py`, followed by `scripts/check_workspace_forms.py` for property mappings and `scripts/check_workspace_render.py` for final layouts. All three run through the installed browser harness against a **fresh disposable** `tmp/v1-release-project...` project. Set `VOLT_FORGE_BROWSER_PORT` when the test editor uses another port. It exercises actual forms, stale runs, component drafts, limits, investigation, case variants, comparison, model evidence, downloaded replay, narrow viewports and keyboard tabs. It never operates on the user's saved project.

The pre-redesign editor and guide are preserved under `reports/ui_cleanup/before_source/`.
