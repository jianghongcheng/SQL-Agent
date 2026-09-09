"""Independent local Docker + real Ollama acceptance with frozen paired cases.

Only this script's generated containers are stopped. Business mounts are read-only.
Oracle/evaluation files are not mounted. No mutation approvals are issued.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import math
import os
from pathlib import Path
import secrets
import socket
import subprocess
import threading
import time
import urllib.request
from urllib.parse import urlparse
import uuid
from sql_agent.acceptance_report import summarize, paired_comparison


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--dataset',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--image',required=True)
    p.add_argument('--embedding',type=Path,required=True)
    p.add_argument('--reranker',type=Path,required=True)
    p.add_argument('--planner',default='qwen3:8b')
    p.add_argument('--reviewer',default='qwen2.5-coder:14b')
    p.add_argument('--keep-alive-seconds',type=int,default=120)
    p.add_argument('--base-url',default='http://127.0.0.1:11434')
    p.add_argument('--modes',nargs='+',choices=['bm25','hybrid','hybrid_reranked'],default=['bm25','hybrid','hybrid_reranked'])
    p.add_argument('--limit',type=int,default=0,help='Smoke-only subset; never presented as a complete evaluation')
    p.add_argument('--no-task-warmup',action='store_true',help='Evaluate each frozen task once; include cold start in latency')
    args=p.parse_args()
    if not 0 <= args.keep_alive_seconds <= 600:
        raise ValueError('keep-alive must be 0..600 seconds')
    if urlparse(args.base_url).hostname not in {'127.0.0.1','localhost'}:
        raise ValueError('this runner only accepts loopback inference endpoints')
    args.dataset=args.dataset.resolve(); args.output=args.output.resolve()
    args.output.mkdir(parents=True,exist_ok=False); args.output.chmod(0o700)
    frozen=json.loads((args.dataset/'evaluation.json').read_text())
    cases=frozen['cases'][:args.limit] if args.limit else frozen['cases']
    root=Path(__file__).resolve().parents[1]
    manifest={'dataset_sha256':hashlib.sha256((args.dataset/'evaluation.json').read_bytes()).hexdigest(),
        'knowledge_sha256':hashlib.sha256((args.dataset/'knowledge.json').read_bytes()).hexdigest(),
        'source_sha256':{str(f.relative_to(root)):hashlib.sha256(f.read_bytes()).hexdigest() for f in (root/'src').rglob('*.py')},
        'image':args.image,'planner':args.planner,'reviewer':args.reviewer,'modes':args.modes,
        'cases':len(cases),'families':len({c['family'] for c in cases}),
        'keep_alive_seconds':args.keep_alive_seconds,
        'scope':frozen['scope'],'concurrency':2,'workers':2,'automatic_publication':False,
        'inference_scope':'Loopback Ollama endpoint; independent API/Worker containers; shared host GPU, not cloud or long-term SLO.',
        'inference_base_url':args.base_url,
        'analysis_plan':'Compare all planned cases, count failures, cluster paired accuracy by task family. Candidate agreement is not a release. No model retuning on outcomes.'}
    manifest['task_warmup'] = not args.no_task_warmup
    def docker(*parts):
        return subprocess.check_output(['docker',*parts],text=True,stderr=subprocess.STDOUT,timeout=120).strip()
    manifest['image_id']=docker('image','inspect',args.image,'--format','{{.Id}}')
    installed=json.loads(docker('run','--rm','--entrypoint','python',args.image,'-c',
        "import hashlib,json,pathlib,sql_agent; p=pathlib.Path(sql_agent.__file__).parent; "
        "print(json.dumps({'src/sql_agent/'+str(f.relative_to(p)):hashlib.sha256(f.read_bytes()).hexdigest() for f in p.rglob('*.py')}))"))
    if installed != manifest['source_sha256']:
        raise ValueError('image code differs from the evaluation checkout; rebuild before running')
    manifest['image_source_verified']=True
    with urllib.request.urlopen(args.base_url+'/api/tags',timeout=10) as response:
        tags=json.load(response)['models']
    manifest['model_metadata']=[m for m in tags if m['name'] in {args.planner,args.reviewer}]
    if len(manifest['model_metadata']) != len({args.planner,args.reviewer}):
        raise ValueError('required local models missing; no automatic pull')
    (args.output/'manifest.json').write_text(json.dumps(manifest,indent=2))
    all_records={}; results={}
    for mode in args.modes:
        out=args.output/mode; out.mkdir(); (out/'control').mkdir()
        project='sql-agent-live-'+uuid.uuid4().hex[:10]
        with socket.socket() as sock:
            sock.bind(('127.0.0.1',0)); port=sock.getsockname()[1]
        token=secrets.token_hex(24)
        env={'SQL_AGENT_MUTATION_CONFIG':'/config/mutations.json','SQL_AGENT_JOB_DB':'/control/jobs.db',
            'SQL_AGENT_PLANNER_BASE_URL':args.base_url,'SQL_AGENT_PLANNER_MODEL':args.planner,
            'SQL_AGENT_PLANNER_MAX_TOKENS':'512','SQL_AGENT_PLANNER_TIMEOUT_SECONDS':'120',
            'SQL_AGENT_REVIEWER_BASE_URL':args.base_url,'SQL_AGENT_REVIEWER_MODEL':args.reviewer,
            'SQL_AGENT_REVIEWER_MAX_TOKENS':'512','SQL_AGENT_REVIEWER_TIMEOUT_SECONDS':'120',
            'SQL_AGENT_PLANNER_KEEP_ALIVE_SECONDS':str(args.keep_alive_seconds),
            'SQL_AGENT_REVIEWER_KEEP_ALIVE_SECONDS':str(args.keep_alive_seconds),
            'SQL_AGENT_KNOWLEDGE_CONFIG':'/config/knowledge.json',
            'SQL_AGENT_RETRIEVAL_MODE':'bm25' if mode=='bm25' else 'hybrid',
            'SQL_AGENT_EMBEDDING_MODEL_PATH':'/models/embedding',
            'SQL_AGENT_EMBEDDING_CACHE':'/control/vectors.db','SQL_AGENT_CHUNKING_MODE':'structure'}
        if mode=='hybrid_reranked': env['SQL_AGENT_RERANKER_MODEL_PATH']='/models/reranker'
        mounts=[str(out/'control')+':/control',str(args.dataset/'business')+':/business:ro',
            str(args.dataset/'mutations.json')+':/config/mutations.json:ro',
            str(args.dataset/'knowledge.json')+':/config/knowledge.json:ro',
            str(args.embedding.resolve())+':/models/embedding:ro',str(args.reranker.resolve())+':/models/reranker:ro']
        common={'image':args.image,'network_mode':'host','volumes':mounts,
            'user':str(os.getuid())+':'+str(os.getgid()),
            'environment':env,'security_opt':['no-new-privileges:true'],'cap_drop':['ALL'],
            'mem_limit':'3g','cpus':2}
        worker={**common,'command':['sql-agent-worker','--poll-seconds','0.1']}
        api={**common,'environment':{**env,'SQL_AGENT_API_KEYS':json.dumps({token:{'name':'acceptance','role':'operator'}})},
            'command':['uvicorn','sql_agent.api:create_app','--factory','--host','127.0.0.1','--port',str(port)]}
        config=out/'compose.json'; config.write_text(json.dumps({'services':{'api':api,'worker1':worker,'worker2':worker}})); config.chmod(0o600)
        command=['docker','compose','-p',project,'-f',str(config)]
        logs=[]; evidence={'project':project,'mode':mode,'scope':manifest['inference_scope']}
        def compose(*parts,check=True):
            result=subprocess.run(command+list(parts),capture_output=True,text=True,timeout=120)
            logs.append((result.stdout+result.stderr).replace(token,'<REDACTED>'))
            if check and result.returncode: raise RuntimeError('compose failed; inspect container.log')
            return result.stdout
        def call(path,payload=None,idem=None):
            headers={'Content-Type':'application/json','x-api-key':token}
            if idem: headers['idempotency-key']=idem
            request=urllib.request.Request('http://127.0.0.1:'+str(port)+path,
                data=json.dumps(payload).encode() if payload is not None else None,headers=headers)
            with urllib.request.urlopen(request,timeout=15) as response:
                body=response.read()
                return json.loads(body) if 'application/json' in response.headers.get('content-type','') else body.decode()
        def trial(case,label):
            tick=time.perf_counter()
            rec={'case_id':case['case_id'],'family':case['family'],'correct':False,'status':'failed','verifier_status':'not_run','has_candidate':False}
            try:
                submitted=call('/v1/requests',{'database_id':case['database_id'],'question':case['question']},label+case['case_id'])
                rec['submit_seconds']=time.perf_counter()-tick; ident=submitted['job']['job_id']
                rec['job_id']=ident
                deadline=time.monotonic()+360
                while time.monotonic()<deadline:
                    job=call('/v1/requests/'+ident)
                    if job['status'] not in ('queued','running'): break
                    time.sleep(.2)
                else: raise TimeoutError('live job deadline')
                result=job.get('result') or (job.get('error') or {}).get('evidence') or {}
                candidate=result.get('candidate_output') or result.get('output')
                rec.update(status=job['status'],has_candidate=candidate is not None,
                    correct=bool(candidate and candidate['rows']==case['expected']['rows'] and candidate['columns']==case['expected']['columns']),
                    verifier_status=result.get('semantic_review',{}).get('status','not_run'),
                    telemetry=result.get('telemetry',{}),
                    relevant_retrieved=all(i in {h.get('parent_id',h['id']) for h in result.get('retrieval',{}).get('hits',[])} for i in case['relevant_ids']),
                    schema_table_recall=len(set(case['required_tables']) & set(result.get('schema_linking',{}).get('selected_tables',[])))/len(case['required_tables']))
                rec['job']=job
            except Exception as exc: rec['error_type']=type(exc).__name__
            rec['seconds']=time.perf_counter()-tick
            (out/(label+case['case_id'].replace(':','_')+'.json')).write_text(json.dumps(rec,indent=2))
            print(json.dumps({'mode':mode,'case':case['case_id'],'label':label,'correct':rec['correct'],'status':rec['status'],'seconds':round(rec['seconds'],2)}),flush=True)
            return rec
        samples=[]; stopped=threading.Event()
        def sample_gpu():
            while not stopped.is_set():
                try:
                    raw=subprocess.check_output(['nvidia-smi','--query-gpu=power.draw,memory.used','--format=csv,noheader,nounits'],text=True,timeout=3)
                    power,memory=map(float,raw.strip().splitlines()[0].split(','))
                    samples.append({'time':time.time(),'power_w':power,'memory_mib':memory})
                except Exception: pass
                stopped.wait(1)
        monitor=threading.Thread(target=sample_gpu,daemon=True)
        try:
            compose('up','-d')
            deadline=time.monotonic()+45
            while True:
                try:
                    call('/health');break
                except OSError:
                    if time.monotonic()>deadline: raise
                    time.sleep(.2)
            monitor.start()
            # Two warm-up jobs are excluded from accuracy and latency summaries.
            if not args.no_task_warmup:
                with ThreadPoolExecutor(max_workers=2) as pool:
                    warm=list(pool.map(lambda c:trial(c,'warm-'),cases[:2]))
                if any('job' not in r for r in warm):
                    raise RuntimeError('warmup transport failed; inspect raw artifacts')
            start=time.perf_counter()
            with ThreadPoolExecutor(max_workers=2) as pool:
                records=list(pool.map(lambda c:trial(c,'eval-'),cases))
            elapsed=time.perf_counter()-start
            all_records[mode]=records
            evidence.update(summary=summarize(records),elapsed_seconds=elapsed,
                terminal_jobs_per_second=sum(r['status'] in ('needs_review','completed') for r in records)/elapsed,
                relevant_document_recall=sum(r.get('relevant_retrieved',False) for r in records)/len(records),
                schema_table_recall=sum(r.get('schema_table_recall',0) for r in records)/len(records))
            (out/'metrics.prom').write_text(call('/metrics'))
            evidence['container_stats']=docker('stats','--no-stream','--format','{{json .}}',*compose('ps','-q').split())
            # Recreate this deployment only. Completed candidate evidence must survive.
            first=next(r for r in records if 'job_id' in r)
            before=call('/v1/requests/'+first['job_id'])['result']
            compose('restart','api','worker1','worker2')
            time.sleep(2)
            evidence['result_survives_restart']=call('/v1/requests/'+first['job_id'])['result']==before
            evidence['business_unchanged']=all(hashlib.sha256((args.dataset/'business'/name).read_bytes()).hexdigest()==sha for name,sha in frozen['database_sha256'].items())
            evidence['run_complete']=True
        except Exception as exc:
            evidence.update(run_complete=False,error_type=type(exc).__name__,error=str(exc).replace(token,'<REDACTED>'))
            raise
        finally:
            stopped.set()
            if monitor.is_alive(): monitor.join(timeout=4)
            energy=sum((b['time']-a['time'])*(a['power_w']+b['power_w'])/2 for a,b in zip(samples,samples[1:]))/3_600_000
            evidence['energy']={'gpu_board_kwh':energy if len(samples)>1 else None,'samples':len(samples),
                'scope':'Whole shared GPU board during warmup and evaluation, excludes CPU/host; not attributable per-job cost.',
                'actual_dollar_cost':None,'cost_scope':'Resource observation only. Cost comparison uses input/output tokens in summary.token_cost.'}
            compose('logs','--no-color','--tail','200',check=False)
            cleanup=subprocess.run(command+['down'],capture_output=True,text=True,timeout=120)
            evidence['containers_removed']=cleanup.returncode==0
            (out/'evidence.json').write_text(json.dumps(evidence,indent=2))
            (out/'gpu.json').write_text(json.dumps(samples))
            (out/'container.log').write_text('\n'.join(logs))
            results[mode]=evidence
            (args.output/'summary.json').write_text(json.dumps(results,indent=2))
    comparisons={}
    for baseline,candidate in zip(args.modes,args.modes[1:]):
        comparisons[baseline+'__vs__'+candidate]=paired_comparison(all_records[baseline],all_records[candidate])
    (args.output/'paired.json').write_text(json.dumps(comparisons,indent=2))
    print(json.dumps({'complete':True,'comparisons':comparisons}),flush=True)


if __name__=='__main__': main()
