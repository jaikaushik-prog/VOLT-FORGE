"""The two real designs on the slide: the 4-cell starting design and the 2-cell result."""
import json
from pathlib import Path

from voltforge.project import Project
from voltforge.studio.store import Studio

path = Path('workspace/demo_pi'); Project.create_reference(path); studio = Studio(path)
four = studio.create('parallel', 4, 'Starting design, 4 cells', mission=dict(preset='pi5_gateway_backup'))
two = studio.create('parallel', 2, 'Improved design, 2 cells', mission=dict(preset='pi5_gateway_backup'))
tests = [studio.run(d['id'], d['version'], title='Pi backup, 10 min') for d in (four, two)]
compare = studio.compare([t['id'] for t in tests])
print(compare['identical_test_conditions'], [t['summary']['metrics']['minimum_voltage_V'] for t in tests])
Path('tmp/demo_ids.json').write_text(json.dumps(dict(a=four['id'], b=two['id'], ta=tests[0]['id'], tb=tests[1]['id'])))
