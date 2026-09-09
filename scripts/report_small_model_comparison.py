"""Summarize one frozen small-model training run and its historical reference."""
import argparse
import hashlib
import json
from pathlib import Path


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, required=True)
    p.add_argument('--reference', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    run = args.root / 'qwen-0.5b'
    read = lambda path: json.loads(path.read_text())
    paired = read(run / 'paired.json')
    old = read(args.reference / 'paired.json')
    stress = read(run / 'fixture-stress.json')
    manifest = read(run / 'manifest.json')
    if paired['dataset_sha256'] != old['dataset_sha256']:
        raise ValueError('Historical comparison dataset differs')
    usage = {}
    for name in ('baseline', 'adapter'):
        records = read(run / (name + '.json'))
        if len(records) != 100 or len({r['id'] for r in records}) != 100:
            raise ValueError('Incomplete evaluation')
        if any(r['total_tokens'] != r['input_tokens'] + r['output_tokens'] for r in records):
            raise ValueError('Invalid token ledger')
        usage[name] = {k: sum(r[k] for r in records) for k in ('input_tokens', 'output_tokens', 'total_tokens')}
    weights = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (run/'adapter').glob('*.safetensors')}
    if not weights:
        raise ValueError('Missing trained adapter')
    report = {'manifest':manifest, 'current':paired, 'historical':old,
              'tokens':usage, 'fixture_stress':stress, 'adapter_sha256':weights}
    (args.root / 'comparison.json').write_text(json.dumps(report, indent=2))
    lines = ['# Small-model NL2SQL QLoRA comparison', '',
             'A new 0.5B training run, compared with its own baseline and the saved 1.5B experiment.',
             'Same frozen 512 train / 64 dev / 100 test split; one epoch, rank 16, seed 42.',
             'The dev split was not used for selection. No test-driven hyperparameter search.', '',
             '| Model | Before | After | Fixed | Regressed |', '| --- | ---: | ---: | ---: | ---: |']
    for label, data in [('Qwen2.5-Coder-0.5B-Instruct (new)', paired), ('Qwen2.5-Coder-1.5B-Instruct (historical)', old)]:
        s = data['summary']
        lines.append(f"| {label} | {s['baseline']['correct']}/100 | {s['adapter']['correct']}/100 | {s['fixed']} | {s['regressed']} |")
    ci = paired['paired']['cluster_bootstrap95']
    lines += ['', f"0.5B domain-cluster 95% difference interval: **{ci[0]*100:.2f} to {ci[1]*100:.2f} percentage points**.",
              f"Duplicated-row stress: {stress['counts']['baseline']['both_fixtures_match']}/{stress['scorable']} → {stress['counts']['adapter']['both_fixtures_match']}/{stress['scorable']}; {stress['unscorable']} unscorable fixtures remain recorded.", '',
              'Scores apply the same JSON-fence normalization and execute against source-labelled fixtures.',
              'This is not deployed Agent accuracy or independently verified business correctness.', '',
              '## Tokens and runtime', '', '| 0.5B condition | Input tokens | Output tokens | Total tokens | Generation seconds |',
              '| --- | ---: | ---: | ---: | ---: |']
    for name, u in usage.items():
        seconds = paired['generation_timing'][name]['generation_seconds']
        lines.append(f"| {name} | {u['input_tokens']:,} | {u['output_tokens']:,} | {u['total_tokens']:,} | {seconds:.2f} |")
    t = paired['training']
    lines += ['', f"Training: {t['samples']} samples, {t['seconds']:.2f} seconds, {t['training_tokens']:,} processed tokens, {t['supervised_tokens']:,} supervised tokens; peak allocated GPU memory {t['peak_allocated_bytes']/2**30:.2f} GiB.",
              'Inference uses batches of four; generation seconds exclude loading and SQL scoring. This is not HTTP request latency.',
              'Token counts exclude input padding and output padding after EOS. All outputs, including incorrect ones, count.',
              'Local token workload is not an API invoice. Historical timing is not a controlled cross-model speed comparison.', '',
              '## Changed-case inspection', '',
              '- Case 76091 restores the omitted manufacturer predicate; case 49293 restores the USA filter and expected projection.',
              '- Case 31613 regresses by dropping the ceramic-artifact predicate; case 1039 invents Rural/Non-Rural values in a state column.',
              '- Case 65292 is scored as fixed on its fixture but still omits the Shelters/Hospitals predicate. Case 95414 omits the non-null initiative predicate. These are not demonstrated semantic fixes.',
              '- Case 22244 changes column order to match the reference. Execution equality therefore includes output-contract alignment, not only reasoning gains.',
              'All 23 changed cases are retained in `qwen-0.5b/changed-cases.json`. Duplication stress cannot expose every missing filter.', '',
              '## Evidence and limits', '',
              'The duplicated-row stress report, paired statistics, raw responses, loss trace, model revision and adapter hashes are retained in `outputs/validation/small-model-comparison/`.',
              'A single seed and synthetic source fixtures limit generalization. The adapter is not automatically promoted.', '',
              'Model source: [official Qwen repository](https://huggingface.co/Qwen/Qwen2.5-Coder-0.5B-Instruct).', '',
              '## Reproduce', '',
              'Use the recorded model revision and `environment.txt`. Choose a fresh output directory; training refuses to overwrite an existing run.', '',
              '```bash',
              'PYTHONPATH=src python scripts/train_sql_lora.py --model runtime/models/qwen-coder-0.5b --dataset outputs/validation/strong-signal/qlora-dataset.json --output /tmp/sql-agent-small-reproduction',
              'PYTHONPATH=src python scripts/score_sql_lora.py --dataset outputs/validation/strong-signal/qlora-dataset.json --run /tmp/sql-agent-small-reproduction',
              'PYTHONPATH=src python scripts/analyze_sql_lora.py --dataset outputs/validation/strong-signal/qlora-dataset.json --run /tmp/sql-agent-small-reproduction --output /tmp/sql-agent-small-reproduction/paired.json',
              'PYTHONPATH=src python scripts/analyze_sql_fixture_stress.py --dataset outputs/validation/strong-signal/qlora-dataset.json --run /tmp/sql-agent-small-reproduction --output /tmp/sql-agent-small-reproduction/fixture-stress.json',
              '```', '']
    args.output.write_text('\n'.join(lines))
    print(json.dumps({'summary':paired['summary'], 'tokens':usage, 'paired':paired['paired']}, indent=2))


if __name__ == '__main__':
    main()
