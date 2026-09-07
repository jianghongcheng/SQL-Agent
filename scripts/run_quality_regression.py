"""Frozen regression: 26 known questions, two fixtures, bounded thinking + repair.

No runtime oracle, no hidden-test claim. No retry on semantic oracle failures.
"""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import shutil
import sqlite3
import urllib.request
from scripts import run_paired_sql_benchmark as runner
from scripts import transfer_sql_cases as billing
from scripts import run_manufacturing_transfer as manufacturing
from scripts.quality_profile import QualityModel, OPTIONS
from geomed_copilot import paired_benchmark as dev


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--repeats',type=int,default=3)
    args=parser.parse_args()
    if args.repeats<1:parser.error('repeats must be positive')
    args.output.mkdir(parents=True,exist_ok=False)
    sources=list((runner.ROOT/'src/geomed_copilot').glob('*.py')) + [Path(__file__),Path(runner.__file__),Path(billing.__file__),Path(manufacturing.__file__),runner.ROOT/'scripts/quality_profile.py']
    hashes={str(p.resolve().relative_to(runner.ROOT)):runner.sha_bytes(p.read_bytes()) for p in sources}
    for source in sources:
        target=args.output/'source_snapshot'/source.resolve().relative_to(runner.ROOT)
        target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target)
    cases=(*dev.CASES,*billing.CASES,*manufacturing.CASES)
    databases={};data={}
    for domain in sorted({c.domain for c in cases}):
        databases[domain]={};data[domain]={}
        for v in range(2):
            path=(args.output/f'{domain}_{v}.sqlite').resolve();databases[domain][v]=path
            if domain=='billing':
                values=billing.fixture(v);billing.create_database(path,values)
            elif domain=='manufacturing':
                values=manufacturing.fixture(v)
                with sqlite3.connect(path) as db:
                    db.executescript(manufacturing.SCHEMA)
                    for table,rows in values.items():
                        placeholders=','.join('?' for _ in rows[0])
                        db.executemany(f'INSERT INTO {table} VALUES ({placeholders})',rows)
            else:
                values=dev.fixture(domain,v);dev.create_database(path,domain,values)
            data[domain][v]=values
    model_name='qwen3:14b'
    def model_info():
        with urllib.request.urlopen('http://127.0.0.1:11434/api/tags',timeout=10) as r:
            return next(m for m in json.load(r)['models'] if m['name']==model_name)
    model=model_info();schedule=[(c,v,t) for t in range(args.repeats) for c in cases for v in range(2)]
    dbhash={p.name:runner.sha_bytes(p.read_bytes()) for domain in databases.values() for p in domain.values()}
    manifest={'source_sha256':hashes,'database_sha256':dbhash,'model':model,'options':OPTIONS,
        'thinking':True,'timeout_seconds':120,'max_sql_rounds':3,'max_model_attempts':runner.CALL_LIMIT,
        'seeds':[917+t for t in range(args.repeats)],'cases':[asdict(c) for c in cases],
        'repeats':args.repeats,'episodes_planned':len(schedule),
        'schedule':[(c.case_id,v,t,'native_sql_repair') for c,v,t in schedule],
        'scope':'Known development/regression questions including previous transfer failures. Not held-out or public benchmark. Offline Python oracles never reach the model. First/final query comparison describes within-trajectory recovery, not randomized ablation.'}
    runner.write_json(args.output/'manifest.json',manifest)
    rows=[]
    for index,(case,v,t) in enumerate(schedule):
        runner.expected={'billing':billing.expected,'manufacturing':manufacturing.expected}.get(case.domain,dev.expected)
        row=runner.run_episode(case,v,'native_sql_repair','clean',t,None,databases[case.domain],data[case.domain],QualityModel(model_name,917+t))
        rows.append(row);runner.write_json(args.output/f'episode_{index:04d}.json',row)
        print(json.dumps({'done':index+1,'planned':len(schedule),'case':case.case_id,'variant':v,'trial':t,'correct':row['accepted_correct'],'calls':len(row['calls']),'ms':row['elapsed_ms']}),flush=True)
    summary={'episodes':len(rows),'all':runner.summarize(rows,args.repeats),
        'by_domain':{d:runner.summarize([r for r in rows if r['domain']==d],args.repeats) for d in data},
        'sources_unchanged':all(runner.sha_bytes((runner.ROOT/p).read_bytes())==h for p,h in hashes.items()),
        'databases_unchanged':all(runner.sha_bytes((args.output/p).read_bytes())==h for p,h in dbhash.items()),
        'model_unchanged':model_info()['digest']==model['digest']}
    runner.write_json(args.output/'summary.json',summary)
    assert summary['sources_unchanged'] and summary['databases_unchanged'] and summary['model_unchanged']
    print(json.dumps(summary),flush=True)

if __name__=='__main__':main()
