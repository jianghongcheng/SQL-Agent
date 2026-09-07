"""Export a completed data-probe comparison with inspectable evidence and SQL."""
import argparse
from collections import Counter
import html
import json
from pathlib import Path


def render(directory):
    manifest = json.loads((directory / 'manifest.json').read_text())
    summary = json.loads((directory / 'summary.json').read_text())
    rows = [json.loads(p.read_text()) for p in sorted(directory.glob('episode_*.json'))]
    keys = [(r['case_id'], r['variant'], r['method'], r['profile'], r['trial']) for r in rows]
    planned = [tuple(r[:5]) for r in manifest['schedule']]
    if len(keys) != len(set(keys)) or Counter(keys) != Counter(planned):
        raise ValueError('incomplete or duplicate episodes')
    if len(rows) != summary['episodes'] or len(rows) != manifest['episodes_planned']:
        raise ValueError('episode count mismatch')
    for key in ('sources_unchanged', 'databases_unchanged', 'all_within_attempt_budget'):
        if summary.get(key) is not True:
            raise ValueError('failed integrity check: ' + key)
    body = ['<h1>SQL Agent：查数据是否有帮助？</h1>',
            '<p>开发集配对回归；不是未见测试或生产准确率。展开每次运行可查看探查、观察与最终 SQL。</p>',
            '<table><tr><th>策略</th><th>正确保留</th><th>错误保留</th><th>停止</th><th>模型调用</th><th>p95 秒</th></tr>']
    for method in manifest['selected_methods']:
        selected = [r for r in rows if r['method'] == method]
        correct = sum(r['accepted_correct'] for r in selected)
        wrong = sum(r['accepted_incorrect'] for r in selected)
        stopped = sum(not r['controller_accepted'] for r in selected)
        calls = sum(len(r['calls']) for r in selected)
        stats = summary['by_method'][method]['all']
        if (correct, wrong, stopped, calls) != (
                stats['accepted_correct'], stats['accepted_incorrect'],
                stats['held_or_stopped'], stats['model_attempts_including_injected_faults']):
            raise ValueError('summary differs from episode records')
        body.append(f'<tr><td>{html.escape(method)}</td><td>{correct}/{len(selected)}</td>'
                    f'<td>{wrong}</td><td>{stopped}</td><td>{calls}</td>'
                    f'<td>{stats["pipeline_p95_ms"]/1000:.2f}</td></tr>')
    observations = [o for r in rows for t in r['pipeline']['result']['agent_trajectory']
                    if t['step'] == 'data_probe' for o in t['observations']]
    body.append('</table><h2>数据库探查</h2><pre>' + html.escape(json.dumps({
        'probe_status': dict(Counter(o['status'] for o in observations)),
        'truncated_outputs': sum(o.get('truncated', False) for o in observations),
        'paired_difference': summary['paired_clean_differences'],
    }, ensure_ascii=False, indent=2)) + '</pre>')
    for i, row in enumerate(rows):
        trace = [t for t in row['pipeline']['result']['agent_trajectory']
                 if t['step'] in ('data_probe', 'propose', 'route')]
        title = f'{i:04d} {row["case_id"]} / {row["method"]} / variant={row["variant"]} / trial={row["trial"]} / correct={row["accepted_correct"]}'
        body.append('<details><summary>' + html.escape(title) + '</summary><pre>'
                    + html.escape(json.dumps(trace, ensure_ascii=False, indent=2)) + '</pre></details>')
    return ('<!doctype html><html lang="zh"><meta charset="utf-8"><title>SQL Data Agent 实验</title>'
            '<style>body{font:16px system-ui;max-width:1000px;margin:40px auto;padding:20px;color:#173042}'
            'td,th{padding:12px;text-align:left;border-bottom:1px solid #ddd}'
            'details{margin:12px 0;padding:12px;background:#f3f6f8}summary{cursor:pointer}'
            'pre{white-space:pre-wrap;overflow-wrap:anywhere}</style>' + ''.join(body) + '</html>')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    directory = parser.parse_args().directory
    (directory / 'report.html').write_text(render(directory))
