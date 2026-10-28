"""Whole-file allocation guard and independent Samsung discharge assessment.

Only development-validation tests are opened by default. The final assessment
requires a frozen candidate seal and a separate explicit command.
"""
from pathlib import Path
import argparse
import hashlib
import io
import json
import sys
import zipfile

import numpy as np
from scipy.io import loadmat

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from voltforge.models.cell_catalogue import CellModel
from voltforge.models.coupling_v2 import rc_interval


def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--final',action='store_true');args=parser.parse_args()
    root=ROOT/'reports/model_catalogue_v1';candidate=root/'candidate_catalogue.json'
    plan=json.loads((ROOT/'configs/model_catalogue_upgrade_v1.plan.json').read_text())
    archive_path=ROOT/'data/raw/model_upgrade_sources/samsung30t-v2.zip'
    procedure=None
    if args.final:
        from voltforge.models.assessment_contract import verify_reserved_access
        names,procedure=verify_reserved_access(ROOT,archive_path,ROOT/'configs/samsung_assessment_procedure_v1.json',root/'assessment_seal.json')
    else:names=plan['development_validation']
    model=CellModel(json.loads(candidate.read_text())['models']['SAMSUNG_30T'])
    results=[]
    with zipfile.ZipFile(archive_path) as archive:
        for name in names:
            d=loadmat(io.BytesIO(archive.read(name)),simplify_cells=True)['meas']
            time=np.asarray(d['Time'],float);current=-np.asarray(d['Current'],float)
            measured=np.asarray(d['Voltage'],float);temperature=np.asarray(d['Battery_Temp_degC'],float)
            # Assessment uses the documented fully charged preparation and
            # current integration, never measured voltage to reset state.
            positive=current>.1
            starts=np.flatnonzero(positive)
            if not len(starts):raise ValueError('No discharge phase in allocated assessment')
            start=int(starts[0]);later=np.flatnonzero(~positive[start:])
            finish=start+int(later[0]) if len(later) else len(time)
            if args.final:start,finish=0,len(time)
            soc=1.;vp=np.zeros(model.nrc);rows=[];stop=None
            for i in range(start,finish):
                t=time[i]
                if not model.supported(soc,float(temperature[i])):
                    stop=dict(row=i+1,reason='outside_model_state',soc=float(soc),temperature_C=float(temperature[i]));break
                u,r0,r,tau=model.parameters(soc,float(temperature[i]))
                pred=float(u-r0*current[i]-vp.sum())
                if args.final:
                    issue=model.operating_error(float(temperature[i]),float(current[i]),pred)
                    if issue:
                        stop=dict(row=i+1,reason=issue[0],message=issue[1]);break
                rows.append(dict(source_row=i+1,time_s=float(t-time[0]),measured_V=float(measured[i]),predicted_V=pred,error_V=pred-float(measured[i]),soc=float(soc),cell_temperature_C=float(temperature[i])))
                if i==finish-1:break
                h=float(time[i+1]-t)
                if h<0:raise ValueError('Assessment clock reversed')
                soc-=current[i]*h/(3600*model.capacity)
                vp,_,_=rc_interval(vp,np.full(model.nrc,current[i]),r,tau,h)
            e=np.array([r['error_V'] for r in rows])
            result=dict(source=name,source_sha256=hashlib.sha256(archive.read(name)).hexdigest(),total_rows=len(time),discharge_phase_rows=finish-start,predicted_rows=len(rows),
                        fraction_rows_predicted=len(rows)/(finish-start),stop=stop,voltage_rmse_V=float(np.sqrt(np.mean(e**2))) if len(e) else None,
                        voltage_max_abs_V=float(np.max(abs(e))) if len(e) else None,
                        state_initialization='Frozen source-verified full-charge preparation, zero initial relaxation' if args.final else 'Development assumption: full-charge preparation, zero initial relaxation',
                        temperature_input='Measured cell surface temperature; this assesses electrical response only, not thermal prediction')
            if args.final:
                budget=procedure['acceptance']
                result['outcome']='within_declared_error_budget' if (stop is None and result['fraction_rows_predicted']>=budget['minimum_coverage'] and result['voltage_rmse_V'] is not None and result['voltage_rmse_V']<=budget['voltage_rmse_V'] and result['voltage_max_abs_V']<=budget['voltage_max_abs_V']) else 'failed_or_incomplete'
            results.append(result)
            if rows:
                import csv
                path=root/('final_' if args.final else 'development_')/(Path(name).stem+'.csv');path.parent.mkdir(exist_ok=True)
                with path.open('w') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    path=root/('final_assessment.json' if args.final else 'development_assessment.json')
    path.write_text(json.dumps(dict(candidate_sha256=digest(candidate),results=results,kind='final' if args.final else 'development'),indent=2)+'\n')
    for r in results:print(json.dumps(r))


if __name__=='__main__':main()
