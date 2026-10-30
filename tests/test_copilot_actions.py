"""Copilot actions from natural prompts, using the shapes the live model returned in the audit."""
import pytest

from voltforge.studio.copilot import apply_actions, compact_trace
from voltforge.studio.network import settings_default, template


def action(op, target='', value=0, text=''):
    return dict(op=op, target=target, value=value, text=text, from_terminal='', to_terminal='')


BUILD = action('use_template', value=4, text='parallel')


@pytest.mark.parametrize('target', ['all', ''])
def test_new_draft_applies_a_blank_or_all_target_to_every_cell(target):
    graph, settings = template('blank'), settings_default()
    labels = apply_actions(graph, settings, [BUILD, action('set_charge', target, 80), action('set_model', target, text='SAMSUNG_30T')], new_design=True)
    assert [c['charge_pct'] for c in graph['cells']] == [80]*4
    assert {c['model'] for c in graph['cells']} == {'SAMSUNG_30T'}
    assert 'All cells: starting charge 80%' in labels


def test_new_draft_accepts_cell_edits_listed_before_the_template():
    graph, settings = template('blank'), settings_default()
    apply_actions(graph, settings, [action('set_temperature', 'all', 30), BUILD], new_design=True)
    assert [c['temperature_C'] for c in graph['cells']] == [30]*4


@pytest.mark.parametrize('target', ['all', ''])
def test_existing_design_must_name_the_cell(target):
    graph, settings = template('parallel', 4), settings_default()
    with pytest.raises(ValueError, match='Select an existing cell'):
        apply_actions(graph, settings, [action('set_charge', target, 80)])
    assert [c['charge_pct'] for c in graph['cells']] == [70]*4


def test_named_cell_still_edits_only_that_cell_in_a_new_draft():
    graph, settings = template('blank'), settings_default()
    apply_actions(graph, settings, [BUILD, action('set_charge', 'cell2', 55)], new_design=True)
    assert [c['charge_pct'] for c in graph['cells']] == [70, 55, 70, 70]


def test_trace_is_bounded_and_keeps_both_ends_and_events():
    rows = [dict(time_s=float(i), current_A=1., voltage_V=3.6, cell_current_A=[.5, .5], temperature_C=[None, None], charge_pct=[70., 70.]) for i in range(5000)]
    rows[1234]['event_kind'] = 'requested_load_change'
    trace = compact_trace(rows)
    assert len(trace) <= 45
    assert trace[0]['time_s'] == 0 and trace[-1]['time_s'] == 4999 and 1234 in [r['time_s'] for r in trace]
