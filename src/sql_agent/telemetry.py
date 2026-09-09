"""Per-job model usage accounting, including failed and retried requests."""


def summarize_calls(recovery, elapsed_ms):
    stages = {}
    for stage, events in recovery.items():
        calls = [e for e in events if e['event'] in ('success', 'failure')]
        stages[stage] = {
            'calls': len(calls),
            'failed_calls': sum(e['event'] == 'failure' for e in calls),
            'retries': sum(e['attempt'] > 1 for e in calls),
            'call_elapsed_ms': round(sum(e.get('elapsed_ms', 0) for e in calls), 3),
            'retry_wait_ms': round(sum(e.get('delay_seconds', 0) * 1000 for e in calls), 3),
            'prompt_tokens_observed': sum(e.get('prompt_tokens') or 0 for e in calls),
            'completion_tokens_observed': sum(e.get('completion_tokens') or 0 for e in calls),
            'calls_without_complete_usage': sum(e.get('prompt_tokens') is None or
                                                e.get('completion_tokens') is None for e in calls),
        }
    totals = {key: sum(stage[key] for stage in stages.values()) for key in (
        'calls', 'failed_calls', 'retries', 'prompt_tokens_observed',
        'completion_tokens_observed', 'calls_without_complete_usage')}
    return {
        'pipeline_elapsed_ms': round(elapsed_ms, 3),
        'latency_scope': 'worker_pipeline_excluding_queue_wait_and_http',
        'stages': stages, **totals,
        'usage_complete': totals['calls_without_complete_usage'] == 0,
        'monetary_cost': None,
        'cost_reason': 'No provider pricing or local hardware/power cost supplied; token usage is not a dollar cost.',
    }
