import numpy as np
import pytest
from voltforge.models.ladder import solve_ladder


def test_symmetric_ideal_parallel_analytic():
    s = solve_ladder([3.7]*4,[.02]*4,[0]*3,[0]*3,12.)
    np.testing.assert_allclose(s.branch_A,[3.]*4,atol=1e-12)
    assert s.terminal_V == pytest.approx(3.64)


def test_two_cell_shared_rail_analytic():
    # r_cell=.1, total rail=.2: I1=3*I2 and I1+I2=10.
    s = solve_ladder([3.7,3.7],[.1,.1],[.12],[.08],10.)
    np.testing.assert_allclose(s.branch_A,[7.5,2.5],atol=1e-12)
    assert s.terminal_V == pytest.approx(2.95)
    np.testing.assert_allclose(s.positive_nodes_V,[2.95,3.25])
    np.testing.assert_allclose(s.negative_nodes_V,[0,-.2])
    assert s.rail_loss_W == pytest.approx(1.25)
    assert s.ohmic_cell_loss_W == pytest.approx(6.25)


def test_unequal_sources_allow_circulating_currents():
    s = solve_ladder([4.,3.8],[.1,.2],[0.],[0.],0.)
    np.testing.assert_allclose(s.branch_A,[2/3,-2/3],atol=1e-12)
    assert s.terminal_V == pytest.approx(59/15)


def test_single_cell_and_charge_sign():
    s = solve_ladder([3.7],[.02],[],[],-2.)
    assert s.branch_A[0] == -2
    assert s.terminal_V == pytest.approx(3.74)
    assert abs(s.energy_residual_W) < 1e-12


def test_kirchhoff_and_power_identity_for_asymmetric_case():
    s = solve_ladder([3.8,3.72,3.74,3.77],[.021,.025,.023,.03],
                     [.001,.003,.002],[.003,.001,.004],14.)
    assert abs(s.kcl_residual_A) < 1e-12
    assert abs(s.energy_residual_W) < 1e-12
    np.testing.assert_allclose(s.cell_terminal_V,s.positive_nodes_V-s.negative_nodes_V,atol=1e-12)
    # Direct adjacent voltage-drop relation, independent of the impedance assembly.
    for k,rail in enumerate([.004,.004,.006]):
        assert s.cell_terminal_V[k+1]-s.cell_terminal_V[k] == pytest.approx(rail*s.branch_A[k+1:].sum())


@pytest.mark.parametrize('resistance', [[0,.1],[-.1,.1],[float('nan'),.1]])
def test_invalid_cell_resistance_rejected(resistance):
    with pytest.raises(ValueError):
        solve_ladder([3.7,3.7],resistance,[.001],[.001],1)


def test_invalid_shape_and_negative_rail_rejected():
    with pytest.raises(ValueError):
        solve_ladder([3.7,3.7],[.1,.1],[],[],1)
    with pytest.raises(ValueError):
        solve_ladder([3.7,3.7],[.1,.1],[-.001],[.001],1)
