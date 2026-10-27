import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from voltforge.models import thermal_v1
from voltforge.models.coupling_v2 import rc_interval
from voltforge.simulation import workflow as w


def make_models(r0=0.025, r1=0.025, tau_s=60.0):
    return [{'parameters_ohm': [r0, r1], 'tau_s': tau_s} for _ in range(4)]


def make_frame(times, *, r0_loss=None, current=None, polarization=None,
               pos_rail=None, neg_rail=None, default_zero=True):
    n = 4
    if r0_loss is None:
        r0_loss = np.zeros((len(times), n))
    elif np.ndim(r0_loss) == 1:
        r0_loss = np.tile(np.asarray(r0_loss, float)[None, :], (len(times), 1))
    else:
        r0_loss = np.asarray(r0_loss, float)

    if current is None:
        current = np.zeros((len(times), n))
    elif np.ndim(current) == 1:
        current = np.tile(np.asarray(current, float)[None, :], (len(times), 1))
    else:
        current = np.asarray(current, float)

    if polarization is None:
        polarization = np.zeros((len(times), n))
    elif np.ndim(polarization) == 1:
        polarization = np.tile(np.asarray(polarization, float)[None, :], (len(times), 1))
    else:
        polarization = np.asarray(polarization, float)

    if pos_rail is None:
        pos_rail = np.zeros((len(times), n - 1))
    elif np.ndim(pos_rail) == 1:
        pos_rail = np.tile(np.asarray(pos_rail, float)[None, :], (len(times), 1))
    else:
        pos_rail = np.asarray(pos_rail, float)

    if neg_rail is None:
        neg_rail = np.zeros((len(times), n - 1))
    elif np.ndim(neg_rail) == 1:
        neg_rail = np.tile(np.asarray(neg_rail, float)[None, :], (len(times), 1))
    else:
        neg_rail = np.asarray(neg_rail, float)

    times = np.asarray(times, float)
    step_s = np.zeros(len(times))
    if len(times) > 1:
        step_s[:-1] = times[1:] - times[:-1]
    step_s[-1] = 0.0

    data = {'time_s': times, 'step_s': step_s}
    for k in range(1, n + 1):
        data[f'I{k}_A'] = current[:, k - 1]
        data[f'polarization{k}_V'] = polarization[:, k - 1]
        data[f'R0_loss{k}_W'] = r0_loss[:, k - 1]
    for k in range(1, n):
        data[f'positive_rail{k}_loss_W'] = pos_rail[:, k - 1]
        data[f'negative_rail{k}_loss_W'] = neg_rail[:, k - 1]
    return pd.DataFrame(data)


def test_one_node_step():
    models = make_models()
    times = np.arange(0.0, 201.0, 1.0)
    r0_loss = np.full((len(times), 4), 2.0)
    frame = make_frame(times, r0_loss=r0_loss)
    params = {
        'heat_capacity_J_per_K': [50.0, 50.0, 50.0, 50.0],
        'ambient_conductance_W_per_K': [0.5, 0.5, 0.5, 0.5],
        'neighbour_conductance_W_per_K': [0.0, 0.0, 0.0],
        'rail_heat_to_cells_fraction': 0.5,
    }
    out = thermal_v1.simulate(frame, models, params, initial_C=[25.0, 25.0, 25.0, 25.0], ambient_C=25.0)
    for k in range(1, 5):
        T = out[f'T{k}_C'].to_numpy()
        expected = 25.0 + 4.0 * (1.0 - np.exp(-out['time_s'].to_numpy() / 100.0))
        assert np.max(np.abs(T - expected)) < 1e-9
    idx = np.where(np.isclose(out['time_s'].to_numpy(), 100.0))[0][0]
    for k in range(1, 5):
        assert abs((out[f'T{k}_C'].iloc[idx] - 25.0) - 4.0 * (1.0 - np.exp(-1.0))) < 1e-9


def test_insulated_heating():
    models = make_models()
    times = np.array([0.0, 1.0, 10.0, 50.0])
    r0_loss = np.full((len(times), 4), 2.0)
    frame = make_frame(times, r0_loss=r0_loss)
    params = {
        'heat_capacity_J_per_K': [50.0, 50.0, 50.0, 50.0],
        'ambient_conductance_W_per_K': [0.0, 0.0, 0.0, 0.0],
        'neighbour_conductance_W_per_K': [0.0, 0.0, 0.0],
        'rail_heat_to_cells_fraction': 0.5,
    }
    out = thermal_v1.simulate(frame, models, params, initial_C=[20.0, 20.0, 20.0, 20.0], ambient_C=25.0)
    for k in range(1, 5):
        T = out[f'T{k}_C'].to_numpy()
        expected = 20.0 + 2.0 * out['time_s'].to_numpy() / 50.0
        assert np.max(np.abs(T - expected)) < 1e-9


