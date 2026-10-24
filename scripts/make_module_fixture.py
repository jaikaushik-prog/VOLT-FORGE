"""Explicitly synthetic importer fixture from a saved simulation, with known offsets.

This checks the plumbing only; it is deliberately not an independent model test.
"""
import argparse
import copy
from pathlib import Path
import pandas as pd
from voltforge.simulation import workflow as w
from voltforge.simulation.measurements import CHANNELS


def make(run,out):
    run=Path(run);out=Path(out);out.mkdir(parents=True,exist_ok=True)
    c=w.read(run/'configuration.json');f=pd.read_csv(run/'trajectory.csv').iloc[::4].copy()
    # All voltage readings get a known +10 mV fixture offset; no measurement claim.
    records={'source_row':range(1,len(f)+1),'time_s':f.time_s.to_numpy()};channels={}
    for name,(unit,location) in CHANNELS.items():
        records[name]=f[name].to_numpy()+.01 if unit=='V' else (f[name].to_numpy() if unit=='A' else [23.]*len(f))
        channels[name]=dict(unit=unit,location=location,sensor_id='SYNTHETIC_'+name,time_column='time_s',
            calibration=dict(status='synthetic',source='Generated software fixture; not an instrument certificate',date='2026-10-25',absolute_uncertainty=.001))
        if unit=='A':channels[name]['polarity']='discharge_positive'
        if unit=='V':channels[name]['polarity']='positive_minus_negative'
    meta=dict(schema_version=1,data_kind='synthetic_fixture',dataset_id='generated-v2-module-plumbing-check',cell_order=c['cell_order'],
        time_unit='s',time_origin='Synthetic elapsed seconds since the configured load begins',channels=channels,
        preparation=dict(history='Synthetic initial states copied from configuration',initial_soc=c['initial_soc'],initial_polarization_V=c['initial_polarization_V'],rest_s=0,source='software fixture'),
        synchronization=dict(method='Same generated clock',evidence='Synthetic common timestamps',alignment_tolerance_s=0.,maximum_gap_s=2.),
        fixture_truth=dict(voltage_offset_V=.01,physical_evidence=False,source_run_config_sha256=w.digest(run/'configuration.json')))
    pd.DataFrame(records).to_csv(out/'measurements.csv',index=False);w.save(out/'metadata.json',meta)
    print('Created SYNTHETIC fixture; not real measurements:',out)


if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__);p.add_argument('--run',type=Path,default=w.DEFAULT_OUT/'runs/equal_soc');p.add_argument('--out',type=Path,default=Path('tests/fixtures/module_synthetic'))
    a=p.parse_args();make(a.run,a.out)
