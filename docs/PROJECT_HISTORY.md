# Historical implementation notes

Previous README retained for provenance. Use the current README and dated reports for configuration and results.

# ContractSQL — SQL Data Agent

A contract-driven agent for **read-only SQL queries and query repair**. It collects
schema and execution errors, proposes a query, enforces policy, checks the output
contract, and either accepts the result, retries within a budget, or stops for
review. API, MCP and CLI use the same SQL job pipeline.

The portfolio-facing name is **ContractSQL**. Existing `radmeasure` commands and
`geomed_copilot` imports remain compatible; the remote repository has not been renamed.

## Business context and review workspace

[Frozen paired benchmark: 432 episodes](PAIRED_SQL_BENCHMARK_RESULTS.md)
compares one-shot, execution retry and independent checking across 12 synthetic
question families. Checking reduced wrong retained candidates but also reduced
correct retention and increased calls. This is not an accuracy-improvement claim.
The local demo links to the recorded comparison at `/benchmark`.

[Market requirements and remaining gaps](MARKET_ALIGNMENT_2026_09.md) ·
[Runtime measurements and regression evidence](COMMERCE_OBSERVABILITY.md).
Jobs now retain model latency, retries and token usage; the local UI displays these
measurements. Unknown cost remains unknown. Two regressing generation changes were
rejected by a 24-episode synthetic evaluation; the retained configuration passed 22/24.

**Local browser demo:** run `PYTHONPATH=src:. python scripts/local_demo.py start`
with the project dependencies and Ollama `qwen3:8b`, then open
http://127.0.0.1:8765. Includes three verified commerce metrics, source-health
blocking, and review actions. [Setup, walkthrough and validation](LOCAL_DEMO.md).

[The business-context workflow](BUSINESS_CONTEXT_WORKFLOW.md) adds task-scoped
metric definitions, bounded source-quality/freshness checks and a review interface
showing definitions, data issues, SQL and candidate results. Blocking source checks
stop before inference. The live demo also preserves checker failures: correct
candidates can still be held for review; no improvement in general accuracy is claimed.

```bash
PYTHONPATH=src:. python scripts/demo_business_context.py --output runtime/business-context-demo
```

## Business demo: orders, customers and refunds

Given synthetic commerce data, answer questions such as “What is January's net
revenue after all recorded refunds?” The fixture includes cancelled orders,
multiple refunds per order, absent customers, NULL regions and date boundaries.
Business definitions are explicit; reference SQL and hand-calculated answers
are used only for offline evaluation.

With Python 3.10+, dependencies installed as below, and an existing local Ollama
server with `qwen3:8b` available:

```bash
python scripts/demo_commerce.py
```

This runs real inference through the persistent job/worker pipeline, prints
business results and refusal behavior, and saves raw evidence under
`runtime/commerce-demo`. It exits nonzero if independent answer checks fail.
Use a fresh `--output` directory to repeat a run. No model is downloaded for you.
Use `--all` to include the known semantic failures in customer-level aggregation
and empty-cohort queries; the default three-task walkthrough is not an accuracy benchmark.

[Demo walkthrough and business definitions](COMMERCE_DEMO.md) ·
[Business evaluation and limitations](COMMERCE_EVALUATION.md)

For fixed business tasks, use the new verified catalog mode:

```bash
python scripts/demo_commerce.py --verified --catalog-fallback --all \
  --output runtime/commerce-verified
```

Observed: 12/12 expected outcomes, comprising **4 model answers, 5 explicit
registered-query fallbacks and 3 refusals**. This is not blind SQL accuracy.
The previously failing HTTP case now passes in this mode. Business checks,
same-snapshot verification, question binding and worker lease renewal are
documented in [reliability changes and remaining limits](RELIABILITY.md).

## Real public data validation

Imported **48,326 NYC TLC trip records and 265 zones**, preserving anomalies and
checking results independently from raw Parquet. Six analytics/data-quality
questions each passed three real-model runs without catalog fallback. A separate
local HTTP workload with **4 clients and 2 workers** returned **24/24 correct
answers**, deduplicated all 24 repeat submissions, and observed **2.23 s P95**.
These are short local acceptance checks, not a production SLA or broad SQL score.

[Dataset selection, sources, limitations and reproduction](DATASET_VALIDATION.md)
also compares BIRD Mini-Dev, BIRD-Critic and Spider 2.0. BIRD task files have been
inventoried; no official benchmark scores are claimed.

## Combined experiment

[The frozen combined run](COMBINED_EXPERIMENT.md) now includes **30 external
BIRD Mini-Dev cases**, real TLC queries, HTTP concurrency, injected schema drift
and recovery tests. External SQL matches were **10/30** for both single and
three-attempt runs; 15 accepted outputs disagreed with reference results. Thus
general SQL question answering is not production-ready. The real-data HTTP track
passed 24/24 tasks (P95 2.43 s), and 72 regression tests passed. These metrics
remain separate; a passing runner does not mean a passing SQL benchmark.

```bash
python scripts/run_combined_validation.py --output outputs/validation/combined-new
```

See the report for database setup, frozen selection, grading and raw artifacts.