def test_passive_exchange():
    models = make_models()
    times = np.arange(0.0, 2000.0 + 1.0, 1.0)
    frame = make_frame(times)
    params = {
        'heat_capacity_J_per_K': [50.0, 50.0, 50.0, 50.0],
        'ambient_conductance_W_per_K': [0.0, 0.0, 0.0, 0.0],
        'neighbour_conductance_W_per_K': [1.0, 1.0, 1.0],
        'rail_heat_to_cells_fraction': 0.5,
    }
    out = thermal_v1.simulate(frame, models, params, initial_C=[30.0, 20.0, 20.0, 20.0], ambient_C=25.0)
    Cth = 50.0
    Tmat = np.column_stack([out[f'T{k}_C'].to_numpy() for k in range(1, 5)])
    sums = Tmat.sum(axis=1) * Cth
    assert np.max(np.abs(sums - sums[0])) < 1e-9
    Tmax = Tmat.max(axis=1)
    Tmin = Tmat.min(axis=1)
    for i in range(len(Tmax) - 1):
        assert Tmax[i + 1] <= Tmax[i] + 1e-12
        assert Tmin[i + 1] >= Tmin[i] - 1e-12
    assert np.max(np.abs(Tmat[-1] - 22.5)) < 1e-3


def test_equilibrium_without_heat():
    times = np.arange(0.0, 101.0, 1.0)
    frame = make_frame(times)
    models = make_models()
    params = {
        'heat_capacity_J_per_K': [50.0, 50.0, 50.0, 50.0],
        'ambient_conductance_W_per_K': [0.15, 0.15, 0.15, 0.15],
        'neighbour_conductance_W_per_K': [0.05, 0.05, 0.05],
        'rail_heat_to_cells_fraction': 0.5,
    }
    out = thermal_v1.simulate(frame, models, params, initial_C=[23.0, 23.0, 23.0, 23.0], ambient_C=23.0)
    for k in range(1, 5):
        T = out[f'T{k}_C'].to_numpy()
        assert np.max(np.abs(T - 23.0)) < 1e-12


def test_rail_heat_allocation():
    models = make_models()
    times = [0.0, 1.0]
    fraction = 0.5
    frame = make_frame(times, pos_rail=[1.0, 0.0, 0.0])
    cells, direct = thermal_v1.heat_inputs(frame, models, fraction)
    assert np.allclose(cells[0], [0.25, 0.25, 0, 0])
    assert abs(direct[0] - 0.5) < 1e-12
    assert abs(cells[0].sum() + direct[0] - 1.0) < 1e-12

    fraction = 1.0
    cells, direct = thermal_v1.heat_inputs(frame, models, fraction)
    assert np.allclose(cells[0], [0.5, 0.5, 0, 0])
    assert abs(direct[0] - 0.0) < 1e-12
    assert abs(cells[0].sum() + direct[0] - 1.0) < 1e-12

    fraction = 0.5
    frame = make_frame(times, neg_rail=[0.0, 0.0, 2.0])
    cells, direct = thermal_v1.heat_inputs(frame, models, fraction)
    assert np.allclose(cells[0], [0, 0, 0.5, 0.5])
    assert abs(direct[0] - 1.0) < 1e-12
    assert abs(cells[0].sum() + direct[0] - 2.0) < 1e-12


def test_exact_r1_interval_heat():
    import math

    models = make_models()
    models[0]['parameters_ohm'][1] = 0.01
    models[0]['tau_s'] = 10.0
    times = [0.0, 10.0]
    current = np.array([[2.0, 0, 0, 0], [0.0, 0, 0, 0]])
    frame = make_frame(times, current=current)
    cells, _ = thermal_v1.heat_inputs(frame, models, 0.5)
    b = 0.02
    d = -0.02
    h = 10.0
    tau = 10.0
    R1 = 0.01
    energy = (b * b * h + 2 * b * d * tau * (1 - math.exp(-1)) + d * d * tau * (1 - math.exp(-2)) / 2) / R1
    assert abs(cells[0, 0] - energy / 10.0) < 1e-12
