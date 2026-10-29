# VOLT-FORGE V3

Build an editable battery circuit, test it, investigate its limits, compare a change and export the experiment.

## Open the studio

Use Python 3.12. Extract the complete source bundle or clone the source checkout. Run these commands from its root:

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python scripts/run_editor.py --project workspace/my_project --port 8794
```

Open <http://127.0.0.1:8794>. No frontend build, original research archive or AI connection is needed to build circuits and run calculations. Keep the complete source folder: its reference assets are part of the application. A Python wheel alone is not the studio distribution.

On Windows, use `.venv\Scripts\python.exe` in place of `.venv/bin/python`. The current release checks run on macOS with Python 3.12; a separate Windows execution check is still needed before claiming platform qualification.

The copilot uses an installed, authenticated Codex or Claude CLI with available usage. Credentials stay with that local CLI. The release includes no account credentials. A live comparison explanation was checked through the actual interface.

## First experiment

1. Open the four-cell example, or use **Help → Try the guided example**. The guide creates its own editable design.
2. Select a cell to see its illustration and edit starting charge or temperature. In Circuit, change actual terminal connections and battery outputs. Dragging changes the drawing position.
3. In Test, set total current, duration and room temperature. Add changing load intervals, design targets or optional monitoring when useful.
4. Run the calculation. Inspect a chart with the pointer, keyboard or time slider. Read the recorded values and calculated insights.
5. Use Find limits to test higher demand, a warmer room or a poorer connection. Open a case as a separate editable design.
6. Compare saved experiments under matching conditions. The copilot can explain the recorded comparison and propose changes for review.
7. Export the report, data, models and replay script. Saved designs stay in the chosen project folder.

## What V3 adds

- Up to 16 cell instances and 80 links, with series, parallel, mixed and blank starting points. Assembly and circuit views use the same design.
- Published temperature-dependent LG M50T parameters and a separately fitted Samsung 30T model. Original four nominal-temperature profiles remain available for historical studies.
- Custom cells with four initial inputs: name, capacity, nominal voltage and DC resistance. Temperature estimates can use the recorded example heat properties, user-supplied properties or electrical-only mode. CSV voltage references and declarative JSON lookup models can be imported and saved as new versions.
- Coupled electrical and lumped thermal calculations, changing current profiles, per-cell operating limits, event-aware results and explicit partial-duty outcomes.
- Dimensioned copper links and external output routes. Their resistance, contact assumptions, losses and material mass affect the calculation. Canvas pixels are separate from physical dimensions.
- Virtual per-cell sensing, bias, sample interval and delayed external disconnect. Internal parallel-cell circulation continues after that ideal disconnect.
- Immutable experiments, stale-result detection, recoverable saves, paired design comparisons, a real AI copilot and portable numerical replay.
- A seven-step walkthrough with real calculations, resume, comparison, live AI and export.

## Scientific basis

The model and source records are in [SCIENTIFIC_SOURCES.md](third_party/SCIENTIFIC_SOURCES.md), [cell_catalogue_v1.json](configs/cell_catalogue_v1.json) and [thermal_sources_v1.json](configs/thermal_sources_v1.json). Each exported experiment captures the actual models, heat properties, instance overrides, operating requirements and solver source used.

The new LG model uses whole-cell three-branch electrical tables from pinned PyECN source. Its heat-capacity reference is 58.5 J/K from published measurements of the exact M50T model. Its default cooling value is a separate effective fixture estimate fitted with recorded changing ambient temperature and independently supplied heat capacity. The sensitivity study carries the observed spread in cooling estimates into the design comparison.

The Samsung electrical model has its own public calibration records and retained development results. Failed cold-condition assessments remain excluded. Its heat properties remain assumptions. The application enforces each model's recorded cell-temperature and charge range. Room temperature is a separate boundary condition; there is no universal 22–28 °C battery restriction.

Independent synthetic electrical checks against native PyBaMM and closed-form solutions pass for charge, discharge, rest and several relaxation orders. Separate SciPy ODE checks cover state-dependent coupled feedback. A baseline and two physical alternatives were evaluated in 31 paired scenarios and repeated at half the solver step: 186 calculations. The report in `evidence/engineering_decision/` contains the conditional recommendation, reversals and numerical resolutions when the evidence bundle is supplied.

This evidence establishes traceable parameter sources, numerical verification and conditional design comparisons. Independent measured module accuracy remains an open Round 2 task. The illustrative assembly is not manufacturing CAD. Spatial/core temperature, fluid flow, mechanical stress, ageing, runaway and qualified protection hardware are outside this release.

## Reproduce an exported experiment

Extract its ZIP, create a Python 3.12 environment with its captured requirements, and run:

```sh
python -I replay.py
```

The replay checks the saved numerical samples. The accompanying HTML report explains inputs, results, targets and source assumptions. It does not need the original project folder or live AI.

## Software checks

```sh
.venv/bin/python -m pytest -q
node --test tests/*.test.mjs
```

The latest full backend run has 393 passes and eight skips requiring the original historical research archive. The complete JavaScript suite and browser workflow records accompany the local release evidence. Those data-dependent skips are reported separately from executed checks. Use the clean-install record to verify the exact bundle and runtime that were exercised.
