"""Synthetic checks; no real unused measurement outcomes are accessed."""
import csv
import io
import json
import math
from pathlib import Path
import sys

import numpy as np
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import ae_p45b_identifiability as study
from ae_p45b_intake import PARAMETERS
from ae_p45b_reproduction import Table25, simulate
from ae_p45b_low_soc import annotate, segments
from ae_p45b_equations import Parameters


def synthetic():
    stream = io.StringIO(); writer = csv.writer(stream); writer.writerow(PARAMETERS)
    for z in [-.1,0.,.2,1.]:
        writer.writerow([z,4.5*(z-1),25,3.7+z*.1,3.6+z*.1,.01,.005,400,.01,2000,20,0])
    table = Table25(stream.getvalue().encode())
    currents = [0.]*2+[-135.]*100+[0.]*60
    for _ in range(4): currents += [-4.5]*6+[0.]*80
    rows = [dict(source_line=i+2,time_s=float(i),source_current_A=c,voltage_V=3.5,
        controlled_temperature_degC=25.) for i,c in enumerate(currents)]
    marked,_ = annotate(table,rows); seg,pairs = segments(table,marked)
    for r,m in zip(rows,marked): r['segment_id'] = m['segment_id']
    return table,rows,seg,pairs


@pytest.fixture(scope='module')
def prepared():
    table,rows,seg,pairs = synthetic()
    base,matrix = study.make_basis(table,rows,seg,'primary')
    groups,weights = study.allocation(base,seg,pairs)
    return table,rows,seg,pairs,base,matrix,groups,weights


def test_adapter_preserves_reference_tau_and_high_soc():
    table,*_ = synthetic(); adapted = study.ResistanceTable(table,[.02,.03,.04])
    for z in [-.05,.05,.199,.2,.6,1.]:
        old,_ = table.query(z); new,_ = adapted.query(z)
        assert new.ocv_charge_V == old.ocv_charge_V
        assert new.ocv_discharge_V == old.ocv_discharge_V and new.gamma == old.gamma
        assert new.r1_Ohm*new.c1_F == pytest.approx(old.r1_Ohm*old.c1_F)
        assert new.r2_Ohm*new.c2_F == pytest.approx(old.r2_Ohm*old.c2_F)
        assert new.r0_Ohm-old.r0_Ohm == pytest.approx(.02*max(0,(.2-z)/.2))
        if z >= .2: assert new == old


@pytest.mark.parametrize('increments', [[-.001,0,0],[0,.201,0],[0,float('nan'),0],[0,0]])
def test_invalid_candidate_rejected(increments):
    table,*_ = synthetic()
    with pytest.raises(ValueError): study.ResistanceTable(table,increments)


def test_domain_policy_and_inactive_rc_are_not_silently_repaired():
    table,*_ = synthetic(); adapted = study.ResistanceTable(table,[.01,0,0])
    with pytest.raises(ValueError,match='outside'): adapted.query(1.1)
    with pytest.raises(ValueError,match='extension'): adapted.query(1.1,'nearest')
    class Inactive:
        values = table.values
        def query(self,z,outside): return Parameters(3.7,3.6,.01,0,0,.01,2000,20),[]
    with pytest.raises(ValueError,match='activate'):
        study.ResistanceTable(Inactive(),[0,.01,0]).query(.1)


def test_superposition_matches_direct_continuous_solver_and_sign(prepared):
    table,rows,seg,_,base,matrix,_,_ = prepared; coef = np.array([.004,.008,.012])
    direct = study.replay(study.ResistanceTable(table,coef),rows,seg,'primary')
    assert study.values(direct) == pytest.approx(study.values(base)+matrix@coef,abs=1e-12)
    assert np.all(matrix[:,0] <= 0)  # Discharge lowers voltage.
    for a,b in zip(base['rows'],direct['rows']):
        assert a['soc'] == b['soc'] and a['hysteresis'] == b['hysteresis']
    assert any(r['direction']=='rest' and r['v2_V'] < -.001 for r in direct['rows'])


