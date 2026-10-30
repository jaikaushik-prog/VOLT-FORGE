"""V4 mission, wiring, cost, protection, sizing and charging behaviour."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from voltforge.models.cell_catalogue import load_additional
from voltforge.project import Project
from voltforge.studio.design_rules import review
from voltforge.studio.failure_search import resize_parallel, sizing_verdict
from voltforge.studio.loads import application_view, apply_mission, battery_current, build_mission
from voltforge.studio.network import settings_default, simulate, template
from voltforge.studio.parts import estimate, load_prices, unit_price
from voltforge.studio.protection import defaults
from voltforge.studio.store import Studio

ROOT = Path(__file__).resolve().parents[1]
BANK = load_additional(ROOT)
LG = 'LG_M50T_ECN'


def design(count=2, kind='parallel', model=LG):
    g = template(kind, count)
    for c in g['cells']: c['model'] = model
    return g


def settings(current=3., seconds=60.):
    s = settings_default(); s['profile'] = [dict(start_s=0., end_s=seconds, current_A=current)]
    return s


@pytest.fixture
def studio(tmp_path):
    path = tmp_path/'project'; Project.create_reference(path)
    return Studio(path)


def test_pi_preset_uses_the_voltage_floor_and_labels_every_value():
    s = apply_mission(settings_default(), build_mission(preset='pi5_gateway_backup'))
    assert s['profile'][0]['current_A'] == pytest.approx(25/(.9*3.3)) == pytest.approx(8.4175, abs=1e-3)
    assert s['profile'][0]['end_s'] == 600 and s['limits']['min_voltage_V'] == 3.3 and s['ambient_C'] == 23
    rows = {r['key']: r['basis'] for r in application_view(s)['requirements']}
    assert rows['device_power_W'] == 'sourced' and rows['duration_s'] == 'assumed' and rows['voltage_floor_V'] == 'assumed'
    assert 'held constant' in application_view(s)['approximation']


def test_editing_a_preset_value_relabels_only_that_value_as_custom():
    s = apply_mission(settings_default(), build_mission(preset='pi5_gateway_backup'))
    s['profile'][0]['end_s'] = 900.
    view = application_view(s); rows = {r['key']: r for r in view['requirements']}
    assert rows['duration_s']['basis'] == 'custom' and rows['duration_s']['value'] == 900 and '600' in rows['duration_s']['reason']
    assert rows['voltage_floor_V']['basis'] == 'assumed' and view['customized']


def test_custom_watts_and_charge_tests_set_the_right_current():
    watts = apply_mission(settings_default(), build_mission(preset='custom_watts', power_W=10., efficiency=.8, voltage_floor_V=3.2, duration_s=120.))
    assert watts['profile'][0]['current_A'] == pytest.approx(battery_current(10, .8, 3.2))
    assert {r['basis'] for r in application_view(watts)['requirements']} == {'custom'}
    charge = apply_mission(settings_default(), build_mission('charge', current_A=2., duration_s=300.))
    assert charge['profile'][0]['current_A'] == -2 and charge['limits']['min_voltage_V'] is None
    with pytest.raises(ValueError, match='lowest battery voltage'):
        build_mission(preset='custom_watts', power_W=10.)
    with pytest.raises(ValueError, match='discharge tests'):
        build_mission('charge', 'pi5_gateway_backup')


def test_setup_inputs_create_a_design_and_the_mission_reaches_the_result(studio):
    doc = studio.create('parallel', 2, 'Gateway', mission=dict(preset='pi5_gateway_backup'))
    assert doc['application']['name'] == 'Raspberry Pi 5 gateway backup'
    test = studio.run(doc['id'], doc['version'])
    assert test['summary']['application']['requirements'][0]['basis'] == 'sourced'
    assert test['case']['description']['name'] == 'Raspberry Pi 5 gateway backup'
    assert test['status'] == 'completed' and test['name'].startswith('10 min')


def test_resistive_self_short_blocks_a_direct_simulation_as_well_as_preflight():
    g = design(1)
    g['connections'].append(dict(id='wire1', a='cell1:p', b='cell1:n', resistance_mohm=5., source='Test'))
    with pytest.raises(ValueError, match='short circuit'):
        simulate(g, settings(), BANK)


def test_a_cell_wired_backwards_in_series_is_flagged_and_saved_with_the_result():
    g = design(3, 'series')
    g['connections'][1].update(a='cell2:n', b='cell3:n')
    g['output']['negative'] = 'cell3:p'
    result = simulate(g, settings(1.), BANK)
    found = {w['rule']: w for w in result.summary['design_warnings']}
    assert 'opposed_cell' in found and found['opposed_cell']['cells'] == ['cell3']


def test_mixed_cells_in_parallel_warn_but_still_run():
    g = design(2); g['cells'][1]['model'] = 'SAMSUNG_30T'
    result = simulate(g, settings(), BANK)
    assert result.status == 'completed'
    assert any(w['rule'] == 'mixed_parallel' for w in result.summary['design_warnings'])


def test_a_clean_parallel_design_raises_no_warnings():
    assert review(design(4), BANK) == []


def test_large_charge_mismatch_reports_circulating_current():
    g = design(2); g['cells'][0]['charge_pct'] = 95.; g['cells'][1]['charge_pct'] = 25.
    for w in g['connections']: w['resistance_mohm'] = .1
    assert any(w['rule'] == 'circulating_current' for w in review(g, BANK))


def test_cost_keeps_currencies_apart_and_never_prices_an_unknown_at_zero():
    prices = deepcopy(load_prices(ROOT))
    prices['items']['converter'] = dict(name='Test converter', slot='converter', listings=[])
    g = design(2); g['cells'][1]['model'] = 'SAMSUNG_30T'
    result = estimate(g, BANK, prices)
    assert result['subtotals'] == {'INR': 1206, 'USD': 6.99}
    assert 'Test converter' in result['unpriced']
    assert next(r for r in result['lines'] if r['part'] == 'Test converter')['priced'] is False


def test_price_is_the_average_of_one_parts_listings_and_refuses_mixed_currencies():
    assert unit_price(dict(name='x', listings=[dict(price=100, currency='INR'), dict(price=200, currency='INR')]))['value'] == 150
    with pytest.raises(ValueError, match='one currency'):
        unit_price(dict(name='x', listings=[dict(price=1, currency='INR'), dict(price=1, currency='USD')]))


def test_saved_tests_keep_their_prices_when_todays_prices_change(studio):
    doc = studio.create('parallel', 2, 'Cost', mission=dict(preset='stress_12a'))
    test = studio.run(doc['id'], doc['version'])
    before = test['parts']['subtotals']
    studio.prices['items']['cell:'+LG]['listings'][0]['price'] = 9999
    assert studio.test(test['id'])['parts']['subtotals'] == before
    assert studio.document(doc['id'])['parts']['subtotals']['INR'] > before['INR']


def test_voltage_ceiling_disconnects_a_charging_test():
    g = design(1); g['cells'][0]['charge_pct'] = 90.
    s = settings(-1.45, 3000.)
    s['protection'] = dict(defaults(), current_max_A=None, voltage_max_V=4.1)
    result = simulate(g, s, BANK)
    assert result.summary['protection']['event']['quantity'] == 'voltage_V'
    assert result.summary['protection']['event']['threshold'] == 4.1


def test_charge_temperature_window_only_acts_while_charging():
    g = design(1); g['cells'][0]['temperature_C'] = 20.
    s = settings(-1., 20.); s['protection'] = dict(defaults(), current_max_A=None, charge_temperature_C=[25., 45.])
    assert simulate(g, s, BANK).summary['protection']['event']['quantity'] == 'charge_temperature_C'
    s = settings(1., 20.); s['protection'] = dict(defaults(), current_max_A=None, charge_temperature_C=[25., 45.])
    assert simulate(g, s, BANK).summary['protection']['event'] is None


def test_saved_v3_protection_definitions_stay_valid():
    g = design(1); s = settings(1., 20.)
    old = defaults(); old.pop('voltage_max_V'); old.pop('charge_temperature_C')
    s['protection'] = old
    assert simulate(g, s, BANK).status == 'completed'


def test_charging_reports_time_charge_energy_and_why_it_stopped():
    result = simulate(design(1), settings(-1., 600.), BANK)
    charging = result.summary['charging']
    assert charging['charge_gained_Ah'] == pytest.approx(600/3600) and charging['energy_received_Wh'] > 0
    assert charging['stop_reason'] == 'requested_time_reached' and 'not a full recharge' in charging['note']


def test_link_checks_report_density_without_calling_it_a_rating():
    from voltforge.studio.conductors import apply, copper_reference
    g = design(2); apply(g['connections'][0], dict(copper_reference(), length_mm=20., width_mm=8., thickness_mm=.2, contact_mohm=.1,
                                                     material_source='Test', assumption_source='Test'))
    links = simulate(g, settings(6.), BANK).summary['link_checks']
    assert links['links'][0]['current_density_A_mm2'] == pytest.approx(links['links'][0]['peak_current_A']/1.6)
    assert links['links'][1]['current_density_A_mm2'] is None and 'not a certified' in links['note']


@pytest.mark.parametrize('count', [1, 2, 3, 6])
def test_resize_keeps_models_states_links_and_output_style(count):
    g = design(4); g['cells'][2]['charge_pct'] = 65.
    for w in g['connections']: w['resistance_mohm'] = 2.5
    g['output']['negative'] = 'cell4:n'
    sized = resize_parallel(g, count)
    assert len(sized['cells']) == count and len(sized['connections']) == 2*(count-1)
    assert {c['model'] for c in sized['cells']} == {LG}
    assert all(w['resistance_mohm'] == 2.5 for w in sized['connections'])
    assert sized['output'] == dict(positive='cell1:p', negative=f'cell{count}:n')
    simulate(sized, settings(2.), BANK)


def test_resize_refuses_a_series_design():
    with pytest.raises(ValueError, match='simple parallel'):
        resize_parallel(design(2, 'series'), 1)


def test_find_smallest_separates_outcomes_and_reopens_the_exact_inputs(studio):
    doc = studio.create('parallel', 4, 'Sizing', mission=dict(preset='pi5_gateway_backup'))
    base = studio.run(doc['id'], doc['version'])
    record = studio.begin_investigation(doc['id'], doc['version'], base['id'], 'cell_count')
    assert [p['cell_count'] for p in record['planned']] == [1, 2, 3, 4]
    for i in range(4): record = studio.investigate_case(record['id'], i)
    verdicts = [c['sizing'] for c in record['cases']]
    assert verdicts[0] == 'refused' and verdicts[1:] == ['qualifies']*3
    assert record['sizing']['smallest_cell_count'] == 2 and 'among the parallel arrangements tested' in record['sizing']['claim']
    assert record['cases'][1]['parts']['subtotals']['INR'] < record['cases'][3]['parts']['subtotals']['INR']
    opened = studio.open_investigation_case(record['id'], 1)
    assert len(opened['design']['graph']['cells']) == 2 and opened['test']['settings'] == base['settings']


def test_sizing_verdict_does_not_pass_an_untargeted_case():
    class R: pass
    r = R(); r.stop = None
    r.summary = dict(checks=[], assessment=dict(requested_demand_met=True), thermal_available=True, verification={})
    assert sizing_verdict(r, None) == 'incomplete'
