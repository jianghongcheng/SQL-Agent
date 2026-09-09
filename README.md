# SQL-Agent

**A tool-using SQL agent for business data analysis, with read-only execution, bounded repair, and human review.**

[![CI](https://github.com/jianghongcheng/SQL-Agent/actions/workflows/ci.yml/badge.svg)](https://github.com/jianghongcheng/SQL-Agent/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

Ask about revenue, orders, or customer activity. SQL-Agent uses a local LLM to
generate SQL against registered SQLite sources, executes it within explicit
limits, and returns the result alongside the query and execution history.
Failed attempts feed a bounded repair loop; general-analysis results go to review.

[Quick start](#quick-start) · [Architecture](#architecture) · [Results](#evaluation) · [Usage](docs/USAGE.md)

## Demo

![SQL-Agent dashboard with a synthetic commerce query](docs/assets/dashboard.png)

The dashboard supports scalar answers, order lists, and grouped summaries.
The screenshot shows synthetic commerce data; the walkthrough includes six
[example questions and expected answers](docs/USAGE.md#six-questions-to-test-yourself).

## Architecture

![Agent execution and review workflow](docs/assets/workflow.svg)

The diagram shows the general-analysis path. SQL attempts within one job share
a read snapshot. Passing runtime checks produces a reviewable candidate, not
an automatically approved business answer.
Retry is allowed only for repairable errors while the SQL attempt budget remains.

| Engineering decision | Implementation |
| --- | --- |
| Separate SQL proposals from execution authority | Registered sources, SQLite read-only authorization, query and output budgets |
| Repair with observed feedback | Schema-aware generation and up to three SQL attempts; repeated proposals and denied actions stop early |
| Recover background work | Persistent jobs, idempotency keys, renewable leases, retries, and stale-worker write protection |
| Make results inspectable | SQL, errors, model usage, routing decisions, contract hashes, and review history |
| Support multiple clients | Browser dashboard, FastAPI, CLI, and MCP |

[Execution and recovery details](docs/RELIABILITY.md) · [Task registration](docs/USAGE.md#register-additional-tasks)

## Evaluation

Configuration comparison on **26 development questions × 2 database instances ×
3 trials**, scored against independently calculated answers:

| Configuration | Correct runs | p95 latency |
| --- | ---: | ---: |
| Coder 14B, single SQL attempt | 102/156 (65.4%) | 2.12 s |
| Qwen3 14B, no thinking, repair enabled | 108/156 (69.2%) | 2.23 s |
| Qwen3 14B, thinking and repair | **142/156 (91.0%)** | 74.83 s |

The selected configuration trades latency for correctness, motivating asynchronous
delivery. It still produced 13 incorrect candidates and one stop. These are
repeated development runs, not 156 independent questions; model and execution
settings differ between rows. See [protocols, failures, external BIRD results,
and reproduction](docs/EVALUATION.md).

Recovery tests exercise worker termination, lease expiry, duplicate submission,
and stale-result rejection. They test service behavior separately from model accuracy.

## Quick start

Requires Python 3.10+, a running local Ollama service, and enough memory for
`qwen3:14b`. Install Ollama separately, then:

```bash
git clone https://github.com/jianghongcheng/SQL-Agent.git
cd SQL-Agent
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
ollama pull qwen3:14b
python scripts/local_demo.py start --model qwen3:14b --generation-format sql --thinking --max-tokens 8192
```

Open **http://127.0.0.1:8765**, select **Enter local demo**, and use
`commerce_analysis`. The local-only key is `123`. Inspect SQL and results when
the job reaches `needs_review`, then record an approval or rejection.

```bash
python scripts/local_demo.py status
python scripts/local_demo.py stop
python -m pytest -q
```

**Stack:** Python, Ollama, SQLite, FastAPI, MCP, Docker, GitHub Actions.

## Scope

This release supports registered SQLite analytical sources and local deployment.
General SQL requires human review; fixed catalog tasks can use explicitly
registered reference queries. Service-wide roles are implemented, not multi-tenant
data isolation. See [operational limits](docs/RELIABILITY.md#operational-limits)
before deploying beyond a local environment.

[Usage](docs/USAGE.md) · [Evaluation](docs/EVALUATION.md) · [Contributing](CONTRIBUTING.md) · [MIT license](LICENSE)
