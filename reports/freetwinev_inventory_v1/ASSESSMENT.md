# FreeTwinEV dataset intake and suitability

The added download is useful experimental module data, but it cannot directly
validate VOLT-FORGE's frozen LG M50T model or its individual current-sharing
predictions. Keep it as a separate P45B evidence collection. A future P45B
module-voltage benchmark is a candidate, conditional on appropriate cell/model
characterization, measurement metadata and a prospective assessment allocation.
No model replacement or new supported editor cell type is adopted here.

## Source and access boundary

Milan Plzák, Šimon Berta, Andrej Ürge and Martin Baťa, **P45B 1s4p Battery Module
Measurement**, Zenodo version v1, published 28 January 2026,
[DOI 10.5281/zenodo.18405243](https://zenodo.org/records/18405243).
License stated by both the public record and local LICENSE: CC BY 4.0.
[Author documentation](https://freetwinev.stuba.sk/battery-module-measurement/)
describes the electro-thermal experiment. The local README still contains a
placeholder DOI; the actual public DOI is recorded separately, without rewriting
the downloaded file.

Local source: `1s4p Battery Module Measurement/`. The original ZIP was also found
in the user's Downloads folder. `verification.json` records its SHA-256, checks
the published MD5 `dea7c0e8c7146f517d71979ac546249d`, and compares every extracted
file with the archive. The downloaded folder is excluded from Git; the audit,
source hashes and provenance are versioned.

Only directory names, CSV first-line headers, README/LICENSE, the protocol
workbook and the DOCX's text were interpreted. Every source file was read as
opaque bytes for hashing. **Zero measurement rows were interpreted; none of the
AllData XLSX workbooks was opened.** There are no waveform plots, fitted
parameters, voltage residuals, quality rankings or calibration adjustments from
these new experiments. CSV/XLSX numerical equivalence is author-declared and has
not been independently checked.

## Confirmed local inventory

- **32 files, 30,259,801 bytes:** 14 CSV/XLSX pairs plus README, LICENSE,
  Measurement_Protocol.xlsx and a DOCX.
- **14 complete records:** IDs 01, 02 and 11–22. Folder identifiers and DAQ
  timestamps agree with the protocol's Test_Matrix entries.
- All CSV files share **30 column names**. The first is literally `timesamp`,
  whereas the README describes `timestamp [s]`. A future adapter needs an
  explicit alias with original-column provenance; originals remain unchanged.
- One module-current channel, one module-voltage channel, SOC and coolant flow.
  Temperature fields comprise ambient/inlet/outlet, ten cooling-plate sensors,
  and three axial sensors on each of four cells.
- **No individual branch-current columns and no individual cell-voltage
  columns** exist in these headers. Equal sharing cannot be used to manufacture
  measured branch currents. Module voltage cannot stand in for four independently
  measured cell-node voltages.
- The DOCX contains one nonempty text paragraph, its title, and no embedded media
  or objects. Despite its filename, it does not supply fitted cell parameters.

The protocol contains six sheets: Protocol, Test_Matrix, Photographs, 3D_Model,
Sensor_Layout and Materials. `inventory.json` retains exact metadata cell
addresses, channel names, source file hashes and record identities.

## Declared conditions and evidence gaps

These are **protocol declarations**, not measurements verified from time series:

| Item | Supplied declaration | Source / limitation |
|---|---|---|
| Cells / assembly | Molicel INR21700-P45B, 1s4p | Protocol!A3, C6 and README; different cells from frozen LG M50T. |
| Discharge setpoints | −20, −40, −80, −120 A at module level | Protocol!C13, Test_Matrix!C2:C15. Negative discharge is the declared source convention. Actual signal polarity not yet checked. |
| Charge setpoint | +15 A | Protocol!C14, Test_Matrix!D2:D15. |
| Coolant setpoints | 5, 15 and 25 °C | Protocol!C15; individual cases in Test_Matrix. These are not cell temperatures. |
| Flow setpoints | 0.1, 0.5 and 1.5 L/min | Protocol!C16; actual flow not inspected. |
| Ambient assumption | 23 °C | Protocol!C10; actual temperature history not inspected. |
| Protocol limits | 2.5–4.2 V, cell-surface limit 70 °C | Protocol!C7:C9. Dataset protocol values, not VOLT-FORGE's device acceptance requirements. |
| Charge/rest preparation | Standardized full charge, rest >10 min, coolant stabilization, discharge/rest, some recorded charge/recovery phases | Protocol!A23:G31. These are procedure descriptions; per-run compliance and initial SOC/polarization remain unchecked. |
| Electrical DAQ labels | Module voltage Chan306, current Chan307 | Sensor_Layout!A40:B41. Exact electrical sense points, calibration/ranges/uncertainty and channel timing need verification. |
| Time / temperature units | README says seconds; ambient/inlet/outlet Kelvin | Raw headers have no units. Cell/plate-temperature units require explicit confirmation; no conversion has been applied. |

The nominal equal-sharing arithmetic would give 5–30 A per P45B cell across
these discharge setpoints. That is only arithmetic, not an observed distribution
or evidence of sustained accuracy. It does not extend LG model coverage.

**A specific missing item:** Protocol!A19 says calibration procedures and
coefficients are in `Calibration_Table`, but no sheet by that name exists in the
supplied workbook, including hidden sheets. This establishes a documentation gap;
it does not prove that the instruments were uncalibrated. Request the referenced
table or the corresponding calibration records before treating uncertainty as
known. No outreach has been sent.

Photographs and 3D illustrations are included in the protocol's layout. Their
electrical node equivalence and lead/contact resistances have not been
established in this text-based inventory. Text readers report `#VALUE!` for some
picture cells; that alone is not evidence of corrupt measurement data. Do not
silently assume the existing same-side-terminal ladder represents this fixture.
Initial-state uncertainty, SOC calculation method, actual sampling, missing
points, synchronization/filtering and individual cell characterization remain
unresolved at this access stage.

## Compatibility with the current backend

| Intended use | Decision now |
|---|---|
| Read-only dataset catalogue and future measured-trace viewer | Suitable to develop as a separate evidence profile, retaining units/source identities and missing-evidence flags. Numerical rows require a prior access/allocation declaration. |
| Direct import as the existing LG 1s4p validation package | Unsupported. The importer requires the configured LG cell identities, exact voltage locations, four branch currents and four cell voltages. These cannot be fabricated or filled with model predictions. |
| Current-conservation reconciliation | Unavailable: the measured branch sum is absent. Does not resolve the original Stanford/Hall discrepancy. |
| Individual branch-current or cell-voltage accuracy | Unavailable from these channels. |
| Future P45B module terminal-voltage benchmark | Conditional. Establish a separate suitable electrical model, preparation/load/location mapping, calibration evidence and prospective development/assessment split first. |
| Thermal model validation | Outside the implemented backend. Temperature observations do not create a thermal solver or justify a temperature law. |
| Physical repair ranking / LG application acceptance | Unsupported. No new hardware or engineering-acceptance claim follows from this intake. |

## Allocation and next bounded work

All 14 records remain **complete, unopened and unallocated**. Reading the protocol
does not designate a fresh assessment set. Before interpreting any measured
outcomes, declare which complete records are development evidence and which are
held back, using metadata and the stated question. Do not choose records by fit
quality, random timestamp splits or apparent agreement with expected capacity.
The existing nine unused LG cells and protected module outcomes stay reserved.

The next independent software step is a P45B-specific **measured-data viewing
profile**, separate from the LG simulation controls: preserve source channels,
show incomplete evidence and permit read-only plots for declared development
records. It must not label a measured trace as a prediction or claim current-
sharing validation. In parallel, search public companion material for P45B
characterization and the missing calibration table. A replacement cell model or
new topology would be an explicitly scoped future modelling task.

Minimum unresolved evidence for a credible terminal-voltage comparison includes
the missing calibration/conversion records, timing and voltage-sense locations,
preparation/SOC method, individual-cell electrical characterization or an
explicitly narrower identifiable module model, and connection mapping. Branch
validation additionally requires individual current measurements absent here.

## Reproduce this intake

From the repository root, preserve the recorded output and use a new destination:

```powershell
& C:\Users\DELL\anaconda3\python.exe scripts\inventory_freetwinev.py --out tmp\freetwinev_inventory.json
& C:\Users\DELL\anaconda3\python.exe -m pytest tests\test_freetwinev_inventory.py -q
& C:\Users\DELL\anaconda3\python.exe scripts\verify_freetwinev_intake.py --archive "C:\Users\DELL\Downloads\1s4p Battery Module Measurement.zip" --out tmp\freetwinev_verification.json
```

Five targeted tests verify bounded header access and rejection of duplicate,
empty, unterminated and oversized headers, including deliberately undecodable
bytes after a valid header. The original scientific/solver code is unchanged;
its already-recorded full regression suite was not unnecessarily repeated.
The preservation verifier checks the earlier baseline and all prior release
artifacts. The earlier editor `.gitignore` bytes are retained in
`EDITOR_gitignore_previous.txt` because this intake adds one raw-download
exclusion to the living ignore file. Prior manifests are unchanged.
