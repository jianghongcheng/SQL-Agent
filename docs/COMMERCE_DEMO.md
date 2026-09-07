# Commerce demo and interview walkthrough

This is synthetic operational analytics, not a real customer deployment.
The task is to answer order/customer/refund questions against a read-only source
while preserving a fixed output contract and an inspectable execution record.

## Start

From the repository root, install with `pip install -e '.[dev]'`. An Ollama
server must already serve the chosen model; this project does not download it.

```bash
python scripts/demo_commerce.py
```

The command creates a SQLite source, registered task configuration and job
database. It runs total net revenue, correction of an invalid candidate, and
a prohibited write request through `JobPipeline` and `Worker`. It compares the
returned business values with separately hand-calculated expectations. A failed
check returns exit code 1 and retains the evidence. Correcting the candidate on
the first proposal does not count as multi-round recovery.

For another run, choose a new directory with `--output runtime/commerce-run-2`.
Use `--all` for all 12 cases, including known failures. The initial demo included
customer-level net revenue and failed its independent check; that artifact is
retained under `outputs/validation/commerce_demo_v1`. The default walkthrough
now demonstrates the working total-net query; no overall accuracy is inferred
from this selected subset. The 14B comparison was not better overall.

## Metric definitions

- Money is integer USD cents; no exchange rates or currency conversions.
- A paid order has `status = 'paid'`; cancelled orders are excluded.
- January cohort: order dates from 2026-01-01 inclusive to 2026-02-01 exclusive.
- Cohort net revenue: paid order gross minus all recorded refunds on those orders,
  including refunds issued in later months. This is a cohort metric, not cash flow.
- Refunds must be aggregated per order before joining to avoid duplicating gross.
- Customer reports include customers with no matching orders, with zero revenue.

Hand-calculated January totals: paid gross 29,000 cents, refunds 11,000 cents,
net 18,000 cents. Customer net: Ada 12,000; Ben 0; Cy 6,000; Di 0.
Fixtures are in `data/demo/commerce.sql`; independent expected results and
reference queries are in `data/benchmarks/commerce_v1.json`.

## Two-minute walkthrough

1. Explain the question and show the metric definition above.
2. Run the command. Show the output, task state, generated SQL and contract hash
   in the saved JSON. Explain the independent check versus runtime validation.
3. Show the refused write. Refusal is a successful safety outcome, not a SQL answer.
4. Show the separate `SQL_RETRY_VALIDATION.md` three-attempt trace, explicitly
   identifying its injected schema changes.
5. Show the 8B model's wrong customer total in the evaluation report. Explain why
   a structural contract cannot catch every business error.

This is a walkthrough script, not a claimed recorded video.

## Real local HTTP deployment check

After generating the demo source and configuration:

```bash
python scripts/smoke_commerce_service.py \
  --tasks runtime/commerce-demo/tasks.json \
  --output runtime/commerce-service-check
```

The script starts an API on an ephemeral loopback port, generates temporary auth,
queues a task before starting the worker, checks idempotency and authentication,
and verifies a real model answer. It stops its own processes afterward. This
checks local process integration, not public deployment or long-term uptime.
The recorded HTTP runs completed the transport/queue path but failed the answer
check, including a run given a valid candidate. See `COMMERCE_EVALUATION.md`.
Treat a nonzero exit as an unresolved failure, not a successful deployment test.

For interactive use, start API and worker as described in the README, with
`RADMEASURE_SQL_TASKS` pointing at the generated absolute `tasks.json` path in
both processes, and the same model settings and job database. The existing web
interface is at `/`. Roles apply service-wide; per-tenant data access is not implemented.
