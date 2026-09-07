"""Exercise stdio MCP -> authenticated API -> worker, without model inference."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.request
import uuid

ROOT=Path(__file__).resolve().parents[1]
BASE='http://127.0.0.1:8765'


def exchange(messages,key='123'):
    env={**os.environ,'PYTHONPATH':str(ROOT/'src'),'RADMEASURE_API_URL':BASE,'RADMEASURE_MCP_API_KEY':key}
    result=subprocess.run([sys.executable,'-m','geomed_copilot.mcp_server'],
        input='\n'.join(json.dumps(m) for m in messages)+'\n',text=True,
        capture_output=True,env=env,timeout=30)
    if result.returncode:raise RuntimeError(result.stderr)
    replies=[json.loads(line) for line in result.stdout.splitlines()]
    assert len(replies)==len(messages)
    return replies


def message(identifier,method,params=None):
    value={'jsonrpc':'2.0','id':identifier,'method':method}
    if params is not None:value['params']=params
    return value


def initialize():
    return message(1,'initialize',{'protocolVersion':'2024-11-05','capabilities':{},
                                  'clientInfo':{'name':'local-acceptance','version':'1'}})


def main():
    output=ROOT/'runtime/local-demo/mcp-acceptance.json'
    report={'passed':False,'started_at':datetime.now(timezone.utc).isoformat(),
            'scope':'Local raw JSON-RPC stdio client; not a certification of third-party client compatibility.'}
    try:
        submit={'name':'submit_sql_task','arguments':{'task_id':'blocked_stale',
                                                     'idempotency_key':'mcp-validation-'+uuid.uuid4().hex}}
        replies=exchange([initialize(),message(2,'tools/list'),message(3,'tools/call',submit),message(4,'tools/call',submit)])
        assert replies[0]['result']['protocolVersion']=='2024-11-05'
        assert {t['name'] for t in replies[1]['result']['tools']}=={'list_sql_tasks','submit_sql_task','get_sql_job'}
        first=replies[2]['result']['structuredContent']['job']['job_id']
        assert replies[3]['result']['structuredContent']['job']['job_id']==first
        report['job_id']=first
        # A single worker can be serving a bounded inference job ahead of us.
        # This is an acceptance timeout, not a queue-latency SLO.
        wait_started=time.monotonic()
        deadline=wait_started+180
        while True:
            request=urllib.request.Request(BASE+'/v1/jobs/'+first,headers={'x-api-key':'123'})
            with urllib.request.urlopen(request,timeout=5) as response:job=json.load(response)
            if job['status'] not in {'queued','running'}:break
            if time.monotonic()>deadline:raise TimeoutError('worker did not settle the blocked task')
            time.sleep(.2)
        report['observed_wait_seconds']=round(time.monotonic()-wait_started,3)
        got=exchange([initialize(),message(2,'tools/call',{'name':'get_sql_job','arguments':{'job_id':first}})])
        result=got[1]['result']['structuredContent']
        assert result['job_id']==first and result['status']=='needs_review'
        assert result['result']['release']['reason']=='data_quality_blocked'
        assert result['result']['telemetry']['calls']==0
        refused=exchange([initialize(),message(2,'tools/call',{'name':'list_sql_tasks','arguments':{}}),message(3,'ping')],key='invalid-local-key')
        assert refused[1]['result']['isError'] is True and refused[2]['result']=={}
        report.update(passed=True,checks=['stdio initialization','tool discovery','authenticated submission',
            'duplicate submission deduplicated','worker blocks stale data before model calls',
            'MCP reads the persisted job','invalid API key rejected without terminating server'])
    except Exception as exc:
        report['error']={'type':type(exc).__name__,'message':str(exc)[:1000]}
        raise
    finally:
        report['completed_at']=datetime.now(timezone.utc).isoformat()
        output.parent.mkdir(parents=True,exist_ok=True)
        history=output.parent/'mcp-runs'
        history.mkdir(exist_ok=True)
        (history/(datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'.json')).write_text(json.dumps(report,indent=2))
        output.write_text(json.dumps(report,indent=2));print(json.dumps(report),flush=True)


if __name__=='__main__':main()
