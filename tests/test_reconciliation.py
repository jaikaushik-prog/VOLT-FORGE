"""Tests of the second MAT decoder against separately constructed values."""
import importlib.util
from io import BytesIO
from pathlib import Path

import numpy as np
import pytest
from scipy.io import savemat

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('independent_reconciliation',ROOT/'scripts/reconcile_independent.py')
ind=importlib.util.module_from_spec(spec);spec.loader.exec_module(ind)


@pytest.mark.parametrize('compressed',[False,True])
def test_mat_numeric_order_float_precision_and_small_tags(compressed):
    b=BytesIO()
    savemat(b,{'x':np.array([[1.,-2.],[3.125,1e-9]]),'short':'A'},do_compression=compressed)
    arrays=list(ind.top_arrays(b.getvalue()[128:]))
    np.testing.assert_array_equal(arrays[0],[1.,3.125,-2.,1e-9])
    assert arrays[1]=='A'


def test_independent_decoder_rejects_corrupt_payload():
    b=BytesIO();savemat(b,{'x':np.array([1.,2.])})
    with pytest.raises(ValueError,match='outside file'):
        list(ind.top_arrays(b.getvalue()[128:-5]))


def test_real_second_decoder_source_polarity_and_channels():
    from zipfile import ZipFile
    archives=list(ROOT.glob('Full factorial*.zip'))
    if not archives: pytest.skip('Requires official archive')
    with ZipFile(archives[0]) as z:
        name=next(n for n in z.namelist() if n.endswith('/M1_NMC_Unaged_R0_T25.mat'))
        table=ind.independent_table(z.read(name))
    # Independently inspected worksheet values and fixed reported population.
    assert len(table['Test_Times'])==33079
    assert table['Test_Times'][0]==pytest.approx(1.0001)
    assert table['VoltageV'][0]==pytest.approx(3.469592332839966,abs=1e-12)
    mask=table['Step_Index']==5
    residual=table['CurrentA'][mask].copy()
    for k in range(1,5): residual-=table[f'CurrentA_Cell_{k}'][mask]
    assert residual.mean()==pytest.approx(-1.6832915320630526,abs=1e-12)
    assert np.sqrt(np.mean(residual**2))==pytest.approx(1.6858798703845315,abs=1e-12)
