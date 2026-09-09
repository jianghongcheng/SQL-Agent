"""Bounded local HTTP load check with real model workers and independent answers.

This is an acceptance workload, not a sustained production SLO measurement.
Only child processes started here are stopped. Credentials are ephemeral.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import math
import os
from pathlib import Path
import secrets
import socket
import statistics
import subprocess
import sys
import time
import urllib.error
import urllib.request


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--requests', type=int, default=24)
    args = parser.parse_args()
    if not 1 <= args.requests <= 100:
        parser.error('requests must be 1..100')
    tasks = json.loads((args.data / 'tasks.json').read_text())
    expected = json.loads((args.data / 'expected.json').read_text())
    args.output.mkdir(parents=True, exist_ok=False)
    token = secrets.token_hex(24)
    env = os.environ.copy()
    for key in ('SQL_AGENT_DATABASE_URL',):
        env.pop(key, None)
    env.update(SQL_AGENT_SQL_TASKS=str((args.data / 'tasks.json').resolve()),
        SQL_AGENT_JOB_DB=str((args.output / 'jobs.sqlite').resolve()),
        SQL_AGENT_API_KEYS=json.dumps({token: {'name': 'load-check', 'role': 'operator'}}),
        SQL_AGENT_PLANNER_PROVIDER='ollama', SQL_AGENT_PLANNER_MODEL='qwen3:8b',
        SQL_AGENT_PLANNER_BASE_URL='http://127.0.0.1:11434', SQL_AGENT_PLANNER_TIMEOUT_SECONDS='30')
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0)); port = sock.getsockname()[1]
    base = f'http://127.0.0.1:{port}'
    processes = []
    def request(path, payload=None, key='health'):
        req = urllib.request.Request(base + path,
            data=None if payload is None else json.dumps(payload).encode(),
            headers={'content-type': 'application/json', 'x-api-key': token, 'idempotency-key': key})
        with urllib.request.urlopen(req, timeout=10) as response:
            return json.load(response)
    try:
        with (args.output / 'service.log').open('w') as log:
            processes.append(subprocess.Popen([sys.executable, '-m', 'uvicorn',
                'sql_agent.api:create_app', '--factory', '--host', '127.0.0.1', '--port', str(port)],
                env=env, stdout=log, stderr=log))
            deadline = time.monotonic() + 20
            while True:
                try:
                    request('/health'); break
                except OSError:
                    if time.monotonic() > deadline:
                        raise RuntimeError('API startup failed')
                    time.sleep(.2)
            for _ in range(2):
                processes.append(subprocess.Popen([sys.executable, '-m', 'sql_agent.worker'],
                    env=env, stdout=log, stderr=log))
            started = time.perf_counter()
            def run(index):
                task_id = tasks[index % len(tasks)]['task_id']
                start = time.perf_counter()
                payload = {'task_id': task_id}
                submitted = request('/v1/jobs', payload, str(index))
                duplicate = request('/v1/jobs', payload, str(index))
                dedup = submitted['job']['job_id'] == duplicate['job']['job_id'] and not duplicate['created']
                deadline = time.monotonic() + 150
                while True:
                    job = request('/v1/jobs/' + submitted['job']['job_id'])
                    if job['status'] in ('completed', 'needs_review', 'failed'):
                        break
                    if time.monotonic() > deadline:
                        raise TimeoutError('job deadline exceeded')
                    time.sleep(.1)
                correct = job['status'] == 'completed' and (job.get('result') or {}).get('output') == expected[task_id]
                row = {'index': index, 'task_id': task_id, 'deduplicated': dedup,
                    'correct': correct, 'false_accept': job['status'] == 'completed' and not correct,
                    'wall_ms': (time.perf_counter()-start)*1000, 'job': job}
                (args.output / f'job_{index:03}.json').write_text(json.dumps(row, indent=2))
                return row
            with ThreadPoolExecutor(max_workers=4) as pool:
                rows = list(pool.map(run, range(args.requests)))
            elapsed = time.perf_counter()-started
            latencies = sorted(r['wall_ms'] for r in rows)
            summary = {'requests': len(rows), 'unique_tasks': len({r['task_id'] for r in rows}),
                'clients': 4, 'workers': 2, 'correct': sum(r['correct'] for r in rows),
                'false_accept': sum(r['false_accept'] for r in rows),
                'deduplicated': sum(r['deduplicated'] for r in rows),
                'catalog_fallback': sum((r['job'].get('result') or {}).get('routing', {}).get('reason') == 'registered_business_fallback_verified' for r in rows),
                'median_ms': statistics.median(latencies), 'p95_ms': latencies[math.ceil(.95*len(rows))-1],
                'elapsed_seconds': elapsed, 'throughput_jobs_per_second': len(rows)/elapsed,
                'scope': 'Real local HTTP + two real model workers on registered real-data tasks. Includes queue/poll time. Small closed-loop run, not production SLO or scalability evidence.'}
            (args.output / 'summary.json').write_text(json.dumps(summary, indent=2))
            print(json.dumps(summary, indent=2))
            if summary['correct'] != len(rows) or summary['deduplicated'] != len(rows):
                raise SystemExit(1)
    finally:
        for process in reversed(processes):
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill(); process.wait()


if __name__ == '__main__':
    main()
