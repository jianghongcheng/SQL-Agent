# General SQL correctness and release controls

A reproducible service bug allowed `SELECT department AS name FROM employees`
to complete a request for employee names. The structural contract matched, but
the requested meaning did not. `tests/test_semantic_release.py` first reproduced
this as a failing pipeline test.

## Implemented behavior

- A service result is automatically `completed` only when the candidate passes
  the registered business verifier. That verifier is an application-owned query
  definition, not universal proof or benchmark gold supplied to a model.
- General SQL results go to `needs_review`. `output` is null; a structurally valid
  candidate is retained separately in `candidate_output`. `release.approved` is
  false, with an explicit reason. Existing authenticated review endpoints persist
  a human decision; they do not silently promote model agreement into proof.
- Model-backed general SQL tasks run an independent query check automatically.
  The second planner sees the question and schema, not the primary SQL, rows,
  errors or reference answer. Benchmark column descriptions are also provided
  when available. This is independent generation context, not an independent
  model: both calls currently use the configured model and can share errors.
- Both queries execute in one read snapshot with the production authorizer,
  function allowlist, VM budget and row limit. Comparison preserves duplicates,
  row order and column count, ignoring aliases. Unrequested row-order differences
  can conservatively reject equivalent answers.
- One independent query is generated per session. Disagreement triggers bounded
  primary repair without exposing the independent SQL to the repairing model.
  An unavailable, malformed, unsafe or oversized check stops the loop. There are
  at most three primary proposals plus one independent model proposal, with
  additional bounded database executions for checks.
- Agreement is labeled `independent_query_agreement_not_semantic_proof`. Even
  agreement remains review-required in the general service. Tests explicitly
  cover two agreeing but wrong queries.

The scripted employee demo now has an explicit registered query and therefore
continues to complete after verification. Its registered question cannot be
changed to ask a different business question. Generic tasks without trusted
verification now have intentionally stricter release behavior.

## Validation design

```bash
python -m pytest -q
python scripts/validate_semantic_gate.py \
  --output outputs/validation/bird_semantic_gate_v1
```

The full 500-case screening study freezes the earlier bounded-run candidates.
Previously stopped cases remain stopped. Each previously accepted candidate is
re-executed and its output hash must match the baseline; a new live independent
query checks it. Gold labels are reused only for offline scoring. Five baseline
reference execution failures remain unknown and receive no correctness credit.

This is a paired screening study on a previously evaluated dataset. It is not
fresh end-to-end generation accuracy, a test of live semantic-repair gains, or
an unseen generalization estimate. Correctness, error filtering, lost correct
answers and coverage must be reported together. Zero automatic releases in the
general service is a conservative policy, not 100% model accuracy.

## Operational boundaries

General natural-language SQL cannot be declared semantically correct merely
because it executes or another model agrees. Ambiguous business definitions,
correlated model errors and incomplete data remain unresolved. This change fixes
an unsafe success label and adds checkable evidence and a repair route; it does
not establish production-proven general SQL accuracy, a production SLO or real
user adoption. Existing resource and tenant-isolation limitations still apply.

## Completed paired screening results

All **500/500** unique IDs were processed. Baseline per-case files are unchanged;
358 live independent model calls checked previously accepted candidates. The
other 142 previously stopped tasks stayed stopped.

| Metric | Original bounded candidates | Independent agreement subset |
|---|---:|---:|
| Candidate count | 358 | 167 |
| Reference matches | 140 | 94 |
| Reference disagreements | 217 | 72 |
| Unknown reference result | 1 | 1 |
| Precision on graded candidates | 39.2% | 56.6% |
| Correct answers retained out of 500 | 28.0% | 18.8% |

The check screens out **145/217 (66.8%)** reference-disagreeing candidates, but
also loses **46/140 (32.9%)** previously correct answers. It retains 67.1% of
correct answers. There are 129 disagreements and 62 unavailable checks. Agreement
coverage is 167/500 (33.4%); it is not a success rate. Five original reference
limit errors remain in the dataset, including one in the agreement subset.

**72 wrong candidates still agree with the independent query.** Therefore the
screen is insufficient for autonomous general SQL release. It improves selected
candidate precision at a substantial coverage cost; it does not improve overall
answer accuracy. The service's zero unverified automatic releases is an explicit
review policy, not a claim of zero model errors.

Artifacts: `outputs/validation/bird_semantic_gate_v1/` contains the manifest,
500 per-case files, summary, coverage audit, console log and regression logs.
The manifest records source hashes during this frozen run. After the
application-output-contract fix below, all 358 benchmark prompts were reconstructed
and verified byte-identical in `post_contract_fix_audit.json`; benchmark mode
explicitly omits output contracts because BIRD supplies no application schema.

## Live semantic repair and the output-contract bug

The first live recovery experiment exposed an avoidable verifier error: the
primary model repaired all six injected queries, but the check model added IDs
or unrelated columns in five cases, so only 1/6 reached agreement. The independent
planner had not received the application-owned output schema. A failing test
reproduced this missing input.

The service checker now receives the required output columns and an instruction
not to add sorting keys or explanatory columns. These columns come from the
application contract, never from a benchmark reference. On the unchanged six
injected cases, the final run recovered **6/6**, using **6 live check calls and
6 live repair calls**. Each case began with an executable wrong filter or an
incorrect source field hidden behind the right alias. The controller detected
disagreement, replanned without seeing the check SQL, and matched the offline
reference after repair. The result remains review-required in production.

This is fault injection across three small synthetic domains, not six natural
model failures or a claim of 100% general accuracy. The failed first run is
preserved under `outputs/validation/live_semantic_repair_v1/`; the corrected run
is `outputs/validation/live_semantic_repair_v2/`. Reproduce with:

```bash
python scripts/validate_live_semantic_repair.py \
  --output outputs/validation/live-semantic-new
```

Final full regression suite: **89 passed**. Coverage includes real authenticated
API/worker persistence, correlated wrong agreement, independent-context isolation,
unsafe/unavailable checks, duplicate/order/column mismatches, same-snapshot reads,
semantic repair, trusted business verification and worker recovery. Existing
FastAPI/httpx deprecation warning remains unrelated to correctness.

`routing` and `execution_record` retain the low-level controller decision for
audit; consumers must use job status and `release.approved` for publication.

