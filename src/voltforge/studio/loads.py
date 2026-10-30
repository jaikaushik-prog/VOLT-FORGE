"""Load presets and the versioned mission a design is tested against.

A preset fills in the test and records where each value came from. The solver
holds battery current constant, so a power load is converted at the voltage
floor, where a constant-power converter would draw the most current.
"""
from copy import deepcopy

from .cases import validate_case

VERSION = 'voltforge.mission/1'
TEST_TYPES = ('discharge', 'charge', 'custom')
BASES = ('sourced', 'assumed', 'custom')
PI_SUPPLY_URL = 'https://www.raspberrypi.com/products/raspberry-pi-5/'
# Requirement key -> how to read its live value back from test settings.
LIVE = {'load_current_A': lambda s: abs(s['profile'][0]['current_A']) if len(s['profile']) == 1 else None,
        'duration_s': lambda s: s['profile'][-1]['end_s'],
        'voltage_floor_V': lambda s: s['limits']['min_voltage_V'],
        'ambient_C': lambda s: s['ambient_C']}
ROUNDING = 1e-9


def requirement(key, label, value, unit, basis, reason, source_url=None):
    row = dict(key=key, label=label, value=value, unit=unit, basis=basis, reason=reason)
    if source_url: row['source_url'] = source_url
    return row


def battery_current(power_W, efficiency, voltage_floor_V):
    return power_W/(efficiency*voltage_floor_V)


def pi5_gateway_backup():
    power, efficiency, floor = 25., .9, 3.3
    current = battery_current(power, efficiency, floor)
    case = dict(name='Raspberry Pi 5 gateway backup', purpose='Keep a Raspberry Pi 5 monitoring gateway running through a short power cut.',
                source='5 V, 5 A supply recommendation from Raspberry Pi. Converter efficiency, run time, voltage limit and room temperature are study assumptions.')
    return dict(case=case, load=dict(kind='power', power_W=power, converter_efficiency=efficiency, current_A=current), requirements=[
        requirement('device_power_W', 'Pi supply power', power, 'W', 'sourced', 'The 5 V, 5 A recommended supply, an upper envelope and not a measured draw.', PI_SUPPLY_URL),
        requirement('converter_efficiency', 'Converter efficiency', efficiency, 'ratio', 'assumed', 'Typical assumption for a boost converter. Not a selected part yet.'),
        requirement('load_current_A', 'Battery current', current, 'A', 'assumed', 'Power divided by efficiency and the voltage limit. Held constant as an approximation.'),
        requirement('duration_s', 'Run time', 600., 's', 'assumed', 'Covers a short outage or a safe shutdown.'),
        requirement('voltage_floor_V', 'Lowest battery voltage', floor, 'V', 'assumed', 'Declared minimum at the converter input.'),
        requirement('ambient_C', 'Room temperature', 23., '°C', 'assumed', 'Declared study condition.')])


def stress_12a():
    case = dict(name='12 A stress test', purpose='Push the design harder than the gateway needs, to see where it runs out of margin.',
                source='Declared benchmark. 12 A did not come from a device requirement.')
    return dict(case=case, load=dict(kind='current', current_A=12.), requirements=[
        requirement('load_current_A', 'Battery current', 12., 'A', 'assumed', 'Declared stress level.'),
        requirement('duration_s', 'Run time', 600., 's', 'assumed', 'Declared study condition.'),
        requirement('voltage_floor_V', 'Lowest battery voltage', 3.3, 'V', 'assumed', 'Declared study condition.'),
        requirement('ambient_C', 'Room temperature', 23., '°C', 'assumed', 'Declared study condition.')])


PRESETS = dict(pi5_gateway_backup=pi5_gateway_backup, stress_12a=stress_12a)


def custom(name, load, duration_s, voltage_floor_V, ambient_C):
    case = dict(name=name or 'Custom load', purpose='A load defined by the person running this test.', source='User-defined load and targets; no independent source supplied.')
    reason = 'Entered during setup.'
    rows = [requirement('load_current_A', 'Battery current', load['current_A'], 'A', 'custom', reason),
            requirement('duration_s', 'Run time', duration_s, 's', 'custom', reason),
            requirement('ambient_C', 'Room temperature', ambient_C, '°C', 'custom', reason)]
    if load['kind'] == 'power':
        rows[:0] = [requirement('device_power_W', 'Load power', load['power_W'], 'W', 'custom', reason),
                    requirement('converter_efficiency', 'Converter efficiency', load['converter_efficiency'], 'ratio', 'custom', reason)]
    if voltage_floor_V is not None:
        rows.insert(-1, requirement('voltage_floor_V', 'Lowest battery voltage', voltage_floor_V, 'V', 'custom', reason))
    return dict(case=case, load=load, requirements=rows)


