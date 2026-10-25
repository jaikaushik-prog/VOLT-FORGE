"""Analytical checks of the paper equations; no real dataset access."""
from dataclasses import replace
import math
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
from ae_p45b_equations import Parameters, State, advance, reference_query, synthetic_demo, terminal_voltage


P = Parameters(3.8, 3.7, 0.01, 0.005, 2000.0, 0.01, 10000.0, 50.0)


def test_one_hour_one_c_and_polarity():
    for current, expected in [(-4.5, -0.1), (4.5, 1.9), (0, 0.9)]:
        result = advance(State(0.9, 0), P, current, 3600, 4.5)
        assert result.soc == pytest.approx(expected)
    # Nominal-capacity SOC may pass zero; reference support is a separate check.


@pytest.mark.parametrize('h,voltage', [(-1, 3.7), (0, 3.75), (1, 3.8)])
def test_reference_branch_mixture(h, voltage):
    assert terminal_voltage(State(0.5, h), P, 0) == pytest.approx(voltage)


def test_instantaneous_voltage_jump_without_state_change():
    state = State(0.5, -1, -0.01, -0.02)
    before = terminal_voltage(state, P, -4.5)
    after = terminal_voltage(state, P, 2.25)
    assert after-before == pytest.approx(6.75*P.r0_Ohm)
    assert terminal_voltage(State(0.5, -1), P, -4.5) == pytest.approx(3.655)


@pytest.mark.parametrize('current', [-4.5, 4.5])
def test_pulse_matches_analytical_step_response(current):
    dt = 23.0
    state = State(0.5, 0.25, 0.03, -0.02)
    result = advance(state, P, current, dt, 4.5)
    target_h = math.copysign(1, current)
    h = target_h + (state.hysteresis-target_h)*math.exp(-50*abs(current)*dt/16200)
    v1 = current*0.005 + (0.03-current*0.005)*math.exp(-dt/10)
    v2 = current*0.01 + (-0.02-current*0.01)*math.exp(-dt/100)
    voltage = (1+h)/2*3.8 + (1-h)/2*3.7 + current*0.01 + v1 + v2
    assert result.hysteresis == pytest.approx(h)
    assert result.v1_V == pytest.approx(v1)
    assert result.v2_V == pytest.approx(v2)
    assert terminal_voltage(result, P, current) == pytest.approx(voltage)


def test_rest_relaxes_rc_but_not_hysteresis_or_soc():
    state = State(0.4, -0.6, -0.03, -0.04)
    result = advance(state, P, 0, 100, 4.5)
    assert result.soc == state.soc and result.hysteresis == state.hysteresis
    assert result.v1_V == pytest.approx(-0.03*math.exp(-10))
    assert result.v2_V == pytest.approx(-0.04/math.e)
    assert terminal_voltage(result, P, 0) > terminal_voltage(state, P, 0)


def test_constant_input_semigroup_and_charge_accounting():
    start = State(0.6, -1)
    coarse = advance(start, P, -4.5, 60, 4.5)
    fine = start
    for _ in range(240):
        fine = advance(fine, P, -4.5, 0.25, 4.5)
    assert fine.soc == pytest.approx(coarse.soc, abs=1e-13)
    assert fine.hysteresis == coarse.hysteresis
    assert fine.v1_V == pytest.approx(coarse.v1_V, abs=1e-13)
    assert fine.v2_V == pytest.approx(coarse.v2_V, abs=1e-13)
    assert (start.soc-fine.soc)*4.5 == pytest.approx(4.5*60/3600)


def test_current_reversal_hysteresis_remains_bounded():
    state = State(0.5, -1)
    state = advance(state, P, 4.5, 30, 4.5)
    assert -1 < state.hysteresis < 1
    reversal = advance(state, P, -4.5, 30, 4.5)
    assert -1 < reversal.hysteresis < state.hysteresis


def test_zero_gamma_freezes_hysteresis():
    state = advance(State(0.5, 0.2), replace(P, gamma=0), 4.5, 60, 4.5)
    assert state.hysteresis == 0.2


def test_degenerate_rc_is_algebraic_zero_not_division_by_zero():
    p = replace(P, r2_Ohm=0, c2_F=0)
    state = State(0.5, -1, 0, 0.99)
    assert terminal_voltage(state, p, 0) == 3.7
    result = advance(state, p, -4.5, 10, 4.5)
    assert result.v2_V == 0


def test_unsupported_reference_stops_or_is_explicitly_flagged():
    with pytest.raises(ValueError, match='outside reference'):
        reference_query(-0.02, 0, 1)
    query, flags = reference_query(-0.02, 0, 1, outside='nearest')
    assert query == 0 and 'UNSUPPORTED_REFERENCE_EXTENSION' in flags[0]
    assert reference_query(-0.02, -0.1, 1) == (-0.02, [])
    assert reference_query(1, 0, 1) == (1, [])
    assert reference_query(1.1, 0, 1, outside='nearest')[0] == 1


@pytest.mark.parametrize('change', [dict(r0_Ohm=-1), dict(gamma=-1),
    dict(c1_F=0), dict(c2_F=float('nan')), dict(ocv_charge_V=0)])
def test_invalid_parameters_rejected(change):
    with pytest.raises(ValueError):
        replace(P, **change)


@pytest.mark.parametrize('dt,capacity,current', [(0, 4.5, 1), (-1, 4.5, 1),
    (1, 0, 1), (1, 4.5, float('inf'))])
def test_invalid_update_rejected(dt, capacity, current):
    with pytest.raises(ValueError):
        advance(State(0.5, 0), P, current, dt, capacity)


def test_demo_complete_sequence_step_invariance_and_labels():
    coarse, fine = synthetic_demo(1), synthetic_demo(0.25)
    assert coarse['evidence'].startswith('SYNTHETIC SOFTWARE CHECK ONLY')
    assert coarse['experimental_validation'] == 'not performed'
    assert not coarse['thermal_model']
    for key in ('soc', 'hysteresis', 'v1_V', 'v2_V', 'voltage_V'):
        assert coarse['samples'][-1][key] == pytest.approx(fine['samples'][-1][key], abs=1e-12)
    assert coarse['samples'][-1]['soc'] == pytest.approx(0.6+(-4.5*60+2.25*60)/16200)
    assert len(coarse['samples']) == 241
    assert coarse['samples'][60]['current_charge_positive_A'] == 0
    assert coarse['samples'][180]['current_charge_positive_A'] == 2.25
