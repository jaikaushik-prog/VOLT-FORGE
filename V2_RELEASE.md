# VOLT-FORGE V2 studio

Snapshot prepared 27 October 2026. This is the modular studio rebuild, built on the preserved electrical-model and project infrastructure.

## What is implemented

- A quiet opening screen with an example, an empty design and the AI copilot.
- Build, Test and Results as the main workflow.
- Add and remove cells, wire their terminals, place the output terminals, move components and undo edits. The circuit solver consumes the actual connection graph. Supported graphs can contain up to 16 cell instances and 80 links, using the four available LG M50T sample profiles.
- A synchronized illustrative assembly view. Moving a component changes its position; wiring and thermal-contact inputs retain separate physical meanings.
- A selected-cell illustration and contextual charge, temperature and connection controls.
- Editable test duration and changing current profiles. Duration is not fixed to the six-minute example. The solver enforces its sample and model-domain limits.
- Interactive current, voltage and temperature charts, with numeric probes, a pinned time, keyboard navigation, series controls and values linked to the assembly.
- Calculated insights, guided connection-wear experiments, named test history, comparison and report/data export.
- A real AI copilot through a locally installed, authenticated Codex or Claude CLI. It can explain project context and propose typed edits. The user reviews a proposal before applying it. Numerical results come from the solver.
- Additive import of earlier saved designs. Existing project records and frozen scientific artifacts are retained.

## Open V2

Use Python 3.12. From the repository root on macOS or Linux:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
PYTHONPATH=src .venv/bin/python scripts/run_editor.py --project workspace/editor_project --port 8792
```

Open <http://127.0.0.1:8792>. The frontend has no separate build step. The launcher also works on Windows with the corresponding virtual-environment Python path. Project documents are stored locally under the ignored `workspace/` directory.

The example and numerical solver use the versioned reference assets already in this repository. The original research-data archive is needed for archive-dependent reproduction checks, rather than for simply opening the studio.

AI requires a compatible CLI on `PATH` with an authenticated account and available usage. Codex is selected when installed; otherwise Claude is selected. No account credentials are included in the repository. Opening the app and using the circuit solver do not require the AI provider to answer.

## Demonstrate the workflow

1. Open the example, or create an empty design and add cells.
2. In Circuit, connect the appropriate cell terminals and choose the positive and negative outputs. Check the wiring before testing.
3. Select a cell to change its starting charge. Select a connection to edit its resistance.
4. Open Test, choose current, duration and starting conditions, then run the test.
5. Open Results. Hover over a chart to read values; pin a time to inspect the same instant on the assembly.
6. Try a guided connection-wear scenario and compare its named test with the original under matching conditions.
7. Ask the copilot for an explanation or a proposed edit, review its proposed changes, then apply them.
8. Export the report and recorded results.

## Scientific scope of this snapshot

The electrical models are frozen nominal-temperature, one-RC fits for four measured LG M50T sample profiles. New cell instances reuse those profiles. They do not represent an independently characterized catalogue of cell types.

The modular solver enforces a **22 to 28 degrees Celsius** operating policy for these nominal-temperature fits and stops when a trajectory leaves that range. This policy is an interim modelling boundary, not an experimentally calibrated temperature-dependent model. Temperature is calculated with a lumped thermal model and declared parameters; it does not feed back into the frozen electrical fits.

Numerical verification and browser acceptance do not establish experimental module accuracy. Current-calibration reconciliation, temperature-dependent characterization, fixture-specific thermal identification, independent module validation and uncertainty-based acceptance are the next scientific work. See [the science and validation plan](SCIENCE_AND_VALIDATION_PLAN.md) and [the existing data audit](DATA_READINESS.md).

The assembly view is an editable illustration. Navigable solid-model CAD and manufacturing exports remain future work.

## Verification already executed

The completed rebuild checks recorded:

- 291 Python tests passed, with 8 archive-dependent checks skipped.
- 28 JavaScript tests passed.
- 17 browser workflow checks passed, including custom two-cell wiring, delete and undo, a 735-second test, interactive chart values, comparison, responsive layouts and a live AI proposal applied after review.
- 124 declared protected inputs and artifacts were checked without a mismatch. All 146 pre-existing user-project files checked during the rebuild were unchanged.

The browser record is [browser_acceptance.json](reports/experience_rebuild/browser_acceptance.json). The protected-input record is [protected-inputs.json](reports/experience_rebuild/protected-inputs.json). The Python and JavaScript records are [python-tests.xml](reports/experience_rebuild/python-tests.xml) and [javascript-tests.tap](reports/experience_rebuild/javascript-tests.tap). These are the checks run for this snapshot, not a new claim of physical validation.

To repeat the software checks in a disposable working environment:

```bash
PYTHONPATH=src:. .venv/bin/python -m pytest -q
node --test tests/*.test.mjs
```

The browser acceptance driver is `scripts/check_experience_browser.py`. It requires the separately installed browser harness and a disposable test project. Do not point an acceptance driver at a user's working project.

The earlier `V1_RELEASE.md`, `EDITOR_GUIDE.md` and legacy engineering reports describe previous workflow stages. Use this file for the current studio workflow.
