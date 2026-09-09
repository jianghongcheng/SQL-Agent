# Public metric evidence — 2026-09-09

These are synthetic commerce development cases, not private business traffic.
The files deliberately exclude API credentials, control databases, session IDs,
private Compose configuration, model weights and unrelated host state.

- [metrics.json](metrics.json): complete metric denominators, paired intervals,
  model/image identities and source fingerprints for the before/after runs.
- [before.json](before.json) and [after.json](after.json): all 48 cases per run,
  including question, generated SQL, expected/actual results, advisory verifier SQL,
  terminal status, token ledger, latency and original local-record hashes.
- [qlora.json](qlora.json): new 0.5B and historical 1.5B scoring summaries,
  uncertainty, token workload, training measurements and new adapter hashes.
- [sha256.json](sha256.json): hashes of the public JSON evidence files.
- [verification.json](verification.json): publication checks; 383 tests passed in
  the full invocation, then all 19 skipped PostgreSQL tests passed against a
  disposable database. All 402 collected tests were covered across the two runs.

Accuracy requires exact output columns and ordered rows against the external
Python oracle. SQL execution alone does not count. Token cost per correct task
includes all submitted workload, not just correct tasks. Verifier false accept
is wrong candidates with agreement divided by all wrong candidates; false discovery
uses all agreements as its denominator. No general answers were auto-released.

The post-repair development run is 35/48, with two wrong agreements among 13
wrong candidates (15.4% false accept) and among 23 agreements (8.7% false discovery).
The same templates recur across data variants; confidence intervals cluster by
question family. Latency excludes the separately retained task warmups and includes
client queue/polling time. This is a shared-host comparison, not a production SLO.

Recompute public metrics from a checkout with development dependencies installed:

```bash
PYTHONPATH=src:. python scripts/verify_public_metrics.py
```

No blind-holdout score is included. New synthetic holdout/challenge cases were
prepared after runtime freeze, but no completed, verified report has been published
in this release. See [remaining gates](../../NEXT_QUALITY_GATES.md).
