import json

import numpy as np
import pandas as pd
import pytest

from voltforge.project import engineering


@pytest.mark.parametrize('limit', [float('nan'), float('inf'), float('-inf'), '4.5', True, {}])
def test_invalid_limit_is_not_a_configured_requirement(limit):
    result = engineering.screen(frame([3, 4]), None,
        {'peak_branch_current_A': {'limit': limit, 'documented_source': 'Declared test target'}})
    req = result['requirements']['peak_branch_current_A']
    assert req['status'] == 'requirement not configured'
    assert req['reason'] == 'Limit must be a finite number'


@pytest.mark.parametrize('source', [{}, False, 123])
def test_requirement_source_must_be_nonempty_text(source):
    result = engineering.screen(frame([3, 4]), None,
        {'peak_branch_current_A': {'limit': 5.0, 'documented_source': source}})
    assert result['requirements']['peak_branch_current_A']['status'] == 'requirement not configured'


def test_thermal_alignment_uses_times_and_positions_not_index_labels():
    electrical = frame([3, 4])
    thermal = pd.DataFrame({'time_s': [0.0, 1.0], 'T1_C': [25.0, 60.0],
        'T2_C': [25.0]*2, 'T3_C': [25.0]*2, 'T4_C': [25.0]*2}, index=[10, 11])
    metric = engineering.metrics(electrical, thermal)['peak_cell_temperature_C']
    assert metric['value'] == 60.0 and metric['time_s'] == 1.0 and metric['component'] == 'cell_1'
    electrical['time_s'] += 10000
    thermal['time_s'] = [10000.05, 10001.05]
    with pytest.raises(ValueError, match='samples differ'):
        engineering.metrics(electrical, thermal)


def frame(i1, module=14.0, others=3.0, step=1.0) -> pd.DataFrame:
    if hasattr(i1, "__iter__") and not isinstance(i1, str):
        i1_list = list(i1)
    else:
        i1_list = [i1]
    n = len(i1_list)
    time_s = [float(i) for i in range(n)]
    step_s = []
    for i in range(n):
        if i == n - 1:
            step_s.append(0.0)
        else:
            step_s.append(float(step))
    if isinstance(module, (int, float)):
        module_current_A = [float(module)] * n
    else:
        module_current_A = [float(m) for m in module]
    terminal_V = [3.5] * n
    I1_A = [float(x) for x in i1_list]
    I2_A = [float(others)] * n
    I3_A = [float(others)] * n
    I4_A = [float(others)] * n
    return pd.DataFrame(
        {
            "time_s": time_s,
            "step_s": step_s,
            "module_current_A": module_current_A,
            "terminal_V": terminal_V,
            "I1_A": I1_A,
            "I2_A": I2_A,
            "I3_A": I3_A,
            "I4_A": I4_A,
        }
    )


def test_unconfigured():
    df = frame([3, 4, 5])
    res = engineering.screen(df, thermal=None, requirements=None)
    reqs = res["requirements"]
    for name in engineering.LIMITS:
        assert reqs[name]["status"] == "requirement not configured"
    reqs2 = engineering.screen(
        df,
        thermal=None,
        requirements={"peak_branch_current_A": {"limit": 4.5, "documented_source": "  "}},
    )["requirements"]
    assert reqs2["peak_branch_current_A"]["status"] == "requirement not configured"


def test_peak_current_violation():
    df = frame([3, 4, 5.2, 4, 3], module=14.0, others=3.0, step=1.0)
    res = engineering.screen(
        df,
        thermal=None,
        requirements={"peak_branch_current_A": {"limit": 4.5, "documented_source": "test"}},
    )
    r = res["requirements"]["peak_branch_current_A"]
    assert r["status"] == "simulated violation of configured limit"
    assert abs(r["value"] - 5.2) < 1e-12
    assert abs(r["margin"] - (-0.7)) < 1e-12  # limit - value = 4.5 - 5.2 = -0.7
    assert abs(r["time_s"] - 2.0) < 1e-12
    assert r["component"] == "cell_1"
    assert abs(r["first_crossing_time_s"] - 2.0) < 1e-12
    assert abs(r["time_above_limit_s"] - 1.0) < 1e-12


