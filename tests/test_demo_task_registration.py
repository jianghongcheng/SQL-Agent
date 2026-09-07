import json
from scripts import local_demo
from geomed_copilot.sql_config import SQLTaskRegistry
from geomed_copilot.business_context import retrieve_definitions


def test_billing_demo_uses_visible_dictionary_without_answer_verifier(tmp_path,monkeypatch):
    monkeypatch.setattr(local_demo,'RUNTIME',tmp_path)
    local_demo.prepare()
    monkeypatch.setenv('RADMEASURE_SQL_TASKS',str(tmp_path/'tasks.json'))
    task=SQLTaskRegistry.from_env().get('invoice_balance')
    assert not task.contract.verification_sql and not task.contract.fallback_to_verified_query
    definitions=retrieve_definitions(task.question,task.definitions)
    assert len(definitions)==1 and definitions[0]['source']=='synthetic billing dictionary'
    assert "state is exactly 'settled'" in definitions[0]['definition']
    rows=json.loads((tmp_path/'tasks.json').read_text())
    assert len(rows)==8 and task.database.is_file()

    analysis=SQLTaskRegistry.from_env().get('commerce_analysis')
    assert analysis.contract.dynamic_columns and len(analysis.example_questions)==3
    assert not analysis.contract.verification_sql
