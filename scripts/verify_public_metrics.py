"""Recompute the published development metrics without LLMs or private artifacts."""
import hashlib
import json
from pathlib import Path
from scripts.holdout_metrics import metrics
from sql_agent.acceptance_report import paired_comparison


def main():
    root=Path(__file__).resolve().parents[1]/'docs/evidence/2026-09-09'
    read=lambda p:json.loads(p.read_text())
    for name,digest in read(root/'sha256.json').items():
        if hashlib.sha256((root/name).read_bytes()).hexdigest()!=digest:raise ValueError('Public evidence hash differs: '+name)
    report=read(root/'metrics.json');records={}
    for name in ('before','after'):
        rows=read(root/(name+'.json'))
        if len(rows)!=48 or len({r['case_id'] for r in rows})!=48:raise ValueError('Incomplete records')
        for r in rows:
            actual=r['candidate'];expected=r['expected']
            correct=bool(actual and actual['columns']==expected['columns'] and actual['rows']==expected['rows'])
            if r['correct']!=correct:raise ValueError('Oracle mismatch: '+r['case_id'])
        if metrics(rows)!=report['summaries'][name]:raise ValueError('Recomputed metrics differ: '+name)
        records[name]=rows
    if paired_comparison(records['before'],records['after'])!=report['paired']:raise ValueError('Paired statistics differ')
    print('Verified: 96 public records, metric denominators, token costs, latency, paired statistics and hashes.')


if __name__=='__main__':main()
