"""Strict, deliberately small project/design schema and editor-to-solver mapping."""
import copy
import math

from voltforge.models.coupling_v2 import VoltageReference, validate_profile

SCHEMA = 'voltforge.project/1'
DESIGN_SCHEMA = 'voltforge.design/1'
SCHEMA_V2 = 'voltforge.project/2'
PROJECT_SCHEMAS = (SCHEMA, SCHEMA_V2)
DESIGN_SCHEMA_V2 = 'voltforge.design/2'
THERMAL_MODEL = 'lumped_four_node_v1'
ENGINEERING_LIMITS = {'peak_branch_current_A': 'A', 'current_imbalance_pct': '%', 'peak_cell_temperature_C': 'degC'}
ACTIVE_CURRENT_FLOOR_A = 0.5
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
    require(isinstance(q['classification'], str) and q['classification'] in CLASSIFICATIONS and isinstance(q['source'], str) and bool(q['source'].strip()), label + ': provenance required')
    require(low is None or q['value'] >= low, label + ': below mathematical lower bound')
    require(high is None or q['value'] <= high, label + ': above mathematical upper bound')


def reference_design(case, manifest, version=1, thermal=None):
    require(type(version) is int and version in (1, 2), 'Unsupported design schema', 'unsupported_request')
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
    design = dict(schema_version=DESIGN_SCHEMA, topology=TOPOLOGY,
        nodes=[f'{p}{k}' for p in ['p', 'n'] for k in range(1, 5)],
        terminals=dict(positive='p1', negative='n1', voltage_reference='n1'),
        cells=cells, connections=connections,
        scenario=dict(load_profile=copy.deepcopy(case['load']), load_unit='A', time_unit='s',
            current_polarity='discharge_positive', load_provenance=case['load_classification'],
            temperature=copy.deepcopy(case['temperature'])),
        simulation=dict(dt_s=case['dt_s'], reference_extrapolation='forbidden',
            permit_unvalidated_waveform_transfer=True, thermal_model=False),
        requirements=copy.deepcopy(case['requirements']))
    if version == 1:
        return design
    if version == 2:
        if thermal is None:
            raise RequestError('invalid_request', 'invalid_request')
        design = copy.deepcopy(design)
        design['schema_version'] = DESIGN_SCHEMA_V2
        design['thermal'] = {
            'model': THERMAL_MODEL,
            'coupling': 'one-way: electrical losses heat the cells; temperatures do not change the frozen electrical parameters',
            'reversible_heat': 'omitted',
            'initial_temperature': 'scenario.temperature.assumed_surface_C',
            'ambient_temperature': 'scenario.temperature.assumed_ambient_C',
            'heat_capacity_J_per_K': copy.deepcopy(thermal['heat_capacity_J_per_K']),
            'ambient_conductance_W_per_K': copy.deepcopy(thermal['ambient_conductance_W_per_K']),
            'neighbour_conductance_W_per_K': copy.deepcopy(thermal['neighbour_conductance_W_per_K']),
            'rail_heat_to_cells_fraction': copy.deepcopy(thermal['rail_heat_to_cells_fraction']),
        }
        design['engineering_requirements'] = {name: {'limit': None, 'unit': unit, 'documented_source': None} for name, unit in ENGINEERING_LIMITS.items()}
        design['engineering_requirements']['active_current_floor_A'] = ACTIVE_CURRENT_FLOOR_A
        return design
    raise RequestError('unsupported_request', 'Unsupported design schema')


def _check_quantity_list(q, unit, label, expected_len, low=None, high=None, allow_zero=False):
    keys(q, ['value', 'unit', 'classification', 'source'], label)
    require(q['unit'] == unit, label + ': finite value and unit ' + unit + ' required')
    require(isinstance(q['classification'], str) and q['classification'] in CLASSIFICATIONS and isinstance(q['source'], str) and bool(q['source'].strip()), label + ': provenance required')
    require(isinstance(q['value'], list) and len(q['value']) == expected_len, label + ': list required')
    for v in q['value']:
        require(finite(v) and type(v) is not bool, label + ': finite value required')
        if low is not None:
            require(v >= low, label + ': below mathematical lower bound')
        if high is not None:
            require(v <= high, label + ': above mathematical upper bound')
    return


