"""Descriptive matched-case latency comparison; does not hide incomplete trials."""
import argparse
import hashlib
import json
import math
from pathlib import Path


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--before',type=Path,required=True)
    p.add_argument('--after',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    conditions={}; manifests={}; hashes={}
    for name,path in [('before',args.before),('after',args.after)]:
        manifests[name]=json.loads((path.parent/'manifest.json').read_text())
        records={}; hashes[name]={}
        for f in sorted(path.glob('eval-*.json')):
            record=json.loads(f.read_text())
            if record['case_id'] in records: raise ValueError('duplicate case')
            records[record['case_id']]=record; hashes[name][f.name]=hashlib.sha256(f.read_bytes()).hexdigest()
        conditions[name]=records
    for key in ('dataset_sha256','knowledge_sha256','image_id','planner','reviewer','concurrency'):
        if manifests['before'][key]!=manifests['after'][key]: raise ValueError('not matched: '+key)
    ids=sorted(conditions['before'].keys() & conditions['after'].keys())
    if not ids: raise ValueError('no matched cases')
    summary={}
    for name,records in conditions.items():
        times=sorted(records[i]['seconds'] for i in ids)
        load=[sum(s.get('model_load_ms_observed',0) for s in records[i].get('telemetry',{}).get('stages',{}).values()) for i in ids]
        summary[name]={'n_matched':len(ids),'n_observed_total':len(records),
            'p50_seconds':times[math.ceil(.5*len(times))-1],'p95_seconds':times[math.ceil(.95*len(times))-1],
            'correct':sum(records[i]['correct'] for i in ids),
            'mean_model_load_ms_observed':sum(load)/len(load),
            'jobs_without_telemetry':sum(not records[i].get('telemetry') for i in ids)}
    result={'summary':summary,'matched_case_ids':ids,'raw_sha256':hashes,
        'median_latency_ratio_before_over_after':summary['before']['p50_seconds']/summary['after']['p50_seconds'],
        'scope':'Diagnostic serving-profile comparison on the intersection of saved cases. Before trial was interrupted; not a completed accuracy comparison or production SLO.',
        'changed':'Independent inference process, 4096 context, two resident models, one parallel request/model and flash attention. Not a single-factor keep-alive ablation.',
        'cold_start_excluded':'Warm-up records remain in both source directories and must be reported separately.'}
    with args.output.open('x') as stream: json.dump(result,stream,indent=2)
    print(json.dumps({k:v for k,v in result.items() if k!='raw_sha256'},indent=2))


if __name__=='__main__': main()
