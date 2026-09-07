"""Paired selective gate on all 500 frozen BIRD candidates; no gold sent to models.

This measures screening, not fresh generation accuracy or unseen generalization.
"""
import argparse
from collections import Counter
from dataclasses import asdict
import json
from pathlib import Path
import sqlite3
import urllib.request

from geomed_copilot.bounded_runtime import ActionProposal, BoundedAgentRuntime
from geomed_copilot.data_agent import DataContract
from geomed_copilot.execution_record import digest
from geomed_copilot.planner import OllamaPlannerModel
from geomed_copilot.semantic_review import IndependentSQLPlanner, SemanticSQLSession
try:
    from scripts.validate_bird_external import file_hash
    from scripts.validate_live_sql_agent import RecordingModel
except ModuleNotFoundError:
    from validate_bird_external import file_hash
    from validate_live_sql_agent import RecordingModel


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', type=Path, default=Path('outputs/validation/bird_500_v1'))
    parser.add_argument('--data', type=Path, default=Path('data/local/bird_mini_dev'))
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads((args.baseline / 'manifest.json').read_text())
    rows = json.loads((args.data / 'sqlite.jsonl').read_text())
    cases = {r['question_id']: {'question': r['question'], 'evidence': r['evidence'], 'db_id': r['db_id']} for r in rows}
    assert len(cases) == 500 and set(cases) == set(manifest['question_ids'])
    assert file_hash(args.data / 'sqlite.jsonl') == manifest['question_file_sha256']
    databases = args.data / 'databases_full'
    for item in manifest['source']['files']:
        assert file_hash(databases / item['path']) == item['sha256']
    source_dir = Path(__file__).resolve().parents[1] / 'src/geomed_copilot'
    hashes = {p.name: file_hash(p) for p in source_dir.glob('*.py')}
    with urllib.request.urlopen('http://127.0.0.1:11434/api/tags', timeout=10) as response:
        model_info = [m for m in json.load(response)['models'] if m['name'] == 'qwen3:8b']
    assert model_info == manifest['model']
    args.output.mkdir(parents=True, exist_ok=False)
    protocol = {'n': 500, 'question_ids': manifest['question_ids'],
        'baseline': str(args.baseline), 'baseline_manifest_sha256': file_hash(args.baseline / 'manifest.json'),
        'baseline_records_sha256': {str(i): file_hash(args.baseline / f'{i}.json') for i in manifest['question_ids']},
        'source_hashes': hashes, 'model': model_info, 'review_prompt': IndependentSQLPlanner.PROMPT_VERSION,
        'runner_sha256': file_hash(Path(__file__)), 'comparison': 'exact ordered rows preserving duplicates; column count; aliases ignored',
        'design': 'Frozen primary candidates; one independent check for each previously accepted candidate; no repair or tuning during this run.',
        'limitations': 'Same model and seen benchmark. Agreement is not proof. No claim of unbiased unseen generalization. Production auto-release remains disabled without trusted business verification.',
        'reference': 'Reuse frozen offline baseline labels; five reference errors remain unknown and receive no correctness credit.'}
    (args.output / 'manifest.json').write_text(json.dumps(protocol, indent=2))
    records = []
    for i in manifest['question_ids']:
        previous = json.loads((args.baseline / f'{i}.json').read_text())
        primary = previous['bounded']
        record = {'question_id': i, 'db_id': previous['db_id'], 'difficulty': previous['difficulty'],
            'primary_correct': primary['execution_match'], 'primary_false_accept': primary['false_accept'],
            'reference_error': previous.get('reference_error'), 'agreement': False, 'review': {'status': 'primary_stopped'}, 'model_calls': []}
        if primary['outcome']['decision'] == 'KEEP':
            case = cases[i]
            path = databases / case['db_id'] / (case['db_id'] + '.sqlite')
            proposals = [t['proposal'] for t in primary['outcome']['trajectory'] if t['step'] == 'propose']
            proposal = ActionProposal(**proposals[-1])
            descriptions = {p.name: p.read_text(errors='replace') for p in sorted((path.parent / 'database_description').glob('*.csv'))}
            model = RecordingModel(OllamaPlannerModel('http://127.0.0.1:11434', 'qwen3:8b', timeout=30))
            db = sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True)
            try:
                session = SemanticSQLSession(db, DataContract(('dynamic_benchmark_output',), max_rows=10000),
                    case['question'] + '\nProvided BIRD evidence: ' + case['evidence'],
                    IndependentSQLPlanner(model, descriptions, use_output_contract=False), dynamic_columns=True)
                outcome = BoundedAgentRuntime().run(proposal, session)
                assert digest(session.candidate_output) == digest(primary['outcome']['output']), 'primary output drift'
                record.update(agreement=outcome.decision == 'KEEP', review=session.semantic_review,
                    outcome=asdict(outcome), model_calls=model.calls)
            finally:
                db.close()
        records.append(record)
        (args.output / f'{i}.json').write_text(json.dumps(record, indent=2))
        print(json.dumps({'n': len(records), 'id': i, 'status': record['review']['status'],
                          'agreement': record['agreement'], 'correct': record['primary_correct']}), flush=True)
    def metrics(selected):
        agreed = [r for r in selected if r['agreement']]
        known = [r for r in agreed if not r['reference_error']]
        correct = sum(r['primary_correct'] for r in agreed)
        return {'n': len(selected), 'review_states': dict(Counter(r['review']['status'] for r in selected)),
            'primary_correct': sum(r['primary_correct'] for r in selected),
            'primary_false_accept': sum(r['primary_false_accept'] for r in selected),
            'agreement_count': len(agreed), 'agreement_correct': correct,
            'agreement_wrong': sum(r['primary_false_accept'] for r in agreed),
            'agreement_ungraded': sum(bool(r['reference_error']) for r in agreed),
            'agreement_precision_graded': correct / len(known) if known else None,
            'correct_retention': correct / sum(r['primary_correct'] for r in selected) if any(r['primary_correct'] for r in selected) else None,
            'model_calls': sum(len(r['model_calls']) for r in selected)}
    summary = metrics(records)
    summary['by_database'] = {d: metrics([r for r in records if r['db_id'] == d]) for d in sorted({r['db_id'] for r in records})}
    summary['production_auto_released_unverified'] = 0
    summary['source_unchanged_during_run'] = hashes == {p.name: file_hash(p) for p in source_dir.glob('*.py')}
    assert summary['source_unchanged_during_run']
    (args.output / 'summary.json').write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary), flush=True)


if __name__ == '__main__':
    main()
