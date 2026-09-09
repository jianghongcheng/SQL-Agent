# Contributing

SQL-Agent is a SQL Data Agent prototype. Keep analysis tasks read-only. Changes
to business data must use the separate, explicitly enabled CRUD workflow with
administrator approval, transactions and execution receipts.

- Keep offline evaluation answers out of planner prompts and general-query validation.
  Fixed catalog tasks may use application-owned reference SQL declared in their
  contract. Report those checks separately from blind model evaluation.
- Distinguish scripted demonstrations from real-model experiments.
- Preserve source provenance, benchmark conditions and negative results.
- Test failure behavior, role checks, stale claims and contract drift when changed.
- Never commit database credentials, API keys or private source databases.
- Before publishing, inspect the staged file list and local documentation links.
  Use portable commands and label excluded local artifacts explicitly.
- Run `python -m pytest -q` and `python -m compileall -q src` before proposing changes.
