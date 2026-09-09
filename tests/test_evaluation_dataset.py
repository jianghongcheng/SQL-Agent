import json

import pytest

from sql_agent.evaluation_dataset import load_dataset
from sql_agent.evaluation_dataset import score_runs
from sql_agent.evaluation_dataset import verify_snapshots


def case(identifier='q1', split='dev'):
    return dict(case_id=identifier, family_id='orders-total', split=split,
                user_request='Total revenue?', snapshot_id='fixture-v1',
                required_evidence=['orders.amount'], operation='SELECT',
                allowed_tables=['orders'], allowed_columns=['orders.amount'],
                risk='read', clarification_required=False, approval_required=False,
                expected_result={'columns':['total'], 'rows':[[17000]]}, ordered=True)


def test_dataset_rejects_family_leakage_and_duplicate_case_ids(tmp_path):
    path = tmp_path / 'cases.json'
    dataset = dict(schema_version=1, dataset_version='0.1.0',
                   snapshots={'fixture-v1': {'sha256':'a' * 64}}, cases=[case()])
    path.write_text(json.dumps(dataset))
    assert load_dataset(path)['cases'][0]['case_id'] == 'q1'
    dataset['cases'].append(case('q2', 'held_out'))
    path.write_text(json.dumps(dataset))
    with pytest.raises(ValueError, match='family'):
        load_dataset(path)
    dataset['cases'] = [case(), case()]
    path.write_text(json.dumps(dataset))
    with pytest.raises(ValueError, match='duplicate'):
        load_dataset(path)


def test_report_keeps_unknown_missing_and_repeats_visible():
    unknown = {**case('q2'), 'expected_result':None}
    dataset = dict(dataset_version='0.1.0', cases=[case(), unknown, case('q3')])
    records = [dict(case_id='q1', trial=0, output={'columns':['total'], 'rows':[[17000]]}),
               dict(case_id='q1', trial=1, output={'columns':['total'], 'rows':[[1]]}),
               dict(case_id='q2', trial=0, output=None)]
    report = score_runs(dataset, records, split='dev', repeats=2)
    assert report['expected_runs'] == 6
    assert report['observed_runs'] == 3
    assert report['missing_runs'] == 3
    assert report['correct'] == 1
    assert report['incorrect'] == 1
    assert report['ungraded'] == 1
    assert report['observed_graded_accuracy'] == 0.5
    assert report['complete'] is False
    with pytest.raises(ValueError, match='duplicate'):
        score_runs(dataset, records + records[:1], split='dev', repeats=2)


def test_snapshot_verification_rejects_changed_fixture(tmp_path):
    fixture = tmp_path / 'fixture.sql'
    fixture.write_bytes(b'abc')
    dataset = {'snapshots':{'fixture-v1':{
        'sha256':'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad'}}}
    assert verify_snapshots(dataset, {'fixture-v1':fixture}) == ['fixture-v1']
    fixture.write_bytes(b'changed')
    with pytest.raises(ValueError, match='snapshot hash'):
        verify_snapshots(dataset, {'fixture-v1':fixture})
