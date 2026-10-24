import numpy as np
import pandas as pd
import pytest
from voltforge.models import reference_investigation as r


def model():
    return {'reference':{'rest':[{'soc':.1,'V':3.1},{'soc':.4,'V':3.6},{'soc':.7,'V':3.85},{'soc':.95,'V':4.2}]}}


def test_reference_coordinate_shift_is_exact_gauge_symmetry():
    z=np.linspace(.1,.95,100);a=r.reference_function(model(),None,'sealed_rest_pchip')
    for shift in [-.02,.02]:
        b=r.reference_function(model(),None,'sealed_rest_pchip',shift)
        np.testing.assert_allclose(a(z),b(z+shift),atol=1e-14)
        assert np.max(abs(a(z[5:-5]+shift)-a(z[5:-5])))>.01


def test_linear_reference_cannot_separate_soc_from_voltage_offset():
    z=np.linspace(.2,.8,101);ref=lambda x:3.3+.8*np.asarray(x)
    grid=np.linspace(-.02,.02,81)
    table,result=r.alignment_profile(z,ref(z)+.004,np.ones(len(z)),ref,grid,.03)
    assert table.mse_joint_V2.max()<1e-28
    assert result['delta_and_offset']['delta_support']==[-.02,.02]
    assert result['sensitivity_column_cosine']==pytest.approx(1)


def test_profile_recovers_known_relative_alignment_with_curved_reference():
    z=np.linspace(.2,.8,301);ref=lambda x:3.1+np.asarray(x)**2
    _,result=r.alignment_profile(z,ref(z+.01)+.003,np.ones(len(z)),ref,np.linspace(-.02,.02,81),.02)
    assert result['delta_and_offset']['delta_soc']==pytest.approx(.01)
    assert result['delta_and_offset']['offset_V']==pytest.approx(.003)


def test_unallocated_cell_rejected_before_any_source_access(monkeypatch):
    monkeypatch.setattr(r.m,'load_cell',lambda *a:pytest.fail('Unexpected data access'))
    plan={'cells':['P7'],'reserved_unused_cells':['P3'],'calibration_cycles':[1,3],'development_cycles':[2,4]}
    with pytest.raises(ValueError):r.load_used('P3',[1,3],plan)
    with pytest.raises(ValueError):r.load_used('P7',[1,2,3,4],plan)


def test_diagnostic_prediction_does_not_reinitialize_from_voltage():
    f=pd.DataFrame(dict(reference_V=[3.7,3.6],predicted_V=[3.6,3.5],soc=[.7,.6],V_V=[3.61,3.51]))
    ref=lambda z:3.+np.asarray(z)
    a=r.diagnostic_prediction(f,ref,.01,.002)
    f.V_V=999.;b=r.diagnostic_prediction(f,ref,.01,.002)
    np.testing.assert_allclose(a.predicted_V,b.predicted_V)
    np.testing.assert_allclose(a.predicted_V,[3.612,3.512])


def test_offset_bound_and_common_support_are_enforced():
    z=np.array([.3,.4]);ref=lambda x:np.asarray(x)
    _,res=r.alignment_profile(z,z+.1,np.ones(2),ref,[-.02,0,.02],.01)
    assert res['delta_and_offset']['offset_on_boundary']
    with pytest.raises(ValueError):r.alignment_profile(z,z,np.ones(2),lambda x:np.full_like(x,np.nan),[0],.01)
