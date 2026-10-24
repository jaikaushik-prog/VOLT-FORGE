# VOLT-FORGE data readiness and provisional modelling

Executable inspection of the **real Piombo et al. parallel-cell dataset**, DOI
[10.17632/zh58byr53c.2](https://data.mendeley.com/datasets/zh58byr53c/2).
Read [MODELLING_DECISION.md](MODELLING_DECISION.md) for the current decision and
[DATA_READINESS.md](DATA_READINESS.md) for the original inspection record.
The project includes provisional cell identification and a separate static
ladder solver. Experimental module validation is pending. There is no optimizer,
ranked repair result or web application.

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

No source data are uploaded, published, or placed in a remote repository. This
folder was not a Git repository; `.gitignore` is ready for later initialization.
Synthetic values exist only inside software tests. Integration tests explicitly
skip if the original archive is absent; they all ran with the actual archive here.
