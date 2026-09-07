# Verified business tasks and operational recovery

## What changed

Structural SQL validation accepted wrong customer totals, wrong date filters and
duplicate orders. Replaying the saved SQL now rejects those outputs. Fixed
business tasks can declare `verification_sql` in their service-owned contract.
The verifier executes against the same read transaction as the candidate, with
the same read-only authorizer and execution/output limits. Exact ordered results
must match. Invalid, failing or oversized verifiers fail closed.

The query is part of the contract hash and is excluded from model prompts.
Verified tasks reject question overrides at both HTTP and registry/session
boundaries. The model receives its previous SQL and an explicit mismatch reason
for bounded correction. Changing the business question requires a new registered
task and an appropriate business definition/check.

`fallback_to_verified_query: true` additionally permits ONE registered-query
fallback after exhausted/repeated repair or planner failure (including timeout).
It is disabled by default and requires a verifier. The action passes the SQL
policy and verifier and is recorded as `registered_business_fallback_verified`,
never as model-generated success. Policy-denied writes, planner STOP, missing
schema, and broken verifiers do not trigger this fallback. The model proposal
budget remains three; the optional catalog action is a separate additional
execution, plus verifier executions. No claim of three total database calls is made.

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

Workers now renew their lease every one-third of the lease duration (default
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

## Remaining production boundaries

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

These changes close specific correctness and lifecycle bugs. They do not justify
describing the entire system as production-proven.

## General SQL release boundary

The service now withholds unverified general SQL from automatic completion and
runs independent query checking for model-backed tasks. Agreement is not proof;
results remain review-required without trusted business verification. See
[the implementation and paired evaluation](SEMANTIC_CORRECTNESS.md). Historical
benchmark scores above are preserved and are not replaced with abstention rates.

## SQLite 读取一致性与 MCP 输入边界

每次 SQL 任务在首次收集 schema 前开启读事务；后续执行与修复保持同一快照，连接由流水线关闭。`tests/test_sql_snapshot.py` 用实际 WAL 并发写入验证：外部数据改变后，修复仍读取任务开始时的数据。长读事务在 rollback-journal 模式可能阻塞写入；本测试采用 WAL，并未由只读任务修改数据库日志模式，也未验证远程数据库隔离。

`tools/call` 要求 params 为对象，畸形输入返回 JSON-RPC -32602；`tests/test_mcp_invalid_params.py` 检查无效请求和无效 JSON 后 stdio 进程仍能响应 ping。这是输入可靠性验证，不是所有第三方 MCP 客户端的兼容性认证。
