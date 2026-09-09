"""Compare frozen live SQL trials; distinguish development repairs from blind evaluation."""
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
from sql_agent.acceptance_report import summarize, paired_comparison


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--baseline', type=Path, required=True)
    p.add_argument('--candidate', type=Path, required=True)
    p.add_argument('--dataset', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--markdown', type=Path, required=True)
    args = p.parse_args()
    read = lambda path: json.loads(path.read_text())
    manifests = [read(d/'manifest.json') for d in (args.baseline, args.candidate)]
    for key in ('dataset_sha256','knowledge_sha256','planner','reviewer','concurrency','workers','keep_alive_seconds','model_metadata'):
        if manifests[0][key] != manifests[1][key]:
            raise ValueError('Unmatched trial setting: '+key)
    evaluation = args.dataset/'evaluation.json'
    if hashlib.sha256(evaluation.read_bytes()).hexdigest() != manifests[0]['dataset_sha256']:
        raise ValueError('Dataset changed')
    cases = {c['case_id']:c for c in read(evaluation)['cases']}
    records = {}; hashes = {}
    for label, directory in (('before',args.baseline),('after',args.candidate)):
        paths = sorted((directory/'bm25').glob('eval-*.json'))
        rows = [read(path) for path in paths]
        if len(rows) != len(cases) or {r['case_id'] for r in rows} != cases.keys():
            raise ValueError('Incomplete or duplicated trial')
        for r in rows:
            result = r['job'].get('result') or {}
            actual = result.get('candidate_output') or result.get('output')
            expected = cases[r['case_id']]['expected']
            verified = bool(actual and actual.get('rows') == expected['rows']
                            and actual.get('columns') == expected['columns'])
            if r['correct'] != verified:
                raise ValueError('Stored correctness differs from external oracle')
        records[label] = rows
        hashes[label] = {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    summaries = {k:summarize(v) for k,v in records.items()}
    families = defaultdict(dict)
    for label, rows in records.items():
        for family in {r['family'] for r in rows}:
            subset = [r for r in rows if r['family']==family]
            families[family][label] = {'n':len(subset),'correct':sum(r['correct'] for r in subset)}
    paired = paired_comparison(records['before'],records['after'])
    a,b = ({r['case_id']:r for r in records[k]} for k in ('before','after'))
    changes = []
    for ident in sorted(a):
        if a[ident]['correct'] != b[ident]['correct']:
            changes.append({'case_id':ident,'change':'fixed' if b[ident]['correct'] else 'regressed',
                'before_sql':(a[ident]['job'].get('result') or {}).get('sql'),
                'after_sql':(b[ident]['job'].get('result') or {}).get('sql')})
    keep = summaries['after']['correct'] > summaries['before']['correct'] and summaries['after']['unavailable'] <= summaries['before']['unavailable']
    report = {'scope':'Previously inspected development set; not blind generalization or production SLO.',
              'summaries':summaries,'families':families,'paired':paired,'changes':changes,'raw_sha256':hashes,
              'retain_development_change':keep,'automatic_release':False}
    with args.output.open('x') as f: json.dump(report,f,indent=2)
    lines = ['# SQL correctness development repair', '', report['scope'], '',
        'The generator now explicitly plans population, output grain, parent preservation, separate one-to-many aggregates, anti-existence and tie handling.',
        'Models, knowledge, frozen cases and retrieval mode remain matched. Historical versus current timing is descriptive on a shared host.', '',
        '| Family | Before | After |','| --- | ---: | ---: |']
    for name,r in sorted(families.items()):
        lines.append(f"| {name} | {r['before']['correct']}/{r['before']['n']} | {r['after']['correct']}/{r['after']['n']} |")
    lines += ['', '| Metric | Before | After |','| --- | ---: | ---: |']
    for title,values in [
        ('Correct', [s['correct'] for s in summaries.values()]),
        ('Unavailable jobs',[s['unavailable'] for s in summaries.values()]),
        ('Total tokens',[s['token_cost']['total_tokens'] for s in summaries.values()]),
        ('Tokens / externally verified correct result',[s['token_cost']['tokens_per_correct_result'] for s in summaries.values()]),
        ('Client p95 seconds',[s['p95_seconds'] for s in summaries.values()])]:
        lines.append(f'| {title} | {values[0]} | {values[1]} |')
    lo,hi=paired['cluster_bootstrap95']
    lines += ['', f"Fixed {paired['fixed']}; regressed {paired['regressed']}. Family-cluster 95% difference interval: {lo*100:.2f} to {hi*100:.2f} percentage points.",
        f"Retain development change under the predeclared rule: {keep}. Human review remains required.", '',
        '## Remaining errors', '',
        'Wrong answers with verifier agreement: '+', '.join(sorted(r['case_id'] for r in records['after'] if not r['correct'] and r['verifier_status']=='agreement'))+'. Agreement is not a correctness gate.',
        'Regressed cases: '+', '.join(c['case_id'] for c in changes if c['change']=='regressed')+'. Family totals can hide offsetting fixes and regressions.',
        'These inspected cases are development evidence. No further prompt selection was performed during this comparison.', '',
        'All changed SQLs and raw record hashes are retained in `outputs/validation/correctness-v1/comparison.json`.',
        'This experiment does not pass the production or generalization gates. See [remaining gates](NEXT_QUALITY_GATES.md).', '']
    args.markdown.write_text('\n'.join(lines))
    print(json.dumps({'summaries':summaries,'paired':paired,'retain_development_change':keep},indent=2))


if __name__ == '__main__':
    main()
