import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from voltforge.models import thermal_v1
from tests.test_thermal_v1 import make_frame, make_models


def test_ledger_closes_with_irregular_steps():
    models = make_models()
    steps = [0.25, 0.25, 0.1, 1.0, 0.4, 2.0, 0.05]
    times = [0.0]
    t = 0.0
    while t < 100.0:
        for s in steps:
            t += s
            times.append(t)
            if t >= 100.0:
                break
        if t >= 100.0:
            break
    times = np.array(times)
    r0_loss = np.zeros((len(times), 4))
    for j in range(len(times)):
        for k in range(4):
            r0_loss[j, k] = 0.3 + 0.1 * np.sin(times[j]) + 0.05 * k
    pos_rail = np.full((len(times), 3), 0.02)
    neg_rail = np.full((len(times), 3), 0.01)
    frame = make_frame(times, r0_loss=r0_loss, pos_rail=pos_rail, neg_rail=neg_rail)
    params = {
        'heat_capacity_J_per_K': [69.25] * 4,
        'ambient_conductance_W_per_K': [0.15] * 4,
        'neighbour_conductance_W_per_K': [0.05] * 3,
        'rail_heat_to_cells_fraction': 0.5,
    }
    out = thermal_v1.simulate(frame, models, params, initial_C=[25, 26, 24, 25], ambient_C=25)
    scale = max(1, out.generated_in_cells_J.iloc[-1])
    for _, row in out.iterrows():
        assert abs(row['ledger_residual_J']) <= 1e-9 * scale
    assert thermal_v1.summarize(out, {})['relative_ledger_residual'] < 1e-9


def test_parameter_and_frame_validation():
    models = make_models()
    times = [0.0, 1.0, 2.0]
    frame = make_frame(times)
    base_params = {
        'heat_capacity_J_per_K': [50.0, 50.0, 50.0, 50.0],
        'ambient_conductance_W_per_K': [0.15, 0.15, 0.15, 0.15],
        'neighbour_conductance_W_per_K': [0.05, 0.05, 0.05],
        'rail_heat_to_cells_fraction': 0.5,
    }
    with pytest.raises(ValueError):
        thermal_v1.simulate(frame, models, dict(base_params, heat_capacity_J_per_K=[-1, 50, 50, 50]), [25, 25, 25, 25], 25)
    with pytest.raises(ValueError):
        thermal_v1.simulate(frame, models, dict(base_params, heat_capacity_J_per_K=[0, 50, 50, 50]), [25, 25, 25, 25], 25)
    with pytest.raises(ValueError):
        thermal_v1.simulate(frame, models, dict(base_params, ambient_conductance_W_per_K=[-0.1, 0.1, 0.1, 0.1]), [25, 25, 25, 25], 25)
    with pytest.raises(ValueError):
        thermal_v1.simulate(frame, models, dict(base_params, neighbour_conductance_W_per_K=[-0.1, 0, 0]), [25, 25, 25, 25], 25)
    with pytest.raises(ValueError):
        thermal_v1.simulate(frame, models, dict(base_params, rail_heat_to_cells_fraction=-0.1), [25, 25, 25, 25], 25)
    with pytest.raises(ValueError):
        thermal_v1.simulate(frame, models, dict(base_params, rail_heat_to_cells_fraction=1.1), [25, 25, 25, 25], 25)
    with pytest.raises(ValueError):
        thermal_v1.simulate(frame, models, dict(base_params, heat_capacity_J_per_K=[50, 50, 50]), [25, 25, 25, 25], 25)
    with pytest.raises(ValueError):
        thermal_v1.simulate(frame, models, dict(base_params, neighbour_conductance_W_per_K=[0.05, 0.05, 0.05, 0.05]), [25, 25, 25, 25], 25)
    bad_g = dict(base_params)
    bad_g['ambient_conductance_W_per_K'] = [float('nan'), 0.15, 0.15, 0.15]
    with pytest.raises(ValueError):
        thermal_v1.simulate(frame, models, bad_g, [25, 25, 25, 25], 25)
    with pytest.raises(ValueError):
        thermal_v1.simulate(frame, models, base_params, [float('nan'), 25, 25, 25], 25)
    bad_frame = make_frame([0, 1, 3])
    bad_frame['step_s'] = [1, 1, 0]
    with pytest.raises(ValueError):
        thermal_v1.simulate(bad_frame, models, base_params, [25, 25, 25, 25], 25)
    empty = pd.DataFrame()
    res = thermal_v1.simulate(empty, models, base_params, [25, 25, 25, 25], 25)
    assert isinstance(res, pd.DataFrame)
    assert len(res) == 0


