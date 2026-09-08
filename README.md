# ContractSQL

A SQL Data Agent that turns natural-language requests into **reviewable,
read-only queries** over registered SQLite sources.

The default `commerce_analysis` task supports totals, row lists and grouped
results. A local model proposes SQL; the application controls execution,
bounded repair, persistent jobs and human review.

## Quick start

Requires Python 3.10+, local Ollama and the `qwen3:14b` model.

```bash
git clone https://github.com/jianghongcheng/contractsql.git
cd contractsql
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
PYTHONPATH=src:. python scripts/local_demo.py start --model qwen3:14b --generation-format sql --thinking --max-tokens 8192
```

Open http://127.0.0.1:8765 and select **Enter local demo**. The public demo key
`123` is only for loopback demonstrations, not deployment.

## How it works

Question + registered task → durable job → bounded SQL generation/execution/repair
→ candidate + evidence → human review.

- API, browser dashboard, CLI and MCP interfaces.
- Read-only authorization, query budgets and output checks.
- Idempotent submission, worker leases, retries and stale-worker write protection.
- SQL, errors, model usage and review records retained for inspection.
- Separate offline scoring against reference answers.

## Documentation

- [Usage](docs/USAGE.md): setup, examples, task registration and interfaces.
- [Evaluation](docs/EVALUATION.md): protocols, results, failures and reproduction.
- [Reliability](docs/RELIABILITY.md): execution limits, recovery and review.

## Boundaries

Successful execution is not proof of a correct business answer. General-analysis
candidates require review, including when structural checks pass. Fixed catalog
metrics can use a separately registered reference query; that is not a general
semantic verifier.

This is a local prototype, without demonstrated customer adoption, sustained-load
SLOs or production accuracy. Only SQLite analytical sources are supported.
PostgreSQL job-store integration has not been validated against a live service.

Code, tests, synthetic fixtures and evaluation scripts are public. Raw run logs,
runtime databases, model weights and downloaded datasets are not bundled.

Medical imaging is maintained separately in
[RadMeasure](https://github.com/jianghongcheng/radmeasure-agent).
Legacy `geomed_copilot` imports and `radmeasure` command aliases remain; install
the two projects in separate virtual environments. Shared project history is
still accessible in Git.
