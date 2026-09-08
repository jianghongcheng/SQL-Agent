"""Live-model recovery from six injected executable-but-wrong SQL candidates.

Fault injection demonstrates routing; it is not natural model accuracy.
"""
import argparse
from dataclasses import asdict
import json
from pathlib import Path

from contractsql.bounded_runtime import ActionProposal
from contractsql.data_agent import ContractSQLPlanner, DataAgentLoop, DataContract
from contractsql.planner import OllamaPlannerModel
from contractsql.semantic_review import IndependentSQLPlanner, SemanticSQLSession
try:
    from scripts.validate_live_sql_agent import cases, database, RecordingModel
except ModuleNotFoundError:
    from validate_live_sql_agent import cases, database, RecordingModel


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    suite = [c for c in cases() if c['kind'] in {'wrong_filter', 'contract_alias'}]
    (args.output / 'manifest.json').write_text(json.dumps({
        'design': 'Six injected executable wrong candidates in three synthetic domains; live independent checking and live primary repair; no runtime gold.',
        'ids': [c['id'] for c in suite], 'model': 'qwen3:8b', 'primary_attempt_limit': 3,
        'independent_check_limit': 1, 'claim': 'Fault-recovery demonstration, not blind accuracy.'}, indent=2))
    records = []
    for case in suite:
        repair = RecordingModel(OllamaPlannerModel('http://127.0.0.1:11434', 'qwen3:8b', timeout=30))
        checker = RecordingModel(OllamaPlannerModel('http://127.0.0.1:11434', 'qwen3:8b', timeout=30))
        planner = ContractSQLPlanner(repair)
        def injected(ctx):
            if ctx.attempt == 1:
                return ActionProposal('REPAIR', 'sql_query', {'sql': case['initial_sql']}, 'injected_semantic_fault')
            return planner(ctx)
        db = database(case)
        try:
            session = SemanticSQLSession(db, DataContract(**case['contract']), case['goal'], IndependentSQLPlanner(checker))
            result = DataAgentLoop(3).run(case['goal'], injected, session)
        finally:
            db.close()
        # Gold executes only after the live controller has finished.
        db = database(case)
        try:
            expected = tuple(db.execute(case['gold_sql']).fetchall())
        finally:
            db.close()
        record = {'id': case['id'], 'outcome': asdict(result), 'review': session.semantic_review,
                  'repair_model_calls': repair.calls, 'check_model_calls': checker.calls,
                  'recovered_correct': result.decision == 'KEEP' and result.output['rows'] == expected}
        (args.output / (case['id'].replace(':', '_') + '.json')).write_text(json.dumps(record, indent=2))
        records.append(record)
        print(json.dumps({'id': case['id'], 'recovered_correct': record['recovered_correct'],
                          'repair_calls': len(repair.calls), 'check_calls': len(checker.calls)}), flush=True)
    summary = {'n': len(records), 'recovered_correct': sum(r['recovered_correct'] for r in records),
               'repair_model_calls': sum(len(r['repair_model_calls']) for r in records),
               'independent_model_calls': sum(len(r['check_model_calls']) for r in records),
               'production_auto_release': False, 'fault_injection': True}
    (args.output / 'summary.json').write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary), flush=True)


if __name__ == '__main__':
    main()