def build_mission(test_type='discharge', preset='custom_amps', name=None, current_A=None, power_W=None, efficiency=None,
                  duration_s=None, voltage_floor_V=None, ambient_C=None):
    from .network import number
    if test_type not in TEST_TYPES: raise ValueError('Choose a discharge, charge or custom test.')
    if preset in PRESETS:
        if test_type != 'discharge': raise ValueError('These load presets are discharge tests. Use a custom load for charging.')
        body = PRESETS[preset]()
    elif preset in ('custom_amps', 'custom_watts'):
        duration = number(600. if duration_s is None else duration_s, 'Run time', .1, 86400)
        ambient = number(23. if ambient_C is None else ambient_C, 'Room temperature', -40, 100)
        floor = None if voltage_floor_V is None else number(voltage_floor_V, 'Lowest battery voltage', .1, 1000)
        if preset == 'custom_amps':
            load = dict(kind='current', current_A=number(current_A, 'Battery current', .001, 200))
        else:
            if floor is None: raise ValueError('A power load needs a lowest battery voltage to set its current.')
            power = number(power_W, 'Load power', .001, 100000); eff = number(.9 if efficiency is None else efficiency, 'Converter efficiency', .01, 1)
            load = dict(kind='power', power_W=power, converter_efficiency=eff, current_A=number(battery_current(power, eff, floor), 'Battery current', .001, 200))
        body = custom(name, load, duration, floor, ambient)
    else:
        raise ValueError('Choose a load preset or a custom load.')
    return dict(version=VERSION, preset=preset, test_type=test_type, **body)


def apply_mission(settings, mission):
    """Write the mission into test settings. Everything stays editable afterwards."""
    validate_mission(mission)
    values = {r['key']: r['value'] for r in mission['requirements']}
    sign = -1. if mission['test_type'] == 'charge' else 1.
    settings['profile'] = [dict(start_s=0., end_s=values['duration_s'], current_A=sign*values['load_current_A'])]
    settings['ambient_C'] = values['ambient_C']
    settings['limits']['min_voltage_V'] = values.get('voltage_floor_V')
    settings['case'] = deepcopy(mission['case']); settings['mission'] = deepcopy(mission)
    return settings


def validate_mission(value):
    from .network import number
    if not isinstance(value, dict) or set(value) != {'version', 'preset', 'test_type', 'case', 'load', 'requirements'} or value['version'] != VERSION:
        raise ValueError('This mission format is not supported.')
    if value['test_type'] not in TEST_TYPES or not isinstance(value['preset'], str): raise ValueError('Choose a discharge, charge or custom test.')
    validate_case(value['case'])
    load = value['load']
    if not isinstance(load, dict) or load.get('kind') not in ('current', 'power') or set(load)-{'kind', 'current_A', 'power_W', 'converter_efficiency'}:
        raise ValueError('This load definition is not supported.')
    number(load['current_A'], 'Battery current', 0, 200)
    rows = value['requirements']
    if not isinstance(rows, list) or not 1 <= len(rows) <= 12: raise ValueError('List up to 12 requirements.')
    for row in rows:
        if not isinstance(row, dict) or set(row)-{'source_url'} != {'key', 'label', 'value', 'unit', 'basis', 'reason'} or row['basis'] not in BASES:
            raise ValueError('Each requirement needs a value and whether it is sourced, assumed or custom.')
        number(row['value'], row['key'])
    if {'load_current_A', 'duration_s', 'ambient_C'}-{r['key'] for r in rows}: raise ValueError('A mission needs a current, a run time and a room temperature.')


def application_view(settings):
    """Requirements as tested. A value edited after setup is relabelled custom."""
    mission = settings.get('mission')
    if not mission: return None
    rows = []
    for row in mission['requirements']:
        row = deepcopy(row); read = LIVE.get(row['key'])
        live = read(settings) if read else row['value']
        if live is None or abs(live-row['value']) > ROUNDING:
            preset_value = row['value']
            row.update(value=live, basis='custom', reason=f'Changed from the preset value of {preset_value:g} {row["unit"]}.')
        rows.append(row)
    return dict(name=mission['case']['name'], purpose=mission['case']['purpose'], preset=mission['preset'], test_type=mission['test_type'],
                load=deepcopy(mission['load']), requirements=rows, customized=any(r['basis'] == 'custom' for r in rows) and mission['preset'] in PRESETS,
                approximation='Battery current is held constant. A real converter draws more current as battery voltage falls.' if mission['load']['kind'] == 'power' else None)
