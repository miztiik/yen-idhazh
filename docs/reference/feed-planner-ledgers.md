# Feed planner ledgers

**Last Updated**: 2026-10-30

Which planner data is retained, and where is it stored?

**Status**: Current five-ledger contract for the isolated TypeScript planner.
TypeScript owns planner settings, events, requests, private receipts, stage
payloads, ledgers and their file validation. Python keeps the gardener
scheduler, which delegates planner row validation and compaction to TypeScript.

**Scope**: Retained storage and audit contracts for the isolated planner.
These formats do not authorize production worker integration or prove
publication; see [planning completion](../architecture/sources/feed-ingest-audit.md#partial-results-and-boundaries).

**Five committed ledgers**, all under `state/raw/feed-ingest-plan/`:

- `discovered-articles`
- `selected-articles`
- `rejected-articles`
- `feed-health-state`
- `plan-runs`

`selected-articles` also has a GitHub Actions artifact representation containing
`article_text` for the summarizer. That artifact is not another ledger.
Committed selected rows never contain `article_text`.

Breaking format changes and removal of old planner-family raw and compact
ledgers are approved within the
[clean-break boundary](#approved-clean-break-delivery). New-family shared-ledger
storage support is in scope; the separate Python news pipeline remains
unchanged. This page defines the retained formats and their current readers
and writers.

Use section letters and field IDs when reviewing, for example "C20" or "B12-B14".
Keep IDs stable during iteration; do not reuse a removed field's ID.
Metadata is stored once per file, not repeated on every row. Every nested field
is listed below; there are no hidden policy or assessment payloads.

## Contents

- [A. discovered-articles](#a-discovered-articles)
- [B. selected-articles](#b-selected-articles)
- [C. feed-health-state](#c-feed-health-state)
- [D. plan-runs](#d-plan-runs)
- [M. rejected-articles](#m-rejected-articles)
- [E. Dates, counters and compaction](#e-dates-counters-and-compaction)
- [F. Screenshot ledger mapping](#f-screenshot-ledger-mapping)
- [G. Declared payload field mapping](#g-declared-payload-field-mapping)
- [H. Nested payload mapping](#h-nested-payload-mapping)
- [K. API inventory](#k-api-inventory)
- [L. Lookback summaries](#l-lookback-summaries)
- [TypeScript contract ownership](#typescript-contract-ownership)
- [Shared rules and removals](#shared-rules-and-removals)
- [Design rationale](#design-rationale)

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

No `feed_id` or `publisher_id`: the discovery reader does not
need them. Feed attribution belongs in health and selected output; publisher
identity belongs in selected metadata and the curated registry.

The planner reads the configured `discovered_articles.lookback_days` of prior
UTC days plus today. This setting belongs to the TypeScript planner; it does
not replace the native pipeline's separate `collect.seen_window_days`.

## B. selected-articles

**Committed metadata ledger plus artifact handoff.** Compute each selected
article once in memory, then serialize two representations:

- GitHub Actions artifact: selected metadata plus `article_text`.
- Committed Parquet: the declared metadata fields, without `article_text`.

Use an explicit allowlisted metadata projection with its own strict schema.
Do not mutate the shared object with `pop`, `delete` or another in-place removal:
that could remove the text before the artifact is produced. Do not maintain two
independently calculated selections.

### Table B - Selected article fields

| ID | Final field | Location | Committed? | Why |
| --- | --- | --- | --- | --- |
| B1 | `schema_version` | File metadata | Yes | Validate each representation's declared format |
| B2 | `run_id` | Artifact header / Parquet row | Yes | Link to `plan-runs`; preserve identity when compaction mixes runs |
| B3 | `url_key` | Article | Yes | Stable article identity |
| B4 | `feed_id` | Article | Yes | Identify the supplying feed |
| B5 | `publisher_id` | Article | Yes | Curated publisher identity used by selection; nullable |
| B6 | `canonical_url` | Article | Yes | Validated article URL |
| B7 | `title` | Article | Yes | Selected article metadata and summarizer input |
| B8 | `categories` | Article | Yes | Original feed category strings; empty arrays remain empty arrays |
| B9 | `article_text` | Artifact article | No | Sanitized summarizer input; never in committed Parquet or logs |
| B10 | `author` | Article | Yes | Attribution; nullable |
| B11 | `published_at` | Article | Yes | Trusted source publication or actual selection-start UTC instant; unknown source time does not make this null |
| B12 | `tier` | Article | Yes | Configured tier used for this choice |
| B13 | `weight` | Article | Yes | Configured feed weight actually used |
| B14 | `applied_tier_weight` | Article | Yes | Applied tier multiplier |
| B15 | `editorial_rank` | Article | Yes | Chosen order |
| B16 | `estimated_work` | Article | Yes | Work estimate used for bin packing |
| B17 | `worker_assignment` | Article | Yes | Zero-based partition assignment; null before partitioning |
| B18 | `ratings.base_article_score` | Article | Yes | Priority before selection adjustments, not an article-quality verdict |
| B19 | `ratings.marginal_score` | Article | Yes | Actual score when chosen |
| B20 | `ratings.adjustments[].term` | Article | Yes | Identify each evaluated adjustment |
| B21 | `ratings.adjustments[].value` | Article | Yes | Signed contribution; null means unavailable, zero means a known no-op |
| B22 | `ratings.recency_score` | Article | Yes | Actual recency contribution to the base score |
| B23 | `ratings.feed_authority_score` | Article | Yes | Actual weighted feed-authority contribution to the base score |
| B24 | `feed_limit` | Article | Yes | Per-feed share limit computed from the requested output count |
| B25 | `exploration_slot` | Article | Yes | Explain a choice made through the exploration allocation |
| B26 | `cap_relaxations` | Article | Yes | Record which configured caps were relaxed for this choice |
| B27 | `timing_at` | Article | Yes | Publication/first-sight instant actually used for age |
| B28 | `timing_basis` | Article | Yes | Explain the admitted age basis |
| B29 | `age_hours` | Article | Yes | Age actually evaluated, not age at artifact upload |
| B30 | `date` | Artifact header / Parquet row | Yes | Owning run's UTC accounting date, not publication date |
| B31 | `evaluated_at` | Artifact header / D19 | In D19 | Save the evaluation clock once in the run ledger; include it in the self-contained artifact |
| B32 | Removed | - | - | Fixed allowance bonuses no longer govern selection |
| B33 | `attempt` | Artifact header / Parquet row | Yes | Owning workflow/run attempt; not a selection-idempotency key |
| B34 | `published_at_source` | Article | Yes | `source` or `selection`; never infer provenance from the timestamp |
| B35 | `freshness_cutoff_at` | Article | Yes | Actual admitted window's UTC cutoff against the saved evaluation clock; null for unknown age |

The compact `adjustments` list replaces the large existing score-evidence tree.
It distinguishes unavailable evidence from a measured zero. It does not contain
copied configuration or empty classification trees. Fields B22-B29 and B32 were
included to explain real score components, quota/exploration decisions and age.
Every numerical adjustment still active must be represented. These values
explain the chosen result; they do not preserve every losing candidate or
promise a complete historical replay.

`evaluated_at` records the clock actually used. A saved parsed batch can retain
an earlier age-evaluation clock; the artifact must not substitute upload time
or a later API call's start time.

Only an entry-level, timezone-qualified source instant can supply publication
time. A feed's build or update date cannot date its articles. After admission
and choice, an absent or untrusted source date uses D22, the actual captured
selection-start UTC instant, with `published_at_source = selection`. The
spelling stays ISO 8601 with `Z`, as for source instants. This does not change
B27-B29, the original first sight, freshness eligibility, recency or ranking.
Unknown timing evidence stays in `timing_basis = unavailable`, `timing_at = null`
and `age_hours = null`. It does not create a fabricated historical publication
source or rewrite the selection-start fallback. The artifact and metadata
projection use the same chosen values.

The TypeScript planner reader accepts the current native ledger stamps:
`2026-10-29` for discovered and selected articles, `2026-10-26` for plan runs
and `2026-10-30` for feed health. Health retains compatible `2026-10-27`
files without rewriting their saved fractions. Discovery and selected history also retain
the exact earlier stamps listed in [article cleanup compatibility](#article-cleanup-compatibility).
Rejected articles use `2026-10-29T20:15`;
their exact `2026-10-27` and `2026-10-29` predecessors remain readable with null fetch-evidence
fields. It verifies the physical fields, file identity
and canonical digest, then parses every row with the matching current schema.
The selected and plan-run `2026-10-25` rows and the selected `2026-10-25`
artifact are obsolete and refuse explicitly; they are unchanged on disk and
receive no migration, null-fill or invented provenance.

Empty categories stay arrays. The native Parquet and JSON comparison found
that null increased both representations, so no nullable category shape is
introduced.

Use recency, curated tier/weight, the explicitly enabled measured article-pass
adjustment and applicable feed/publisher/domain selection controls. Do not
infer verticals, desks, lenses or article-quality verdicts here. Removing those
classification-based controls is part of the runtime cutover,
not merely a column rename.

Existing genuine publication inputs may still support an already-declared
publisher adjustment. If that linkage is unavailable, retain the existing
explicit current-run fallback; never manufacture publication counts from
selected counts. No publication-result columns are added to these ledgers.

## C. feed-health-state

**Committed ledger.** One finalized raw Parquet file per
run and UTC work day, batching all feed rows for that run/day. Rows describe
that run's work, not cumulative daily totals or a copied rolling snapshot.

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
| C8 | `permission` | Feed/run/day | Allowed, denied or unknown as observed for this work |
| C9 | `availability` | Feed/run/day | Availability/rest result observed for this run |
| C10 | `strikes` | Feed/run/day | Failure-streak result; nullable when unverified |
| C11 | `rested_runs` | Feed/run/day | Rest-progress result |
| C12 | `last_failure_code` | Feed/run/day | Explain the run's latest feed failure without free-text payloads |
| C13 | `status` | Feed/run/day | Actual feed HTTP status; nullable; not catalog membership |
| C14 | `reliability.productive` | Captured lookback | Productive reads in the measured lookback used for this run |
| C15 | `reliability.attempted` | Captured lookback | Evidence-bearing reads; excludes rest/robots skips |
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
| C30 | `robots_requests` | Run counters | Actual robots requests; cache reuse adds zero |
| C31 | `counts_complete` | Run counters | Flag incomplete accounting; unknown counts remain null |
| C32 | `rejection_counts[].reason_code` | Run counters | Aggregate rejection reason |
| C33 | `rejection_counts[].count` | Run counters | Number rejected for that grouped reason |
| C34 | `run_id` | Feed/run/day | Link to run settings and retain identity after compaction mixes runs |
| C35 | `rejection_counts[].subject` | Run counters | Distinguish feed failures from article exclusions |
| C36 | `rejection_counts[].stage` | Run counters | Preserve which stage made the decision |
| C37 | `rejection_counts[].attribution` | Run counters | Feed, pipeline or unknown for failures; null for ordinary exclusions |
| C38 | `attempt` | Feed/run/day | Retain the run attempt when compacted rows from different executions coexist |
| C39 | `items` | Feed/run/day | Existing distinct-offered-URL count used to decide whether the feed read was productive |
| C40 | `outcome` | Feed/run/day | Native download/permission result, not parse success; combined with C39 for reliability/rest settlement |

Retired field IDs: C3 moved to D16; C4 moved to D17; C17 moved to D21. These
settings belong once to the run, rather than repeated on every feed row or
assumed constant across compacted files. The API supplies
`reliability.window_days` from the linked D21 value.

Run counters are accumulated during that run only. Daily opportunity counts
sum those per-run decisions; they do not claim unique articles across the day.
Planning yield is calculated from selected/candidate counts. Request totals
measure spend, not blame.

`outcome` preserves the native download/permission result. An HTTP success
can therefore record `ok` even when the feed is empty or parsing fails.
`last_failure_code = FEED_PARSE_FAILED` identifies the latter; it does not
rewrite the download outcome. A human-facing feed read result combines that
outcome, the usable URL count and the failure code.

The current writer's productivity test remains `outcome == "ok"` and
`items > 0`; `ok` with zero items is a failed/nonproductive read.
Its `items` counts distinct offered canonical URLs across candidates and
article-level rejections. It is not automatically the raw XML-entry count,
extracted-article count or selected count. C39-C40 preserve that distinction
rather than silently changing the score when replacing the old health writer.

Captured reliability fields C14-C16 and C18-C21 describe the lookback evaluated
for this run. They are not additive counters. API daily views aggregate the relevant
run counters, never C14-C21. Storage copies must be deduplicated by the declared
execution/feed/day identity; genuinely repeated work is not erased merely
because another attempt happened. Feed reliability/rest still use their native
logical-read settlement and skip rules. Missing evidence remains unavailable,
not perfect reliability. Feed titles, configuration and retirement settings are
joined from the registry.

The global Python health ledger and `frontend/public/source-health.json` remain
unchanged. A future TypeScript health view must derive its operational data
from this ledger, not create another authority. Planning cannot supply
publication statistics.

No publication counts, publication-based retirement countdown, article text or
individual request history.

The seven-day request component is a spend report only, not a qualified waste
score or ranking penalty. Known HTTP costs remain attributed to the feed whose
work incurred them; missing accounting stays unknown. Detailed causal request
history and the former request-score qualification fields are not required.

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
| D18 | `reliability_penalty_enabled` | Run | Whether the known reliability factor was applied to priority |
| D19 | `evaluated_at` | Run | Actual captured age/scoring clock used by the selected batch |
| D20 | `request_report_closed_days` | Run | Actual closed-UTC-day window for the request-spend report; default seven |
| D21 | `reliability_window_days` | Run | Actual represented-day feed-reliability lookback; current default 30 |
| D22 | `selection_started_at_utc` | Run | Actual selection-start clock used to capture current feedback windows, distinct from a saved batch's older age clock |

For `/plan`, timing entries describe internal phases, not HTTP self-calls.
Record one span per major phase, not one span for every internal article
operation. Standalone APIs record their request-level spans. There are no
per-article trace trees.

The two health captures are intentional: one supplies pre-request evidence;
the other includes current work before selection. New rows store their
distinct purposes, not two position-dependent copies of one name. A reader
preserves an older `feed-health-summary` value and labels its purpose
unrecorded; list position cannot prove which capture it was.

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

The proposed physical write is one batched health Parquet per run per UTC work
day. A normal single-day run produces one file containing all its feed rows,
not one file per feed/request/article. A run crossing 00:00 UTC may need two
day files. Completed feed evidence must remain recordable when later article
work fails.

Example: one execution records `failed_reads = 1`, and another records
`failed_reads = 1` for the same feed/day. The daily view reports two failed
checks after removing duplicate storage representations. Neither execution
writes the cumulative two back as its own contribution.

Daily request-spend totals include real dispatched work from distinct
attempts, including failed attempts. Deduplicating raw/compact representations
must not discard that work. Logical lifecycle settlement and request-spend
accounting are different views of these records.

Compaction preserves the row identity and recorded values while packing files.
It does not calculate new scores, sum captured lookback totals, change their
evaluation clock or make missing data complete. This is not a proposal for a
new generic retry, replay or correction engine.

## F. Screenshot ledger mapping

The screenshot names eight ledgers; it does not display their columns. The
mapping below uses the actual declared row contracts behind those names.
Original identifiers are quoted only to identify the old data.

### Table F - All eight old ledgers

| ID | Old ledger | Relevant facts retained | Destination | Deliberately removed |
| --- | --- | --- | --- | --- |
| F1 | `article-assessments` | Chosen article identity, age evidence, actual score components; rejection reason totals | B, C | Per-article/per-stage historical assessments, diagnostic trees and model-verdict placeholders |
| F2 | `dispatches` | Selected metadata, order, work estimate and worker assignment; text in the artifact only | B; run-level strategy/count in D | Committed article text and duplicate nested candidate/selection copies |
| F3 | `diversity` | Underlying feed/category/selection facts where already needed | B, C, D | Historical diversity metric series; not an input the selector needs to read |
| F4 | `document-observations` | Request spend, feed failures, aggregate rejection causes; API/phase timings | C, D | Individual request/operation records, per-article timings, causal joins and correction chains |
| F5 | `editorial-selections` | Chosen rank, effective tier/weight, actual scores, quota/exploration exceptions | B | Separate old selection format, copied configuration and classification trees |
| F6 | `operational-state` | Relevant feed identity and reporting context only | C, D | Old qualified article-request-waste score and its revision/snapshot machinery |
| F7 | `rejections` | Counts grouped by feed, subject, stage, reason and known attribution | C | Permanent rejected-article identities, titles, URLs and diagnostic payloads |
| F8 | `source-runs` | Feed outcomes, selection counts, measured reliability; run summary and API timings | C, D | Repeated registry snapshots, publication/lead counts and completion proofs |

The not-yet-active snapshot/head design is also superseded by this proposal.
It is not a ninth screenshot ledger and is not retained beside the lean
health data.

## G. Declared payload field mapping

All 177 top-level payload fields from the eight screenshot row contracts are
accounted for below: 38 + 4 + 28 + 25 + 14 + 22 + 15 + 31.
Nested objects count once in that total; section H states what happens inside
them. Shared writer identity is reduced to the explicit date/run/attempt fields
in the main tables; other generic identity columns are not added.

### Table G - Complete top-level field disposition

| ID | Old ledger | Old declared fields | Destination or removal |
| --- | --- | --- | --- |
| G1 | `article-assessments` | `version` | File `schema_version`; no repeated row stamp |
| G2 | `article-assessments` | `date`, `correlation_id`, `observed_at` | Relevant UTC dates in B/C/D; correlation and per-assessment time history removed |
| G3 | `article-assessments` | `candidate_id`, `feed_id`, `source`, `canonical_url`, `url_key`, `categories` | Selected-only identity/configuration subset in B; A keeps first sight; transient candidate identity is not a new durable key |
| G4 | `article-assessments` | `labels` | Planner classification dossier removed; original RSS categories remain B8 |
| G5 | `article-assessments` | `stage`, `decision`, `reason` | Terminal rejection counts in C32-C37 and chosen order in B15; no per-stage article diary |
| G6 | `article-assessments` | `policy` | Runtime configuration; only declared run settings in D and actual applied values in B are retained |
| G7 | `article-assessments` | `timing_at`, `timing_basis`, `age_hours` | Selected-only age evidence B27-B29 |
| G8 | `article-assessments` | `max_age_hours`, `extracted_word_count`, `source_form`, `extraction_outcome`, `word_threshold`, `author_present`, `publisher_identity`, `attribution_status`, `paywall`, `required_fields_present`, `suitability_status` | Technical checks remain in execution; failures become C reason counts; author/publisher identity of selected articles remains in B; no permanent check-by-check record |
| G9 | `article-assessments` | `informative_verdict_status`, `informative_verdict`, `informative_evaluator_version`, `suitability_verdict_status`, `suitability_verdict`, `suitability_evaluator_version` | Removed: article-quality judgements are not this planner's task |
| G10 | `article-assessments` | `diagnostics`, `score_evidence`, `score_evidence_status` | Chosen scores in B18-B29; per-article diagnostics and duplicate availability wrappers removed |
| G11 | `dispatches` | `version` | B1 |
| G12 | `dispatches` | `content` | Lean selected content in B; detailed nested disposition in H |
| G13 | `dispatches` | `selection` | Lean selection evidence in B; no second copy of article/configuration |
| G14 | `dispatches` | `partition` | B17 worker assignment; D8-D9 strategy and worker count |
| G15 | `diversity` | `version`, `date`, `correlation_id`, `run_id`, `as_of` | Required run identity/date in D; metric-series identity and correlation copies removed |
| G16 | `diversity` | `metric`, `basis`, `window_start`, `window_end`, `dimension`, `stage`, `window_days`, `dimension_value`, `top_k` | Removed with historical diversity analysis; not repurposed as feed-reliability fields |
| G17 | `diversity` | `value`, `unit`, `before_value`, `after_value`, `numerator`, `denominator`, `item_count`, `source_count` | Historical metrics removed. B/C/D retain independently measured base counts, not renamed copies of these metrics |
| G18 | `diversity` | `history_coverage_days`, `history_required_days`, `algorithm_version`, `config_sha256`, `availability`, `unavailable_reason` | Old metric interpretation/proof removed; C21/C31 retain their own health/count completeness |
| G19 | `editorial-selections` | `version`, `date`, `correlation_id` | B1/B30 and D; correlation copy removed |
| G20 | `editorial-selections` | `candidate_id`, `feed_id`, `source`, `canonical_url`, `url_key` | B3-B6/B12-B14; candidate identity remains transient |
| G21 | `editorial-selections` | `vertical`, `labels` | Removed from the proposed planner output/classification scope; not disguised as RSS categories |
| G22 | `editorial-selections` | `editorial_rank`, `estimated_work` | B15-B16 |
| G23 | `editorial-selections` | `ratings`, `policy` | Reduced chosen-score evidence in B and declared run settings in D; full policy tree removed |
| G24 | `document-observations` | `version`, `correlation_id`, `observed_run_id`, `observed_attempt` | File schema plus C34/C38 and D2/D15; no per-operation correlation record |
| G25 | `document-observations` | `event_id`, `caused_by_event_id`, `corrects_event_id`, `correction_revision` | Removed with historical causal/correction accounting |
| G26 | `document-observations` | `feed_id`, `publisher_id`, `article_id`, `candidate_id` | Feed identity in C; selected article/publisher identity in B; no operation-level identity rows |
| G27 | `document-observations` | `document_kind`, `operation`, `outcome`, `attribution`, `failure_code`, `http_status`, `dispatched_request_count`, `request_coverage` | C28-C31 request totals/coverage, C12/C13/C40 feed outcomes, C32-C37 grouped causes; individual article HTTP outcomes are not retained |
| G28 | `document-observations` | `occurred_at`, `duration_ms`, `request_phase`, `request_sequence`, `retry` | C7 feed-check time and D API timings; request totals include actual retries/hops; individual operation clocks/order removed |
| G29 | `operational-state` | `version`, `date`, `written_at_utc`, `evidence_cutoff_utc`, `feed_id` | Relevant schema/run/feed context in C/D; old request-score cutoff removed with that score |
| G30 | `operational-state` | `state_revision`, `parent_revision`, `code_revision`, `policy_version` | Removed revision/reproduction machinery; no Git SHA |
| G31 | `operational-state` | `window_days`, `window_start`, `window_end`, `evidence_start_utc`, `evidence_end_utc` | Seven-day date-window concept retained for the spend report L3/D20, not the old score. D21/C18/C19 describe the separate native feed-reliability window |
| G32 | `operational-state` | `measured_target_requests`, `measured_source_wasted_requests`, `observed_attempted_opportunities`, `observed_measured_opportunities`, `measured_coverage`, `qualification_status`, `request_waste_ratio`, `operational_penalty` | Raw request spend remains C28-C30; causal waste, qualification and article-cost penalty deliberately removed, not reconstructed from totals |
| G33 | `rejections` | `version`, `date`, `correlation_id`, `rejected_at` | Schema and UTC accounting date retained at output grain; per-rejected-article clocks/correlation removed |
| G34 | `rejections` | `feed_id`, `feed_url`, `subject`, `stage`, `drop_reason` | C5/C32/C35/C36; feed URL comes from registry |
| G35 | `rejections` | `candidate_id`, `url_key`, `canonical_url`, `title`, `categories` | No permanent rejected-article record. A may retain the URL key for first sight; B keeps content only if selected |
| G36 | `rejections` | `details` | Known feed failure code/status and grouped reasons in C; detailed per-article failure payload removed |
| G37 | `source-runs` | `version`, `date`, `run_id`, `correlation_id`, `attempt` | Schema plus D2/D14/D15 and C22/C34/C38; correlation copy removed |
| G38 | `source-runs` | `feed_id`, `source`, `status` | Feed identity in C, selected applied configuration in B, registry membership remains configuration. Old catalog `status` is not C13's HTTP status |
| G39 | `source-runs` | `fetch_status`, `parse_status`, `last_failure_at`, `last_failure_reason` | C7/C12/C13/C32-C40 outcomes and grouped causes; no duplicated per-feed duration/diagnostic tree |
| G40 | `source-runs` | `parsed_count`, `harvested_count`, `fresh_count`, `duplicate_count`, `eligible_count`, `normalized_count`, `selected_count` | Relevant offered URLs C39, admitted candidates C26, selected C27 and rejected reasons C32-C37; exact old stage-population series removed |
| G41 | `source-runs` | `published_count`, `lead_count` | Removed: planning does not know downstream publication/lead results |
| G42 | `source-runs` | `drop_reasons` | C32/C33/C35-C37 grouped rejection counts |
| G43 | `source-runs` | `fetch_duration_ms`, `parse_duration_ms` | D11-D13 records actual API/phase spans; old per-feed spans are not falsely summed into parallel wall time |
| G44 | `source-runs` | `history_success_fraction`, `history_success_attempts`, `history_window_days` | C16/C15/D21 native reliability evidence |
| G45 | `source-runs` | `observation_phase`, `observed_at`, `expected_source_count`, `completion_evidence` | D run result and relevant check/evaluation clocks; per-feed completion-proof copies and publication-observer phase removed |

## H. Nested payload mapping

### Table H - No hidden retained payload trees

| ID | Old nested data | Retain or move | Deliberate loss |
| --- | --- | --- | --- |
| H1 | Candidate content identity, URL, title, categories, author and publication time | B3-B11; B9 is artifact-only | No committed article text; volatile offered-entry IDs/ordinals stay internal |
| H2 | Candidate `fetched_at`, `word_count` | Actual age basis B27-B31 and work estimate B16 where used | No duplicated fetch timestamp/word-count column merely to restate another value |
| H3 | Feed snapshot ID, publisher, tier, weight and applied tier weight | B4/B5/B12-B14; feed key C5 | Repeated title/feed URL/form/kind/status trees are not saved; live configuration remains authoritative |
| H4 | `labels` desk/lens/vertical/event/entity classification and origin fields | Not retained in the simplified planner scope; RSS strings remain B8 | Active classification-based rules are removed with that scope, not silently left without explanations |
| H5 | Policy version/hash, admission thresholds, recency/authority coefficients, tier budgets and concentration coefficients | Runtime configuration; actual contributions B18-B26/B35 and explicit run settings D16-D18 | No full historical policy replay or repeated per-article configuration snapshots |
| H6 | Score base and marginal values | B18/B19 plus explicit components B22/B23 | None for explaining the two totals |
| H7 | Numerical penalties and their availability | B20/B21; null remains unavailable, not a measured zero | Full nested operands/witness trees are not copied; this is not a promise of complete replay |
| H8 | Feed limit, exploration and relaxed caps | B24-B26 | No allowance bonuses or witness objects |
| H9 | Carrier outlets, representative and replacement references | Applicable duplicate handling can run in memory; B keeps the selected URL | No permanent competitor/carrier reconstruction; unused replacement scaffolding removed |
| H10 | Rejection details: HTTP/timeout/word/age bounds, matched URL/date/marker, failure code, history window and diagnostics | Checks remain in execution; C keeps grouped causes and feed-level code/status | No historical per-article diagnostic dossier |
| H11 | Fetch/extraction diagnostic trees, quality measurements and warnings | Sparse exceptional diagnostics outside ledger data; API duration in D | No routine copied article measurement trees |
| H12 | Headline matches, weighted lens, watchlist and salience observations | Not silently promoted into scores; any retained active effect must appear in B20/B21 or B32 | No copied classification/voting history or invented vote bonus |
| H13 | Completed-file IDs/digests/counts and logical completion commitments | Removed with the full-audit product | No claimed proof of historical complete-attempt reconstruction |
| H14 | Raw/compact file envelopes and indexes | Minimal declared storage metadata and native packing still required | They are not a reason to add every old generic identity field to the new payload |

## K. API inventory

These are local operator services, not a backend for the published site.
The route registrations implement 14 HTTP operations across three local
services. The selected persistence operation replaces the old route; there is
no permanent compatibility API.

### Table K - HTTP operations

| ID | Service | Method and full path | Current role |
| --- | --- | --- | --- |
| K1 | Feed planner | `GET /api/2026-10-20/health` | Implemented: listener/enablement check only, not a feed-reliability query |
| K2 | Feed planner | `POST /api/2026-10-20/plan` | Runs the shared stages and finalizes the five ledgers and selected text artifact |
| K3 | Feed planner | `POST /api/2026-10-20/fetch` | Implemented fetch for either a configured feed or an explicitly permitted article |
| K4 | Feed planner | `POST /api/2026-10-20/parse` | Parses one saved feed or article without network calls; feed parsing returns body-free offers and a server-owned batch |
| K5 | Feed planner | `POST /api/2026-10-20/select-articles` | Implemented combined admission/ranking; no selection-idempotency requirement or input-count cap |
| K6 | Feed planner | `POST /api/2026-10-20/partition-articles` | Implemented worker assignment/bin packing; does not reselect |
| K7 | Feed planner | `POST /api/2026-10-20/persist-selected-articles` | Writes B without text and produces its text-bearing artifact; the removed persistence route returns ordinary HTTP 404 |
| K8 | Feed planner | `POST /api/2026-10-20/feed-health-state` | Explicit `summarize` or `record` for a server-owned batch; returns C, request spend, the reliability window and actual write receipts when recorded |
| K9 | Host fingerprints | `GET /api/2026-10-20/health` | Implemented separate service health check |
| K10 | Host fingerprints | `POST /api/2026-10-20/fingerprint` | Implemented optional machine collection/persistence; not mandatory planner evidence |
| K11 | Host probes | `GET /api/2026-10-20/sample` | Implemented standalone machine CPU/RAM sample |
| K12 | Host probes | `POST /api/2026-10-24/start-task-profile` | Implemented optional explicitly pinned process profiling |
| K13 | Host probes | `POST /api/2026-10-24/stop-task-profile` | Implemented stop/readback for that profile |
| K14 | Host probes | `POST /api/2026-10-24/cache/latency` | Implemented optional owned cache benchmark; not planner article timing |
| K15 | Feed planner | `POST /api/2026-10-20/collections` | Starts one run-owned collection and captures eligible feeds, run identity and policy |
| K16 | Feed planner | `POST /api/2026-10-20/collections/complete` | Requires terminal feed/article work, saves discovery and harvested rejections, and returns the complete global batch |
| K17 | Feed planner | `POST /api/2026-10-20/collections/cancel` | Cancels owned work, blocks partial-input selection, and returns rejection receipts and a partial-health batch reference |

The two health paths belong to different service listeners. The standalone RAM
HTTP proof uses K11; it is not another RAM API. The ledger writer is a library
and CLI, not an additional HTTP service. No `GET /feeds` or read-only
`GET /feed-health-state` route currently exists.

K3 uses `feed_id`, not an old `source_id` alias. Article work can reference a
server-owned `batch_id` and `offer_id`; an explicit operator URL remains a
separate permitted control. K5 waits until every offer is terminal. K8 checks
the default-off service flag before reading a batch or private SQLite store.

## L. Lookback summaries

The shared TypeScript health operation reads native planner rows and supplies
K8 and selection. It is not K1's listener health response.

### Table L - Independent windows

| ID | Component | Current default and unit | Retained meaning |
| --- | --- | --- | --- |
| L1 | Lifecycle/rest | `feedback.lifecycle_window_days = 31` represented UTC days | Use the newest named represented days, not 31 fabricated consecutive dates; preserve endpoint and native rest ordering |
| L2 | Feed-read reliability | `collect.reliability_window_days = 30` represented days; `collect.reliability_floor = 0.5` | Productive / evidence-bearing feed reads, with the configured floor; keep the existing feed metric and expose incomplete evidence |
| L3 | Request-spend report | `feedback.request_report_closed_days = 7` closed UTC calendar days | Sum observed feed/article/robots request spend, not a waste score or ranking penalty |

**Confirmed decision:** Retain the seven-day component as a feed request-spend
report only. Remove the qualified causal request-waste score. Its
measured-opportunity qualification and normalized CPU/memory/request weights
are not reused for this report. This does not silently enable a feed-reliability
fallback when request data is unavailable.

All three windows use UTC. The 31-day lifecycle and seven-day request windows
are not interchangeable reliability windows. The 30-day feed-read window
already exists in current configuration. The cutover keeps those meanings
rather than changing 30 to 31 or using the seven-day request window for
feed-read scoring.

Represented membership follows native coverage. A daily entry contributes its
day only when it has rows. A nonempty monthly or yearly entry contributes
every calendar day in that declared cover, including a covered day with no
feed row. This is named evidence, not padding outside the inventory.
Covered membership never invents a feed check or request; denominators and
counters still come only from actual rows. Known-empty daily entries are not
lifecycle or reliability members. Missing, refused or lost evidence stays
explicitly incomplete.

The shared operation:

1. Capture the trusted selection/feedback clock once in D22. Ordinary age
   evaluation may retain the earlier parsed-batch clock in D19.
2. Resolve only named raw/compact inputs for the configured window inventory.
   The same bounded read can serve L1 and L2. No repository/history scan or
   copied snapshot of every input is introduced.
3. Validate and settle run/feed/endpoint records using their declared identities.
   Raw/compact overlap is one representation of the same fact; distinct actual
   work remains visible. Missing/corrupt input is a gap, not a zero.
4. Calculate feed reliability from the actual per-run outcome/items evidence.
   Exclude rest/robots skips, retain productive and attempted denominators, and
   return the window bounds, completeness and production factor. Saved
   per-run reliability results are captured results, never inputs to another
   summation.
5. Calculate the L3 report over the seven closed UTC days ending yesterday,
   relative to D22. Sum C28-C30 and return report bounds and completeness.
   Unknown request coverage is exposed; do not infer waste, blame or zero cost.
6. Record the run's own health counters in C. Do not copy cumulative seven- or
   31-day request totals into each new run's counter fields. K8 returns the
   body-free summary; it does not create another summary ledger or JSON authority.

`/plan` calls the shared TypeScript reader before selection, then the shared
recording/update operation after selection while partitioning can proceed.
These are real HTTP requests to stage APIs on the same trusted local listener,
not direct calls into stage execution modules. They do not imply process isolation
or an external message broker. Standalone
`/select-articles` does not acquire an implicit update side effect; K8 remains
an explicit operator operation.

Each capture shares its named-index and Parquet reads in memory. Pre-fetch
health governs rest before requests start. Selection refreshes health at D22
after the complete input arrives, so a saved parsed batch does not freeze
feedback or window membership. D11-D13 include the measured cost of both
captures. There is no per-candidate history read or persistent result cache.

## M. rejected-articles

Explicit selection persistence writes one row for each parsed candidate not
selected, including runs with zero selected articles. Run finalization also
retains completed terminal article-fetch and extraction failures. Standalone
fetch and parse operations save those failures when their stage completes;
the private fetch receipt is not their sole store.
This ledger has no title, body, policy or score
tree and no explorer consent.
Without explorer consent, its files are not staged in the site and it has no
published-payload ceiling in `config/idhazh.json`.

### Table M - Rejected article fields

| Id | Field | Meaning |
| --- | --- | --- |
| M1 | `schema_version` | File metadata declaring the current row format |
| M2 | `run_id`, `attempt`, `date` | Execution identity and its UTC accounting day |
| M3 | `candidate_id` | Original offered or parsed candidate identity; null only for a harvest failure without one |
| M4 | `url_key`, `feed_id` | Canonical URL hash and supplying feed |
| M5 | `stage`, `reason_code` | Terminal harvest failure or final screening/curation refusal; retained rows accept bounded historical reason strings |
| M6 | `freshness_cutoff_at` | Applied UTC age cutoff, or null when no cutoff was applied |
| M7 | `http_status` | Actual article response status, or null if not observed; never the robots response |
| M8 | `fetch_failure` | Typed terminal download failure, or null when no fetch failure was observed |
| M9 | `error_code` | Validated low-level transport code, or null if not observed |
| M10 | `robots` | Observed `allowed`, `denied` or `unknown` permission, or null before observation |
| M11 | `robots_http_status` | Actual robots response status, or null if not observed |
| M12 | `robots_failure` | Typed robots download failure, or null if not observed |

Row identity is run, attempt and candidate. Selected cutoffs use their admitted
window. Age refusals use the failed threshold. An unopened older step is not
an applied cutoff. Harvest rows require an actual offered URL identity, not a
replacement for a malformed or absent address. Retries produce one terminal
row per candidate and run, not one row per attempt; a recovered fetch produces
no stale failure row. Run finalization retains completed failures if selection,
partitioning or selected-output persistence later fails; see the
[write timing and process-loss limit](../architecture/sources/feed-harvesting.md#work-facts-and-failures).
Feed-health counters
remain grouped and never count these detail rows again.
Repeated writes of an identical raw rejection batch use the same physical
file identity and verify that existing file before reusing it. Other planner
ledgers keep their existing file identities.

The reader checks the physical Arrow schema and original digest against the
file's exact accepted version before filling the six absent evidence fields
with null. Old files are not rewritten. Compaction accepts old and current
members together and writes the current format. Unknown versions still refuse.
Known current reasons keep their stage checks; unknown or
retired reason strings remain readable evidence when they follow the bounded
uppercase reason-code pattern.

## TypeScript contract ownership

The Zod schemas under `packages/common-contracts/src/schemas/` are the sole
contract authority for planner configuration, events, requests, private
receipts, stage payloads and the five planner ledgers. The TypeScript writer
validates and writes planner Parquet and artifacts. Python has no planner row,
stage or configuration model and no cross-language comparison copy. Native
Python ledger readers refuse planner rows; the published-file check delegates
their validation to TypeScript.

The Python gardener remains the scheduler for every ledger family. Its shared
compact-index records are maintenance marks, not planner row contracts. For
planner data, the gardener hands one named bounded period to the TypeScript
adapter, which validates exact raw and compact Parquet members at one captured
Git revision and returns verified bytes and exact source paths. Python applies
that result through its existing pass and commit flow.

Planner contracts still carry current schema stamps and changelogs. The
version checks have no Python copy. Rejected-article compatibility and
[article cleanup compatibility](#article-cleanup-compatibility) belong to
the native TypeScript reader. The TypeScript tests and the real
gardener-adapter integration test own this boundary. Health consumers use the separate
[field-read contract](#field-based-health-history) rather than full-row compliance.

## Raw-day membership

The five planner ledgers have no active raw-day `index.json` reader or writer.
Their data remains in immutable UUID Parquet siblings under
`state/raw/feed-ingest-plan/<ledger>/YYYY/MM/DD/`. Historical derived JSON lists
are left inert; this change does not scan or rewrite the corpus. TypeScript
planner history also does not read compact-index JSON: it checks exact
yearly, monthly and daily Parquet paths in precedence order. The gardener's
shared compact indexes remain its scheduling marks and are not planner row
contracts. Other ledger families keep their own history readers.

Configuration names a finite UTC lookback or explicit bounded UTC days.
The workflow captures one full Git commit id before staging. For each requested
registered day it checks that exact path with `git ls-tree <revision> -- <day>`
and lists only that directory with `git ls-tree -l <revision>:<day>`.
A successful absent-path result proves no committed members at that revision;
a failed Git read does not prove absence. A directory may contain zero or many
regular UUID Parquet files. An old regular `index.json` is ignored, not parsed.
Other filenames, nonregular members and wrong registered roots are refused.
There is no state-root walk, replacement saved catalog or run discovery.

The existing named-day input carries `day`, optional compact `indexes`,
`raw_files` and `raw_revision`. Repository staging supplies the full member
set and its captured revision, not a partial hand-picked subset. A supplied
set must equal the Git listing; missing, additional or repeated members make
the read incomplete. Authored planner configuration rejects `raw_index` and
requires `raw_revision` with `raw_files`; an unproved subset is not a valid
configuration. After sparse checkout, each file must match its Git blob
and size at that same revision, then pass the existing Parquet footer, schema,
canonical content digest, filename, ledger and UTC-day checks. Missing files,
failed listings and refused bytes remain explicit history gaps, never empty
successful history. A supplied `raw_revision` pins history reads to that
commit; a shared reader capture refuses a second revision. Repository staging
captures current `HEAD` and rejects supplied revisions that differ, so staged
output cannot mix commits.

Direct current-invocation input still uses `raw_files` without `raw_revision`:
the caller supplies all exact completed paths from the existing writer result.
It is a trusted complete result, not a way to discover archived repository
history or to assert completeness for an arbitrary subset. Native identity
and content checks still run. No new persisted manifest is introduced.

Yearly, monthly and daily compact precedence is unchanged. Planner raw
siblings still join the selected compact representation so newly appended
work is not hidden by an earlier packed period. Source windows and health
represented-day membership keep their existing meanings. Publication accepts
only exact completed immutable paths and independently registered permissions;
reading a day grants no permission to publish it. The publisher builds a
private candidate on fresh main, refuses byte collisions and retries normal
pushes without rerunning producers or changing the caller's checkout.

## Shared rules and removals

- No article text in committed ledgers, committed repository files or normal-run logs.
- Counts and durations use integers. Genuine two-state facts use booleans.
  Ratios and weights remain numeric. Unknown is not zero or false.
- Schema versions are date stamps stored once per file.
- Ledger identity is known from its registered output, not a repeated `ledger`
  column. `date`, `run_id` and `attempt` are retained where required by the
  explicit main tables, not injected as a generic identity tree.
- No Git SHA, `unit_id`, revision chains, duplicate head files or hidden generic
  writer identity columns in these formats.
- Replace the old assessment, rejection, diversity, editorial-selection,
  dispatch, operation-history and operational-score formats with the four
  declared ledgers. Keep selected metadata in B, not separate duplicate
  `editorial-selections` and `dispatches` ledgers.
- Remove full event exports, archived intermediate batches, copied policy trees
  and planner classifications.
- Keep technical admission, safety, freshness, selection and partitioning.
  Article quality is not judged here.
- DNS, pinned-address, redirect, robots and sanitization checks remain. Reduced
  permission history does not authorize a fetch or weaken those checks.
- Actual existing published/item outcomes remain external exclusion inputs.
  They are not written or inferred by planning.
- Ordinary planning does not require machine fingerprints or CPU/RAM/cache/copy
  proofs. Their independent tools in K remain available.
- Existing rest fields do not claim completion of the
  [deferred controls](../architecture/contracts/feed-ingest-feedback.md#deferred-controls).
  No unused future-policy columns
  are preallocated, and those policy tasks are not silently cancelled.
- The separate Python news pipeline remains unchanged. Planner persistence,
  row readers and compaction use TypeScript contracts; the Python gardener
  retains scheduling and shared maintenance indexes.

## Design rationale

### Keep the field review together

The field lists, old-to-new mappings, API inventory and window definitions
answer one question: which planner data is retained and where. They remain
together so each retained field can be reviewed against its old source and
consumer without losing the stable review IDs. Current behavior belongs in
the linked subsystem pages, not a second execution narrative.

### Approved clean-break delivery

**User approval, 2026-10-25 UTC:** Replace the old planner formats in their
actual code paths. No old-to-new migrators, compatibility readers, aliases or
dual writers are required or permitted for this replacement. The old-to-new
tables above explain field disposition; they are not migration instructions.

### TypeScript current-format refusal

**Breaking cutover approval, 2026-10-26 UTC:** The TypeScript planner native
reader and selected-artifact reader accept only their current ledger stamps.
The selected and plan-run row stamps and selected artifact stamp are
`2026-10-26`; the discovered and feed-health stamps remain `2026-10-25`.
Obsolete selected and plan-run `2026-10-25` rows refuse with a contract
diagnostic. Obsolete selected artifacts refuse instead of adding a historical
provenance default. Missing age evidence remains null; a real current-run
selection instant remains selection provenance.

This is the maintainer-approved TypeScript exception to the read-side migration
rule in `CLAUDE.md` section 11. Python's historical planner row readers and
contract copies are retired. The gardener registry and scheduler remain; the
published-file validator and compact writer use the current TypeScript
contracts.

The shared TypeScript ledger reader has no migration table. Strict full-row
validation accepts only the contract's declared row stamps. The separate health
field reader accepts the columns it needs without using their row schema date
as an acceptance gate. Article cleanup has its own named compatible stamps below.

### Field-based health history

**User-directed ruling, 2026-10-29 UTC:** A row schema date identifies a format;
it does not prove that a consumer's required fields are missing or invalid.
Health history reads accept compatible required fields from older and newer
row stamps. Writers, compaction and full-file publication validation still
require their full declared row schema. No stored history is rewritten.

The shared writer package exports `readStoredPlannerParquet` for stored-file
validation and retains `readPlannerParquet` for strict full-row validation.
Both verify the registered ledger, supported file envelope, raw filename,
and whole-file canonical digest. Stored-file validation computes that digest
from the actual Arrow columns, including nested and unrelated columns, not
from the consumer's projection. A changed unrelated cell still fails integrity.
An unsupported stored physical type fails explicitly rather than skipping
part of the digest.

`readFeedHealthFieldsDay` in the planner service reads one named UTC day through
the same raw/compact membership, captured Git revision and file-byte checks.
It returns independent `uses`: `request_totals`, `feed_rest`,
`feed_reliability` and `article_admission`. Their schemas are declared once in
`packages/common-contracts/src/schemas/feed-health-fields.schema.ts`:

- Every use requires `date`, `run_id`, `attempt`, `feed_id` and `endpoint_key`.
- Request totals require `feed_requests`, `article_requests` and `robots_requests`.
- Rest and feed-read reliability each require `checked_at`, `outcome` and `items`.
  Their observation time must agree with the UTC work day.
- Article admission requires `article_candidates`, `counts_complete` and the
  rejection reason, count, subject and attribution fields.

Each use returns validated `rows`, `partial_rows` containing only individually
valid fields from rejected rows, and `gaps` naming the use, field, UTC day,
missing/invalid reason and row identity when known. A row with invalid identity
is never exposed as partial attributable evidence. Null remains null, and
missing or invalid counters are omitted from partial rows, never replaced with
zero. This lets a later request report account for each counter independently.
File coverage (`complete`, `represented`, file `gaps`) is separate from field
coverage: `complete` alone never proves every required counter is known.

Identical copies of a fact count once. Conflicting copies fail before any
projection, including conflicts in fields a use does not read. The identity
includes the endpoint and run attempt, so neither changed endpoints nor real
repeated work collapse into another fact. Missing request columns do not remove
valid feed-check evidence. No rest, reliability or article selection policy is
changed by this read contract. Production planning, standalone document work,
selection and health summaries use these field projections. Strict full-row
validation remains on the write and maintenance paths.

`readFeedHistory` returns rest, feed-read reliability and article-admission
inputs from the named represented-day inventory. `preparePlanningHealth`
supplies those inputs before both combined and standalone fetch work. Neither
path adds closed request-report days or calculates historical request totals.
Current-run request recording is unchanged.

`readRequestHistory` reads only the configured closed calendar days and returns
validated request rows, partial request rows, field gaps and file coverage.
`prepareRequestReport` is its request-only reporting entry point.
Selection and explicit health summaries combine planning evidence with that
report through `prepareFeedHealthState`; their shared capture cache keeps one
stored file read and Git revision per capture.

The request report adds each usable feed, article and robots counter
independently, including individually valid fields from partial rows.
Absent, invalid and null counters remain unknown; a known zero is retained.
For each feed and counter, `coverage` declares `status` (`complete`, `partial`
or `none`), `known_records`, `unknown_records`, `recorded_days` and
`complete_days`. Recorded days have at least one usable counter. Complete days
have complete file evidence and no unknown matching counter or unattributable
record. Known-empty complete windows produce zero; incomplete windows without
any usable counter produce null, not an estimated zero.

`missing_days` names missing or incomplete day files. `unattributed_days`
names days with invalid row identities that cannot be assigned to a feed.
`input_complete` preserves the staged-input gap flag; when false, no day can
be claimed complete, but known counters remain usable. Unknown-record counts
cover attributable rows only; missing files and unattributable rows are
reported separately, never presented as a count of lost records. Each
counter is complete only when all configured closed days are complete.
Feed and report completeness require every counter to be complete.

The report schema and selected/partitioned stage payloads are stamped
`2026-10-29`. Current stage readers refuse earlier formats under the
TypeScript planner compatibility rule; no historical ledger is rewritten.
The [operator report guide](../how-to/run-feed-ingest-plan-test.md) defines
the partial-total marker and report-only ordering.

Before projection, stored and finalized in-memory facts from the current run
and attempt are excluded. Supplied current work then replaces that execution.
Endpoint matching and productive logical-read settlement remain unchanged.
A required-field gap affects only its use and matching endpoint, or all feeds
when identity is invalid. Rest requires complete evidence; article admission
is unknown if any required evidence is missing. Incomplete feed-read ratios
remain labelled incomplete and are not substituted for the article-admission
rate used by selection.

### Article cleanup compatibility

**User approval, 2026-10-29 UTC:** Article identity and initial request cleanup
now share a policy that removes every article query string and fragment.
Discovery rows, selected rows/artifacts, candidate and stage payloads, and private
fetch receipts written with this policy use `2026-10-29` stamps. Feed identity
and Python discovery do not change.

The native reader accepts exact compatible discovery `2026-10-25` and selected
`2026-10-27` rows/artifacts. Private fetched documents and operation journals also
accept `2026-10-28`. Old row and receipt stamps remain unchanged on read; a
compacted container can use its current stamp without relabeling historical rows.
Earlier incompatible stamps still refuse. Existing published records and joins
retain their original keys.

Parsed feed batches written with `2026-10-29` remain readable because the new
`body_limit` diagnostic is nullable and defaults to `null`. New batches use
`2026-10-30`; reading an older batch preserves its original stamp.

Saved fetch responses remain replayable with their original identity. An old
article fetch receipt cannot be parsed into a current-policy candidate; fetch
the article again. There is no migration table, dual writer or permanent alias
ledger.

Targeted deletion of the same eight obsolete ledger prefixes named in Table F
under both `state/raw/feed-ingest-plan/` and
`state/compact/feed-ingest-plan/` is permitted, including their compact files
and indexes. It does not authorize deletion of either broader root, other
families, the global Python `feed-health` data or the historical corpus, a
Python news-pipeline rewrite, or a Git history rewrite.

Registration alone cannot make the native file reader and compactor accept
the declared minimal metadata. Include new-family native file-format,
readback, settlement and daily/monthly/yearly packing support, plus the
TypeScript Parquet reader. Do not restore `unit_id` or hidden generic identity
fields to fit the existing infrastructure. Keep every other family's current
protocol unchanged, and remove dead old-family native models and exports with
their replacement. These are shared-ledger storage changes, not changes to
Python news fetching, selection, summarization or publication.

The runtime cutover uses typed events and asynchronous, bounded concurrent
work. Independent requests and work may overlap; each fetch must precede its
parse, selection waits for its complete eligible input, and partitioning waits
for selection. Health recording and reporting may overlap partitioning after
selection. Do not serialize all runs through one global queue. Existing fetch
safety checks and the artifact-only article-text boundary remain unchanged.

### Share each bounded health capture

The pre-fetch decision and fresh selection feedback answer different questions
at different instants. A run needs both when work or external evidence changes
between them. Pre-fetch captures derive planning evidence only; selection and
explicit summaries also derive the request report. Each capture shares bounded
file reads among its consumers. The run records
the full measured health-summary cost through D11-D13, not only its last
refresh. This is a measured operation cost, not a claim of a speed improvement.

Captured reliability in C records what selection used. It is not a result cache
proved fresh for another request. No fifth summary ledger, separate summary
service, new API or profiler gate is needed.

Consider an incremental persisted cache only if representative runner evidence
changes that recommendation. First consider keeping any justified cache in
the existing health data family rather than adding a ledger or API. Do not
build cursor, fingerprint, revision or head machinery before that evidence
shows a need.

## See also

- [I Feed scope](../architecture/sources/i-feed.md#continuing-this-work) - deferred policy, worker, Python and console work.
- [Selection rules](../architecture/sources/feed-curation.md) - current selection behavior.
- [Feed history and reliability](../architecture/sources/planner-feed-history.md) - current native readers and represented-day rules.
- [Operator API](../architecture/sources/feed-operator-api.md) - current planner routes and contracts.
- [Host probe API](host-probe-api.md) - independent optional host operations.
