"""Independent expectations for conversions, missingness, ordering and mapping."""
from io import BytesIO
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from scipy.io import savemat

from voltforge.data.archive import Archive, locate_archive, run_factors
from voltforge.data.cli import validate_splits
from voltforge.data.inspection import (convert, discharge_current, time_audit,
    contiguous_segments, kcl_audit, raw_module, inspect_cell)
from voltforge.data.matlab import cell_mat, module_mat, scalar_string, table_pool

ROOT = Path(__file__).resolve().parents[1]


def test_units_independent_physical_values():
    assert convert([1500], "mA", "A")[0] == 1.5
    assert convert([2500], "ms", "s")[0] == 2.5
    assert convert([4200], "mV", "V")[0] == 4.2
    assert convert([3], "mOhm", "Ohm")[0] == .003
    assert convert([23], "degC", "degC")[0] == 23
    with pytest.raises(ValueError):
        convert([3], "mOhm", "A")


def test_sign_is_explicit_and_charge_becomes_negative():
    np.testing.assert_array_equal(discharge_current([-14.55, 6.466, 0], "charge"), [14.55, -6.466, 0])
    np.testing.assert_array_equal(discharge_current([2, -3], "discharge"), [2, -3])
    with pytest.raises(ValueError):
        discharge_current([1], "auto")


def test_timestamp_gaps_duplicates_backwards_preserve_source_rows():
    # Synthetic timestamps for software testing ONLY.
    t = [0, 1, 1, 5, 4, np.nan, 6]
    result = time_audit(t, 1, [2, 3, 4, 5, 6, 7, 8])
    assert result["nonfinite_timestamps"] == 1
    assert result["duplicate_timestamps"] == 1
    assert result["backwards_intervals"] == 1
    assert result["gaps"] == [dict(after_source_row=4, before_source_row=5, start_s=1., end_s=5., interval_s=4.)]
    assert [list(s) for s in contiguous_segments([0, 1, 5, 6], 1.5)] == [[0, 1], [2, 3]]


def test_conservation_does_not_fill_missing_branch_with_zero():
    f = pd.DataFrame({"module_current_A": [10., 10., 10.], "step_index": [5, 5, 5],
                      "branch_1_A": [1., 1., 1.], "branch_2_A": [2., 2., 2.],
                      "branch_3_A": [3., 3., 3.], "branch_4_A": [4., 5., np.nan]})
    residual, report = kcl_audit(f)
    np.testing.assert_equal(residual, [0., 1., np.nan])
    assert report["overall"]["mean"] == .5
    assert report["overall"]["missing_or_nonfinite"] == 1
    assert report["acceptance_tolerance_A"] is None


def test_characterization_fixture_arrays_and_missing_field():
    # Explicitly synthetic, in-memory MAT fixture; never written to data/reports.
    stream = BytesIO()
    savemat(stream, {"TimeData": [0., 10., 20.], "CurrentData": [-.25]*3,
                    "OCV": [4.2, 4.1, 4.0], "TempData": [23., 23., 23.]})
    frame = cell_mat(stream.getvalue(), "pseudo_ocv")
    assert list(frame.TimeData) == [0, 10, 20]
    assert frame.OCV.iloc[-1] == 4.
    with pytest.raises(ValueError, match="Missing characterization"):
        cell_mat(stream.getvalue(), "hppc_ms")


def test_integral_units_and_gap_refusal():
    # Synthetic 1 A discharge lasting 20 seconds: independently 1/180 Ah.
    class Fixture:
        def __init__(self, times):
            stream = BytesIO()
            savemat(stream, {"TimeData": times, "CurrentData": [-1., -1., -1.],
                            "OCV": [4.2, 3.5, 2.5], "TempData": [23., 23., 23.]})
            self.blob = stream.getvalue()

        def read(self, _):
            return self.blob

    _, good = inspect_cell(Fixture([0., 10., 20.]), "TEST_ONLY", "pseudo_ocv")
    assert good["observed_discharge_integral_Ah"] == pytest.approx(1/180)
    _, gap = inspect_cell(Fixture([0., 10., 100.]), "TEST_ONLY", "pseudo_ocv")
    assert gap["observed_discharge_integral_Ah"] is None


def test_unexpected_mcos_layout_and_string_rejected():
    with pytest.raises(ValueError):
        scalar_string(np.array([1, 2, 1, 1, 2, 0], dtype=np.uint64))
    stream = BytesIO()
    savemat(stream, {"x": [1., 2.]})
    with pytest.raises(ValueError, match="Missing MATLAB"):
        table_pool(stream.getvalue())


