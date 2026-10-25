"""Channel mapping and descriptive audits; no battery parameter fitting."""
from io import BytesIO
import re

import numpy as np
import pandas as pd

from .matlab import module_mat, cell_mat

RAW_MAP = {
    "Test_Time(s)": "time_s", "Step_Time(s)": "step_time_s", "Step_Index": "step_index",
    "Cycle_Index": "cycle_index", "Voltage(V)": "module_voltage_V", "Current(A)": "module_current_A",
}
PROCESSED_MAP = dict(zip(
    ["Test_Times", "Step_Times", "Step_Index", "Cycle_Index", "VoltageV", "CurrentA"], RAW_MAP.values()))


def discharge_current(values, source_positive):
    if source_positive not in ("charge", "discharge"):
        raise ValueError("Current sign must be declared, not guessed")
    return np.asarray(values, dtype=float) * (-1 if source_positive == "charge" else 1)


def convert(values, source_unit, target_unit):
    factors = {("s", "s"): 1., ("ms", "s"): 1e-3, ("A", "A"): 1., ("mA", "A"): 1e-3,
               ("V", "V"): 1., ("mV", "V"): 1e-3, ("mOhm", "Ohm"): 1e-3,
               ("degC", "degC"): 1.}
    if (source_unit, target_unit) not in factors:
        raise ValueError(f"Unsupported unit conversion {source_unit} -> {target_unit}")
    return np.asarray(values, dtype=float) * factors[source_unit, target_unit]


def raw_module(blob):
    with pd.ExcelFile(BytesIO(blob), engine="openpyxl") as book:
        if "Data" not in book.sheet_names or "Global_Info" not in book.sheet_names:
            raise ValueError("Expected Data and Global_Info sheets")
        raw = book.parse("Data")
        info = book.parse("Global_Info", header=None)
    if not raw.columns.is_unique or not set(RAW_MAP).issubset(raw.columns):
        raise ValueError("Missing or duplicate raw module headers")
    temperatures = {}
    for i in range(1, 6):
        candidates = [c for c in raw if re.fullmatch(rf"Aux_Temperature\(.+\)_{i}", str(c))]
        if len(candidates) != 1:
            raise ValueError(f"Ambiguous temperature channel {i}")
        temperatures[i] = candidates[0]
    expected_aux = [f"Aux_Voltage(V)_{i}" for i in range(1, 6)]
    if not set(expected_aux + ["Date_Time"]).issubset(raw.columns):
        raise ValueError("Missing raw Hall/power supply/date channel")
    normalized = pd.DataFrame({new: raw[old] for old, new in RAW_MAP.items()})
    normalized["module_current_A"] = discharge_current(normalized.module_current_A, "charge")
    normalized.insert(0, "source_xlsx_row", np.arange(2, len(raw) + 2))
    normalized.insert(1, "source_mat_row", np.arange(1, len(raw) + 1))
    normalized["date_time_local_unspecified_zone"] = pd.to_datetime(raw.Date_Time, errors="coerce")
    for i in range(1, 5):
        normalized[f"hall_{i}_V"] = raw[f"Aux_Voltage(V)_{i}"]
        normalized[f"surface_{i}_C"] = raw[temperatures[i]]
    normalized["hall_supply_V"] = raw["Aux_Voltage(V)_5"]
    normalized["ambient_C"] = raw[temperatures[5]]
    metadata = dict(raw_headers=list(raw.columns), raw_test_name=str(info.iloc[1, 3]),
                    global_info_start_datetime=str(info.iloc[4, 1]),
                    temperature_headers={str(k): v for k, v in temperatures.items()})
    return raw, normalized, metadata


def series_stats(values):
    a = np.asarray(values, dtype=float)
    finite = a[np.isfinite(a)]
    if not len(finite):
        return dict(count=0, missing_or_nonfinite=int(len(a)), min=None, max=None, mean=None,
                    rms=None, max_abs=None)
    return dict(count=int(len(finite)), missing_or_nonfinite=int(len(a) - len(finite)),
                min=float(finite.min()), max=float(finite.max()), mean=float(finite.mean()),
                rms=float(np.sqrt(np.mean(finite**2))), max_abs=float(np.abs(finite).max()))


