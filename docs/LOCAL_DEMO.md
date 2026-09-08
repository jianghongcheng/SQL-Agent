# ContractSQL local demonstration

Open **http://127.0.0.1:8765** on this machine. Click **Enter local demo** on the sign-in page.
Eight registered tasks use synthetic
data, a real worker and local Ollama `qwen3:14b` with reasoning enabled. This is an
asynchronous demonstration: the selected evaluation profile had 74.83-second p95
latency. General results require review.

The homepage links to **http://127.0.0.1:8765/benchmark**: 864 recorded inference
episodes across several experiments, including failures and per-query evidence.
These are repeated development experiments, not 864 independent questions. The
page also shows 3456 offline data-instance checks, which add no model calls.

## Present the workflow

1. Select `net_revenue`, leave initial SQL empty, submit and wait for the worker.
   Inspect business definitions, source checks, SQL, tokens and the accepted
   result: **17000 cents ($170)**. Unknown dollar cost is explicitly unavailable.
2. Select `blocked_stale`. Source checks block analysis before model inference.
   Record a rejection with notes and inspect the persisted review history.
3. Select `invoice_balance`. Inspect the visible **synthetic billing dictionary**,
   which defines settled receipts, and submit. Expected fixture balances are
   `[[11,38],[12,100],[13,-70],[14,0],[15,50]]`. This task has no reference-query
   verifier or answer fallback; its general candidate still needs review.
4. Open **Full evidence and audit history** for SQL, tool observations and review
   events. Use the benchmark page to explain both successful repairs and failures.

The other tasks are `gross_revenue`, `approved_refunds`, `blocked_invalid` and
`free_analysis_review`. Fixed questions cannot be edited away from their registered
metric. Human approval records a decision; it is not a correctness proof.

## Start and stop

From the repository, with dependencies and the Ollama model already installed:

```bash
PYTHONPATH=src:. python scripts/local_demo.py start \
  --model qwen3:14b --generation-format sql --thinking --max-tokens 8192
PYTHONPATH=src:. python scripts/local_demo.py status
PYTHONPATH=src:. python scripts/local_demo.py stop
```

Use Python from the virtual environment where you installed the project.
The launcher does not download models. It binds the API to loopback and uses the
intentionally public `123` credential. Restarting refreshes disposable
source fixtures and ingestion times; job history remains in
`runtime/local-demo/jobs.sqlite`. The freshness budget is 24 hours. Logs are
`runtime/local-demo/api.log` and `worker.log`.

## Reproduce acceptance

```bash
python -m pytest -q
PYTHONPATH=src:. python scripts/validate_local_login.py
PYTHONPATH=src:. python scripts/validate_local_demo_browser.py
PYTHONPATH=src:. python scripts/validate_local_mcp.py
PYTHONPATH=src:. python scripts/validate_model_comparison_browser.py
```

Browser checks require Playwright and Chrome at `/usr/bin/google-chrome`.
Run acceptance scripts sequentially for a predictable demonstration. A single
worker can keep another job queued during a long inference request. The MCP
acceptance wait budget is 180 seconds, not a queue-latency SLO.

- Full Python suite: **217 passed**, one dependency deprecation warning; also
  verified through a console-script-style pytest entry point without PYTHONPATH.
  The subsequent dashboard edit passed all 8 relevant API/evidence tests; browser
  acceptance additionally checks that review notes clear when the job changes.
- Browser evidence: `runtime/local-demo/browser-acceptance.json`; every run,
  including failures, is retained in `browser-runs/` with screenshots/job evidence.
- MCP evidence: `runtime/local-demo/mcp-acceptance.json` and `mcp-runs/`; verifies
  stdio discovery, authentication, idempotency and persisted blocked-task access.
- Report evidence: `runtime/local-demo/benchmark-browser-acceptance.json`; verifies
  all 864 trajectories, comparison counts and expandable SQL evidence.