def test_no_violation_wording():
    df = frame([3, 4, 5.2, 4, 3], module=14.0, others=3.0, step=1.0)
    res = engineering.screen(
        df,
        thermal=None,
        requirements={"peak_branch_current_A": {"limit": 6, "documented_source": "test"}},
    )
    r = res["requirements"]["peak_branch_current_A"]
    assert r["status"] == "no sampled exceedance; insufficient evidence for a pass"
    assert abs(r["margin"] - 0.8) < 1e-12  # 6 - 5.2 = 0.8


def test_partial_run():
    df = frame([3, 4, 5.2, 4, 3], module=14.0, others=3.0, step=1.0)
    res1 = engineering.screen(
        df,
        thermal=None,
        requirements={"peak_branch_current_A": {"limit": 6, "documented_source": "test"}},
        completed=False,
    )
    assert res1["requirements"]["peak_branch_current_A"]["status"] == "insufficient simulation"
    res2 = engineering.screen(
        df,
        thermal=None,
        requirements={"peak_branch_current_A": {"limit": 4.5, "documented_source": "test"}},
        completed=False,
    )
    assert res2["requirements"]["peak_branch_current_A"]["status"] == "simulated violation of configured limit"


def test_imbalance_active_floor():
    # row0: module 14 A, currents I1..I4 = [5,3,3,3]
    df = pd.DataFrame(
        {
            "time_s": [0.0, 1.0],
            "step_s": [1.0, 0.0],
            "module_current_A": [14.0, 0.2],
            "terminal_V": [3.5, 3.5],
            "I1_A": [5.0, 0.3],
            "I2_A": [3.0, -0.1],
            "I3_A": [3.0, -0.1],
            "I4_A": [3.0, -0.1],
        }
    )
    ps = engineering.per_sample(df, thermal=None)
    imb_row0 = ps.at[0, "current_imbalance_pct"]
    # per_sample imbalance row0 = 100*2/3.5 = 57.142857142857146
    assert abs(imb_row0 - (100.0 * 2.0 / 3.5)) < 1e-9
    assert np.isnan(ps.at[1, "current_imbalance_pct"])
    mets = engineering.metrics(df, thermal=None)
    assert mets["current_imbalance_pct"]["active_samples"] == 1
    # only rest row and configured imbalance limit -> not evaluable
    df_rest = pd.DataFrame(
        {
            "time_s": [1.0],
            "step_s": [0.0],
            "module_current_A": [0.2],
            "terminal_V": [3.5],
            "I1_A": [0.3],
            "I2_A": [-0.1],
            "I3_A": [-0.1],
            "I4_A": [-0.1],
        }
    )
    res_rest = engineering.screen(
        df_rest,
        thermal=None,
        requirements={"current_imbalance_pct": {"limit": 50, "documented_source": "test"}},
    )
    assert res_rest["requirements"]["current_imbalance_pct"]["status"] == "not evaluable"