def time_audit(time_s, nominal_s, row_numbers=None):
    t = np.asarray(time_s, dtype=float)
    rows = np.arange(1, len(t) + 1) if row_numbers is None else np.asarray(row_numbers)
    delta = np.diff(t)
    finite = delta[np.isfinite(delta)]
    gaps = np.flatnonzero(delta > 1.5 * nominal_s)
    return dict(rows=len(t), nonfinite_timestamps=int((~np.isfinite(t)).sum()),
                backwards_intervals=int((delta < 0).sum()), repeated_adjacent_timestamps=int((delta == 0).sum()),
                duplicate_timestamps=int(pd.Series(t).dropna().duplicated().sum()),
                start_s=float(t[0]) if len(t) and np.isfinite(t[0]) else None,
                end_s=float(t[-1]) if len(t) and np.isfinite(t[-1]) else None,
                interval_min_s=float(finite.min()) if len(finite) else None,
                interval_median_s=float(np.median(finite)) if len(finite) else None,
                interval_max_s=float(finite.max()) if len(finite) else None,
                interval_quantiles_s=np.quantile(finite, [.01, .1, .9, .99]).tolist() if len(finite) else [],
                gap_threshold_s=1.5 * nominal_s, gap_rule_status="provisional screening rule, not instrument accuracy",
                gaps=[dict(after_source_row=int(rows[i]), before_source_row=int(rows[i+1]),
                           start_s=float(t[i]), end_s=float(t[i+1]), interval_s=float(delta[i])) for i in gaps])


def contiguous_segments(time_s, gap_s):
    t = np.asarray(time_s, dtype=float)
    boundaries = np.flatnonzero((np.diff(t) > gap_s) | (np.diff(t) <= 0) |
                               ~np.isfinite(t[1:]) | ~np.isfinite(t[:-1])) + 1
    return [s for s in np.split(np.arange(len(t)), boundaries) if len(s)]


def kcl_audit(frame):
    branches = frame[[f"branch_{i}_A" for i in range(1, 5)]].to_numpy()
    # numpy sum propagates NaN; never pretend missing branch current is zero.
    residual = branches.sum(axis=1) - frame.module_current_A.to_numpy()
    steps = frame.step_index.to_numpy()
    report = {"definition": "sum(author branch discharge currents) - raw module discharge current [A]",
              "overall": series_stats(residual), "by_step": {}}
    for step in sorted(frame.step_index.dropna().unique()):
        report["by_step"][str(int(step))] = series_stats(residual[steps == step])
    # Descriptive one/two-sample alignment sensitivity only. No correction is applied.
    total = branches.sum(axis=1)
    module = frame.module_current_A.to_numpy()
    lag_stats = {}
    for lag in [-2, -1, 0, 1, 2]:
        a = total[max(0, lag):len(total)+min(0, lag)]
        b = module[max(0, -lag):len(module)+min(0, -lag)]
        lag_stats[str(lag)] = series_stats(a - b)
    report["sample_lag_sensitivity"] = lag_stats
    report["acceptance_tolerance_A"] = None
    report["tolerance_reason"] = "No end-to-end sensor uncertainty budget supplied; residuals are observations, not a precision acceptance test."
    return residual, report


