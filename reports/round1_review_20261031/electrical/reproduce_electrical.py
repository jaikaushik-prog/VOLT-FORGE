"""Read-only V4 synthetic probes; writes only the requested fresh JSON receipt.

No project creation, raw-data reader, network call, tuning, or frozen-result mutation.
"""
from copy import deepcopy
from importlib.metadata import version, PackageNotFoundError
from pathlib import Path
import argparse
import json
import platform
import sys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--repo', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    if args.out.exists():
        raise SystemExit('Refusing to overwrite receipt')
    sys.path.insert(0, str(args.repo / 'src'))
    from voltforge.models.cell_catalogue import load_additional
    from voltforge.models.custom_cells import normalize
    from voltforge.studio.failure_search import sizing_verdict, outcome
    from voltforge.studio.network import simulate, settings_default, template
    from voltforge.studio.parts import estimate, load_prices

    packages = {}
    for item in ['numpy', 'scipy', 'pandas', 'matplotlib', 'openpyxl', 'pytest']:
        try:
            packages[item] = version(item)
        except PackageNotFoundError:
            packages[item] = 'not installed'
    receipt = dict(python=sys.version, platform=platform.platform(), packages=packages,
                   scope='Synthetic/local model probes; no raw measurements read', cases={})
    record = normalize(dict(name='Synthetic 3.7 V cell with unspecified limits', capacity_Ah=2.,
                            nominal_voltage_V=3.7, resistance_mohm=20.), 'custom_probe')
    bank = {'custom_probe': record}

    def setup(kind='parallel', count=1, current=1., duration=60.):
        graph = template(kind, count)
        for cell in graph['cells']:
            cell['model'] = 'custom_probe'
        settings = settings_default()
        settings['profile'] = [dict(start_s=0., end_s=duration, current_A=current)]
        settings['limits']['min_voltage_V'] = 3.3
        return graph, settings

    graph, settings = setup(current=8.)
    result = simulate(graph, settings, bank)
    receipt['cases']['missing_limits_sizing'] = dict(
        input=dict(model=record, graph=graph, settings=settings),
        actual=dict(status=result.status, sizing=sizing_verdict(result, {'ready': True}),
                    outcome=outcome(graph, settings, result), warnings=result.summary['design_warnings'],
                    metrics=result.summary['metrics'], checks=result.summary['checks'],
                    verification=result.summary['verification']),
        expected='Incomplete operating-limit assessment; never unqualified qualifying design')

    graph, settings = setup('series', 2, -1., 600.)
    result = simulate(graph, settings, bank)
    receipt['cases']['series_charge_ah'] = dict(
        input=dict(graph=graph, settings=settings),
        actual=result.summary['charging'],
        expected_pack_charge_received_Ah=1.*600./3600.,
        note='Summed cell Ah may be reported separately, but is not pack-input Ah')

    graph, settings = setup('parallel', 2, 2., 1.)
    for wire in graph['connections']:
        wire['resistance_mohm'] = 0.
    result = simulate(graph, settings, bank)
    receipt['cases']['ideal_link_unknown_as_zero'] = dict(
        input=dict(graph=graph, settings=settings),
        row_cell_current_A=result.rows[0]['cell_current_A'],
        row_wire_current_A=result.rows[0]['wire_current_A'],
        actual=result.summary['link_checks'],
        expected='Each unique link carries 1 A in this ladder, or report uncomputed current as null, not zero')

    lg_bank = load_additional(args.repo)
    graph, settings = setup('series', 2, 1., 1.)
    for cell in graph['cells']:
        cell['model'] = 'LG_M50T_ECN'
    result = simulate(graph, settings, lg_bank)
    parts = estimate(graph, lg_bank, load_prices(args.repo))
    receipt['cases']['count_only_parts'] = dict(
        input=dict(graph=graph, settings=settings), terminal_V=result.rows[0]['voltage_V'],
        actual=dict(lines=[row for row in parts['lines'] if row['slot'] in ('converter', 'protection')],
                    warnings=result.summary['design_warnings']),
        expected='Board compatibility unknown/incompatible for this series battery; no implied compatible board/protection')

    graph, settings = setup('parallel', 2, -3., 10.)
    for cell in graph['cells']:
        cell['model'] = 'LG_M50T_ECN'
    try:
        result = simulate(graph, settings, lg_bank)
        observed = dict(status=result.status, peak_cell_current_A=result.summary['metrics']['peak_cell_current_A'])
    except ValueError as exc:
        observed = dict(status='refused', reason=str(exc))
    receipt['cases']['board_three_amp_charging'] = dict(
        input=dict(graph=graph, settings=settings), actual=observed,
        expected='Refusal is correct under deployed cell rule; board charge compatibility must not be inferred from discharge pass',
        ideal_share_A=1.5, deployed_charge_limit_at_23C_A=1.455)

    graph, settings = setup('parallel', 2, 2., 5.)
    baseline = simulate(graph, settings, bank)
    shuffled = deepcopy(graph)
    shuffled['cells'].reverse()
    shuffled['connections'].reverse()
    permuted = simulate(shuffled, settings, bank)
    receipt['cases']['permutation_control'] = dict(
        baseline_voltage_V=baseline.rows[-1]['voltage_V'],
        permuted_voltage_V=permuted.rows[-1]['voltage_V'],
        maximum_voltage_difference_V=max(abs(a['voltage_V']-b['voltage_V']) for a,b in zip(baseline.rows,permuted.rows)),
        first_law_closed=baseline.summary['verification']['first_law_closed'],
        expected='Equivalent orderings preserve terminal response; first-law closes')

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(receipt, indent=2, allow_nan=False)+'\n', encoding='utf-8')
    print(json.dumps(dict(receipt=str(args.out), packages=packages,
                         sizing=receipt['cases']['missing_limits_sizing']['actual']['sizing'],
                         charge_ah=receipt['cases']['series_charge_ah']['actual']['charge_gained_Ah'],
                         board_charge=observed, order_error_V=receipt['cases']['permutation_control']['maximum_voltage_difference_V'])))


if __name__ == '__main__':
    main()
