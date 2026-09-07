# Fresh Qwen3-8B validation

This is the **pre-fix baseline**. See [false-refusal fix validation](SQL_PLANNER_FIX_VALIDATION.md)
for subsequent results; the failed baseline remains preserved below.

Run: 2026-09-05, existing local Ollama `qwen3:8b`, Q4_K_M. Model digest and
suite hash are saved in the manifest. No model weights, runtime code or prompts
were changed in response to this run's failures.

Command:

```bash
python scripts/validate_live_sql_agent.py --model qwen3:8b \
  --output outputs/validation/live_sql_qwen3_8b_20260905
```

The script froze 21 synthetic cases across employees, orders and tickets before
calling the model. It saved full prompts, raw completions, token/timing metadata,
execution traces and offline grading. Gold SQL is available only to the grader,
not the model prompt or runtime verifier. Each source has four synthetic rows;
this is a small functionality test, not a representative generalization study.

## Observed results

| Case type | Correct outcomes |
|---|---:|
| Valid query | 3/3 |
| Missing-column repair | 3/3 |
| Wrong-filter repair | 3/3 |
| Grouped aggregation | 0/3 |
| Output alias correction | 0/3 |
| Unsafe write requests | 3/3 stopped |
| Unsupported network requests | 3/3 stopped |

Legitimate task completion: **9/15 (60%)**. Restricted/unsupported requests:
**6/6 stopped**. Total mixed outcomes: **15/21**, not a 15/21 query-repair score.
All six safety cases were stopped by the model itself; they do not demonstrate
that the policy layer intercepted unsafe model proposals in this run.

Accepted semantically incorrect answers observed: **0**. This small result does
not establish semantic verification; the contract is still structural. All six
legitimate failures were explicit model STOP responses, not SQL engine errors.

There were **21 real model calls**, one per case. Total bounded-run wall time was
about **24.2 seconds**, including the first request's loading overhead. No retry
was executed. A paired first-proposal replay achieved the same 15/21 outcomes;
this is not a second independently prompted experiment. Incremental benefit of
retry is therefore **not demonstrated**.

An additional tool/verifier diagnostic executed the 15 reference queries through
the same SQL policy and contract checks: **15/15 passed**. This isolates the six
failures to planning/refusal behavior for this fixture. Reference execution is
an integrity check, not model performance and not evidence of a successful fix.

## Artifacts and next gap

Local artifacts: `outputs/validation/live_sql_qwen3_8b_20260905/` contains
`manifest.json`, `cases.json`, per-case raw output, `summary.json`, and
`reference_query_diagnostic.json`. These artifacts are stored locally and have
not been pushed; the script and this report are reviewable source.

The next engineering target is unnecessary refusal on valid aggregation and
alias tasks. Do not silently retry every STOP: deliberate refusals protect the
unsupported/write cases. Any prompt/router change must be checked on a separate
new task set as well as these known failures. Additional cases that actually
trigger execution/verification failures are needed to evaluate adaptive retries.
