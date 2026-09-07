"""Exercise the running local API and worker; synthetic demo acceptance only."""
import json,time,urllib.request,uuid
from pathlib import Path

BASE='http://127.0.0.1:8765'

def call(path,data=None,key='123',idem=None):
 headers={'x-api-key':key,'content-type':'application/json'}
 if idem:headers['idempotency-key']=idem
 request=urllib.request.Request(BASE+path,headers=headers,data=json.dumps(data).encode() if data is not None else None)
 with urllib.request.urlopen(request,timeout=10) as response:return json.load(response)


def main():
 output=Path('runtime/local-demo/acceptance.json');records=[]
 for task in call('/v1/tasks')['tasks']:
  tid=task['task_id'];idem=str(uuid.uuid4());payload={'task_id':tid}
  first=call('/v1/jobs',payload,idem=idem);second=call('/v1/jobs',payload,idem=idem)
  assert first['job']['job_id']==second['job']['job_id'] and not second['created']
  jid=first['job']['job_id'];deadline=time.monotonic()+180
  while True:
   job=call('/v1/jobs/'+jid)
   if job['status'] not in ('queued','running'):break
   if time.monotonic()>deadline:raise TimeoutError(jid)
   time.sleep(.5)
  r=job['result'];expected={'net_revenue':17000,'gross_revenue':18000,'approved_refunds':1000}
  telemetry=r['telemetry']
  assert telemetry['pipeline_elapsed_ms'] >= 0 and telemetry['monetary_cost'] is None
  if tid in expected:
   passed=job['status']=='completed' and r['output']['rows']==[[expected[tid]]]
   assert telemetry['calls'] > 0 and telemetry['prompt_tokens_observed'] > 0
  elif tid.startswith('blocked_'):
   passed=job['status']=='needs_review' and r['source_health']['blocked'] and r['output'] is None
   assert telemetry['calls'] == 0
  else:
   passed=job['status']=='needs_review' and r['output'] is None
   review=call('/v1/jobs/'+jid+'/review',{'decision':'reject','notes':'Automated demo acceptance: request a registered metric before release.'})
   assert review['status']=='review_rejected'
  record={'task_id':tid,'job_id':jid,'status':job['status'],'passed':passed,'result':r,'events':call('/v1/jobs/'+jid+'/events')['events']}
  records.append(record);print(json.dumps({'task':tid,'status':job['status'],'passed':passed}),flush=True)
 output.write_text(json.dumps({'n':len(records),'passed':sum(r['passed'] for r in records),'records':records},indent=2))
 assert all(r['passed'] for r in records),'See acceptance.json for retained failures'

if __name__=='__main__':main()
