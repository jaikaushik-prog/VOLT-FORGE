# P45B measurement viewer decision

The local editor now has a separate **Measurements** view. It reads the complete
FreeTwinEV ID01 CSV, plots measured module current and voltage, offers each
temperature/SOC/flow channel, inspects exact source rows and exports the original
CSV or a JSON summary with provenance. It provides no P45B prediction and no
model-error or repair claim. The frozen LG M50T simulator remains separate.

## Allocation and actual access

The [plan](PLAN.md) and [allocation](../../configs/freetwinev_viewer_v1.json) were
committed as `e965d21` **before** opening ID01 measurement rows. Selection used
protocol metadata: lowest nominal discharge (20 A), 25 degC coolant, 1.5 L/min
and recorded charge/recovery steps. This was not a selection by measured error
or observed capacity. The complete ID01 record is now used development evidence.
The other **13 complete FreeTwinEV records remain unopened**, as do all AllData
XLSX files. Future assessment use still requires a prospective model/procedure
and allocation. Nine unused LG cells and frozen module outcomes stay protected.

The earlier `freetwinev_inventory_v1` report describes the earlier header-only
stage and is not rewritten. All 32 original files remain byte-identical to that
inventory, which was verified against the published Zenodo v1 ZIP checksum.

## Confirmed observations in ID01

Source: `AllData/ID01_20251126_150908248/FreeTwinEV_1s4p_ID_01.csv`, SHA256
`aa05b4f6445e6aecdd86db92bade11ef3d722450f53bfae75efc3ef0386bca55`.
Line 1 contains names, including the source spelling `timesamp`. **Line 2 is a
units row**, explicitly defining every temperature channel in kelvin. That
resolves the earlier unit uncertainty for ID01 without guessing from magnitudes.
The unopened records have not been checked for their own units rows.

| Observation | ID01 source result |
|---|---:|
| Samples / source lines | 2,413 / 3–2,415 |
| Recorded time span | 12,059.998 s (201.000 min) |
| Median sampling interval | 5.000 s |
| Minimum / maximum interval | 4.328 / 5.532 s |
| Module current range | −20.0841953 to +15.0615005 A |
| Module voltage range | 2.52804461 to 4.20465939 V |
| Blank readings | 0 across the 30 source columns |
| Intervals exceeding twice the median | 0 |

These are descriptive measurements with unresolved calibration uncertainty.
Negative current denotes discharge per `Measurement_Protocol.xlsx!Protocol!C13`;
the viewer leaves the sign intact. It neither estimates branch currents by
division nor imports these records into the LG validation comparator. A shared
row timestamp is not proof of synchronized channel acquisition. Roughly five-
second sampling cannot establish instantaneous voltage steps or sub-second
dynamics; this is an interpretation of the observed time resolution, not a
claim about the original DAQ hardware.

Source SOC is displayed as a supplied channel, not independently calculated SOC.
Temperature traces are measured sensor readings, not predicted cell temperature.
Nominal setpoints are labelled protocol values, not asserted measured compliance.
No measured voltage extreme is treated as a pass/fail application limit.

## Interface and software checks

Start the existing server and open `/measurements`; see [usage and API](USAGE.md).
Catalogue access needs only the versioned inventory/allocation. ID01 reads check
the original SHA256 before decoding. The pinned allocation, inventory and plan
hashes prevent an unnoticed change in allowed records. Protected IDs fail before
source filesystem access. Source changes fail visibly. No cache can return
stale measurements following a source-file change.

The parser requires the known header and explicit units row. Unsupported calendar
time, nonnumeric/nonfinite values, missing time/current/voltage, duplicate or
backwards timestamps and ragged rows are rejected. Optional empty readings stay
null. It does not sort, align, interpolate, shift, clip or rescale data.
Plots retain per-bin extrema and endpoints; missing readings or intervals over
twice the median break their lines. Exact-row lookup retains raw timestamp text,
source line and all source numeric values. Display decimation never changes the
original CSV or summary extrema. Hashes detect changes, not instrument accuracy.

See `pytest_final.xml`, `browser_final/verification.json` and
`release_verification.json` for the final test/preservation receipts. Synthetic
tests cover parser errors, gap handling, extrema, authorization before source
access, provenance, pagination, raw-download protection and actual HTTP routes.
The existing editor transport tests exercise simulation, edit invalidation,
variant comparison and export. Browser checks use real allocated ID01 in an
isolated browser profile, including source-row selection, sensor switching,
rapid navigation, byte-exact CSV download, JSON export and a 390px layout.
Desktop and mobile screenshots were visually inspected. An initial browser
harness selector typo was corrected before acceptance; it was not a data error.

## Public evidence search and next step

The [search record](PUBLIC_EVIDENCE.md) identifies three public P45B resources.
The strongest next lead is an About:Energy release with ECM parameters and
characterization/cycling data. It is evidence for **another characterized P45B
cell**, not evidence that these four module cells share the same parameters.
Only landing-page/README metadata was read; its raw traces, parameters and
validation workbook remain unopened in this sprint.

The missing FreeTwinEV Calibration_Table was not located in the supplied archive
or the checked public documentation. Timing uncertainty, voltage sense locations,
cell identities/parameter mapping, interconnect resistance and source SOC method
remain unresolved. Individual branch currents and cell voltages are absent.
Thus current sharing cannot be validated from this download, regardless of
whether a separate P45B cell model can be built. No outreach was sent.

Next: inventory the newly identified cell-characterization release and review its
model definitions/licence, then predeclare a separate P45B modelling and assessment
procedure before opening its outcomes. A module-terminal comparison may become
possible under explicit transfer assumptions; calibrated branch-sharing validation
still requires additional measurements. For now the useful student workflow is
to inspect an actual discharge/recharge record and understand which quantities
were measured. Experimental module validation remains **awaiting suitable measurements**.
