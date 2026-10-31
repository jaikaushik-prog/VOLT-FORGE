"""Synthetic regressions for limit coverage, candidate parts and charge semantics.

No raw measurements, fitted parameters, frozen outputs or external services.
"""
from copy import deepcopy
from pathlib import Path

import pytest

from voltforge.models.cell_catalogue import load_additional
from voltforge.models.custom_cells import normalize
from voltforge.studio.failure_search import inputs, outcome, sizing_verdict
from voltforge.studio.loads import apply_mission, build_mission, validate_mission
from voltforge.studio.network import settings_default, simulate, template, validate_settings
from voltforge.studio.parts import estimate, load_prices
from voltforge.studio.protection import defaults
from voltforge.studio.report import html_report


ROOT = Path(__file__).resolve().parents[1]
LIMITS = dict(voltage_V=[2.5, 4.2], max_discharge_A=10., max_charge_A=10.,
              discharge_temperature_C=[-20., 55.], charge_temperature_C=[0., 45.])


def fixture(kind='parallel', count=1, current=1., seconds=2., limits=None, **cell_values):
    definition = dict(name='Synthetic cell', capacity_Ah=2., nominal_voltage_V=3.7, resistance_mohm=20.)
    if limits is not None:
        definition['operating_limits'] = deepcopy(limits)
    definition.update(cell_values)
    bank = {'custom_fixture': normalize(definition, 'custom_fixture')}
    graph = template(kind, count)
    for cell in graph['cells']:
        cell['model'] = 'custom_fixture'
    settings = settings_default()
    settings['profile'] = [dict(start_s=0., end_s=seconds, current_A=current)]
    settings['limits']['min_voltage_V'] = 3.3
    return graph, settings, bank


def test_unspecified_cell_limits_cannot_qualify_even_with_thermal_defaults_and_closed_budget():
    graph, settings, bank = fixture(current=8., seconds=60.)
    result = simulate(graph, settings, bank)
    assert result.status == 'completed'
    assert result.summary['verification']['first_law_closed']
    assert result.summary['metrics']['minimum_voltage_V'] == pytest.approx(3.54)
    assert sizing_verdict(result, None) == 'incomplete'
    assert outcome(graph, settings, result)['kind'] == 'unassessed'
    assert set(result.summary['operating_limit_coverage']['cells'][0]['missing']) == {
        'voltage_V', 'max_discharge_A', 'discharge_temperature_C'}


def test_only_current_directions_that_occur_need_limits():
    limits = {key: value for key, value in LIMITS.items() if 'charge' not in key or 'discharge' in key}
    graph, settings, bank = fixture(limits=limits)
    result = simulate(graph, settings, bank)
    assert sizing_verdict(result, None) == 'qualifies'
    settings['profile'][0]['current_A'] = -1.
    result = simulate(graph, settings, bank)
    assert sizing_verdict(result, None) == 'incomplete'
    assert set(result.summary['operating_limit_coverage']['cells'][0]['missing']) == {'max_charge_A', 'charge_temperature_C'}


@pytest.mark.parametrize('missing', ['voltage_V', 'max_discharge_A', 'discharge_temperature_C'])
def test_each_required_limit_is_coverage_not_an_implicit_unlimited_rating(missing):
    limits = deepcopy(LIMITS)
    limits.pop(missing)
    graph, settings, bank = fixture(limits=limits)
    result = simulate(graph, settings, bank)
    assert sizing_verdict(result, None) == 'incomplete'
    assert result.summary['operating_limit_coverage']['cells'][0]['missing'] == [missing]


def test_internal_charging_requires_charge_limits_during_a_discharge_mission():
    limits = {key: value for key, value in LIMITS.items() if 'charge' not in key or 'discharge' in key}
    graph, settings, bank = fixture(count=2, current=.1, limits=limits,
                                    reference={'soc': [0., 1.], 'voltage_V': [3., 4.2]})
    graph['cells'][1]['charge_pct'] = 60.
    result = simulate(graph, settings, bank)
    assert result.rows[0]['cell_current_A'][1] < 0 < result.rows[0]['current_A']
    coverage = result.summary['operating_limit_coverage']['cells']
    assert coverage[0]['complete'] and not coverage[1]['complete']
    assert coverage[1]['directions'] == ['charge']
    assert sizing_verdict(result, None) == 'incomplete'


