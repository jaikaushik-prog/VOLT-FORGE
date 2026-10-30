"""First-law checks that can fail, and limit-enforcing references for the deployed cells.

The oracle shares no lookup, RC or circuit code with the product. Its heat comes from
the energy identity (open-circuit power minus terminal power), not a branch formula.
"""
import json
from pathlib import Path

import numpy as np
import pytest
from scipy.integrate import solve_ivp
from scipy.interpolate import RegularGridInterpolator

from voltforge.models.cell_catalogue import CellModel, lint_tables, load_additional
from voltforge.models.coupling_v2 import rc_interval
from voltforge.studio import temperature_engine
from voltforge.studio.network import settings_default, simulate, template

ROOT = Path(__file__).resolve().parents[1]
BANK = load_additional(ROOT)
TOLERANCE = 1e-3  # Largest accepted first-law residual, as a share of the electrical loss.


def record(key='falling', capacity=2.):
    """Branch resistance falls tenfold with charge while tau stays fixed."""
    zs = [.1, .4, .7, 1.]; ts = [15., 35., 55.]
    r = [.04, .02, .008, .004]
    grid = lambda f: [[f(i) for i in range(4)] for _ in ts]
    return dict(kind='temperature_dependent_ecm/1', key=key, name=key, family='Synthetic verification fixture', origin='user',
                capacity_Ah=capacity, nrc=1, soc=zs, temperature_C=ts, ocv_V=grid(lambda i: 3.4+.7*zs[i]), r0_ohm=grid(lambda i: .02),
                r_ohm=grid(lambda i: [r[i]]), tau_s=grid(lambda i: [40.]),
                operating_limits={'voltage_V': [2.5, 4.3], 'max_charge_A': 10., 'max_discharge_A': 10.},
                thermal_defaults={'heat_capacity_J_K': 50., 'ambient_conductance_W_K': .2})


def build(key, count, current, seconds, charge=70., dt=.5):
    g = template('parallel', count)
    for c in g['cells']: c.update(model=key, charge_pct=charge)
    s = settings_default(); s['profile'] = [dict(start_s=0., end_s=float(seconds), current_A=float(current))]; s['dt_s'] = dt
    return g, s


def assert_closed(result):
    v = result.summary['verification']
    assert v['first_law_closed'] and abs(v['first_law_residual_J']) <= TOLERANCE*max(1., abs(v['electrical_dissipation_J']))
    assert abs(v['final_energy_residual_Wh'])*3600 <= TOLERANCE*max(1., abs(v['electrical_dissipation_J']))
    assert v['max_thermal_residual_J'] < 1e-8


@pytest.mark.parametrize('count,current,charge', [(1, 3., 90.), (2, 5., 90.), (2, -3., 40.)])
def test_budgets_close_when_branch_resistance_falls_with_charge(count, current, charge):
    g, s = build('falling', count, current, 400, charge)
    result = simulate(g, s, {'falling': record()})
    assert result.status == 'completed'
    assert_closed(result)


def test_budgets_close_through_charge_reversal_and_a_non_rested_start():
    g, s = build('falling', 2, 3., 300)
    g['cells'][0]['polarization_V'] = -.02; g['cells'][1]['polarization_V'] = .01
    s['profile'] = [dict(start_s=0., end_s=100., current_A=4.), dict(start_s=100., end_s=200., current_A=-3.), dict(start_s=200., end_s=300., current_A=0.)]
    result = simulate(g, s, {'falling': record()})
    assert result.status == 'completed'
    assert_closed(result)


def test_budget_keeps_reversible_heat_and_conductor_heat_on_their_own_terms():
    g, s = build('LG_M50T_ECN', 2, 6., 300)
    g['thermal']['wire_heat_fraction'] = .25
    for c in g['connections']: c['resistance_mohm'] = 5.
    result = simulate(g, s, BANK)
    assert_closed(result)
    end = result.rows[-1]
    # Cell heating alone does not equal the electrical loss here: a share leaves through the links.
    stored = sum((T-23)*58.5 for T in end['temperature_C'])
    assert stored < end['electrical_dissipation_J']


def resistor_heat_forcing(current, b, d, active, tau):
    resistance = b/np.where(current[:, None] == 0, 1, current[:, None])
    n, nrc = b.shape
    coefficients = np.zeros((n, 2*n*nrc)); decay = np.empty(2*n*nrc)
    for i in range(n):
        for k in range(nrc):
            coefficients[i, 2*(i*nrc+k)] = active[i, k]*2*b[i, k]*d[i, k]/resistance[i, k]
            coefficients[i, 2*(i*nrc+k)+1] = active[i, k]*d[i, k]**2/resistance[i, k]
            decay[2*(i*nrc+k):2*(i*nrc+k)+2] = [-1/tau[i, k], -2/tau[i, k]]
    return np.sum(active*b*b/resistance, axis=1), coefficients, decay


def test_first_law_check_fails_on_the_v3_resistor_heat_form(monkeypatch):
    def v3_interval(vp, current, r1, tau, h):
        end, loss, _ = rc_interval(vp, current, r1, tau, h)
        return end, loss, loss
    monkeypatch.setattr(temperature_engine, 'branch_forcing', resistor_heat_forcing)
    monkeypatch.setattr(temperature_engine, 'rc_interval', v3_interval)
    g, s = build('SAMSUNG_30T', 1, 6., 540)
    result = simulate(g, s, BANK)
    v = result.summary['verification']
    # The old form reproduces its unsourced heat, and this check now shows it.
    assert not v['first_law_closed'] and abs(v['first_law_residual_J']) > .25*v['electrical_dissipation_J']
    assert 'disagree' in result.summary['insights'][0]
    assert abs(v['final_energy_residual_Wh'])*3600 > .25*v['electrical_dissipation_J']
    assert result.rows[-1]['temperature_C'][0] > 35


