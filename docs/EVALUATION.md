# Evaluation

This document separates model configuration comparisons, product acceptance,
external-dataset evaluation, and software verification. Each result retains its
own dataset, denominator, and execution conditions.

## Latest verified results — 2026-09-09

- [SQL correctness repair](SQL_CORRECTNESS_REPAIR.md): **21/48 → 35/48** on the
  inspected six-family development set; **6,629 → 4,250 tokens per correct task**;
  p95 **5.85 → 5.91 s**. After repair, **2/13 wrong candidates** receive verifier
  agreement. All general answers require human review; this is not blind accuracy.
- [Small-model QLoRA](SMALL_MODEL_COMPARISON.md): newly trained 0.5B **44/100 →
  51/100**, compared with historical 1.5B **52/100 → 59/100**. Both conditions use
  identical JSON-fence normalization. The adapters are not promoted.
- [Public evidence](evidence/2026-09-09/README.md) contains synthetic development
  records, expected results, model identities, metric denominators and hashes.
- A frozen 108-case holdout/challenge protocol is prepared, but no completed,
  verified result is included in this release. It is not counted as a passed gate.

The 91.0% historical thinking-model experiment below uses different models,
settings and repeated questions. Do not substitute it for the current pipeline.

## Current local acceptance protocols

The local implementation extends the historical results below with three separate
protocols. A completed run demonstrates its stated scope, not production readiness.

- `prepare_agent_acceptance.py` freezes six existing developer-authored commerce
  families across fresh data seeds. The default has 48 instances, not 48 independent
  task families. Python arithmetic computes the expected results; evaluation files
  are never mounted into the Agent containers.
- `validate_live_rag_deployment.py` runs BM25, hybrid and hybrid-plus-cross-encoder
  against the same cases and Planner/Verifier settings. It records every failure,
  candidate, review decision, observed token usage, submit-to-result timing, read-only
  database hashes and restart evidence. Two warm-up jobs per condition are retained
  separately. CPU retrieval runs inside isolated containers; generation uses the
  configured local Ollama service on the shared host. All general results still
  require review. Agreement rates are not automatic-release rates.
- `analyze_sql_lora.py` verifies saved generation/dataset hashes, computes paired
  fixes and regressions, and resamples entire source domains for uncertainty.
  The 100-case pilot is 52 correct before and 59 after adaptation, with nine fixes
  and two regressions. The reproducible domain-cluster interval includes zero;
  the candidate is not promoted. Data labels are source-provided, not manually
  verified clinical or commercial outcomes.

Cost is measured in **input and output tokens**. Report Planner and Verifier
usage, failed calls, retries, and total observed consumption per submitted job
and per correct result. The latter includes spend on all incorrect/failed jobs,
not just tokens from successful jobs. Incomplete provider usage or an unobserved
crashed attempt makes the total unknown; observed counts remain a lower bound.
Monetary conversion requires explicit input/output model prices and is not used
for this acceptance. GPU board samples are optional resource observations only.

The [Strong Signal acceptance record](STRONG_SIGNAL_ACCEPTANCE.md) separates
local engineering acceptance from semantic accuracy and model promotion.

Reproduction uses fresh output directories and locally available models:

```bash
PYTHONPATH=src:. python scripts/prepare_agent_acceptance.py --output /tmp/agent-cases --instances 8
docker build -f Dockerfile.rag -t sql-agent-rag:local .
PYTHONPATH=src:. python scripts/validate_live_rag_deployment.py \
  --dataset /tmp/agent-cases --output /tmp/agent-evaluation \
  --image sql-agent-rag:local --embedding /path/to/local/minilm \
  --reranker /path/to/local/cross-encoder
```

The runner removes only its generated containers and retains fixture/control files,
private Compose configuration and raw evidence locally. Host networking is used
to reach loopback Ollama; this is a single-workspace acceptance deployment, not a
network-isolated multi-tenant installation. Do not publish the private Compose file.

If Docker lacks a GPU runtime, `run_isolated_inference_trial.py` owns a separate
native Ollama process and points the Docker API/Workers at its ephemeral loopback
port. It does not change the installed service. Existing model files must be
non-writable; cloud access and startup pruning are disabled. The trial sets a
4096-token context, two resident models, one parallel request per model and flash
attention. Wait for sufficient free VRAM rather than stopping other workloads.
This is a serving-profile comparison, not a single-factor keep-alive ablation.

```bash
PYTHONPATH=src:. python scripts/run_isolated_inference_trial.py \
  --output /tmp/isolated-agent-evaluation \
  --models /usr/share/ollama/.ollama/models -- \
  --dataset /tmp/agent-cases --image sql-agent-rag:local \
  --embedding /path/to/local/minilm --reranker /path/to/local/cross-encoder
```

## Historical software verification

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
