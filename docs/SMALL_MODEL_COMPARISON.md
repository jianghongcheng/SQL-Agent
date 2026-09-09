# Small-model NL2SQL QLoRA comparison

A new 0.5B training run, compared with its own baseline and the saved 1.5B experiment.
Same frozen 512 train / 64 dev / 100 test split; one epoch, rank 16, seed 42.
The dev split was not used for selection. No test-driven hyperparameter search.

| Model | Before | After | Fixed | Regressed |
| --- | ---: | ---: | ---: | ---: |
| Qwen2.5-Coder-0.5B-Instruct (new) | 44/100 | 51/100 | 15 | 8 |
| Qwen2.5-Coder-1.5B-Instruct (historical) | 52/100 | 59/100 | 9 | 2 |

0.5B domain-cluster 95% difference interval: **-1.19 to 15.13 percentage points**.
Duplicated-row stress: 33/89 → 41/89; 11 unscorable fixtures remain recorded.

Scores apply the same JSON-fence normalization and execute against source-labelled fixtures.
This is not deployed Agent accuracy or independently verified business correctness.

## Tokens and runtime

| 0.5B condition | Input tokens | Output tokens | Total tokens | Generation seconds |
| --- | ---: | ---: | ---: | ---: |
| baseline | 9,197 | 3,724 | 12,921 | 66.13 |
| adapter | 9,197 | 2,849 | 12,046 | 63.67 |

Training: 512 samples, 121.77 seconds, 65,634 processed tokens, 17,824 supervised tokens; peak allocated GPU memory 1.26 GiB.
Inference uses batches of four; generation seconds exclude loading and SQL scoring. This is not HTTP request latency.
Token counts exclude input padding and output padding after EOS. All outputs, including incorrect ones, count.
Local token workload is not an API invoice. Historical timing is not a controlled cross-model speed comparison.

## Changed-case inspection

- Case 76091 restores the omitted manufacturer predicate; case 49293 restores the USA filter and expected projection.
- Case 31613 regresses by dropping the ceramic-artifact predicate; case 1039 invents Rural/Non-Rural values in a state column.
- Case 65292 is scored as fixed on its fixture but still omits the Shelters/Hospitals predicate. Case 95414 omits the non-null initiative predicate. These are not demonstrated semantic fixes.
- Case 22244 changes column order to match the reference. Execution equality therefore includes output-contract alignment, not only reasoning gains.
All 23 changed cases are retained in `qwen-0.5b/changed-cases.json`. Duplication stress cannot expose every missing filter.

## Evidence and limits

The duplicated-row stress report, paired statistics, raw responses, loss trace, model revision and adapter hashes are retained in `outputs/validation/small-model-comparison/`.
A single seed and synthetic source fixtures limit generalization. The adapter is not automatically promoted.

Model source: [official Qwen repository](https://huggingface.co/Qwen/Qwen2.5-Coder-0.5B-Instruct).

## Reproduce

Use the recorded model revision and `environment.txt`. Choose a fresh output directory; training refuses to overwrite an existing run.

```bash
PYTHONPATH=src python scripts/train_sql_lora.py --model runtime/models/qwen-coder-0.5b --dataset outputs/validation/strong-signal/qlora-dataset.json --output /tmp/sql-agent-small-reproduction
PYTHONPATH=src python scripts/score_sql_lora.py --dataset outputs/validation/strong-signal/qlora-dataset.json --run /tmp/sql-agent-small-reproduction
PYTHONPATH=src python scripts/analyze_sql_lora.py --dataset outputs/validation/strong-signal/qlora-dataset.json --run /tmp/sql-agent-small-reproduction --output /tmp/sql-agent-small-reproduction/paired.json
PYTHONPATH=src python scripts/analyze_sql_fixture_stress.py --dataset outputs/validation/strong-signal/qlora-dataset.json --run /tmp/sql-agent-small-reproduction --output /tmp/sql-agent-small-reproduction/fixture-stress.json
```