def test_explicit_cell_limit_still_refuses_and_missing_thermal_still_incomplete():
    graph, settings, bank = fixture(current=8., limits=dict(LIMITS, max_discharge_A=7.))
    with pytest.raises(ValueError, match='operating limit'):
        simulate(graph, settings, bank)
    graph, settings, bank = fixture(limits=LIMITS, thermal_preset='none')
    assert sizing_verdict(simulate(graph, settings, bank), None) == 'incomplete'


def test_known_lg_rules_cover_the_mission_without_requiring_duplicate_catalogue_fields():
    graph, settings, _ = fixture(count=2, current=25/(.9*3.3))
    for cell in graph['cells']:
        cell['model'] = 'LG_M50T_ECN'
    result = simulate(graph, settings, load_additional(ROOT))
    assert result.summary['operating_limit_coverage']['complete']
    assert sizing_verdict(result, None) == 'qualifies'
    historical = deepcopy(result)
    historical.summary.pop('operating_limit_coverage')
    assert sizing_verdict(historical, None) == 'incomplete'
    result.summary['verification'].pop('first_law_closed')
    assert sizing_verdict(result, None) == 'incomplete'


@pytest.mark.parametrize('kind,count,per_cell_A', [('parallel', 1, 1.), ('series', 2, 1.), ('parallel', 2, .5), ('mixed', 4, .5)])
def test_pack_charge_is_topology_independent_and_per_cell_charge_is_separate(kind, count, per_cell_A):
    graph, settings, bank = fixture(kind, count, -1., 60., limits=LIMITS)
    # Ideal symmetric paths give the analytical equal-share control. Finite
    # same-end ladder links intentionally produce unequal branch currents.
    for wire in graph['connections']:
        wire['resistance_mohm'] = 0.
    charging = simulate(graph, settings, bank).summary['charging']
    assert charging['version'] == 'voltforge.pack-charge/2'
    assert charging['received_charge_Ah'] == pytest.approx(60/3600)
    assert charging['delivered_charge_Ah'] == 0
    assert charging['net_charge_gained_Ah'] == pytest.approx(60/3600)
    assert charging['charge_gained_Ah'] == charging['net_charge_gained_Ah']
    assert list(charging['per_cell_charge_gained_Ah'].values()) == pytest.approx([per_cell_A*60/3600]*count)


def test_mixed_cycle_distinguishes_gross_received_delivered_and_net_pack_charge():
    graph, settings, bank = fixture('series', 2, limits=LIMITS)
    settings['profile'] = [dict(start_s=0., end_s=2., current_A=-2.), dict(start_s=2., end_s=5., current_A=1.),
                           dict(start_s=5., end_s=6., current_A=0.)]
    charging = simulate(graph, settings, bank).summary['charging']
    assert charging['received_charge_Ah'] == pytest.approx(4/3600)
    assert charging['delivered_charge_Ah'] == pytest.approx(3/3600)
    assert charging['net_charge_gained_Ah'] == pytest.approx(1/3600)


def test_pack_charge_uses_actual_served_intervals_after_protection_and_early_stop():
    graph, settings, bank = fixture(current=-2., seconds=10., limits=LIMITS)
    settings['protection'] = dict(defaults(), current_max_A=1., response_delay_s=.5)
    result = simulate(graph, settings, bank)
    assert result.summary['charging']['received_charge_Ah'] == pytest.approx(1/3600)
    assert result.summary['service']['unserved_demand_s'] == pytest.approx(9.5)
    settings.pop('protection')
    graph['cells'][0]['charge_pct'] = 99.99
    result = simulate(graph, settings, bank)
    assert result.status == 'stopped' and result.stop['reason'] == 'charge_domain'
    assert result.summary['charging']['received_charge_Ah'] == pytest.approx(2*result.rows[-1]['time_s']/3600)


def test_external_disconnect_does_not_confuse_internal_cell_transfer_with_pack_charge():
    graph, settings, bank = fixture(count=2, current=-1., seconds=2., limits=LIMITS,
                                    reference={'soc': [0., 1.], 'voltage_V': [3., 4.2]})
    graph['cells'][1]['charge_pct'] = 60.
    settings['protection'] = dict(defaults(), current_max_A=.1, response_delay_s=0.)
    charging = simulate(graph, settings, bank).summary['charging']
    assert charging['received_charge_Ah'] == charging['net_charge_gained_Ah'] == 0
    assert min(charging['per_cell_charge_gained_Ah'].values()) < 0 < max(charging['per_cell_charge_gained_Ah'].values())


