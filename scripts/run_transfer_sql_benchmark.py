"""Complete two-model, new-schema comparison, frozen before inference."""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import shutil
import urllib.request

from scripts import run_paired_sql_benchmark as runner
from scripts import transfer_sql_cases as suite
from contractsql.planner import OllamaPlannerModel


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--models',nargs='+',required=True)
    args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=False)
    sources=list((runner.ROOT/'src/contractsql').glob('*.py'))+[Path(__file__),Path(suite.__file__),Path(runner.__file__)]
    hashes={str(p.resolve().relative_to(runner.ROOT)):runner.sha_bytes(p.read_bytes()) for p in sources}
    for source in sources:
        target=args.output/'source_snapshot'/source.resolve().relative_to(runner.ROOT)
        target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target)
    databases={};data={}
    for variant in range(2):
        data[variant]=suite.fixture(variant)
        databases[variant]=(args.output/f'billing_{variant}.sqlite').resolve()
        suite.create_database(databases[variant],data[variant])
    with urllib.request.urlopen('http://127.0.0.1:11434/api/tags',timeout=10) as response:
        models={m['name']:m for m in json.load(response)['models']}
    for model in args.models:
        if model not in models:raise ValueError('model unavailable: '+model)
    dbhash={p.name:runner.sha_bytes(p.read_bytes()) for p in databases.values()}
    schedule=[(model,case,variant,trial) for model in args.models for trial in range(3)
              for case in suite.CASES for variant in range(2)]
    manifest={'source_sha256':hashes,'database_sha256':dbhash,'models':{m:models[m] for m in args.models},
              'cases':[asdict(c) for c in suite.CASES], 'episodes_planned':len(schedule),
              'schedule':[(m,c.case_id,v,t) for m,c,v,t in schedule],
              'scope':'New billing schema/questions; familiar operator motifs. Frozen before inference, no tuning during run. Not a public benchmark.',
              'protocol':'native_sql_v1, temperature=0, max_tokens=2048, one SQL round, no checker/probes; sequential model blocks, not latency-randomized'}
    runner.write_json(args.output/'manifest.json',manifest)
    runner.expected=suite.expected
    rows=[]
    for index,(model,case,variant,trial) in enumerate(schedule):
        delegate=OllamaPlannerModel('http://127.0.0.1:11434',model,max_tokens=2048,json_mode=False)
        row=runner.run_episode(case,variant,'native_sql','clean',trial,None,databases,data,delegate)
        row['model']=model
        runner.write_json(args.output/f'episode_{index:04d}.json',row);rows.append(row)
        print(json.dumps({'done':index+1,'planned':len(schedule),'model':model,'case':case.case_id,'correct':row['accepted_correct']}),flush=True)
    with urllib.request.urlopen('http://127.0.0.1:11434/api/tags',timeout=10) as response:
        end={m['name']:m['digest'] for m in json.load(response)['models']}
    summary={'episodes':len(rows),'by_model':{m:runner.summarize([r for r in rows if r['model']==m],3) for m in args.models},
             'sources_unchanged':all(runner.sha_bytes((runner.ROOT/p).read_bytes())==h for p,h in hashes.items()),
             'databases_unchanged':all(runner.sha_bytes((args.output/p).read_bytes())==h for p,h in dbhash.items()),
             'models_unchanged':all(end[m]==models[m]['digest'] for m in args.models)}
    runner.write_json(args.output/'summary.json',summary)
    assert summary['sources_unchanged'] and summary['databases_unchanged'] and summary['models_unchanged']
    print(json.dumps(summary),flush=True)


if __name__=='__main__':main()
