"""Four previously inspected development cases: feasibility check, not benchmark."""
import argparse
import json
from pathlib import Path
from scripts.quality_profile import QualityModel, OPTIONS
from scripts import run_paired_sql_benchmark as runner
from scripts import transfer_sql_cases as billing
from contractsql import paired_benchmark as dev


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--model',default='qwen3:8b')
    parser.add_argument('--method',choices=['native_sql_guided','native_sql_repair'],default='native_sql_repair')
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=False)
    ids=('available_units','unworked_tickets','invoice_balance','largest_ties')
    runner.write_json(args.output/'manifest.json',{'case_ids':ids,'model':args.model,'options':OPTIONS,
        'thinking':True,'method':args.method,'scope':'Feasibility pilot on inspected failures; not accuracy evidence.'})
    for case in [c for c in (*dev.CASES,*billing.CASES) if c.case_id in ids]:
        data={};dbs={}
        for v in range(2):
            path=(args.output/f'{case.case_id}_{v}.sqlite').resolve();dbs[v]=path
            data[v]=billing.fixture(v) if case.domain=='billing' else dev.fixture(case.domain,v)
            if case.domain=='billing':billing.create_database(path,data[v])
            else:dev.create_database(path,case.domain,data[v])
        runner.expected=billing.expected if case.domain=='billing' else dev.expected
        row=runner.run_episode(case,0,args.method,'clean',0,None,dbs,data,QualityModel(args.model))
        runner.write_json(args.output/(case.case_id+'.json'),row)
        print(json.dumps({'case':case.case_id,'correct':row['accepted_correct'],'ms':row['elapsed_ms'],
                          'calls':len(row['calls'])}),flush=True)


if __name__=='__main__':main()
