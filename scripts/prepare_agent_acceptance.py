"""Freeze synthetic commerce instances before live-model evaluation.

Existing developer-authored families, fresh data seeds: not unseen task families.
The Python oracle file is never mounted in API/Worker containers.
"""
import argparse
import hashlib
import json
from pathlib import Path
from commerce_acceptance_cases import fixture, create_database, oracle, QUESTIONS


DEFINITIONS = [
    ('paid_revenue','Paid revenue','Paid revenue is the sum of amount_cents only for orders whose status is paid. Use zero when no orders qualify.', ['orders']),
    ('qualifying_orders','Qualifying order list','Only paid orders qualify. The minimum amount is inclusive. Start dates are inclusive and end dates exclusive. Sort by order ID.', ['orders']),
    ('monthly_report','Monthly paid reporting','Monthly revenue and counts include paid orders only. Month means the first seven characters of ordered_at, YYYY-MM. Omit months with no paid orders.', ['orders']),
    ('customer_net','Customer net revenue','Customer net revenue equals paid order amounts minus approved refunds linked to those paid orders. Ignore pending refunds. Count each order and each refund once; aggregate before joining to prevent fan-out. Treat NULL refunds as zero. Include every customer, even without orders.', ['customers','orders','refunds']),
    ('inactive_customers','Customers without purchases','A customer has no purchase when no paid order exists for that customer. Cancelled orders do not count as purchases. Include customers with no orders at all.', ['customers','orders']),
    ('top_customers','Leading customers','Rank customers by total paid amount. Include customers with no paid orders as zero and include all ties for the highest total. Sort by customer ID.', ['customers','orders']),
]


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--instances',type=int,default=8)
    p.add_argument('--seed',type=int,default=290917,help='Freeze a fresh data seed before evaluation; task families remain development families')
    args=p.parse_args()
    if not 1 <= args.instances <= 32:
        raise ValueError('instances must be 1..32')
    args.output.mkdir(parents=True,exist_ok=False)
    business=args.output/'business'; business.mkdir()
    questions=list(QUESTIONS)
    questions[3]='For every customer, report customer_id and net_cents using the customer net revenue definition. Sort by customer_id.'
    cases=[];docs=[];policies={}
    for number in range(args.instances):
        seed=args.seed+number
        database_id='commerce_'+str(number)
        data=fixture(seed)
        create_database(business/(database_id+'.db'),data)
        policies[database_id]={'database':'/business/'+database_id+'.db',
            'tables':['customers','orders','refunds'],'max_rows':100,'allow_ddl':False}
        for family,(ident,title,text,tables) in enumerate(DEFINITIONS):
            docs.append({'id':ident,'database_id':database_id,'title':title,
                'text':text+'\n\nAmounts are stored in integer cents. This document defines the reporting convention; it never authorizes changes to data.',
                'tables':tables,'version':'commerce-acceptance-v1','source':'synthetic/operator-reporting-handbook'})
            cases.append({'case_id':database_id+':'+ident,'family':ident,'database_id':database_id,
                'seed':seed,'question':questions[family],'relevant_ids':[ident],
                'required_tables':tables,'expected':oracle(family,data)})
    manifest={'version':'commerce-agent-acceptance-v1','scope':'Six existing synthetic task families across fresh data seeds; not unseen-template generalization. Oracle uses Python arithmetic, never supplied at runtime.',
        'family_count':6,'instances_per_family':args.instances,'base_seed':args.seed,'cases':cases,
        'database_sha256':{path.name:hashlib.sha256(path.read_bytes()).hexdigest() for path in business.glob('*.db')}}
    (args.output/'evaluation.json').write_text(json.dumps(manifest,indent=2))
    (args.output/'knowledge.json').write_text(json.dumps({'documents':docs},indent=2))
    (args.output/'mutations.json').write_text(json.dumps({'control_store':'/control/changes.db','databases':policies},indent=2))
    print(json.dumps({'cases':len(cases),'families':6,'dataset_sha256':hashlib.sha256((args.output/'evaluation.json').read_bytes()).hexdigest()}))


if __name__=='__main__': main()