def validate_design(design, base, manifest):
    require(isinstance(design, dict), 'Unexpected or missing fields: design')
    schema_version = design.get('schema_version')
    if schema_version == DESIGN_SCHEMA:
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
    elif schema_version == DESIGN_SCHEMA_V2:
        expected_v1 = reference_design(base, manifest)
        # run same checks on every v1 part
        keys(design, set(expected_v1) | {'thermal', 'engineering_requirements'}, 'design')
        require(design['schema_version'] == DESIGN_SCHEMA_V2, 'Only the fixed same-side 1s4p nodes/terminals are supported', 'unsupported_request')
        for key in ['topology', 'nodes', 'terminals']:
            require(design[key] == expected_v1[key], 'Only the fixed same-side 1s4p nodes/terminals are supported', 'unsupported_request')
        keys(design['cells'], expected_v1['cells'], 'cells')
        keys(design['connections'], expected_v1['connections'], 'connections')
        for k, (cid, c) in enumerate(design['cells'].items()):
            keys(c, expected_v1['cells'][cid], cid)
            for key in set(c) - {'initial_soc', 'initial_polarization'}:
                require(c[key] == expected_v1['cells'][cid][key], cid + ': cell identity, terminals and sealed model are read-only', 'unsupported_request')
            check_quantity(c['initial_soc'], 'fraction', cid + '.initial_soc', 0, 1)
            check_quantity(c['initial_polarization'], 'V', cid + '.initial_polarization')
            index = int(cid.split('_')[1])-1
            require(VoltageReference(base['models'][index]).supported(c['initial_soc']['value']), cid + ': initial SOC outside reference support')
        for cid, c in design['connections'].items():
            keys(c, expected_v1['connections'][cid], cid)
            for key in set(c) - {'resistance'}:
                require(c[key] == expected_v1['connections'][cid][key], 'Unsupported rewiring: ' + cid, 'unsupported_request')
            check_quantity(c['resistance'], 'ohm', cid + '.resistance', 0)
        s = design['scenario']
        keys(s, expected_v1['scenario'], 'scenario')
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
        keys(t, expected_v1['scenario']['temperature'], 'temperature')
        require(t['thermal_model'] is False and t['parameter_temperature_scaling'] is False, 'Thermal simulation and temperature laws are unavailable', 'unsupported_request')
        require(finite(t['assumed_ambient_C']) and isinstance(t['assumed_surface_C'], list) and len(t['assumed_surface_C']) == 4
                and all(finite(x) for x in t['assumed_surface_C']), 'Four finite surface assumptions and ambient temperature required')
        require(isinstance(t['evidence'], str) and bool(t['evidence'].strip()), 'Temperature evidence required')
        n = design['simulation']
        keys(n, expected_v1['simulation'], 'simulation')
        require(n['reference_extrapolation'] == 'forbidden' and n['permit_unvalidated_waveform_transfer'] is True
                and n['thermal_model'] is False, 'Only explicitly permitted electrical waveform investigation without extrapolation is supported', 'unsupported_request')
        require(finite(n['dt_s']) and n['dt_s'] >= 1e-6 and duration/n['dt_s'] <= 1000000,
                'dt_s must be >= 1e-6 and the run must contain <= 1000000 nominal steps')
        r = design['requirements']
        keys(r, expected_v1['requirements'], 'requirements')
        for key in ['minimum_terminal_voltage_V', 'maximum_contiguous_excursion_s']:
            require(r[key] is None or (finite(r[key]) and r[key] >= 0), 'Requirements must be null or finite nonnegative values')
        require(r['minimum_terminal_voltage_V'] is None or r['minimum_terminal_voltage_V'] > 0, 'Minimum voltage must be positive')
        require(r['documented_source'] is None or (isinstance(r['documented_source'], str) and bool(r['documented_source'].strip())), 'Requirement source must be null or a nonempty string')
        # thermal
        thermal = design['thermal']
        thermal_keys = ['model', 'coupling', 'reversible_heat', 'initial_temperature', 'ambient_temperature',
                        'heat_capacity_J_per_K', 'ambient_conductance_W_per_K', 'neighbour_conductance_W_per_K', 'rail_heat_to_cells_fraction']
        keys(thermal, thermal_keys, 'thermal')
        require(thermal['model'] == THERMAL_MODEL, 'Unsupported design schema', 'unsupported_request')
        require(thermal['coupling'] == 'one-way: electrical losses heat the cells; temperatures do not change the frozen electrical parameters', 'Unsupported design schema', 'unsupported_request')
        require(thermal['reversible_heat'] == 'omitted', 'Unsupported design schema', 'unsupported_request')
        require(thermal['initial_temperature'] == 'scenario.temperature.assumed_surface_C', 'Unsupported design schema', 'unsupported_request')
        require(thermal['ambient_temperature'] == 'scenario.temperature.assumed_ambient_C', 'Unsupported design schema', 'unsupported_request')
        _check_quantity_list(thermal['heat_capacity_J_per_K'], 'J/K', 'thermal.heat_capacity_J_per_K', 4, low=0)
        require(all(x > 0 for x in thermal['heat_capacity_J_per_K']['value']), 'thermal.heat_capacity_J_per_K: heat capacity must be positive')
        _check_quantity_list(thermal['ambient_conductance_W_per_K'], 'W/K', 'thermal.ambient_conductance_W_per_K', 4, low=0)
        _check_quantity_list(thermal['neighbour_conductance_W_per_K'], 'W/K', 'thermal.neighbour_conductance_W_per_K', 3, low=0)
        rq = thermal['rail_heat_to_cells_fraction']
        keys(rq, ['value', 'unit', 'classification', 'source'], 'thermal.rail_heat_to_cells_fraction')
        require(rq['unit'] == 'fraction', 'thermal.rail_heat_to_cells_fraction: finite value and unit fraction required')
        require(isinstance(rq['classification'], str) and rq['classification'] in CLASSIFICATIONS and isinstance(rq['source'], str) and bool(rq['source'].strip()), 'thermal.rail_heat_to_cells_fraction: provenance required')
        require(finite(rq['value']) and type(rq['value']) is not bool and 0 <= rq['value'] <= 1, 'thermal.rail_heat_to_cells_fraction: finite value required')
        # engineering requirements
        er = design['engineering_requirements']
        er_keys = ['peak_branch_current_A', 'current_imbalance_pct', 'peak_cell_temperature_C', 'active_current_floor_A']
        keys(er, er_keys, 'engineering_requirements')
        require(er['active_current_floor_A'] == ACTIVE_CURRENT_FLOOR_A, 'Unsupported design schema', 'unsupported_request')
        for name, unit in ENGINEERING_LIMITS.items():
            e = er[name]
            keys(e, ['limit', 'unit', 'documented_source'], 'engineering_requirements.' + name)
            require(e['unit'] == unit, 'engineering_requirements.' + name)
            if e['limit'] is not None:
                require(finite(e['limit']) and type(e['limit']) is not bool, 'engineering_requirements.' + name)
                require(isinstance(e['documented_source'], str) and bool(e['documented_source'].strip()), 'engineering_requirements.' + name + ': configured limit needs a documented source')
                if name in ['peak_branch_current_A', 'current_imbalance_pct']:
                    require(e['limit'] > 0, 'engineering_requirements.' + name)
            if e['documented_source'] is not None:
                require(isinstance(e['documented_source'], str) and bool(e['documented_source'].strip()), 'engineering_requirements.' + name)
        return design
    else:
        raise RequestError('unsupported_request', 'Unsupported design schema')