def test_analytic_rest_relaxes_with_unchanged_tau(prepared):
    table,rows,seg,_,_,_,_,_ = prepared
    run = study.replay(study.ResistanceTable(table,[.004,.008,.012]),rows,seg,'primary')
    rest = seg[-1]; a = int(rest['start_index']); b = a+10
    elapsed = run['rows'][b]['time_s']-run['rows'][a]['time_s']
    assert run['rows'][b]['v1_V'] == pytest.approx(run['rows'][a]['v1_V']*math.exp(-elapsed/2),abs=1e-12)
    assert run['rows'][b]['v2_V'] == pytest.approx(run['rows'][a]['v2_V']*math.exp(-elapsed/20),abs=1e-12)


def test_complete_pair_weights_balance_phases_without_bridging(prepared):
    _,_,seg,_,base,_,groups,w = prepared
    assert w.sum() == pytest.approx(1)
    for g in groups:
        assert w[g['indices']].sum() == pytest.approx(1/len(groups))
        for key in ['pulse_segment_id','rest_segment_id']:
            phase = seg[g[key]]; a,b = int(phase['start_index']),int(phase['end_index'])
            assert w[a:b+1].sum() == pytest.approx(.5/len(groups))
        assert g['indices'] == list(range(g['indices'][0],g['indices'][-1]+1))
    assert study.phase_weights([0,1,10]) == pytest.approx([.05,.5,.45])
    with pytest.raises(ValueError): study.phase_weights([1,1])


def test_allocation_ignores_voltage_and_keeps_fixed_origin_membership(prepared):
    _,_,seg,pairs,base,_,groups,_ = prepared
    changed = study.vector_run(base,study.values(base))
    for r in changed['rows']: r['voltage_V'] = -9999; r['soc'] += .1
    ids = [g['pair_index'] for g in groups]
    same,_ = study.allocation(changed,seg,pairs,selected_ids=ids)
    assert [g['indices'] for g in same] == [g['indices'] for g in groups]


def test_recovers_known_resistance_and_leave_out_never_uses_excluded_voltage(prepared):
    _,_,_,_,_,a,groups,w = prepared; expected = np.array([.004,.008,.012]); target = a@expected
    fitted,score = study.fit(a,target,w,[0,1,2])
    assert fitted == pytest.approx(expected,abs=1e-10) and score < 1e-8
    prediction,folds = study.leave_pair_out(a,target,w,[0,1,2],groups)
    assert prediction[w>0] == pytest.approx(target[w>0],abs=1e-10)
    changed = target.copy(); changed[groups[0]['indices']] += 123.
    _,altered = study.leave_pair_out(a,changed,w,[0,1,2],groups)
    assert altered['folds'][0] == folds['folds'][0]
    assert np.all(np.isnan(prediction[w==0]))


def test_rank_deficiency_is_reported_not_false_certainty():
    x = np.linspace(-1,1,15); a = np.column_stack([x,x,x]); w = np.ones(15)/15
    coef,score = study.fit(a,a@np.array([.01,.02,.03]),w,[0,1,2])
    result = study.identifiability(a,a@coef,w,[0,1,2],coef)
    assert result['rank'] == 1 and result['normalized_condition_number'] is None
    assert 'NOT confidence' in result['uncertainty_interpretation']


def test_upper_bound_and_nonfinite_inputs():
    a = np.column_stack([np.ones(10),np.zeros(10),np.zeros(10)]); w = np.ones(10)
    coef,_ = study.fit(a,np.ones(10),w,[0]); assert coef[0] == pytest.approx(.2)
    with pytest.raises(ValueError): study.fit(a,np.full(10,np.nan),w,[0])
    with pytest.raises(ValueError): study.fit(a,np.ones(10),np.zeros(10),[0])


def test_time_metrics_do_not_bridge_excluded_pairs():
    rows = [dict(time_s=t,residual_V=e) for t,e in [(0,.1),(1,.1),(100,None),(200,.2),(202,.2)]]
    result = study.metrics(rows)
    assert result['covered_duration_s'] == 3
    assert result['time_rmse_mV'] == pytest.approx(1000*math.sqrt((.01+2*.04)/3))


def test_screening_is_json_serializable_and_checks_recovery(prepared):
    _,_,seg,pairs,base,_,groups,_ = prepared
    _,_,diagnostics = study.summarize_gitt(base,seg,pairs)
    result = study.screening(base,diagnostics,base,diagnostics,groups,10.,10.)
    restored = json.loads(json.dumps(result))
    assert restored['checks']['objective_improves_20pct'] is False
    assert restored['checks']['late_rest_median_max_degrades_at_most_5mV'] is True
    assert restored['all_pass'] is False
