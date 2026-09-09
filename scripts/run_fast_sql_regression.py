"""Matched non-thinking Qwen3 14B configuration on the frozen 26-question set.

Run after quality_regression_v1 completes so GPU queueing does not confound latency.
"""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import shutil
import urllib.request
from sql_agent.paired_benchmark import Case
from sql_agent import paired_benchmark as dev
from sql_agent.planner import OllamaPlannerModel
from scripts import run_paired_sql_benchmark as runner
from scripts import transfer_sql_cases as billing
from scripts import run_manufacturing_transfer as manufacturing


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    previous=runner.ROOT/'outputs/validation/quality_regression_v1'
    previous_summary=json.loads((previous/'summary.json').read_text())
    assert previous_summary['episodes']==156 and previous_summary['sources_unchanged']
    origin=json.loads((previous/'manifest.json').read_text())
    for relative,digest in origin['source_sha256'].items():
        if relative.startswith('src/'):
            assert runner.sha_bytes((runner.ROOT/relative).read_bytes())==digest, 'runtime changed before matched configuration comparison'
    args.output.mkdir(parents=True,exist_ok=False)
    cases=[Case(**c) for c in origin['cases']]
    sources=list((runner.ROOT/'src/sql_agent').glob('*.py'))+[Path(__file__),Path(runner.__file__),Path(billing.__file__),Path(manufacturing.__file__)]
    hashes={str(p.resolve().relative_to(runner.ROOT)):runner.sha_bytes(p.read_bytes()) for p in sources}
    for source in sources:
        target=args.output/'source_snapshot'/source.resolve().relative_to(runner.ROOT)
        target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target)
    dbs={};data={}
    for domain in sorted({c.domain for c in cases}):
        dbs[domain]={};data[domain]={}
        for v in range(2):
            name=f'{domain}_{v}.sqlite';source=previous/name
            assert runner.sha_bytes(source.read_bytes())==origin['database_sha256'][name]
            path=(args.output/name).resolve();shutil.copyfile(source,path);dbs[domain][v]=path
            data[domain][v]=billing.fixture(v) if domain=='billing' else manufacturing.fixture(v) if domain=='manufacturing' else dev.fixture(domain,v)
    def model_info():
        with urllib.request.urlopen('http://127.0.0.1:11434/api/tags',timeout=10) as r:
            return next(m for m in json.load(r)['models'] if m['name']=='qwen3:14b')
    model=model_info()
    assert model['digest']==origin['model']['digest']
    schedule=[(c,v,t) for t in range(3) for c in cases for v in range(2)]
    manifest={'source_sha256':hashes,'database_sha256':origin['database_sha256'],'model':model,
        'options':{'temperature':0,'num_predict':8192,'num_ctx':'provider default'},
        'thinking':False,'runtime_source_matches_thinking_run':True,'timeout_seconds':30,'max_sql_rounds':3,'max_model_attempts':runner.CALL_LIMIT,
        'cases':[asdict(c) for c in cases],'repeats':3,'episodes_planned':len(schedule),
        'schedule':[(c.case_id,v,t,'native_sql_repair') for c,v,t in schedule],
        'scope':'Known regression set, matched to thinking run. Same first prompt and maximum SQL rounds; sampling, thinking, context setting and request timeout differ. Not a single-factor causal ablation. Greedy repeats measure observed consistency, not independent sample probabilities.'}
    runner.write_json(args.output/'manifest.json',manifest);rows=[]
    delegate=OllamaPlannerModel('http://127.0.0.1:11434','qwen3:14b',timeout=30,max_tokens=8192,json_mode=False)
    for index,(case,v,t) in enumerate(schedule):
        runner.expected={'billing':billing.expected,'manufacturing':manufacturing.expected}.get(case.domain,dev.expected)
        row=runner.run_episode(case,v,'native_sql_repair','clean',t,None,dbs[case.domain],data[case.domain],delegate)
        rows.append(row);runner.write_json(args.output/f'episode_{index:04d}.json',row)
        if index==0:
            with urllib.request.urlopen('http://127.0.0.1:11434/api/ps',timeout=10) as r:
                runner.write_json(args.output/'observed_runtime.json',json.load(r))
        print(json.dumps({'done':index+1,'planned':len(schedule),'case':case.case_id,'correct':row['accepted_correct'],'calls':len(row['calls'])}),flush=True)
    summary={'episodes':len(rows),'all':runner.summarize(rows,3),
        'by_domain':{d:runner.summarize([r for r in rows if r['domain']==d],3) for d in data},
        'sources_unchanged':all(runner.sha_bytes((runner.ROOT/p).read_bytes())==h for p,h in hashes.items()),
        'databases_unchanged':all(runner.sha_bytes((args.output/p).read_bytes())==h for p,h in origin['database_sha256'].items()),
        'model_unchanged':model_info()['digest']==model['digest']}
    runner.write_json(args.output/'summary.json',summary)
    assert summary['sources_unchanged'] and summary['databases_unchanged'] and summary['model_unchanged']
    print(json.dumps(summary),flush=True)

if __name__=='__main__':main()
