"""Operational rerun after the v1 concurrency failure; no new accuracy claim."""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import shutil
import time
import argparse
from scripts.run_product_acceptance import ROOT,Harness,freeze,save,digest,model_info,stamp


def run(source,out):
    freeze(out)
    manifest=json.loads((out/'manifest.json').read_text())
    manifest['scope']='Operational regression after v1 API polling failure; all questions reused from v1. Not new held-out accuracy.'
    manifest['planned']={'evaluation_episodes':0,'demo_queries':0,'concurrent_real_jobs':4,'api_workers':1,'sql_workers':1}
    manifest['prior_run']=str(source)
    manifest['prior_provider_records_sha256']=digest(source/'provider_requests.json')
    relative=str(Path(__file__).resolve().relative_to(ROOT))
    manifest['source_sha256'][relative]=digest(ROOT/relative)
    target=out/'source_snapshot'/relative;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/relative,target)
    save(out/'manifest.json',manifest)
    h=Harness(out);summary={'completed':False,'started_at':stamp(),'scope':manifest['scope']}
    # Reconstruct provider-format responses from recorded final SQL and usage.
    # No reasoning trace or oracle is supplied; these are fault-drill fixtures.
    for record in json.loads((source/'provider_requests.json').read_text()):
        if record.get('final_content'):
            raw={'message':{'content':record['final_content']},'prompt_eval_count':record.get('prompt_tokens'),
                 'eval_count':record.get('completion_tokens'),'done_reason':'stop'}
            h.cache[record['request_sha256']]=json.dumps(raw).encode()
    try:
        h.start('api');h.start('worker');h.phase='concurrency_4_real_inference'
        cases=json.loads((source/'frozen_cases.json').read_text());started=time.monotonic()
        with ThreadPoolExecutor(max_workers=4) as pool:
            results=list(pool.map(lambda pair:h.run_case(pair[1],f'concurrent_{pair[0]}'),enumerate(cases[:4])))
        elapsed=time.monotonic()-started
        summary['concurrency']={'requests':4,'completed':len(results),'sql_workers':1,'correct':sum(r['correct'] for r in results),
                                'wall_seconds':elapsed,'completed_jobs_per_minute':4/elapsed*60,
                                'client_latency_ms':[r['client_submit_to_result_ms'] for r in results]}
        h.faults(next(c for c in cases if c['case_id']=='q0_data0'))
        summary['completed']=True
    except Exception as exc:
        summary['error']={'type':type(exc).__name__,'message':str(exc)}
        raise
    finally:
        h.close();summary['completed_at']=stamp()
        summary['sources_unchanged']=all(digest(ROOT/p)==sha for p,sha in manifest['source_sha256'].items())
        summary['inputs_unchanged']=all(digest(out/p)==sha for p,sha in manifest['input_sha256'].items())
        summary['model_unchanged']=model_info()['digest']==manifest['model']['digest']
        save(out/'summary.json',summary);print(json.dumps(summary,indent=2),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--source',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    a=parser.parse_args();run(a.source.resolve(),a.output.resolve())
