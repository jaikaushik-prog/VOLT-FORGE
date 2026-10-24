import copy
import sys
import numpy as np
import pytest
from voltforge.simulation import workflow as w
from voltforge.simulation.__main__ import main


def test_complete_cli_workflow_preserves_models_and_reports_missing_requirements(tmp_path,monkeypatch):
    try:w.m.v1.source_archive()
    except ValueError:pytest.skip('Official archive needed to configure the attributed reference sensitivity')
    app=w.read(w.APPLICATION);app['load'][0]['end_s']=2.
    plan=w.read(w.SCENARIOS)
    plan['scenarios'][3]['overrides']['load'][0]['end_s']=2.
    app_path=tmp_path/'app.json';plan_path=tmp_path/'scenarios.json';out=tmp_path/'output'
    w.save(app_path,app);w.save(plan_path,plan)
    def cli(*args):monkeypatch.setattr(sys,'argv',['voltforge-simulation',*map(str,args)]);return main()
    assert cli('configure','--application',app_path,'--scenarios',plan_path,'--workspace',out)==0
    manifest=w.read(out/'manifest.json')
    assert manifest['new_characterization_cells_opened']==[] and manifest['measurement_outcomes_opened']==[]
    assert cli('simulate','--workspace',out,'--main-only')==0
    assert cli('compare','--workspace',out)==0
    for name in manifest['scenarios']:
        s=w.read(out/'runs'/name/'summary.json')
        assert s['status']=='completed' and s['voltage_requirement']['status']=='requirement not configured'
        assert s['decision']=='insufficient evidence' and s['experimental_validation']=='awaiting suitable measurements'
        assert all(x['experimental_waveform_support']=='unsupported transfer' for x in s['coverage']['cells'].values())
        assert s['max_kcl_residual_A']<1e-12
    monkeypatch.syspath_prepend('scripts')
    from make_module_fixture import make
    make(out/'runs/equal_soc',tmp_path/'synthetic')
    assert cli('validate','--measurements',tmp_path/'synthetic','--out',tmp_path/'ingestion')==0
    assert cli('compare','--workspace',out,'--measurements',tmp_path/'synthetic','--out',tmp_path/'comparison')==0
    comparison=w.read(tmp_path/'comparison/comparison.json')
    assert comparison['comparisons']['terminal_V']['bias']==pytest.approx(-.01,abs=1e-12)
    assert comparison['experimental_validation']=='awaiting suitable measurements'
    assert w.check_baseline()==112
    # A changed requirement/scenario cannot silently replace the predeclared config.
    app['load'][0]['current_A']=1.;w.save(app_path,app)
    with pytest.raises(ValueError):w.load_configuration(out)
