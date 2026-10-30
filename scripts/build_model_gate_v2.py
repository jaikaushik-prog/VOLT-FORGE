"""Fresh gate for the exact deployed V4 catalogue. Checks repairs; asserts no validation."""
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from voltforge.models.cell_catalogue import lint_tables, load_additional
from voltforge.studio.network import settings_default, simulate, template

OUT = ROOT/'reports/model_catalogue_v2/gate.json'


def run(key, current, seconds, charge=70., capacity=None):
    g = template('parallel', 1); g['cells'][0].update(model=key, charge_pct=charge)
    if capacity: g['thermal']['cell_parameters'] = {'cell1': {'heat_capacity_J_K': capacity}}
    s = settings_default(); s['profile'] = [dict(start_s=0., end_s=float(seconds), current_A=float(current))]
    return simulate(g, s, BANK)


def continuity(current):
    # Held temperature: only the tables can move voltage across the old 18-20% jump.
    rows = [r for r in run('LG_M50T_ECN', current, 1.2*.15*5*3600/current+1, 30., 10000.).rows if 15 <= r['charge_pct'][0] <= 25]
    return dict(current_A=current, largest_upward_voltage_step_V=float(max(np.diff([r['voltage_V'] for r in rows]).max(), 0.)))


BANK = load_additional(ROOT)
raw = (ROOT/'configs/cell_catalogue_v2.json').read_bytes()
data = json.loads(raw)
samsung = {}
for current, seconds in ((6., 1560.), (4., 2300.)):
    r = run('SAMSUNG_30T', current, seconds)
    v = r.summary['verification']
    samsung[f'{current:g}A'] = dict(status=r.status, stop=r.stop['reason'], stop_time_s=r.stop['time_s'],
                                    peak_temperature_C=r.summary['metrics']['peak_temperature_C'],
                                    first_law_residual_J=v['first_law_residual_J'], electrical_loss_J=v['electrical_dissipation_J'])
checks = dict(table_lint_findings=sum(len(lint_tables(m)) for m in data['models'].values()),
              lg_continuity=[continuity(i) for i in (1., 3., 5.)], samsung=samsung)
gate = dict(version='voltforge.model-gate/2', created_utc=datetime.now(timezone.utc).isoformat(),
            deployed_catalogue='configs/cell_catalogue_v2.json', deployed_catalogue_sha256=hashlib.sha256(raw).hexdigest(),
            parent_sha256=data['revision']['parent_sha256'], lg_revision_status=data['revision']['status'],
            passed=checks['table_lint_findings'] == 0 and all(c['largest_upward_voltage_step_V'] < 1e-4 for c in checks['lg_continuity'])
            and all(s['stop'] == 'charge_domain' and s['stop_time_s'] > 544 for s in samsung.values()),
            checks=checks, measured_accuracy_established=False,
            note='This binds the repaired checks to the exact deployed hash. The V1 gate recorded a stale production hash; it is retained unchanged.')
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(gate, indent=2, allow_nan=False)+'\n')
print(json.dumps(dict(passed=gate['passed'], checks=checks), indent=1))
if not gate['passed']: raise SystemExit(1)
