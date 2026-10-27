"""Cycle balance uses only in-repository reconciliation CSVs; no archive access."""
import importlib.util
from pathlib import Path

import pytest
import numpy as np

spec = importlib.util.spec_from_file_location('cycle_balance', Path(__file__).parents[1] / 'scripts/cycle_balance.py')
cb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cb)


@pytest.mark.parametrize('run,cycler,hall', [('M1_NMC_Unaged_R0_T25', 1.1445, .9983), ('M1_NMC_Unaged_R3_T25', .9195, 1.0042)])
def test_pinned_observed_ratios_do_not_establish_absolute_channel_calibration(run, cycler, hall):
    r = cb.balance(cb.ROOT / 'reports/reconciliation' / f'{run}_residual.csv')
    c = r['channels']
    assert c['cycler_module_current']['discharged_over_recharged'] == pytest.approx(cycler, abs=5e-4)
    assert c['hall_branch_sum']['discharged_over_recharged'] == pytest.approx(hall, abs=5e-4)
    assert c['cycler_module_current']['mean_discharge_current_A'] == pytest.approx(14.55, abs=.02)
    assert abs(c['hall_branch_sum']['discharged_over_recharged'] - 1) < .005  # observed proximity, not a calibration tolerance
    assert r['recharge']['first_row'] > r['discharge']['last_row']


def test_recharge_integration_does_not_bridge_excluded_rows():
    current = np.array([2, 2, 2, 0, -1, -1, 0, 2, 2, -1, -1], dtype=float)
    time = np.arange(len(current))*3600.0
    recharge = np.flatnonzero(current < -0.05)
    assert -cb.integral_Ah(time, current, recharge) == pytest.approx(2.0)
    # Two isolated selected observations supply no observed interval to integrate.
    assert cb.integral_Ah(np.array([0., 1., 2.])*3600, np.array([-1., 100., -1.]), np.array([0, 2])) == 0.0
    assert cb.integral_Ah(time, current, np.array([], dtype=int)) == 0.0
