# Evaluation boundaries

Three distinct kinds of evidence must remain separate:

1. **Unit/integration tests:** validate execution behavior, API contracts,
   authorization, worker fencing and recovery boundaries. Scripted planners
   establish control flow, not language-model capability.
2. **Historical frozen SQL artifacts:** v1/v2/v3 compare fixed proposals under
   policy/verifier configurations. They are retained for reproducibility.
3. **New adaptive-loop evaluation:** not yet established by a real-model
   controlled comparison. Do not reuse the old metrics as new-loop results.

The stored v3 table is:

| Class | LLM only | Policy + verifier |
|---|---:|---:|
| KEEP | 36/36 | 36/36 |
| REPAIR | 30/36 | 30/36 |
| STOP | 7/36 | 32/36 |
| Total | 73/108 | 98/108 |

The added successes come from policy rejection. The historical verifier gets
reference rows; the new runtime verifier never does. Unsafe action counts in the
ungated benchmark are admission bookkeeping, not destructive SQL execution.
A query returning departments under a `name` column can satisfy the structural
contract while answering the wrong question.

For the next capability experiment, author task contracts independently of model
outputs, freeze tasks, and compare fixed workflow, one attempt, and bounded
repair using the same model. Keep reference answers outside planner/runtime.
Measure task success, false acceptance, unsafe admission, unnecessary stopping,
model/tool calls and latency. No user adoption or deployment outcomes are implied.
