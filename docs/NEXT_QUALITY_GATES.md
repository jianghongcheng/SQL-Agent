# Remaining quality gates

Only three workstreams remain: SQL correctness, production evidence, and generalization.
The existing local engineering checklist is complete; none of the evidence below may
be replaced by more component tests, synthetic traffic presented as real traffic, or
repeated evaluation of familiar question templates.

## 1. SQL correctness — active development

The original BM25 development run has 48 cases across six known question families:

| Family | Correct |
| --- | ---: |
| Paid revenue | 8/8 |
| Qualifying orders | 8/8 |
| Monthly report | 5/8 |
| Customer net revenue | 0/8 |
| Customers without purchases | 0/8 |
| Highest-value customers including ties | 0/8 |

The knowledge was retrieved for failing examples. Observed errors include null-rejecting
WHERE predicates after LEFT JOIN, aggregation fan-out, incorrect anti-existence and
missing zero-valued customers/ties. Development work starts with explicit population,
output grain and aggregation planning in the SQL generator. No expected SQL or rows
are inserted into its prompt. A frozen before/after comparison retains all 48 cases,
wrong answers, unavailable results, verifier status, token totals and paired family
bootstrap intervals. A better score here is development progress, not generalization.

Success is correct output against the external oracle, not SQL execution, verifier
agreement, a needs_review status or absence of exceptions. Human approval remains.
Every regression must be listed; do not repeatedly tune against a claimed blind set.

## 2. Production evidence — requires real workload and SLO agreement

First obtain authorized, de-identified request traces and a read-only database snapshot
(or an explicitly approved production read path). Define expected answers or a human
adjudication process, workload mix, concurrency/arrival-rate envelope and timeout before
measuring. A workload without a quality oracle cannot establish successful task cost.

Proposed collection stages: a 24-hour local soak, then at least seven days of real
workload observation. These durations are a plan, not completed evidence. Local
synthetic soak is recorded separately and cannot pass the real-workload gate.

Freeze the SLO targets and measurement window before running; the repository does not
yet contain an agreed business SLO. Report:

- Attempts submitted, terminal outcomes, infrastructure failures, semantic failures,
  unresolved/manual-review outcomes and missing telemetry, with explicit denominators.
- Client submission-to-terminal p50/p95/p99, including queue time, with sample counts,
  timeouts/censored requests and hourly distributions. Do not remove slow failures.
- Service availability separately from correct-answer rate. Do not combine these into
  an undefined failure-rate number or count pending reviews as successful tasks.
- Total input/output tokens across successes, wrong answers, failed calls and retries,
  divided by independently verified successful tasks. No verified successes means the
  ratio is undefined. Incomplete usage means the exact total is unknown.
- Time-bucketed queue age/depth, process/GPU memory, restart/recovery evidence and
  configuration/source fingerprints. Repeated requests are not independent quality cases.

No real workload or business SLO has been supplied for this new stage. The earlier
100 scripted jobs and short inference trial do not satisfy this gate.

## 3. Generalization — separate frozen evaluation

After selecting a candidate using development data, freeze its source/model/prompt,
retrieval corpus, inference settings, dataset hashes and analysis protocol. Evaluate
once, without supplying answer SQL or expected rows to the runtime. Test-derived
changes require a new untouched holdout; the old set becomes development data.

Separate the following strata rather than pooling away weak ones:

- New data instances of familiar schemas/rules: a control, not unseen-task evidence.
- Domain shift with independently authored questions and business definitions.
- Unseen schema structure, including changed relationships/cardinalities and column
  layouts. Identifier renaming alone is only an identifier-robustness control.
- Unseen combinations of business rules: eligibility, refunds, exclusions, date
  boundaries, NULLs, no activity and ties. Withhold combinations from development.

Use independent answer adjudication plus counterexample fixtures (multiple children,
identical amounts, nulls, nonqualifying children and ties). Synthetic source SQL alone
is insufficient for a claim of human business correctness. Report per-stratum and
worst-stratum correctness, abstention/review rate, tokens per verified success and
paired uncertainty clustered by genuinely independent schema/domain units.

The existing 48-case commerce run and the inspected 100-case fine-tuning test set are
already seen. Neither can now be relabelled as blind. No blind-holdout result is claimed.
