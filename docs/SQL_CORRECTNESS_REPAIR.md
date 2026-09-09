# SQL correctness development repair

Previously inspected development set; not blind generalization or production SLO.

The generator now explicitly plans population, output grain, parent preservation, separate one-to-many aggregates, anti-existence and tie handling.
Models, knowledge, frozen cases and retrieval mode remain matched. Historical versus current timing is descriptive on a shared host.

| Family | Before | After |
| --- | ---: | ---: |
| customer_net | 0/8 | 6/8 |
| inactive_customers | 0/8 | 8/8 |
| monthly_report | 5/8 | 5/8 |
| paid_revenue | 8/8 | 8/8 |
| qualifying_orders | 8/8 | 8/8 |
| top_customers | 0/8 | 0/8 |

| Metric | Before | After |
| --- | ---: | ---: |
| Correct | 21 | 35 |
| Unavailable jobs | 0 | 0 |
| Total tokens | 139207 | 148734 |
| Tokens / externally verified correct result | 6628.9047619047615 | 4249.542857142857 |
| Client p95 seconds | 5.854504919843748 | 5.909396583912894 |

Fixed 15; regressed 1. Family-cluster 95% difference interval: 0.00 to 62.50 percentage points.
Retain development change under the predeclared rule: True. Human review remains required.

## Remaining errors

Wrong answers with verifier agreement: commerce_0:top_customers, commerce_2:top_customers. Agreement is not a correctness gate.
Regressed cases: commerce_4:monthly_report. Family totals can hide offsetting fixes and regressions.
These inspected cases are development evidence. No further prompt selection was performed during this comparison.

All changed SQLs and raw record hashes are retained in `outputs/validation/correctness-v1/comparison.json`.
This experiment does not pass the production or generalization gates. See [remaining gates](NEXT_QUALITY_GATES.md).
