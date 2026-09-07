# Complete three-database BIRD evaluation

This run evaluates all 110 Mini-Dev questions in the downloaded California
schools (30), financial (32) and student club (48) databases. It is not the full
500-question Mini-Dev benchmark. The difficulty mix is 32 simple, 61 moderate
and 17 challenging questions. No cases are excluded based on model behavior.

```bash
python scripts/validate_bird_external.py --all-domains \
  --output outputs/validation/bird-110-new
```

Only the runner's case selection and reporting were extended from the earlier
30-question pilot. Production source hashes match that run; the benchmark
planner, model (`qwen3:8b`), three-attempt budget and scoring rules are unchanged.
All 110 questions are executed afresh. The single-attempt comparison replays
each bounded run's first live response; it is not an independently prompted
single-shot baseline.

Gold SQL remains exclusively in the offline reference grader. Runtime gold
verification and catalog fallback are disabled. The benchmark adapter uses
dynamic output columns and production SQL authorization/VM/row limits. Official
question evidence and column descriptions are provided. See
[the combined protocol](COMBINED_EXPERIMENT.md) for grading and adapter details.

The report separates the previous 30 pilot questions from the additional 80.
“Additional” means not previously run by this project; it does not assert absence
from model pretraining or independence from the already seen database domains.
The metrics measure agreement with reference query results, not human adjudication
of ambiguous questions. Set agreement ignores duplicates and row order; a separate
multiset metric preserves duplicate differences. Both retain column order.

Artifacts are under `outputs/validation/bird_110_v1/`: the pre-inference manifest,
all per-question records, raw prompts/responses and final summary. All errors,
unsupported queries and timeouts remain visible and are not silently excluded.

## Completed results

All **110/110** selected IDs produced records, with no duplicates, missing cases
or reference execution errors. Production source hashes were unchanged and
matched the earlier combined run. There were 128 actual model calls; the
single-attempt arm reused first responses rather than making 110 extra calls.

| Database | Questions | Single-attempt set match | Three-attempt set match |
|---|---:|---:|---:|
| California schools | 30 | 5 | 5 |
| Financial | 32 | 7 | 7 |
| Student club | 48 | 21 | 23 |
| Total | 110 | **33 (30.0%)** | **35 (31.8%)** |

The stricter multiset scores were 31/110 and 33/110 respectively. By difficulty,
single → bounded matches were simple 18→19 of 32; moderate 14→15 of 61;
challenging 1→1 of 17.

| Cohort | Questions | Single match | Bounded match |
|---|---:|---:|---:|
| Prior pilot, rerun afresh | 30 | 10 | 10 |
| Additional cases | 80 | 23 | 25 |

Cases **1390** and **1356** recovered to reference-matching answers on retry.
However, accepted reference disagreements increased from **53 to 58**; cases
28, 40, 62, 79 and 1389 newly became accepted disagreements after retries.
The bounded run accepted 93 outputs in total: 35 matched and 58 disagreed;
17 tasks stopped. This is agreement with the dataset reference, not independent
human adjudication of every question.

The result provides a small observed retry gain, not evidence of broad semantic
reliability. Even on these three domains, most generated answers do not match
the reference. The fixed business-catalog safety track and the general blind
SQL track must remain separate. No production-level general SQL accuracy or
full 500-question benchmark result is claimed.

`summary.json` contains both cohorts and database counts; `coverage_audit.json`
checks all IDs and records outcome reasons/difficulty; `run.log` preserves the
complete console output. No failed cases were removed from the denominator.