class Oracle:
    """Single cell at constant current, with its own bilinear table lookup."""

    def __init__(self, key, current, ambient=23.):
        self.m = BANK[key]; self.i = current; self.ambient = ambient
        self.q = self.m['capacity_Ah']*3600; self.nrc = self.m['nrc']
        axes = (np.array(self.m['temperature_C']), np.array(self.m['soc']))
        # Trial stages may step just past the limit before the terminal event trims them.
        self.look = {k: RegularGridInterpolator(axes, np.array(self.m[k]), bounds_error=False, fill_value=None) for k in ('ocv_V', 'r0_ohm', 'r_ohm', 'tau_s')}
        self.heat = self.m['thermal_defaults']['heat_capacity_J_K']; self.g = self.m['thermal_defaults']['ambient_conductance_W_K']

    def rhs(self, _, y):
        z, T, v = y[0], y[1], y[2:]
        point = np.array([T, z])
        u, r0 = float(self.look['ocv_V'](point)), float(self.look['r0_ohm'](point))
        r, tau = np.ravel(self.look['r_ohm'](point)), np.ravel(self.look['tau_s'](point))
        terminal = u-v.sum()-r0*self.i
        heat = (u-terminal)*self.i
        return np.r_[-self.i/self.q, (heat+self.g*(self.ambient-T))/self.heat, (self.i*r-v)/tau]

    def run(self, seconds, stop_soc):
        event = lambda _, y: y[0]-stop_soc
        event.terminal = True
        return solve_ivp(self.rhs, (0, seconds), np.r_[.7, self.ambient, np.zeros(self.nrc)], method='RK45', rtol=1e-7, atol=1e-8,
                         max_step=2., events=event)


@pytest.mark.parametrize('current,seconds', [(6., 1560.), (4., 2300.)])
def test_samsung_runs_to_its_charge_limit_and_matches_a_limit_enforcing_oracle(current, seconds):
    g, s = build('SAMSUNG_30T', 1, current, seconds)
    result = simulate(g, s, BANK)
    oracle = Oracle('SAMSUNG_30T', current).run(seconds, .15)
    assert result.status == 'stopped' and result.stop['reason'] == 'charge_domain'
    assert result.stop['time_s'] > 544
    assert result.stop['time_s'] == pytest.approx(oracle.t[-1], abs=.5)
    assert result.summary['metrics']['peak_temperature_C'] == pytest.approx(oracle.y[1].max(), abs=.1)
    assert_closed(result)


def test_lg_has_no_voltage_step_at_fixed_current_and_temperature():
    # A very large heat capacity holds temperature, so only the table can move voltage.
    g, s = build('LG_M50T_ECN', 1, 3., 2520, charge=30.)
    g['thermal']['cell_parameters'] = {'cell1': {'heat_capacity_J_K': 10000.}}
    result = simulate(g, s, BANK)
    rows = [r for r in result.rows if 15 <= r['charge_pct'][0] <= 25]
    assert max(r['temperature_C'][0] for r in rows)-min(r['temperature_C'][0] for r in rows) < .05
    steps = np.diff([r['voltage_V'] for r in rows])
    assert steps.max() < 1e-4


def test_v1_table_keeps_its_step_and_the_lint_finds_it():
    v1 = json.loads((ROOT/'configs/cell_catalogue_v1.json').read_text())['models']['LG_M50T_ECN']
    found = lint_tables(v1)
    assert len(found) == 5 and {f['table'] for f in found} == {'tau_s'}
    assert all(f['soc'] == [.18, .2] and f['branch'] == 2 for f in found)


def test_v2_revision_changes_only_the_recorded_lg_entries():
    v1 = json.loads((ROOT/'configs/cell_catalogue_v1.json').read_text())
    v2 = json.loads((ROOT/'configs/cell_catalogue_v2.json').read_text())
    assert all(not lint_tables(m) for m in v2['models'].values())
    assert v2['models']['SAMSUNG_30T'] == v1['models']['SAMSUNG_30T']
    old, new = v1['models']['LG_M50T_ECN'], v2['models']['LG_M50T_ECN']
    assert v2['revision']['entries_changed'] == 45 and 'Unvalidated' in v2['revision']['status']
    assert {k for k in old if old[k] != new[k]} == {'tau_s', 'limitations'}
    moved = np.array(old['tau_s']) != np.array(new['tau_s'])
    assert moved.sum() == 45 and moved[..., :2].sum() == 0
    assert np.all(np.array(new['tau_s'])[moved] == 350.1424873)
    CellModel(new)


def test_lg_voltage_step_check_fails_on_the_v1_table():
    v1 = json.loads((ROOT/'configs/cell_catalogue_v1.json').read_text())['models']
    g, s = build('LG_M50T_ECN', 1, 3., 2520, charge=30.)
    g['thermal']['cell_parameters'] = {'cell1': {'heat_capacity_J_K': 10000.}}
    rows = [r for r in simulate(g, s, v1).rows if 15 <= r['charge_pct'][0] <= 25]
    assert np.diff([r['voltage_V'] for r in rows]).max() > 1e-3
