"""Count the slide's data and research KPIs from the project's own records."""
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]


def read(path): return json.loads((ROOT/path).read_text())


inventory = read('reports/file_inventory.json'); splits = read('configs/splits.json'); plan = read('configs/model_catalogue_upgrade_v1.plan.json')
modules = sum('/Raw_data/' in r['member'] and r['member'].endswith('.xlsx') for r in inventory)
out = dict(study_runs=sum(1 for _ in open(ROOT/'reports/design_study_v2/run1/cases.jsonl')), lab_experiments=modules, data_files=len(inventory),
           sealed_module_records=len(splits['final_assessment']), sealed_cell_records=len(plan['final_assessment_reserved']),
           sealed_total=len(splits['final_assessment'])+len(plan['final_assessment_reserved']))
(ROOT/'reports/slide_v4/kpi.json').write_text(json.dumps(out, indent=1)+'\n'); print(out)