The [complete three-database extension](BIRD_110_VALIDATION.md) has now run
**all 110 questions**: single-attempt 33/110 and three-attempt 35/110 set matches;
the additional 80 questions scored 23/80 and 25/80. All failures were retained.
The 58 accepted reference disagreements in the bounded run confirm that generic
SQL semantic reliability remains unresolved.

[A subsequent function-policy fix](SQL_FUNCTION_POLICY_FIX.md) removes false
blocks on LIKE and common date/string functions. Replaying all 500 frozen proposals
adds 9 correct and 29 incorrect executable candidates; it is not a fresh generation
score. General results still require review.

## Full 500-question rerun after recovery changes

[The complete rerun](BIRD_500_RERUN_V2.md) regenerated all 500 BIRD questions:
**135/500 first-proposal matches and 140/500 bounded matches**, unchanged from v1.
Fresh independent checking retained 96 correct, 75 incorrect and 1 ungraded candidate.
These results do not demonstrate improved general SQL correctness. Both stages retain
all failures and preserve the original runs for comparison.

## Multi-dimensional reliability evaluation

[The new evaluation report](AGENT_RELIABILITY_EVALUATION.md) records **108 complete
pipeline runs**, repeated trials, database side effects, injected failures and token costs.
After [bounded model recovery and an alias clarification](MODEL_RECOVERY_FIX.md),
all 45/45 known synthetic answerable runs retained correct candidates (previously 42/45),
and all 27 injected availability failures recovered (previously 0/27). Persistent
failures still stop after the retry budget. All generic results remain subject to review.
These are scoped regression results, not production readiness or held-out accuracy.
Mini-Interact public tasks were audited, but missing official gold/tests prevent scoring.

## Run locally

Python 3.10+:

```bash
pip install -e '.[dev]'
radmeasure --task employee_names --sql 'SELECT full_name FROM employees'
```

The default task uses a synthetic employee database and an explicitly scripted
planner. The first query fails; the next query uses the actual column name. This
is a reproducible integration demo, not an LLM performance result.

Start the API and worker in separate terminals with the same job database:

```bash
export RADMEASURE_JOB_DB="$PWD/runtime/sql-jobs.db"
export RADMEASURE_API_KEYS='{"operator-local":{"name":"operator","role":"operator"},"viewer-local":{"name":"viewer","role":"viewer"},"admin-local":{"name":"admin","role":"admin"}}'
uvicorn geomed_copilot.api:create_app --factory --host 127.0.0.1 --port 8000
# In the second terminal, set RADMEASURE_JOB_DB to the same path:
radmeasure-worker
```

Open `http://127.0.0.1:8000` for the SQL task interface, or submit directly:

```bash
curl http://127.0.0.1:8000/v1/jobs \
  -H 'content-type: application/json' \
  -H 'x-api-key: operator-local' \
  -H 'idempotency-key: example-1' \
  -d '{"task_id":"employee_names","initial_sql":"SELECT full_name FROM employees"}'
```

Poll `GET /v1/jobs/{job_id}` with a viewer/operator key. Inspect
`result.execution_record` for the contract, evidence, decisions and budgets.
`completed` now requires the registered business query verifier to pass. General
SQL is `needs_review`, with `output: null` and a separately labeled
`candidate_output`. Independent SQL agreement is advisory and cannot approve
release. See [semantic correctness controls](SEMANTIC_CORRECTNESS.md).

## Architecture

```text
API / MCP / CLI
       ↓
Registered task → fixed contract + approved SQLite data source
       ↓
JobRepository → Worker → JobPipeline
       ↓
Collect schema/errors → propose SQL → policy → execute → verify
       ↑                                             ↓
       └──────── bounded repair ← decide ─────────────┘
                                      ├─ completed
                                      └─ needs_review
       ↓
Execution evidence + contract hash + job events + replay lineage
```

| Layer | Responsibility | Modules |
|---|---|---|
| Access | Authentication, submission, result inspection | `api`, `mcp_server`, `cli` |
| Jobs | Persistent state, atomic claims, retries, owner fencing | `jobs`, `postgres_jobs`, `worker` |
| Agent | Evidence-driven proposal and bounded repair | `pipeline`, `data_agent`, `planner` |
| Execution | Registered tasks, fixed contracts, read-only SQL | `sql_config`, `sql_environment`, `bounded_runtime` |
| Evidence | Contract snapshots, decision records, replay lineage | `execution_record`, `replay` |

This applies the collect/act/verify/decide, explicit-contract and evidence ideas
from Eduardo Vieira's *Data Agents on Databricks*. It does not require Databricks
or multiple agents. See [design and guarantees](DATA_AGENT.md).

## Real model and data

Enable the existing model adapter by setting both endpoint and model:

```bash
export RADMEASURE_PLANNER_PROVIDER=ollama
export RADMEASURE_PLANNER_BASE_URL=http://127.0.0.1:11434
export RADMEASURE_PLANNER_MODEL=qwen3:8b
radmeasure --task employee_names --sql 'SELECT full_name FROM employees'
```

