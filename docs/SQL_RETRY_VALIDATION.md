# Real-model bounded retry validation

The SQL agent recovered from explicitly injected schema changes using real
`qwen3:8b` responses. This establishes controlled recovery capability, not an
improvement in natural Text-to-SQL accuracy. The previous 36 validation cases
succeeded without retries and therefore supplied no evidence of retry benefit.

## Protocol

`scripts/validate_live_sql_retries.py` freezes 12 synthetic cases before inference:
three tables, each with zero, one, two, or three column renames. The harness
renames a column after planning and before execution, modeling schema drift.
These are deliberately injected failures, not naturally occurring model errors.
The agent does not issue DDL; production execution remains read-only.

Each case has four paired arms: one attempt, two attempts with feedback, three
attempts with feedback, and three attempts with frozen initial schema and no
error feedback. Every arm uses the identical first real-model response and the
same migration schedule prefix. Subsequent responses are real model calls;
none are edited or replaced with gold SQL. Fixed contracts are identical across
arms. Gold queries are executed independently for exact output grading and are
never included in planner context.

The frozen arm ablates schema refresh and execution feedback together. It does
not isolate their individual effects. The attempt ceiling is matched, but actual
call counts can differ: duplicate-proposal detection ends some runs early.
The first response was generated in the three-attempt context then replayed;
this is a paired ablation, not an independently optimized single-shot baseline.

## Results

Correct answers, across three cases per row:

| Injected column changes | One attempt | Two attempts + feedback | Three attempts + feedback | Three attempts, frozen evidence |
|---|---:|---:|---:|---:|
| 0 | 3/3 | 3/3 | 3/3 | 3/3 |
| 1 | 0/3 | 3/3 | 3/3 | 0/3 |
| 2 | 0/3 | 0/3 | 3/3 | 0/3 |
| 3 | 0/3 | 0/3 | 0/3 | 0/3 |

There were 47 live model calls and 36 first-response replays across 48 arms.
No arm falsely accepted an incorrect answer. Under three consecutive changes,
the feedback agent exhausted its three-attempt budget and stopped in all three
cases. These are expected negative controls, not successful answers.

Actual `customers_drift_2` execution trace:

1. `SELECT name AS item FROM customers ORDER BY id` → `no such column: name`.
   Harness had renamed `name` to `display_name` after planning.
2. `SELECT display_name AS item FROM customers ORDER BY id;` →
   `no such column: display_name`. Harness had renamed it to `customer_label`.
3. `SELECT customer_label AS item FROM customers ORDER BY id;` →
   column `item`, rows `Alpha`, `Beta`, matching the independent reference.

This demonstrates **three total attempts, including two retries**. Success
depends on refreshed evidence and the environment stabilizing within budget.
It does not demonstrate semantic-error detection, arbitrary failure recovery,
production reliability, or statistical generalization. The cases are small,
related synthetic scenarios with one run per case and model temperature zero.

## Artifacts and reproduction

Raw prompts, responses, token metadata, injected DDL, errors, outputs, and agent
execution records are in `outputs/validation/live_sql_retry_drift_v1/`.
`manifest.json` records model details and hashes of source, harness, and cases;
`summary.json` contains the table counts. The harness refuses to overwrite an
existing output directory.

```bash
PYTHONPATH=src:. python \
  scripts/validate_live_sql_retries.py \
  --output outputs/validation/live_sql_retry_drift_new
```

Existing regression suite: **43 passed**. Artifact checks additionally verified
identical first responses, fixed contract hashes, matching migration prefixes,
and zero false accepts across all 48 arms. Production agent code was unchanged
for this experiment.
