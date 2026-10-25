# VOLT-FORGE battery-engineering workspace

Executable inspection of the **real Piombo et al. parallel-cell dataset**, DOI
[10.17632/zh58byr53c.2](https://data.mendeley.com/datasets/zh58byr53c/2).
Read [SIMULATION_READINESS.md](SIMULATION_READINESS.md) for the current four-cell
electrical project workflow and validation-backend status;
[REFERENCE_INITIAL_STATE_DECISION.md](REFERENCE_INITIAL_STATE_DECISION.md)
for the completed bounded investigation, which keeps v2 frozen;
[MODEL_IMPROVEMENT_DECISION.md](MODEL_IMPROVEMENT_DECISION.md) for the v2 decision,
[MODELLING_DECISION.md](MODELLING_DECISION.md) for the sealed v1 stage and
[DATA_READINESS.md](DATA_READINESS.md) for the original inspection record.
The product direction is a visual workspace for design, simulation and evidence.
The implemented core is a versioned four-cell electrical project backend with
immutable runs, variant comparison and reproducible export. Experimental module
validation is pending. A local 2D web editor now connects to this backend.
There is no optimizer or ranked repair result.

Public project repository: https://github.com/jaikaushik-prog/VOLT-FORGE.
Local upload preparation is described in [GITHUB_UPLOAD.md](GITHUB_UPLOAD.md).

## Open the 2D workspace

```powershell
& C:\Users\DELL\anaconda3\python.exe scripts\run_editor.py --open
```

Open **http://127.0.0.1:8765**. Select a cell or rail, preview an edit, save a
variant, run it, inspect current/voltage and compare/export saved simulations.
The editor keeps its working project in ignored `workspace/editor_project`;
recorded demonstration runs stay untouched. See [EDITOR_GUIDE.md](EDITOR_GUIDE.md)
for exact controls, limitations, local HTTP contract and verification commands.
Thermal simulation and AI optimization remain unavailable.

## Inspect the added P45B measurements

Click **Measurements** in the editor or open **http://127.0.0.1:8765/measurements**.
The separate read-only viewer shows the complete FreeTwinEV ID01 development
record: measured module current/voltage, source sensors, exact samples and exports.
The other 13 complete records remain protected. Keep the original downloaded
folder local; it is excluded from Git. This is not a P45B simulation or module
validation. See the [viewer decision](reports/measurement_viewer_v1/DECISION.md),
[commands/API](reports/measurement_viewer_v1/USAGE.md) and
[new public P45B evidence leads](reports/measurement_viewer_v1/PUBLIC_EVIDENCE.md).

The complete About:Energy P45B release has also been verified. See the
[P45B intake decision](reports/p45b_intake_v1/DECISION.md) and
[prospective modelling plan](reports/p45b_intake_v1/MODELLING_PLAN.md).
Its 51 CSV files include both experimental data and author simulations. The
initial intake preserved every outcome until a declared modelling procedure.

The subsequently supplied full paper resolves the core electrical-specification
access blocker. See the [paper review and equation checks](reports/p45b_paper_v1/DECISION.md).
A separate two-RC/hysteresis implementation now reproduces the declared 25 degC
1C discharge using the published base table. See the
[reproduction results and plots](reports/p45b_reproduction_v1/DECISION.md): full-record
RMSE is 35.86 mV and maximum error reaches 336.04 mV near discharge termination.
This requires diagnosis before voltage-limit or P45B module decisions. At that
stage, the other 50 measurement files and author validation workbook remained
unopened. The frozen LG model and editor physics are unchanged.

The [same-record author comparison](reports/p45b_author_comparison_v1/DECISION.md)
now shows that our voltage prediction matches the authors' output to 0.0183 mV
RMSE. Their prediction has the same approximately 336 mV end-of-discharge miss
against measurement. This confirms close reproduction for this case, not battery
accuracy. That stage passed 74 focused tests without adjusting parameters or
initial states.

The [bounded low-charge diagnosis](reports/p45b_low_soc_v1/DECISION.md) now uses
the separately declared 25 degC C/30 and GITT development records. The published
reference closely matches C/30 loaded voltage. Near 4% nominal SOC, GITT voltage
recovers about 461 mV after unloading, while the table's steady-current drop
scale is about 128 mV. That scale is not a transient prediction, and finite-rest
voltage is not established equilibrium OCV. No model revision was adopted.
That stage passed 86 focused tests without adopting a model revision.

The [complete frozen-model GITT replay](reports/p45b_gitt_replay_v1/DECISION.md)
now reports 29.88 mV sample RMSE, 22.19 mV time RMSE and 333.37 mV maximum error.
Near empty, full transient simulation predicts about 114 mV recovery versus
461 mV measured. The discrepancy persists under declared numerical, current
sampling and supported starting-SOC sensitivities. All **99 focused tests** pass;
**48 other measurement files** and the validation workbook remain protected.
No new model was adopted. The next step is a bounded investigation of whether
existing low-SOC parameters can identify both pulse and relaxation behavior.
This remains cell-model development, with experimental module validation pending.

## First product workflow and frontend handoff

Read [FRONTEND_CONTRACT.md](FRONTEND_CONTRACT.md) for the Python/JSON interface,
[MVP_SCOPE.md](MVP_SCOPE.md) for implemented versus future capabilities, and the
[product vision](VOLT_FORGE_Product_Vision.md) for the broader direction.

```powershell
$env:PYTHONPATH = 'src'
& C:\Users\DELL\anaconda3\python.exe scripts\demonstrate_product_workflow.py
```

This loads A0, saves its run, creates A1 with one declared p1-p2 resistance edit,
shows inherited results as outdated, reruns A1, compares identical operating
conditions and exports/replays both simulations. Existing completed demo outputs
are verified and preserved; use `--out tmp/product_demo_fresh` for a new run.
The configured reference assets suffice; this workflow does not decode raw data.
See [comparison and plot](reports/product_integration_v1/demo/comparison.json),
[plot](reports/product_integration_v1/demo/comparison.png), and
[actual API examples](reports/product_integration_v1/FRONTEND_EXAMPLES.md).
That product-handoff release passed **100 tests**. These are software checks; module accuracy,
load-voltage acceptance, thermal behaviour and repair benefits remain unvalidated.

```powershell
& C:\Users\DELL\anaconda3\python.exe -m pytest -q --junitxml=tmp/product_tests.xml
& C:\Users\DELL\anaconda3\python.exe scripts\verify_editor_release.py --out tmp/editor_verification.json
```

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
& C:\Users\DELL\anaconda3\python.exe -m pytest -q
```

The fixture is explicitly synthetic and contains a known voltage offset; it
tests ingestion plumbing, not experimental accuracy. See the
[import specification](MEASUREMENT_IMPORT_SPEC.md),
[predeclared application](configs/module_application_v1.json),
[scenario plan](configs/module_scenarios_v1.json) and
[comparison/plots](reports/module_simulation_v1/COMPARISON.md).
At that completed backend release, **75 tests passed**. Preserve its existing
outputs and test XML; use new output directories for new investigations.
The frozen v2/reference-investigation artifacts remain
unchanged; no unused cell or protected module outcome was opened.

## Bounded reference/initial-state investigation

The 55% result is a reduction in prediction RMSE on the declared subset,
not an improvement in battery performance. A bounded investigation on P7/P13/P19
confirmed sensitivity to reference shape and the difficulty of separating SOC
alignment from reference bias. It did not replace the frozen v2 model. All nine
remaining unused cells are preserved; the bounded electrical editor is now
implemented, while the optimizer remains paused.
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
