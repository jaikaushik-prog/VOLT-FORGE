"""Lumped four-node surface-equivalent thermal model, one-way coupled to a saved electrical run.

Heat sources come from the electrical trajectory under its left-held current convention:
per-cell R0 loss, exact per-interval R1 (polarization) resistor loss, and rail-segment loss
allocated to the two adjacent cells by a declared fraction, the remainder released directly to
ambient. Temperatures do not feed back into the frozen electrical parameters, reversible heat
is omitted, and the state is one surface-equivalent temperature per cell, never a core value.
Each held interval is integrated exactly with an augmented matrix exponential, which also gives
the exact interval integral of temperature for the energy ledger.
"""
import numpy as np
import pandas as pd
from scipy.linalg import expm

from .coupling_v2 import rc_interval

VERSION = 'lumped_four_node_v1_exact_rc'


def check_parameters(parameters, n=4):
    c = np.asarray(parameters['heat_capacity_J_per_K'], float)
    g = np.asarray(parameters['ambient_conductance_W_per_K'], float)
    k = np.asarray(parameters['neighbour_conductance_W_per_K'], float)
    f = float(parameters['rail_heat_to_cells_fraction'])
    if c.shape != (n,) or g.shape != (n,) or k.shape != (n-1,):
        raise ValueError('Expected n heat capacities, n ambient conductances and n-1 neighbour conductances')
    if not np.isfinite(np.r_[c, g, k, f]).all():
        raise ValueError('Thermal parameters must be finite')
    if np.any(c <= 0) or np.any(g < 0) or np.any(k < 0) or not 0 <= f <= 1:
        raise ValueError('Heat capacity must be positive, conductances nonnegative and the rail fraction in [0, 1]')
    return c, g, k, f


def conductance_matrix(ambient, neighbour):
    """Symmetric network matrix K: ambient on the diagonal plus a Laplacian for passive pairs."""
    m = np.diag(np.asarray(ambient, float))
    for i, gij in enumerate(neighbour):
        m[i, i] += gij; m[i+1, i+1] += gij; m[i, i+1] -= gij; m[i+1, i] -= gij
    return m


def heat_inputs(frame, models, fraction):
    """Average heat [W] over each saved interval [t_j, t_j + step_s_j): into each cell, and rail heat sent straight to ambient."""
    n, h = len(models), frame.step_s.to_numpy(float)
    held = h > 0
    cells, direct = np.zeros((len(frame), n)), np.zeros(len(frame))
    for k, m in enumerate(models, 1):
        r1, tau = m['parameters_ohm'][1], m['tau_s']
        current, vp = frame[f'I{k}_A'].to_numpy(float), frame[f'polarization{k}_V'].to_numpy(float)
        r1_power = vp*vp/r1  # instantaneous value; replaced by the exact interval mean where time advances
        if held.any():
            _, energy, _ = rc_interval(vp[held], current[held], r1, tau, h[held])
            r1_power[held] = energy/h[held]
        cells[:, k-1] = frame[f'R0_loss{k}_W'].to_numpy(float) + r1_power
    for k in range(1, n):
        rail = frame[f'positive_rail{k}_loss_W'].to_numpy(float) + frame[f'negative_rail{k}_loss_W'].to_numpy(float)
        cells[:, k-1] += fraction*rail/2
        cells[:, k] += fraction*rail/2
        direct += (1-fraction)*rail
    return cells, direct


def propagator(rate, h):
    """exp([[A,0,I],[I,0,0],[0,0,0]] h) for state [T, integral T, forcing]; exact for held forcing."""
    n = len(rate)
    m = np.zeros((3*n, 3*n))
    m[:n, :n] = rate; m[:n, 2*n:] = np.eye(n); m[n:2*n, :n] = np.eye(n)
    e = expm(m*h)
    return e[:n, :n], e[:n, 2*n:], e[n:2*n, :n], e[n:2*n, 2*n:]


def rc_propagator(rate, tau, h):
    """Exact propagation of T, integral(T), constant heat and two decaying RC heat modes.

    With held current, vp = b + d*exp(-t/tau). Its resistor heat therefore has
    constant, exp(-t/tau) and exp(-2*t/tau) terms. Averaging those terms before
    cooling conserves total heat but does not give the correct temperature.
    """
    n = len(rate)
    matrix = np.zeros((5*n, 5*n))
    matrix[:n, :n] = rate
    for start in (2*n, 3*n, 4*n):
        matrix[:n, start:start+n] = np.eye(n)
    matrix[n:2*n, :n] = np.eye(n)
    matrix[3*n:4*n, 3*n:4*n] = -np.diag(1/tau)
    matrix[4*n:, 4*n:] = -np.diag(2/tau)
    return expm(matrix*h)[:2*n]


