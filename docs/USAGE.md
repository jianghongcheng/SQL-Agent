# Usage

## Run the local demo

With Python 3.10+, Ollama running locally, and `qwen3:14b` installed:

```bash
git clone https://github.com/jianghongcheng/contractsql.git
cd contractsql
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
exist. Set `CONTRACTSQL_SQL_TASKS=/absolute/path/tasks.json` in API and worker.
Configure a real planner endpoint for custom tasks. The default scripted planner
is intentionally limited to the synthetic employee-name demonstration.

Submit `task_id`, optional `question`, and optional `initial_sql`. Extra fields
such as database paths or contract overrides are rejected. The question must stay within the registered task's output contract. Fixed-column
contracts require matching columns; the bundled commerce_analysis task instead
permits 1–50 uniquely named columns and up to 200 rows. Authentication currently grants
roles across the configured service, not per-dataset tenant permissions.

Only SQLite query sources are supported. Registered connections use `mode=ro`
and `query_only`; SQLite user-defined function names are allowlisted during
execution. Do not use this as a sandbox for hostile database files.

Review records notes and disposition of an existing stopped task. To try revised
SQL, submit another job with a new idempotency key. `completed` means runtime
checks passed; independently assess semantic correctness where it matters.

## API and MCP

The local API exposes OpenAPI documentation at http://127.0.0.1:8765/docs.
Use the dashboard to submit a task, inspect its SQL and record approval or rejection.
API-key clients remain supported; never publish real keys.

For direct stdio MCP, configure the same registered tasks and model environment
as the API and worker, then run `contractsql-mcp`.
See [MCP implementation](../src/contractsql/mcp_server.py) for tool schemas.
The stdio process must be able to access its configured job store.

The browser exchanges a configured access key for an in-memory session.
Sessions expire after eight hours; restarting the API requires sign-in again.
Login does not add per-dataset permissions or multi-tenant isolation.

## Runtime files and evaluation pages

The launcher writes generated databases, job state and logs under
`runtime/local-demo/`. Models are installed separately through Ollama.
The benchmark link opens a local report when one has been generated; otherwise
it opens the public [evaluation documentation](EVALUATION.md).

## Upgrading from 0.5

Version 0.6 uses the `contractsql` Python package, `contractsql*` commands, and
`CONTRACTSQL_*` environment variables. Replace earlier package imports and
environment names in your launcher configuration. Create a fresh virtual
environment when upgrading to avoid stale entry points from editable installs.
The package and command names are now independent of other applications.
The optional Compose stack also uses `contractsql` database and role names.
Existing PostgreSQL volumes retain their original roles and databases; update
the connection configuration or migrate them explicitly before upgrading.

## Testing

```bash
python -m pytest -q
python -m compileall -q src
```

Browser interaction tests additionally need Playwright and Chrome.
Tests using optional dependencies may be skipped when they are unavailable.
