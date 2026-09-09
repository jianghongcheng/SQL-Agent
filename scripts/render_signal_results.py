"""Render sanitized metrics from the evidence audit; no secrets or raw prompts."""
import argparse
import json
from pathlib import Path


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--audit',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    args = p.parse_args()
    report = json.loads(args.audit.read_text())
    checks = report['checks']
    lines = ['# SQL-Agent — local Strong Signal results', '',
             '**Local engineering protocol: '+('complete' if report['local_engineering_complete'] else 'incomplete')+'.**', '',
             'This is the requested single-host local deployment scope. It does not establish',
             'a production SLO or semantic correctness. General queries require human review;',
             'the fine-tuned candidate is not promoted.', '',
             '| Evidence | Status |', '| --- | --- |']
    for name, check in checks.items():
        lines.append(f"| {name} | {'Passed' if check['passed'] else 'Incomplete / failed'} |")
    if checks['regression']['passed']:
        n = checks['regression']['details']['passed_tests']
        lines.extend(['',f'Full regression: **{n} passed**, no skipped tests; includes headless Chrome and disposable PostgreSQL.'])
    if checks['live_agent_and_evaluation']['passed']:
        lines.extend(['','## Real-model SQL and token cost', '',
            '48 instances in six known synthetic task families, eight fresh data instances each.',
            'Same models and frozen prompts/settings across the three retrieval conditions.',
            'Failures remain in the denominator. These are development-family results,',
            'not unseen-task or production accuracy. No general answer was auto-published.', '',
            '| Retrieval | Correct | Failed / unavailable | Total tokens | Tokens / job | Tokens / correct result | p95 (s) |',
            '| --- | ---: | ---: | ---: | ---: | ---: | ---: |'])
        for mode,d in checks['live_agent_and_evaluation']['details'].items():
            cost=d['token_cost']
            def number(value):
                return 'unknown' if value is None else f'{value:,.1f}'
            lines.append(f"| {mode} | {d['correct']}/{d['n']} | {d['unavailable']} | {number(cost['total_tokens'])} | {number(cost['tokens_per_submitted_job'])} | {number(cost['tokens_per_correct_result'])} | {d['p95_seconds']:.2f} |")
        lines.extend(['', 'Token cost includes input/output usage from both roles, repairs and failed jobs.',
            'Exact totals are not invented for calls without provider usage. The per-correct',
            'ratio includes the workload spent on incorrect/failed jobs. Sequential runs share',
            'host resources; latency comparisons are descriptive. Paired family-bootstrap',
            'intervals and all disagreements are retained in the local raw report.'])
    if checks['rag']['passed']:
        d=checks['rag']['details']['structure']
        lines.extend(['','## Retrieval-only evaluation','',
            '| Configuration | Hit@1 | Recall@4 | Warm p95 (ms) |','| --- | ---: | ---: | ---: |'])
        for mode in ('bm25','hybrid','hybrid_reranked'):
            r=d[mode+'_warm_cache']
            lines.append(f"| {mode} | {r['hit_at_1']*100:.2f}% | {r['recall_at_4']*100:.2f}% | {r['p95_seconds']*1000:.2f} |")
        lines.extend(['','16 synthetic retrieval queries, eight document families. Window and paragraph',
            'chunking tie on these short documents; no chunking accuracy advantage is claimed.',
            'Paragraph boundaries are covered by boundary tests. Better document retrieval',
            'must not be substituted for end-to-end SQL correctness.'])
    if checks['finetuning']['passed']:
        d=checks['finetuning']['details']; s=d['summary']; ci=d['paired']['cluster_bootstrap95']
        lines.extend(['','## QLoRA','',
            f"Source-fixture agreement: **{s['baseline']['correct']}/100 → {s['adapter']['correct']}/100**; {d['paired']['fixed']} fixes, {d['paired']['regressed']} regressions.",
            f'Domain-cluster 95% difference interval: **{ci[0]*100:.2f} to {ci[1]*100:.2f} percentage points**.',
            'Fair scoring strips JSON fences in both conditions. The additional duplicated-row',
            'stress check gives 43/89 → 48/89; 11 unscorable fixtures are retained. Its',
            'interval includes zero. The saved adapter exists, but is **not promoted**.',
            'See [the original failure analysis](STRONG_SIGNAL_ACCEPTANCE.md#original-qlora-failure-analysis).'])
    if checks['deployment']['passed']:
        d=checks['deployment']['details']; load=d['load']; serving=d['historical_serving_comparison']
        lines.extend(['','## Local deployment and recovery','',
            f"**{load['successes']}/{load['jobs']} scripted HTTP jobs** at concurrency {load['concurrency']}; p95 **{load['p95_seconds']:.3f} seconds**.",
            'This tests queue/worker delivery, not LLM latency. Seven deployment check groups',
            'pass, including authentication, idempotency, metrics and restart persistence.',
            'The separate gateway test denies direct worker writes and commits an approved',
            'synthetic change exactly once under repeated approval.', '',
            f"Historical serving-profile diagnostic, ten matched cases: p95 **{serving['before']['p95_seconds']:.2f} → {serving['after']['p95_seconds']:.2f} seconds**.",
            'The interrupted baseline and warm-up records remain available; this is not a',
            'single-factor causal claim or a production capacity/SLO measurement.'])
    lines.extend(['','## Reproduction and artifacts','',
        'Protocol, commands and limitations: [Strong Signal acceptance](STRONG_SIGNAL_ACCEPTANCE.md).',
        'Local raw files and the audit hash inventory: `outputs/validation/strong-signal/`.',
        'Docker credentials and control databases remain local and are not part of this summary.',
        'No GitHub, resume or public deployment was updated by this acceptance run.',''])
    args.output.write_text('\n'.join(lines))
    print(args.output)


if __name__ == '__main__':
    main()
