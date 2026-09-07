# SQL Data Agent design

ContractSQL has one domain: SQL queries and query repair. A service-owned
`SQLTaskRegistry` resolves task IDs to a database and immutable `DataContract`.
The API fixes a contract hash when accepting a task. Neither request content nor
planner output can change it during execution.

`JobPipeline` runs `DataAgentLoop` inside the existing worker. Collection reads
schema and previous execution errors. `ContractSQLPlanner` supports structured JSON proposals; `NativeSQLPlanner`
supports a single SQL text response. Both feed the same bounded runtime. `BoundedAgentRuntime` checks the action/tool policy before
SQL execution. `ContractSQLSession` also installs a SQLite authorizer and VM
budget, limits returned rows, and checks columns/nullability/row counts.

The deterministic router accepts, performs a bounded retry, or stops. Repeated
identical proposals, denied actions, missing schema and malformed model output
stop. A human can inspect stopped work and record an approve/reject disposition;
this is not permission to perform a write action.

## Persistence and ownership

The job repository stores final execution evidence and job events. Agent repair
counts and infrastructure attempts are separate. Worker completion/failure
requires the original claim, matching job ID, owner and attempt generation, plus
an unexpired lease. Expiration fails exhausted jobs instead of requeueing forever.

The current worker lease is 300 seconds, renewed every 100 seconds. If renewal
fails or a claim expires, its result is discarded and another claim may rerun the read-only job.
Retries can repeat model cost. Mid-step progress is not persisted. PostgreSQL and
SQLite expose the same job contract; live PostgreSQL validation is separate from
local SQLite tests.

`ExecutionRecord` snapshots the contract and collect/act/verify/decide events.
It is an audit record, not a strict transition-enforcing workflow engine. Evidence
hashes identify bytes; they do not authenticate writers or freeze source data.
NaN/Infinity in audit evidence use tagged JSON values.

Replay links to the original trace and pins its contract hash. Model versions,
data snapshots, prompts and proposed SQL are not pinned. It is a re-execution
with lineage, not a claim of deterministic output reproduction.

## Relationship to the book

This implementation uses the explicit state/contract, evidence collection and
bounded verification loop described in *Data Agents on Databricks*, chapters
4–9. It implements a narrow SQL task, not Forge's complete pipeline platform.
The book's chapter 16 explicitly avoids persistent LangGraph checkpoints and
recovers from artifacts; our whole-job retry is less capable than that design.
Databricks, Bronze/Silver/Gold layers, multiple agents and pipeline writes are
not necessary for this project's chosen scope.

Optional registered business-query verification and audited catalog fallback
are described in [RELIABILITY.md](RELIABILITY.md). This mode deliberately uses
service-owned business SQL and must not be reported as blind model evaluation.

## SQLite 读取一致性与 MCP 输入边界

每次 SQL 任务在首次收集 schema 前开启读事务；后续执行与修复保持同一快照，连接由流水线关闭。`tests/test_sql_snapshot.py` 用实际 WAL 并发写入验证：外部数据改变后，修复仍读取任务开始时的数据。长读事务在 rollback-journal 模式可能阻塞写入；本测试采用 WAL，并未由只读任务修改数据库日志模式，也未验证远程数据库隔离。

`tools/call` 要求 params 为对象，畸形输入返回 JSON-RPC -32602；`tests/test_mcp_invalid_params.py` 检查无效请求和无效 JSON 后 stdio 进程仍能响应 ping。这是输入可靠性验证，不是所有第三方 MCP 客户端的兼容性认证。
