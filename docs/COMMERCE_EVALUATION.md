# Commerce evaluation: correct execution versus correct business answers

This report preserves the original blind-generation results. A subsequent
verified business-catalog mode fixes false acceptance for registered tasks and
passes the HTTP check; see [RELIABILITY.md](RELIABILITY.md). Its catalog-assisted
results are not comparable as blind model accuracy.

## Protocol

Twelve synthetic cases were frozen in `data/benchmarks/commerce_v1.json` before
the first model run: nine answerable queries and three refusal tasks. All use
the same small commerce fixture, so these are related cases, not 12 independent
business datasets. Cases cover joins, refund fanout, dates, NULLs, empty cohorts,
candidate correction, write refusal, missing data and external actions.

Reference SQL is run on a separate database for exact columns/ordered-row
comparison. Nine hand-calculated answer assertions cross-check those references.
A further test ensures naive refund joins produce a wrong answer on this fixture.
Reference SQL and expected answers are not supplied to the planner or runtime
verifier. The model does receive explicit business definitions in the question.

The one-attempt arm replays the first response from the bounded arm. It is not
an independently optimized single-shot prompt. Real prompts/responses and model
metadata are retained, including unsuccessful attempts. Each configuration was
run once; no confidence intervals or generalization claims are warranted.

## Results

| Configuration | Correct answers / 9 | Expected refusals / 3 | Total / 12 | Wrong answers accepted |
|---|---:|---:|---:|---:|
| Qwen3-8B, prompt v2 | 6 | 3 | 9 | 2 |
| Qwen3-8B, prompt v3 | 7 | 3 | 10 | 2 |
| Qwen3-14B, prompt v3 | 6 | 3 | 9 | 2 |

Prompt v3 adds general checks for referenced tables, aggregation grain and
LEFT JOIN filtering. It was developed after seeing the v2 failures: this is a
development-set comparison, **not held-out improvement**. It fixed the total-net
case in this run but did not eliminate semantic errors. The larger model did
not improve overall performance. The old 36-case validation and schema-drift
results used earlier prompts; they are historical, not fresh v3 regression runs.

Remaining 8B v3 failures:

- Customer net: returned Ada 22,000 and Cy 0 cents instead of 12,000 and 6,000.
  Direct refund joins duplicate gross amounts; NULL arithmetic loses revenue.
- Empty March cohort: used the January date range and returned 29,000 instead
  of zero. The question included a January metric definition as background;
  the model applied it despite the explicit March request.

Both passed structural contracts. Thus runtime `completed` must not be read as
independent business correctness. These failures are intentionally retained.

8B v3 recovered one refusal outcome on retry: the missing-credit-score request
first generated invalid SQL, then stopped after execution feedback. This is not
a repaired correct SQL answer. The separate schema-drift experiment demonstrates
controlled answer recovery and has its own explicit fault-injection boundaries.

## Latency and model consumption

| Configuration | Median task latency | Observed P95 | Model calls | Prompt tokens | Completion tokens |
|---|---:|---:|---:|---:|---:|
| 8B v3 | 1.120 s | 1.753 s | 13 | 9,474 | 1,001 |
| 14B v3 | 1.959 s | 25.459 s | 15 | 10,985 | 1,538 |

P95 is nearest-rank over only 12 observations. Warmup/loading and resource
contention were not controlled; this is not a controlled speed comparison or
service-level objective. GPU details could not be verified with `nvidia-smi` in
the execution environment. Model digests/quantization details are recorded in
each manifest; OS details are in `metrics.json`. Local hardware/electricity cost
was not measured, so no dollar cost or cost-saving claim is made.

8B used one additional retry call (15 completion tokens); 14B used three (597
completion tokens). Timing comes from real bounded runs, not replay baselines.

## Artifacts

All paths below are relative to the repository root:

- `outputs/validation/commerce_v1_qwen3_8b/`: frozen v2 baseline and failures.
- `outputs/validation/commerce_v1_prompt_v3/`: 8B v3 run and metrics.
- `outputs/validation/commerce_v1_qwen3_14b_v3/`: larger-model comparison and metrics.
- `outputs/validation/commerce_demo_v1/`: failed initial customer-level demo.
- `outputs/validation/commerce_demo_v3/`: selected final three-task walkthrough,
  all independently checked. This subset is not the full benchmark.
- `outputs/validation/commerce_service_v1/`: unseeded HTTP run; the persisted
  job returned order 101 twice because the model added a refund JOIN. The
  assertion failed; the job database and service log retain the evidence.
- `outputs/validation/commerce_service_seeded_v1/`: repeat with an explicitly
  supplied correct candidate SQL; the independent check also failed. Its
  `summary.json` records the result, so this is not counted as a passing smoke test.

Use `scripts/validate_live_sql_agent.py` to repeat evaluation and
`scripts/summarize_sql_metrics.py` to compute observed latency/token summaries.
Use a fresh output directory to retain previous evidence.

## Engineering validation and remaining work

The regression suite has 53 passing tests, including the 10 new business-fixture
checks. Existing tests cover expired leases, stale ownership and infrastructure
retry budgets. These tests do not establish live process crash recovery.
`scripts/smoke_commerce_service.py` separately exercises real local HTTP,
authentication, idempotency and a queued task processed by a real-model worker.
Both HTTP runs passed those transport/queue checks but failed the business-answer
assertion. Earlier benchmark success on this question was therefore not stable
across these runs. No end-to-end service correctness or reproducibility claim
is supported. The smoke command deliberately exits nonzero on wrong answers.

Not completed: public deployment, real users, long-running service measurements,
mid-step resume, live worker-kill/model-timeout drills, per-tenant data permissions,
and general semantic verification. The next reliability work should target those
gaps rather than describing this prototype as production-proven.
