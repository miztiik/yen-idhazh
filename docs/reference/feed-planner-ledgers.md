# Feed planner ledgers

**Last Updated**: 2026-11-04

Which data does each feed planner ledger retain?

**Five committed ledgers**, all under `state/raw/feed-ingest-plan/`:

- `discovered-articles`
- `selected-articles`
- `rejected-articles`
- `feed-health-state`
- `plan-runs`

Selected text is written to a separate workflow artifact for the summarizer.
It is not stored in committed selected rows.

The [article identity contract](../architecture/contracts/identity.md#typescript-resource-addresses)
maps public API `article_id` to native `url_key`. Discovery, selected and
rejected column names do not change. Combined summaries may include readable
URLs under the [response option](../architecture/sources/feed-plan-runner.md#entry-points-and-controls);
that option adds no ledger column, including to `plan-runs`.

The TypeScript schemas own planner settings, events, requests, receipts, stage
payloads and these ledgers. Python runs the gardener scheduler and delegates
planner validation and compaction to the TypeScript writer.

## Contents

- [A. discovered-articles](#a-discovered-articles)
- [B. selected-articles](#b-selected-articles)
- [C. feed-health-state](#c-feed-health-state)
- [D. plan-runs](#d-plan-runs)
- [M. rejected-articles](#m-rejected-articles)
- [E. Dates, counters and compaction](#e-dates-counters-and-compaction)
- [L. Lookback summaries](#l-lookback-summaries)
- [TypeScript contract ownership](#typescript-contract-ownership)
- [Raw-day membership](#raw-day-membership)
- [Field-based health history](#field-based-health-history)
- [TypeScript current-format refusal](#typescript-current-format-refusal)

## A. discovered-articles

**Committed ledger.** Records earliest discovery globally across feeds, including
articles never selected.

### Table A - Discovery fields

| ID | Final field | Location | Why |
| --- | --- | --- | --- |
| A1 | `schema_version` | Metadata | Identify the declared format |
| A2 | `url_key` | Row | Stable hash of the canonical URL |
| A3 | `first_seen_at` | Row | Establish age for undated articles; never reset on rediscovery |
| A4 | `date` | Row | UTC date of first discovery; explicit day-partition/query key |

## B. selected-articles

**Committed metadata ledger plus artifact handoff.** Compute each selected
article once in memory, then serialize two representations:

- Workflow artifact: selected metadata plus `article_text`.
- Committed Parquet: the declared metadata fields, without `article_text`.

### Table B - Selected article fields

| ID | Final field | Location | Committed? | Why |
| --- | --- | --- | --- | --- |
| B1 | `schema_version` | File metadata | Yes | Validate each representation's declared format |
| B2 | `run_id` | Artifact header / Parquet row | Yes | Link to `plan-runs`; preserve identity when compaction mixes runs |
| B3 | `url_key` | Article | Yes | Stable article identity |
| B4 | `feed_id` | Article | Yes | Identify the supplying feed |
| B5 | `publisher_id` | Article | Yes | Curated publisher metadata; nullable; not a selection count key |
| B6 | `canonical_url` | Article | Yes | Validated article URL |
| B7 | `title` | Article | Yes | Selected article metadata and summarizer input |
| B8 | `categories` | Article | Yes | Original feed category strings; empty arrays remain empty arrays |
| B9 | `article_text` | Artifact article | No | Sanitized summarizer input; never in committed Parquet or logs |
| B10 | `author` | Article | Yes | Attribution; nullable |
| B11 | `published_at` | Article | Yes | Trusted source publication or actual selection-start UTC instant; unknown source time does not make this null |
| B13 | `weight` | Article | Yes | Configured feed weight actually used |
| B15 | `editorial_rank` | Article | Yes | Chosen order |
| B16 | `estimated_work` | Article | Yes | Work estimate used for bin packing |
| B17 | `worker_assignment` | Article | Yes | Zero-based partition assignment; null before partitioning |
| B18 | `ratings.base_article_score` | Article | Yes | Cached authority plus recency plus technical pass adjustment plus substance; includes both fixed adjustments |
| B19 | `ratings.marginal_score` | Article | Yes | Actual score when chosen |
| B20 | `ratings.adjustments[].term` | Article | Yes | Identify each evaluated adjustment |
| B21 | `ratings.adjustments[].value` | Article | Yes | Required finite signed contribution for each of the five terms; never null |
| B22 | `ratings.recency_score` | Article | Yes | Actual recency contribution to the base score |
| B23 | `ratings.feed_authority_score` | Article | Yes | Actual weighted feed-authority contribution to the base score |
| B27 | `timing_at` | Article | Yes | UTC publication/first-sight instant actually used for age; null only for unavailable timing |
| B28 | `timing_basis` | Article | Yes | `published_at`, `first_seen` or `unavailable`, consistent with B27/B29 |
| B29 | `age_hours` | Article | Yes | Finite signed age actually evaluated, not age at upload; null only for unavailable timing |
| B30 | `date` | Artifact header / Parquet row | Yes | Owning run's UTC accounting date, not publication date |
| B31 | `evaluated_at` | Artifact header / D19 | In D19 | Save the evaluation clock once in the run ledger; include it in the self-contained artifact |
| B33 | `attempt` | Artifact header / Parquet row | Yes | Owning workflow/run attempt; not a selection-idempotency key |
| B34 | `published_at_source` | Article | Yes | `source` or `selection`; never infer provenance from the timestamp |
| B35 | `freshness_cutoff_at` | Article | Yes | Required UTC global-policy cutoff against D19, including when age is unknown; not proof of freshness |
| B36 | `word_count` | Article | Yes | Required nonnegative integer count of the complete sanitized body, copied from parsing |
| B37 | `substance_word_count` | Article | Yes | Required nonnegative integer retained-paragraph count, copied from screening; includes measured zero and must be <= B36 |

Unavailable history remains null in its evidence and contributes a zero
adjustment. A measured zero pass fraction still receives the configured floor
penalty.

### Table N - Required score adjustments in stored order

| ID | Term | Meaning |
| --- | --- | --- |
| N1 | `article_pass_rate` | Fixed authority reduction from measured technical article-pass history; numeric zero when disabled or history is unavailable |
| N2 | `substance_quality_score` | Fixed signed screening substance score, cached as `freshness.substance_score` before selection |
| N3 | `domain_diversity_penalty` | Negative configured coefficient times squared pre-choice count for the canonical website key; numeric zero for its first winner |
| N4 | `feed_diversity_penalty` | Negative configured coefficient times squared pre-choice feed count; numeric zero for its first winner |
| N5 | `novelty_bonus` | Configured first-use feed bonus when that feed has no prior winner; otherwise zero; not historical or story novelty |

Every selected row requires these five terms once in this order. The score is
reconstructed in the stored order:

```text
base_article_score = ((feed_authority_score + recency_score) + article_pass_rate) + substance_quality_score
marginal_score = ((base_article_score + domain_diversity_penalty) + feed_diversity_penalty) + novelty_bonus
```

Static adjustments are part of the base score and are not added twice. The
[curation rules](../architecture/sources/feed-curation.md) define the
calculation, configured inputs and tie rule.

`evaluated_at` is the age and scoring clock captured for the selected batch.
When no trusted entry-level publication time exists, `published_at` uses the
captured selection-start time and `published_at_source` is `selection`. This
display timestamp does not change age evidence, freshness or ranking.
Unavailable timing is represented by null timing fields and a zero recency
score. Both known and unavailable timing require the captured freshness cutoff.

## C. feed-health-state

**Committed ledger.** One finalized raw Parquet file per
run and UTC work day, batching all feed rows for that run/day. Actual work
counters describe that run/day, not cumulative daily totals. Lifecycle and
reliability columns retain the supported saved calculation, updated with this
run's actual work. Carry-forward rows do not claim a new check.

Daily totals and an API/public `recent_days` view are derived from the bounded
run rows. Compaction packs the rows; it does not turn run counters into daily
totals or add together saved rolling reliability results.

### Table C - Feed health fields

| ID | Final field | Location | Why |
| --- | --- | --- | --- |
| C1 | `schema_version` | Metadata | Identify the format |
| C2 | `updated_at` | Metadata | When this run/day file was finalized; not a counter-reset clock |
| C5 | `feed_id` | Feed/run/day | Identify the feed |
| C6 | `endpoint_key` | Feed/run/day | Prevent a changed feed URL inheriting the old endpoint's state |
| C7 | `checked_at` | Feed/run/day | Actual feed-check time; nullable when this work day had no feed check |
| C9 | `availability` | Feed/run/day | Supported computed eligibility, rest, retirement or unknown state |
| C10 | `strikes` | Feed/run/day | Observed logical failure streak; a supported lower bound when earlier history is partial, null before known checks |
| C12 | `last_failure_code` | Feed/run/day | Explain the run's latest feed failure without free-text payloads |
| C13 | `status` | Feed/run/day | Actual feed HTTP status; nullable; not catalog membership |
| C14 | `reliability.productive` | Captured lookback | Productive reads in the measured lookback used for this run |
| C15 | `reliability.attempted` | Captured lookback | Evidence-bearing reads; excludes rest skips |
| C16 | `reliability.success_fraction` | Captured lookback | Measured productive fraction, saved downward to three decimal places |
| C18 | `reliability.from_day` | Captured lookback | Beginning of the represented evidence window |
| C19 | `reliability.through_day` | Captured lookback | End of that window |
| C20 | `reliability.production_factor` | Captured lookback | Original fraction with the run's floor applied, then saved downward to three decimal places |
| C21 | `reliability.complete` | Captured lookback | Distinguish complete lookback coverage from partial history |
| C22 | `date` | Feed/run/day | UTC day of the work being counted |
| C23 | `feed_reads` | Run counters | Logical feed checks represented by this row, not retry requests |
| C24 | `productive_reads` | Run counters | Productive checks under the existing outcome/items rule |
| C25 | `failed_reads` | Run counters | Failed feed checks represented by this row |
| C26 | `article_candidates` | Run counters | Original captures passing technical admission, accounted on their actual UTC settlement day; independent of selection |
| C27 | `articles_selected` | Run counters | Selected opportunities from this feed in this run/day |
| C28 | `feed_requests` | Run counters | Actual feed requests, including retries/redirects |
| C29 | `article_requests` | Run counters | Actual article requests |
| C31 | `counts_complete` | Run counters | Flag incomplete accounting; unknown counts remain null |
| C32 | `rejection_counts[].reason_code` | Run counters | Aggregate rejection reason |
| C33 | `rejection_counts[].count` | Run counters | Number rejected for that grouped reason |
| C34 | `run_id` | Feed/run/day | Link to run settings and retain identity after compaction mixes runs |
| C35 | `rejection_counts[].subject` | Run counters | Distinguish feed failures from article exclusions |
| C36 | `rejection_counts[].stage` | Run counters | Preserve which stage made the decision |
| C37 | `rejection_counts[].attribution` | Run counters | Feed, pipeline or unknown for failures; null for ordinary exclusions |
| C38 | `attempt` | Feed/run/day | Retain the run attempt when compacted rows from different executions coexist |
| C39 | `items` | Feed/run/day | Existing distinct-offered-URL count used to decide whether the feed read was productive |
| C40 | `outcome` | Feed/run/day | Native target-download result, not parsed validity; combined with C39 for read productivity |
| C41 | `links` | Feed/run/day | Zero or one `{ traceId, spanId }` reference to the logical feed-check fetch operation; empty when no check is known |
| C42 | `check_result` | Feed/run/day | Parsed validity or typed HTTP, timeout, transport, local or interrupted result |
| C43 | `rest_until` | Saved calculation | Supported UTC recovery deadline |
| C44 | `first_confirmed_failure_at` | Saved calculation | UTC first observed confirmed failure in the known episode; partial history does not claim an earlier unseen start |
| C45 | `failed_recovery_checks` | Saved calculation | Observed qualifying confirmed recovery failures; partial history does not claim an exact earlier total |
| C46 | `retired_at` | Saved calculation | UTC instant of a proven retirement decision |
| C47 | `retirement_reason` | Saved calculation | Typed reason recorded with C46 |
| C48 | `availability_updated_at` | Saved calculation | Actual check instant that last changed the calculation; carry-forward does not advance it |
| C49 | `availability_complete` | Saved calculation | Whether the complete lifecycle calculation is supported; not source reachability |

Run counters describe that run and work day, not cumulative daily totals.
Daily opportunity totals sum per-run decisions and do not claim unique articles.
Request totals measure dispatched work, not waste or blame.

The writer treats a read as productive only when `outcome == "ok"` and
`items > 0`. `items` counts distinct offered canonical URLs, not raw entries,
extracted articles or selected articles.

Saved reliability values describe the lookback evaluated for that run; they
are not additive counters. Readers aggregate run counters separately and
deduplicate repeated storage representations without discarding distinct work.
Missing evidence remains unknown.

The same historical check keeps its original C41 reference across run, attempt
and day projections. Rest and reliability count that logical check once, not
once per stored copy or network retry. A contradictory copy remains incomplete
evidence. These historical references do not require a live listener entry and
cannot reopen a fetched body or stage result.

## D. plan-runs

**Committed ledger.** One small summary per execution, including empty and
failed runs.

### Table D - Run fields

| ID | Final field | Location | Why |
| --- | --- | --- | --- |
| D1 | `schema_version` | Metadata | Identify the format |
| D2 | `run_id` | Run | Identify the execution |
| D3 | `started_at` | Run | UTC start time, stored once |
| D4 | `duration_ms` | Run | Measured monotonic elapsed time; null when a restarted stage chain has no recoverable start; no redundant end timestamp |
| D5 | `status` | Run | Completed, partial or failed |
| D6 | `failure_code` | Run | Explain a run-level failure; nullable |
| D7 | `selected_count` | Run | Explicit result, including zero; a missing selected file is not an empty result |
| D8 | `strategy` | Run | Actual partition strategy |
| D9 | `dispatch_count` | Run | Number of worker partitions |
| D10 | `selected_articles_artifact` | Run | Relative POSIX artifact path only; no traversal, absolute path, content or signed URL |
| D11 | `api_timings[].operation` | Timing entry | Actual fetch, parse, select, partition, persist, feed-health-before-fetch or feed-health-for-selection operation |
| D12 | `api_timings[].duration_ms` | Timing entry | Measured operation duration |
| D13 | `api_timings[].status` | Timing entry | Completed, failed or interrupted |
| D14 | `date` | Run | UTC accounting day of `started_at`; explicit day-partition/query key |
| D15 | `attempt` | Run | Identify the workflow/run attempt, where applicable |
| D16 | `lifecycle_window_days` | Run | Actual represented-day limit used by this run |
| D17 | `reliability_floor` | Run | Actual floor used for this run's saved factors |
| D18 | `reliability_penalty_enabled` | Run | Whether the measured technical article-pass adjustment was enabled |
| D19 | `evaluated_at` | Run | Actual captured age/scoring clock used by the selected batch |
| D20 | `request_report_closed_days` | Run | Actual closed-UTC-day window for the request-spend report; default seven |
| D21 | `reliability_window_days` | Run | Actual represented-day feed-reliability lookback; current default 30 |
| D22 | `selection_started_at_utc` | Run | Actual selection-start clock used to capture current feedback windows, distinct from a saved batch's older age clock |
| D23 | `selection_metrics` | Run | Required nullable object; null only when selection did not complete, regardless of run status or a captured selection-start clock |
| D24 | `selection_metrics.selected_website_groups` | Run | Distinct canonical website keys from the configured resolver; zero for completed empty selection; otherwise positive and <= D7 |
| D25 | `selection_metrics.selected_feeds` | Run | Distinct selected feed IDs, including first uses with zero configured bonus; not historically new feeds; bounds match D24 |
| D26 | `selection_metrics.mean_substance_score` | Run | Arithmetic mean of exactly one required finite `substance_quality_score` adjustment per selected row; null only for completed empty selection |

An empty completed selection has zero counts and a null mean. A nonempty
selection requires positive bounded counts and a finite mean. Missing or
repeated substance-score terms fail validation. The metrics come from selected
metadata, not a second analysis.

Selection metrics and the selected count remain recorded if a later assignment
or persistence step fails. A null metric means selection did not complete; it
does not mean measured zero.

Timings describe measured API operations or major plan phases. They do not form
per-article trace trees.

## E. Dates, counters and compaction

### Table E - Date meanings

| ID | Output | Date field | Meaning |
| --- | --- | --- | --- |
| E1 | `discovered-articles` | A4 `date` | UTC day of A3 `first_seen_at` |
| E2 | `selected-articles` | B30 `date`, artifact header / committed row | Owning run's accounting day, not publication day |
| E3 | `feed-health-state` | C22 `date` | Actual UTC work day for this row's counters |
| E4 | `plan-runs` | D14 `date` | UTC day of D3 `started_at` |

`date` is a compact partition/query key, not another timing trace. Publication
time, first discovery, actual feed checks and run start describe different
events; they are not replaced by one fabricated common timestamp.

The health ledger groups all feed rows from one run and UTC work day. A run
crossing midnight can write two day files. Completed feed work remains
recordable when a later stage fails.

Compaction preserves row identity and recorded values. It does not recalculate
scores, add saved lookback values, change evaluation clocks or turn missing
evidence into complete data.

## L. Lookback summaries

These current settings govern lifecycle, feed-read reliability and request
spend.

### Table L - Independent windows

| ID | Component | Current default and unit | Retained meaning |
| --- | --- | --- | --- |
| L1 | Lifecycle/rest | `feedback.lifecycle_window_days = 31` represented UTC days | Select named represented days for lifecycle evidence |
| L2 | Feed-read reliability | `collect.reliability_window_days = 30` represented days; `collect.reliability_floor = 0.5` | Measure productive feed reads and apply the configured floor |
| L3 | Request-spend report | `feedback.request_report_closed_days = 7` closed UTC calendar days | Sum observed feed and article requests; not a waste score or ranking penalty |

The windows use UTC and serve different calculations. Unknown or missing
evidence remains incomplete; saved reliability values are not added as daily
counters.

## M. rejected-articles

This ledger records parsed candidates that were not selected and completed
article fetch or extraction failures. It does not store titles, article text,
policy trees or scores. Completed failures remain available when a later
stage fails.

### Table M - Rejected article fields

| ID | Field | Meaning |
| --- | --- | --- |
| M1 | `schema_version` | File metadata declaring the current row format |
| M2 | `run_id`, `attempt`, `date` | Execution identity and its UTC accounting day |
| M3 | `candidate_id` | Required non-null lowercase hyphenated UUIDv4 for the captured article input |
| M4 | `url_key`, `feed_id` | Canonical URL hash and supplying feed |
| M5 | `stage`, `reason_code` | Terminal harvest failure or final screening/curation refusal |
| M6 | `freshness_cutoff_at` | Applied UTC age cutoff, or null when no cutoff was applied |
| M7 | `http_status` | Actual article target response status, or null if not observed |
| M8 | `fetch_failure` | Typed terminal download failure, or null when no fetch failure was observed |
| M9 | `error_code` | Validated low-level transport code, or null if not observed |
| M13 | `pacing_time_ms` | Measured total queue wait for the fetch, or null when unmeasured |
| M14 | `pacing_settings` | Effective domain delay, publisher delay, jitter and enable setting |

Rows are identified by run, attempt and candidate. Retries produce one
terminal row per candidate and run; a recovered fetch does not leave a stale
failure row. Distinct captured inputs for one URL remain distinct rows.
There is no nullable-identity settlement fallback. Feed refusals and malformed
article entries do not become terminal article rows.
Grouped health counters remain the source for health totals, so
rejection rows are not counted again.
See [harvesting](../architecture/sources/feed-harvesting.md#work-facts-and-failures)
for when completed failure rows are written.

The [current TypeScript contract](../architecture/sources/planner-feed-history.md)
defines row validation and historical read behavior.

## TypeScript contract ownership

Schemas under `packages/common-contracts/src/schemas/` define these rows.
The gardener delegates planner validation and compaction to the TypeScript
writer.

## Raw-day membership

See the [bounded day membership rules](../architecture/sources/planner-feed-history.md#named-evidence-and-independent-windows).

## Field-based health history

See the [health history rules](../architecture/sources/planner-feed-history.md#missing-and-refused-evidence).

## TypeScript current-format refusal

See the [current-format rules](../architecture/sources/planner-feed-history.md#raw-and-compact-copies).

## See also

- [Selection rules](../architecture/sources/feed-curation.md) - current selection behavior.
- [Feed history and reliability](../architecture/sources/planner-feed-history.md) - current native readers and represented-day rules.
- [Operator API](../architecture/sources/feed-operator-api.md) - current planner routes and contracts.