def test_real_engine_integration():
    case = json.loads(Path('reports/module_simulation_v1/configured/equal_soc.json').read_text())
    from voltforge.simulation import workflow as w
    frame = w.execute_case(case, None).frame
    cfg = json.loads(Path('configs/thermal_v1.json').read_text())
    params = {k: cfg[k]['value'] for k in ['heat_capacity_J_per_K', 'ambient_conductance_W_per_K', 'neighbour_conductance_W_per_K', 'rail_heat_to_cells_fraction']}
    out = thermal_v1.simulate(frame, case['models'], params, case['temperature']['assumed_surface_C'], case['temperature']['assumed_ambient_C'])
    assert len(out) == len(frame)
    for i in range(1, 5):
        assert np.all(np.isfinite(out[f'T{i}_C']))
        T = out[f'T{i}_C'].to_numpy()
        assert np.all(np.diff(T) >= -1e-12)
    Cth = np.array(params['heat_capacity_J_per_K'])
    peak_rise = 0.0
    for i in range(1, 5):
        T = out[f'T{i}_C'].to_numpy()
        rise = T - T[0]
        peak_rise = max(peak_rise, rise.max())
    rates = np.column_stack([out[f'heat{k}_W'].to_numpy() / Cth[k-1] for k in range(1, 5)])   # K/s per cell
    bound = np.concatenate([[0.0], np.cumsum(rates.max(axis=1)[:-1] * out.step_s.to_numpy()[:-1])])
    temps = np.column_stack([out[f'T{k}_C'].to_numpy() for k in range(1, 5)])
    hottest_rise = temps.max(axis=1) - temps[0].max()
    assert np.all(hottest_rise <= bound + 1e-12)
    assert hottest_rise.max() > 0
    summary = thermal_v1.summarize(out, params)
    assert summary['relative_ledger_residual'] < 1e-9
    for k in ['peak_cell_temperature_C', 'peak_cell', 'maximum_spread_K']:
        assert k in summary
    assert 'not validated' in summary['classification']
    print(f'PEAK_RISE_K={peak_rise}')
    print(f'MAX_SPREAD_K={summary["maximum_spread_K"]}')


@pytest.mark.parametrize('step', [30.0, 10.0, 1.0, 0.1])
def test_decaying_rc_heat_matches_analytic_temperature_on_every_saved_grid(step):
    # Independent solution of dT/dt + .1*(T-25) = 10*exp(-t/5).
    times = np.arange(0.0, 30.0 + step/2, step)
    vp = np.zeros((len(times), 4))
    vp[:, 0] = np.exp(-times/10)
    frame = make_frame(times, polarization=vp)
    params = dict(heat_capacity_J_per_K=[1.0]*4, ambient_conductance_W_per_K=[0.1]*4,
                  neighbour_conductance_W_per_K=[0.0]*3, rail_heat_to_cells_fraction=0.5)
    out = thermal_v1.simulate(frame, make_models(r1=0.1, tau_s=10), params, [25.0]*4, 25.0)
    expected = 25 + 100*(np.exp(-times/10)-np.exp(-times/5))
    np.testing.assert_allclose(out.T1_C, expected, rtol=0, atol=1e-9)
    np.testing.assert_allclose(out[['T2_C', 'T3_C', 'T4_C']], 25.0, rtol=0, atol=1e-9)
    assert out.generated_in_cells_J.iloc[-1] == pytest.approx(50*(1-np.exp(-6)), abs=1e-10)
    assert thermal_v1.summarize(out, params)['relative_ledger_residual'] < 1e-9


def test_nonzero_current_rc_modes_include_resonant_forcing():
    times = np.array([0.0, 10.0, 30.0])
    current = np.zeros((len(times), 4)); current[:, 0] = 1.0
    vp = np.zeros_like(current); vp[:, 0] = 0.1+0.9*np.exp(-times/10)
    frame = make_frame(times, current=current, polarization=vp)
    params = dict(heat_capacity_J_per_K=[1.0]*4, ambient_conductance_W_per_K=[0.1]*4,
                  neighbour_conductance_W_per_K=[0.0]*3, rail_heat_to_cells_fraction=0.5)
    out = thermal_v1.simulate(frame, make_models(r1=0.1, tau_s=10), params, [25.0]*4, 25.0)
    # q(t)=.1+1.8*exp(-t/10)+8.1*exp(-t/5). The first decay resonates with cooling.
    expected = 25 + (1-np.exp(-times/10)) + 1.8*times*np.exp(-times/10)
    expected += 81*(np.exp(-times/10)-np.exp(-times/5))
    np.testing.assert_allclose(out.T1_C, expected, rtol=0, atol=1e-9)


@pytest.mark.parametrize('kind', ['backwards', 'nan_time', 'nan_step', 'positive_terminal_step',
                                 'nan_loss', 'nan_current', 'nan_polarization', 'negative_loss'])
def test_invalid_saved_trajectory_is_rejected(kind):
    frame = make_frame([0.0, 1.0])
    if kind == 'backwards':
        frame['time_s'] = [0.0, -1.0]; frame['step_s'] = [-1.0, 0.0]
    elif kind == 'nan_time':
        frame.loc[1, 'time_s'] = np.nan
    elif kind == 'nan_step':
        frame.loc[0, 'step_s'] = np.nan
    elif kind == 'positive_terminal_step':
        frame.loc[1, 'step_s'] = 100.0
    else:
        column = {'nan_loss': 'R0_loss1_W', 'nan_current': 'I1_A',
                  'nan_polarization': 'polarization1_V', 'negative_loss': 'R0_loss1_W'}[kind]
        frame.loc[0, column] = -1.0 if kind == 'negative_loss' else np.nan
    params = dict(heat_capacity_J_per_K=[50.0]*4, ambient_conductance_W_per_K=[0.1]*4,
                  neighbour_conductance_W_per_K=[0.0]*3, rail_heat_to_cells_fraction=0.5)
    with pytest.raises(ValueError):
        thermal_v1.simulate(frame, make_models(), params, [25.0]*4, 25.0)


@pytest.mark.parametrize('column', ['T1_C', 'ledger_residual_J', 'generated_in_cells_J'])
def test_summary_rejects_nonfinite_temperature_or_energy(column):
    params = dict(heat_capacity_J_per_K=[50.0]*4, ambient_conductance_W_per_K=[0.1]*4,
                  neighbour_conductance_W_per_K=[0.0]*3, rail_heat_to_cells_fraction=0.5)
    out = thermal_v1.simulate(make_frame([0.0, 1.0]), make_models(), params, [25.0]*4, 25.0)
    out.loc[0, column] = np.nan
    with pytest.raises(ValueError, match='finite'):
        thermal_v1.summarize(out, params)