def test_factor_units_and_unknown_experiment_rejection():
    r = run_factors("M1_NMC_Unaged_R3_T25")
    assert r["interconnect_ohm"] == .003
    assert r["ambient_setpoint_C"] == 25
    with pytest.raises(ValueError):
        run_factors("M1_NMC_Unaged_R3000_T25")


def test_split_disjointness_and_quarantine():
    s = json.loads((ROOT / "configs/splits.json").read_text())
    runs = [{**run_factors(name), "cells": ["P1", "P2", "P3", "P4"]}
            for g in ("calibration", "development_validation", "final_assessment", "quarantine") for name in s[g]]
    validate_splits(s, runs)
    s["development_validation"].append(s["final_assessment"][0])
    with pytest.raises(ValueError, match="disjoint"):
        validate_splits(s, runs)


def test_no_final_or_aged_run_in_initial_inspection():
    s = json.loads((ROOT / "configs/splits.json").read_text())
    assert not set(s["initial_inspection"]) & set(s["final_assessment"] + s["quarantine"])
    assert s["quarantine"] == ["M2_NMC_Unaged_R1_T25"]


@pytest.fixture(scope="module")
def archive():
    try:
        path = locate_archive(ROOT)
    except ValueError:
        pytest.skip("Real-data integration tests require the original official archive")
    a = Archive(path)
    yield a
    a.close()


@pytest.fixture(scope="module")
def baseline(archive):
    return raw_module(archive.read("M1_NMC_Unaged_R0_T25.xlsx"))


def test_real_raw_parser_against_inspected_excel_values(baseline):
    raw, frame, meta = baseline
    # Values inspected directly in original Excel Data rows 2..5, before implementation.
    assert len(frame) == 33079
    assert meta["raw_test_name"] == "TEST_53_NMC_R0_T25_NEW_DOE2"
    assert list(frame.source_xlsx_row.iloc[:4]) == [2, 3, 4, 5]
    assert list(frame.source_mat_row.iloc[:4]) == [1, 2, 3, 4]
    assert frame.time_s.iloc[0] == 1.0001
    assert frame.module_voltage_V.iloc[0] == pytest.approx(3.469592332839966, abs=1e-12)
    assert frame.hall_1_V.iloc[0] == pytest.approx(2.495847702026367, abs=1e-12)
    assert frame.surface_1_C.iloc[0] == pytest.approx(25.313634872436523, abs=1e-12)
    assert frame.ambient_C.iloc[0] == pytest.approx(25.827146530151367, abs=1e-12)
    assert str(frame.date_time_local_unspecified_zone.iloc[0]) == "2022-12-21 07:54:22.441000"
    # Protocol expectations independent of sign-conversion implementation.
    assert frame.loc[frame.step_index == 2, "module_current_A"].max() < -6.
    assert frame.loc[frame.step_index == 5, "module_current_A"].min() > 14.
    assert raw["Internal Resistance(Ohm)"].isna().all()


def test_real_matlab_labels_and_independent_raw_agreement(archive, baseline):
    _, raw, _ = baseline
    m, cells = module_mat(archive.read("M1_NMC_Unaged_R0_T25.mat"))
    # Article Table 5 row 53 independently specifies these cells in this order.
    assert cells == ["P7", "P17", "P19", "P13"]
    np.testing.assert_array_equal(m.Test_Times, raw.time_s)
    np.testing.assert_array_equal(m.VoltageV, raw.module_voltage_V)
    np.testing.assert_array_equal(m.CurrentA, -raw.module_current_A)
    # Temperatures after the initial samples may differ: audit, do not assume equality.
    assert m.TemperatureC_Cell_1.iloc[0] == raw.surface_1_C.iloc[0]


def test_real_row32_metadata_contradiction_is_preserved(archive):
    _, cells = module_mat(archive.read("M2_NMC_Unaged_R1_T25.mat"), metadata_only=True)
    assert cells == ["P20", "P11", "P17", "Y1"]


def test_real_characterization_inspected_values(archive):
    p = cell_mat(archive.read("OCVDis_P7.mat"), "pseudo_ocv")
    assert len(p) == 7199
    assert p.TimeData.iloc[0] == 0
    assert p.TimeData.iloc[1] == 10
    assert p.OCV.iloc[0] == pytest.approx(4.17803001, abs=5e-9)
    assert p.CurrentData.max() < 0
    assert p.OCV.iloc[-1] < 2.5
