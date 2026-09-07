import sqlite3
from dataclasses import FrozenInstanceError

import pytest

from geomed_copilot.bounded_runtime import ActionProposal
from geomed_copilot.data_agent import ContractSQLPlanner, ContractSQLSession, DataAgentLoop, DataContract
from geomed_copilot.sql_environment import demo_database


@pytest.fixture
def connection():
    db = demo_database()
    yield db
    db.close()


def proposal(sql):
    return ActionProposal("REPAIR", "sql_query", {"sql": sql})


def test_repair_uses_new_evidence_without_gold(connection):
    contexts = []

    def planner(context):
        contexts.append(context)
        return proposal("SELECT missing FROM employees" if context.attempt == 1
                        else "SELECT name FROM employees ORDER BY id")

    result = DataAgentLoop().run("names", planner, ContractSQLSession(
        connection, DataContract(("name",), non_null=("name",), min_rows=1)))
    assert result.decision == "KEEP"
    assert result.output["rows"] == (("Ada",), ("Grace",), ("Linus",))
    assert len(contexts) == 2
    assert "missing" in contexts[1].evidence.previous_error
    assert contexts[0].evidence.schema
    assert contexts[0].evidence.contract_hash == contexts[1].evidence.contract_hash
    assert "not_semantic_proof" in result.reason


@pytest.mark.parametrize("sql", ["DROP TABLE employees", "SELECT load_extension('x')"])
def test_unsafe_actions_stop_without_replanning(connection, sql):
    calls = []

    def planner(context):
        calls.append(context)
        return proposal(sql)

    result = DataAgentLoop().run("names", planner, ContractSQLSession(
        connection, DataContract(("name",))))
    assert result.decision == "STOP"
    assert len(calls) == 1
    assert connection.execute("SELECT count(*) FROM employees").fetchone() == (3,)


def test_verification_failure_retries_then_exhausts(connection):
    result = DataAgentLoop(2).run("names", lambda ctx: proposal(
        f"SELECT NULL AS name FROM employees LIMIT {ctx.attempt}"),
        ContractSQLSession(connection, DataContract(("name",), non_null=("name",))))
    assert result.reason == "attempt_budget_exhausted:null_contract_violation"
    assert result.output is None


def test_repeated_proposal_stops(connection):
    result = DataAgentLoop().run("names", lambda ctx: proposal("SELECT bad FROM employees"),
                                 ContractSQLSession(connection, DataContract(("name",))))
    assert result.reason == "repeated_proposal"


def test_output_bounded_and_invalid_result_not_published(connection):
    result = DataAgentLoop(1).run("names", lambda ctx: proposal("SELECT name FROM employees"),
        ContractSQLSession(connection, DataContract(("name",), max_rows=1)))
    assert result.reason == "attempt_budget_exhausted:row_count_contract_mismatch"
    assert result.output is None


def test_contract_is_immutable_and_does_not_prove_semantics(connection):
    columns = ["name"]
    contract = DataContract(columns)
    columns.append("salary")
    assert contract.columns == ("name",)
    with pytest.raises(FrozenInstanceError):
        contract.min_rows = 2
    # A structurally valid but semantically wrong query can pass these checks.
    result = DataAgentLoop().run("employee names", lambda ctx: proposal(
        "SELECT department AS name FROM employees"), ContractSQLSession(connection, contract))
    assert result.decision == "KEEP"
    assert result.reason == "contract_checks_passed_not_semantic_proof"


def test_missing_evidence_stops_before_planning():
    db = sqlite3.connect(":memory:")
    try:
        def planner(ctx):
            pytest.fail("planner must not run without evidence")
        result = DataAgentLoop().run("names", planner, ContractSQLSession(db, DataContract(("name",))))
        assert result.reason == "missing_schema_evidence"
    finally:
        db.close()


def test_invalid_planner_output_stops(connection):
    result = DataAgentLoop().run("names", lambda ctx: {"sql": "SELECT 1"},
                                 ContractSQLSession(connection, DataContract(("name",))))
    assert result.reason == "invalid_proposal"


def test_model_adapter_receives_error_and_repairs(connection):
    class Model:
        def __init__(self):
            self.prompts = []

        def complete(self, prompt):
            self.prompts.append(prompt)
            if len(self.prompts) == 1:
                return '{"action":"REPAIR","sql":"SELECT missing FROM employees"}'
            assert "no such column: missing" in prompt
            return '{"action":"REPAIR","sql":"SELECT name FROM employees"}'

    model = Model()
    result = DataAgentLoop().run("names", ContractSQLPlanner(model),
                                 ContractSQLSession(connection, DataContract(("name",))))
    assert result.decision == "KEEP"
    assert len(model.prompts) == 2


@pytest.mark.parametrize("response", ['not json', '{"action":"REPAIR","sql":"SELECT name FROM employees","contract":{}}'])
def test_model_cannot_supply_contract_or_malformed_json(connection, response):
    class Model:
        def complete(self, prompt):
            return response

    result = DataAgentLoop().run("names", ContractSQLPlanner(Model()),
                                 ContractSQLSession(connection, DataContract(("name",))))
    assert result.decision == "STOP"
    assert result.reason.startswith("planner_error:")
    assert not any(item["step"] == "act_verify" for item in result.trajectory)
