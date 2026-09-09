"""Paired real-model recovery experiment with explicitly injected schema drift.

DDL belongs to this test harness, never to the agent. No model output is edited.
The frozen-feedback arm removes BOTH schema refresh and error feedback, so this
experiment cannot attribute their effects separately or estimate natural errors.
"""
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import argparse
import urllib.request

from validate_live_sql_agent import database, RecordingModel
from sql_agent.data_agent import SQLAgentPlanner, SQLAgentSession, DataAgentLoop, DataContract
from sql_agent.planner import OllamaPlannerModel
import sql_agent.data_agent as implementation


class DriftSession(SQLAgentSession):
    def __init__(self, db, contract, migrations, frozen=False):
        super().__init__(db, contract)
        self.migrations = migrations
        self.executions = []
        self.frozen = frozen
        self.first_evidence = None

    def collect(self, reason="", output=None):
        evidence = super().collect(reason, output)
        if self.first_evidence is None:
            self.first_evidence = evidence
        return self.first_evidence if self.frozen else evidence

    def execute(self, proposal):
        index = len(self.executions)
        ddl = self.migrations[index] if index < len(self.migrations) else None
        if ddl:
            self.connection.execute(ddl)
        event = {"attempt": index + 1, "injected_ddl": ddl, "sql": proposal.arguments["sql"]}
        self.executions.append(event)
        try:
            result = super().execute(proposal)
            event["output"] = result
            return result
        except Exception as exc:
            event["error"] = str(exc)
            raise


def suite():
    result = []
    for table, original, middle, final in [
        ("customers", "name", "display_name", "customer_label"),
        ("products", "title", "product_title", "product_label"),
        ("offices", "city", "city_name", "location_label"),
    ]:
        for changes in (0, 1, 2, 3):
            names = [original, middle, final, "latest_label"]
            result.append({
                "id": f"{table}_drift_{changes}", "changes": changes,
                "setup_sql": f"CREATE TABLE {table}(id INTEGER PRIMARY KEY, {original} TEXT); INSERT INTO {table} VALUES(1,'Alpha'),(2,'Beta');",
                "goal": f"List the text labels of all {table}, ordered by id. The table has one text label column; return its actual values under the output alias item.",
                "contract": {"columns": ["item"], "max_rows": 100},
                "migrations": [f"ALTER TABLE {table} RENAME COLUMN {names[i]} TO {names[i+1]}" for i in range(changes)],
                "gold_sql": f"SELECT {names[changes]} AS item FROM {table} ORDER BY id",
            })
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    cases = suite()
    raw = json.dumps(cases, indent=2)
    (args.output / "cases.json").write_text(raw)
    with urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=10) as response:
        tags = json.load(response)
    (args.output / "manifest.json").write_text(json.dumps({
        "started_at": datetime.now(timezone.utc).isoformat(), "model": "qwen3:8b",
        "model_details": [m for m in tags["models"] if m["name"] == "qwen3:8b"],
        "suite_sha256": hashlib.sha256(raw.encode()).hexdigest(),
        "source_sha256": hashlib.sha256(Path(implementation.__file__).read_bytes()).hexdigest(),
        "harness_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "scope": "Controlled schema-drift fault injection, not natural model-error frequency or general accuracy.",
        "comparison": "Identical first live response and migration schedule; attempts 1/2/3, plus 3-attempt frozen schema/error evidence. Duplicate proposals still terminate normally.",
    }, indent=2))
    rows = []
    for case in cases:
        oracle = database(case)
        for ddl in case["migrations"]:
            oracle.execute(ddl)
        cursor = oracle.execute(case["gold_sql"])
        expected = {"columns": tuple(c[0] for c in cursor.description), "rows": tuple(cursor.fetchall())}
        oracle.close()
        row = {"id": case["id"], "changes": case["changes"], "arms": {}}
        first = None
        for label, attempts, frozen in [("feedback_3", 3, False), ("single", 1, False), ("feedback_2", 2, False), ("frozen_3", 3, True)]:
            recorder = RecordingModel(OllamaPlannerModel("http://127.0.0.1:11434", "qwen3:8b", timeout=120))

            class PairedModel:
                count = 0

                def complete(self, prompt):
                    self.count += 1
                    if self.count == 1 and first is not None:
                        recorder.calls.append({"prompt": prompt, "content": first, "replayed_first_response": True})
                        return first
                    return recorder.complete(prompt)

            db = database(case)
            session = DriftSession(db, DataContract(**case["contract"]), case["migrations"], frozen)
            try:
                outcome = DataAgentLoop(attempts).run(case["goal"], SQLAgentPlanner(PairedModel()), session)
            finally:
                db.close()
            if label == "feedback_3":
                first = recorder.calls[0].get("content") if recorder.calls else None
                if first is None:
                    raise RuntimeError("No first model response; paired comparison invalid")
            row["arms"][label] = {"outcome": asdict(outcome), "correct_answer": outcome.decision == "KEEP" and outcome.output == expected,
                "false_accept": outcome.decision == "KEEP" and outcome.output != expected,
                "executions": session.executions, "model_calls": recorder.calls}
        rows.append(row)
        (args.output / f'{case["id"]}.json').write_text(json.dumps(row, indent=2))
        print(json.dumps({"id": case["id"], **{k: {"correct": v["correct_answer"], "calls": len(v["model_calls"]), "reason": v["outcome"]["reason"]} for k, v in row["arms"].items()}}), flush=True)
    summary = {str(changes): {arm: {"correct": sum(r["arms"][arm]["correct_answer"] for r in rows if r["changes"] == changes),
        "n": sum(r["changes"] == changes for r in rows), "false_accept": sum(r["arms"][arm]["false_accept"] for r in rows if r["changes"] == changes)}
        for arm in ("single", "feedback_2", "feedback_3", "frozen_3")} for changes in range(4)}
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary), flush=True)


if __name__ == "__main__":
    main()
