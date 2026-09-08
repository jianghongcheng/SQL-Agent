# Execution control and operational recovery

## Fixed-task verification

Structural SQL validation checks executable form, not business semantics. Fixed
business tasks can declare `verification_sql` in their application-owned contract
to compare customer totals, date filters, and duplicate handling.
The verifier executes against the same read transaction as the candidate, with
the same read-only authorizer and execution/output limits. Exact ordered results
must match. Invalid, failing or oversized verifiers fail closed.

The query is part of the contract hash and is excluded from model prompts.
Verified tasks reject question overrides at both HTTP and registry/session
boundaries. The model receives its previous SQL and an explicit mismatch reason
for bounded correction. Changing the business question requires a new registered
task and an appropriate business definition/check.

`fallback_to_verified_query: true` additionally permits one registered-query
fallback after exhausted/repeated repair or planner failure (including timeout).
It is disabled by default and requires a verifier. The action passes the SQL
policy and verifier and is recorded as `registered_business_fallback_verified`,
never as model-generated success. Policy-denied writes, planner STOP, missing
schema, and broken verifiers do not trigger this fallback. The model proposal
budget remains three; the optional catalog action is a separate additional
execution, plus verifier executions. SQL proposal budgets and total database
calls are counted separately.

This is a bounded business-query catalog, **not a general semantic verifier**.
The demo catalog's SQL definitions were promoted from the earlier development
references and checked against hand-calculated fixtures. They are not an
independent held-out oracle. The numbers below are system acceptance checks,
not improved model accuracy. Incorrect business definitions can still produce
incorrect business results. Domain-owner review is required before actual use.

For already fixed questions, directly running a registered query may be simpler
and cheaper than using a model. The agent remains useful for candidate generation
and repair, while this optional mode provides a deterministic operational path.

## Reproduce

With dependencies installed and local Ollama `qwen3:8b` available:

```bash
python scripts/demo_commerce.py --verified --catalog-fallback --all \
  --output runtime/commerce-verified
python scripts/smoke_commerce_service.py \
  --tasks runtime/commerce-verified/tasks.json \
  --output runtime/commerce-http
python -m pytest -q
```

Use fresh output directories. `--verified` without `--catalog-fallback` tests
rejection/repair alone; plain mode remains an exploratory, structurally checked
SQL generator. Do not expose exploratory tasks as verified business answers.
For a business-only service, register only tasks with reviewed verifiers.

## Observed results

`outputs/validation/commerce_catalog_v1/summary.json` records 12/12 expected
outcomes: **4 model-generated verified answers, 5 registered-query fallbacks,
3 refusals**. No incorrect output was marked completed in that run. Without
catalog fallback, `commerce_verified_v1` rejected four answerable tasks rather
than accepting wrong answers; it is not counted as full success.

`outputs/validation/commerce_service_catalog_v1/summary.json` records a passing
real HTTP/API/worker/Ollama check of the previously failing order-list scenario,
including authentication, duplicate submission and verified-question binding.
The final code including heartbeat was checked again in
`outputs/validation/commerce_service_catalog_final/summary.json`.
Historical failed runs remain intact. These are small local acceptance checks,
not a reliability percentage, an uptime claim, or a blind model benchmark.

## Worker lifecycle

Workers renew their lease every one-third of the lease duration (default
300 seconds). Renewal requires the same owner, attempt generation, running state
and unexpired lease. An expired claim cannot be resurrected. Renewal failure
marks the local claim lost and prevents publishing its result. Final writes
remain fenced by the repository. Heartbeats stop when work ends.

Tests verify that a job lasting longer than its initial lease stays owned and
cannot be claimed by a competitor. A separate test starts a real worker process,
kills it, waits for actual lease expiration, then verifies that a replacement
completes the job on attempt two. This uses SQLite and the scripted employee
planner to isolate infrastructure behavior; it is not a real-model crash test.
The PostgreSQL renewal implementation is included but has not been live-tested.

A local delayed HTTP model endpoint tests timeout handling through the real
adapter: explicitly enabled catalog fallback returns the checked business result
and records the planner error. It is an injected outage, not an observed Ollama
availability measurement. Regression suite: **68 passed**.

## Operational limits

- No real users, public deployment, sustained load test or SLO evidence yet.
- Service-wide roles are implemented; per-tenant table/row authorization is not.
- Recovery reruns whole read-only jobs; model calls may be duplicated. No mid-step resume.
- Read snapshots last for the session, including model retries; long sessions can
  retain database snapshots and cause contention. Production sizing is unmeasured.
- urllib timeouts and SQLite VM limits do not provide a total process deadline or
  memory isolation. A permanently hung worker can keep heartbeating; process
  supervision/deadlines remain required before unattended production operation.
- Existing stored contract hashes change with new contract fields. Old replay
  may reject a changed contract; never silently rewrite historical evidence.

These mechanisms provide bounded execution and recovery for local services;
production capacity and deployment isolation require separate validation.

## General SQL release boundary

General SQL remains review-required without registered business verification.
An independent model checker is available as an optional strategy; it is not
enabled in the documented SQL-text demo profile. Its agreement does not prove
correctness. See [the evaluation summary](EVALUATION.md) for the separate
checker experiments and their abstention tradeoffs.

## Read snapshots and MCP input validation

Each SQL task opens a read transaction before collecting schema; execution and
repair share that snapshot until the pipeline closes the connection.
`tests/test_sql_snapshot.py` exercises concurrent writes in WAL mode and checks
that repairs still read the original snapshot. Long reads can block writers in
rollback-journal mode; the read-only task does not change the journal mode.

MCP `tools/call` requires object parameters and rejects malformed calls with
JSON-RPC error -32602. `tests/test_mcp_invalid_params.py` checks that the stdio
process still responds to ping after invalid requests and malformed JSON.
