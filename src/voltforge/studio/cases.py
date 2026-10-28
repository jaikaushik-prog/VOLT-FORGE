"""Small versioned application contract derived from the actual saved experiment."""
from copy import deepcopy

BENCHMARK = dict(name='Low-voltage backup design study',
    purpose='Compare four-cell connection arrangements under the saved load, duration and starting conditions.',
    source='Declared Round 1 design-study benchmark. The proposed 3.3 V output floor is not a manufacturer rating or a connected-device specification.')
DEFAULT = dict(name='Battery design study',purpose='Explore this design under the declared test conditions.',
               source='User-proposed operating conditions and design targets; independent device compatibility is not established.')


def validate_case(value):
    if not isinstance(value,dict) or set(value)!={'name','purpose','source'}:
        raise ValueError('An application description needs a name, purpose and source.')
    for key,length in [('name',120),('purpose',1000),('source',2000)]:
        if not isinstance(value[key],str) or not 1<=len(value[key].strip())<=length:
            raise ValueError('Give the application a short name, purpose and target source.')


def case_record(graph,settings):
    from .network import digest
    description=deepcopy(settings.get('case',DEFAULT));validate_case(description)
    targets=[dict(quantity=key,value=value,kind='declared_design_target',
                  source=(description['source'] if description!=BENCHMARK or (key=='min_voltage_V' and value==3.3)
                          else 'User-proposed change to the benchmark target; independent source not supplied.'))
             for key,value in settings['limits'].items() if value is not None]
    mission=dict(profile=deepcopy(settings['profile']),ambient_C=settings['ambient_C'],
                 monitoring_and_protection=deepcopy(settings.get('protection')),
                 initial_cells=[{key:c[key] for key in ('id','charge_pct','temperature_C','polarization_V')} for c in graph['cells']],
                 preparation='Declared starting charge, cell temperature and electrical relaxation; not a measured hardware initializer.')
    content=dict(description=description,mission=mission,targets=targets,
                 priorities=['Complete the requested service','Meet declared output targets','Compare cell stress and connection trade-offs'],
                 physical_validation=False)
    return dict(version='voltforge.application-case/1',fingerprint=digest(content),
                requirements_fingerprint=digest(dict(description=description,targets=targets)),**content)