def test_temperature():
    df = frame([3, 4, 5.2, 4, 3], module=14.0, others=3.0, step=1.0)
    # 5 rows, time_s 0-4
    thermal = pd.DataFrame(
        {
            "time_s": [0.0, 1.0, 2.0, 3.0, 4.0],
            "T1_C": [40.0, 41.0, 42.0, 43.0, 44.0],
            "T2_C": [40.0, 41.0, 42.0, 43.0, 44.0],
            "T3_C": [40.0, 41.0, 42.0, 47.0, 44.0],  # reaches 47.0 at t=3
            "T4_C": [40.0, 41.0, 42.0, 43.0, 44.0],
        }
    )
    mets = engineering.metrics(df, thermal=thermal)
    pt = mets["peak_cell_temperature_C"]
    assert abs(pt["value"] - 47.0) < 1e-12
    assert pt["component"] == "cell_3"
    assert abs(pt["time_s"] - 3.0) < 1e-12
    res_violation = engineering.screen(
        df,
        thermal=thermal,
        requirements={"peak_cell_temperature_C": {"limit": 45, "documented_source": "test"}},
    )
    r = res_violation["requirements"]["peak_cell_temperature_C"]
    assert r["status"] == "simulated violation of configured limit"
    assert abs(r["margin"] - (-2.0)) < 1e-12  # 45 - 47 = -2.0
    # maximum_temperature_spread_K equals hand-computed max over rows of (row max - row min)
    spreads = []
    for i in range(5):
        rowvals = [thermal.at[i, "T1_C"], thermal.at[i, "T2_C"], thermal.at[i, "T3_C"], thermal.at[i, "T4_C"]]
        spreads.append(max(rowvals) - min(rowvals))
    hand_max_spread = max(spreads)
    assert abs(mets["maximum_temperature_spread_K"]["value"] - hand_max_spread) < 1e-12
    res_ne = engineering.screen(
        df,
        thermal=None,
        requirements={"peak_cell_temperature_C": {"limit": 45, "documented_source": "test"}},
    )
    assert res_ne["requirements"]["peak_cell_temperature_C"]["status"] == "not evaluable"


def test_mismatched_and_empty():
    df = frame([3, 4, 5])
    thermal_bad = pd.DataFrame(
        {
            "time_s": [0.0, 1.0],  # different length
            "T1_C": [40.0, 41.0],
            "T2_C": [40.0, 41.0],
            "T3_C": [40.0, 41.0],
            "T4_C": [40.0, 41.0],
        }
    )
    with pytest.raises(ValueError):
        engineering.per_sample(df, thermal=thermal_bad)
    # empty frame (columns present, zero rows)
    df_empty = pd.DataFrame(
        columns=["time_s", "step_s", "module_current_A", "terminal_V", "I1_A", "I2_A", "I3_A", "I4_A"]
    )
    mets_empty = engineering.metrics(df_empty, thermal=None)
    for k, v in mets_empty.items():
        assert v["value"] is None
    res_empty = engineering.screen(df_empty, thermal=None, requirements={"peak_branch_current_A": {"limit": 4.5, "documented_source": "test"}})
    assert res_empty["requirements"]["peak_branch_current_A"]["status"] == "not evaluable"


def test_no_pass_verdicts():
    results_list = []
    df = frame([3, 4, 5])
    results_list.append(engineering.screen(df, thermal=None, requirements=None))
    df2 = frame([3, 4, 5.2, 4, 3])
    results_list.append(
        engineering.screen(
            df2,
            thermal=None,
            requirements={"peak_branch_current_A": {"limit": 4.5, "documented_source": "test"}},
        )
    )
    results_list.append(
        engineering.screen(
            df2,
            thermal=None,
            requirements={"peak_branch_current_A": {"limit": 6, "documented_source": "test"}},
        )
    )
    results_list.append(
        engineering.screen(
            df2,
            thermal=None,
            requirements={"peak_branch_current_A": {"limit": 6, "documented_source": "test"}},
            completed=False,
        )
    )
    df_rest = pd.DataFrame(
        {
            "time_s": [1.0],
            "step_s": [0.0],
            "module_current_A": [0.2],
            "terminal_V": [3.5],
            "I1_A": [0.3],
            "I2_A": [-0.1],
            "I3_A": [-0.1],
            "I4_A": [-0.1],
        }
    )
    results_list.append(
        engineering.screen(
            df_rest,
            thermal=None,
            requirements={"current_imbalance_pct": {"limit": 50, "documented_source": "test"}},
        )
    )
    combined = json.dumps(results_list)
    # 'pass' only appears inside 'insufficient evidence for a pass'
    # remove that phrase, then assert 'pass' not in remaining text case-insensitive
    combined_no_phrase = combined.replace("insufficient evidence for a pass", "")
    assert "pass" not in combined_no_phrase.lower()
    # json.dumps(..., allow_nan=False) succeeds
    json.dumps(results_list, allow_nan=False)
