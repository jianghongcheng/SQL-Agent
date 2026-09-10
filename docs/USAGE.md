# Usage

## Retrieval-augmented generation (RAG)

Set `SQL_AGENT_KNOWLEDGE_CONFIG=/absolute/path/to/knowledge.json` in the worker
environment before starting it. Copy the format in `examples/knowledge.json`,
then replace its synthetic definitions with reviewed knowledge for your own
registered database ID and table names. Documents require unique per-database
IDs, titles, text, source, version and an explicit `tables` list. An empty list
means database-wide reference material; it is not a wildcard across databases.
Do not include held-out evaluation answers, credentials or private unrelated data.

For a natural-language database request, the shared graph runs
`validate → retrieve_context → schema_linking → plan_sql → classify_sql`, followed by the same
query or approved-change nodes. BM25 ranks source-scoped passages, selecting up
to four whole passages and 6,000 text characters in compatibility BM25 mode.
Hybrid mode splits long passages into token windows before retrieval. Schema is still read from the configured database;
retrieved documentation is not authoritative schema or execution permission.

Each result includes `retrieval` with status, scores, source, version, content
hash and the passages supplied to the model. Database-request checkpoints retain
this evidence across repair and approval. Treat those records as sensitive;
existing workspace roles are not per-user or tenant isolation.

No match means generation uses the question and live schema; it does not mean
the answer is grounded in a retrieved definition. Explicit SQL skips retrieval.
Registered contract tasks retain their existing term-matched/required definitions.
The corpus is operator-curated JSON passages, not automatic PDF ingestion.
There is no measured SQL-answer accuracy lift from RAG yet. Retrieval relevance
and downstream answer correctness are separate evaluations.

### Enable local hybrid retrieval

Install the optional dependency with `pip install -e '.[rag]'`. Download an
embedding model deliberately before startup; runtime uses local files only,
CPU inference and `trust_remote_code=False`. The tested model is
`sentence-transformers/all-MiniLM-L6-v2` (384 dimensions); see its
[model card](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2).
Its input limit is checked rather than silently truncating embedding inputs.

```bash
export SQL_AGENT_RETRIEVAL_MODE=hybrid
export SQL_AGENT_KNOWLEDGE_CONFIG=/absolute/path/to/knowledge.json
export SQL_AGENT_EMBEDDING_MODEL_PATH=/absolute/path/to/local-embedding-model
export SQL_AGENT_EMBEDDING_CACHE=/absolute/path/to/private-runtime/vectors.sqlite
sql-agent-worker
```

The cache must be separate from business, job and graph databases. It is a
SQLite vector cache with exact in-process cosine search, not pgvector/Qdrant or
an ANN index. New cache files are mode 0600; use a private parent directory.
Model files and passage content/metadata are hashed; changed content or model
files receive different cache keys. Old entries are retained, not silently
overwritten. This is a trusted single-workspace cache, not encrypted storage.

Pipeline details:

1. Filter documents by database and table allowlist **before** chunking/embedding.
2. Tokenize with the embedding model tokenizer. Use at most 200 body tokens per
   chunk, reducing this for long titles, with 32-token overlap. Store parent ID,
   parent hash and original character offsets. This is token-window chunking,
   not sentence-aware or a guarantee that an entire business rule fits one chunk.
3. Rank chunks using BM25 and normalized dense cosine similarity. Take up to 20
   candidates per branch and combine ranks with `sum(1/(60 + rank))` (RRF).
4. Select up to four chunks under the 6,000-body-character budget. Skip oversized
   chunks and continue to later candidates. The budget does not include all JSON
   metadata or the entire LLM prompt. Siblings may both appear; no MMR.
5. Return lexical/dense ranks, fused score, model hash and source evidence with
   the Job. Dense similarity >0 is only a candidate filter, **not** a calibrated
   relevance/confidence threshold. All general query candidates still need review.

Hybrid configuration/model/embedding errors do not silently downgrade to BM25.
Use `SQL_AGENT_RETRIEVAL_MODE=bm25` explicitly for compatibility. Models are not
downloaded by the Worker. Default Compose does not mount models or install the
rag extra: container deployment needs a rag-enabled image, read-only model and
knowledge mounts, and a separate writable cache mount before enabling these vars.
No existing service is automatically reconfigured.

