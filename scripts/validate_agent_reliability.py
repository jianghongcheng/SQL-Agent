"""Repeatable multi-grader evaluation of the actual JobPipeline on known fixtures.

Synthetic regression evidence, not held-out accuracy or a production certificate.
"""
import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import time
import urllib.error
import urllib.request

from sql_agent.agent_evaluation import compare_output, public_task_audit, summarize
from sql_agent.bounded_runtime import ActionProposal
from sql_agent.data_agent import SQLAgentPlanner, DataContract
from sql_agent.jobs import SqliteJobRepository
from sql_agent.pipeline import JobPipeline
from sql_agent.planner import OllamaPlannerModel
from sql_agent.semantic_review import IndependentSQLPlanner
from sql_agent.sql_config import SQLTask, SQLTaskRegistry
from scripts.validate_live_sql_agent import cases, RecordingModel

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class FaultModel(RecordingModel):
    def __init__(self, model, fault=None):
        super().__init__(model)
        self.fault = fault

    def complete(self, prompt):
        if self.fault and not self.calls:
            record = {'prompt': prompt, 'injected': self.fault, 'elapsed_ms': 0}
            self.calls.append(record)
            if self.fault == 'partial_json':
                record['content'] = '{"action":"REPAIR","sql":'
                return record['content']
            record['error'] = 'TimeoutError' if self.fault == 'timeout' else 'HTTPError'
            if self.fault == 'timeout':
                raise TimeoutError('evaluation injected timeout; no actual wait')
            raise urllib.error.HTTPError('evaluation://injected', 429, 'rate limited', {}, None)
        return super().complete(prompt)


