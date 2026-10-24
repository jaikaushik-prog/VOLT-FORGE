"""Expose load-only errors so long rests cannot hide application errors."""
from voltforge.models import improvement as m
from summarize_improvement import get_predictions,SHORT,longest_contiguous_span
import numpy as np
import pandas as pd


def main():
    m.check_procedure();plan=m.read_json(m.PLAN);out={}
    for role,cells in [('development',plan['development_cells']),('fresh',plan['fresh_cells'])]:
        out[role]={}
        for cell in cells:
            out[role][cell]={}
            for kind in m.METHODS:
                f=get_predictions(m.OUT/role,cell,kind,plan);primary=m.primary_mask(f,plan)
                masks={'primary_4_85A_discharge':primary&(f.step==10),'primary_all_loaded':primary&(abs(f.I_A)>.01),
                    'primary_rest':primary&(abs(f.I_A)<=.01),'below_SOC_0_2':f.soc<.2}
                out[role][cell][kind]={name:m.aggregate(f,mask) for name,mask in masks.items()}
    m.save(m.OUT/'domain_slices.json',out)
    coverage=[]
    for role,cells in [('development',plan['development_cells']),('fresh',plan['fresh_cells'])]:
        for cell in cells:
            _,f,_=m.load_cell(cell,plan['calibration_cycles'])
            f=f[f.cycle.isin(plan['calibration_cycles'])&(f.step>=10)]
            model=m.read_json(m.OUT/role/f'{cell}_models.json')['C2_rest_reference_RC']
            valid=np.isfinite(m.reference(f.soc,f.loaded_V,model['reference'],'rest'))
            bands={'rest':abs(f.I_A)<=.01,'near_equal_share_3_64A':f.I_A.between(3.4,3.9),
                '4_85A_plateau':f.I_A.between(4.8,4.9),'above_4_9A':f.I_A>4.9,'charge':f.I_A<-.01}
            record=dict(role=role,cell=cell,actual_fit_current_min_A=float(f.I_A[valid].min()),
                actual_fit_current_max_A=float(f.I_A[valid].max()),unsupported_reference_rows=int((~valid).sum()),
                surface_min_C=float(f.surface_C[valid].min()),surface_max_C=float(f.surface_C[valid].max()),bands={})
            for label,mask in bands.items():
                mask=mask&valid;record['bands'][label]=dict(samples=int(mask.sum()),longest_observed_contiguous_span_s=longest_contiguous_span(f,mask))
            coverage.append(record)
    m.save(m.OUT/'calibration_coverage.json',coverage)
    # Keep the evaluation coverage's dwell field consistent with actual contiguous runs.
    table=pd.read_csv(m.OUT/'observed_evaluation_coverage.csv')
    for k,row in table.iterrows():
        f=get_predictions(m.OUT/row.role,row.cell,'C2_rest_reference_RC',plan)
        table.loc[k,'longest_continuous_positive_load_s']=longest_contiguous_span(f,(f.phase==row.phase)&(f.I_A>.01))
    table.to_csv(m.OUT/'observed_evaluation_coverage.csv',index=False)
    lines=['# Load-specific assessment errors','','These slices supplement the prespecified primary-domain score. They prevent hour-long rests from obscuring errors under the application-relevant 4.85 A discharge. No model selection is changed.','',
        '| Cell | Model | Primary 4.85 A sample/time RMSE [mV] | Bias [mV] | Max [mV] | Primary rest RMSE [mV] |',
        '|---|---|---:|---:|---:|---:|']
    for cell,models in out['fresh'].items():
        for kind,data in models.items():
            d=data['primary_4_85A_discharge'];r=data['primary_rest']
            lines.append(f"| {cell} | {SHORT[kind]} | {d['sample_rmse_mV']:.2f} / {d['time_rmse_mV']:.2f} | {d['bias_mV']:.2f} | {d['max_abs_mV']:.2f} | {r['sample_rmse_mV']:.2f} |")
    (m.OUT/'LOAD_ERRORS.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print('\n'.join(lines))


if __name__=='__main__': main()
