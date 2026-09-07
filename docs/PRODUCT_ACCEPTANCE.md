# Flexible SQL analysis: small-scale product acceptance

This acceptance evaluates a local, single-worker SQL Data Agent. It does not
measure external-user adoption, production availability, or a public benchmark.

## Product change

The `commerce_analysis` task uses one registered SQLite database and permits
variable result columns. Users can ask for totals, order lists, and monthly
summaries without registering a different output schema for every question.
The homepage selects this task by default and offers three editable examples.

The contract still requires read-only execution, no more than 200 rows for this
task, 1–50 uniquely named result columns, and human review. Dynamic columns cannot
be combined with a fixed business-reference verifier. Existing fixed contracts
retain their previous hashes and semantics. This is flexibility within a
registered source, not arbitrary database access or automatic semantic proof.

The page records observed time from clicking Submit until it first displays a
terminal result. This includes request handling, queue wait and polling. It is
reported separately from worker processing time and is only available when the
current page observed that submission; reopening an old job does not invent it.

## Frozen evaluation

`outputs/validation/product_acceptance_v1/manifest.json` was written before the
first evaluation request. It records source snapshots, data hashes, model digest,
configuration and the complete schedule. `frozen_cases.json` contains six newly
authored questions on each of two deterministic synthetic datasets, with ordered
answers computed in Python before inference. No answer or reference SQL is sent
to the worker. This is 12 first-run question/instance episodes, not 12 distinct
questions and not a held-out public benchmark.

Questions cover a paid-order total, a date/amount-filtered list, monthly grouping,
net revenue with multiple refunds, customers without paid orders, and ties for
the largest customer total. The data includes cancelled orders, missing children,
NULL refund amounts, repeated amounts and tied maxima. An explicit hand-calculated
fixture tests the Python oracle before the run.

The model profile is Qwen3 14B through local Ollama, reasoning enabled, seed 917,
8192 output tokens, 16384 context, 120-second request timeout and at most three SQL
rounds. There is no separate planner model, independent checker or data probe.
All incorrect candidates and stopped runs stay in the denominator and artifacts.
Once these outcomes are inspected or used for a fix, this set becomes regression
data. A future accuracy claim needs another untouched set.

## Workflow, faults and performance

Three additional model-generated queries exercise scalar, list and monthly
outputs on one demo database. Four additional real inference requests are
submitted concurrently to one API process and one SQL worker. These repeat known
questions and are reported separately from first-run correctness.

Client latency is measured with a monotonic clock, before the POST through the
first observed terminal GET, using a 100-ms polling interval. All waiting and
failed work counts. Report per-condition latency rather than describing a short
four-request workload as sustained production throughput.

Resource samples record API/worker RSS and CPU seconds, plus device-wide GPU
memory and utilization. GPU observations include any other work on the same GPU;
they are not attributable to an individual query. No artificial warm-up requests
are removed from measured latency.

Fault drills use an isolated API/job database/worker and a local HTTP proxy:

- SIGKILL the worker after its model HTTP request is in flight, then recover the
  same job after its actual three-second lease expires.
- Restart the API with a queued job and verify durable recovery.
- Send eight simultaneous submissions with one idempotency key; verify one job,
  one submission event and a consistent persisted review.
- Delay one provider response past a 250-ms client timeout, then recover on the
  next request; delay every response and verify bounded stopping after retries.

The fault proxy replays a provider-format fixture reconstructed from previously recorded final SQL and usage after the
injected failure. This isolates process/queue/transport behavior; it is not fresh
model inference or evidence of model availability. Normal correctness and
concurrency trials use real Ollama inference. A permanent timeout should stop
safely, not be counted as successful answer recovery.

## Reproduce

```bash
PYTHONPATH=src:. python scripts/run_product_acceptance.py freeze --output outputs/validation/product_acceptance_fresh
PYTHONPATH=src:. python scripts/run_product_acceptance.py run --output outputs/validation/product_acceptance_fresh
```

Requires the installed model, local Ollama, and API dependencies. Use a fresh
output directory. The runner starts isolated services and removes its processes
on completion, leaving records, logs and databases intact. Any exception is saved
in `summary.json`; never replace a failed run with a successful screenshot.


