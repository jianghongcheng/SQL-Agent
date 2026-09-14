# Evaluation

SQL-Agent reports model quality separately from software reliability. Accuracy,
latency, and token measurements are tied to a named dataset and configuration;
software tests do not count as model-quality evidence.

## BIRD Mini-Dev comparison

The current public result compares SQL-Agent with PV-SQL on the same 500 official
BIRD Mini-Dev questions and SQLite databases.

| Model | SQL-Agent | PV-SQL |
| --- | ---: | ---: |
| Qwen3-4B | **196/500 (39.2%)** | 180/500 (36.0%) |
| Gemma3-4B | 108/500 (21.6%) | **110/500 (22.0%)** |
| Qwen3-0.6B | **37/500 (7.4%)** | 34/500 (6.8%) |

SQL-Agent used full schema context, bounded repair for eligible execution errors,
and a fixed Qwen2.5-Coder-7B advisory Verifier. PV-SQL used its
Probe–Generate–Verify/Repair workflow. Each pair used the same base-model weights,
temperature, context and output limits, dataset, and execution scorer.

Gold SQL was unavailable to generation, probing, repair, and verification. It was
used only after inference to compare execution results. A task counted as correct
when the candidate and reference queries executed successfully and returned equal
result sets. Errors counted against the full denominator of 500.

The comparison is local and paired. It is not an official BIRD leaderboard
submission and does not reproduce the PV-SQL paper's full BIRD setup. See the
[public evidence record](evidence/2026-09-13/README.md) for token cost, p95 latency,
paired gains and losses, model settings, and the pinned upstream PV-SQL commit.

## Retrieval evaluation

The included retrieval fixture contains 16 synthetic questions over reviewed
schema and business-rule documents:

| Retrieval configuration | Hit@1 |
| --- | ---: |
| BM25 | 68.75% |
| BM25 + vector retrieval | 87.50% |
| Hybrid retrieval + cross-encoder reranking | 93.75% |

This evaluates whether the expected context appears first. It is not end-to-end
SQL accuracy and should not be compared with BIRD execution accuracy.

## Software verification

The automated test suite covers read-only enforcement, table permissions,
mutation approval, transaction idempotency, job leases, retries, stale-worker
rejection, checkpoint recovery, API/MCP behavior, and deterministic evaluation
logic.

A separate local Docker run completed 100/100 scripted jobs at concurrency 8 with
0.698-second p95 latency. It excluded LLM inference and is an engineering
recovery/load check rather than a production SLO.

## Cost accounting

Token cost includes observed Planner and Verifier input/output tokens, failed
calls, and retries. Tokens per correct task divide total observed workload tokens
by the number of correct tasks. Missing provider usage remains unknown rather
than being recorded as zero.

Latency measures the configuration named in each evidence record. Local latency
does not establish production availability or throughput.

## Reproduction limits

The repository includes public summaries and deterministic validation code, but
not raw model responses, cloned third-party repositories, BIRD database files,
model weights, runtime databases, credentials, or service logs. Those artifacts
remain excluded through `.gitignore`.

Dataset source information is recorded in
[the dataset registry](../data/dataset_registry.json). Obtain BIRD separately and
respect its license and terms.
