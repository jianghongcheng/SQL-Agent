"""Known-positive/negative, multi-instance grader checks; no model benchmark."""
import argparse
import hashlib
import json
from pathlib import Path
import sqlite3
from contractsql.agent_evaluation import compare_output


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    fixtures={
        'base':[(1,'Ada',150),(2,'Bo',80)],
        'boundary':[(1,'Ada',150),(2,'Bo',100)],
        'ordering':[(1,'Ada',150),(2,'Bo',120)],
        'duplicate_values':[(1,'Ada',150),(2,'Ada',120),(3,'Bo',80)],
        'null_and_empty':[(1,None,150),(2,'Bo',None),(3,'Cy',80)],
        'empty_result':[(1,'Ada',80),(2,'Bo',None)],
    }
    queries={
        'correct':'SELECT name FROM items WHERE amount > 100 ORDER BY id',
        'incorrect_boundary':'SELECT name FROM items WHERE amount >= 100 ORDER BY id',
        'incorrect_distinct':'SELECT DISTINCT name FROM items WHERE amount > 100 ORDER BY id',
        'incorrect_null_filter':'SELECT name FROM items WHERE amount > 100 AND name IS NOT NULL ORDER BY id',
        'incorrect_order':'SELECT name FROM items WHERE amount > 100 ORDER BY id DESC',
    }
    rows=[]
    for name,values in fixtures.items():
        db=sqlite3.connect(':memory:')
        db.execute('CREATE TABLE items(id INTEGER, name TEXT, amount INTEGER)')
        db.executemany('INSERT INTO items VALUES (?,?,?)',values)
        # Oracle uses Python business predicate, not another generated SQL.
        expected={'columns':['name'],'rows':[[label] for _,label,amount in sorted(values) if amount is not None and amount>100]}
        for label,query in queries.items():
            cursor=db.execute(query)
            actual={'columns':[c[0] for c in cursor.description],'rows':cursor.fetchall()}
            rows.append({'fixture':name,'candidate':label,'sql':query,
                         'matches':compare_output(actual,expected),'actual':actual,'expected':expected})
        db.close()
    accepted={label:all(r['matches'] for r in rows if r['candidate']==label) for label in queries}
    assert accepted['correct'] and not any(v for k,v in accepted.items() if k!='correct')
    result={'scope':'Authored grader sanity checks, not human calibration or Agent performance.',
            'task':'Names with amount strictly greater than 100, ordered by id; preserve duplicates and NULL names.',
            'fixtures':fixtures,'rows':rows,'passes_all_instances':accepted,
            'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'lesson':'Wrong boundary, DISTINCT, NULL filtering and ordering can match the base DB but fail another valid instance.'}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2))
    print(json.dumps(accepted))


if __name__=='__main__': main()
