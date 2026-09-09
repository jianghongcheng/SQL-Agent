# SQL-Agent — local Strong Signal results

**Local engineering protocol: complete.**

This is the requested single-host local deployment scope. It does not establish
a production SLO or semantic correctness. General queries require human review;
the fine-tuned candidate is not promoted.

| Evidence | Status |
| --- | --- |
| regression | Passed |
| rag | Passed |
| live_agent_and_evaluation | Passed |
| finetuning | Passed |
| deployment | Passed |

Full regression: **396 passed**, no skipped tests; includes headless Chrome and disposable PostgreSQL.

## Real-model SQL and token cost

48 instances in six known synthetic task families, eight fresh data instances each.
Same models and frozen prompts/settings across the three retrieval conditions.
Failures remain in the denominator. These are development-family results,
not unseen-task or production accuracy. No general answer was auto-published.

| Retrieval | Correct | Failed / unavailable | Total tokens | Tokens / job | Tokens / correct result | p95 (s) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| bm25 | 21/48 | 0 | 139,207.0 | 2,900.1 | 6,628.9 | 5.85 |
| hybrid | 19/48 | 2 | 193,651.0 | 4,034.4 | 10,192.2 | 9.47 |
| hybrid_reranked | 19/48 | 0 | 208,927.0 | 4,352.6 | 10,996.2 | 8.98 |

Token cost includes input/output usage from both roles, repairs and failed jobs.
Exact totals are not invented for calls without provider usage. The per-correct
ratio includes the workload spent on incorrect/failed jobs. Sequential runs share
host resources; latency comparisons are descriptive. Paired family-bootstrap
intervals and all disagreements are retained in the local raw report.

## Retrieval-only evaluation

| Configuration | Hit@1 | Recall@4 | Warm p95 (ms) |
| --- | ---: | ---: | ---: |
| bm25 | 68.75% | 81.25% | 0.15 |
| hybrid | 87.50% | 100.00% | 13.54 |
| hybrid_reranked | 93.75% | 100.00% | 108.97 |

16 synthetic retrieval queries, eight document families. Window and paragraph
chunking tie on these short documents; no chunking accuracy advantage is claimed.
Paragraph boundaries are covered by boundary tests. Better document retrieval
must not be substituted for end-to-end SQL correctness.

## QLoRA

Source-fixture agreement: **52/100 → 59/100**; 9 fixes, 2 regressions.
Domain-cluster 95% difference interval: **0.00 to 14.47 percentage points**.
Fair scoring strips JSON fences in both conditions. The additional duplicated-row
stress check gives 43/89 → 48/89; 11 unscorable fixtures are retained. Its
interval includes zero. The saved adapter exists, but is **not promoted**.
See [the original failure analysis](STRONG_SIGNAL_ACCEPTANCE.md#original-qlora-failure-analysis).

## Local deployment and recovery

**100/100 scripted HTTP jobs** at concurrency 8; p95 **0.698 seconds**.
This tests queue/worker delivery, not LLM latency. Seven deployment check groups
pass, including authentication, idempotency, metrics and restart persistence.
The separate gateway test denies direct worker writes and commits an approved
synthetic change exactly once under repeated approval.

Historical serving-profile diagnostic, ten matched cases: p95 **47.11 → 6.90 seconds**.
The interrupted baseline and warm-up records remain available; this is not a
single-factor causal claim or a production capacity/SLO measurement.

## Reproduction and artifacts

Protocol, commands and limitations: [Strong Signal acceptance](STRONG_SIGNAL_ACCEPTANCE.md).
Local raw files and the audit hash inventory: `outputs/validation/strong-signal/`.
Docker credentials and control databases remain local and are not part of this summary.
No GitHub, resume or public deployment was updated by this acceptance run.