## First-run results and concurrency failure

The v1 first-run evaluation completed all 12 episodes: **11 correct and 1
incorrect**, all routed to review, with no automatic release. Sequential client
submit-to-result p50 was **24.25 seconds**, p95 **96.35 seconds** (nearest rank).
Each episode made one model request. This is a small six-question synthetic set,
not a production accuracy estimate.

The failed query omitted the required `paid` status predicate and returned two
cancelled orders. Its SQL executed and matched the requested column names, so
structural checks did not detect the semantic error. The full candidate and
expected rows remain in `evaluation_04.json`.

All three separately measured demo shapes returned the expected rows: total
**58250 cents**, a **17-row** order list, and **4 monthly rows**. Their client
latencies were 8.70, 21.44 and 10.29 seconds. Output aliases were not fixed for these
three questions; the grader compared the requested ordered row values.

The subsequent four-request concurrency stage failed with an HTTP read timeout.
The v1 summary deliberately remains `completed: false`, even though the earlier
correctness and demo phases finished. Three jobs were queued and one running when
the harness stopped its own processes; no successful concurrency result is claimed
for that run.

A separate no-model reproduction also timed out under concurrent API polling.
Python thread dumps showed one queue thread in connection close and other threads
in connection open. The queue now serializes short SQLite connection transactions
within each process; model inference is outside that lock. The same real-HTTP
reproduction then completed **400 reads in 0.62 seconds** without timeout. This is
a local mitigation with a throughput tradeoff, not an upstream SQLite diagnosis
or evidence about other builds.

`product_operations_v2` repeats the operational phases with the queue fix. Its
questions are reused from v1 and must not be called a fresh accuracy evaluation.
Provider-format fixtures for fault recovery are reconstructed from the recorded
final SQL and usage; these drills make no new inference claims.


## Operational rerun and live browser results

The separately frozen v2 run completed with source, model and input hashes
unchanged. Four concurrent requests to one SQL worker all returned; **3/4 were
correct**. Observed submit-to-result times were 79.64, 103.18, 139.00 and 173.63
seconds. The 173.63-second burst completed 1.38 jobs/minute; this is not sustained
capacity. The retained error in `concurrent_1.json` subtracted refunds and omitted
the paid predicate when the question asked for paid-order totals. No semantic
correctness improvement is claimed from the queue fix.

All five operational checks passed: worker termination/reclaim, API restart,
eight duplicate submissions producing one job and one consistent review trail,
transient timeout recovery, and bounded stopping on persistent timeout. Worker
recovery took 3.45 seconds with a three-second lease and a recorded response
fixture. Persistent timeout exhausted three adapter calls and produced no
candidate. These are process/transport tests, not fresh model recovery estimates.

There were 179 resource samples. Peak API RSS was 55.59 MiB and worker RSS 25.07
MiB; these exclude the Ollama model server. Device-wide GPU memory peaked at
15729 MiB and utilization at 99%, including other GPU activity. Per-process CPU
seconds remain in `resources.json`. This short run does not test a memory leak,
long-running stability, multi-worker scaling or a production SLO.

The live browser run passed login, three model-generated queries on the same
source, approval for each, and reopening historical evidence. Results were
58250 cents, 17 orders and four monthly totals; observed click-to-result times
were **9.32, 21.29 and 10.78 seconds**. No JavaScript errors occurred. Evidence is
`runtime/local-demo/flexible-acceptance.json` and the timestamped `flexible-runs`
directory. These repeated demo questions are not additional held-out accuracy.
The full automated suite passed **237 tests** (one dependency warning).

Regenerate the combined local report with:

```bash
PYTHONPATH=src:. python scripts/publish_product_acceptance.py
```

A defensible interview claim is: built and locally validated a SQL Data Agent
with variable result shapes, review and audit history, bounded read-only
execution, durable job recovery and idempotent submission; reported correctness,
end-to-end latency and failures under frozen, explicitly limited conditions.
External-user usefulness and production readiness remain unvalidated.
