# Dictionary from inspected files

Actual observed raw headers and missing counts are preserved verbatim in
`actual_raw_columns.json`. The following applies to the two audited runs. Raw
files have `Global_Info` and `Data` sheets; `Data` has **23 columns**, more than
the abbreviated article description. Processed module tables have 15 numeric
columns plus a separate four-position cell-name table.

| Source field | Meaning/unit | Normalized field and handling |
|---|---|---|
| `Date_Time` | Excel datetime, milliseconds present; time zone unspecified | `date_time_local_unspecified_zone`; no UTC assumption |
| `Test_Time(s)` / `Test_Times` | Elapsed test seconds | `time_s`, unchanged; primary clock |
| `Step_Time(s)` / `Step_Times` | Seconds since current step began | `step_time_s`; resets are expected |
| `Step_Index`, `Cycle_Index` | Protocol flags, dimensionless | `step_index`, `cycle_index`; retained |
| `Voltage(V)` / `VoltageV` | Measured module terminal voltage, V | `module_voltage_V`; cell-level 1s4p voltage |
| `Current(A)` / `CurrentA` | Measured module current, A; source positive on charge | `module_current_A = -source`; positive discharge |
| `Aux_Voltage(V)_1..4` | Hall-sensor output voltages, V, **not amperes** | `hall_1_V..hall_4_V`; raw values retained |
| `Aux_Voltage(V)_5` | Hall-sensor supply voltage, V | `hall_supply_V`; distinct from module voltage |
| `Aux_Temperature(��)_1..4` | Cell-centre surface temperatures; raw unit text is damaged | `surface_1_C..surface_4_C`; Celsius verified against processed labels/article |
| `Aux_Temperature(��)_5` | Measured chamber ambient temperature, degC | `ambient_C`; not replaced with setpoint |
| `CurrentA_Cell_1..4` (processed MAT only) | Author-calibrated branch measurements, A; source positive charge | `branch_1_A..branch_4_A = -source`; calibration provenance unresolved |
| `TemperatureC_Cell_1..4`, `Ambient_TemperatureC` (processed MAT) | Surface/ambient degC | Independently compared with raw Excel; all values equal in inspected runs |
| `Charge_Capacity(Ah)`, `Discharge_Capacity(Ah)` | Cycler accumulators, Ah | Inventoried; retained in raw; not substituted for integrals |
| `Charge_Energy(Wh)`, `Discharge_Energy(Wh)` | Cycler accumulators, Wh | Inventoried; retained in raw; not used for repair claims |
| `Internal Resistance(Ohm)` | Exported resistance channel, Ohm | Entirely missing in both runs; cannot identify cell/interconnect resistance |
| `dV/dt(V/s)` | Exported voltage derivative, V/s | Inventoried; retained in raw; not used as a calibrated derivative |
| `Data_processed.Cells_name.Position_1..4` | Individual physical cell IDs | Decoded into run inventory and CSV provenance |
| Filename `M1/M2`, `NMC/NCA/Mixed`, `Aged/Unaged`, `R0/R1/R3`, `T10/T25/T40` | Test bench, chemistry, ageing label, interconnect mOhm, chamber setpoint degC | Explicit factors in run inventory; `mOhm * 0.001 = Ohm`; labels are not measured resistance/ambient |

`source_xlsx_row` counts worksheet rows from 1, including the header (first data
row is 2). `source_mat_row` counts numeric-table rows from 1. Their source paths
and hashes are in each run's `provenance.json`. `kcl_residual_A` is derived as
`branch_1_A + branch_2_A + branch_3_A + branch_4_A - module_current_A`, with
nonfinite branches propagating into the residual.

M1 position 1 is nearest the common terminal side; positions 2, 3, 4 progress
away from it. M1 uses Hall sensors H1-H4; M2 uses H5-H8 with local positions 1-4.
These are physical branch/position labels, not four independent series-resistor
values. The terminal arrangement and shared rail segments are discussed in
`../DATA_READINESS.md`.

## Characterization and calibration

| Record | Actual fields | Interpretation |
|---|---|---|
| `OCVDis_<cell>.mat` | `TimeData`, `CurrentData`, `OCV`, `TempData` | Seconds, source charge-positive A, loaded C/20 voltage V, surface degC. `OCV` is pseudo-OCV, not equilibrium OCV. First array element has `source_mat_row=1`. |
| `HPPC_MultiSine_<cell>.mat` | `TimeData`, `CurrentData`, `VoltageData`, `TempData`, `StepIndex`, `CycleIndex` | Seconds, charge-positive A, V, surface degC, source protocol flags. Step numbering differs from the article's conceptual Table 2 sequence; preserve actual flags. |
| `H1_Calibration.mat` through `H4_Calibration.mat` | `Test_Times`, `Step_Times`, `Step_Index`, `Cycle_Index`, `CurrentA`, `HallVoltage`, `PowerSupplyVoltage`, `CellTempData`, `AmbientTempData` | Logged elapsed/step seconds, flags, cycler A, Hall V, supply V, surface and ambient degC. All four files parsed and fitted only for descriptive calibration diagnostics. |

Cell characterization is at a **documented chamber setpoint of 23 C**; it has
surface-temperature measurements but no independent ambient channel. In the
inspected records, pseudo-OCV is logged about every 10 s; HPPC/MS mixes about
1 s and 0.1 s intervals and short event-boundary intervals. It is not uniformly
sampled. The configured module temperatures of 10/25/40 C are present in actual
filenames; only 25 C module signal records have been audited here.

Missing or ambiguous information: raw module sheets have no cell-ID fields,
the raw header unit encoding is damaged, exact sensor processing coefficients
and scripts are absent from the archive, end-to-end instrument uncertainty is
unspecified, and actual contact/shunt resistances are not separately measured.
Core temperature, thermal contact conductance, core-surface gradients, heat
generation, convection coefficients and per-cell SOC are **not observed channels**.
