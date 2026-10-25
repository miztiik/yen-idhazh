# Feed planner ledgers

**Last Updated**: 2026-10-25

Which planner data is retained, and where is it stored?

**Status**: Working proposal for the
[Plan 67 simplification review](../../TODO/20261024-67-feed-ingest-feedback-and-selection-plan.md),
with an approved clean-break delivery direction, not an implemented contract.
Fields and runtime recommendations remain under review except for the explicit
confirmed decisions below. Delivery is authorized after the minimal four-ledger
contracts and storage are delivered. The superseded compatibility and state
branches remain paused; saving this proposal implements no schema or runtime
change.

**Scope**: Simplify the storage and audit portions of
[Plan 66](../../TODO/20261020-66-feed-ingest-plan.md) and
[Plan 67](../../TODO/20261024-67-feed-ingest-feedback-and-selection-plan.md).

**Four committed ledgers**, all under `state/raw/feed-ingest-plan/`:

- `discovered-articles`
- `selected-articles`
- `feed-health-state`
- `plan-runs`

`selected-articles` also has a GitHub Actions artifact representation containing
`article_text` for the summarizer. That artifact is not a fifth ledger.
Committed selected rows never contain `article_text`.

Breaking format changes and removal of old planner-family raw ledgers are
approved within the [clean-break boundary](#approved-clean-break-delivery).
Python remains unchanged. This page describes the proposed design, not
implemented behavior.

Use section letters and field IDs when reviewing, for example "C20" or "B12-B14".
Keep IDs stable during iteration; do not reuse a removed field's ID.
Metadata is stored once per file, not repeated on every row. Every nested field
is listed below; there are no hidden policy or assessment payloads.

## Contents

- [A. discovered-articles](#a-discovered-articles)
- [B. selected-articles](#b-selected-articles)
- [C. feed-health-state](#c-feed-health-state)
- [D. plan-runs](#d-plan-runs)
- [E. Dates, counters and compaction](#e-dates-counters-and-compaction)
- [F. Screenshot ledger mapping](#f-screenshot-ledger-mapping)
- [G. Declared payload field mapping](#g-declared-payload-field-mapping)
- [H. Nested payload mapping](#h-nested-payload-mapping)
- [K. API inventory](#k-api-inventory)
- [L. Lookback summaries](#l-lookback-summaries)
- [Shared rules and removals](#shared-rules-and-removals)
- [Design rationale](#design-rationale)

## A. discovered-articles

**Committed ledger.** Records first sight globally across feeds, including
articles never selected.

### Table A - Discovery fields

| ID | Final field | Location | Why |
| --- | --- | --- | --- |
| A1 | `schema_version` | Metadata | Identify the declared format |
| A2 | `url_key` | Row | Stable hash of the canonical URL |
| A3 | `first_seen_at` | Row | Establish age for undated articles; never reset on rediscovery |
| A4 | `date` | Row | UTC date of first discovery; explicit day-partition/query key |

No `feed_id` or `publisher_id` in this proposal: the first-sight reader does not
need them. Feed attribution belongs in health and selected output; publisher
identity belongs in selected metadata and the curated registry.

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
| B8 | `categories` | Article | Yes | Original RSS category strings, not inferred classifications |
| B9 | `article_text` | Artifact article | No | Sanitized summarizer input; never in committed Parquet or logs |
| B10 | `author` | Article | Yes | Attribution; nullable |
| B11 | `published_at` | Article | Yes | Actual publication time; nullable |
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
| B24 | `feed_allowance` | Article | Yes | Effective feed allowance used before portfolio selection |
| B25 | `exploration_slot` | Article | Yes | Explain a choice made through the exploration allocation |
| B26 | `cap_relaxations` | Article | Yes | Record which configured caps were relaxed for this choice |
| B27 | `timing_at` | Article | Yes | Publication/first-sight instant actually used for age |
| B28 | `timing_basis` | Article | Yes | Explain the admitted age basis |
| B29 | `age_hours` | Article | Yes | Age actually evaluated, not age at artifact upload |
| B30 | `date` | Artifact header / Parquet row | Yes | Owning run's UTC accounting date, not publication date |
| B31 | `evaluated_at` | Artifact header / D19 | In D19 | Save the evaluation clock once in the run ledger; include it in the self-contained artifact |
| B32 | `allowance_reasons` | Article | Yes | Compact codes for allowance bonuses actually used; no copied witness trees |
| B33 | `attempt` | Artifact header / Parquet row | Yes | Owning workflow/run attempt; not a selection-idempotency key |

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

Use recency, curated tier/weight, the explicitly enabled measured feed-reliability
adjustment and applicable feed/publisher/domain selection controls. Do not
infer verticals, desks, lenses or article-quality verdicts here. Removing those
classification-based controls is part of this proposed runtime simplification,
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
| C16 | `reliability.success_fraction` | Captured lookback | Measured productive fraction |
| C18 | `reliability.from_day` | Captured lookback | Beginning of the represented evidence window |
| C19 | `reliability.through_day` | Captured lookback | End of that window |
| C20 | `reliability.production_factor` | Captured lookback | Saved factor after applying the run's floor |
| C21 | `reliability.complete` | Captured lookback | Distinguish complete lookback coverage from partial history |
| C22 | `date` | Feed/run/day | UTC day of the work being counted |
| C23 | `feed_reads` | Run counters | Logical feed checks represented by this row, not retry requests |
| C24 | `productive_reads` | Run counters | Productive checks under the existing outcome/items rule |
| C25 | `failed_reads` | Run counters | Failed feed checks represented by this row |
| C26 | `article_candidates` | Run counters | Article opportunities reaching selection in this run/day |
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
| C40 | `outcome` | Feed/run/day | Existing feed outcome, including skipped/blocked/failed cases; needed for reliability/rest settlement |

Retired field IDs: C3 moved to D16; C4 moved to D17; C17 moved to D21. These
settings belong once to the run, rather than repeated on every feed row or
assumed constant across compacted files. The API supplies
`reliability.window_days` from the linked D21 value.

Run counters are accumulated during that run only. Daily opportunity counts
sum those per-run decisions; they do not claim unique articles across the day.
Planning yield is calculated from selected/candidate counts. Request totals
measure spend, not blame.

The current writer's productivity test is `outcome == "ok"` and `items > 0`.
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

The TypeScript replacement for `frontend/public/source-health.json` gets its
operational data from this ledger. Any generated public JSON is a view, not
another authority. Planning cannot supply publication statistics.

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
| D4 | `duration_ms` | Run | Total elapsed time; no redundant end timestamp |
| D5 | `status` | Run | Completed, partial or failed |
| D6 | `failure_code` | Run | Explain a run-level failure; nullable |
| D7 | `selected_count` | Run | Explicit result, including zero; a missing selected file is not an empty result |
| D8 | `strategy` | Run | Actual partition strategy |
| D9 | `dispatch_count` | Run | Number of worker partitions |
| D10 | `selected_articles_artifact` | Run | Artifact reference only, not its content or a signed URL |
| D11 | `api_timings[].operation` | Timing entry | Actual fetch, parse, select, partition, persist or feed-health-summary operation |
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
| G3 | `article-assessments` | `candidate_id`, `source_id`, `source`, `canonical_url`, `url_key`, `categories` | Selected-only identity/configuration subset in B; A keeps first sight; transient candidate identity is not a new durable key |
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
| G20 | `editorial-selections` | `candidate_id`, `source_id`, `source`, `canonical_url`, `url_key` | B3-B6/B12-B14; candidate identity remains transient |
| G21 | `editorial-selections` | `vertical`, `labels` | Removed from the proposed planner output/classification scope; not disguised as RSS categories |
| G22 | `editorial-selections` | `editorial_rank`, `estimated_work` | B15-B16 |
| G23 | `editorial-selections` | `ratings`, `policy` | Reduced chosen-score evidence in B and declared run settings in D; full policy tree removed |
| G24 | `document-observations` | `version`, `correlation_id`, `observed_run_id`, `observed_attempt` | File schema plus C34/C38 and D2/D15; no per-operation correlation record |
| G25 | `document-observations` | `event_id`, `caused_by_event_id`, `corrects_event_id`, `correction_revision` | Removed with historical causal/correction accounting |
| G26 | `document-observations` | `source_id`, `publisher_id`, `article_id`, `candidate_id` | Feed identity in C; selected article/publisher identity in B; no operation-level identity rows |
| G27 | `document-observations` | `document_kind`, `operation`, `outcome`, `attribution`, `failure_code`, `http_status`, `dispatched_request_count`, `request_coverage` | C28-C31 request totals/coverage, C12/C13/C40 feed outcomes, C32-C37 grouped causes; individual article HTTP outcomes are not retained |
| G28 | `document-observations` | `occurred_at`, `duration_ms`, `request_phase`, `request_sequence`, `retry` | C7 feed-check time and D API timings; request totals include actual retries/hops; individual operation clocks/order removed |
| G29 | `operational-state` | `version`, `date`, `written_at_utc`, `evidence_cutoff_utc`, `source_id` | Relevant schema/run/feed context in C/D; old request-score cutoff removed with that score |
| G30 | `operational-state` | `state_revision`, `parent_revision`, `code_revision`, `policy_version` | Removed revision/reproduction machinery; no Git SHA |
| G31 | `operational-state` | `window_days`, `window_start`, `window_end`, `evidence_start_utc`, `evidence_end_utc` | Seven-day date-window concept retained for the spend report L3/D20, not the old score. D21/C18/C19 describe the separate native feed-reliability window |
| G32 | `operational-state` | `measured_target_requests`, `measured_source_wasted_requests`, `observed_attempted_opportunities`, `observed_measured_opportunities`, `measured_coverage`, `qualification_status`, `request_waste_ratio`, `operational_penalty` | Raw request spend remains C28-C30; causal waste, qualification and article-cost penalty deliberately removed, not reconstructed from totals |
| G33 | `rejections` | `version`, `date`, `correlation_id`, `rejected_at` | Schema and UTC accounting date retained at output grain; per-rejected-article clocks/correlation removed |
| G34 | `rejections` | `source_id`, `feed_url`, `subject`, `stage`, `drop_reason` | C5/C32/C35/C36; feed URL comes from registry |
| G35 | `rejections` | `candidate_id`, `url_key`, `canonical_url`, `title`, `categories` | No permanent rejected-article record. A may retain the URL key for first sight; B keeps content only if selected |
| G36 | `rejections` | `details` | Known feed failure code/status and grouped reasons in C; detailed per-article failure payload removed |
| G37 | `source-runs` | `version`, `date`, `run_id`, `correlation_id`, `attempt` | Schema plus D2/D14/D15 and C22/C34/C38; correlation copy removed |
| G38 | `source-runs` | `source_id`, `source`, `status` | Feed identity in C, selected applied configuration in B, registry membership remains configuration. Old catalog `status` is not C13's HTTP status |
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
| H5 | Policy version/hash, admission thresholds, recency/authority coefficients, allowances and concentration coefficients | Runtime configuration; actual contributions B18-B26/B32 and explicit run settings D16-D18 | No full historical policy replay or repeated per-article configuration snapshots |
| H6 | Score base and marginal values | B18/B19 plus explicit components B22/B23 | None for explaining the two totals |
| H7 | Numerical penalties and their availability | B20/B21; null remains unavailable, not a measured zero | Full nested operands/witness trees are not copied; this is not a promise of complete replay |
| H8 | Effective allowance, bonus witnesses, exploration and relaxed caps | B24-B26/B32 | Full witness objects removed; relevant reason codes remain |
| H9 | Carrier outlets, representative and replacement references | Applicable duplicate handling can run in memory; B keeps the selected URL | No permanent competitor/carrier reconstruction; unused replacement scaffolding removed |
| H10 | Rejection details: HTTP/timeout/word/age bounds, matched URL/date/marker, failure code, history window and diagnostics | Checks remain in execution; C keeps grouped causes and feed-level code/status | No historical per-article diagnostic dossier |
| H11 | Fetch/extraction diagnostic trees, quality measurements and warnings | Sparse exceptional diagnostics outside ledger data; API duration in D | No routine copied article measurement trees |
| H12 | Headline matches, weighted lens, watchlist and salience observations | Not silently promoted into scores; any retained active effect must appear in B20/B21 or B32 | No copied classification/voting history or invented vote bonus |
| H13 | Completed-file IDs/digests/counts and logical completion commitments | Removed with the full-audit product | No claimed proof of historical complete-attempt reconstruction |
| H14 | Raw/compact file envelopes and indexes | Minimal declared storage metadata and native packing still required | They are not a reason to add every old generic identity field to the new payload |

## K. API inventory

These are local operator services, not a backend for the published site.
The current route registrations implement 13 HTTP operations across the three
services; one feedback operation is planned. Renaming the persistence operation
replaces it; it does not create an additional permanent compatibility API.

### Table K - Plan 66/67 HTTP operations

| ID | Service | Method and full path | Current implementation / proposed simplified role |
| --- | --- | --- | --- |
| K1 | Feed planner | `GET /api/2026-10-20/health` | Implemented: listener/enablement check only, not a feed-reliability query |
| K2 | Feed planner | `POST /api/2026-10-20/plan` | Implemented orchestration; adapt outputs to the four ledgers and article artifact |
| K3 | Feed planner | `POST /api/2026-10-20/fetch` | Implemented fetch for either a configured feed or an explicitly permitted article |
| K4 | Feed planner | `POST /api/2026-10-20/parse` | Implemented parse for fetched feed XML or article HTML; no separate parse-feeds route |
| K5 | Feed planner | `POST /api/2026-10-20/select-articles` | Implemented combined admission/ranking; no selection-idempotency requirement or input-count cap |
| K6 | Feed planner | `POST /api/2026-10-20/partition-articles` | Implemented worker assignment/bin packing; does not reselect |
| K7 | Feed planner | `POST /api/2026-10-20/persist-dispatches` | Implemented old persistence route. Proposed replacement: `POST /api/2026-10-20/persist-selected-articles`, writing B without text and producing its text-bearing artifact |
| K8 | Feed planner | `POST /api/2026-10-20/feed-health-state` | Planned contract, not a registered route yet. Adapt it to the simplified health recording/lookback operation in L, not the superseded snapshot/head format |
| K9 | Host fingerprints | `GET /api/2026-10-20/health` | Implemented separate service health check |
| K10 | Host fingerprints | `POST /api/2026-10-20/fingerprint` | Implemented optional machine collection/persistence; not mandatory planner evidence |
| K11 | Host probes | `GET /api/2026-10-20/sample` | Implemented standalone machine CPU/RAM sample |
| K12 | Host probes | `POST /api/2026-10-24/start-task-profile` | Implemented optional explicitly pinned process profiling |
| K13 | Host probes | `POST /api/2026-10-24/stop-task-profile` | Implemented stop/readback for that profile |
| K14 | Host probes | `POST /api/2026-10-24/cache/latency` | Implemented optional owned cache benchmark; not planner article timing |

The two health paths belong to different service listeners. The standalone RAM
HTTP proof uses K11; it is not another RAM API. The ledger writer is a library
and CLI, not an additional HTTP service. No `GET /feeds` or read-only
`GET /feed-health-state` route currently exists.

K8 must have its strict request/response contract revised for the four-ledger
format before implementation. Its presence in the old contract documentation
does not mean a working route exists.

## L. Lookback summaries

The current TypeScript reliability computation is an internal native reader.
It is not K1's listener health response. K8 was planned to expose the feedback
operation, but its runtime route was not implemented.

### Table L - Independent windows

| ID | Component | Current default and unit | Proposed retained meaning |
| --- | --- | --- | --- |
| L1 | Lifecycle/rest | `feedback.lifecycle_window_days = 31` represented UTC days | Use the newest named represented days, not 31 fabricated consecutive dates; preserve endpoint and native rest ordering |
| L2 | Feed-read reliability | `collect.reliability_window_days = 30` represented days; `collect.reliability_floor = 0.5` | Productive / evidence-bearing feed reads, with the configured floor; keep the existing feed metric and expose incomplete evidence |
| L3 | Request-spend report | Existing `feedback.window_days = 7` closed UTC calendar days | Rename the setting to `feedback.request_report_closed_days`; sum observed feed/article/robots request spend, not a waste score or ranking penalty |

**Confirmed decision:** Retain the seven-day component as a feed request-spend
report only. Remove the qualified causal request-waste score. Its
measured-opportunity qualification and normalized CPU/memory/request weights
are not reused for this report. This does not silently enable a feed-reliability
fallback when request data is unavailable.

All three windows use UTC. The 31-day lifecycle and seven-day request windows
are not interchangeable reliability windows. The 30-day feed-read window
already exists in current configuration. This proposal keeps those meanings
rather than changing 30 to 31 or using the seven-day request window for
feed-read scoring.

The shared operation will:

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
These are direct stage calls, not HTTP self-calls. Standalone
`/select-articles` does not acquire an implicit update side effect; K8 remains
an explicit operator operation.

The same successfully saved health data can supply the TypeScript health-view
projection. The browser does not derive a second competing reliability verdict.
All of this is proposed runtime behavior; current code and the old K8 DTO are
not claimed to have been migrated.

## Shared rules and removals

- No article text in committed ledgers, repository files or normal-run logs.
- Counts and durations use integers. Genuine two-state facts use booleans.
  Ratios and weights remain numeric. Unknown is not zero or false.
- Schema versions are date stamps stored once per file.
- Ledger identity is known from its registered output, not a repeated `ledger`
  column. `date`, `run_id` and `attempt` are retained where required by the
  explicit main tables, not injected as a generic identity tree.
- No Git SHA, `unit_id`, revision chains, duplicate head files or hidden generic
  writer identity columns in these proposed formats.
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
- Existing rest fields do not claim completion of the separately tracked D5
  earned-recovery, trial/review or polling work. No unused future-policy columns
  are preallocated, and those policy tasks are not silently cancelled.
- Python production remains unchanged. Implementation follows Plan 67's
  authorized clean-break sequence; the superseded compatibility migration is
  not resumed.

## Design rationale

### Keep the field review together

The field lists, old-to-new mappings, API inventory and window definitions
answer one question: which planner data is retained and where. They remain
together so each proposed field can be reviewed against its old source and
consumer without losing the stable review IDs. Plan 67 tracks removal or
splitting of obsolete duplicated prose after the replacement contracts are
settled and the affected consumers are migrated.

### Approved clean-break delivery

**User approval, 2026-10-25 UTC:** Replace the old planner formats in their
actual code paths. No old-to-new migrators, compatibility readers, aliases or
dual writers are required or permitted for this replacement. The old-to-new
tables above explain field disposition; they are not migration instructions.

Targeted deletion of the old raw ledgers named in Table F under
`state/raw/feed-ingest-plan/` is permitted. It does not authorize deletion in
other families, deletion of compact archives or the historical corpus, Python
production changes, or a Git history rewrite.

The documentation and updated Plan 67 must reach remote `main` before
implementation starts. Contracts, current-format readers and writers, API
cutover, and the required old-writer/data/registry cleanup ship together when
separating them would leave an unused second implementation. Declare the
minimal four contracts before their logic within that cohesive change; do not
land a compatibility phase.

The runtime cutover uses typed events and asynchronous, bounded concurrent
work. Independent requests and work may overlap; each fetch must precede its
parse, selection waits for its complete eligible input, and partitioning waits
for selection. Health recording and reporting may overlap partitioning after
selection. Do not serialize all runs through one global queue. Existing fetch
safety checks and the artifact-only article-text boundary remain unchanged.

### Compute the lookbacks once per run

**Provisional recommendation, not a measured runtime claim:** Do not add a
fifth summary ledger, a separate summary service or another API. Reuse the
planned `feed-health-state` shared operation, compute the bounded lookbacks
once per run and share the result among consumers in memory. The captured
reliability fields in C record what that run used; they are not a cache proved
fresh enough for a later run.

**Estimate:** Simple feed/day counters should be cheap to aggregate, but no
timing of the proposed format exists and file I/O may dominate. When the real
implementation exists, record the actual `feed-health-summary` duration through
the existing `plan-runs` API/phase timing fields D11-D13. This does not require
host fingerprints, cache benchmarks or process profiling.

Consider an incremental persisted cache only if representative runner evidence
changes that recommendation. First consider keeping any justified cache in
the existing health data family rather than adding a ledger or API. Do not
build cursor, fingerprint, revision or head machinery before that evidence
shows a need.

## See also

- [Plan 66](../../TODO/20261020-66-feed-ingest-plan.md) - the delivered planner and unfinished follow-up scope.
- [Plan 67](../../TODO/20261024-67-feed-ingest-feedback-and-selection-plan.md) - replacement review, paused implementation and deferred cleanup.
- [Selection rules](../architecture/sources/feed-curation.md) - current selection behavior.
- [Feed history and reliability](../architecture/sources/planner-feed-history.md) - current native readers and represented-day rules.
- [Operator API](../architecture/sources/feed-operator-api.md) - current planner routes and contracts.
- [Host probe API](host-probe-api.md) - independent optional host operations.
