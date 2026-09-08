"""Live-model, synthetic business-context and preflight demonstration."""
import argparse
from dataclasses import asdict
from datetime import datetime,timezone,timedelta
import json
from pathlib import Path
import sqlite3

from contractsql.business_context import MetricDefinition,QualityCheck
from contractsql.data_agent import DataContract,ContractSQLPlanner
from contractsql.planner import OllamaPlannerModel
from contractsql.sql_config import SQLTask,SQLTaskRegistry
from contractsql.pipeline import JobPipeline
from contractsql.jobs import SqliteJobRepository
from contractsql.worker import Worker
from contractsql.execution_record import digest
from scripts.validate_live_sql_agent import RecordingModel


def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);args=p.parse_args();args.output.mkdir(parents=True,exist_ok=False)
 results=[]
 for scenario in ['healthy_1','healthy_2','healthy_3','stale','invalid_amount','missing_freshness']:
  path=(args.output/(scenario+'.sqlite')).resolve();db=sqlite3.connect(path)
  db.executescript('CREATE TABLE orders(id INTEGER PRIMARY KEY, amount REAL); CREATE TABLE refunds(order_id INTEGER, amount REAL, status TEXT); CREATE TABLE ingestion_log(completed_at TEXT); INSERT INTO orders VALUES(1,100),(2,80); INSERT INTO refunds VALUES(1,10,"approved"),(1,20,"pending");')
  now=datetime.now(timezone.utc);stamp=now-timedelta(days=3) if scenario=='stale' else now
  if scenario!='missing_freshness':db.execute('INSERT INTO ingestion_log VALUES(?)',(stamp.isoformat(),))
  if scenario=='invalid_amount':db.execute('UPDATE orders SET amount=NULL WHERE id=1')
  db.commit();db.close()
  definitions=(MetricDefinition('net_revenue',('net revenue',),'Net revenue equals the sum of all order amounts minus only approved refund amounts. Pending refunds are excluded. Orders without approved refunds still contribute their full order amount; missing approved refunds count as zero. Each order amount is counted once even when an order has several refunds. Report the overall total.','demo-commerce-policy','1',True),)
  checks=(QualityCheck('amount_required','SELECT COUNT(*) FROM orders WHERE amount IS NULL','violation_count',0,'blocking','Demo business rule: order amount must be present.'),QualityCheck('daily_ingestion','SELECT MAX(completed_at) FROM ingestion_log','freshness',24,'blocking','Demo operating policy: ingest at least daily; 24h is a declared demo budget, not an industry standard.'))
  task=SQLTask('net_revenue','What is our net revenue?',DataContract(('net_revenue',),max_rows=1),path,definitions,checks)
  config=[{'task_id':task.task_id,'question':task.question,'contract':asdict(task.contract),'database':path.name,'definitions':[asdict(d) for d in definitions],'quality_checks':[asdict(c) for c in checks]}]
  (args.output/(scenario+'_tasks.json')).write_text(json.dumps(config,indent=2))
  model=RecordingModel(OllamaPlannerModel('http://127.0.0.1:11434','qwen3:8b'))
  repo=SqliteJobRepository(args.output/(scenario+'_jobs.sqlite'));job,_=repo.submit('sql_analysis',{'task_id':task.task_id,'_business_context_sha256':task.context_sha256},scenario)
  worker=Worker(repo,JobPipeline(SQLTaskRegistry((task,)),ContractSQLPlanner(model)));worker.run_once();result=repo.get(job.job_id).to_dict();r=result['result'] or {}
  candidate=r.get('candidate_output');expected_healthy=scenario.startswith('healthy')
  correct=candidate is not None and candidate['rows']==[[170.0]]
  success=(correct and r.get('routing',{}).get('decision')=='KEEP') if expected_healthy else r.get('source_health',{}).get('blocked') is True and len(model.calls)==0
  record={'scenario':scenario,'expected_healthy':expected_healthy,'success':success,'candidate_correct':correct,'model_calls':model.calls,'job':result,'events':repo.events(job.job_id)}
  results.append(record);(args.output/(scenario+'.json')).write_text(json.dumps(record,indent=2));print(json.dumps({'scenario':scenario,'success':success,'calls':len(model.calls),'health':r.get('source_health',{}).get('status')}),flush=True)
 summary={'n':len(results),'passed':sum(r['success'] for r in results),'model_calls':sum(len(r['model_calls']) for r in results),'scope':'Six synthetic scenarios; real model and durable worker; expected net revenue independently 100+80-10=170. No automatic release and no general accuracy claim.'}
 (args.output/'summary.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary),flush=True)

if __name__=='__main__':main()
