"""Create three declared manual Pi-backup examples; no optimization or measured validation."""
from pathlib import Path
import argparse
import json
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from voltforge.project.service import Project
from voltforge.studio.store import Studio


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project',type=Path,required=True,help='Fresh working-project directory')
    parser.add_argument('--out',type=Path,required=True,help='New JSON receipt path')
    args=parser.parse_args()
    if args.project.exists() or args.out.exists():
        raise SystemExit('Choose new project and receipt paths; existing work will not be overwritten.')
    # Case allocation is declared before executing any simulation.
    cases=[dict(count=4,name='Review demo: 4-cell baseline'),
           dict(count=3,name='Review demo: 3-cell alternative'),
           dict(count=2,name='Review demo: 2-cell alternative')]
    Project.create_reference(args.project)
    studio=Studio(args.project);runs=[]
    for case in cases:
        doc=studio.create(kind='parallel',count=case['count'],name=case['name'],
                          mission=dict(test_type='discharge',preset='pi5_gateway_backup'))
        run=studio.run(doc['id'],doc['version'])
        runs.append(run)
    comparisons=[studio.compare([runs[0]['id'],run['id']]) for run in runs[1:]]
    receipt=dict(scope='Software workflow demonstration; three manually declared nominal cases. No measured module validation or robust design ranking.',
                 project=str(args.project.resolve()),software_hash=studio.software_hash,
                 model_hash=runs[0]['model_hash'],declared_cases=cases,
                 runs=[dict(id=r['id'],design_id=r['design_id'],name=r['design_name'],status=r['status'],
                            metrics=r['summary']['metrics'],operating_limit_coverage=r['summary']['operating_limit_coverage'],
                            requirement_checks=r['summary']['checks'],parts=r['parts'],
                            graph=r['graph'],settings=r['settings']) for r in runs],
                 comparisons=[{key:value for key,value in item.items() if key!='tests'} for item in comparisons])
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(receipt,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print(json.dumps({'project':receipt['project'],'runs':[{'cells':c['count'],'status':r['status'],
                     'minimum_voltage_V':r['summary']['metrics']['minimum_voltage_V'],
                     'peak_cell_current_A':r['summary']['metrics']['peak_cell_current_A']} for c,r in zip(cases,runs)]},indent=2))


if __name__=='__main__':main()