def test_ideal_link_currents_are_unknown_and_finite_link_currents_remain_calculated():
    graph, settings, bank = fixture(count=2, current=2., limits=LIMITS)
    graph['connections'][0]['resistance_mohm'] = 0.
    result = simulate(graph, settings, bank)
    first, second = result.summary['link_checks']['links']
    assert first['peak_current_A'] is None and first['current_density_A_mm2'] is None
    assert first['peak_loss_W'] == 0 and first['current_status'] == 'not_computed'
    assert 'Zero loss does not imply zero current' in first['current_reason']
    assert second['peak_current_A'] > 0 and second['current_status'] == 'calculated'
    for wire in graph['connections']:
        wire['resistance_mohm'] = 0.
    result = simulate(graph, settings, bank)
    assert result.rows[0]['cell_current_A'] == pytest.approx([1., 1.])
    assert all(link['peak_current_A'] is None for link in result.summary['link_checks']['links'])


def candidate(kind='parallel', count=2, power=25.):
    graph = template(kind, count)
    for cell in graph['cells']:
        cell['model'] = 'LG_M50T_ECN'
    settings = apply_mission(settings_default(), build_mission(preset='custom_watts', power_W=power, efficiency=.9, voltage_floor_V=3.3))
    bank = load_additional(ROOT)
    return graph, settings, bank


def board(parts):
    return next(row for row in parts['lines'] if row['slot'] == 'converter')


@pytest.mark.parametrize('kind,count', [('series', 2), ('mixed', 4)])
def test_series_and_mixed_batteries_do_not_inherit_compatible_parallel_boards(kind, count):
    graph, settings, bank = candidate(kind, count)
    result = estimate(graph, bank, load_prices(ROOT), settings)
    assert board(result)['compatibility']['status'] == 'incompatible'
    protection = next(row for row in result['lines'] if row['slot'] == 'protection')
    assert protection['included'] is False and protection['included_in_candidate'] is True
    assert protection['compatibility']['status'] == 'not_assessed'


@pytest.mark.parametrize('count', [1, 3])
def test_unsupported_holder_counts_remain_unassessed(count):
    graph, settings, bank = candidate(count=count)
    assert board(estimate(graph, bank, load_prices(ROOT), settings))['compatibility']['status'] == 'not_assessed'


def test_unknown_cells_mixed_cells_unknown_demand_and_excess_power_are_not_board_passes():
    prices = load_prices(ROOT)
    graph, settings, bank = fixture(count=2, limits=LIMITS)
    assert board(estimate(graph, bank, prices, settings))['compatibility']['status'] == 'not_assessed'
    graph, settings, bank = candidate()
    assert board(estimate(graph, bank, prices))['compatibility']['status'] == 'not_assessed'
    graph['cells'][1]['model'] = 'SAMSUNG_30T'
    assert board(estimate(graph, bank, prices, settings))['compatibility']['status'] == 'incompatible'
    graph, settings, bank = candidate(power=31.)
    assert board(estimate(graph, bank, prices, settings))['compatibility']['status'] == 'incompatible'


def test_matching_holder_and_power_is_only_a_conditional_candidate_with_source_path_limits():
    graph, settings, bank = candidate()
    prices = load_prices(ROOT)
    original = deepcopy(prices)
    result = estimate(graph, bank, prices, settings)
    row = board(result)
    assert row['compatibility']['status'] == 'conditional'
    assert row['selection'] == 'candidate' and row['cost'] == 46.
    assert result['cell_subtotals'] == {'INR': 2412.} and result['cell_cost_complete']
    assert 'external-input step-down path' in row['limits']
    assert any('2.91 A' in text for text in row['compatibility']['conditions'])
    assert prices == original  # Historical catalogue/provenance stays intact.
    settings['profile'] = [dict(start_s=0., end_s=2., current_A=-3.)]
    with pytest.raises(ValueError, match='1.455 A'):
        simulate(graph, settings, bank)
    assert board(estimate(graph, bank, prices, settings))['compatibility']['status'] == 'not_assessed'