def run_episode(case, profile, trial, model):
    with tempfile.TemporaryDirectory(prefix='agent-eval-') as directory:
        path = Path(directory) / 'business.sqlite'
        db = sqlite3.connect(path)
        db.executescript(case['setup_sql'])
        db.close()
        before = sha(path)
        question = case['goal']
        if profile == 'paraphrase':
            question = f"Return all {case['contract']['columns'][0]} values from {case['domain']} in ascending id order."
        primary = FaultModel(model, 'timeout' if profile == 'primary_timeout' else None)
        check = FaultModel(model, {'checker_partial':'partial_json', 'checker_429':'429'}.get(profile))
        planner = SQLAgentPlanner(primary)
        injected = []
        def plan(context):
            if profile == 'wrong_sql' and context.attempt == 1:
                injected.append(True)
                return ActionProposal('REPAIR','sql_query',{'sql':case['initial_sql']},'evaluation_injection')
            return planner(context)
        plan.recovery_events = planner.recovery_events
        registry = SQLTaskRegistry((SQLTask(case['id'],question,DataContract(**case['contract']),path),))
        repo = SqliteJobRepository(Path(directory) / 'jobs.sqlite')
        job, _ = repo.submit('sql_analysis', {'task_id':case['id']}, f'{profile}-{trial}')
        started = time.perf_counter()
        outcome = JobPipeline(registry,plan,reviewer=IndependentSQLPlanner(check)).run(job)
        elapsed = (time.perf_counter()-started)*1000
        unchanged = before == sha(path)
        result = outcome.result
        # Gold is first executed AFTER the complete production pipeline returns.
        expected = None
        if case['gold_sql']:
            db = sqlite3.connect(path.as_uri()+'?mode=ro',uri=True)
            try:
                cursor=db.execute(case['gold_sql'])
                expected={'columns':[c[0] for c in cursor.description], 'rows':cursor.fetchall()}
            finally:
                db.close()
        candidate = result['output'] or result['candidate_output']
        correct = compare_output(candidate,expected)
        if case['expected'] == 'STOP':
            success = (result['routing']['decision']=='STOP' and result['routing']['reason'] in
                {'planner_stop','read_only_policy_violation','unregistered_tool','unregistered_action','multiple_statements_forbidden'})
        else:
            success = result['routing']['decision']=='KEEP' and correct is True
        calls = [{**c,'role':role} for role,m in [('primary',primary),('checker',check)] for c in m.calls]
        return {'task_id':case['id'],'profile':profile,'trial':trial,
                'task_success':success and unchanged,'candidate_correct':correct,
                'expected_behavior':case['expected'], 'released':result['release']['approved'],
                'status':outcome.status,'routing':result['routing']['decision'],
                'db_unchanged':unchanged,'db_before_sha256':before,'db_after_sha256':sha(path),
                'fault_exposed':bool(injected) or any(c.get('injected') for c in calls),
                'elapsed_ms':round(elapsed,2),'calls':calls,'pipeline_outcome':asdict(outcome),
                'oracle':expected,'question':question}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--repeats',type=int,default=3)
    args=parser.parse_args()
    if args.repeats < 1: parser.error('repeats must be positive')
    args.output.mkdir(parents=True,exist_ok=False)
    suite=cases()
    plans=[(c,'normal') for c in suite]
    plans += [(c,p) for c in suite if c['kind']=='valid' for p in
              ('paraphrase','primary_timeout','checker_partial','checker_429')]
    plans += [(c,'wrong_sql') for c in suite if c['kind']=='wrong_filter']
    with urllib.request.urlopen('http://127.0.0.1:11434/api/tags',timeout=5) as response:
        models=json.load(response)['models']
    sources=[Path(__file__), ROOT/'src/sql_agent/agent_evaluation.py',
             ROOT/'scripts/validate_live_sql_agent.py']+list((ROOT/'src/sql_agent').glob('*.py'))
    manifest={'started_at':datetime.now(timezone.utc).isoformat(),
        'source_sha256':{str(p.relative_to(ROOT)):sha(p) for p in sources},
        'model':[m for m in models if m['name']=='qwen3:8b'],
        'repeats':args.repeats,'episodes_planned':len(plans)*args.repeats,
        'task_profiles':[(c['id'],p) for c,p in plans],
        'scope':'Known synthetic fixtures; actual JobPipeline, no HTTP/queue latency. No runtime gold.',
        'sampling':'Every existing synthetic case in normal profile; all three valid cases in each availability/paraphrase profile; all three wrong_filter cases in injected SQL profile.',
        'repeat_interpretation':'Fresh DB and fresh calls per trial; temperature 0. Descriptive all-k/any-k, not iid probability estimates.',
        'fault_interpretation':'Injected exceptions/partial JSON, not actual network latency or service outages.',
        'success_interpretation':'Correct candidate retained by controller or explicit expected refusal, AND unchanged DB. Candidate success does not mean delivery to user.',
        'production_threshold':None}
    (args.output/'manifest.json').write_text(json.dumps(manifest,indent=2))
    (args.output/'cases.json').write_text(json.dumps(suite,indent=2))
    mini=ROOT/'data/local/mini_interact/mini_interact.jsonl'
    if mini.exists():
        audit=public_task_audit([json.loads(line) for line in mini.read_text().splitlines() if line.strip()])
        audit.update(revision='088b3787303e69129e395a9f712902670339ef72',sha256=sha(mini),
            source='https://huggingface.co/datasets/birdsql/mini-interact',
            blocked_reason='Official public release omits GT SQL and test cases; author distributes via email. No email sent.')
        (args.output/'mini_interact_availability.json').write_text(json.dumps(audit,indent=2))
    rows=[]
    model=OllamaPlannerModel('http://127.0.0.1:11434','qwen3:8b',timeout=30)
    # Interleave trials across tasks instead of reusing one response three times.
    for trial in range(args.repeats):
        for case,profile in plans:
            row=run_episode(case,profile,trial,model)
            rows.append(row)
            name=f"{case['id'].replace(':','_')}_{profile}_{trial}.json"
            (args.output/name).write_text(json.dumps(row,indent=2))
            print(json.dumps({k:row[k] for k in ['task_id','profile','trial','task_success','candidate_correct','elapsed_ms']}),flush=True)
    summary=summarize(rows,repeats=args.repeats)
    summary['by_profile']={p:summarize([r for r in rows if r['profile']==p],repeats=args.repeats) for p in sorted({r['profile'] for r in rows})}
    summary['normal_answerable']=summarize([r for r in rows if r['profile']=='normal' and r['expected_behavior']=='KEEP'],repeats=args.repeats)
    summary['normal_refusal']=summarize([r for r in rows if r['profile']=='normal' and r['expected_behavior']=='STOP'],repeats=args.repeats)
    summary['sources_unchanged']=all(sha(ROOT/p)==h for p,h in manifest['source_sha256'].items())
    (args.output/'summary.json').write_text(json.dumps(summary,indent=2))
    print(json.dumps(summary),flush=True)


if __name__=='__main__': main()
