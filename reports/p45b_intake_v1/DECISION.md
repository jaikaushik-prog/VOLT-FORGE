# About:Energy P45B intake decision

The user supplied the complete six-file release. **Every file matches its published
Zenodo v1 MD5.** The archive contains 51 CSVs grouped into 43 filename families.
No experimental or author-simulation rows were interpreted, no numerical parameter
rows were read, and the validation workbook was only hashed as opaque bytes.
Frozen LG models and the current simulator remain unchanged.

## What the files provide

| Supplied file | Role and intake access |
|---|---|
| `molicel_p45b_data.zip` | 51 CSV members; filenames, headers, sizes and hashes only. Not extracted. |
| `Molicel P45B Data Release Data Format Documentation.pdf` | Both pages read and rendered for visual checking. |
| `readme_Molicel_P45B_dataset_AE.txt` | Release and protocol documentation read. |
| `Molicel_INR-21700-P45B_ECM.csv` | Base fitted parameter table; header only. |
| `Molicel_INR-21700-P45B_ECM-charge.csv` | Charge-optimized fitted table; header only. |
| `Molicel P45B ECM Validation Matrix.xlsx` | Protected author assessment results; no workbook/sheet opened. |

The [inventory](inventory.json) records exact hashes, names, channel classes and
family grouping. The [allocation proposal](../../configs/ae_p45b_allocation_v1.json)
keeps every family protected. The [modelling plan](MODELLING_PLAN.md) defines a
first 25 degC single-cell scope and distinguishes an independent simple model
from reproducing the authors' published model.

## Important interpretation findings

The archive has **16 experimental-only files** (C/30 and GITT) and **35 files with
experimental plus author-simulation columns**. There are eight additional
`-charge.csv` variants, associated with the charge-optimized parameter set. Thus
51 files must not be counted as 51 independent tests. There are 43 filename
families, not 43 established cell identities. Paired experimental-value equality
remains untested because outcomes remain unopened.

Format-guide pages 1–2 define the experimental channels as elapsed seconds,
applied current, measured voltage and controlled surface temperature. Currents
are negative on discharge. The synthetic-tested adapter preserves that original
current and exposes a separately named sign-reversed solver input. It never uses
the authors' simulation channels to fill missing measured data or initial states.

In particular, **SOC_sim and E_OCV_V are predictions**, not measured SOC or an
experimental equilibrium curve. I_sim_A may differ from I_exp_A because the
authors interpolated simulation outputs to experimental timestamps. Q_sim_W is
documented as signed cell power, not measured heat generation. The guide identifies
1C as 4.5 A and C/30 as 0.15 A; neither establishes actual capacity for each record.
T_exp_degC refers to Peltier-controlled cell temperature, not proof of uniform
internal temperature or equivalence to the liquid-cooled FreeTwinEV module.

These distinctions are implemented in `scripts/ae_p45b_intake.py` and tested using
synthetic fixtures. The CLI exposes only the header-level intake. The numeric
experimental adapter is not called on real outcomes at this stage.

## Provenance and licence

Primary record: [About:Energy P45B ECM data release, v1](https://zenodo.org/records/19052626),
DOI **10.5281/zenodo.19052626**. The public API metadata declares `access_right=open`
and `license.id=cc-by-4.0`. That resolves the earlier uncertainty raised by the
README's general copyright paragraph. A compact metadata receipt is in
[public_release.json](public_release.json); the full API response remains locally
under ignored `data/raw/ae_p45b_metadata/record_19052626.json` with its SHA256.

Credit: Edmund Dickinson, Ceren Zor, Darryl Doyle, Christian Pilling, Katie Lukow,
Kieran O'Regan and Gavin White, About:Energy (2026). Licence:
[Creative Commons Attribution 4.0](https://creativecommons.org/licenses/by/4.0/).
Our additions are metadata inventory, channel classification, filename grouping,
prospective allocation and synthetic importer tests. No measured numerical data,
parameter values or author validation errors are republished by this intake.
The original six files remain local and are excluded from GitHub.

## What is ready and what still needs evidence

Ready: source identity, experimental/simulated channel separation, sign/units
mapping, complete-family inventory and a tested adapter for future allocated data.
Twenty synthetic tests pass, including rejection of simulated-only inputs,
malformed/nonfinite experimental data, duplicate/backwards timestamps, unknown
schemas, duplicate/unsafe ZIP names and source identity mismatch. An undecodable
outcome fixture proves header inventory does not send measurement bytes to the
text decoder. Raw archives are hashed without interpreting measurement rows.

Not yet done: P45B fitting, actual-record integration/sampling diagnostics,
initial-state determination, parameter-identifiability analysis or voltage-error
assessment. No new accuracy number or validated P45B module capability is claimed.

For exact published-model reproduction, the [detailed model specification](https://docs.aboutenergy.io/products/Electrical/ECM/specification/)
redirects to a login handoff, and the [linked SSRN preprint](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6861858)
returned HTTP 403 to the reader. Exact hysteresis and lookup/initial-state rules
cannot be inferred solely from headers. An accessible specification is the remaining
external dependency for that route. Independent measured-data model development
can proceed after its procedure is frozen, using the reserved allocation proposal.

For FreeTwinEV module validation, missing calibration/timing/sense-node evidence,
cell identity mapping and branch-current measurements remain unresolved. The
new single-cell dataset does not remove these blockers. No outreach was sent.

## Reproduce

Run from the repository root. Keep original downloads there and use new outputs:

```powershell
& C:\Users\DELL\anaconda3\python.exe scripts\ae_p45b_intake.py --out tmp\ae_p45b_inventory.json
& C:\Users\DELL\anaconda3\python.exe -m pytest tests\test_ae_p45b_intake.py -q
& C:\Users\DELL\anaconda3\python.exe scripts\verify_p45b_intake.py --out tmp\ae_p45b_verification.json
```

`verification.json` records source and prior-release preservation. Earlier living
README and ignore-file bytes are retained under `previous/` because their current
versions add the new intake link and exclude the original files. Existing release
reports/manifests are not overwritten. PDF reading used isolated temporary reader
packages; the modelling environment and pinned dependencies were not changed.
