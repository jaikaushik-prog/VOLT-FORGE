"""Fail-closed authorization for untouched whole-record assessment observations.

This checks files and metadata before the caller opens a MAT/CSV signal. A
candidate hash alone is insufficient to freeze an assessment.
"""
from pathlib import Path
import hashlib
import json


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def validate_procedure(procedure,allocation):
    if procedure.get('version')!='voltforge.electrical-assessment/1' or procedure.get('status')!='frozen':
        raise ValueError('Freeze the assessment procedure before opening reserved signals.')
    records=procedure.get('records')
    reserved=set(allocation['final_assessment_reserved'])
    exposed=set(allocation['calibration'])|set(allocation['development_validation'])
    if not isinstance(records,list) or not records or len(set(records))!=len(records) or set(records)-reserved or set(records)&exposed:
        raise ValueError('Every assessment record must have an unexposed reserved whole-test allocation.')
    allowed=set(procedure.get('eligible_chamber_labels_C',[]))
    for name in records:
        try:chamber=int(Path(name).parent.name.removesuffix('degC'))
        except ValueError:raise ValueError('The source condition cannot be identified from its allocated metadata.') from None
        if chamber not in allowed:raise ValueError('This source condition was not allocated to the selected model assessment.')
    if procedure.get('window')!='whole_record' or procedure.get('voltage_state_reset') is not False:
        raise ValueError('Use complete allocated records without voltage-based state resets.')
    init=procedure.get('initialization',{})
    if init.get('preparation_verified') is not True or not isinstance(init.get('source_locator'),str) or not init['source_locator'].strip():
        raise ValueError('Verify the source preparation and its locator before freezing the starting state.')
    if init.get('soc')!=1. or init.get('relaxation_V')!=0.:
        raise ValueError('The current assessment adapter supports only the declared full-charge, rested initializer.')
    if procedure.get('temperature_input')!='measured_cell_surface' or procedure.get('scope')!='electrical_response_only':
        raise ValueError('Keep electrical response assessment separate from thermal prediction.')
    if procedure.get('outside_support')!='stop_and_fail_full_record' or procedure.get('component_limits')!='enforce':
        raise ValueError('Unsupported states and operating limits must stop the assessment without a partial-record pass.')
    if procedure.get('interpolation')!='production_bilinear_no_extrapolation' or procedure.get('integration')!='held_current_exact_rc_per_source_interval':
        raise ValueError('The frozen interpolation and time integration must match this assessment adapter.')
    thresholds=procedure.get('acceptance',{})
    if thresholds!={'minimum_coverage':1.,'voltage_rmse_V':.05,'voltage_max_abs_V':.15}:
        raise ValueError('Use the predeclared complete-record research-prototype error budget.')
    if procedure.get('source_sampling')!='retain_original_order_and_duplicate_time_events':
        raise ValueError('Preserve original source samples and one-sided current events.')
    if procedure.get('refit_after_assessment') is not False:raise ValueError('Assessment observations cannot be used to refit this frozen version.')
    return records


def input_fingerprints(root,archive,procedure_path):
    root=Path(root);archive=Path(archive)
    paths=['configs/model_catalogue_upgrade_v1.plan.json','configs/cell_catalogue_v1.json','configs/cell_catalogue_v2.json',
           'reports/model_catalogue_v1/candidate_catalogue.json','scripts/assess_cell_catalogue.py',
           'tests/test_temperature_models.py','tests/test_coupled_reference.py']
    paths += [str(p.relative_to(root)) for folder in ('models','studio') for p in sorted((root/'src/voltforge'/folder).glob('*.py'))]
    import numpy,scipy,platform
    return dict(procedure_sha256=sha(procedure_path),archive_sha256=sha(archive),
                files={name:sha(root/name) for name in paths},
                runtime=dict(python=platform.python_version(),numpy=numpy.__version__,scipy=scipy.__version__))


def verify_reserved_access(root,archive,procedure_path,seal_path):
    root=Path(root)
    allocation=json.loads((root/'configs/model_catalogue_upgrade_v1.plan.json').read_text())
    procedure=json.loads(Path(procedure_path).read_text())
    records=validate_procedure(procedure,allocation)
    current=input_fingerprints(root,archive,procedure_path)
    if current['archive_sha256']!=allocation['archive_sha256']:raise ValueError('The assessment source archive does not match its allocated revision.')
    seal=json.loads(Path(seal_path).read_text())
    if seal.get('version')!='voltforge.assessment-seal/1' or seal.get('inputs')!=current:
        raise ValueError('The candidate, code, procedure, source or runtime changed after the assessment freeze.')
    return records,procedure
