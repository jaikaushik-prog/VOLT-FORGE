# Bounded public evidence search — 2026-10-25

This is a discovery record, not a model selection or validation result. No external
messages were sent. Metadata pages and one README were inspected; no new candidate
cell measurements, model parameters or assessment spreadsheets were opened.

| Primary source | What its metadata establishes | What it does not resolve here |
|---|---|---|
| [FreeTwinEV module record, v1](https://zenodo.org/records/18405243), [project description](https://freetwinev.stuba.sk/battery-module-measurement/) | Original P45B 1s4p electro-thermal dataset; accompanying protocol and sensor channels | No supplied Calibration_Table, branch-current channels or identified per-cell electrical parameters |
| [FreeTwinEV P45B Cell Internal Resistance Mapping, v1](https://zenodo.org/records/17242656) | Resistance and voltage measurements of 600 P45B cells; published 2025-10-01; 5.3 MB ZIP, published MD5 `cecf478e37e28b996fcecac6b01ef34a` | Metadata alone does not map four specific module cells or establish OCV/dynamic parameters. Archive not downloaded/opened |
| [University of Twente: P45B Activation and Impedance Investigation](https://research.utwente.nl/en/datasets/p45b-activation-and-impedance-investigation/) | Activation and impedance measurements of 60 pristine P45B cells; DOI 10.5281/zenodo.17249545; listed 2025-10-02 | Not proof of module-cell identity, dynamic-load coverage or calibration for this module. Zenodo page was inaccessible through the web reader; institutional metadata was available |
| [About:Energy P45B ECM data release, v1](https://zenodo.org/records/19052626) | ECM lookup tables, cycling-data archive, data-format PDF and validation-matrix workbook. Published date shown as 2026-03-20 (record created/modified 2026-06-01) | Separate cells and thermal setup; module transfer, calibration and interconnect mapping still require review |

The [About:Energy README](https://zenodo.org/records/19052626/files/readme_Molicel_P45B_dataset_AE.txt?download=1)
lists low-rate charge/discharge, GITT, constant-current and drive-cycle records
at several temperatures, with additional aviation duty profiles. It distinguishes
base and charge-optimized parameter tables. This is a promising source for a
new, explicitly scoped P45B electrical investigation; no numerical parameter or
accuracy claim has been adopted. Its listed archive `molicel_p45b_data.zip` is
12.4 MB, published MD5 `0bd40f92dfabcea679900696cc2c0077`.

The authors' [ECM announcement](https://www.aboutenergy.io/post/molicel-p45b-battery-model-ecm-open-source-validation)
links the release and describes a different model structure and thermal protocol
from VOLT-FORGE's frozen LG model. It reports CC BY 4.0 availability, whereas the
README also contains a general copyright/liability paragraph. Confirm the exact
dataset licence and attribution terms from the release metadata before importing
or redistributing files. Do not automatically transplant a published circuit or
temperature law into this module. Vendor-reported validation claims have not been
reproduced here and do not validate VOLT-FORGE.

Queries covered `site:freetwinev.stuba.sk Calibration_Table`, P45B calibration,
parameter identification, characterization, OCV and HPPC, plus Zenodo and the
linked primary pages. No matching FreeTwinEV calibration table was found in this
bounded search. That is not proof that it is unavailable elsewhere.

## Precise remaining evidence

1. The Calibration_Table referenced by `Measurement_Protocol.xlsx`, Protocol!A19:
   channel coefficients, units, offsets, calibration dates and uncertainties;
   any post-processing applied before CSV export.
2. Timestamp construction, channel scan order/delays, original sample rate and
   any filtering or resampling; actual current and voltage sensor specifications.
3. Exact module voltage-sense nodes and electrical connection diagram, contact
   and rail resistances, and identity mapping of the four P45B cells to any
   resistance/activation/characterization records.
4. The source SOC calculation and capacity basis, actual charge/rest/preparation
   history and initial cell states. Protocol instructions alone are not logs.
5. For branch-sharing validation, synchronized individual branch currents and
   defined cell-node voltages. These channels are absent from the downloaded
   module dataset; no processing can reconstruct independent measurements.

These are prepared questions only. No lab request or author outreach was sent.