Read each acceptance file's `passed` and timestamps for the actual latest result.
An initial MCP acceptance timed out while queued behind browser inference; an
initial browser check incorrectly read hidden evidence as visible text. Both
failures were retained and the acceptance scripts corrected.

## Limits

Three fixed metrics compare output against registered business-reference SQL on
one shared read snapshot. Those checks are separate from blind SQL evaluation.
The billing demo's visible dictionary is additional application context; its
success must not be mixed into the pure SQL regression score. Historical BIRD 500
questions have not been rerun with the selected profile. No current result proves
production usage, a deployment SLO, or general semantic correctness.

## Button interaction fix

The earlier acceptance covered successful task execution but missed several
interaction failures. The dashboard now provides visible, sticky action feedback;
validates missing job IDs; disables a pending submission; uses browser random bytes
instead of requiring `crypto.randomUUID`; and continues polling when an existing
queued/running job is opened. Request errors no longer overwrite the job status.
Review controls explain why approval is unavailable. Reload the page after a UI
update to load the current script.

Reproduce isolated browser regressions with
`python -m pytest -q tests/test_dashboard_interactions.py` (Chrome and Playwright).
The ten tests use deterministic HTTP responses and cover loading, authorization
failure, empty inputs, submission compatibility, polling, and both review actions.
Run `PYTHONPATH=src:. python scripts/validate_dashboard_buttons.py` to click all six
buttons against the real local service. It creates its own synthetic jobs and
records every attempt under `runtime/local-demo/button-runs/`; latest outcome is
`button-acceptance.json`. Explicit initial SQL is used; this is UI acceptance, not
a SQL generation accuracy experiment.


The initial selection now prefers the editable `commerce_analysis` task. Fixed metrics are labeled in the selector and have a visible lock
explanation plus a button to switch to an editable task. Questions and SQL drafts
are retained per task during switching/reloading. Editable questions still use
the selected task's registered source and output contract. The input acceptance
record is `runtime/local-demo/input-acceptance.json`, covering real typing at
1440px and 390px widths and submission of the edited question to the API.


## Browser sign-in

The browser now exchanges a configured access key for a server-side session via
`POST /v1/auth/login`. The local demo button uses the intentionally public demo
credential; it is not a public account-registration service. Successful login
shows the authenticated name and role. `GET /v1/auth/session` restores the session
on refresh. `POST /v1/auth/logout` revokes it server-side and clears the cookie.
A signed-out or expired session cannot read tasks or submit jobs. Existing API-key
clients and MCP remain supported.

Cookies are HttpOnly, SameSite=Strict, and Secure on HTTPS. Sessions expire after
8 hours, are bounded to 1024 entries, and are held in this API process's memory;
restarting the API requires signing in again. This local single-process setup
is not a shared multi-replica identity service. No email/password registration,
password reset, or OAuth integration is claimed. The workspace's existing shared
role model remains in place; login does not add tenant isolation.

The latest real-browser result is `runtime/local-demo/login-acceptance.json`;
all attempts and screenshots are under `login-runs/`. It verifies invalid access,
login, refresh, editing, logout and denial when replaying the revoked cookie.

After the login change, the complete Python suite passed **232 tests** (one
FastAPI/Starlette dependency deprecation warning). The real-browser sign-in run
also passed, including server rejection of the revoked session. Test output is
retained in `runtime/local-demo/login-regression-tests.log`.


## Flexible commerce analysis

The default task is now `commerce_analysis`, using `analytics.sqlite`. The Example
question menu offers total revenue, a full order list, and monthly revenue on the
same database; users can also type a new question. Results may have different
column names and row counts, within read-only and size limits. This task always
requires review. The older fixed metric tasks remain available.

The result panel separates worker processing time from observed submit-to-result
time on the current browser page. The latter includes queue and polling latency.
The new acceptance protocol and its limitations are documented in
[PRODUCT_ACCEPTANCE.md](PRODUCT_ACCEPTANCE.md).
