# VOLT-FORGE electrical model research

Executable inspection of the **real Piombo et al. parallel-cell dataset**, DOI
[10.17632/zh58byr53c.2](https://data.mendeley.com/datasets/zh58byr53c/2).
Read [SIMULATION_READINESS.md](SIMULATION_READINESS.md) for the current four-cell
electrical CLI and validation-backend status;
[REFERENCE_INITIAL_STATE_DECISION.md](REFERENCE_INITIAL_STATE_DECISION.md)
for the completed bounded investigation, which keeps v2 frozen;
[MODEL_IMPROVEMENT_DECISION.md](MODEL_IMPROVEMENT_DECISION.md) for the v2 decision,
[MODELLING_DECISION.md](MODELLING_DECISION.md) for the sealed v1 stage and
[DATA_READINESS.md](DATA_READINESS.md) for the original inspection record.
The project includes provisional cell identification, a static ladder solver
and a dynamic four-cell command-line backend. Experimental module validation is pending. There is no optimizer,
ranked repair result or web application.

Public project repository: https://github.com/jaikaushik-prog/VOLT-FORGE.
Local upload preparation is described in [GITHUB_UPLOAD.md](GITHUB_UPLOAD.md).

## Four-cell electrical simulation backend

The frozen v2 model now supports configured rails, initial states, piecewise
loads, SOC/polarization evolution, electrical losses, power/energy accounting,
coverage flags and future-measurement ingestion. Four manual cases and separate
sensitivities are supplied; there is no automatic ranking. Device voltage and
excursion requirements remain unset: **requirement not configured**, never pass.
All design decisions return **insufficient evidence**; experimental validation
is **awaiting suitable measurements**. No thermal model is included.

```powershell
$env:PYTHONPATH = 'src'
& C:\Users\DELL\anaconda3\python.exe -m voltforge.simulation configure
& C:\Users\DELL\anaconda3\python.exe -m voltforge.simulation simulate
& C:\Users\DELL\anaconda3\python.exe -m voltforge.simulation compare
& C:\Users\DELL\anaconda3\python.exe scripts\make_module_fixture.py
& C:\Users\DELL\anaconda3\python.exe -m voltforge.simulation validate --measurements tests/fixtures/module_synthetic --out reports/module_simulation_v1/synthetic_ingestion
& C:\Users\DELL\anaconda3\python.exe -m voltforge.simulation compare --measurements tests/fixtures/module_synthetic --out reports/module_simulation_v1/synthetic_comparison
& C:\Users\DELL\anaconda3\python.exe -m pytest -q --junitxml=reports/module_simulation_v1/pytest.xml
```

The fixture is explicitly synthetic and contains a known voltage offset; it
tests ingestion plumbing, not experimental accuracy. See the
[import specification](MEASUREMENT_IMPORT_SPEC.md),
[predeclared application](configs/module_application_v1.json),
[scenario plan](configs/module_scenarios_v1.json) and
[comparison/plots](reports/module_simulation_v1/COMPARISON.md).
All **75 tests pass**. The frozen v2/reference-investigation artifacts remain
unchanged; no unused cell or protected module outcome was opened.

## Bounded reference/initial-state investigation

The 55% result is a reduction in prediction RMSE on the declared subset,
not an improvement in battery performance. A bounded investigation on P7/P13/P19
confirmed sensitivity to reference shape and the difficulty of separating SOC
alignment from reference bias. It did not replace the frozen v2 model. All nine
remaining unused cells are preserved; the app and optimizer stay paused.
The actual load-voltage requirement and measurement uncertainty must establish
an acceptance budget before another fitting sprint. See the decision above and
the [prepared faculty/lab brief](reports/reference_initial_state_v1/LAB_REQUEST.md).

```powershell
$env:PYTHONPATH = 'src'
& C:\Users\DELL\anaconda3\python.exe -m voltforge.models.reference_investigation verify
& C:\Users\DELL\anaconda3\python.exe -m voltforge.models.reference_investigation run
& C:\Users\DELL\anaconda3\python.exe -m pytest -q
```

At that completed stage, the suite passed 52 tests. That investigation binds 112 durable
baseline artifacts and does not write v1/v2 outputs. Reproduction of historical
v2 diagnostics below is unnecessary for the new investigation; avoid rewriting
frozen artifacts with different formatting or software versions.

## V2 improvement sprint

The selected model uses a calibration-rest reference and one RC. Additional
characterized-cell assessment improves primary-domain RMS error, but maximum
errors still exceed the proposed voltage-decision budget. Module validation
remains blocked by current-reference reconciliation. See the decision report
for the exact operating case and the distinction between development, fresh
characterized-cell assessment and unsupported transfer.

Reproduce the completed results **without refitting**:

```powershell
$env:PYTHONPATH = 'src'
& C:\Users\DELL\anaconda3\python.exe -m voltforge.models.improvement verify
& C:\Users\DELL\anaconda3\python.exe -m voltforge.models.improvement assess
& C:\Users\DELL\anaconda3\python.exe scripts\model_improvement_diagnostics.py
& C:\Users\DELL\anaconda3\python.exe scripts\summarize_improvement.py
& C:\Users\DELL\anaconda3\python.exe scripts\summarize_domains.py
& C:\Users\DELL\anaconda3\python.exe scripts\check_coupling_imbalance.py
& C:\Users\DELL\anaconda3\python.exe -m pytest -q
```

The report command reconstructs any missing v2 prediction CSVs from frozen
parameters, preserving model seals. The upload bundle omits these large
reproducible CSVs but includes numerical summaries, models, hashes and plots.
The official dataset is required to reproduce calculations and all integration
checks. Keep exact file bytes: `.gitattributes` disables line-ending conversion
because the scientific seals hash code and artifacts.

The original stage order was `improvement reserve`, `improvement develop`,
`improvement calibrate-fresh`, then `improvement assess`. The `develop` command
refuses to overwrite an existing procedure seal; do not delete seals to tune
against opened evidence. A future iteration requires a versioned plan and new
assessment allocation. The machine-readable plan and lock are
`configs/model_improvement_v2*.json`; procedure/fresh-model seals are under
`reports/improvement_v2/`.

- [Complete comparison and plots](reports/improvement_v2/RESULTS.md)
- [Load-only errors](reports/improvement_v2/LOAD_ERRORS.md)
- [Frozen plan](MODEL_IMPROVEMENT_PLAN.md)
- [Parameter stability](reports/improvement_v2/parameter_stability.json)
- [Assumption sensitivity](reports/improvement_v2/assumption_sensitivity.json)
- [Source/header evidence review](reports/improvement_v2/diagnosis/archive_metadata_evidence.json)
- [Software coupling](reports/improvement_v2/software_coupling/results.json)
- [Verification record](reports/improvement_v2/VERIFICATION.md)

## Reproduce the modelling and reconciliation sprint

From PowerShell in the project root, using the existing Anaconda environment:

```powershell
$env:PYTHONPATH = 'src'
& C:\Users\DELL\anaconda3\python.exe scripts\reconcile_independent.py
& C:\Users\DELL\anaconda3\python.exe -m voltforge.models.identification reserve
& C:\Users\DELL\anaconda3\python.exe -m voltforge.models.identification fit
& C:\Users\DELL\anaconda3\python.exe -m voltforge.models.identification assess
& C:\Users\DELL\anaconda3\python.exe scripts\summarize_sprint.py
& C:\Users\DELL\anaconda3\python.exe -m pytest -q
```

Run `reserve` before `fit`, then `assess`; `identification all` performs those
stages in order. In this completed workspace, `fit` detects the model seal and
does **not** refit. `assess` reproduces predictions after checking hashes.
Do not remove the seal to tune on the opened assessment. A reviewed new version
needs fresh assessment evidence. In a fresh checkout, reproduce the original
inventory/audit below first; the identification lock verifies those inputs.
Identification expects exactly one official ZIP in the root or `data/raw/`.

The independent reconciliation script reads the two already-open module runs
and eight Hall calibration files through separate MAT5/XML readers. It accepts
`--archive` for another location. It consumes no original audit outputs;
`summarize_sprint.py` compares the two calculations afterward.

New deliverables:

- [Reconciliation](reports/reconciliation/RECONCILIATION.md) and
  [prepared author questions](reports/reconciliation/AUTHOR_QUESTIONS.md), not sent.
- [Cell results](reports/identification_v1/RESULTS.md), parameter uncertainty,
  identifiability plots and seven measured/predicted assessment figures.
- `configs/cell_identification_v1*.json`: whole-cycle allocation and source hashes.
- `reports/identification_v1/model_seal.json`: frozen implementation/model hashes.
- `reports/identification_v1/*_assessment_predictions.csv`: source rows,
  inputs, temperature, voltage reference, measured/predicted voltage and error.
- [Static ladder solver](src/voltforge/models/ladder.py) and analytical tests
  in `tests/test_ladder.py`; experimental validation pending.
- [Preservation/analytical checks](reports/sprint_verification/results.json).

## Run on this computer

The user-supplied dataset ZIP is already in the project root. It is read in place
and ignored by Git; it does not need to be extracted. The previously registered
Microsoft Store Python launcher failed in this sandbox. The existing Anaconda
Python below was successfully used instead.

From PowerShell in `C:\Users\DELL\Desktop\volt-forge`:

```powershell
$env:PYTHONPATH = 'src'
& C:\Users\DELL\anaconda3\python.exe -m voltforge.data.cli all
& C:\Users\DELL\anaconda3\python.exe -m pytest -q
```

`all` verifies ZIP members and hashes, inventories the experiments, binds the
frozen split manifest to input hashes, audits the two selected 25 C runs, parses
the seven relevant cells' characterization records, and regenerates the plots.
Allow roughly a few minutes on this machine; raw Excel parsing dominates.

To repeat only the measured-data audit after inventory:

```powershell
$env:PYTHONPATH = 'src'
& C:\Users\DELL\anaconda3\python.exe -m voltforge.data.cli audit
```

An archive elsewhere can be selected explicitly:

```powershell
python -m voltforge.data.cli all --archive 'D:\datasets\official-download.zip'
```

## Reproduce elsewhere

Use CPython 3.12 and the tested versions in `requirements.txt`. In an environment
with package-registry access:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
$env:PYTHONPATH = 'src'
.\.venv\Scripts\python.exe -m voltforge.data.cli all
.\.venv\Scripts\python.exe -m pytest -q
```

The clean-environment installation commands are provided for reproduction; this
session used the existing Anaconda installation and did not test an online install.

## Official retrieval and attribution

1. Open the [version 2 record](https://data.mendeley.com/datasets/zh58byr53c/2).
2. Use its **Download All** control. Preserve the downloaded ZIP unchanged in the
   project root (the existing default filename begins `Full factorial`), or under
   `data/raw/`. If multiple ZIPs exist, pass `--archive` explicitly.
3. Run `inventory` or `all`. Compare the archive SHA-256 to
   `reports/provenance.json`; the supplied ZIP is 758,227,888 bytes. ZIP packaging
   can change while members remain identical: review member hashes before
   explicitly revising a frozen archive binding. The CLI does not do that silently.

The record specifies **CC BY 4.0**. Attribute Gabriele Piombo, Simone Fasolato,
Robert Heymer, Marc Francis Hidalgo, Mona Faraji Niri, Davide Martino Raimondo,
James Marco, and Simona Onori (2024), *Full factorial design of experiments
dataset for parallel-connected lithium-ion cells imbalanced performance
investigation*, Mendeley Data, version 2. See [ATTRIBUTION.md](ATTRIBUTION.md).
Our CSVs convert current polarity; supplied observations remain unchanged.
Fitted cell parameters and predictions are stored separately. Author-processed
MAT data are distinguished from original raw exports.

## Outputs and guards

- `reports/file_inventory.json`: every ZIP member's size, CRC and SHA-256.
- `reports/run_inventory.csv` / `.json`: actual run factors and decoded cell IDs.
- `configs/splits.json` and `splits.lock.json`: fixed whole-experiment assignments
  and input hashes. The audit command refuses reserved or quarantined signals.
- `data/processed/`: reproducible normalized CSVs with source row references.
- `reports/module_audit.json`, `characterization_audit.json`, and
  `hall_calibration_audit.json`: numerical audit results.
- `reports/plots/`: full-cycle, discharge and conservation figures for each run.
- [Data dictionary](reports/DATA_DICTIONARY.md) and
  [parser limitations](reports/PARSER_NOTES.md).

The official raw archive and processed-data cache remain local and excluded
from Git. Reports include attributed derived observations and predictions.
The upload bundle is prepared locally; this session has not pushed it to GitHub.
Synthetic values are confined to labelled software tests and coupling checks.
Archive-dependent checks require the official download; all 75 tests ran with
the actual archive present here. See the verification record for the scope of
those checks.
