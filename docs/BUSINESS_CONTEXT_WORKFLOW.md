# Business context, source health and review workflow

## Implemented

The registered SQL task can now include:

- `definitions`: metric ID, matching terms, definition text, source, version and optional `required` flag. Retrieval is task-scoped literal term matching plus required entries. It is not vector RAG, multi-hop retrieval or cross-task search.
- `quality_checks`: server-owned read-only scalar query, check kind, maximum, severity and policy rationale. `violation_count` measures violating rows; `freshness` measures hours since an explicitly timezone-qualified timestamp. Blocking failure or unknown prevents model calls. Warning checks remain visible but do not block.
- A context hash pinned at API/CLI submission. A changed definition or quality policy causes the worker to reject the old context rather than silently substitute new rules. Replay retains the pinned hash. Legacy direct repository callers without the hash use current configuration.

Checks and SQL analysis use the same SQLite connection/read snapshot. Queries remain subject to the existing authorizer, function allowlist, VM budget and row limit. Checks do not write source data. Missing checks are shown as `not_configured`, not a successful quality evaluation. A future/invalid/missing timestamp is unknown, not fresh. A configured 24-hour budget is a demo policy, not a universal standard.

The pipeline saves matched definitions with sources/version, quality observations and rationale, query trajectory, candidate result and release decision. The model receives selected definitions but no reference answer SQL. The source-health SQL and its errors are not injected as prior query/repair evidence.

The homepage now displays registered tasks, metric definitions, source health, candidate result, proposed SQL and review actions. An admin can record an approval/rejection and notes through the existing authenticated review API; viewers cannot review. It also loads existing jobs and their audit events. Corrected requests create new jobs, preserving original results. The review action records a human decision; it does not rewrite the original output or upgrade automatic verification.

Candidate tables currently show at most 100 rows; full evidence remains in the JSON panel. No browser visual inspection was performed; JavaScript syntax and the API/worker/review behavior were checked. No full Temporal engine, vector database or new multi-agent runtime was added.

## How to run the demonstration

From the repository root with an installed project and local Ollama `qwen3:8b`:

```bash
PYTHONPATH=src:. python scripts/demo_business_context.py --output runtime/business-context-demo
```

This creates six small synthetic databases, task configuration files and durable job histories. The metric is approved-refund net revenue: 100 + 80 - 10 = 170; pending refunds do not reduce revenue. It runs three healthy trials plus stale ingestion, missing amount and missing ingestion timestamp scenarios. The generated healthy task config can be used with the existing API/worker:

```bash
export RADMEASURE_SQL_TASKS="$PWD/runtime/business-context-demo/healthy_1_tasks.json"
export RADMEASURE_PLANNER_PROVIDER=ollama
export RADMEASURE_PLANNER_BASE_URL=http://127.0.0.1:11434
export RADMEASURE_PLANNER_MODEL=qwen3:8b
```

Configure the API keys and shared job repository using the existing local deployment instructions; start API and worker with the same environment. The generated freshness timestamp will eventually become stale by design; regenerate a fresh demo rather than disabling the check. Configuration source SQL is trusted application policy, not client input.

## Observed validation, including failures

Full regression: **128 passed**. New tests cover task-scoped retrieval, definition-version hashing, blocked/unknown freshness, unauthorized SQL rejection, skipped model calls on blocked inputs, API/worker evidence persistence, viewer review denial and admin review audit.

`outputs/validation/business_context_v1/` contains the first real-model run. All three healthy trials produced the correct candidate but the independent checker dropped orders without approved refunds. Three source-health failure scenarios blocked before inference. Overall predefined success: **3/6**, not 6/6.

`outputs/validation/business_context_v2/` retains a second run after explicitly adding the missing no-refund business rule. The primary model again produced 170 in all three healthy trials, but the checker incorrectly calculated a refund total. These trials still stopped for review. The stale, missing-amount and missing-timestamp scenarios again blocked with **zero model calls**. Overall predefined success remains **3/6**. This is not evidence of improved general semantic accuracy. All generic outputs still require review.

The UI and evidence path make these failures inspectable, but they do not solve the known independent-checker weakness. No human reviewed these live runs; human-review behavior was exercised by automated API integration tests only. No new BIRD score is claimed.

## Design sources and differences

We inspected public code and implemented project-specific equivalents; no external source code was copied into the runtime.

- [E-Commerce tools](https://github.com/gayathrisuresh182/-E-COMMERCE-STREAMING-ANALYTICS-PLATFORM/blob/65794b53ad1b81b51f2948d4ff2f917e43d46d96/api/agent/tools.py): separate schema/freshness/business tools inspired source-health evidence. Our checks use the existing bounded SQLite executor and explicit policy rationale.
- [Legal RAG term resolver](https://github.com/gayathrisuresh182/Legal-Document-RAG-Pipeline/blob/71adce515a0893c390f8120d8d51c4ae2895f3a7/backend/app/rag/nodes/term_resolver.py): scoped definition retrieval inspired task-scoped metric definitions. Our first implementation uses deterministic matching; it does not claim their multi-hop capabilities.
- [Solon workflow](https://github.com/gayathrisuresh182/solon-underwriting-platform/blob/25efbfad23badfe359ba26e120cb5afddfeb95ff/ai/workflows/submission_workflow.py) and [field review component](https://github.com/gayathrisuresh182/solon-underwriting-platform/blob/25efbfad23badfe359ba26e120cb5afddfeb95ff/web/src/components/FieldReviewTable.tsx): explicit stages, provenance and human review informed our review experience. We reuse the existing durable job repository and review API rather than claiming Temporal activity-level recovery.
