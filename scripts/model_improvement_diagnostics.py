"""Open-evidence diagnosis and archive metadata review; never fresh voltage."""
from collections import Counter
from io import BytesIO
import json
import struct
import zlib
from pathlib import Path
import xml.etree.ElementTree as ET
from zipfile import ZipFile
import numpy as np
import pandas as pd
from scipy.io import whosmat
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from voltforge.models import improvement as m
from reconcile_independent import tags


def opaque_safe_headers(blob):
    """Read only MAT tag names/class/dimensions, never numeric channel values."""
    records=[]
    def visit(payload):
        for kind,value in tags(payload):
            if kind==15: visit(zlib.decompress(value))
            elif kind==14:
                p=list(tags(value));cls=struct.unpack_from('<I',p[0][1])[0]&255
                name=p[1 if cls==17 else 2][1].decode('utf-8',errors='replace')
                shape=None if cls==17 else np.frombuffer(p[1][1],dtype='<i4').astype(int).tolist()
                records.append(dict(name=name,shape=shape,type='MAT_class_'+str(cls)))
    visit(blob[128:]);return records


def main():
    m.verify();plan=m.read_json(m.PLAN);out=m.OUT/'diagnosis';out.mkdir(parents=True,exist_ok=True)
    results={}
    for cell in plan['development_cells']:
        low,f,q=m.load_cell(cell,list(range(1,10)))
        old=m.read_json(m.v1.OUT/f'{cell}_model.json')
        model=dict(kind='baseline',parameters_ohm=[old['parameters']['R0_ohm']],tau_s=1.,
            soc_knots=plan['bounds']['soc_knots'],reference={'baseline':old['rest_reference_anchors']})
        pred=m.predictions(f,model,list(range(1,10)));result=m.score(pred,plan)
        anchors=[]
        for c,g in pred.groupby('cycle'):
            r=g[g.step==11];r=r[r.time_s>=r.time_s.iloc[-1]-10]
            s=g[g.step==10]
            anchors.append(dict(cycle=int(c),soc=float(r.soc.median()),late_rest_bias_mV=float(r.error_V.mean()*1000),
                long_load=m.aggregate(s),late_rest_first_row=int(r.row.iloc[0]),late_rest_last_row=int(r.row.iloc[-1])))
        result['late_rest_by_cycle']=anchors
        # Reproduce actual v1 held predictions on their original source rows.
        previous=pd.read_csv(m.v1.OUT/f'{cell}_assessment_predictions.csv')
        joined=previous[['row','predicted_V']].merge(pred[['row','predicted_V']],on='row',suffixes=('_v1','_reproduced'))
        result['sealed_v1_prediction_max_difference_V']=float(abs(joined.predicted_V_v1-joined.predicted_V_reproduced).max())
        if result['sealed_v1_prediction_max_difference_V']>1e-11: raise ValueError('V1 reproduction failed')
        dt=np.diff(f.time_s);i=f.I_A.to_numpy()
        left=1-np.r_[0,np.cumsum(i[:-1]*dt)]/(3600*q);right=1-np.r_[0,np.cumsum(i[1:]*dt)]/(3600*q)
        result['quadrature_soc_max_change']=dict(left=float(max(abs(left-f.soc))),right=float(max(abs(right-f.soc))))
        result['residual_temperature_correlation']=float(np.corrcoef(pred.error_V,pred.surface_C)[0,1])
        result['temperature_correlation_caveat']='Load, time, SOC and temperature co-vary; correlation is not a temperature law.'
        results[cell]=result
        if cell=='P7':
            pred.to_csv(out/'P7_sealed_v1_full_record_predictions.csv',index=False)
            fig,axes=plt.subplots(2,3,figsize=(14,8),layout='constrained')
            # Plot decimation only, every row remains in numerical diagnostics.
            p=pred.iloc[::10];e=p.error_V*1000
            for ax,x,label in [(axes[0,0],p.soc,'SOC proxy'),(axes[0,1],p.I_A,'Discharge current [A]'),
                (axes[0,2],np.log10(1+p.since_transition_s),'log10(1 + seconds since current transition)'),
                (axes[1,0],p.surface_C,'Recorded surface temperature [C]')]:
                ax.scatter(x,e,s=2,alpha=.25);ax.axhline(0,color='black',lw=.5)
                ax.set(xlabel=label,ylabel='V1 predicted - measured [mV]');ax.grid(alpha=.2)
            axes[1,1].plot([a['soc'] for a in anchors],[a['late_rest_bias_mV'] for a in anchors],'o-')
            axes[1,1].set(xlabel='SOC at late pre-pulse rest',ylabel='Rest-reference bias [mV]')
            for c,g in pred[pred.step==10].groupby('cycle'):
                axes[1,2].plot(g.time_s-g.time_s.iloc[0],g.error_V*1000,label=str(c))
            axes[1,2].set(xlabel='Seconds in 4.85 A discharge',ylabel='V1 error [mV]');axes[1,2].legend(title='Cycle',fontsize=7,ncol=3)
            fig.suptitle('P7 sealed-v1 diagnosis on already-opened data; no new assessment evidence')
            fig.savefig(out/'P7_residual_diagnosis.png',dpi=140);plt.close(fig)
    m.save(out/'sealed_v1_diagnosis.json',results)

    # New hypothesis: additional packaged metadata/macros/hidden worksheets may
    # contain missing coefficients or schedules. Inspect structure, not final traces.
    inventory=m.read_json('reports/file_inventory.json');metadata=[]
    with ZipFile(m.v1.source_archive()) as z:
        for item in inventory:
            name=item['member'];blob=z.read(name)
            if name.endswith('.mat'):
                try:
                    variables=whosmat(BytesIO(blob))
                    variables=[dict(name=n,shape=list(s),type=t) for n,s,t in variables]
                    reader='SciPy whosmat headers'
                except TypeError:
                    variables=opaque_safe_headers(blob);reader='Opaque-safe MAT5 tag headers; no channel-value decoding'
                metadata.append(dict(member=name,variables=variables,reader=reader))
            elif name.endswith('.xlsx'):
                with ZipFile(BytesIO(blob)) as w:
                    ns={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
                    book=ET.fromstring(w.read('xl/workbook.xml'))
                    sheets=[dict(name=s.attrib['name'],state=s.attrib.get('state','visible')) for s in book.find('s:sheets',ns)]
                    extras=[n for n in w.namelist() if any(k in n.lower() for k in ['vbaproject','customxml','externallink','embedding'])]
                    names=[x.attrib.get('name') for x in book.findall('s:definedNames/s:definedName',ns)]
                    metadata.append(dict(member=name,sheets=sheets,embedded_or_external_parts=extras,defined_names=names))
    m.save(out/'archive_metadata_evidence.json',dict(
        hypothesis='Check for overlooked packaged code, coefficient objects, hidden worksheets, macros or external/embedded metadata.',
        inspected='ZIP names, MAT variable headers/shapes/types, workbook structure only; no new module voltage/current outcomes.',
        extensions=dict(Counter(Path(r['member']).suffix for r in inventory)),members=metadata,
        separate_processing_files=[r['member'] for r in inventory if Path(r['member']).suffix not in ['.mat','.xlsx']]))
    print('V1 predictions reproduced; residual diagnostics and archive structural evidence saved.')


if __name__=='__main__': main()
