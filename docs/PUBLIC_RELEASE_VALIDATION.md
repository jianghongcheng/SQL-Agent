# ContractSQL public release

Checked locally on 2026-09-06 (America/Chicago), Python 3.11.

- Full suite: **237 passed**, 26.75 seconds, one dependency deprecation warning.
- Python source compilation passed.
- Harbor v1 export reproduced the committed task files without a diff.
- Medical source and research scripts are removed from the current SQL tree.
  Shared project history is preserved, not rewritten.

This check validates software regressions. It is not a fresh live-model accuracy
benchmark, deployment load test, or production-user impact measurement.
Existing reports preserve the dates and limitations of earlier local experiments.

## Public contents

Code, tests, synthetic SQL fixtures, and explanatory reports are included.
Raw outputs/validation runs are intentionally not published: they include runtime
databases, logs, third-party benchmark content, and source snapshots. Models,
downloaded datasets, and local processed data also remain excluded.
Report references to these artifacts describe local evidence, not files supplied
in a fresh public clone. Reproduce runs with the documented prerequisites.

The Python distribution is named contractsql. Legacy radmeasure commands and
geomed_copilot imports are retained for compatibility. Use separate virtual
environments for this project and RadMeasure because the legacy module namespace
is still shared.

The existing local working project and the archived medical tree were not edited.
