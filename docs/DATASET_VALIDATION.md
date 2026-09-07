# Dataset selection and real-data service validation

Sources checked on 2026-09-06. Use complementary workloads: external SQL quality,
debugging capability, and operational behavior over real records. A benchmark
score alone does not establish production readiness.

Update: the [combined experiment](COMBINED_EXPERIMENT.md) has since downloaded
three canonical BIRD databases and executed a frozen 30-case subset. The initial
inventory status and first TLC run below are retained as historical records.
The combined report contains the newer external score and fresh service results.

## Selected datasets

| Dataset | Purpose | Current integration | Constraint |
|---|---|---|---|
| NYC TLC green trips + taxi zones | Real data ingestion, quality checks, joins, HTTP workload | Imported and executed; results below | Questions are authored by this project, not an official SQL benchmark |
| BIRD Mini-Dev SQLite | Independent question-to-SQL answer evaluation across domains | Official 500-question/SQL release downloaded and inventoried | Matching canonical databases and an official-compatible grader still required |
| BIRD-Critic SQLite | Repair user-reported SQL issues | Official 500-issue release downloaded and inventoried | Includes management/writes; no correctness score without applicable official checks |
| Spider 2.0-Lite SQLite subset | More complex enterprise-style SQL workflows | Researched, not executed | Current runtime/tool context is narrower; cloud variants require separate setup |

[BIRD Mini-Dev's official card](https://huggingface.co/datasets/birdsql/bird_mini_dev)
describes 500 examples across 11 databases. Its SQLite release was pinned to
`f65faf4ae3b638c1fa6df1d3370c8d92c8366301`. Local inventory contains 148 simple,
250 moderate and 102 challenging cases. Do not mix versions or silently replace
its database with a similarly named database from another benchmark.

[BIRD-Critic's official SQLite card](https://huggingface.co/datasets/birdsql/bird-critic-1.0-sqlite)
describes SQL debugging tasks and several evaluation methods. The downloaded
`af2b1c3` task file has 500 issues: 284 Query, 75 Management and 141 Personalization;
203 have preprocessing SQL. Its fields do not include gold SQL or per-case test
functions. Category labels alone do not prove a task fits a read-only agent.
Official evaluator resources are linked from the
[project repository](https://github.com/bird-bench/BIRD-CRITIC-1).

Both BIRD dataset cards identify **CC BY-SA 4.0**. Raw downloads and attribution
cards are retained under ignored `data/local/`, not relicensed under this
project's code license. Inventory files record source revisions and hashes.
Medical domains are outside this project's intended public demo; any future
non-medical/read-only subset must publish exclusions before inference, and must
not be presented as a full benchmark score.

[Spider 2.0's official repository](https://github.com/xlang-ai/Spider2) lists 135
SQLite tasks within the 547-example Lite setting. It also reports Snowflake
access disruption dated 2026-08-12. Start with local SQLite rather than making
the portfolio demo dependent on that account. Repository code uses MIT; review
individual source-data terms separately. No Spider 2.0 score is claimed here.

## Real business records imported now

Source: [NYC TLC trip records](https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page),
January 2025 green trips and the official zone lookup. The source publishes
Parquet records and cautions that submitted data is not guaranteed accurate.
The [AWS dataset registry](https://registry.opendata.aws/nyc-tlc-trip-records-pds/)
links NYC terms of use; this is not being described as CC-licensed data.

The source Parquet is 1,178,451 bytes. Import retained **all 48,326 rows** and
**265 zones**. Seven source columns were selected, timestamps stored as ISO text,
and a row ID added. No outliers were silently removed. Raw file and SQLite SHA256
hashes, download URLs and transformations are recorded in the import manifest.

Independent Python calculations on raw Parquet, checked against imported SQLite:

| Check | Observed count |
|---|---:|
| All trip records | 48,326 |
| January pickup timestamps | 48,283 |
| Outside January or missing pickup timestamp | 43 |
| Missing passenger count | 1,836 |
| Negative fare | 150 |
| Zero distance | 2,671 |

An additional task groups trips by pickup location, joins zone names and checks
the top five with deterministic tie-breaking. These six tasks were defined before
the first model run; they are simple coverage tasks, not a broad SQL challenge.
The expected outputs were not obtained by asking the model or merely running
the same SQL used by the catalog verifier.

## Real-model and HTTP results

`outputs/validation/tlc_paired_v1/` contains three repeats per task:

- Exploratory mode: **18/18 correct**, zero false accepts and no catalog fallback.
- Verified mode: **18/18 correct**, same first responses replayed, no fallback.
- Only **six unique questions**; 18 repetitions are not 18 independent problems.
- Exploratory median 0.924 s, observed P95 1.337 s for these local worker runs.
- Verified timings exclude the replayed first inference and cannot be compared
  as end-to-end latency. There is no demonstrated retry benefit on this suite.

`outputs/validation/tlc_http_load_v1/` uses live inference, not response replay:

| Local acceptance workload | Result |
|---|---:|
| Clients / worker processes | 4 / 2 |
| Tasks submitted | 24 across six questions |
| Correct outputs | 24/24 |
| Duplicate submissions deduplicated | 24/24 |
| Incorrect outputs accepted / catalog fallbacks | 0 / 0 |
| Median / observed P95 completion latency | 1.961 s / 2.226 s |
| Total workload duration | 12.683 s |
| Observed throughput | 1.892 jobs/s |

Timing includes submission, queueing, model execution and result polling. This
is a short closed-loop test on one machine, not a sustained load test, production
SLO, scaling limit or claim about other hardware. Every result was independently
checked. Worker kill/recovery and HTTP model timeout are separately tested as
described in [RELIABILITY.md](RELIABILITY.md).

## Reproduce

Python 3.10+, install `pip install -e '.[dev,data]'`; an existing local Ollama
server must provide `qwen3:8b`. From the repository root:

```bash
python scripts/prepare_tlc_data.py --output data/local/tlc-new
python scripts/validate_registered_dataset.py --data data/local/tlc-new \
  --output outputs/validation/tlc-new --repeats 3
python scripts/load_registered_service.py --data data/local/tlc-new \
  --output outputs/validation/tlc-http-new
```

Commands refuse to overwrite prior output directories. Generated `tasks.json`
also works with the existing API/worker configuration. Database files and raw
BIRD downloads remain in ignored local data. The paired evaluator now checks
the database hash against the import manifest before inference; that preflight
was added after the first recorded run, whose original manifest is preserved.

## What these results support

The project now demonstrates a reproducible public-data import, explicit data
quality checks, independently checked query results, and authenticated API/worker
operation under a small concurrent workload. This is stronger evidence than only
toy SQL tests. It does not yet establish broad external benchmark accuracy,
tenant isolation, public deployment, durable recovery at scale or long-term uptime.

The next independent model-quality target is BIRD Mini-Dev using its matching
databases and reference execution grader. Keep gold SQL out of prompts, runtime
business checks and catalog fallback in that track. Publish unsupported cases,
timeouts and exclusions rather than removing them from the denominator after
seeing model results. Use BIRD-Critic only with its applicable issue tests, and
Spider 2.0 after extending context/tool support; do not claim either from a
subset of successfully executing queries.
