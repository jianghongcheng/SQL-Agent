"""Describe recorded inference costs; no invented dollar prices or SLA claims."""
import argparse
import json
import math
import platform
from pathlib import Path
import statistics


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run', type=Path)
    args = parser.parse_args()
    cases = json.loads((args.run / 'cases.json').read_text())
    rows = [json.loads((args.run / (c['id'].replace(':', '_') + '.json')).read_text()) for c in cases]
    values = [r['bounded_wall_ms'] for r in rows]
    calls = [call for r in rows for call in r['model_calls']]
    def tokens(key, selected):
        return sum(c.get('metadata', {}).get(key, 0) or 0 for c in selected)
    result = {
        'n': len(rows), 'latency_ms': {'median': statistics.median(values),
            'p95_nearest_rank': sorted(values)[math.ceil(.95 * len(values))-1]},
        'model_calls': len(calls), 'prompt_tokens': tokens('prompt_tokens', calls),
        'completion_tokens': tokens('completion_tokens', calls),
        'retry_calls': sum(max(0, len(r['model_calls'])-1) for r in rows),
        'retry_completion_tokens': tokens('completion_tokens', [c for r in rows for c in r['model_calls'][1:]]),
        'platform_at_summary_time': platform.platform(),
        'limitations': 'Small single-run local sample; warmup and contention uncontrolled. Not an SLA. Local electricity/hardware cost unmeasured; no dollar-cost claim.',
    }
    (args.run / 'metrics.json').write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
