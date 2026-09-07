# Market evidence and implementation priorities — 2026-09-06

This is a focused engineering comparison, not a representative US hiring survey.
Eight distinct role examples are retained below: seven had readable employer
descriptions; one Google role was available in the search index but could not be
confirmed on its live page. Five of the seven readable descriptions have an
experience minimum compatible with two years or less. A minimum of two years is
not the same as an entry-level designation or a guarantee of candidate fit.

The LinkedIn MCP entry-level California search returned zero results. The second
LinkedIn connector failed OAuth refresh. Neither response establishes that no
jobs exist. Employer pages and a real browser supplied the evidence below.
Posting dates are unknown; this date is the check date, not a posting date.

## Role evidence

| Employer / role | Location and experience | Evidence relevant to this project | Screening decision |
|---|---|---|---|
| [LiteLLM — AI Engineer](https://jobs.ashbyhq.com/litellm/6e025e39-6f8a-46bd-91f7-8784d1f5076b) | San Francisco; 1–2 years backend/full-stack production experience | Python, FastAPI, provider interoperability, MCP authentication, developer experience, user engagement | Direct target by years; need stronger evidence of provider interoperability and real users |
| [Eloquent AI — AI Engineer, Platform](https://jobs.ashbyhq.com/eloquentai/5ebee283-cf69-40a6-af38-e7d703bbab0f) | San Francisco; 1–2 years full-stack production experience | Backend integration, React/TypeScript/Node, cloud architecture, usable AI applications | Years fit; current plain-JS local UI does not establish the requested full-stack/cloud experience |
| [The Nuclear Company — AI Engineer 1, Platform Integration & AI/Data](https://job-boards.greenhouse.io/thenuclearcompany/jobs/5285585008?gh_src=Eclipse+job+board) | Washington, DC; 0–2 years; projects count | Backend/data integration, CI/CD, monitoring, MCP interfaces, traceable releases | Junior target; domain/platform ramp and location remain tradeoffs |
| [The Nuclear Company — AI Engineer 1, Compliance, Quality & Testing](https://job-boards.greenhouse.io/thenuclearcompany/jobs/5286179008) | Washington, DC; 0–2 years; projects count | Pytest/Playwright, prompt regression, output validation, behavioral consistency, traceable evidence | Junior quality/AI role; different emphasis from core agent development |
| [Cadence — AI Engineer](https://job-boards.greenhouse.io/solutions/jobs/4680769006) | Remote; 2+ years production AI/ML | Reliability, observability, cost efficiency, offline/safety/regression evaluation, recovery and human escalation | Two-year minimum, but substantial production expectations; used as workflow evidence, not a reason to add medicine back to this SQL project |
| [Fluency — AI Engineer](https://jobs.ashbyhq.com/fluency/9a83146e-e32d-4e0c-84b5-59996a58a821/) | San Francisco; no numerical experience floor found | End-to-end delivery, regression-catching evals, quality/latency/cost decisions, real users | Requirements comparison only; cannot certify junior eligibility |
| [Aperia — AI Engineer, LLMs + C#](https://job-boards.greenhouse.io/aperiasolutions/jobs/5200477007) | GA/TX/NE; 2+ years AI exposure **and 4+ years professional software development** | Enterprise integration, evaluation, monitoring, C#/.NET | Excluded from the two-year target; do not screen using only the AI experience line |
| [Google — GDC AI Applications and Agents](https://www.google.com/about/careers/applications/jobs/results/126988379509138118-software-engineer-gdc-ai-applications-and-agents?hl=en-PK&page=1) | Indexed: Sunnyvale; 2 years software development or 1 year with advanced degree in industry | Indexed: deployed agents, APIs/SDKs, platform engineering; algorithms and Kubernetes preferred | **Current availability unconfirmed.** Browser showed a jobs list, not this JD. Retained only as indexed large-company role evidence |

Readable Ashby browser snapshots are in `runtime/market-check-20260906/`.
The two Nuclear Company roles share an employer and must not be treated as
independent evidence about company-wide market prevalence. No hiring probability
or large-versus-small-company acceptance rate is inferred from these examples.

## What this means for ContractSQL

| Requirement | Existing evidence | Gap and action |
|---|---|---|
| Agent/backend integration | FastAPI, worker queue, SQL tools, contracts, review events | Preserve a coherent SQL product; avoid adding unrelated frameworks solely for keywords |
| Observability and cost tradeoffs | Previously recovery events and HTTP counters; usage existed in offline tools | **Implemented:** persistent per-job primary/checker requests, latency, retries and observed tokens; no invented dollar costs |
| Reliable monitoring | Previously stored every HTTP duration; review/replay/trace IDs could create new labels | **Fixed:** cumulative histogram buckets, normalized routes, bounded unknown-route/method labels |
| Evaluation that discovers failures | Prior 500-case BIRD report and small local demo | **Added:** same 24 synthetic episodes across three candidate configurations, independent arithmetic, controlled timeouts, source-integrity check, retained failures; regressing generation changes rejected |
| Practical error recovery | Bounded transient retries | **Measured:** injected timeout recovery separately from successful semantic completion; an API retry alone is not task success |
| Product presentation | Local query/review dashboard | **Added:** run performance display; real browser validation, not screenshots alone |
| Full-stack/cloud delivery | Local deployment and plain-JS UI | Still lacks demonstrated React/TypeScript depth, cloud deployment and real user feedback; local demo does not fill those gaps |
| General agent answer quality | BIRD 500 historical results and fixed commerce verification | General SQL correctness remains a major limitation; fixed metric success must not be described as general accuracy |

Prioritize agent/backend/platform roles whose requirements match your actual work.
The SF small-team examples value ownership and users, while the indexed Google
example adds platform scale and algorithms. This supports preparing different
project explanations for different roles; it does **not** show that small
companies are easier to enter. Your PhD/research history can support research
roles separately without trying to make this SQL project prove model-training work.

For an interview, explain one concrete chain: a multi-refund join duplicated order
amounts; an independent business reference refused release; the trace identified
an ineffective repair; two proposed generation/context changes were evaluated;
the regression evidence rejected both changes. Observability improvements shipped,
while the better original generation configuration was retained. Refer to
[the measured results](COMMERCE_OBSERVABILITY.md), including the unresolved failure.
