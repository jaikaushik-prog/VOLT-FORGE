"""Isolated, synthetic-tested electrical kernel for SSRN 6861858, pp. 7-9.

Positive current charges. Parameters are held constant during each step. This
module does not load published parameter tables or measurements, fit parameters,
predict temperature, or replace the frozen LG model. Its CLI uses invented values.
"""
import argparse
from dataclasses import asdict, dataclass
import json
import math
from pathlib import Path


def finite(*values):
    if not all(math.isfinite(v) for v in values):
        raise ValueError('All electrical inputs must be finite')


@dataclass(frozen=True)
class Parameters:
    ocv_charge_V: float
    ocv_discharge_V: float
    r0_Ohm: float
    r1_Ohm: float
    c1_F: float
    r2_Ohm: float
    c2_F: float
    gamma: float

    def __post_init__(self):
        finite(*asdict(self).values())
        if self.ocv_charge_V <= 0 or self.ocv_discharge_V <= 0:
            raise ValueError('Voltage references must be positive')
        if min(self.r0_Ohm, self.r1_Ohm, self.r2_Ohm, self.c1_F,
               self.c2_F, self.gamma) < 0:
            raise ValueError('Resistances, capacitances and gamma cannot be negative')
        for r, c in [(self.r1_Ohm, self.c1_F), (self.r2_Ohm, self.c2_F)]:
            if r > 0 and c <= 0:
                raise ValueError('An active RC pair needs positive capacitance')
            if not math.isfinite(r*c) or (r > 0 and r*c == 0):
                raise ValueError('RC time constant overflow or underflow')


@dataclass(frozen=True)
class State:
    soc: float
    hysteresis: float
    v1_V: float = 0.0
    v2_V: float = 0.0

    def __post_init__(self):
        finite(*asdict(self).values())
        if not -1 <= self.hysteresis <= 1:
            raise ValueError('Hysteresis must lie in [-1, 1]')
        # No universal [0, 1] SOC clipping: the paper uses a nominal-capacity origin.


def terminal_voltage(state, parameters, current_charge_positive_A):
    """Equations 1, 4 and 5; R0 acts immediately, including at the first sample."""
    finite(current_charge_positive_A)
    h = state.hysteresis
    reference = ((1+h)*parameters.ocv_charge_V +
                 (1-h)*parameters.ocv_discharge_V)/2
    # A zero-R pair has tau=0 and algebraic voltage zero, not a stored voltage.
    v1 = state.v1_V if parameters.r1_Ohm else 0.0
    v2 = state.v2_V if parameters.r2_Ohm else 0.0
    result = reference + current_charge_positive_A*parameters.r0_Ohm + v1 + v2
    finite(result)
    return result


def advance(state, parameters, current_charge_positive_A, dt_s, capacity_Ah):
    """Exact constant-input, constant-parameter update of Eqs. 2, 5, 6.

    This is not an exact variable-parameter integrator. A future table wrapper
    must control substeps and check reference support at both endpoints. Capacity
    is explicit: published reproduction uses 4.5 Ah, not a fitted usable capacity.
    """
    finite(current_charge_positive_A, dt_s, capacity_Ah)
    if dt_s <= 0 or capacity_Ah <= 0:
        raise ValueError('Time step and nominal capacity must be positive')
    current = current_charge_positive_A
    q_C = 3600.0*capacity_Ah
    finite(q_C)
    soc = state.soc + current*dt_s/q_C
    # expm1 preserves small increments and convexity without silent clipping.
    target_h = 1.0 if current > 0 else (-1.0 if current < 0 else state.hysteresis)
    factor = -math.expm1(-parameters.gamma*abs(current)/q_C*dt_s)
    h = state.hysteresis + (target_h-state.hysteresis)*factor

    def rc(previous, r, c):
        if r == 0:
            return 0.0
        return previous + (current*r-previous)*(-math.expm1(-dt_s/(r*c)))

    return State(soc, h, rc(state.v1_V, parameters.r1_Ohm, parameters.c1_F),
                 rc(state.v2_V, parameters.r2_Ohm, parameters.c2_F))


def reference_query(soc, lower_soc, upper_soc, *, outside='stop'):
    """Explicit support policy for a future lookup layer; never clip the state.

    The paper recommends nearest-boundary parameter extension. Our default stops.
    The opt-in policy returns the boundary query and a prominent flag while the
    caller retains the actual integrated SOC. This is not a table interpolator.
    """
    finite(soc, lower_soc, upper_soc)
    if lower_soc >= upper_soc:
        raise ValueError('Reference interval must have positive width')
    if outside not in ('stop', 'nearest'):
        raise ValueError('Unknown reference-support policy')
    if lower_soc <= soc <= upper_soc:
        return soc, []
    if outside == 'stop':
        raise ValueError(f'SOC {soc:g} outside reference [{lower_soc:g}, {upper_soc:g}]')
    return (lower_soc if soc < lower_soc else upper_soc), [
        'UNSUPPORTED_REFERENCE_EXTENSION: nearest-boundary parameters; SOC is unchanged']


def synthetic_demo(dt_s=1.0):
    """Invented discharge/rest/charge pulse sequence, not P45B predictions."""
    finite(dt_s)
    if dt_s < 0.01 or dt_s > 60:
        raise ValueError('Synthetic demo step must be in [0.01, 60] seconds')
    p = Parameters(3.8, 3.7, 0.01, 0.005, 2000.0, 0.01, 10000.0, 50.0)
    state = State(0.6, -1.0)
    samples = []
    elapsed = 0.0
    for duration, current in [(60.0, -4.5), (120.0, 0.0), (60.0, 2.25)]:
        end = elapsed + duration
        while elapsed < end:
            samples.append(dict(time_s=elapsed, current_charge_positive_A=current,
                voltage_V=terminal_voltage(state, p, current), **asdict(state)))
            step = min(dt_s, end-elapsed)
            state = advance(state, p, current, step, 4.5)
            elapsed = min(end, elapsed+step)
    samples.append(dict(time_s=elapsed, current_charge_positive_A=2.25,
        voltage_V=terminal_voltage(state, p, 2.25), **asdict(state)))
    return dict(schema_version='voltforge.ae_p45b_equation_demo/1',
        evidence='SYNTHETIC SOFTWARE CHECK ONLY; invented parameters and inputs',
        parameters=asdict(p), nominal_capacity_Ah=4.5, dt_s=dt_s,
        current_convention='positive charge, negative discharge',
        thermal_model=False, experimental_validation='not performed',
        samples=samples)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--dt-s', type=float, default=1.0)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    dest = args.out.resolve()
    if not any(dest.is_relative_to(root/name) for name in ('tmp', 'reports', 'workspace')):
        raise SystemExit('Write generated outputs under tmp/, reports/ or workspace/.')
    result = synthetic_demo(args.dt_s)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(json.dumps(result, indent=2, allow_nan=False)+'\n')
    print('Synthetic equation demonstration written. No measured or fitted P45B values used.')


if __name__ == '__main__':
    main()
