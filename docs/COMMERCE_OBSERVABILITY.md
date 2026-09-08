# Measured operations and regression evidence

Checked 2026-09-06. This report covers evaluation, observability, backend
reliability, and cost/latency measurements.

## Implemented changes

Each completed pipeline result now persists `telemetry`, including primary and
checker request counts, failures, transport retries, request duration, retry wait,
and observed input/output tokens. Failed JSON responses with usage still count;
timeouts with no usage are explicitly unknown. Provider adapters expose usage to
the worker, not just offline scripts. Recovery observations exclude prompts,
response text, endpoint URLs and credentials.

`pipeline_elapsed_ms` measures the worker pipeline, excluding queue wait and HTTP
latency. It is not user-perceived end-to-end latency. The local dashboard shows
runtime, calls, retries and token coverage. Monetary cost remains null: neither
local hardware/power pricing nor a hosted-provider price schedule is configured.

HTTP metrics now accumulate fixed histogram buckets rather than storing every
request duration. Review, replay and trace routes normalize identifiers; unmatched
paths and custom methods use bounded labels. A regression test sends 50,000
observations across unique paths and verifies five retained label combinations,
fixed bucket storage, correct counts and no leaked path IDs. This establishes
bounded observation storage for that input pattern, not a service load SLO.

## Experiment and rejected changes

Run `scripts/validate_commerce_observability.py --output NEW_DIRECTORY` with
`PYTHONPATH=src:.`, dependencies installed and Ollama `qwen3:8b` running.
The directory must be new. Every episode saves its job, telemetry and trajectory;
the process exits nonzero when any required task fails, after retaining evidence.

The same 24 episodes combine four fixtures (empty, approved/pending, multiple
approved refunds, pending-only), three metrics and two profiles (clean and one
controlled timeout before a real provider request). Outputs are independently
graded by Python arithmetic. No initial answer SQL or catalog fallback is used.
The injected timeout is simulated, not a naturally occurring provider outage.

| Configuration | Correct released results / 24 | Wrong releases | Not released | Successful tasks after injected timeout / 12 |
|---|---:|---:|---:|---:|
| v1: original generation/context, new telemetry | 22 | 0 | 2 | 11 |
| v2: extra generic scalar-total prompt guidance | 12 | 0 | 12 | 6 |
| v3: original planner, metric-specific context | 20 | 0 | 4 | 10 |

Both proposed generation/context changes regressed and were reverted. The final
deployment retains v1 generation/context plus the new operational measurements.
Raw artifacts: `outputs/validation/commerce_observability_v1/`, `_v2/`, `_v3/`.
These are three development runs of the same 24 cases, **not 72 unique tasks**.

The remaining v1 failure is net revenue when an order has multiple approved
refunds. The model joins detail rows and duplicates order amounts. The verifier
blocks the incorrect result, but retries fail to repair it: this is safe withholding
within this fixture, not successful task completion. The two affected episodes
are clean and injected-timeout versions of the same task.

V1 observed 50 model attempts, including 12 injected failures without usage;
all 24 episodes had telemetry and all source files were unchanged. Its sample
pipeline p95 was 2870.759 ms. One trial per fixture/metric/profile is insufficient
for a stable latency estimate, repeated-run reliability claim, or an SLO.
The original 500-question BIRD results remain separate and unchanged.

## Verification and remaining work

Full Python regression suite: 151 passed (one existing dependency deprecation
warning). New tests cover histogram boundaries/storage, adapter usage, malformed
JSON accounting, missing usage, exhausted timeout retries and per-job accounting.
The local API/browser acceptance scripts also verify visible telemetry, zero model
requests for blocked sources, and the existing query/review flow.

Next meaningful correctness work requires new independent fixtures and a repair
method that fixes grain errors without degrading simpler tasks. More prompt text
alone did not pass this regression exercise. Cloud operations, actual user feedback,
and true end-to-end cost/latency evidence remain unestablished.