def test_cell_cost_keeps_currencies_apart_and_does_not_call_a_partial_price_complete():
    graph, settings, bank = candidate()
    graph['cells'][1]['model'] = 'SAMSUNG_30T'
    prices = load_prices(ROOT)
    result = estimate(graph, bank, prices, settings)
    assert result['cell_subtotals'] == {'INR': 1206., 'USD': 6.99}
    assert result['cell_cost_complete']
    prices = deepcopy(prices)
    prices['items'].pop('cell:SAMSUNG_30T')
    result = estimate(graph, bank, prices, settings)
    assert result['cell_subtotals'] == {'INR': 1206.} and not result['cell_cost_complete']


def test_backup_efficiency_remains_an_assumption_for_the_correct_power_path():
    settings = apply_mission(settings_default(), build_mission(preset='pi5_gateway_backup'))
    row = next(r for r in settings['mission']['requirements'] if r['key'] == 'converter_efficiency')
    assert row['basis'] == 'assumed' and row['value'] == .9
    assert 'external power-input step-down path' in row['reason']
    assert 'no measured backup-efficiency curve' in row['reason']


@pytest.mark.parametrize('change', ['current', 'floor', 'power_metadata', 'efficiency_metadata', 'requirement_metadata', 'pressure_test'])
def test_stale_power_proxy_cannot_assess_the_live_board_demand(change):
    graph, settings, bank = candidate()
    if change == 'current':
        settings['profile'][0]['current_A'] = 12.
    elif change == 'floor':
        settings['limits']['min_voltage_V'] = 3.5
    elif change == 'power_metadata':
        settings['mission']['load']['power_W'] = 30.
    elif change == 'efficiency_metadata':
        settings['mission']['load']['converter_efficiency'] = .85
        next(r for r in settings['mission']['requirements'] if r['key'] == 'converter_efficiency')['value'] = .85
    elif change == 'requirement_metadata':
        next(r for r in settings['mission']['requirements'] if r['key'] == 'device_power_W')['value'] = 20.
    else:
        graph, settings = inputs(graph, settings, dict(factor=1.25, ambient_offset=0., extra_resistance=0.))
    validate_settings(settings)  # Editable profiles remain valid simulations.
    row = board(estimate(graph, bank, load_prices(ROOT), settings))
    assert row['compatibility']['status'] == 'not_assessed'
    assert row['compatibility']['demand']['power_W'] is None
    assert any('no longer match' in reason for reason in row['compatibility']['reasons'])
    assert row['selection'] == 'candidate' and row['cost'] == 46.


def test_ambient_and_duration_edits_do_not_invalidate_an_unchanged_power_proxy():
    graph, settings, bank = candidate()
    settings['ambient_C'] = 25.
    settings['profile'][0]['end_s'] = 120.
    row = board(estimate(graph, bank, load_prices(ROOT), settings))
    assert row['compatibility']['status'] == 'conditional'
    assert row['compatibility']['demand']['power_W'] == 25.


INVALID_POWER_FIELDS = [
    ('power_W', 'missing'), ('power_W', '25'), ('power_W', None), ('power_W', float('nan')),
    ('power_W', float('inf')), ('power_W', True), ('power_W', 0.), ('power_W', -1.), ('power_W', 100001.),
    ('converter_efficiency', 'missing'), ('converter_efficiency', '0.9'), ('converter_efficiency', None),
    ('converter_efficiency', float('nan')), ('converter_efficiency', True), ('converter_efficiency', 0.),
    ('converter_efficiency', -.1), ('converter_efficiency', 1.01)]


def invalid_power_settings(field, value):
    _, settings, _ = candidate()
    if value == 'missing':
        settings['mission']['load'].pop(field)
    else:
        settings['mission']['load'][field] = value
    return settings


@pytest.mark.parametrize('field,value', INVALID_POWER_FIELDS)
def test_invalid_power_values_are_rejected_and_standalone_parts_are_robust(field, value):
    graph, _, bank = candidate()
    settings = invalid_power_settings(field, value)
    with pytest.raises(ValueError):
        validate_mission(settings['mission'])
    with pytest.raises(ValueError):
        validate_settings(settings)
    compatibility = board(estimate(graph, bank, load_prices(ROOT), settings))['compatibility']
    assert compatibility['status'] == 'not_assessed'
    assert compatibility['demand']['power_W'] is None


