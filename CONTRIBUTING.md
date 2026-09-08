# Contributing

ContractSQL is a SQL Data Agent prototype. Keep changes focused on registered
read-only tasks, explicit contracts, evidence, evaluation and reliable execution.

- Keep reference answers out of planner prompts and runtime verification.
- Distinguish scripted demonstrations from real-model experiments.
- Preserve source provenance, benchmark conditions and negative results.
- Test failure behavior, role checks, stale claims and contract drift when changed.
- Never commit database credentials, API keys or private source databases.
- Keep personal career material, account troubleshooting, and machine-specific
  scratch notes outside this public repository.
- Before publishing, inspect the staged file list and local documentation links.
  Use portable commands and label excluded local artifacts explicitly.
- Run `python -m pytest -q` and `python -m compileall -q src` before proposing changes.
