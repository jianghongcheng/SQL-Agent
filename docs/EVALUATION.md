# Evaluation

This document separates model configuration comparisons, product acceptance,
external-dataset evaluation, and software verification. Each result retains its
own dataset, denominator, and execution conditions.

## Software verification

The clean public checkout passed 237 tests locally on 2026-09-08, with one
dependency deprecation warning. GitHub CI checks tests, source compilation and
reproducible Harbor export. Optional browser/data tests may skip without their
dependencies. This is software verification, not model accuracy.

## Qwen3-14B configuration comparison

26 known development questions × two fixed database instances × three runs:
156 episodes per configuration. Questions cover inventory, support, logistics,
billing and manufacturing. Repeated runs do not add independent questions.

| Configuration | Correct / wrong / stopped | p95 |
| --- | --- | --- |
| Coder 14B, one SQL round | 102 / 42 / 12 | 2.12 s |
| Qwen3 14B, no thinking, repair enabled | 108 / 48 / 0 | 2.23 s |
| Qwen3 14B, thinking and repair | 142 / 13 / 1 | 74.83 s |

Answers were scored against independent Python results, including column names,
ordered rows, duplicates and values. Each saved SQL was additionally checked on
two instances. Reference answers were not provided to the runtime.
The reasoning configuration used Q4_K_M, up to 8192 output tokens, 16384 context,
120-second requests and up to three SQL rounds. First-query correctness was
138/156; final correctness was 142/156. Thirteen wrong candidates remained.

Model, sampling, budgets and repair settings differ between configurations.
This is not a single-factor thinking ablation. The selected configuration's
91.03% is not unseen-database or production accuracy. All general outputs require
review. The 74.83-second latency motivates asynchronous jobs.

Reproduce with local Ollama and a fresh output directory:

```bash
PYTHONPATH=src:. python scripts/run_quality_regression.py --output outputs/validation/quality_fresh --repeats 3
```

## Flexible-output product acceptance

Six questions × two deterministic synthetic datasets yielded 11/12 correct
first-run candidates, one wrong candidate, and no automatic release. Questions
cover scalar, list and grouped outputs. Answers were calculated independently.
An initial concurrent-polling failure was retained and fixed. After the fix,
four concurrent requests returned, three correctly; observed submit-to-result
times were 79.64, 103.18, 139.00 and 173.63 seconds. This short burst is not
sustained throughput or a production availability measurement.

The queue fix did not establish improved answer correctness. Process/transport
fault checks used recorded SQL response fixtures and are not model-availability
measurements. See [acceptance runner](../scripts/run_product_acceptance.py),
[operational runner](../scripts/run_operational_acceptance.py) and
[independent fixtures](../scripts/commerce_acceptance_cases.py); inspect each
runner's `--help` for parameters before starting a new run.

## Alternative strategies

| Experiment | Scope | Result |
| --- | --- | --- |
| Independent checker | 12 synthetic question families × 2 instances × 3 repeats × 2 conditions × 3 methods = 432 episodes | Normal condition: direct/retry 39/72 correct, checker 30/72; checker rejected wrong and correct outputs |
| Relational planning | 144 episodes, same Qwen3-8B model | 42/72 vs 39/72 correct; calls doubled; descriptive difference interval crosses zero |
| Data probes | 144 episodes, same Qwen3-8B model | 38/72 vs 39/72 correct; 137 successful probes did not establish answer improvement |

For the checker under normal conditions, wrong retained candidates fell from
33 to zero, while 42/72 checker runs stopped. Under injected transient failures,
three wrong candidates passed checker agreement. Agreement is not correctness.
Actual call counts differ; neither extra computation nor recovered transport
requests imply improved semantics.

```bash
PYTHONPATH=src:. python scripts/run_paired_sql_benchmark.py --help
```

Use the runner's frozen cases and independent scorer. Save model/configuration,
source and data hashes, full schedule, all outcomes, costs and failures. Once
results inform changes, that data is development data, not a fresh holdout.

## Historical external BIRD Mini-Dev check

Qwen3-8B v2 covered 500 questions across 11 canonical databases with BIRD input
adaptation. First-candidate set-of-rows matches: 135/500; bounded repair:
140/500; multiset matches: 128/500. Five reference queries could not be scored
within limits. Of 358 retained candidates, 217 were scored wrong. These questions
have been used for analysis and are no longer unseen. This was not an official
leaderboard submission or an HTTP/worker end-to-end test.

A separate checker retained 96 correct, 75 incorrect and one unscorable agreeing
candidate. It did not prove semantic validity. These Qwen3-8B results must not
be replaced by the Qwen3-14B development score above.

```bash
PYTHONPATH=src:. python scripts/validate_bird_external.py --full --databases data/local/bird_mini_dev/databases_full --output outputs/validation/bird_fresh
```

Dataset source revisions and attribution are in
[dataset registry](../data/dataset_registry.json). Obtain datasets separately and
respect their terms. Their contents are not bundled as runtime databases.

## Artifacts and reproduction limits

Synthetic frozen SQL-repair fixtures and historical model proposals remain in
`data/benchmarks/`; their evaluation artifacts are in `outputs/portfolio/`.
Harbor task fixtures are public, not hidden from repository readers.
These earlier protocols are separate from current live-generation results.

Raw `outputs/validation/` runs, logs, snapshots and third-party source databases
are local-only. References to them in scripts or manifests do not mean they ship
with a clone. Re-running requires the documented models, inputs and environment.
The public summaries are not a substitute for independent reproduction.
