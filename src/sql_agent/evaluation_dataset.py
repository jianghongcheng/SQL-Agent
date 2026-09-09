"""Versioned offline evaluation input; never send oracle fields to a planner."""
import json
import hashlib
import re
from pathlib import Path

from .agent_evaluation import compare_output


def verify_snapshots(dataset, paths):
    """Check explicit local immutable fixture paths, without executing any SQL."""
    if set(paths) != set(dataset['snapshots']):
        raise ValueError('snapshot paths must match the manifest')
    verified = []
    for identifier, metadata in dataset['snapshots'].items():
        digest = hashlib.sha256()
        with Path(paths[identifier]).open('rb') as stream:
            for block in iter(lambda: stream.read(65536), b''):
                digest.update(block)
        if digest.hexdigest() != metadata['sha256']:
            raise ValueError(f'snapshot hash mismatch: {identifier}')
        verified.append(identifier)
    return verified


def load_dataset(path):
    data = json.loads(Path(path).read_text())
    if data.get('schema_version') != 1 or not data.get('dataset_version'):
        raise ValueError('unsupported dataset version')
    snapshots = data.get('snapshots', {})
    if not snapshots or any(not re.fullmatch(r'[0-9a-f]{64}', s.get('sha256', ''))
                            for s in snapshots.values()):
        raise ValueError('snapshot sha256 required')
    cases = data.get('cases')
    if not isinstance(cases, list) or not cases:
        raise ValueError('nonempty cases required')
    seen, families = set(), {}
    for case in cases:
        for key in ('case_id', 'family_id', 'user_request', 'snapshot_id'):
            if not isinstance(case.get(key), str) or not case[key].strip():
                raise ValueError(f'{key} required')
        if case['case_id'] in seen:
            raise ValueError('duplicate case_id')
        seen.add(case['case_id'])
        if case.get('split') not in {'dev', 'held_out'}:
            raise ValueError('invalid split')
        if families.setdefault(case['family_id'], case['split']) != case['split']:
            raise ValueError('family overlaps dev and held_out')
        if case['snapshot_id'] not in snapshots:
            raise ValueError('unknown snapshot')
        if case.get('operation') not in {'SELECT', 'INSERT', 'UPDATE', 'DELETE', 'CREATE', 'ALTER', 'DROP', 'TRUNCATE', 'NONE'}:
            raise ValueError('invalid operation')
        if case.get('risk') not in {'read', 'write', 'ddl', 'destructive', 'denied'}:
            raise ValueError('invalid risk')
        for key in ('required_evidence', 'allowed_tables', 'allowed_columns'):
            if not isinstance(case.get(key), list) or any(not isinstance(x, str) for x in case[key]):
                raise ValueError(f'{key} must be a string list')
        for key in ('clarification_required', 'approval_required', 'ordered'):
            if type(case.get(key)) is not bool:
                raise ValueError(f'{key} must be boolean')
        if 'expected_result' not in case:
            raise ValueError('expected_result required; use null for ungraded cases')
        oracle = case['expected_result']
        if oracle is not None and (not isinstance(oracle, dict) or
                not isinstance(oracle.get('columns'), list) or not isinstance(oracle.get('rows'), list)):
            raise ValueError('invalid result oracle')
    return data


def score_runs(dataset, records, *, split, repeats):
    """Grade observed query outputs, not authorization or mutation correctness.

    One invocation represents one fixed configuration. Missing planned trials are
    exposed, never silently treated as correct or removed from coverage counts.
    """
    if split not in {'dev', 'held_out'} or type(repeats) is not int or repeats < 1:
        raise ValueError('invalid split or repeats')
    cases = {c['case_id']: c for c in dataset['cases'] if c['split'] == split}
    seen, counts, results = set(), {'correct':0, 'incorrect':0, 'ungraded':0}, []
    for record in records:
        case_id, trial = record.get('case_id'), record.get('trial')
        if case_id not in cases or type(trial) is not int or not 0 <= trial < repeats:
            raise ValueError('unknown case or invalid trial')
        key = (case_id, trial)
        if key in seen:
            raise ValueError('duplicate trial')
        seen.add(key)
        case = cases[case_id]
        grade = None
        if case['operation'] == 'SELECT' and not case['clarification_required'] and case['risk'] == 'read':
            grade = compare_output(record.get('output'), case['expected_result'], ordered=case['ordered'])
        label = 'ungraded' if grade is None else 'correct' if grade else 'incorrect'
        counts[label] += 1
        results.append({'case_id':case_id, 'trial':trial, 'result_grade':label})
    expected = len(cases) * repeats
    graded = counts['correct'] + counts['incorrect']
    return dict(schema_version=1, dataset_version=dataset['dataset_version'], split=split,
                repeats=repeats, unique_cases=len(cases), expected_runs=expected,
                observed_runs=len(seen), missing_runs=expected-len(seen),
                complete=expected > 0 and expected == len(seen), **counts,
                observed_graded_accuracy=counts['correct']/graded if graded else None,
                results=results, scope='Query-result comparison only; not end-to-end task or safety acceptance.')
