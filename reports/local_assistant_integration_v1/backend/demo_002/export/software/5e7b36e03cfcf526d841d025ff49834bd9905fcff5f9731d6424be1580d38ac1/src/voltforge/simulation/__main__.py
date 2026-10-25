"""Run `python -m voltforge.simulation --help` from the repository root."""
import argparse
import sys
from pathlib import Path
from . import workflow as w


def main():
    p=argparse.ArgumentParser(description='Electrical software verification; experimental module validation pending')
    sub=p.add_subparsers(dest='command',required=True)
    c=sub.add_parser('configure');c.add_argument('--application',type=Path,default=w.APPLICATION);c.add_argument('--scenarios',type=Path,default=w.SCENARIOS);c.add_argument('--workspace',type=Path,default=w.DEFAULT_OUT)
    s=sub.add_parser('simulate');s.add_argument('--workspace',type=Path,default=w.DEFAULT_OUT);s.add_argument('--main-only',action='store_true')
    c=sub.add_parser('compare');c.add_argument('--workspace',type=Path,default=w.DEFAULT_OUT);c.add_argument('--measurements',type=Path);c.add_argument('--scenario',default='equal_soc');c.add_argument('--out',type=Path)
    v=sub.add_parser('validate');v.add_argument('--measurements',type=Path,required=True);v.add_argument('--out',type=Path,required=True)
    args=p.parse_args()
    try:
        if args.command=='configure':w.configure(args.workspace,args.application,args.scenarios)
        elif args.command=='simulate':w.simulate_all(args.workspace,not args.main_only)
        elif args.command=='compare':
            if args.measurements:
                from .measurements import compare_measurements
                manifest=w.load_configuration(args.workspace)
                if args.scenario not in manifest['scenarios']:raise ValueError('Select a predeclared main scenario')
                r=compare_measurements(args.workspace/'runs'/args.scenario,args.measurements,args.out or args.workspace/'measurement_comparison')
                print(r['status']);print(r['experimental_validation'])
                if r['status'].startswith('comparison unavailable'):return 2
            else:
                from .reporting import compare
                compare(args.workspace)
        elif args.command=='validate':
            from .measurements import validate
            r,_,_=validate(args.measurements,args.out);print(r['experimental_validation'])
            print('Structure:',r['valid_structure'],'Alignment:',r['alignment_ok'],'Issues:',r['issues'])
            if not r['valid_structure'] or not r['alignment_ok']:return 2
    except (ValueError,KeyError,OSError) as e:
        print('Cannot complete command:',str(e),file=sys.stderr);return 2
    return 0


if __name__=='__main__':raise SystemExit(main())