The independent SQL checker receives the same retrieved business passages plus
question and live schema, but not candidate SQL, candidate rows or planner reasoning.
Sharing business evidence can still produce common-mode errors. Its agreement is
advisory, not a correctness proof. `RequestPlanner(review_model=...)` and a
`JobPipeline` reviewer with a separate model adapter support distinct models;
without that configuration the planner adapter is reused and labelled accordingly.
There is no automatic PDF ingestion or validated
multilingual retrieval claim in this implementation.

Schema linking is a conservative lexical table selector. `SQL_AGENT_SCHEMA_MAX_TABLES`
(default 8) and `SQL_AGENT_SCHEMA_MAX_CHARS` (default 16000) bound its context.
It retains every column of selected tables and records the authorized catalog hash.
Explicitly requested tables and retrieved-document table references take priority.
Over-budget required tables or insufficient evidence for a large catalog fail
before model inference. The catalog is re-read before generation to reject stale
schema checkpoints. This is not semantic column pruning or automatic join-path
completion. Unsupported schemas remain unsupported by the database executor.

The graph preserves rejected normalized SQL and errors in a shared repair ledger.
Case/format/comment-only retries cannot bypass that ledger. This detects syntactic
normalization equivalence, not all logically equivalent queries. The three-proposal
budget is not a bound on every network retry or checkpoint re-execution.

Completed general-query candidates expose per-stage model calls, observed tokens,
unknown-usage counts and pipeline latency. Monetary cost remains unknown unless
priced separately; local inference is not assumed free. Telemetry on a completed
checkpoint is not comprehensive crash-time billing or inference load evidence.

### Independent checking model

For a distinct checking model, configure `SQL_AGENT_REVIEWER_BASE_URL` and
`SQL_AGENT_REVIEWER_MODEL` on the Worker. `SQL_AGENT_REVIEWER_PROVIDER` accepts
`ollama` (default) or `openai_compatible`; timeout and Ollama generation budget
use `SQL_AGENT_REVIEWER_TIMEOUT_SECONDS` and `SQL_AGENT_REVIEWER_MAX_TOKENS`.
Partial configuration fails startup instead of silently using another model.
With neither setting, the checker retains the default shared model adapter.
Separate adapters do not by themselves prove statistical error independence.

