"""Wiring rules, run by the same path as every simulation.

A short through wires alone blocks the test. Everything else is a warning saved
with the result: mixed cells can be solved, they just need a person to look.
"""
import numpy as np

CAPACITY_MISMATCH = .1
NEAR_ZERO_OUTPUT_V = .5
BACKWARD_RESPONSE_A = 1e-6


def groups(graph):
    """Terminals joined by any connection, whatever its resistance."""
    parent = {}
    def root(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]; x = parent[x]
        return x
    for w in graph['connections']:
        parent[root(w['a'])] = root(w['b'])
    return root


def check_self_short(graph):
    root = groups(graph)
    for c in graph['cells']:
        if root(c['id']+':p') == root(c['id']+':n'):
            raise ValueError(f'{c["name"]} has a short circuit: its two terminals are joined through connections alone. Remove the link that closes this path.')


def warning(rule, message, cells):
    return dict(rule=rule, severity='warning', message=message, cells=cells)


def parallel_pairs(graph):
    root = groups(graph); cells = graph['cells']
    return [(a, b) for i, a in enumerate(cells) for b in cells[i+1:]
            if root(a['id']+':p') == root(b['id']+':p') and root(a['id']+':n') == root(b['id']+':n')]


def operating_limit_coverage(graph, bank, rows):
    """Coverage of recorded limits for the directions each cell actually carried.

    Lookup support and application targets are not cell operating limits. A
    missing limit stays unknown, including charging caused by internal sharing.
    """
    from voltforge.models.cell_catalogue import CellModel
    entries = []
    for i, cell in enumerate(graph['cells']):
        model = CellModel(bank[cell['model']])
        limits = dict(model.record.get('operating_limits') or {})
        lg_rule = model.legacy or model.record.get('key') == 'LG_M50T_ECN'
        if lg_rule:
            # Same deployed temperature-dependent rules as CellModel; these
            # values describe coverage, and do not change the numerical model.
            limits.update(charge_temperature_C=[0., 45.], discharge_temperature_C=[-20., 55.])
            limits.setdefault('voltage_V', [2.5, 4.2])
        directions = [direction for direction, sign in (('discharge', 1.), ('charge', -1.))
                      if any(sign*row['cell_current_A'][i] > 1e-8 for row in rows)]
        missing = [] if limits.get('voltage_V') is not None else ['voltage_V']
        for direction in directions:
            if not lg_rule and limits.get('max_'+direction+'_A') is None:
                missing.append('max_'+direction+'_A')
            if limits.get(direction+'_temperature_C') is None:
                missing.append(direction+'_temperature_C')
        entries.append(dict(cell=cell['id'], directions=directions, complete=not missing,
                            missing=missing, limits=limits,
                            current_rule='Deployed LG temperature-dependent current limits' if lg_rule else 'Recorded cell limits',
                            basis='user_declared' if model.custom else 'deployed_model'))
    return dict(version='voltforge.operating-limit-coverage/1', complete=all(e['complete'] for e in entries), cells=entries,
                note='Coverage of recorded operating limits for calculated branch-current directions; not hardware certification.')


def review(graph, bank):
    """Warnings for one design. Call only on a circuit that already solves."""
    from voltforge.models.cell_catalogue import CellModel
    from .network import Circuit
    found = []
    names = {c['id']: c['name'] for c in graph['cells']}
    models = {c['id']: CellModel(bank[c['model']]) for c in graph['cells']}
    for a, b in parallel_pairs(graph):
        first, second = models[a['id']], models[b['id']]
        if a['model'] != b['model']:
            found.append(warning('mixed_parallel', f'{a["name"]} and {b["name"]} are different cell types in parallel. They will not share current evenly.', [a['id'], b['id']]))
        elif abs(first.capacity-second.capacity) > CAPACITY_MISMATCH*max(first.capacity, second.capacity):
            found.append(warning('mixed_parallel', f'{a["name"]} and {b["name"]} have different capacities in parallel.', [a['id'], b['id']]))
    for c in graph['cells']:
        limits = bank[c['model']].get('operating_limits') or {}
        if not models[c['id']].legacy and c['model'] != 'LG_M50T_ECN' and (limits.get('max_discharge_A') is None or limits.get('max_charge_A') is None):
            missing=[direction for direction in ('charge','discharge') if limits.get('max_'+direction+'_A') is None]
            found.append(warning('missing_limits', f'{c["name"]} has no '+ ' or '.join(missing)+' current limit on record. Tests using that direction have incomplete operating-limit coverage.', [c['id']]))
    states = {c['id']: models[c['id']].parameters(c['charge_pct']/100, c['temperature_C']) if models[c['id']].supported(c['charge_pct']/100, c['temperature_C']) else None for c in graph['cells']}
    if any(v is None for v in states.values()): return found
    emf = np.array([states[c['id']][0]-c['polarization_V'] for c in graph['cells']])
    resistance = np.array([states[c['id']][1] for c in graph['cells']])
    circuit = Circuit(graph, bank)
    rest, loaded = circuit.solve(emf, resistance, 0.), circuit.solve(emf, resistance, 1.)
    # The circuit is linear, so this difference is how each cell responds to load alone.
    response = loaded['current']-rest['current']
    backward = [c['id'] for c, value in zip(graph['cells'], response) if value < -BACKWARD_RESPONSE_A]
    if backward:
        found.append(warning('opposed_cell', ', '.join(names[i] for i in backward)+' is wired backwards: drawing power charges it instead of discharging it.', backward))
    if rest['terminal'] < 0:
        found.append(warning('reversed_output', f'The battery outputs are reversed: positive sits {-rest["terminal"]:.2f} V below negative.', []))
    elif rest['terminal'] < NEAR_ZERO_OUTPUT_V:
        found.append(warning('reversed_output', f'The output reads only {rest["terminal"]:.2f} V. Cells may be cancelling each other out.', []))
    for c, current in zip(graph['cells'], rest['current']):
        issue = models[c['id']].operating_error(c['temperature_C'], float(current), float(states[c['id']][0]))
        if issue and issue[0] in ('current_max', 'charge_current_max'):
            found.append(warning('circulating_current', f'{c["name"]} carries {abs(current):.1f} A with no load connected, because cells are pushing current through each other. {issue[1]}', [c['id']]))
    return found
