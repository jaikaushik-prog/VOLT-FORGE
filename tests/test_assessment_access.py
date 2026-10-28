from copy import deepcopy
import json
from pathlib import Path

import pytest

from voltforge.models.assessment_contract import validate_procedure,verify_reserved_access

ROOT=Path(__file__).resolve().parents[1]


def definitions():
    procedure=json.loads((ROOT/'configs/samsung_assessment_procedure_v1.json').read_text())
    allocation=json.loads((ROOT/'configs/model_catalogue_upgrade_v1.plan.json').read_text())
    return procedure,allocation


def hypothetical_frozen_procedure():
    procedure,allocation=definitions()
    procedure['status']='frozen';procedure['initialization'].update(preparation_verified=True,source_locator='Synthetic test locator, not a real freeze')
    return procedure,allocation


def test_current_draft_is_rejected_before_archive_or_signal_access(tmp_path):
    with pytest.raises(ValueError,match='Freeze the assessment procedure'):
        verify_reserved_access(ROOT,tmp_path/'missing_archive.zip',ROOT/'configs/samsung_assessment_procedure_v1.json',tmp_path/'missing_seal.json')


@pytest.mark.parametrize('mutate',[
    lambda p,a:p.update(records=[a['calibration'][0]]),
    lambda p,a:p.update(records=[a['final_assessment_reserved'][0]]),
    lambda p,a:p.update(records=['unallocated.mat']),
    lambda p,a:p.update(voltage_state_reset=True),
    lambda p,a:p.update(window='best_segment'),
    lambda p,a:p.update(outside_support='clip'),
    lambda p,a:p['initialization'].update(preparation_verified=False),
    lambda p,a:p['acceptance'].update(minimum_coverage=.5),
])
def test_invalid_assessment_contracts_fail_before_decode(mutate):
    p,a=hypothetical_frozen_procedure();mutate(p,a)
    with pytest.raises(ValueError):validate_procedure(p,a)


def test_metadata_allocation_does_not_include_rejected_cold_or_exposed_records():
    p,a=hypothetical_frozen_procedure()
    assert validate_procedure(p,a)==p['records']
    assert len(p['records'])==4
    assert not set(p['records'])&set(a['development_validation'])