For local latency diagnosis, optional `SQL_AGENT_PLANNER_KEEP_ALIVE_SECONDS` and
`SQL_AGENT_REVIEWER_KEEP_ALIVE_SECONDS` pass a bounded 0–600 second residency
request to Ollama. Unset preserves the server default. Provider-reported load,
prompt evaluation and generation durations are recorded separately from HTTP
wall time; missing fields remain explicitly unknown. These fields follow
[Ollama's usage metrics](https://docs.ollama.com/api/usage).

### Independent execution gateway

`uvicorn sql_agent.gateway:create_app --factory --host 0.0.0.0 --port 8001`
starts the optional gateway. Configure `SQL_AGENT_MUTATION_CONFIG` and a private
`SQL_AGENT_GATEWAY_TOKEN` there. The approval API sets `SQL_AGENT_GATEWAY_URL` and
the matching token; the reasoning Worker must not receive gateway/admin tokens or
business write credentials. Without a gateway URL the legacy in-process executor
remains enabled: environment variables alone do not create a credential boundary.

The gateway accepts only plan ID and hash, reloads persisted human approval, and
reuses policy, integrity, expiry, transactional precondition and receipt checks.
It never accepts replacement SQL or a caller-selected reviewer. Network failure
does not fall back to local execution. Deploy with private networking/TLS as
appropriate; this local prototype assumes a trusted single-workspace control store.

Mutation attempts persist before business execution. Interrupted/uncertain attempts
can return `execution_unknown`; repeated approval can confirm a committed effect
from its authoritative business receipt but cannot re-execute an unresolved attempt.
A missing receipt is not proof of rollback. Explicit constraint rejection after
rollback is classified separately. Database-unavailable reconciliation may itself
fail; it does not authorize another mutation. There is no automatic unknown-case
reset or operator override. The Job's review decision and mutation execution status
remain separate; inspect the mutation status rather than treating approval as commit.

`scripts/validate_gateway_trial.py --image IMAGE --output NEW_DIRECTORY` verifies
three local containers: Worker/API business mounts read-only, Gateway read-write,
Worker lacking gateway/admin tokens, and approved duplicate-safe mutation. It uses
explicit SQLite SQL, not live model generation. `scripts/validate_compose_trial.py
--image IMAGE --output NEW_DIRECTORY --load-jobs 100` measures the scripted control
path at eight clients. Neither is a production LLM throughput claim.

### Offline QLoRA experiment

`scripts/prepare_sql_training.py` freezes a domain-disjoint source-labelled dataset
with executable SQLite fixtures, exact normalized schema/question deduplication,
and source hashes. Labels originate from the external corpus, not human business
validation; execution alone does not establish that the source SQL answers the question.
`scripts/train_sql_lora.py` runs local 4-bit NF4 SFT/LoRA and paired base/adapter
evaluation with RAG identically disabled. It does not automatically deploy an adapter.
The first pilot used Qwen2.5-Coder-1.5B-Instruct, 512 training examples, rank 16,
one epoch and 100 domain-isolated test examples. It is not a comparison with the
existing Qwen3-14B Agent or an end-to-end Agent benchmark.

The first pilot's strict JSON scorer rejected fenced baseline responses. Preserve
those raw outputs and use `scripts/score_sql_lora.py` for explicitly labelled
post-hoc alignment to runtime fence handling, applied equally to both conditions.
Report format compliance separately from execution equivalence. The descriptive
52/100 versus 59/100 result includes nine fixes and two regressions; it does not
establish a statistically reliable production gain or justify automatic promotion.

Optional, independently switchable extensions (defaults preserve the baseline):

- `SQL_AGENT_CHUNKING_MODE=structure` respects blank-line paragraph boundaries.
  Oversized paragraphs use overlapping token windows; overlap never crosses a
  paragraph boundary. This is paragraph-aware, not semantic or heading-aware
  parsing, and cannot guarantee complete business rules in every chunk.
- `SQL_AGENT_RERANKER_MODEL_PATH=/absolute/local/model` enables a CPU
  Sentence Transformers CrossEncoder on up to 20 RRF candidates before final
  selection. It loads local files only, rejects oversized input pairs and
  non-finite scores, and does not silently fall back on failure. Evidence records
  the model hash, candidate count, elapsed seconds and per-hit reranker score;
  `score` remains the RRF score, not the reranker score or a confidence value.
- Compare with `scripts/evaluate_hybrid_retrieval.py --chunking structure
  --reranker /absolute/local/model` plus the required arguments below. Compare
  chunking separately on long documents; short single-paragraph examples do not
  establish a chunking improvement. Variant first passes share process caches
  and must not be described as independent cold-start measurements.

Run the database-backed commerce retrieval example (6 labelled queries, version `commerce-retrieval-v2`):

```bash
python scripts/evaluate_hybrid_retrieval.py \
  --knowledge examples/hybrid_knowledge.json --queries examples/hybrid_retrieval_eval.json \
  --model /absolute/path/to/local-embedding-model \
  --cache /absolute/path/to/private-runtime/eval-vectors.sqlite \
  --output /tmp/new-hybrid-evaluation
```

Output must be new. `examples/hybrid_commerce.sql` supplies the matching synthetic
`customers`, `orders`, and `refunds` tables. Import it into a disposable SQLite
database and register those tables if testing SQL generation. This is not an
independently curated holdout. Inventory, shipping, support, and invoice rules
were removed because this fixture has no corresponding tables. The historical
16-query scores used the older terminology-only corpus at Git commit `f14be4b`;
they do not describe this revised example and are not reproduced by this command.
The runner
reports Hit@1, Recall@4, MRR@4 and first/warm-pass latency separately for BM25 and
hybrid. Do not turn this retrieval result into a SQL correctness claim.

Live-model smoke check using only disposable synthetic data:

```bash
SQL_AGENT_KNOWLEDGE_CONFIG="$PWD/examples/knowledge.json" \
  python scripts/validate_unified_requests.py --expect-rag
```

This checks retrieval, generation, execution and approval together for two cases;
it is not a RAG accuracy benchmark. The test grants its synthetic admin approval
only against its own temporary database.

## Run the local demo

With Python 3.10+, Ollama running locally, and `qwen3:14b` installed:

```bash
git clone https://github.com/jianghongcheng/SQL-Agent.git
cd SQL-Agent
pip install -e '.[dev]'
PYTHONPATH=src:. python scripts/local_demo.py start --model qwen3:14b --generation-format sql --thinking --max-tokens 8192
```

Open **http://127.0.0.1:8765**, then click **Enter local demo**.
If using the key field, the local demo key is **`123`**. Select **`commerce_analysis`**
and try the questions below. Existing demo processes can be inspected with `status`
or stopped with `stop`. Credentials are for loopback demonstration only.

## Six questions to test yourself

Use **`commerce_analysis` for all six questions**. Paste only the question into
**Question**, leave **Initial SQL / corrected SQL** empty, and click **Submit
analysis** once. The page polls automatically. Wait for `needs_review`, inspect
**Candidate result** and **Executed / proposed SQL**, then expand the expected
answer below. `needs_review` is the normal outcome for this task, including a
correct answer; it is not an accuracy verdict.

These answers were independently calculated from the current local
`analytics.sqlite` and checked against the deterministic
[commerce fixture](../scripts/commerce_acceptance_cases.py), seed **17**: 6 customers,
17 orders and 15 refunds. All amounts are **integer cents**. Rebuilding the demo
with the documented launcher recreates this fixture; answers must be recalculated
if you change the data. These are known manual regression questions, not a new
held-out benchmark. The answer keys are documentation and are not given to the
runtime Agent.

### 1. Paid revenue — scalar aggregation

```text
What is the total amount in cents of paid orders? Return one column named paid_revenue_cents; use zero if none exist.
```

<details>
<summary>Expected answer and what to check</summary>

| paid_revenue_cents |
|---:|
| 52000 |

Only `status = 'paid'` orders count. **58250** is the total across all orders,
including cancelled orders, and is wrong for this question. Refunds are not part
of the requested measure.

</details>

### 2. Filtered order list — status, amount and date boundaries

```text
List paid orders of at least 2500 cents placed on or after 2026-02-01 and before 2026-04-01. Return order_id, ordered_at, amount_cents, sorted by order_id.
```

<details>
<summary>Expected answer and what to check</summary>

| order_id | ordered_at | amount_cents |
|---:|---|---:|
| 2 | 2026-03-01 | 13500 |
| 4 | 2026-02-01 | 5000 |
| 11 | 2026-02-14 | 5000 |
| 13 | 2026-02-28 | 2500 |

Exactly four rows. February 1 is included; April 1 is excluded. Cancelled orders
15 and 17 meet the date/amount conditions but must not appear.

</details>

### 3. Monthly paid revenue — grouped counts and totals

```text
For each month containing paid orders, return month (YYYY-MM), order_count and revenue_cents for paid orders only, sorted by month.
```

<details>
<summary>Expected answer and what to check</summary>

| month | order_count | revenue_cents |
|---|---:|---:|
| 2026-01 | 3 | 7500 |
| 2026-02 | 3 | 12500 |
| 2026-03 | 4 | 14750 |
| 2026-04 | 3 | 17250 |

Zero-amount paid orders still count as orders. Counts sum to **13** and monthly
revenue sums to **52000**.

</details>

### 4. Customer net revenue — joins, refunds and missing data

```text
For every customer, return customer_id and net_cents: paid order amounts minus approved refund amounts on those paid orders. Count each order and refund once, ignore pending refunds, and use zero for absent or NULL amounts. Include customers without paid orders and sort by customer_id.
```

<details>
<summary>Expected answer and what to check</summary>

| customer_id | net_cents |
|---:|---:|
| 1 | 14500 |
| 2 | 14750 |
| 3 | 13000 |
| 4 | 8500 |
| 5 | 0 |
| 6 | 0 |

Keep all six customers. Avoid counting an order amount repeatedly when it has
multiple refund rows. Pending refunds do not reduce revenue; NULL amounts count
as zero. Customer totals sum to **50750**: 52000 paid revenue minus 1250 approved
refunds on paid orders.

</details>

### 5. Customers without paid orders — absence versus cancellation

```text
List customers who have no paid order. Return customer_id and name, sorted by customer_id. A cancelled order is not a paid order.
```

<details>
<summary>Expected answer and what to check</summary>

| customer_id | name |
|---:|---|
| 5 | Customer 5 |
| 6 | Customer 6 |

Customer 5 has no orders; customer 6 has only a cancelled order. Both qualify.
Having a cancelled order alone does not qualify a customer who also has paid orders.

</details>

### 6. Highest paid revenue — preserve ties

```text
Return all customers tied for the highest total paid order amount. Include customers with no paid orders as zero. Return customer_id and paid_cents, sorted by customer_id.
```

<details>
<summary>Expected answer and what to check</summary>

| customer_id | paid_cents |
|---:|---:|
| 1 | 14750 |
| 2 | 14750 |

Return both tied customers. An unconditional `LIMIT 1` loses a correct row.
This question asks for paid order amounts, so subtracting refunds is wrong.

</details>

### Record your results

Compare column names, ordered rows and values. A successful SQL execution alone
does not pass these checks. Record **Observed submit-to-result (this page)** from
**Run performance**, which includes queue wait and browser polling. Copy it before
reloading; reopening an old job does not reconstruct the browser measurement.

| Question | Job ID | Correct / incorrect / no candidate | Submit-to-result (ms) | Review / issue |
|---|---|---|---|---|
| 1 | | | | |
| 2 | | | | |
| 3 | | | | |
| 4 | | | | |
| 5 | | | | |
| 6 | | | | |

Enter a rationale before clicking **Approve review** or **Reject / request
correction**. Use **Open existing job** to reopen the job by ID and check **Full
evidence and audit history**. If you correct a question or SQL, submit a new job
and retain the original failure. Approval records your decision; it does not
rerun the query or establish an automatic correctness guarantee.


## Register additional tasks

Create an application-owned JSON file, e.g. `tasks.json`:

```json
[
  {
    "task_id": "employee_names",
    "question": "List employee names",
    "database": "company.sqlite",
    "contract": {
      "columns": ["name"],
      "non_null": ["name"],
      "min_rows": 1,
      "max_rows": 1000,
      "version": "1"
    }
  }
]
```

Database paths resolve relative to this JSON file. The database must already
exist. Set `SQL_AGENT_SQL_TASKS=/absolute/path/tasks.json` in API and worker.
Configure a real planner endpoint for custom tasks. The default scripted planner
is intentionally limited to the synthetic employee-name demonstration.

Submit `task_id`, optional `question`, and optional `initial_sql`. Extra fields
such as database paths or contract overrides are rejected. The question must stay within the registered task's output contract. Fixed-column
contracts require matching columns; the bundled commerce_analysis task instead
permits 1–50 uniquely named columns and up to 200 rows. Authentication currently grants
roles across the configured service, not per-dataset tenant permissions.

For independent SQL review, a registered task may set `"ordered": false` in
its contract when row order is irrelevant. The checker then compares row
multisets: duplicates, column count and exact values still matter. The default
is `true`; request text cannot change this application-owned setting. Registered
reference-query verification retains its existing exact comparison. Checker
agreement is corroboration, not proof or automatic publication authorization.
The `independent_sql_v2` prompt explicitly constrains measure ownership and
aggregation grain; it does not prevent all model mistakes. Registered ordering
contracts do not apply implicitly to direct database requests. Those requests
use an advisory SQLite checker with ordered-row comparison when a question and
model are available; checker agreement never permits automatic completion.

Independent review also supports optional application-owned additive-measure
constraints, for example:

```json
"grain_measures": [["movements", "delta", "move_id"], ["holds", "units", "hold_id"]]
```

Each triple declares a source table, additive column and source-row key. The
checker verifies the key against the live SQLite schema, parses SQL, and requires
that joins cannot multiply that measure's source rows. Both candidate and checker
SQL must pass. Current support is conservative: direct tables, `SUM(column)`,
single-column non-null primary keys, many-to-one equality joins, and separately
aggregated correlated subqueries. Derived-table joins, other aggregate forms,
ambiguous bindings and unsupported predicates remain unproven and require review.
Declared keys without live uniqueness evidence are not trusted. This is a
cardinality check, not proof of filters, event order, thresholds, arithmetic or
overall business correctness. No model-generated contract is accepted as an
authority. The option is not enabled implicitly for unregistered queries and
does not change publication authorization or the direct request path.

Only SQLite query sources are supported. Registered connections use `mode=ro`
and `query_only`; SQLite user-defined function names are allowlisted during
execution. Do not use this as a sandbox for hostile database files.

Review records notes and disposition of an existing candidate. To try revised
SQL, submit another job with a new idempotency key. General database requests
return `needs_review`, `output: null`, `candidate_output`, and `semantic_review`
evidence. A model agreement is not business proof. Checker failure or absence
does not discard a successfully executed candidate or silently publish it.
The candidate and checker use separate restricted reads; evidence labels this
snapshot limitation. PostgreSQL checking is not implemented: such candidates
remain review-required. Registered tasks retain their existing business-query
verification and publication rules. Admin review records `review_approved` or
`review_rejected`; historical jobs are not migrated or relabeled.

## API and MCP

### Local deployment acceptance and release checks

Build an isolated image and exercise the existing Compose stack:

```bash
docker build -t sql-agent-trial:local .
python scripts/validate_compose_trial.py --image sql-agent-trial:local --output /tmp/sql-agent-trial-run-001
```

The output directory must not exist. Requires Docker Compose 2.24.4 or newer.
The script uses a unique project, random credentials and a loopback-only random
port. It checks authentication, viewer denial, queued work with Worker stopped,
duplicate submissions, registered repair output, unsafe-query review, metrics,
events and state after restarting PostgreSQL/API/Worker. It then removes only
its own containers and network, retaining the database volume named in
`evidence.json`. Private credentials are mode 0600 in a mode 0700 directory;
never publish them. Evidence/logs remain local. This is a scripted registered
task check, not LLM quality, CRUD acceptance, real user adoption or an SLO test.
Dependency ranges are not a full lockfile; retain the actual image ID for an
exact deployment replay.

CI runs deterministic evaluation and gate tests as part of pytest and writes
`outputs/validation/ci-regression.xml`. A green CI does **not** mean general
query answers are ready for automatic release. Separately run:

```bash
python scripts/check_eval_gate.py audited-counts.json --model-profile model-profile.json --output gate-result.json
```

The output must be new. The counts report has `schema_version: 1`, SHA-256
`configuration_id` (canonical sorted JSON of relative `src/**/*.py` hashes),
`model_profile_id` (canonical sorted JSON of the model profile), `dataset_id`,
`split: "new_templates"`, and `strata.generated` / `strata.challenge`.
Each stratum supplies integer counts: `planned`, `observed`, `correct`,
`incorrect`, `unavailable`, `correct_accepted`, `incorrect_accepted`.
The model profile is JSON containing `model_digest` and `options` (including
sampling, token limits, format and other inference settings).

Gate v1 requires complete runs, no candidate failures, at least 10 correct and
25 incorrect candidates per stratum, >=90% correct-answer pass rate, and zero
observed incorrect accepts. These are conservative release policy choices,
not a statistical guarantee. Missing/stale evidence fails closed. The command
returns nonzero when blocked and does not change runtime authorization. Counts
must come from audited raw runs; the gate cannot authenticate fabricated reports,
verify dataset representativeness, or replace human review of provenance.

Keep trial feedback separate from automated evidence: record the real task,
observed result, failure category and subsequent fix only after someone actually
uses the system. No user-impact claim follows from these smoke checks.

The local API exposes OpenAPI documentation at http://127.0.0.1:8765/docs.
Use the dashboard to submit a task, inspect its SQL and record approval or rejection.
API-key clients remain supported; never publish real keys.

For direct stdio MCP, configure the same registered tasks and model environment
as the API and worker, then run `sql-agent-mcp`.
See [MCP implementation](../src/sql_agent/mcp_server.py) for tool schemas.
The stdio process must be able to access its configured job store.

The browser exchanges a configured access key for an in-memory session.
Sessions expire after eight hours; restarting the API requires sign-in again.
Login does not add per-dataset permissions or multi-tenant isolation.

## Runtime files and evaluation pages

The launcher writes generated databases, job state and logs under
`runtime/local-demo/`. Models are installed separately through Ollama.
The benchmark link opens a local report when one has been generated; otherwise
it opens the public [evaluation documentation](EVALUATION.md).

## Upgrading from ContractSQL

Version 0.7 is named SQL-Agent. It uses the `sql_agent` Python package,
`sql-agent`, `sql-agent-mcp`, and `sql-agent-worker` commands, and
`SQL_AGENT_*` environment variables. Replace `contractsql` imports and
`CONTRACTSQL_*` configuration from 0.6, or earlier package imports and
environment names in your launcher configuration. Create a fresh virtual
environment when upgrading to avoid stale entry points from editable installs.
The package and command names are now independent of other applications.
The optional Compose stack also uses `sql_agent` database and role names.
Existing PostgreSQL volumes retain their original roles and databases; update
the connection configuration or migrate them explicitly before upgrading.

## Approved database changes

SQL-Agent has one browser workspace, one primary asynchronous request API and
one LangGraph definition. Requests accept a question or explicit SQL. The graph
selects the registered source's executor: contracted analysis retains its
snapshot-preserving bounded loop inside the `analyze` node; database sources use
`retrieve_context`, `plan_sql`, `classify_sql`, `read_query` or `preview`, `await_approval` and
`execute_transaction`. The database planner uses the configured local model to
produce SQL proposals, never authorization. Human approval is available only in
the admin API/browser, never as an MCP tool.

Install `pip install -e '.[api,prod]'` for PostgreSQL, or `.[api]` for SQLite.
Create a local configuration file (do not commit credentials or real databases):

```json
{
  "control_store": "changes/control.sqlite",
  "databases": {
    "local": {
      "engine": "sqlite",
      "database": "business.sqlite",
      "tables": ["orders", "notes"],
      "allow_ddl": true,
      "max_rows": 100
    },
    "postgres_demo": {
      "engine": "postgresql",
      "dsn_env": "SQL_AGENT_BUSINESS_POSTGRES_DSN",
      "schema": "agent_demo",
      "tables": ["orders", "notes"],
      "allow_ddl": true,
      "max_rows": 100
    }
  }
}
```

Set `SQL_AGENT_MUTATION_CONFIG` to this file for both API and worker. Paths are
relative to the config file. SQLite business files and PostgreSQL schemas must
already exist. Set the named DSN environment variable locally and use a
least-privilege database role for the configured schema, **not a superuser**.
The PostgreSQL receipt table requires CREATE permission in that schema on first
execution. DDL stays disabled unless `allow_ddl` is explicitly true. No mutation
configuration means all writes stay disabled. Never register the application's
job, approval or graph databases as business data.

Sign in on `/`. The former `/database` URL redirects to this same workspace:

1. Select a configured source and choose question or SQL input.
2. Click **Run request**. The API returns HTTP 202 and a request ID for either input.
3. The worker runs the graph. Read results return; mutations pause with an exact
   SQL, target, affected-row count, proposal hash and expiry.
4. Sign in as an administrator and open the same request ID if necessary.
5. Approve or reject. Mutation approval requires the exact preview hash.

Natural-language database requests need the existing `SQL_AGENT_PLANNER_*`
model configuration in the worker. The model must return a structured SQL
proposal; ambiguous/unsupported or malformed replies stop. Selected query
execution errors may trigger up to three model proposals, but a read repair
cannot escalate into a write. Explicit SQL is not automatically rewritten.
This prompt-based support has not been evaluated as a general NL-to-write benchmark.

Examples, assuming `orders(id INTEGER PRIMARY KEY, amount INTEGER)` exists:

```sql
SELECT * FROM orders ORDER BY id;
INSERT INTO orders (id, amount) VALUES (101, 2500);
UPDATE orders SET amount = 3000 WHERE id = 101;
DELETE FROM orders WHERE id = 101;
CREATE TABLE notes (id INTEGER PRIMARY KEY, body TEXT);
DROP TABLE notes;
```

The semicolon ends **one** statement; submit each separately. UPDATE and DELETE
require WHERE. The affected-row cap also applies to DROP TABLE. Prefer an
isolated sandbox for learning and keep external backups before real changes.

Primary API endpoints (one request lifecycle):

| Endpoint | Role | Meaning |
| --- | --- | --- |
| `GET /v1/sources` | viewer | Configured sources and contracts |
| `POST /v1/requests` | operator | `task_id` OR `database_id`, plus `question` or `sql`; idempotency header required |
| `GET /v1/requests/{id}` | viewer | Job state, result or mutation preview |
| `POST /v1/requests/{id}/review` | admin | `{decision, notes, proposal_sha256}`; hash required for mutations |

Use MCP `list_sql_sources`, `submit_sql_request` and `get_sql_request`. Give MCP
an **operator** key, never an administrator key. Earlier `/v1/jobs`, direct SQL
and mutation endpoints/tools remain compatibility adapters; they do not define
another application. Legacy job review cannot bypass mutation-hash approval.

### Execution guarantees and limits

- SQLite previews execute against an in-memory database copy, not business data.
  SQLite execution authorization rejects access outside the configured tables
  and trigger-driven operations. The full logical snapshot is rechecked under
  a write transaction before execution.
- PostgreSQL previews use metadata, SELECT counts and EXPLAIN **without ANALYZE**.
  They do not prove that INSERT values satisfy every constraint. Approval
  acquires locks, rechecks the table snapshot, executes and verifies affected
  rows. Constraint failures roll back the transaction.
- PostgreSQL's initial profile supports primitive columns and ordinary tables;
  no serial/identity/default/generated columns, user triggers, rules, foreign
  keys, custom constraints, RLS, inheritance, expression/partial indexes, custom
  functions, subqueries, joined mutations or INSERT SELECT. CREATE uses explicit
  columns; DROP has no CASCADE. This is a conservative CRUD profile, not a
  universal PostgreSQL administrator.
- Read-only queries additionally support RLS-enabled
  ordinary tables when the configured database role enforces the row policy;
  use a non-owner role without BYPASSRLS. This does not enable RLS mutations,
  column-level schema filtering, or separate PostgreSQL Gateway credentials.
- Approvals expire after 15 minutes by default. Data/schema or policy changes
  require a new preview. A successful mutation and its protected
  `_sql_agent_mutation_receipts` row commit atomically in the business database.
  Repeating the **same proposal** after a lost response reconciles its receipt;
  do not generate a new proposal to retry an uncertain commit.
- Concurrent review of one graph returns a conflict; inspect status and retry
  the same approval. Failed execution is not automatically repaired or retried.
  Graph state, approval records and business receipts must all be retained.
- The request queue owns worker attempts and stale result publication. Database
  graph requests reuse saved progress and a stable request ID. Contracted
  analysis reruns its complete session node after a crash; its live transaction
  is not serialized. Direct database SELECT retries open separate transactions,
  unlike the contracted loop's same-session snapshot. Do not claim identical
  source versions for every query retry or worker restart.
- Control/checkpoint files and file locks are **single-host** infrastructure,
  even when the business database is PostgreSQL. API instances on unrelated
  hosts are unsupported. No NFS or distributed execution guarantee.
- The default preview budget is 16 MiB and five seconds for individual database
  operations. PostgreSQL snapshots also cap rows at 100,000 per table. This is
  not a global end-to-end request deadline or a large-database implementation.
- Database schemas, files and credentials are trusted operator configuration.
  Use local/private endpoints, OS file permissions, TLS for remote PostgreSQL,
  and database-level least privilege. There is no tenant-level isolation.

Design references: [aparcero/mcp-postgres](https://github.com/aparcero/mcp-postgres)
for separating query/DML/admin policies, and
[mallahyari/langgraph-sql-agent](https://github.com/mallahyari/langgraph-sql-agent)
for explicit graph nodes. These are design references, not copied or embedded
dependencies; database adapters here preserve application-owned approval and
atomic receipts rather than calling an upstream auto-committing write tool.

## Clarifying a natural-language request

For registered database requests, the planner can ask a clarification question
instead of proposing SQL. The job enters `waiting_user`; no worker is held while
waiting. Read `job.result.clarification` for its `id` and `question`, then send:

```http
POST /v1/requests/{job_id}/resume
X-API-Key: <owner operator or administrator key>
Idempotency-Key: <unique reply key>
Content-Type: application/json

{"clarification_id":"<question id>","answer":"Use order ID 1"}
```

The response is HTTP 202 with the queued job. Retrying the same reply/key returns
the current job without enqueueing it again; conflicting reuse returns 409.
Replies are limited to 4,000 characters, two clarification rounds, and the
remaining job attempt budget. Resume does not reset attempts or grant write
permission. Answers are persisted as user input and included in subsequent model
context. Do not include secrets. Current scope: single workspace / trusted tenant
boundary.

SQLite and PostgreSQL job repositories support this lifecycle. The graph still
uses local SQLite checkpoints and a single-host lock; this is not distributed
checkpoint acceptance. The frontend has no answer form yet: use the REST API.
Registered fixed-task analysis does not use this clarification path. Model-driven
clarification is not proof of evidence sufficiency or business correctness.

## Test commands

```bash
python -m pytest -q
python -m compileall -q src
```

Browser interaction tests additionally need Playwright and Chrome.
Tests using optional dependencies may be skipped when they are unavailable.

For a two-case real-model smoke check using disposable SQLite data:
`python scripts/validate_unified_requests.py --model qwen3:14b`.
It queries one synthetic order, generates an update, verifies no pre-approval
change, and approves only that disposable test operation. It is not a benchmark.

For live CRUD tests, set `SQL_AGENT_TEST_POSTGRES_DSN` to a **disposable**
PostgreSQL database and run `python -m pytest -q tests/test_postgres_mutations.py`.
These tests create uniquely named schemas and drop only those schemas afterward.
