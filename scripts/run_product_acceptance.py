"""Freeze then run small real-service acceptance; preserve every episode and fault.

Normal evaluation uses real Ollama. Fault drills explicitly replay a recorded
provider response to isolate transport, queue and process recovery from inference.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
import os
from pathlib import Path
import random
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request

from contractsql.data_agent import DataContract
from scripts.commerce_acceptance_cases import QUESTIONS,COLUMNS,DEMO_QUESTIONS,fixture,create_database,oracle
ROOT=Path(__file__).resolve().parents[1]
KEY='acceptance-local-only'
MODEL='qwen3:14b'


def stamp():return datetime.now(timezone.utc).isoformat()
def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def save(path,value):Path(path).write_text(json.dumps(value,indent=2,ensure_ascii=False))
def http(url,body=None,key=None,timeout=180):
    headers={'Content-Type':'application/json'}
    if key:headers['x-api-key']=key
    request=urllib.request.Request(url,data=None if body is None else json.dumps(body).encode(),headers=headers)
    with urllib.request.urlopen(request,timeout=timeout) as r:return json.load(r)
def free_port():
    with socket.socket() as s:s.bind(('127.0.0.1',0));return s.getsockname()[1]
def model_info():return next(m for m in http('http://127.0.0.1:11434/api/tags')['models'] if m['name']==MODEL)


def freeze(out):
    out.mkdir(parents=True,exist_ok=False)
    (out/'instances').mkdir()
    taskrows=[];cases=[]
    for index,seed in enumerate((2041,4093)):
        data=fixture(seed);path=out/'instances'/f'{seed}.sqlite';create_database(path,data)
        taskrows.append({'task_id':f'eval_{index}','question':QUESTIONS[0],'database':str(path.relative_to(out)),
                         'contract':asdict(DataContract((),dynamic_columns=True,max_rows=200))})
        for q,text in enumerate(QUESTIONS):cases.append({'case_id':f'q{q}_data{index}','task_id':f'eval_{index}','question':text,'expected':oracle(q,data)})
    data=fixture(17);path=out/'instances/demo.sqlite';create_database(path,data)
    taskrows.append({'task_id':'demo','question':DEMO_QUESTIONS[0],'database':'instances/demo.sqlite',
                     'contract':asdict(DataContract((),dynamic_columns=True,max_rows=200))})
    random.Random(811).shuffle(cases)
    save(out/'tasks.json',taskrows);save(out/'frozen_cases.json',cases)
    source_files=list((ROOT/'src').rglob('*.py'))+[Path(__file__),ROOT/'scripts/commerce_acceptance_cases.py']
    source_hashes={str(p.relative_to(ROOT)):digest(p) for p in source_files}
    for relative in source_hashes:
        target=out/'source_snapshot'/relative;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/relative,target)
    manifest={'frozen_at':stamp(),'scope':'6 newly authored questions x 2 synthetic datasets; one first run per question/instance. No benchmark or production claim.',
              'model':model_info(),'profile':{'thinking':True,'max_tokens':8192,'timeout_seconds':120,'context':16384,'seed':917,'sql_rounds':3},
              'planned':{'evaluation_episodes':12,'demo_queries':3,'concurrent_real_jobs':4,'api_workers':1,'sql_workers':1},
              'source_sha256':source_hashes,'input_sha256':{str(p.relative_to(out)):digest(p) for p in [out/'tasks.json',out/'frozen_cases.json',*sorted((out/'instances').glob('*.sqlite'))]},
              'grading':'Exact ordered columns/rows against Python oracles, including duplicates and NULL. Candidate requires review; no automatic semantic proof.',
              'fault_scope':'SIGKILL during an in-flight provider request; API restart with queued job; concurrent duplicate submissions; first request timeout then cached response; persistent timeout. Recorded provider responses isolate infrastructure; fault trials are not new model accuracy samples.',
              'performance_scope':'Client monotonic time from before HTTP submission to first observed terminal response, including queue, polling and network; polling interval 0.1s. GPU samples are device-wide, not per-job attribution.'}
    save(out/'manifest.json',manifest);print('Frozen acceptance inputs: '+str(out),flush=True)


class Harness:
    def __init__(self,out):
        self.out=out;self.manifest=json.loads((out/'manifest.json').read_text());self.base='http://127.0.0.1:'+str(free_port())
        self.procs={};self.phase='setup';self.proxy_mode='normal';self.proxy_count=0;self.requests=[];self.cache={};self.lock=threading.Lock()
        self.arrived=threading.Event();self.unblock=threading.Event();self.resources=[];self.stopped=threading.Event()
        owner=self
        class Proxy(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_POST(self):
                body=self.rfile.read(int(self.headers['Content-Length']));payload=json.loads(body);key=hashlib.sha256(body).hexdigest()
                with owner.lock:
                    mode=owner.proxy_mode;owner.proxy_count+=1;number=owner.proxy_count
                    event={'at':stamp(),'phase':owner.phase,'mode':mode,'request':number,'request_sha256':key,'prompt':payload['messages'][0]['content']}
                    owner.requests.append(event)
                try:
                    if mode=='block_once' and number==1:
                        owner.arrived.set();owner.unblock.wait(15)
                    if mode=='timeout_all' or (mode=='timeout_once' and number==1):time.sleep(1)
                    if mode=='normal':
                        req=urllib.request.Request('http://127.0.0.1:11434/api/chat',data=body,headers={'Content-Type':'application/json'})
                        with urllib.request.urlopen(req,timeout=180) as r:raw=r.read()
                        owner.cache[key]=raw
                    else:
                        raw=owner.cache.get(key)
                        if raw is None:raise RuntimeError('No recorded response for exact request')
                    parsed=json.loads(raw);event.update(completed_at=stamp(),response_source='live_ollama' if mode=='normal' else 'recorded_response',final_content=parsed['message']['content'],prompt_tokens=parsed.get('prompt_eval_count'),completion_tokens=parsed.get('eval_count'))
                    self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(raw)
                except (BrokenPipeError,ConnectionResetError):event['client_disconnected']=True
                except Exception as exc:
                    event['error']=str(exc)
                    try:self.send_error(502)
                    except OSError:pass
        self.proxy=ThreadingHTTPServer(('127.0.0.1',0),Proxy)
        threading.Thread(target=self.proxy.serve_forever,daemon=True).start()
        self.env={**os.environ,'PYTHONPATH':str(ROOT/'src')+':'+str(ROOT),'CONTRACTSQL_JOB_DB':str(out/'jobs.sqlite'),
                  'CONTRACTSQL_SQL_TASKS':str(out/'tasks.json'),'CONTRACTSQL_PLANNER_PROVIDER':'ollama',
                  'CONTRACTSQL_PLANNER_BASE_URL':'http://127.0.0.1:'+str(self.proxy.server_port),'CONTRACTSQL_PLANNER_MODEL':MODEL,
                  'CONTRACTSQL_SQL_GENERATION_FORMAT':'sql','CONTRACTSQL_PLANNER_THINKING':'true','CONTRACTSQL_PLANNER_MAX_TOKENS':'8192',
                  'CONTRACTSQL_PLANNER_TIMEOUT_SECONDS':'120','CONTRACTSQL_API_KEYS':json.dumps({KEY:{'name':'acceptance','role':'admin'}})}
        for key in ('CONTRACTSQL_DATABASE_URL','CONTRACTSQL_LOCAL_DEMO'):self.env.pop(key,None)
        self.sampler=threading.Thread(target=self.sample_resources,daemon=True);self.sampler.start()

    def sample_resources(self):
        while not self.stopped.is_set():
            row={'at':stamp(),'phase':self.phase,'processes':{}}
            for name,proc in list(self.procs.items()):
                try:
                    lines=Path(f'/proc/{proc.pid}/status').read_text().splitlines()
                    rss=next(int(s.split()[1]) for s in lines if s.startswith('VmRSS:'))
                    stat=Path(f'/proc/{proc.pid}/stat').read_text().split()
                    row['processes'][name]={'pid':proc.pid,'rss_kib':rss,'cpu_seconds':(int(stat[13])+int(stat[14]))/os.sysconf('SC_CLK_TCK')}
                except (OSError,StopIteration):pass
            try:
                text=subprocess.check_output(['nvidia-smi','--query-gpu=memory.used,utilization.gpu','--format=csv,noheader,nounits'],text=True,timeout=2).strip()
                row['gpu_device_wide']=text
            except Exception as exc:row['gpu_observation_error']=type(exc).__name__
            self.resources.append(row);self.stopped.wait(1)

    def start(self,name,timeout=120):
        if name=='api':cmd=[sys.executable,'-m','uvicorn','contractsql.api:create_app','--factory','--host','127.0.0.1','--port',self.base.rsplit(':',1)[1]]
        else:cmd=[sys.executable,'-c','from contractsql.worker import Worker; from contractsql.backends import job_repository_from_env; from contractsql.pipeline import JobPipeline; Worker(job_repository_from_env(),JobPipeline(),lease_seconds=3).run_forever(0.05)']
        env={**self.env,'CONTRACTSQL_PLANNER_TIMEOUT_SECONDS':str(timeout)}
        with (self.out/(name+'.log')).open('ab') as log:self.procs[name]=subprocess.Popen(cmd,cwd=ROOT,env=env,stdout=log,stderr=log,start_new_session=True)
        if name=='api':
            end=time.monotonic()+10
            while True:
                try:http(self.base+'/health',timeout=1);break
                except OSError:
                    if time.monotonic()>end:raise TimeoutError('API startup')
                    time.sleep(.1)

    def stop(self,name,kill=False):
        proc=self.procs.pop(name,None)
        if proc is not None:
            proc.kill() if kill else proc.terminate()
            try:proc.wait(timeout=5)
            except subprocess.TimeoutExpired:proc.kill();proc.wait(timeout=5)

    def mode(self,value):
        with self.lock:self.proxy_mode=value;self.proxy_count=0

    def submit(self,case,ident):
        req=urllib.request.Request(self.base+'/v1/jobs',data=json.dumps({'task_id':case['task_id'],'question':case['question']}).encode(),headers={'Content-Type':'application/json','x-api-key':KEY,'idempotency-key':ident})
        with urllib.request.urlopen(req,timeout=10) as r:return json.load(r)

    def get(self,job):return http(self.base+'/v1/jobs/'+job,key=KEY,timeout=10)
    def wait(self,job,seconds=450):
        end=time.monotonic()+seconds
        while True:
            result=self.get(job)
            if result['status'] not in {'queued','running'}:return result
            if time.monotonic()>end:raise TimeoutError('job did not finish: '+job)
            time.sleep(.1)
    def evidence(self,job):return http(self.base+'/v1/jobs/'+job+'/events',key=KEY,timeout=10)
    def run_case(self,case,label):
        started=time.monotonic();submitted=self.submit(case,label);job=self.wait(submitted['job']['job_id'])
        elapsed=(time.monotonic()-started)*1000
        result=job.get('result') or {};actual=result.get('candidate_output') or result.get('output')
        record={'label':label,'case':case,'client_submit_to_result_ms':round(elapsed,3),'correct':actual==case.get('expected') if 'expected' in case else None,'job':job,'events':self.evidence(job['job_id'])}
        save(self.out/(label+'.json'),record);print(json.dumps({'finished':label,'status':job['status'],'correct':record['correct'],'end_to_end_ms':record['client_submit_to_result_ms']}),flush=True)
        return record

    def faults(self,case):
        records={};self.phase='faults_recorded_provider_response';self.stop('worker');self.mode('block_once');self.arrived.clear();self.unblock.clear();self.start('worker')
        started=time.monotonic();job=self.submit(case,'fault_kill')['job']['job_id']
        assert self.arrived.wait(10),'worker did not reach model request'
        before=self.get(job);assert before['status']=='running';self.stop('worker',kill=True);self.unblock.set()
        self.mode('cache');self.start('worker');after=self.wait(job,20)
        assert after['attempts']==2 and after['status']=='needs_review'
        assert after['result']['candidate_output']==case['expected']
        records['kill_worker']={'passed':True,'client_submit_to_result_ms':(time.monotonic()-started)*1000,'before':before,'after':after,'events':self.evidence(job)}
        self.stop('worker');queued=self.submit(case,'fault_api_restart')['job']['job_id'];self.stop('api');self.start('api')
        assert self.get(queued)['status']=='queued';self.start('worker');restored=self.wait(queued,20)
        assert restored['status']=='needs_review';records['api_restart']={'passed':True,'job':restored,'events':self.evidence(queued)}
        with ThreadPoolExecutor(max_workers=8) as pool:duplicates=list(pool.map(lambda _:self.submit(case,'fault_duplicates'),range(8)))
        ids={d['job']['job_id'] for d in duplicates};assert len(ids)==1 and sum(d['created'] for d in duplicates)==1
        duplicate=self.wait(next(iter(ids)),20);events=self.evidence(duplicate['job_id'])
        assert sum(e['event_type']=='submitted' for e in events['events'])==1
        reviewed=http(self.base+'/v1/jobs/'+duplicate['job_id']+'/review',{'decision':'reject','notes':'Acceptance review: duplicate submission must keep one audit trail.'},KEY)
        assert reviewed['status']=='review_rejected';records['duplicates']={'passed':True,'requests':8,'created_jobs':1,'job':reviewed,'events':self.evidence(duplicate['job_id'])}
        self.stop('worker');self.mode('timeout_once');self.start('worker',timeout=.25)
        recovery=self.run_case(case,'fault_timeout_once');assert recovery['correct'] and recovery['job']['result']['telemetry']['retries']==1
        records['transient_timeout']={'passed':True,'evidence':'fault_timeout_once.json'}
        self.stop('worker');self.mode('timeout_all');self.start('worker',timeout=.25)
        exhausted=self.run_case(case,'fault_timeout_all');result=exhausted['job']['result']
        assert exhausted['job']['status']=='needs_review' and result['candidate_output'] is None and result['telemetry']['calls']==3
        records['persistent_timeout']={'passed':True,'evidence':'fault_timeout_all.json','scope':'bounded stop, not successful recovery'}
        save(self.out/'faults.json',records)

    def close(self):
        self.stop('worker');self.stop('api');self.stopped.set();self.sampler.join(timeout=4);self.proxy.shutdown();self.proxy.server_close()
        save(self.out/'provider_requests.json',self.requests);save(self.out/'resources.json',self.resources)


def run(out):
    manifest=json.loads((out/'manifest.json').read_text())
    for relative,sha in manifest['source_sha256'].items():assert digest(ROOT/relative)==sha,'source changed after freeze: '+relative
    for relative,sha in manifest['input_sha256'].items():assert digest(out/relative)==sha,'input changed: '+relative
    with (out/'started.json').open('x') as f:json.dump({'started_at':stamp()},f)
    harness=Harness(out);summary={'completed':False,'started_at':stamp()}
    try:
        harness.start('api');harness.start('worker');cases=json.loads((out/'frozen_cases.json').read_text())
        harness.phase='frozen_evaluation';results=[harness.run_case(c,f'evaluation_{i:02}') for i,c in enumerate(cases)]
        summary['evaluation']={'questions':6,'instances':2,'episodes':len(results),'correct':sum(r['correct'] for r in results),'incorrect_or_stopped':sum(not r['correct'] for r in results),'automatic_releases':sum(r['job'].get('result',{}).get('release',{}).get('approved',False) for r in results)}
        harness.phase='three_output_forms';demos=[];data=fixture(17)
        expected=[[[sum(o[3] for o in data['orders'])]],[[o[0],o[2],o[3]] for o in data['orders']]]
        months={}
        for o in data['orders']:months[o[2][:7]]=months.get(o[2][:7],0)+o[3]
        expected.append([[m,v] for m,v in sorted(months.items())])
        for i,q in enumerate(DEMO_QUESTIONS):
            r=harness.run_case({'task_id':'demo','question':q},f'demo_{i}')
            candidate=r['job']['result']['candidate_output'];demos.append({'question':q,'rows_correct':bool(candidate and candidate['rows']==expected[i]),'end_to_end_ms':r['client_submit_to_result_ms']})
        summary['three_output_forms']=demos
        harness.phase='concurrency_4_real_inference';start=time.monotonic()
        with ThreadPoolExecutor(max_workers=4) as pool:concurrent=list(pool.map(lambda pair:harness.run_case(pair[1],f'concurrent_{pair[0]}'),enumerate(cases[:4])))
        elapsed=time.monotonic()-start
        summary['concurrency']={'requests':4,'sql_workers':1,'wall_seconds':elapsed,'completed_jobs_per_minute':4/elapsed*60,'correct':sum(r['correct'] for r in concurrent),'client_latency_ms':[r['client_submit_to_result_ms'] for r in concurrent]}
        real=results+concurrent
        times=sorted(r['client_submit_to_result_ms'] for r in real)
        summary['real_evaluation_and_concurrent_latency']={'scope':'12 evaluation plus 4 repeated concurrent jobs; demo episodes listed separately','p50_ms':times[math.ceil(.5*len(times))-1],'p95_ms':times[math.ceil(.95*len(times))-1]}
        fault_case=next(c for c in cases if c['case_id']=='q0_data0');harness.faults(fault_case)
        summary['completed']=True
    except Exception as exc:
        summary['error']={'type':type(exc).__name__,'message':str(exc)}
        raise
    finally:
        harness.close();summary['completed_at']=stamp()
        summary['sources_unchanged']=all(digest(ROOT/p)==sha for p,sha in manifest['source_sha256'].items())
        summary['inputs_unchanged']=all(digest(out/p)==sha for p,sha in manifest['input_sha256'].items())
        summary['model_unchanged']=model_info()['digest']==manifest['model']['digest']
        save(out/'summary.json',summary);print(json.dumps(summary,indent=2),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['freeze','run']);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();out=args.output.resolve()
    freeze(out) if args.action=='freeze' else run(out)
