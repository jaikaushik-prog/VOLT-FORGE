# Module measurement import format, version 1

The importer accepts a directory containing **`measurements.csv`** and
**`metadata.json`**. It does not read the protected dataset archive or select
assessment runs. Supply a new, authorized measurement package. The original
files are copied byte-for-byte under the output's `original/` directory and
hashed. Existing different source bytes cannot be overwritten in that directory.

## CSV and electrical locations

Every row needs an increasing integer `source_row` identifying the original
record and an increasing finite `time_s` in elapsed seconds. Do not reset clocks,
sort, deduplicate, average, fill gaps or align by fitting voltage. If an export
has multiple source files, retain their provenance in metadata and provide an
unambiguous source-row mapping before import; this version expects one CSV.

| Required channel | Unit | Exact location identifier |
|---|---|---|
| `module_current_A` | A | `module_load_path` |
| `I1_A` ... `I4_A` | A | `cell1_branch` ... `cell4_branch` |
| `terminal_V` | V | `positive_node1-negative_node1` |
| `V1_V` ... `V4_V` | V | `positive_node1-negative_node1` ... `positive_node4-negative_node4` |
| `surface1_C` ... `surface4_C` | degC | `cell1_surface` ... `cell4_surface` |
| `ambient_C` | degC | `chamber_ambient` |

The terminal is on the position-1 side of both rails. Negative node 1 is the
potential reference, 0 V. Positive segment j connects p_j to p_(j+1); negative
segment j connects n_j to n_(j+1). Reported positive-rail drop is p_(j+1)-p_j;
negative-rail drop is n_j-n_(j+1). Cell voltage is p_j-n_j. The present model has
no additional external terminal leads or converter. A voltage measured at another
location cannot silently stand in for the modeled terminal.

Each channel names its own timestamp column in metadata. Synchronous acquisition
may explicitly use `time_s` for every channel. Otherwise retain columns such as
`I1_time_s`. Every channel clock must increase, remain finite and satisfy the
declared gap/alignment checks against the common time. Timestamp agreement alone
does not prove analog synchronization or remove filtering latency.

Currents may declare `discharge_positive` or `charge_positive`. The only numerical
conversion is multiplication by -1 when charge-positive is declared; the original
bytes remain unchanged. Values must already be in A, V, degC and s. No gain,
offset, unit guessing, current-sum normalization or automatic time shift is applied.

## Required metadata

```json
{
  "schema_version": 1,
  "data_kind": "experimental",
  "dataset_id": "a unique lab record identifier",
  "cell_order": ["P7", "P17", "P19", "P13"],
  "time_unit": "s",
  "time_origin": "documented elapsed-time origin relative to the load schedule",
  "preparation": {
    "history": "charge termination, previous use and rest preparation",
    "initial_soc": [0.70, 0.70, 0.70, 0.70],
    "initial_polarization_V": [0.0, 0.0, 0.0, 0.0],
    "rest_s": 0,
    "source": "actual preparation log and uncertainty, not assumed from voltage fit"
  },
  "synchronization": {
    "method": "actual acquisition/trigger method",
    "evidence": "clock and filtering/latency documentation",
    "alignment_tolerance_s": 0.001,
    "maximum_gap_s": 1.5
  },
  "channels": {
    "module_current_A": {
      "unit": "A",
      "polarity": "discharge_positive",
      "location": "module_load_path",
      "sensor_id": "instrument/channel identifier",
      "time_column": "time_s",
      "calibration": {
        "status": "documented",
        "source": "certificate, range, conversion procedure and uncertainty basis",
        "date": "YYYY-MM-DD",
        "absolute_uncertainty": 0.01
      }
    }
  }
}
```

**This abbreviated example is not a valid complete measurement package and its
numbers are not default requirements or calibration values.** Include all 15
channels, with their actual metadata. Voltage polarity must be
`positive_minus_negative`. Temperature channels do not need a polarity field.
Use `status: "unknown"` and null uncertainty when documentation is missing;
that produces an explicit evidence issue, not a substituted tolerance. Real
measurements require positive finite stated uncertainties. Dates and documents
are recorded assertions; the software cannot certify their authenticity or
metrological sufficiency.

Preparation values are examples of the required shape, not a sanctioned way to
infer initial SOC. Record the evidence and uncertainty behind them. Unknown
preparation, sensor mapping, synchronization or calibration is reported as missing
evidence. A different cell order or voltage location fails the structural check
for this application version.

## Commands and interpretation

```powershell
$env:PYTHONPATH = 'src'
python -m voltforge.simulation validate --measurements PATH_TO_PACKAGE --out reports/new_measurement_check
python -m voltforge.simulation compare --workspace reports/module_simulation_v1 --scenario equal_soc --measurements PATH_TO_PACKAGE --out reports/new_measurement_comparison
```

Validation records missing/nonfinite channels, invalid units, gaps, duplicate or
backward timestamps, mapping/location problems and per-channel clock skew. It
reports the unchanged branch sum minus module current: mean, RMS, maximum,
worst source row and a conservative sum of declared absolute current uncertainty
bounds when available. That arithmetic does not verify the stated uncertainty
or absorb unknown synchronization errors. Neither uncertain current source is
chosen as ground truth merely because it fits the model.

Comparison reports sample/time RMSE, bias and maximum for terminal and cell-node
voltages and individual/module currents, plus source rows and temperatures.
Predictions are interpolated within a simulated interval using its endpoint
solution **before any load switch**; they never interpolate a voltage ramp across
an instantaneous load change. Module input current is held on its declared
interval. No comparison is made outside simulated time support or when alignment
fails. No measured voltage initializes or calibrates the model. Differences
between recorded preparation/load and configured assumptions are explicit issues.

The current comparison uses the configured load, not an automatically chosen
measurement channel as its driver. For a future record with a different waveform,
configure a sourced piecewise-constant load and initial state before comparison.
The source-reference current discrepancy must be resolved before interpreting
module prediction errors. Temperatures are observations only; no temperature
prediction or parameter-temperature law exists here.

Exit code 0 means the requested calculation completed, **not an accuracy pass**.
Structural/timing failures return code 2. Current inconsistency or missing
calibration can still produce useful diagnostic output with explicit issues.
Experimental acceptance needs suitable real measurements, their uncertainty,
a frozen assessment allocation and sourced decision criteria.

## Synthetic fixture

`scripts/make_module_fixture.py` generates an explicitly labelled synthetic
package from a saved simulation with a known +10 mV voltage offset. It tests
ingestion/comparison plumbing; it is not independent verification of that
simulation or experimental evidence. Separate analytical tests verify dynamics.
Its `data_kind: "synthetic_fixture"` always leaves experimental validation at
**awaiting suitable measurements**. Do not relabel it as experimental.