EDITABLE = [
    dict(target='connection', property='resistance', unit='ohm', ids=[f'rail_{p}_{k}' for p in ['p', 'n'] for k in range(1, 4)], meaning='Exploratory effective segment resistance, including represented contacts; no geometry rule'),
    dict(target='cell', property='initial_soc', unit='fraction', ids=[f'cell_{k}' for k in range(1, 5)], meaning='Relative to fixed rested-reference coordinate; not a measured SOC'),
    dict(target='cell', property='initial_polarization', unit='V', ids=[f'cell_{k}' for k in range(1, 5)], meaning='Explicit initial RC state assumption'),
    dict(target='scenario', property='load_profile', unit='A,s', ids=['module'], meaning='Contiguous piecewise constant current, discharge positive'),
    dict(target='scenario', property='temperature', unit='degC', ids=['module'], meaning='Assumed ambient/surface metadata; no thermal evolution or parameter scaling'),
    dict(target='simulation', property='dt_s', unit='s', ids=['module'], meaning='Maximum held-current integration step'),
    dict(target='requirements', property='voltage_requirement', unit='V,s', ids=['module'], meaning='Minimum voltage, maximum contiguous excursion and source; null means unconfigured'),
]

EDITABLE_V2 = EDITABLE + [
    dict(target='thermal', property='heat_capacity', unit='J/K', ids=['module'], meaning='Thermal model values are declared assumptions; edited values replace the assumptions with explicit provenance'),
    dict(target='thermal', property='ambient_conductance', unit='W/K', ids=['module'], meaning='Thermal model values are declared assumptions; edited values replace the assumptions with explicit provenance'),
    dict(target='thermal', property='neighbour_conductance', unit='W/K', ids=['module'], meaning='Thermal model values are declared assumptions; edited values replace the assumptions with explicit provenance'),
    dict(target='thermal', property='rail_heat_to_cells_fraction', unit='fraction', ids=['module'], meaning='Thermal model values are declared assumptions; edited values replace the assumptions with explicit provenance'),
    dict(target='engineering_requirements', property='peak_branch_current', unit='A', ids=['module'], meaning='Engineering limit; a documented source is required and null clears the limit'),
    dict(target='engineering_requirements', property='current_imbalance', unit='%', ids=['module'], meaning='Engineering limit; a documented source is required and null clears the limit'),
    dict(target='engineering_requirements', property='peak_cell_temperature', unit='degC', ids=['module'], meaning='Engineering limit; a documented source is required and null clears the limit'),
]


