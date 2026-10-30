"""Measure the slide's KPIs from the finished study and a timed run of the 16-cell module."""
from pathlib import Path
import json
import platform
import statistics
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
from build_demo_designs import module
from run_design_study_v2 import BANK
from voltforge.studio.network import settings_default, simulate

rows = [json.loads(line) for line in open(ROOT/'reports/design_study_v2/run1/cases.jsonl')]
refused = [r for r in rows if r['outcome'] == 'refused']
assert all('current exceeds' in r['reason'] for r in refused)
graph = module('16-cell backup module', 8); settings = settings_default()
settings['profile'] = [dict(start_s=0., end_s=600., current_A=16.)]
times = []
for _ in range(7):
    start = time.perf_counter(); simulate(graph, settings, {'LG_M50T_ECN': BANK['LG_M50T_ECN']}); times.append(time.perf_counter()-start)
memory = int(subprocess.run(['sysctl', '-n', 'hw.memsize'], capture_output=True, text=True).stdout)/2**30
cpu = subprocess.run(['sysctl', '-n', 'machdep.cpu.brand_string'], capture_output=True, text=True).stdout.strip()
out = dict(study_runs=len(rows), overloads_caught=len(refused), overload_reason='Cell current exceeds the 7.275 A operating limit; the app refused the run',
           simulated_s=600, seconds_16_cells=statistics.median(times), runs_timed=len(times), machine=f'{cpu}, {memory:.0f} GB, {platform.system()}')
(ROOT/'reports/slide_v4/kpi.json').write_text(json.dumps(out, indent=1)+'\n'); print(out)
