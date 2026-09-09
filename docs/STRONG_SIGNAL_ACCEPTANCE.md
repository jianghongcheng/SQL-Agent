# Strong Signal acceptance

Completed measurements: [local acceptance results](STRONG_SIGNAL_RESULTS.md).

Scope: the previously requested **local SQL-Agent demonstration**, registered
databases, one trusted workspace. This record is not a claim of public production
adoption, a multi-tenant security assessment, or an uptime SLO. General answers
continue to require human review. Engineering acceptance and model promotion
are different decisions.

## Acceptance criteria

| Signal | Required evidence | What does not count |
| --- | --- | --- |
| Custom RAG, reranking and evaluation | Token/paragraph boundaries tested; database/table filtering before indexing; local cross-encoder; complete BM25/hybrid/reranked comparisons; retrieval and SQL metrics separate | More modules without tests; treating retrieval recall as SQL correctness |
| Agent roles, tools, error handling, cost | Planner and independently prompted Verifier in LangGraph; bounded SQL repair; durable clarification/approval; real tool execution; input/output token accounting on success, failure and retry | Model agreement as proof; counting missing token usage as zero |
| Domain adaptation and before/after evaluation | Saved NL2SQL QLoRA adapter and provenance; domain-disjoint data; identical inference/scoring; fixes, regressions and source-label audit | Formatting-only gains called semantic accuracy; selective removal of failures |
| Deployment, monitoring, latency and cost | Isolated Docker API/workers and PostgreSQL; health/auth/metrics; queue/restart/approval checks; measured load and latency; token cost analysis | Scripted request latency labelled LLM latency; local traffic labelled production SLO |
| Multiple approaches and statistics | Frozen case IDs and independent oracle; complete planned records; matching image/source fingerprint; paired comparisons with family/domain resampling; raw failures retained | Repeated data variants counted as independent questions; promoting on an interval including zero |

An experiment with a negative result can complete its evaluation protocol. It
does not pass a claim that the candidate improves accuracy, and it does not
authorize replacing the deployed model or publishing an answer automatically.

## Token accounting

`telemetry.token_cost` contains input/output/total tokens when known, and
`observed_total_tokens` plus `complete: false` when some consumption is unknown.
Each completed, waiting or failed worker attempt preserves an `attempt_telemetry`
snapshot in the durable event history. The displayed total adds disjoint attempts,
including clarification resumes, once. A crash before telemetry persistence is
reported through `unobserved_job_attempts`; it cannot be reconstructed as zero.

The dashboard displays both complete and incomplete costs, including failed
jobs. A clarification form resumes the persisted request instead of making a
new unrelated request. Model dollar rates are not assumed.

For evaluation, `tokens_per_correct_result` divides **all observed workload
tokens** by the number of correct candidates. No correct candidates yields an
undefined ratio. Any missing usage makes the exact ratio undefined.

## Experiments

Local raw artifacts: `outputs/validation/strong-signal/` (excluded from Git).
The final machine-readable audit and results table are generated after all
required runs finish; an absent/failed result must not be described as passed.

- Retrieval: two chunking strategies, each with BM25, hybrid, hybrid+reranker;
  16 known synthetic questions in eight document families, first-pass and warm
  records separated. No claim of unseen-question generalization.
- Live Agent: three retrieval configurations on 48 instances in six known
  commerce families. Fresh seed 290929, eight instances/family, no gold file
  mounted into API/workers. Model errors count in the denominator. This is a
  paired development benchmark, not 48 independent question templates.
- QLoRA: 512 train, 64 development, 100 test records from a revision-pinned
  source-labelled corpus. Re-score the immutable base/adapted generations with
  the same JSON-fence handling. This is a replay, not a newly trained model.
- Fixture stress: duplicate source INSERT rows and compare both saved SQLs with
  source SQL on the modified fixture. Primary-key/other invalid duplicates are
  unscorable. This post-hoc check tests accidental agreement, not human meaning.
- Deployment: 100 scripted requests at concurrency eight through real HTTP,
  queue and Worker; PostgreSQL/API/Worker restart and permission checks. The
  separate gateway run uses only a disposable SQLite business database.
- Latency optimization: a rechecked historical comparison of ten matched cases
  in the same old image shows median 37.31→5.89 seconds and p95 47.11→6.90
  seconds after changing the inference serving profile. The baseline trial was
  interrupted; these matched records are a diagnostic observation, not a full
  accuracy comparison or a single-factor causal experiment. The current live
  benchmark uses the isolated two-model residency profile. Sequential retrieval
  conditions share host resources; their latency differences are descriptive.

## Original QLoRA failure analysis

The comparable parser gives **52/100 before, 59/100 after**, nine fixes and two
regressions. Domain-cluster 95% interval for the difference: **0 to +14.47
percentage points**. Strict unfenced JSON improves, but both conditions are
scored with the same fence removal, so formatting is not counted as the
semantic gain.

Manual inspection of changed SQL exposes important limits:

- Case 54071 fixes an omitted `Health = 'Healthy'` condition; case 35904 restores
  grouping by event type. These are interpretable SQL changes.
- Case 13729 matches `SELECT number_of_turbines` with `SUM(number_of_turbines)`
  only while the selected fixture contains one row.
- Case 2384 uses `SUM(impact)` where source SQL uses `AVG(impact)`; one row per
  month masks the mismatch. The wording of the source question is itself not
  an independently audited business specification.
- Case 99103 changes a literal's capitalization but still does not reproduce
  the source predicate. Its match is fixture-dependent.
- Regressions 66045 and 97989 invent or misuse schema/aggregation details.

On the **89 fixtures** that permit row duplication, joint original+stress
agreement is **43/89 before, 48/89 after**; seven fixes, two regressions, and
the domain-cluster interval is **−2.04 to +13.75 points**. Eleven fixtures are
unscorable under this transformation. The adapter is **not promoted**.

## Reproduction

Use Python 3.12 for the tested acceptance environment. `requirements-acceptance.lock`
records its exact dependencies; GPU training and CPU Docker retrieval have their
own recorded environments. Google Chrome is required for browser tests.

```bash
python3.12 -m venv .venv
.venv/bin/pip install -r requirements-acceptance.lock
.venv/bin/pip install --no-deps -e .
PYTHONPATH=src .venv/bin/python scripts/validate_postgres_trial.py --output /tmp/sql-agent-regression-new
.venv/bin/python -m compileall -q src
git diff --check
```

The PostgreSQL runner creates and removes only its disposable container. Live
model commands and local model requirements are in [Evaluation](EVALUATION.md).
Keep credentials, compose secrets, databases and raw outputs local. Report
source/image hashes and retain failures when publishing a sanitized summary.
