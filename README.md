# SQL-Agent

**A LangGraph SQL agent with grounded generation, controlled execution, and reproducible evaluation.**

[![CI](https://github.com/jianghongcheng/SQL-Agent/actions/workflows/ci.yml/badge.svg)](https://github.com/jianghongcheng/SQL-Agent/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

SQL-Agent turns natural-language questions into SQL over registered SQLite and
PostgreSQL databases. It combines schema and business-knowledge retrieval,
Planner–Verifier orchestration, bounded repair, human review, and durable
background execution. Browser, FastAPI, and MCP clients use the same
checkpointed workflow.

[Quick start](#quick-start) · [Architecture](#architecture) · [Evaluation](#evaluation) · [Usage](docs/USAGE.md)

## What it implements

- **Grounded generation:** database-scoped schema linking and optional BM25/vector
  retrieval with cross-encoder reranking.
- **Agent control:** structured Planner decisions, user clarification, bounded
  execution-error repair, and an independent advisory Verifier.
- **Guarded reads:** registered data sources, table permissions, read-only checks,
  bounded database/model calls, and result limits.
- **Approved changes:** impact preview, explicit human approval, transactional
  execution, and idempotency protection.
- **Reliable delivery:** persistent jobs, worker leases, retries, duplicate-request
  handling, and checkpoint resume for clarification and approval interrupts.
- **Evaluation:** execution accuracy, paired error analysis, token usage, latency,
  retrieval quality, and verifier behavior.

## Architecture

![SQL-Agent system architecture](docs/assets/workflow.svg)

The main read path is:

```text
Browser / FastAPI / MCP
        ↓
Persistent job queue and worker
        ↓
Scoped retrieval and schema linking
        ↓
LangGraph Planner
   ├── ask for clarification
   ├── stop unsupported request
   └── propose SQL
        ↓
Policy checks and read-only execution
        ↓
Bounded repair on eligible execution errors
        ↓
Independent Verifier and human review
```

The Planner proposes SQL but does not grant database access. Programmatic policy
checks determine whether the selected database, tables, and operation are allowed.
The Verifier independently generates a comparison query and checks result agreement;
its agreement is evidence, not proof of semantic correctness.

Database changes follow a separate path: preview the affected rows, request human
approval, then execute inside a transaction. Idempotency keys and stale-worker
checks prevent duplicate or superseded writes during retries and recovery.

The BIRD adapter feeds each official question, evidence field, allowlisted SQLite
schema, and database into this same read-only graph. It never mounts gold SQL into
Planner, retrieval, repair, or Verifier context. After the graph finishes, a
separate scorer executes the gold query and compares result sets.

[Execution and recovery details](docs/RELIABILITY.md) ·
[Supported operations and approval boundaries](docs/USAGE.md#approved-database-changes)

## Evaluation

### BIRD Mini-Dev agent comparison — September 13, 2026

Both workflows were evaluated on the same **500 official BIRD Mini-Dev questions**,
SQLite databases, local model weights, decoding settings, and execution scorer:

- **SQL-Agent:** full schema context, bounded execution-error repair, and a fixed
  Qwen2.5-Coder-7B advisory Verifier.
- **PV-SQL:** the upstream Probe–Generate–Verify/Repair workflow, with the tested
  base model performing all three stages.

| Model | SQL-Agent | PV-SQL | PV-SQL relative change |
| --- | ---: | ---: | ---: |
| **Qwen3-4B** | **196/500 (39.2%)** | 180/500 (36.0%) | **−16 tasks** |
| **Gemma3-4B** | 108/500 (21.6%) | **110/500 (22.0%)** | **+2 tasks** |
| **Qwen3-0.6B** | **37/500 (7.4%)** | 34/500 (6.8%) | **−3 tasks** |

| Model | Tokens / correct task: SQL-Agent → PV-SQL | p95 latency: SQL-Agent → PV-SQL |
| --- | ---: | ---: |
| Qwen3-4B | 6,763 → **19,025** | 3.66 s → **8.67 s** |
| Gemma3-4B | 13,253 → **32,022** | 4.11 s → **12.80 s** |
| Qwen3-0.6B | 33,898 → **44,625** | 5.20 s → **5.45 s** |

Paired analysis found that PV-SQL recovered/lost **53/69**, **47/45**, and
**17/20** questions for Qwen3-4B, Gemma3-4B, and Qwen3-0.6B respectively. The
additional probe and verification stages helped some questions while introducing
new failures and substantially increasing token cost.

Gold SQL was excluded from model prompts and runtime decisions and used only for
execution-based scoring. These are local paired configuration results, not an
official BIRD leaderboard submission or a reproduction of the paper's full BIRD
setup.

[Configuration, artifacts, and paired results](docs/evidence/2026-09-13/README.md) ·
[Evaluation protocols](docs/EVALUATION.md)

The reusable evaluator is `scripts/evaluate_bird_agent.py`; model-specific shell
wrappers only select the Planner profile and local model. Runtime outputs and BIRD
database files remain local and are excluded from Git.

### Additional engineering evidence

- Hybrid retrieval with reranking improved retrieval Hit@1 from **68.75% to
  93.75%** on 16 fixed synthetic retrieval queries. This measures retrieval only,
  not end-to-end SQL correctness.
- A local Docker recovery/load run completed **100/100 scripted jobs at
  concurrency 8** with **0.698 s p95** latency. The run excluded LLM inference and
  is an engineering check, not a production SLO.

The [evaluation documentation](docs/EVALUATION.md) records the scoring rules,
configuration boundaries, and reproduction limits.

## Demo

![SQL-Agent dashboard with a synthetic commerce query](docs/assets/dashboard.png)

The included synthetic commerce database supports revenue analysis, order lookup,
and grouped summaries. The dashboard exposes generated SQL, execution results,
review decisions, and job history.

## Quick start

Requires Python 3.10+ and a running local Ollama service:

```bash
git clone https://github.com/jianghongcheng/SQL-Agent.git
cd SQL-Agent
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
ollama pull qwen3:8b
python scripts/local_demo.py start --model qwen3:8b
```

Open **http://127.0.0.1:8765**, select **Enter local demo**, and choose
`commerce_analysis`. The local demo key is `123`.

```bash
python scripts/local_demo.py status
python scripts/local_demo.py stop
python -m pytest -q
```

## Scope

SQL-Agent is a local, single-host reference implementation. It supports registered
SQLite analytical sources and bounded PostgreSQL operations. General SQL and all
database mutations require human review; registered analysis tasks can follow
explicitly configured completion policies. Review
[the operational limits](docs/RELIABILITY.md#operational-limits) before using it
beyond a local environment.

**Stack:** Python, LangGraph, Ollama, SQLite/PostgreSQL, FastAPI, MCP, Docker, and
GitHub Actions.

[Usage](docs/USAGE.md) · [Evaluation](docs/EVALUATION.md) ·
[Contributing](CONTRIBUTING.md) · [MIT license](LICENSE)