def inspect_module(archive, run_id):
    raw, frame, meta = raw_module(archive.read(run_id + ".xlsx"))
    processed, cells = module_mat(archive.read(run_id + ".mat"))
    if len(frame) != len(processed):
        raise ValueError("Raw/processed row counts differ; explicit alignment required")
    differences = {}
    for old, new in PROCESSED_MAP.items():
        p = processed[old].to_numpy()
        if new == "module_current_A":
            p = discharge_current(p, "charge")
        differences[new] = series_stats(p - frame[new].to_numpy())
    # Never align by row index unless elapsed time equality has been verified.
    if not np.array_equal(processed.Test_Times.to_numpy(), frame.time_s.to_numpy()):
        raise ValueError("Raw and processed elapsed time differ; no implicit interpolation")
    for i in range(1, 5):
        frame[f"branch_{i}_A"] = discharge_current(processed[f"CurrentA_Cell_{i}"], "charge")
        differences[f"surface_{i}_C"] = series_stats(processed[f"TemperatureC_Cell_{i}"] - frame[f"surface_{i}_C"])
    differences["ambient_C"] = series_stats(processed.Ambient_TemperatureC - frame.ambient_C)
    residual, kcl = kcl_audit(frame)
    frame["kcl_residual_A"] = residual
    wall = frame.date_time_local_unspecified_zone
    elapsed_wall = (wall - wall.iloc[0]).dt.total_seconds().to_numpy()
    report = dict(run_id=run_id, cells=cells, metadata=meta,
        timestamp=time_audit(frame.time_s, 1., frame.source_xlsx_row),
        wall_timestamp=time_audit(elapsed_wall, 1., frame.source_xlsx_row),
        wall_minus_test_elapsed_s=series_stats(elapsed_wall - (frame.time_s.to_numpy()-frame.time_s.iloc[0])),
        raw_duplicate_rows=int(raw.duplicated().sum()),
        raw_missing_values={c: int(raw[c].isna().sum()) for c in raw},
        channels={c: series_stats(frame[c]) for c in frame.select_dtypes(include="number")},
        raw_vs_author_processed=differences, kcl=kcl, steps=[])
    for step, f in frame.groupby("step_index", sort=True):
        report["steps"].append(dict(step=int(step), rows=len(f), start_s=float(f.time_s.iloc[0]),
            end_s=float(f.time_s.iloc[-1]), duration_s=float(f.time_s.iloc[-1]-f.time_s.iloc[0]),
            source_first_xlsx_row=int(f.source_xlsx_row.iloc[0]), source_last_xlsx_row=int(f.source_xlsx_row.iloc[-1]),
            current_A=series_stats(f.module_current_A), voltage_V=series_stats(f.module_voltage_V)))
    discharge = frame.loc[frame.step_index == 5]
    dis_time = time_audit(discharge.time_s, 1., discharge.source_xlsx_row)
    integral_columns = ["module_current_A"] + [f"branch_{i}_A" for i in range(1,5)]
    if len(discharge) > 1 and not dis_time["gaps"] and not dis_time["backwards_intervals"] and np.isfinite(discharge[integral_columns]).all().all():
        report["observed_step5_integrals_Ah"] = {c:float(np.trapz(discharge[c], discharge.time_s)/3600.) for c in integral_columns}
    else:
        report["observed_step5_integrals_Ah"] = None
    return frame, report


def inspect_cell(archive, cell, protocol):
    base = f"{'OCVDis' if protocol == 'pseudo_ocv' else 'HPPC_MultiSine'}_{cell}.mat"
    raw = cell_mat(archive.read(base), protocol)
    frame = pd.DataFrame(dict(source_mat_row=np.arange(1, len(raw)+1), time_s=raw.TimeData,
        current_A=discharge_current(raw.CurrentData, "charge"),
        voltage_V=raw["OCV" if protocol == "pseudo_ocv" else "VoltageData"], surface_C=raw.TempData))
    for source, target in [("StepIndex", "step_index"), ("CycleIndex", "cycle_index")]:
        if source in raw:
            frame[target] = raw[source]
    report = dict(cell_id=cell, protocol=protocol, source_file=base,
        identification_chamber_setpoint_C=23, setpoint_source="Data in Brief Table 2 / section 3 (not a raw ambient channel)",
        timestamp=time_audit(frame.time_s, 10. if protocol == "pseudo_ocv" else 1.),
        duplicate_rows=int(raw.duplicated().sum()),
        channels={c: series_stats(frame[c]) for c in frame.select_dtypes(include="number")})
    if protocol == "pseudo_ocv":
        valid = np.isfinite(frame[["time_s", "current_A"]].to_numpy()).all()
        monotone = (np.diff(frame.time_s) > 0).all()
        # Do not integrate across missing intervals or silently sort timestamps.
        if valid and monotone and not report["timestamp"]["gaps"] and (frame.current_A > 0).all():
            report["observed_discharge_integral_Ah"] = float(np.trapz(frame.current_A, frame.time_s)/3600.)
        else:
            report["observed_discharge_integral_Ah"] = None
    else:
        report["steps"] = [{"step": int(step), "rows":len(f), "current_A":series_stats(f.current_A)}
                           for step, f in frame.groupby("step_index")]
        report["cycles"] = [int(x) for x in sorted(frame.cycle_index.unique())]
    return frame, report