@pytest.mark.parametrize('key', ['device_power_W', 'converter_efficiency', 'voltage_floor_V'])
def test_power_missions_require_their_conversion_requirement_records(key):
    _, settings, _ = candidate()
    settings['mission']['requirements'] = [r for r in settings['mission']['requirements'] if r['key'] != key]
    with pytest.raises(ValueError, match='missing required'):
        validate_settings(settings)


@pytest.mark.parametrize('settings', [None, [], 'invalid', True, {'mission': 1}, {'mission': []}, {'mission': True}])
def test_standalone_parts_do_not_crash_on_malformed_settings(settings):
    graph, _, bank = candidate()
    assert board(estimate(graph, bank, load_prices(ROOT), settings))['compatibility']['status'] == 'not_assessed'


@pytest.mark.parametrize('profile', [None, [], [None], [{'current_A': '12'}],
                                    [dict(start_s=1., end_s=2., current_A=8.4175)]])
def test_standalone_parts_do_not_crash_on_malformed_live_profile(profile):
    graph, settings, bank = candidate()
    settings['profile'] = profile
    assert board(estimate(graph, bank, load_prices(ROOT), settings))['compatibility']['status'] == 'not_assessed'


def test_malformed_power_mission_is_rejected_before_save_or_recovery_artifacts(tmp_path):
    from voltforge.project.service import Project
    from voltforge.studio.store import Studio
    Project.create_reference(tmp_path/'project')
    studio = Studio(tmp_path/'project')
    original = studio.create('parallel', 2, 'Original', mission={'preset': 'pi5_gateway_backup'})
    snapshot = lambda: {str(path.relative_to(studio.root)): path.read_bytes() for path in studio.root.rglob('*') if path.is_file()}
    before = snapshot()
    for field, value in INVALID_POWER_FIELDS:
        invalid = invalid_power_settings(field, value)
        for method in ('create_from_graph', 'save_copy'):
            with pytest.raises(ValueError):
                getattr(studio, method)(original['graph'], invalid)
            assert snapshot() == before
        with pytest.raises(ValueError):
            studio.save(original['id'], original['version'], original['graph'], invalid)
        assert snapshot() == before
    assert studio.document(original['id'])['version'] == original['version']


def report_record(graph, settings, result):
    return dict(graph=graph, settings=settings, summary=result.summary, rows=result.rows, status=result.status,
                stop=result.stop, name='Synthetic review regression', design_name='Synthetic design', created_utc='2026-10-31T00:00:00Z')


def test_html_report_distinguishes_new_pack_charge_and_historical_aggregate_without_mutation():
    graph, settings, bank = fixture('series', 2, -1., 60., limits=LIMITS)
    record = report_record(graph, settings, simulate(graph, settings, bank))
    record['parts'] = estimate(graph, bank, load_prices(ROOT), settings)
    rendered = html_report(record)
    assert 'Pack charge received (gross)' in rendered and '0.0167 Ah' in rendered
    assert 'incompatible' in rendered and 'Cell operating-limit coverage' in rendered
    historical = deepcopy(record)
    historical['summary'].pop('operating_limit_coverage')
    historical['summary']['charging'] = dict(elapsed_s=60., charge_gained_Ah=2*60/3600,
        energy_received_Wh=record['summary']['charging']['energy_received_Wh'], stop_message='Requested time ended.', note='Historical saved result.')
    for row in historical['parts']['lines']:
        row.pop('compatibility', None)
    before = deepcopy(historical)
    rendered = html_report(historical)
    assert 'Aggregate cell charge gained (historical; not pack Ah)' in rendered and '0.0333 Ah' in rendered
    assert 'Pack charge received (gross)' not in rendered
    assert 'not recorded in this historical result' in rendered
    assert historical == before


def test_historical_ideal_wire_zero_is_not_presented_as_a_measured_or_calculated_zero():
    graph, settings, bank = fixture(count=2, current=2., limits=LIMITS)
    for wire in graph['connections']:
        wire['resistance_mohm'] = 0.
    record = report_record(graph, settings, simulate(graph, settings, bank))
    for link in record['summary']['link_checks']['links']:
        link['peak_current_A'] = 0.  # A historical summary remains immutable.
        link.pop('current_status')
        link.pop('current_reason')
    before = deepcopy(record)
    assert 'Not computed (ideal link)' in html_report(record)
    assert record == before
