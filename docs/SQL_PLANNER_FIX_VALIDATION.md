# SQL planner false-refusal fix

Validated with fresh local Ollama Qwen3-8B calls after the initial 21-case run.
The model, source fixtures and SQL authorization/verification rules were kept
unchanged for the known-case comparison. No scripted SQL answers or gold rows
were inserted into model prompts.

## Change

`ContractSQLPlanner.PROMPT_VERSION = sql_contract_v2` clarifies three distinctions:

- Database schema describes source columns; contract columns describe required
  output names. Aliases and derived expressions need not be source columns.
- SQL aggregates and GROUP BY are supported, subject to the existing function
  allowlist and output contract.
- Initial SQL is a candidate to correct, not authoritative evidence or a
  requirement to preserve a nonexistent column.

STOP remains a terminal decision for unsupported/write goals or insufficient
source information. The fix does not blindly retry STOP or relax SQL policy.
The initial prompt's ambiguity was a working diagnosis; correcting it removed
the observed refusals. No claim is made about the model's hidden reasoning.

## Results

| Evaluation | Before | After |
|---|---:|---:|
| Known legitimate tasks | 9/15 | 15/15 |
| Known aggregate + alias failures | 0/6 | 6/6 |
| Known restricted/unsupported requests stopped | 6/6 | 6/6 |
| Known mixed suite | 15/21 | 21/21 |
| New legitimate tasks | Not run before fix | 11/11 |
| New restricted/unavailable-data requests stopped | Not run before fix | 4/4 |

The 15 new cases were saved before their first model execution in
`data/benchmarks/sql_contract_transfer_v1.json`. They use two new schemas and
include joins, grouped sums, HAVING, computed output, null replacement, empty
aggregation, unavailable fields and a hostile comment in an initial query.
The prompt was not revised after inspecting these new results.

In `shipping:unsafe_update`, the model proposed an UPDATE. The runtime rejected
it with `read_only_policy_violation` before execution. The other three new
restricted/unavailable-data cases were stopped by the model. Thus 4/4 correct
system behavior must not be described as 4/4 model refusals.

All 36 post-fix cases used one model call each. Paired first-proposal replay and
bounded execution scored identically. This establishes a fix for these false
refusals, **not a measured benefit from multi-step retries**. The datasets are
small synthetic functionality checks, not a production accuracy estimate.

## Reproduction and evidence

```bash
python scripts/validate_live_sql_agent.py --model qwen3:8b \
  --output outputs/validation/live_sql_qwen3_8b_prompt_v2_known
python scripts/validate_live_sql_agent.py --model qwen3:8b \
  --suite data/benchmarks/sql_contract_transfer_v1.json \
  --output outputs/validation/live_sql_qwen3_8b_prompt_v2_transfer
python -m pytest -q
```

Use a new output directory when reproducing to preserve the original artifacts.
Each run saves raw prompts/completions, token/timing metadata, execution traces,
case definitions and independent grading. The transfer manifest includes the
prompt version, model digest and planner-source hash. The earlier known-case run
began before those two provenance fields were added to the harness; its saved
prompts still identify the actual prompt used.

Regression result: **43 tests passed**. The harness now treats generation errors
as failures rather than successful safety refusals. Reference-query tests check
that all new legitimate fixtures can satisfy their predeclared runtime contracts;
those reference executions are not counted as model results.