def _check_frame(frame, n):
    required = ['time_s', 'step_s']
    required += [f'{name}{k}_{unit}' for k in range(1, n+1)
                 for name, unit in [('I', 'A'), ('polarization', 'V'), ('R0_loss', 'W')]]
    required += [f'{side}_rail{k}_loss_W' for k in range(1, n)
                 for side in ('positive', 'negative')]
    missing = [name for name in required if name not in frame]
    if missing:
        raise ValueError('Electrical trajectory is missing columns: ' + ', '.join(missing))
    if not np.isfinite(frame[required].to_numpy(dtype=float)).all():
        raise ValueError('Electrical trajectory times, steps, currents, polarization and losses must be finite')
    time, h = frame.time_s.to_numpy(float), frame.step_s.to_numpy(float)
    if np.any(np.diff(time) <= 0) or np.any(h[:-1] <= 0) or h[-1] != 0:
        raise ValueError('Electrical trajectory needs increasing time, positive intervals and a zero terminal step')
    if not np.allclose(time[:-1] + h[:-1], time[1:], rtol=0, atol=1e-9):
        raise ValueError('Electrical trajectory intervals are not contiguous')
    losses = [name for name in required if name.endswith('_loss_W') or name.startswith('R0_loss')]
    if np.any(frame[losses].to_numpy(dtype=float) < 0):
        raise ValueError('Electrical resistor losses must be nonnegative')
    return time, h


def simulate(frame, models, parameters, initial_C, ambient_C):
    n = len(models)
    capacity, ambient, neighbour, fraction = check_parameters(parameters, n)
    t0, tamb = np.asarray(initial_C, float), float(ambient_C)
    if t0.shape != (n,) or not np.isfinite(np.r_[t0, tamb]).all():
        raise ValueError('Finite initial cell temperatures and ambient temperature are required')
    if not len(frame):
        return pd.DataFrame(columns=['time_s', 'step_s'])
    time, h = _check_frame(frame, n)
    r1 = np.asarray([m['parameters_ohm'][1] for m in models], float)
    tau = np.asarray([m['tau_s'] for m in models], float)
    if not np.isfinite(np.r_[r1, tau]).all() or np.any(r1 <= 0) or np.any(tau <= 0):
        raise ValueError('RC resistances and time constants must be finite and positive')
    k = conductance_matrix(ambient, neighbour)
    rate = -k/capacity[:, None]
    heat, direct = heat_inputs(frame, models, fraction)
    constant_heat = frame[[f'R0_loss{i}_W' for i in range(1, n+1)]].to_numpy(float).copy()
    for i in range(1, n):
        rail = (frame[f'positive_rail{i}_loss_W'] + frame[f'negative_rail{i}_loss_W']).to_numpy(float)
        constant_heat[:, i-1] += fraction*rail/2
        constant_heat[:, i] += fraction*rail/2
    current = frame[[f'I{i}_A' for i in range(1, n+1)]].to_numpy(float)
    vp = frame[[f'polarization{i}_V' for i in range(1, n+1)]].to_numpy(float)
    b = current*r1
    d = vp-b
    forcing0 = (constant_heat + b*b/r1 + ambient*tamb)/capacity
    forcing1 = (2*b*d/r1)/capacity
    forcing2 = (d*d/r1)/capacity
    temperature = np.empty((len(frame), n)); temperature[0] = t0
    generated, exchanged, released = np.zeros(len(frame)), np.zeros(len(frame)), np.zeros(len(frame))
    cache = {}
    for j in range(len(frame)-1):
        key = float(h[j])
        if key not in cache:
            cache[key] = rc_propagator(rate, tau, key)
        propagated = cache[key] @ np.r_[temperature[j], np.zeros(n), forcing0[j], forcing1[j], forcing2[j]]
        temperature[j+1], integral = propagated[:n], propagated[n:]
        generated[j+1] = generated[j] + heat[j].sum()*h[j]
        exchanged[j+1] = exchanged[j] + float(ambient@(integral - h[j]*tamb))
        released[j+1] = released[j] + direct[j]*h[j]
    stored = (temperature - t0)@capacity
    out = {'time_s': time, 'step_s': h, 'ambient_C': np.full(len(frame), tamb)}
    for i in range(n):
        out[f'T{i+1}_C'] = temperature[:, i]
        out[f'heat{i+1}_W'] = heat[:, i]
        out[f'to_ambient{i+1}_W'] = ambient[i]*(temperature[:, i] - tamb)
    out.update(heat_to_cells_W=heat.sum(axis=1), rail_heat_to_ambient_W=direct, stored_J=stored,
        generated_in_cells_J=generated, cells_to_ambient_J=exchanged, rail_heat_to_ambient_J=released,
        ledger_residual_J=stored - (generated - exchanged))
    result = pd.DataFrame(out)
    validate_output(result, frame, n)
    return result


