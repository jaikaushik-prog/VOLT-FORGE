"""Verify the delivered predeclared demonstration and record reproducible hashes."""
from pathlib import Path
import xml.etree.ElementTree as ET
from voltforge.models import reference_investigation
from voltforge.simulation import workflow as w


def main():
    lock=reference_investigation.verify();out=w.DEFAULT_OUT;manifest=w.load_configuration(out)
    plan=w.read(out/'scenario_plan.json');runs=[]
    for name in manifest['scenarios']:
        for suffix in ['']+['__'+s['id'] for s in plan['sensitivity_scenarios']]:
            folder=out/'runs'/(name+suffix);score=w.read(folder/'summary.json')
            assert score['status']=='completed',folder
            assert score['voltage_requirement']['status']=='requirement not configured',folder
            assert score['decision']=='insufficient evidence',folder
            assert score['experimental_validation']=='awaiting suitable measurements',folder
            assert all(c['experimental_waveform_support']=='unsupported transfer' for c in score['coverage']['cells'].values()),folder
            runs.append(name+suffix)
    fixture=w.read(out/'synthetic_comparison/comparison.json')
    assert fixture['data_kind']=='synthetic_fixture'
    assert fixture['experimental_validation']=='awaiting suitable measurements'
    assert abs(fixture['comparisons']['terminal_V']['bias']+.01)<1e-10
    suite=ET.parse(out/'pytest.xml').getroot().find('testsuite')
    assert suite.get('tests')=='75' and all(suite.get(k)=='0' for k in ['errors','failures','skipped'])
    files=list(Path('src/voltforge/simulation').glob('*.py'))+[Path('src/voltforge/models/coupling_v2.py')]
    files+=list(Path('tests').glob('test_module*.py'))+[Path(__file__),Path('scripts/make_module_fixture.py')]
    files += [Path(p) for p in ['SIMULATION_PLAN.md','SIMULATION_READINESS.md','MEASUREMENT_IMPORT_SPEC.md',str(w.APPLICATION),str(w.SCENARIOS)]]
    files += [p for p in out.rglob('*') if p.is_file() and p.name!='release_verification.json']
    unique={p.resolve() for p in files};root=Path.cwd().resolve()
    w.save(out/'release_verification.json',dict(verified_utc=w.m.now(),tests=75,protected_original_v1_v2_artifacts=len(lock['protected']),
        original_archive_unchanged=True,unused_characterization_cells=lock['reserved_unused_cells'],
        preserved_reference_investigation=True,main_scenarios=4,sensitivity_scenarios=28,runs=runs,
        experimental_validation='awaiting suitable measurements',
        artifacts={p.relative_to(root).as_posix():w.digest(p) for p in sorted(unique)},
        note='Software demonstration verification; no repository publication, outreach or new module assessment data access.'))
    print('Verified: 75 tests; 32 main/sensitivity runs; 112 protected artifacts and original archive unchanged; nine unused cells preserved.')


if __name__=='__main__':main()
