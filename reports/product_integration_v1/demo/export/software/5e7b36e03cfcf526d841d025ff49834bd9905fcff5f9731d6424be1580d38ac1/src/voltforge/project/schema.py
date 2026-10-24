"""Strict, deliberately small project/design schema and editor-to-solver mapping."""
import copy
import math

from voltforge.models.coupling_v2 import VoltageReference, validate_profile

SCHEMA = 'voltforge.project/1'
DESIGN_SCHEMA = 'voltforge.design/1'
CELLS = ['P7', 'P17', 'P19', 'P13']
TOPOLOGY = '1s4p same-side-terminal ladder'
CLASSIFICATIONS = {'assumed', 'proposed_requirement', 'user_declared_measurement'}


class RequestError(ValueError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def require(condition, message, code='invalid_request'):
    if not condition:
        raise RequestError(code, message)


def keys(obj, names, label):
    require(isinstance(obj, dict) and set(obj) == set(names), 'Unexpected or missing fields: ' + label)


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def quantity(value, unit, source, classification='assumed'):
    return dict(value=value, unit=unit, classification=classification, source=source)


def check_quantity(q, unit, label, low=None, high=None):
    keys(q, ['value', 'unit', 'classification', 'source'], label)
    require(q['unit'] == unit and finite(q['value']), label + ': finite value and unit ' + unit + ' required')
    require(q['classification'] in CLASSIFICATIONS and isinstance(q['source'], str) and bool(q['source'].strip()), label + ': provenance required')
    require(low is None or q['value'] >= low, label + ': below mathematical lower bound')
    require(high is None or q['value'] <= high, label + ': above mathematical upper bound')


def reference_design(case, manifest):
    cells = {}
    for k, cell in enumerate(CELLS, 1):
        cells[f'cell_{k}'] = dict(id=f'cell_{k}', type='cell', identity=cell, part='LG M50T',
            chemistry='NMC', positive_node=f'p{k}', negative_node=f'n{k}',
            model=dict(version='frozen-v2', key='C2_rest_reference_RC', **manifest['model_sources'][cell]),
            initial_soc=quantity(case['initial_soc'][k-1], 'fraction', case['initial_state_evidence']),
            initial_polarization=quantity(case['initial_polarization_V'][k-1], 'V', case['initial_state_evidence']))
    connections = {}
    for rail, prefix in [('positive', 'p'), ('negative', 'n')]:
        for k in range(1, 4):
            cid = f'rail_{prefix}_{k}'
            connections[cid] = dict(id=cid, type='rail_segment', rail=rail,
                node_a=f'{prefix}{k}', node_b=f'{prefix}{k+1}',
                resistance=quantity(case[f'{rail}_rail_ohm'][k-1], 'ohm', case['rail_evidence']))
    return dict(schema_version=DESIGN_SCHEMA, topology=TOPOLOGY,
        nodes=[f'{p}{k}' for p in ['p', 'n'] for k in range(1, 5)],
        terminals=dict(positive='p1', negative='n1', voltage_reference='n1'),
        cells=cells, connections=connections,
        scenario=dict(load_profile=copy.deepcopy(case['load']), load_unit='A', time_unit='s',
            current_polarity='discharge_positive', load_provenance=case['load_classification'],
            temperature=copy.deepcopy(case['temperature'])),
        simulation=dict(dt_s=case['dt_s'], reference_extrapolation='forbidden',
            permit_unvalidated_waveform_transfer=True, thermal_model=False),
        requirements=copy.deepcopy(case['requirements']))


def validate_design(design, base, manifest):
    expected = reference_design(base, manifest)
    keys(design, expected, 'design')
    for key in ['schema_version', 'topology', 'nodes', 'terminals']:
        require(design[key] == expected[key], 'Only the fixed same-side 1s4p nodes/terminals are supported', 'unsupported_request')
    keys(design['cells'], expected['cells'], 'cells')
    keys(design['connections'], expected['connections'], 'connections')
    for k, (cid, c) in enumerate(design['cells'].items()):
        keys(c, expected['cells'][cid], cid)
        for key in set(c) - {'initial_soc', 'initial_polarization'}:
            require(c[key] == expected['cells'][cid][key], cid + ': cell identity, terminals and sealed model are read-only', 'unsupported_request')
        check_quantity(c['initial_soc'], 'fraction', cid + '.initial_soc', 0, 1)
        check_quantity(c['initial_polarization'], 'V', cid + '.initial_polarization')
        index = int(cid.split('_')[1])-1
        require(VoltageReference(base['models'][index]).supported(c['initial_soc']['value']), cid + ': initial SOC outside reference support')
    for cid, c in design['connections'].items():
        keys(c, expected['connections'][cid], cid)
        for key in set(c) - {'resistance'}:
            require(c[key] == expected['connections'][cid][key], 'Unsupported rewiring: ' + cid, 'unsupported_request')
        check_quantity(c['resistance'], 'ohm', cid + '.resistance', 0)
    s = design['scenario']
    keys(s, expected['scenario'], 'scenario')
    require((s['load_unit'], s['time_unit'], s['current_polarity']) == ('A', 's', 'discharge_positive'), 'Unsupported load units/polarity')
    require(isinstance(s['load_provenance'], str) and bool(s['load_provenance'].strip()), 'Load provenance required')
    require(isinstance(s['load_profile'], list), 'Load profile must be an array')
    for step in s['load_profile']:
        keys(step, ['start_s', 'end_s', 'current_A'], 'load interval')
        require(all(finite(x) for x in step.values()), 'Load intervals require finite numeric values')
    try:
        duration = validate_profile(s['load_profile'])
    except (TypeError, ValueError) as exc:
        raise RequestError('invalid_request', str(exc)) from exc
    t = s['temperature']
    keys(t, expected['scenario']['temperature'], 'temperature')
    require(t['thermal_model'] is False and t['parameter_temperature_scaling'] is False, 'Thermal simulation and temperature laws are unavailable', 'unsupported_request')
    require(finite(t['assumed_ambient_C']) and isinstance(t['assumed_surface_C'], list) and len(t['assumed_surface_C']) == 4
            and all(finite(x) for x in t['assumed_surface_C']), 'Four finite surface assumptions and ambient temperature required')
    require(isinstance(t['evidence'], str) and bool(t['evidence'].strip()), 'Temperature evidence required')
    n = design['simulation']
    keys(n, expected['simulation'], 'simulation')
    require(n['reference_extrapolation'] == 'forbidden' and n['permit_unvalidated_waveform_transfer'] is True
            and n['thermal_model'] is False, 'Only explicitly permitted electrical waveform investigation without extrapolation is supported', 'unsupported_request')
    require(finite(n['dt_s']) and n['dt_s'] >= 1e-6 and duration/n['dt_s'] <= 1000000,
            'dt_s must be >= 1e-6 and the run must contain <= 1000000 nominal steps')
    r = design['requirements']
    keys(r, expected['requirements'], 'requirements')
    for key in ['minimum_terminal_voltage_V', 'maximum_contiguous_excursion_s']:
        require(r[key] is None or (finite(r[key]) and r[key] >= 0), 'Requirements must be null or finite nonnegative values')
    require(r['minimum_terminal_voltage_V'] is None or r['minimum_terminal_voltage_V'] > 0, 'Minimum voltage must be positive')
    require(r['documented_source'] is None or (isinstance(r['documented_source'], str) and bool(r['documented_source'].strip())), 'Requirement source must be null or a nonempty string')
    return design


EDITABLE = [
    dict(target='connection', property='resistance', unit='ohm', ids=[f'rail_{p}_{k}' for p in ['p', 'n'] for k in range(1, 4)], meaning='Exploratory effective segment resistance, including represented contacts; no geometry rule'),
    dict(target='cell', property='initial_soc', unit='fraction', ids=[f'cell_{k}' for k in range(1, 5)], meaning='Relative to fixed rested-reference coordinate; not a measured SOC'),
    dict(target='cell', property='initial_polarization', unit='V', ids=[f'cell_{k}' for k in range(1, 5)], meaning='Explicit initial RC state assumption'),
    dict(target='scenario', property='load_profile', unit='A,s', ids=['module'], meaning='Contiguous piecewise constant current, discharge positive'),
    dict(target='scenario', property='temperature', unit='degC', ids=['module'], meaning='Assumed ambient/surface metadata; no thermal evolution or parameter scaling'),
    dict(target='simulation', property='dt_s', unit='s', ids=['module'], meaning='Maximum held-current integration step'),
    dict(target='requirements', property='voltage_requirement', unit='V,s', ids=['module'], meaning='Minimum voltage, maximum contiguous excursion and source; null means unconfigured'),
]


def edited(design, edit, base, manifest):
    keys(edit, ['target', 'id', 'property', 'value', 'unit', 'source', 'classification'], 'edit')
    matches = [p for p in EDITABLE if p['target'] == edit['target'] and p['property'] == edit['property'] and edit['id'] in p['ids']]
    require(bool(matches), 'Unsupported target/property; fitted parameters, identity and topology are read-only', 'unsupported_request')
    require(edit['unit'] == matches[0]['unit'], 'Unsupported edit unit')
    require(edit['classification'] in CLASSIFICATIONS and isinstance(edit['source'], str) and bool(edit['source'].strip()), 'Explicit edit provenance required')
    out = copy.deepcopy(design)
    target, prop, value = edit['target'], edit['property'], copy.deepcopy(edit['value'])
    if target in ['cell', 'connection']:
        out['cells' if target == 'cell' else 'connections'][edit['id']][prop] = quantity(value, edit['unit'], edit['source'], edit['classification'])
    elif target == 'scenario':
        out['scenario'][prop] = value
        if prop == 'load_profile':
            out['scenario']['load_provenance'] = edit['classification'] + ': ' + edit['source']
        elif isinstance(value, dict):
            value['evidence'] = edit['classification'] + ': ' + edit['source']
    elif target == 'simulation':
        out['simulation']['dt_s'] = value
    elif target == 'requirements':
        out['requirements'] = value
    return validate_design(out, base, manifest)


def to_case(design, base, scenario_id, sensitivities):
    c = copy.deepcopy(base)
    for key, prop in [('initial_soc', 'initial_soc'), ('initial_polarization_V', 'initial_polarization')]:
        c[key] = [design['cells'][f'cell_{k}'][prop]['value'] for k in range(1, 5)]
    for rail, prefix in [('positive', 'p'), ('negative', 'n')]:
        c[rail + '_rail_ohm'] = [design['connections'][f'rail_{prefix}_{k}']['resistance']['value'] for k in range(1, 4)]
    c['load'] = copy.deepcopy(design['scenario']['load_profile'])
    c['temperature'] = copy.deepcopy(design['scenario']['temperature'])
    c['requirements'] = copy.deepcopy(design['requirements'])
    c['dt_s'] = design['simulation']['dt_s']
    c['id'] = scenario_id
    c['run_type'] = 'manual simulation comparison'
    if scenario_id != 'nominal':
        options = {s['id']: s for s in sensitivities}
        require(scenario_id in options, 'Unknown sensitivity; only the seven declared one-at-a-time scenarios are supported', 'unsupported_request')
        change = copy.deepcopy(options[scenario_id])
        c['initial_soc'] = [v + change.get('soc_delta', 0) for v in c['initial_soc']]
        c['initial_polarization_V'] = [v + change.get('polarization_delta_V', 0) for v in c['initial_polarization_V']]
        c['capacity_factor'] = change.get('capacity_factor', 1.)
        c['reference_kind'] = change.get('reference', 'sealed_rest_pchip')
        c.update(sensitivity=change, run_type='sensitivity scenario')
    return c


def operating_conditions(case):
    return {key: copy.deepcopy(case[key]) for key in ['cell_order', 'models', 'initial_soc', 'initial_polarization_V',
        'load', 'temperature', 'requirements', 'dt_s', 'reference_kind', 'capacity_factor', 'origin_shift']}


def output_channels(component):
    """Public names map exactly to existing solver CSV columns; no inferred outputs."""
    common = {'time_s': ('time_s', 's')}
    if component == 'module':
        names = {'current_A': ('module_current_A', 'A'), 'terminal_V': ('terminal_V', 'V'),
            'power_W': ('terminal_power_W', 'W'), 'delivered_net_Wh': ('delivered_net_Wh', 'Wh'),
            'received_Wh': ('received_Wh', 'Wh'), 'delivered_positive_Wh': ('delivered_positive_Wh', 'Wh'),
            'charge_As': ('module_charge_As', 'A s'), 'cell_R0_loss_W': ('cell_R0_loss_W', 'W'),
            'rail_loss_W': ('rail_loss_W', 'W'), 'polarization_R1_loss_W': ('polarization_R1_loss_W', 'W'),
            'R0_and_rail_loss_Wh': ('R0_and_rail_loss_Wh', 'Wh'), 'R1_loss_Wh': ('R1_loss_Wh', 'Wh'),
            'kcl_residual_A': ('kcl_residual_A', 'A'), 'charge_balance_As': ('charge_balance_As', 'A s')}
    elif component in [f'cell_{k}' for k in range(1, 5)]:
        k = int(component[-1])
        names = {'current_A': (f'I{k}_A', 'A'), 'voltage_V': (f'V{k}_V', 'V'), 'soc': (f'SOC{k}', 'fraction'),
            'polarization_V': (f'polarization{k}_V', 'V'), 'reference_V': (f'reference{k}_V', 'V'),
            'positive_node_V': (f'positive_node{k}_V', 'V'), 'negative_node_V': (f'negative_node{k}_V', 'V'),
            'R0_loss_W': (f'R0_loss{k}_W', 'W'), 'R1_loss_W': (f'R1_loss{k}_W', 'W')}
    elif component in [f'rail_{p}_{k}' for p in ['p', 'n'] for k in range(1, 4)]:
        _, prefix, k = component.split('_')
        rail = 'positive' if prefix == 'p' else 'negative'
        names = {'current_A': (f'rail{k}_current_A', 'A'), 'voltage_drop_V': (f'{rail}_rail{k}_drop_V', 'V'),
            'loss_W': (f'{rail}_rail{k}_loss_W', 'W')}
    else:
        raise RequestError('unsupported_request', 'Unknown component or unavailable output domain')
    return common | names
