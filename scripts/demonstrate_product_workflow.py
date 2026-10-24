"""A0 -> declared rail edit -> stale A1 -> rerun -> compare -> export -> replay."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

import pandas as pd

from voltforge.project import Project, dispatch
from voltforge.project.service import destination, file_hash, read, verify_files, write_once

DEFAULT_OUT = Path('reports/product_integration_v1/demo')
EDIT = dict(target='connection', id='rail_p_1', property='resistance', value=.0005, unit='ohm',
    classification='assumed', source='Predeclared manual hypothetical p1-p2 segment alternative; feasibility and resistance unmeasured')


def demo(out=DEFAULT_OUT):
    out = destination(out)
    if (out / 'demo_result.json').exists():
        verify_files(out, read(out / 'demo_manifest.json')['artifacts'])
        project = Project(out / 'project')
        result = read(out / 'demo_result.json')
        if any(project.get_run(**x)['freshness'] != 'current' for x in result['selections']):
            raise ValueError('Stored demo uses earlier inputs/software; choose a fresh --out directory')
        print('Existing demonstration verified; preserved without rerunning. Use --out for a fresh reproduction.')
        print(json.dumps(result, indent=2))
        return result
    if out.exists():
        raise ValueError('Demo destination already exists without a completed manifest; choose a fresh --out')
    out.mkdir(parents=True)
    write_once(out / 'declaration.json', dict(baseline='Existing equal-SOC A0, 14.55 A for 360 s, dt 0.25 s',
        alternative=EDIT, comparison='identical operating conditions; one rail resistance change',
        interpretation='simulation comparison; not validated repair, ranking or battery-performance gain',
        requirements='minimum device voltage, excursion duration and source remain unset'))
    calls = []

    def call(operation, **arguments):
        request = dict(operation=operation, arguments=arguments)
        response = dispatch(out / 'project', request)
        number = len(calls) + 1
        write_once(out / 'examples' / f'{number:02d}_{operation}.json', dict(request=request, response=response))
        calls.append(dict(operation=operation, example=f'examples/{number:02d}_{operation}.json'))
        if response['status'] != 'ok':
            raise ValueError(response['error'])
        return response['result']

    a0 = call('load_reference')
    r0 = call('run', variant_id='A0', expected_revision=a0['revision_id'])
    a1 = call('create_variant', source_variant='A0', variant_id='A1', name='One hypothetical positive rail change', expected_revision=a0['revision_id'])
    call('validate_edit', variant_id='A1', edit=EDIT, expected_revision=a1['revision_id'])
    a1 = call('apply_edit', variant_id='A1', edit=EDIT, expected_revision=a1['revision_id'])
    inherited = call('get_run', variant_id='A1', run_id=r0['run_id'])
    assert inherited['freshness'] == 'outdated'
    r1 = call('run', variant_id='A1', expected_revision=a1['revision_id'])
    assert r0['execution_status'] == r1['execution_status'] == 'completed'
    call('update_display', display=dict(positions={'cell_1': [0, 0], 'cell_2': [120, 0], 'cell_3': [240, 0], 'cell_4': [360, 0]},
        camera={'zoom': 1.25}, selection=['rail_p_1']))
    current = call('get_run', variant_id='A1', run_id=r1['run_id'])
    assert current['freshness'] == 'current'
    call('series', variant_id='A1', run_id=r1['run_id'], component_id='cell_1', limit=2)
    selections = [{'variant_id': 'A0', 'run_id': r0['run_id']}, {'variant_id': 'A1', 'run_id': r1['run_id']}]
    comparison = call('compare', selections=selections)
    write_once(out / 'comparison.json', comparison)
    pd.DataFrame(comparison['ordered_results']).to_csv(out / 'comparison.csv', index=False)
    export = call('export', selections=selections, out=str(out / 'export'))
    replays = []
    for run in [r0, r1]:
        process = subprocess.run([sys.executable, '-B', str(out / 'export/replay.py'), run['run_id']],
            cwd=out, capture_output=True, text=True)
        if process.returncode:
            raise ValueError(process.stderr)
        replays.append(json.loads(process.stdout))
    # Actual error responses, captured through the same frontend contract.
    unsupported = dict(operation='run_thermal', arguments={})
    write_once(out / 'examples/unsupported.json', dict(request=unsupported, response=dispatch(out / 'project', unsupported)))
    failed_edit = dict(EDIT, value=-.001)
    invalid = dict(operation='validate_edit', arguments=dict(variant_id='A1', edit=failed_edit, expected_revision=a1['revision_id']))
    write_once(out / 'examples/invalid_edit.json', dict(request=invalid, response=dispatch(out / 'project', invalid)))
    result = dict(kind='simulation comparison', selections=selections, inherited_result_freshness=inherited['freshness'],
        visual_change_result_freshness=current['freshness'], comparison= comparison['ordered_results'],
        export=export, replays=replays, examples=calls, experimental_validation='awaiting suitable measurements')
    write_once(out / 'demo_result.json', result)
    comparison_plot(out, selections)
    # All artifacts excluding the manifest itself; bytecode is intentionally not exported.
    write_once(out / 'demo_manifest.json', dict(artifacts={p.relative_to(out).as_posix(): file_hash(p)
        for p in sorted(out.rglob('*')) if p.is_file()}))
    print(pd.DataFrame(comparison['ordered_results'])[['variant_id', 'maximum_branch_current_A', 'minimum_terminal_voltage_V', 'delivered_net_Wh', 'requirement']].to_string(index=False))
    print('Inherited A0 result on A1: outdated. Visual-only move after A1 run: current.')
    print('Export replays match. Simulation comparison only; experimental module validation awaits measurements.')
    return result


def comparison_plot(out, selections):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(2, 1, figsize=(10, 7), layout='constrained')
    colors = ['#0072B2', '#D55E00', '#009E73', '#CC79A7']
    for index, choice in enumerate(selections):
        f = pd.read_csv(out / 'project/runs' / choice['run_id'] / 'trajectory.csv')
        style = '-' if index == 0 else '--'
        axes[0].plot(f.time_s, f.terminal_V, style, color=['#263746', '#c15f22'][index], label=choice['variant_id'])
        for k, color in enumerate(colors, 1):
            axes[1].plot(f.time_s, f[f'I{k}_A'], style, color=color, label=f"{choice['variant_id']} cell {k}")
    axes[0].set_ylabel('Module terminal voltage [V]')
    axes[1].set_ylabel('Discharge-positive branch current [A]')
    for ax in axes:
        ax.set_xlabel('Time [s]')
        ax.grid(alpha=.2)
        ax.legend(ncol=4, fontsize=8)
    fig.suptitle('A0 vs A1: one hypothetical p1-p2 resistance change\nSame 14.55 A / 360 s case; simulation comparison, validation pending')
    fig.savefig(out / 'comparison.png', dpi=150)
    plt.close(fig)


def frontend_examples(out):
    """Publish complete compact request/response pairs from actual recorded calls."""
    out = Path(out)
    lines = ['# Generated frontend request/response examples', '',
        'Generated from the executed A0/A1 demonstration, not handwritten response fixtures.',
        'Revision/snapshot hashes bind this recorded demonstration; obtain current revision IDs from inspect before new edits.', '',
        'The complete response corpus (including inherited/outdated and completed runs) is in `demo/examples/`.', '']
    for name in ['04_validate_edit.json', '10_series.json', 'unsupported.json', 'invalid_edit.json']:
        pair = read(out / 'examples' / name)
        lines += ['## ' + name, '', 'Request:', '', '```json', json.dumps(pair['request'], indent=2), '```', '',
            'Response:', '', '```json', json.dumps(pair['response'], indent=2), '```', '']
    (out.parent / 'FRONTEND_EXAMPLES.md').write_text('\n'.join(lines), encoding='utf-8', newline='\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    demo(args.out)
    frontend_examples(args.out)