Use `RADMEASURE_PLANNER_PROVIDER=openai_compatible` for an existing compatible
endpoint; `RADMEASURE_PLANNER_API_KEY` is optional authentication. The project
starts no model server and performs no model download automatically.

Register real SQLite sources and task contracts using
[`RADMEASURE_SQL_TASKS`](SQL_TASKS.md). Clients select task IDs; they cannot
supply database paths or replace the configured contract. Sources open read-only.
The task registry must be identical in API and worker processes.

## MCP

Run the API and worker, then configure the stdio process:

```bash
export RADMEASURE_API_URL=http://127.0.0.1:8000
export RADMEASURE_MCP_API_KEY=operator-local
radmeasure-mcp
```

Tools: `list_sql_tasks`, `submit_sql_task`, `get_sql_job`. The MCP adapter calls
the authenticated API, so submission uses the same policy and job path.

## Deployment

`docker compose up --build` defines PostgreSQL job storage, API and worker for
the synthetic SQL task. Default credentials and the loopback port are for local
use. Optional planner variables are shown in `.env.example`.

For custom databases, mount the task configuration and source files read-only
into both API and worker, with matching `RADMEASURE_SQL_TASKS` paths. PostgreSQL
here stores **job state**; the current query environment targets SQLite.

## Evaluation

Fresh Qwen3-8B validation after the planner fix: 21/21 known cases and 15/15 new
synthetic cases met their expected outcomes. This includes refused requests;
it is not a general SQL accuracy claim. All succeeded or stopped on their first
proposal. A subsequent controlled schema-drift experiment recovered 6/6 cases
with one or two changes; three consecutive changes exhausted the budget.
This demonstrates injected-fault recovery, not general accuracy gains.
See [initial results](SQL_PLANNER_FIX_VALIDATION.md) and
[paired retry experiment](SQL_RETRY_VALIDATION.md).

The harder commerce suite reveals failures omitted by those earlier cases:
the 8B model with prompt v3 met 10/12 expected outcomes, including 3 refusals,
but falsely accepted 2 wrong business answers. See the business evaluation above.
Separate HTTP runs also exposed an incorrect duplicate order despite an earlier
benchmark pass. Local API/worker connectivity works, but end-to-end answer
reliability remains unresolved; the smoke check returns failure on wrong answers.

```bash
python scripts/validate_live_sql_agent.py --model qwen3:8b \
  --suite data/benchmarks/commerce_v1.json --output outputs/validation/commerce-new
python scripts/summarize_sql_metrics.py outputs/validation/commerce-new
```

```bash
python -m pytest -q
python -m compileall -q src
python scripts/export_harbor_sql_suite.py
```

Tests cover SQL repair, policy rejection, contract limits, API/worker/MCP flow,
review, replay, idempotency conflicts, expired-lease budgets and stale-owner
fencing. Source files and tests for the previous domain were moved out of this
SQL project rather than counted as SQL coverage.

Historical frozen SQL benchmarks remain under `data/benchmarks` and
`outputs/portfolio`. The 108-case policy-plus-verifier artifact reports 73→98
successful tasks; the 25 additional successes are STOP tasks, while REPAIR stays
30/36. Its reference-answer verifier is an offline evaluation component. Those
numbers do not measure the new adaptive loop. See [evaluation boundaries](EVALUATION.md).

## Scope

- Read-only queries and query-text repair; no data mutation, schema migration or
  automatic database repair.
- Default contract checks cover structure. Optional registered business-query
  checks enforce fixed-task output equality; they do not prove general semantics.
- Events persist at job completion. A crash retries the whole job; there is no
  mid-loop resume. Expired claims cannot publish results, and expiration respects
  the attempt budget. Workers renew their 300-second lease with owner/attempt fencing.
- The SQLite authorizer and VM/row budgets are not a hostile-code sandbox or a
  strict total-memory limit. Use isolated processes for untrusted workloads.
- Replay pins the contract, but uses the current database and model.
- Human review records disposition of a stopped task; approval does not execute
  a new query or fabricate an output.
- The Python import name `geomed_copilot` remains for existing SQL/Harbor
  compatibility. The active implementation and entry points are SQL-only.

Full [500-question BIRD Mini-Dev evaluation](BIRD_500_VALIDATION.md) is now
complete across all 11 databases: first-response set agreement **135/500 (27.0%)**,
up to three attempts **140/500 (28.0%)**; newly evaluated 390 questions **102→105**.
Five reference queries exceed frozen grading limits and remain in the denominator.
Accepted reference disagreements increase **197→217**. This demonstrates complete
evaluation coverage and a small observed retry gain, not production-grade general
SQL accuracy or an official leaderboard score.

[General SQL release controls and validation](SEMANTIC_CORRECTNESS.md):
unverified answers now require review; independent query disagreement can trigger
bounded repair. On all 500 frozen BIRD candidates, screening reduced reference
errors **217→72**, while retaining **94/140** correct answers. Agreement is not
proof and cannot automatically release a general answer. Six injected semantic
faults recovered **6/6** with live model repair; the full test suite passes **89**
tests. The fault-recovery result is separate from blind SQL accuracy.
