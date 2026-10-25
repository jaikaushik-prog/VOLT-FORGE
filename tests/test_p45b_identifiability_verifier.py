"""Checks for the independent fit/metric verifier, using synthetic arrays."""
from pathlib import Path
import sys

import numpy as np
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from verify_p45b_identifiability import kkt, independent_metrics


def test_optimality_rejects_nonoptimal_fit_and_wrong_bound_sign():
    a=np.column_stack([np.ones(10),np.zeros(10),np.zeros(10)]); w=np.ones(10)
    assert kkt(a,np.full(10,.1),w,[.1,0,0],[0]) == 0
    for coefficient in [0,.05,.2]:
        with pytest.raises(AssertionError): kkt(a,np.full(10,.1),w,[coefficient,0,0],[0])


def test_correct_active_bounds_are_not_mistaken_for_solver_failure():
    a=np.column_stack([np.ones(10),np.zeros(10),np.zeros(10)]); w=np.ones(10)
    assert kkt(a,np.full(10,-.1),w,[0,0,0],[0]) == pytest.approx(100)
    assert kkt(a,np.full(10,.3),w,[.2,0,0],[0]) == pytest.approx(100)


def test_independent_metrics_preserve_undefined_intervals():
    t=np.array([0,1,2,100,102]); measured=np.zeros(5); prediction=np.array([.1,.1,np.nan,.2,.2])
    result=independent_metrics(t,measured,prediction)
    assert result['samples']==4 and result['covered_duration_s']==3
    assert result['sample_rmse_mV']==pytest.approx(np.sqrt(25000))
    assert result['time_rmse_mV']==pytest.approx(np.sqrt(30000))
