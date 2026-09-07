"""Live model + controlled timeout injection on 24 synthetic metric episodes.

Independent Python arithmetic grades outputs. No catalog fallback or seeded SQL.
This is a regression/fault exercise, not a general SQL benchmark or production SLO.
"""
import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import sqlite3

from geomed_copilot.commerce_catalog import make_task
from geomed_copilot.data_agent import ContractSQLPlanner
from geomed_copilot.jobs import SqliteJobRepository
from geomed_copilot.pipeline import JobPipeline
from geomed_copilot.planner import OllamaPlannerModel
from geomed_copilot.sql_config import SQLTaskRegistry
from geomed_copilot.worker import Worker

FIXTURES = {
    'empty': ([], []),
    'mixed_status': ([(1, 10000), (2, 8000)], [(1, 1000, 'approved'), (1, 2000, 'pending')]),
    'multiple_approved': ([(1, 10000), (2, 8000)], [(1, 1000, 'approved'), (1, 2000, 'approved')]),
    'pending_only': ([(1, 0), (2, 2500)], [(2, 500, 'pending')]),
}


class TimeoutOnce:
    """Deterministic injected failure, followed by real provider requests."""
    def __init__(self, model):
        self.delegate = model
        self.model = model.model
        self.injected = False

    def complete_with_metadata(self, prompt):
        if not self.injected:
            self.injected = True
            raise TimeoutError('Controlled evaluation fault')
        return self.delegate.complete_with_metadata(prompt)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    records = []
    for name, (orders, refunds) in FIXTURES.items():
        path = (args.output / (name + '.sqlite')).resolve()
        with sqlite3.connect(path) as db:
            db.executescript('CREATE TABLE orders(id INTEGER PRIMARY KEY, amount_cents INTEGER);'
                             'CREATE TABLE refunds(order_id INTEGER, amount_cents INTEGER, status TEXT);'
                             'CREATE TABLE ingestion_log(completed_at TEXT);')
            db.executemany('INSERT INTO orders VALUES(?,?)', orders)
            db.executemany('INSERT INTO refunds VALUES(?,?,?)', refunds)
            db.execute('INSERT INTO ingestion_log VALUES(?)', (datetime.now(timezone.utc).isoformat(),))
        source_before = path.read_bytes()
        gross = sum(amount for _, amount in orders)
        approved = sum(amount for _, amount, status in refunds if status == 'approved')
        expected = {'gross_revenue': gross, 'approved_refunds': approved, 'net_revenue': gross-approved}
        for profile in ('clean', 'timeout_once'):
            for metric, value in expected.items():
                episode = f'{name}_{profile}_{metric}'
                task = make_task(metric, path)
                model = OllamaPlannerModel('http://127.0.0.1:11434', 'qwen3:8b')
                if profile == 'timeout_once':
                    model = TimeoutOnce(model)
                repo = SqliteJobRepository(args.output / (episode + '_jobs.sqlite'))
                job, _ = repo.submit('sql_analysis', {'task_id': metric}, episode)
                worker = Worker(repo, JobPipeline(SQLTaskRegistry((task,)), ContractSQLPlanner(model)))
                worker.run_once()
                job = repo.get(job.job_id)
                result = job.result or {}
                output = result.get('output')
                released = result.get('release', {}).get('approved', False)
                correct = bool(output and output['rows'] == [[value]] and
                               output['columns'] == [metric + '_cents'])
                telemetry = result.get('telemetry', {})
                record = {'episode': episode, 'fixture': name, 'profile': profile,
                          'expected_cents': value, 'released': released,
                          'correct_release': bool(released and correct),
                          'wrong_release': bool(released and not correct),
                          'source_unchanged': path.read_bytes() == source_before,
                          'job': job.to_dict(), 'telemetry': telemetry,
                          'injected_failures': int(profile == 'timeout_once')}
                records.append(record)
                (args.output / (episode + '.json')).write_text(json.dumps(record, indent=2))
                print(json.dumps({k: record[k] for k in ('episode','correct_release','wrong_release')}
                                 | {'calls': telemetry.get('calls'), 'retries': telemetry.get('retries')}), flush=True)
    times = sorted(r['telemetry']['pipeline_elapsed_ms'] for r in records if r['telemetry'])
    summary = {
        'episodes': len(records), 'fixtures': len(FIXTURES), 'metrics': 3,
        'correct_releases': sum(r['correct_release'] for r in records),
        'wrong_releases': sum(r['wrong_release'] for r in records),
        'not_released': sum(not r['released'] for r in records),
        'source_mutations': sum(not r['source_unchanged'] for r in records),
        'injected_timeouts': 12,
        'correct_releases_after_injected_timeout': sum(r['correct_release'] for r in records if r['profile']=='timeout_once'),
        'calls_observed': sum(r['telemetry'].get('calls', 0) for r in records),
        'missing_telemetry_episodes': sum(not r['telemetry'] for r in records),
        'calls_without_complete_usage': sum(r['telemetry'].get('calls_without_complete_usage', 0) for r in records),
        'pipeline_p95_ms': times[math.ceil(.95*len(times))-1] if times else None,
        'monetary_cost': None,
        'scope': 'Synthetic fixed metrics, one trial per fixture/metric/fault profile; includes 12 controlled timeout injections; no general accuracy or SLO claim.',
    }
    (args.output / 'summary.json').write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary), flush=True)
    assert summary['wrong_releases'] == 0 and summary['source_mutations'] == 0
    assert summary['missing_telemetry_episodes'] == 0
    # Local regression expectation for this declared 24-case suite; not an industry threshold.
    assert summary['correct_releases'] == summary['episodes'], 'Incomplete task success; inspect retained failures'


if __name__ == '__main__':
    main()
