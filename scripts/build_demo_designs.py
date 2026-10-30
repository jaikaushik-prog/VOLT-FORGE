"""The two real designs on the slide: the 4-cell starting design and the 2-cell result."""
import json
import sys
from pathlib import Path

from voltforge.project import Project
from voltforge.studio.store import Studio

path = Path('workspace/demo_pi'); Project.create_reference(path); studio = Studio(path)
sys.path.insert(0, 'scripts')
from run_design_study_v2 import build


def design(name, count, option):
    doc = studio.create('parallel', count, name, mission=dict(preset='pi5_gateway_backup'))
    graph, _, _ = build(dict(count=count, option=option, mission='pi'))
    return studio.save(doc['id'], doc['version'], graph, doc['settings'])


four = design('Starting design, 4 cells', 4, 'baseline'); two = design('Smaller, cheaper design, 2 cells', 2, 'opposite')
tests = [studio.run(d['id'], d['version'], title='Pi backup, 10 min') for d in (four, two)]
compare = studio.compare([t['id'] for t in tests])
print(compare['identical_test_conditions'], [t['summary']['metrics']['minimum_voltage_V'] for t in tests])
Path('tmp/demo_ids.json').write_text(json.dumps(dict(a=four['id'], b=two['id'], ta=tests[0]['id'], tb=tests[1]['id'])))
