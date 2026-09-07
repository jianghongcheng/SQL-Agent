# Frozen paired SQL evaluation protocol

Declared before live inference, 2026-09-06. Implementation:
`scripts/run_paired_sql_benchmark.py`; task/oracle definitions:
`src/geomed_copilot/paired_benchmark.py`.

## Question and scope

Does adding execution retries or an independent model checker improve the
fraction of independently correct candidates retained by the controller, and at
what request/token/latency cost? Do the same methods recover after a controlled
transient failure? Does a frozen generated query remain correct on a second
database instance?

This is a new synthetic evaluation set frozen for this run, not a public
benchmark, a claim of unseen model training data, or a production workload.
Its 12 question families across inventory, support and shipping include familiar
SQL motifs. Each has two data instances: 24 question/database pairs, not 24
independent question families. Once results are inspected these cases become
development/regression data, not a reusable untouched holdout.

## Methods and controls

| Method | SQL planning rounds | Independent checker |
|---|---:|---|
| one_shot | 1 | No |
| execution_retry | Up to 3, execution/structural feedback | No |
| checked_agent | Up to 3, including disagreement feedback | One cached independent plan per episode |

All methods use the actual JobPipeline, the same `qwen3:8b` model, schema,
question, structural output contract, SQL authorizer, function/VM/output limits,
and bounded transport-retry helper. There is a shared ceiling of nine model
attempts across primary, checker and transport retries. One-shot intentionally
has fewer SQL rounds and may spend less: equal ceilings are not equal actual
costs. Report actual attempts and tokens; do not attribute gains from additional
spending solely to architecture. No additional framework, reference SQL or
catalog fallback is supplied at runtime.

All queries are generic and the service deliberately withholds automatic release.
Therefore “accepted correct” means the controller retained an independently
correct candidate, **not** a delivered result or production acceptance. Report
wrong controller acceptance separately from automatic release. A zero-release
policy cannot establish useful production precision.

## Design and grading

- 12 families × 2 instances × 3 methods × 2 profiles × 3 fresh trials = **432 episodes**.
- Profiles: clean, or one simulated first-primary-request failure. Six question
  families use timeout, six use HTTP 429. The same family has the same injected
  fault for every method/trial. These exceptions do not simulate outage duration,
  and faults later in the checker or persistent outages are outside this run.
- Database and model/planner state reset for every episode. The model is queried
  afresh; temperature zero is not assumed to guarantee deterministic output.
- Pair groups are shuffled with a declared seed; method order rotates to reduce
  warm-cache/time-order confounding. Inference is sequential; the local demo may
  share the machine, so latency is observational, not an isolated load test.
- Oracles are separate Python arithmetic/set/date calculations, checked against
  hand-computed examples before inference. They are consulted only after the
  production pipeline returns. Neither primary nor checker receives answer rows
  or reference SQL. The independent checker also receives no candidate SQL.
- Grade ordered output columns/rows because ordering is explicitly requested.
  Retain duplicates where relevant. Unknown/missing candidate is not a correct
  answer. No LLM judge supplies the final correctness label.
- Independently execute the frozen first/final proposed SQL against both database
  variants after inference. This checks accidental equality on one instance;
  it does not prove equivalence on every possible database. The method is informed
  by [test-suite SQL evaluation](https://aclanthology.org/2020.emnlp-main.29/).
- Verify source database bytes remain unchanged. Writes to the separate local
  job/audit database are expected, not prohibited side effects.

## Required reporting

For each method, separate clean/fault and domain/subtype results: independently
correct retained candidates, wrong retained candidates, correct candidates held,
coverage, first-to-final repairs/regressions, cross-instance correctness, observed
all-three/any-of-three success, attempt budgets, observed tokens and missing usage,
pipeline p50/p95, and attempts per correct retained candidate including failed
episodes. Pipeline time excludes offline scoring, queue and HTTP time. No dollar
cost estimate without a price or hardware/energy cost model.

Full-run repetition follows the reliability distinction used by
[τ-bench](https://github.com/sierra-research/tau2-bench): all-three success differs
from at-least-one success and from three repairs inside one execution.
Paired clean differences use 2,000 bootstrap resamples over **question families**,
not correlated database variants and repeats as if they were independent.
Only 12 families are available, so the interval is descriptive and cannot
establish US enterprise-wide performance or hiring competitiveness.

The runner writes a manifest, source copies and hashes, model digest, database
hashes, schedule and inputs before inference. Every wrong/stopped episode remains
in the denominator. There is no invented production pass threshold and no
architecture superiority conclusion unless the observed comparison supports it.
Runtime source files and prompts must remain unchanged until the run finishes.
