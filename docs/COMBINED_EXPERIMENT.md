# Combined validation protocol

Follow-up: [all 110 questions in the three databases](BIRD_110_VALIDATION.md)
have now been executed without changing the production code, model or prompt.
This document preserves the earlier 30-question combined run.

This experiment combines different evidence tracks under one frozen run, with
separate denominators. It does not combine SQL accuracy, refusals, repetitions
and infrastructure tests into one success rate.

## Reproduce

Prerequisites: Python dependencies, local Ollama `qwen3:8b`, the downloaded
official Mini-Dev SQLite questions under `data/local/bird_mini_dev`, and the TLC
import described in [DATASET_VALIDATION.md](DATASET_VALIDATION.md).

```bash
python scripts/fetch_bird_databases.py
python scripts/run_combined_validation.py --output outputs/validation/combined-new
```

The first command downloads only three database directories and descriptions
from the [official Mini-Dev package linked by its maintainers](https://github.com/bird-bench/mini_dev).
It uses bounded HTTP ranges, validates ZIP CRCs, and records file SHA256 hashes.
Skip it when the database directory already exists. Raw BIRD data retains its
CC BY-SA 4.0 attribution and remains under ignored local data.

The second command writes the protocol before any model calls, runs every track,
retains stdout/stderr, and writes a combined manifest/summary. Source hashes are
checked again at the end. Use a new output directory for each run. An exit code
of zero means all runners completed, not that every SQL answer was correct;
inspect the per-track scores and failures.

## Tracks and comparison boundaries

| Track | Frozen scope | What is measured |
|---|---|---|
| External SQL | 30 BIRD Mini-Dev cases: 10 each for California schools, financial and student club | One proposal versus up to three attempts, sharing the first response |
| Real records | Six TLC tasks, three repeats each, exploratory and verified modes | Exact answers against independent Python checks; catalog fallback separately |
| HTTP workload | 24 submissions, four clients, two worker processes | Correctness, idempotency, completion latency, actual model inference |
| Injected drift | 12 cases across zero/one/two/three schema changes | One/two/three-attempt recovery, frozen-evidence control, budget exhaustion |
| Regression | Full current suite | Semantic guards, real worker kill/recovery, lease fencing, HTTP model timeout, dataset provenance |

External case selection is the first 10 SHA256 hashes of
`contractsql-bird-v1:<question_id>` within each declared database. No cases are
removed after seeing predictions; failed references remain visible. This is a
small fixed subset, not the full BIRD score or a previously untouched training
holdout. No model/prompt changes are made during this combined run.

The external track provides official question/evidence, schema and column
descriptions to a benchmark adapter. Gold SQL is used only by a separate offline
connection after generation. It is not supplied to the planner, runtime business
verifier, fallback or output contract. The adapter accepts dynamic output columns
because BIRD has no service-owned output contract; the deployed fixed-contract
planner is not used unchanged. Production read-only authorization, function
allowlist, VM budget and bounded loop are retained. This restriction can reject
valid BIRD SQL and must remain visible in the score.

External execution match uses set-of-rows equality, following the
[official EX implementation](https://github.com/bird-bench/mini_dev/blob/main/evaluation/evaluation_ex.py).
A second multiset metric preserves duplicate-row differences. Column aliases
are ignored, column order retained. Set/multiset scores do not test result order.
The evaluation caps results at 10,000 rows and reference execution at 30 seconds;
reference errors are reported separately, with no silent denominator reduction.

Business-catalog results are never reported as external model accuracy. The
paired TLC verified arm replays its first proposal, so its timings exclude first
inference and are not comparable end-to-end latency. HTTP load uses actual model
calls. Drift failures are injected, not claimed as naturally occurring failures.

BIRD-Critic official correctness scoring and Spider 2.0 are **not included** in
this run. Their earlier inventory/research is not counted as experimental data.
The combined evidence does not establish real-user adoption, production uptime,
tenant isolation or a sustained-load SLA.

Run artifacts: `outputs/validation/combined_v1/protocol.json`, per-track logs,
per-case records and `summary.json`.

## Completed run: combined_v1

Completed 2026-09-06. All five runners finished with exit code zero; production
source hashes were unchanged throughout. No tuning or model changes occurred
between tracks. Results are not all successful SQL answers:

| Track | Observed outcome |
|---|---|
| External BIRD, single attempt | 10/30 set matches; 9/30 multiset matches |
| External BIRD, up to three attempts | 10/30 set matches; 9/30 multiset matches; no recovered correct answers |
| TLC exploratory | 18/18 correct across six unique questions; zero fallback |
| TLC paired verified | 18/18 correct; first-response replay, zero fallback |
| HTTP load | 24/24 correct; 24/24 duplicate submissions deduplicated; zero fallback |
| Schema drift | One change: 3/3 recovered in two attempts; two changes: 3/3 recovered in three attempts |
| Continuous schema change | Three changes: 0/3 answered; all exhausted the three-attempt budget |
| Regression | 72 passed, one dependency deprecation warning |

HTTP latency: median **2.008 s**, observed P95 **2.433 s**, measured throughput
**1.865 jobs/s** over a 12.870-second workload. This is local acceptance evidence,
not a service-level objective. TLC paired timings are excluded from this HTTP
measurement. The source contains 48,326 real trip rows and 265 zones.

### External SQL failure evidence

There were no reference execution errors. Per database, set matches were
California schools 3/10, financial 3/10 and student club 4/10, unchanged by retry.
The bounded run accepted 25 outputs: 10 matched the reference and 15 did not.
Five cases stopped. `false_accept` in the artifact means accepted but disagreed
with the benchmark reference; it is not independent human adjudication of
potentially ambiguous questions.

Case 79 changed from an execution failure to an accepted reference-disagreeing
answer after retry. This increased accepted disagreements from 14 to 15 without
increasing correct answers. Thus the retry capability demonstrated under schema
drift did **not** translate to an accuracy gain on these natural questions.

Case 125 repeated SQL referring to an unjoined table and was stopped. Case 24
misinterpreted a threshold condition and added an output column. Case 1411 passed
set comparison but failed the multiset check, exposing duplicate sensitivity
hidden by set-based execution accuracy. All raw responses and execution records
are preserved by question ID under `external_sql/`.

### Engineering conclusion

The fixed-task/read-only service has measured local correctness, concurrency,
idempotency and recovery evidence. **The unconstrained SQL question-answering
path is not production-ready:** the external test reveals substantial semantic
errors that execution success and structural checks cannot catch. A catalog
fallback must remain explicitly identified and must not be enabled in the BIRD
blind evaluation to improve its score artificially.

Before broadening supported business questions, improve and independently
evaluate question interpretation, join planning and semantic acceptance. Reserve
new cases for subsequent validation; do not tune on these 30 and call a rerun
held-out generalization. The current narrow SQLite function/VM limits and the
benchmark-specific dynamic-column adapter also remain part of the reported
evaluation envelope. No full BIRD, BIRD-Critic or Spider 2.0 score is claimed.
