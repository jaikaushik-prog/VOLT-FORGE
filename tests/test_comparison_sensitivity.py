"""Comparison changes must reach the actual cell/fixture used by the solver."""
import json
from pathlib import Path

import numpy as np
import pytest

from scripts.compare_round1_options import make_inputs,scenario_models
from voltforge.models.cell_catalogue import load_additional
from voltforge.project.service import Project
from voltforge.studio.network import simulate
from voltforge.studio.store import Studio

ROOT=Path(__file__).resolve().parents[1]


def protocol():return json.loads((ROOT/'configs/round1_robustness_protocol_v1.json').read_text())


def test_cooling_scenario_reaches_builtin_cell_defaults():
    p=protocol();models=load_additional(ROOT);option=p['options'][0]
    nominal=next(s for s in p['scenarios'] if s['kind']=='nominal')
    cooling=next(s for s in p['scenarios'] if s['key']=='cooling_half')
    graph,settings=make_inputs(p,option,nominal,models)
    baseline=simulate(graph,settings,models)
    graph,settings=make_inputs(p,option,cooling,models)
    changed=simulate(graph,settings,models)
    assert changed.status==baseline.status=='completed'
    assert changed.summary['metrics']['peak_temperature_C']>baseline.summary['metrics']['peak_temperature_C']
    for entry in changed.summary['thermal_assumptions']:
        assert entry['parameters']['ambient_conductance_W_K']['value']==pytest.approx(models['LG_M50T_ECN']['thermal_defaults']['ambient_conductance_W_K']/2)
        assert entry['parameters']['ambient_conductance_W_K']['classification']=='user_override'


def test_identical_parameter_scenario_is_reused_across_physical_options(tmp_path):
    root=tmp_path/'project';Project.create_reference(root);studio=Studio(root)
    p=protocol();scenario=next(s for s in p['scenarios'] if s['key']=='resistance_0_1.1');cache={}
    baseline_graph,settings=make_inputs(p,p['options'][0],{'kind':'nominal'},studio.models)
    baseline=simulate(baseline_graph,settings,studio.models)
    graph,settings=make_inputs(p,p['options'][0],scenario,studio.models);scenario_models(studio,graph,scenario,cache)
    changed_key=graph['cells'][0]['model'];changed=studio.models[changed_key];parent=studio.models['LG_M50T_ECN']
    assert changed_key!='LG_M50T_ECN' and changed['origin']=='user'
    assert np.array(changed['r0_ohm'])==pytest.approx(np.array(parent['r0_ohm'])*1.1)
    assert changed['operating_limits']['max_charge_A']==1.455
    assert all(c['model']=='LG_M50T_ECN' for c in graph['cells'][1:])
    result=simulate(graph,settings,studio.models)
    assert result.rows[0]['cell_current_A'][0]<baseline.rows[0]['cell_current_A'][0]
    other,_=make_inputs(p,p['options'][1],scenario,studio.models);scenario_models(studio,other,scenario,cache)
    assert other['cells'][0]['model']==changed_key and len(cache)==1
    reopened=Studio(root)
    assert changed_key in reopened.models


def test_combined_case_applies_preparation_as_well_as_parameter_changes(tmp_path):
    root=tmp_path/'project';Project.create_reference(root);studio=Studio(root)
    p=protocol();scenario=next(s for s in p['scenarios'] if s['key']=='combined_weak_first')
    graph,_=make_inputs(p,p['options'][0],scenario,studio.models);scenario_models(studio,graph,scenario,{})
    assert graph['cells'][0]['charge_pct']==68.
    assert graph['cells'][0]['polarization_V']==.02
    assert studio.models[graph['cells'][0]['model']]['capacity_Ah']==pytest.approx(4.75)
    assert all(c['charge_pct']==70. and c['polarization_V']==0. for c in graph['cells'][1:])
