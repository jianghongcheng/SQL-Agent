# Full BIRD Mini-Dev coverage

This evaluation runs all 500 official Mini-Dev SQLite questions across eleven
canonical databases. The pinned question inventory contains 148 simple, 250
moderate and 102 challenging questions. Medical databases are included for
benchmark completeness; the application remains a general SQL Data Agent.

```bash
python scripts/fetch_bird_databases.py --full \
  --output data/local/bird_mini_dev/databases_full
python scripts/validate_bird_external.py --full \
  --databases data/local/bird_mini_dev/databases_full \
  --output outputs/validation/bird_500_v1
```

The model remains local `qwen3:8b`; the benchmark prompt, three-attempt bound,
production executor, function allowlist, VM limit and 10,000-row cap are unchanged
from the 110-question run. Every question is executed afresh. The single-attempt
comparison replays the first live response of the bounded run. Reference SQL
is used only by the offline grader; runtime gold verification and catalog fallback
are disabled. Official evidence and column descriptions are model inputs.

Scores report set-of-rows agreement and stricter multiset agreement. Neither
checks row order; both retain column order. These measure agreement with the
reference SQL, without human adjudication. All failures remain in the denominator;
reference execution errors are identified separately. Full question coverage is
not an official leaderboard submission under unrestricted execution settings.

The previous 110 questions and newly evaluated 390 are reported separately.
“New” refers to this project's evaluation history, not model pretraining.
Source: [official Mini-Dev repository](https://github.com/bird-bench/mini_dev),
[question inventory](https://huggingface.co/datasets/birdsql/bird_mini_dev),
revision `f65faf4ae3b638c1fa6df1d3370c8d92c8366301`, CC-BY-SA-4.0.

## Completed results

All **500/500** unique question IDs have records, with zero missing or duplicate
IDs. There were **598 live model calls**. Production source hashes remained
unchanged and match the earlier 110-question run; the recorded model identity
also matches. The original 110-question cohort reproduces its earlier scores.

| Cohort | Questions | Single-attempt set match | Up to three attempts |
|---|---:|---:|---:|
| Previous questions, executed afresh | 110 | 33 (30.0%) | 35 (31.8%) |
| Newly evaluated questions | 390 | 102 (26.2%) | 105 (26.9%) |
| Full Mini-Dev coverage | 500 | **135 (27.0%)** | **140 (28.0%)** |

Multiset agreement is **124/500 (24.8%) → 128/500 (25.6%)**. Retry recovery
occurs on IDs **1098, 1390, 1356, 1162 and 1175**: five additional set matches,
including three in the newly evaluated domains. This is a one-percentage-point
observed gain on this run, not a demonstrated general improvement across models
or independent runs.

Accepted outputs that disagree with the reference increase from **197 to 217**.
The bounded run accepts 358 outputs: 140 match, 217 disagree and one cannot be
graded because its reference execution failed. The remaining 142 tasks stop.
Thus execution acceptance is not evidence of semantic correctness. The result
does not establish production-grade general SQL accuracy.

### Reference execution limitations

Five cases could not be graded under the frozen reference limits: **340, 346,
397** exceed 10,000 reference rows; **518 and 701** exceed the 30-second reference
execution budget. They remain in the 500-case denominator with no correctness
credit. Their semantic correctness is unknown, not established as wrong. Among
the 495 graded cases, set agreement is 135/495 (27.3%) and 140/495 (28.3%). The
primary report retains all 500 to avoid silently excluding failures. All five
are in the new 390-question cohort.

### Results by database

| Database | Questions | Single | Bounded |
|---|---:|---:|---:|

| california_schools | 30 | 5 | 5 |
| card_games | 52 | 6 | 6 |
| codebase_community | 49 | 10 | 10 |
| debit_card_specializing | 30 | 6 | 6 |
| european_football_2 | 51 | 7 | 8 |
| financial | 32 | 7 | 7 |
| formula_1 | 66 | 14 | 14 |
| student_club | 48 | 21 | 23 |
| superhero | 52 | 32 | 32 |
| thrombosis_prediction | 50 | 13 | 15 |
| toxicology | 40 | 14 | 14 |

### Results by difficulty

| Difficulty | Questions | Single | Bounded |
|---|---:|---:|---:|
| challenging | 102 | 17 | 17 |
| moderate | 250 | 57 | 61 |
| simple | 148 | 61 | 62 |

Artifacts: `outputs/validation/bird_500_v1/manifest.json` records selection,
model and source identities before inference; each numeric JSON file contains
model calls, SQL and retry traces; `summary.json` contains scores and cohorts;
`coverage_audit.json` checks completeness, source identity and reference errors;
`run.log` contains the complete run output. Local canonical data and its SHA256
manifest are under `data/local/bird_mini_dev/databases_full/`.

The next reliability gap is detecting executable but semantically incorrect
SQL. The previously tested registered business contracts are a separate track;
their verified results must not be substituted for these blind benchmark scores.