def validate_output(thermal, electrical, n=4):
    """Validate the published thermal schema and its exact positional time binding."""
    required = ['time_s', 'step_s', 'ambient_C', 'heat_to_cells_W', 'rail_heat_to_ambient_W',
                'stored_J', 'generated_in_cells_J', 'cells_to_ambient_J',
                'rail_heat_to_ambient_J', 'ledger_residual_J']
    required += [f'{name}{k}_{unit}' for k in range(1, n+1)
                 for name, unit in [('T', 'C'), ('heat', 'W'), ('to_ambient', 'W')]]
    if any(name not in thermal for name in required):
        raise ValueError('Thermal output is missing required temperature, heat or ledger columns')
    if len(thermal) != len(electrical):
        raise ValueError('Thermal output row count differs from the electrical trajectory')
    if not np.isfinite(thermal[required].to_numpy(dtype=float)).all():
        raise ValueError('Thermal output must contain only finite numeric values')
    for key in ['time_s', 'step_s']:
        if not np.allclose(thermal[key].to_numpy(float), electrical[key].to_numpy(float), rtol=0, atol=1e-9):
            raise ValueError('Thermal output timestamps or steps differ from the electrical trajectory')


def summarize(thermal, parameters):
    if not len(thermal):
        return dict(status='unavailable', reason='No electrical samples to heat')
    cells = [c for c in thermal if c.startswith('T') and c.endswith('_C')]
    required = cells + ['time_s', 'generated_in_cells_J', 'stored_J', 'cells_to_ambient_J',
                        'rail_heat_to_ambient_J', 'ledger_residual_J']
    if not cells or any(name not in thermal for name in required):
        raise ValueError('Thermal summary needs cell temperatures and a complete energy ledger')
    if not np.isfinite(thermal[required].to_numpy(dtype=float)).all():
        raise ValueError('Thermal temperatures, time and energy ledger must be finite')
    temps = thermal[cells].to_numpy()
    peak = np.unravel_index(np.argmax(temps), temps.shape)
    spread = temps.max(axis=1) - temps.min(axis=1)
    scale = max(abs(thermal.generated_in_cells_J.iloc[-1]), abs(thermal.stored_J).max(), 1e-12)
    return dict(model=VERSION, classification='simulated; declared thermal parameters; not validated',
        peak_cell_temperature_C=float(temps[peak]), peak_cell=f'cell_{peak[1]+1}', peak_time_s=float(thermal.time_s.iloc[peak[0]]),
        maximum_spread_K=float(spread.max()), maximum_spread_time_s=float(thermal.time_s.iloc[int(np.argmax(spread))]),
        final_cell_temperatures_C=[float(x) for x in temps[-1]], maximum_rise_K=float((temps - temps[0]).max()),
        heat_into_cells_Wh=float(thermal.generated_in_cells_J.iloc[-1]/3600),
        cells_to_ambient_Wh=float(thermal.cells_to_ambient_J.iloc[-1]/3600),
        rail_heat_to_ambient_Wh=float(thermal.rail_heat_to_ambient_J.iloc[-1]/3600),
        maximum_ledger_residual_J=float(abs(thermal.ledger_residual_J).max()),
        relative_ledger_residual=float(abs(thermal.ledger_residual_J).max()/scale),
        limitations=['Surface-equivalent lumped temperature, not core temperature or an internal gradient',
            'No temperature feedback to the frozen electrical parameters', 'Reversible (entropic) heat omitted',
            'Declared parameters: ' + parameters.get('provenance', 'see design thermal block')])
