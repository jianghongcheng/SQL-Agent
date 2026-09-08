"""Run one frozen, multi-track acceptance experiment without mixing metrics."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    root = Path(__file__).resolve().parents[1]
    steps = [
        ('external_sql', ['scripts/validate_bird_external.py', '--output', str(args.output / 'external_sql')]),
        ('real_data', ['scripts/validate_registered_dataset.py', '--data', 'data/local/tlc_2025_01', '--output', str(args.output / 'real_data'), '--repeats', '3']),
        ('http_load', ['scripts/load_registered_service.py', '--data', 'data/local/tlc_2025_01', '--output', str(args.output / 'http_load'), '--requests', '24']),
        ('schema_drift', ['scripts/validate_live_sql_retries.py', '--output', str(args.output / 'schema_drift')]),
        ('regression', ['-m', 'pytest', '-q']),
    ]
    protocol = {'started_at': datetime.now(timezone.utc).isoformat(),
        'tracks': dict(steps),
        'external_sql': '30 frozen cases, 10 each in California schools/financial/student club. No runtime gold or fallback; same-first-proposal 1 vs 3 attempts.',
        'real_data': '6 TLC tasks x 3 repeats per mode; paired first responses. Catalog-assisted outcomes separate from model results.',
        'http_load': '24 jobs, 4 clients, 2 workers; actual inference and independent expected outputs.',
        'schema_drift': '12 explicitly injected cases across 0/1/2/3 changes, with single/two/three-attempt and frozen-evidence controls.',
        'regression': 'Includes real worker kill/recovery, model HTTP timeout and lease fencing tests.',
        'no_tuning': 'No production/model/prompt changes after this protocol is written. Keep every failed case.',
        'scoring': 'No aggregate accuracy across these different tracks. No claim of production SLA or full BIRD leaderboard score.',
        'not_run': ['BIRD-Critic official correctness scoring', 'Spider 2.0'],
        'source_hashes': {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted((root / 'src/contractsql').glob('*.py'))}}
    (args.output / 'protocol.json').write_text(json.dumps(protocol, indent=2))
    report = {'protocol': 'protocol.json', 'tracks': {}}
    env = os.environ.copy()
    env['PYTHONPATH'] = 'src:.'
    env['PYTEST_DISABLE_PLUGIN_AUTOLOAD'] = '1'
    for name, command in steps:
        print('START ' + name, flush=True)
        started = time.perf_counter()
        with (args.output / (name + '.log')).open('w') as log:
            result = subprocess.run([sys.executable, *command], cwd=root, env=env, stdout=log, stderr=subprocess.STDOUT)
        record = {'exit_code': result.returncode, 'elapsed_seconds': time.perf_counter()-started,
                  'log': name + '.log'}
        summary = args.output / name / 'summary.json'
        if summary.exists():
            record['results'] = json.loads(summary.read_text())
        report['tracks'][name] = record
        (args.output / 'summary.json').write_text(json.dumps(report, indent=2))
        print('END ' + name + ' exit=' + str(result.returncode), flush=True)
    current = {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
               for p in sorted((root / 'src/contractsql').glob('*.py'))}
    report['production_source_unchanged'] = current == protocol['source_hashes']
    report['completed_at'] = datetime.now(timezone.utc).isoformat()
    (args.output / 'summary.json').write_text(json.dumps(report, indent=2))
    if not report['production_source_unchanged'] or any(r['exit_code'] for r in report['tracks'].values()):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