def editable_catalogue(design):
    if design['schema_version'] == DESIGN_SCHEMA_V2:
        return EDITABLE_V2
    return EDITABLE


def edited(design, edit, base, manifest):
    keys(edit, ['target', 'id', 'property', 'value', 'unit', 'source', 'classification'], 'edit')
    catalogue = editable_catalogue(design)
    matches = [p for p in catalogue if p['target'] == edit['target'] and p['property'] == edit['property'] and edit['id'] in p['ids']]
    require(bool(matches), 'Unsupported target/property; fitted parameters, identity and topology are read-only', 'unsupported_request')
    require(edit['unit'] == matches[0]['unit'], 'Unsupported edit unit')
    require(isinstance(edit['classification'], str) and edit['classification'] in CLASSIFICATIONS and isinstance(edit['source'], str) and bool(edit['source'].strip()), 'Explicit edit provenance required')
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
    elif target == 'thermal':
        if prop == 'heat_capacity':
            out['thermal']['heat_capacity_J_per_K'] = quantity(value, edit['unit'], edit['source'], edit['classification'])
        elif prop == 'ambient_conductance':
            out['thermal']['ambient_conductance_W_per_K'] = quantity(value, edit['unit'], edit['source'], edit['classification'])
        elif prop == 'neighbour_conductance':
            out['thermal']['neighbour_conductance_W_per_K'] = quantity(value, edit['unit'], edit['source'], edit['classification'])
        elif prop == 'rail_heat_to_cells_fraction':
            out['thermal']['rail_heat_to_cells_fraction'] = quantity(value, edit['unit'], edit['source'], edit['classification'])
    elif target == 'engineering_requirements':
        if prop == 'peak_branch_current':
            name = 'peak_branch_current_A'
        elif prop == 'current_imbalance':
            name = 'current_imbalance_pct'
        elif prop == 'peak_cell_temperature':
            name = 'peak_cell_temperature_C'
        else:
            require(False, 'Unsupported target/property; fitted parameters, identity and topology are read-only', 'unsupported_request')
        require(isinstance(value, dict) and set(value.keys()) == {'limit', 'documented_source'}, 'Unexpected or missing fields: engineering_requirements')
        out['engineering_requirements'][name] = {'limit': value['limit'], 'unit': ENGINEERING_LIMITS[name], 'documented_source': value['documented_source']}
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


def thermal_parameters(design):
    if design.get('schema_version') != DESIGN_SCHEMA_V2:
        return None
    t = design['thermal']
    sources = [
        t['heat_capacity_J_per_K']['source'],
        t['ambient_conductance_W_per_K']['source'],
        t['neighbour_conductance_W_per_K']['source'],
        t['rail_heat_to_cells_fraction']['source'],
    ]
    return {
        'heat_capacity_J_per_K': list(t['heat_capacity_J_per_K']['value']),
        'ambient_conductance_W_per_K': list(t['ambient_conductance_W_per_K']['value']),
        'neighbour_conductance_W_per_K': list(t['neighbour_conductance_W_per_K']['value']),
        'rail_heat_to_cells_fraction': float(t['rail_heat_to_cells_fraction']['value']),
        'provenance': '; '.join(sources),
    }


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
