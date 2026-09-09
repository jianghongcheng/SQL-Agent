"""Reproducible paired statistics on saved, runtime-aligned QLoRA pilot scores."""
import argparse
import hashlib
import json
import math
from pathlib import Path
from sql_agent.acceptance_report import paired_comparison


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--dataset',type=Path,required=True)
    p.add_argument('--run',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    dataset=json.loads(args.dataset.read_text())
    manifest=json.loads((args.run/'manifest.json').read_text())
    if hashlib.sha256(args.dataset.read_bytes()).hexdigest()!=manifest['dataset_sha256']:
        raise ValueError('frozen dataset hash differs')
    path=args.run/'runtime_aligned_scores.json'
    scored=json.loads(path.read_text())
    domains={r['id']:r['domain'] for r in dataset['splits']['test']}
    rows={}; speed={}
    for name in ('baseline','adapter'):
        raw=args.run/(name+'.json')
        if hashlib.sha256(raw.read_bytes()).hexdigest()!=scored['raw_sha256'][name]:
            raise ValueError('raw generations changed')
        values=json.loads(raw.read_text())
        rows[name]=[{'case_id':str(r['id']),'family':domains[r['id']],'correct':r['correct']}
                    for r in scored['records'][name]]
        if {r['id'] for r in scored['records'][name]}!=set(domains):
            raise ValueError('incomplete frozen test scores')
        elapsed=sum(r['batch_seconds']/r['batch_size'] for r in values)
        latencies=sorted(r['batch_seconds'] for r in values)
        speed[name]={'generation_seconds':elapsed,'queries_per_second':len(values)/elapsed,
            'p95_batch_seconds':latencies[math.ceil(.95*len(latencies))-1],
            'scope':'Batched local model.generate wall time; not request or deployed Agent latency.'}
    report={'protocol':scored['protocol_note'],'scores_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
        'dataset_sha256':manifest['dataset_sha256'],'summary':scored['summary'],
        'paired':paired_comparison(rows['baseline'],rows['adapter']),
        'generation_timing':speed,'training':json.loads((args.run/'training.json').read_text()),
        'deployment_decision':'not_promoted',
        'reason':'Single-fixture source labels, no human semantic audit; uncertainty and regressions retained. Pilot is not proof of deployed Agent improvement.'}
    with args.output.open('x') as stream: json.dump(report,stream,indent=2)
    print(json.dumps({'paired':report['paired'],'timing':speed,'deployment_decision':'not_promoted'},indent=2))


if __name__=='__main__': main()
