# Feed-ingest feedback

How do measured feed and article costs affect the next planner selection?

**Last Updated**: 2026-10-25

**Status**: Per-operation capture, supported failure attribution, bounded
article/request aggregation and a report-only requests-first estimate are
implemented. The operational-state and saved-score contracts are registered
with compatible historical readers. No state writer, persisted-state reader or
selection consumer exists yet; ranking is unchanged.
The user approved separate hardware and request measures, automatic score use
after evidence qualifies, replacement of RSS reliability in the isolated
TypeScript planner, the configurable evidence settings below,
requests-first eligibility, and counting only supported source-side failures
as waste. D3/D4 approvals recorded below define the initial observations and
per-source operational state. The rolling closed-UTC-day window is
configurable with a seven-day default. D5 restriction and recovery thresholds
are approved but inactive until implemented; adaptive polling and review
policy remain open.

## Scope

This contract covers nonsemantic access, extraction and work-cost evidence.
It does not assess truth, news value, article quality or story novelty. A
technical failure changes a source's operational evidence only when its cause
is supported; a pipeline failure is not a source failure.

The historical review used compact Parquet files for seven named UTC days,
2026-10-16 through 2026-10-22: item-health, feed-health and host-fingerprint,
plus the October 22 source-run file. The backend gardener writes compacted
files from raw ledger records; the review did not count both copies. See
[ledger compaction](../publishing/ledger-compaction.md). The records contain
CPU and process-memory readings, but not article-attributed CPU time,
memory-time, a complete HTTP request count or historical publisher IDs. They
describe machine use, not which publisher caused it or how much was waste.

## D3 approved observation scope and remaining field details

Keep `FeedIngestEventSchema` as the one TypeScript-owned planner event
contract. Do not make a second native copy of that event stream. Persisted
operational observations are a different payload: one registered
`feed-ingest-plan/document-observations` raw/compact Parquet row projection
owned by a Pydantic contract. Reuse `event_id`, `source_id`, `run_id`,
`attempt`, `correlation_id` and `candidate_id` from existing observations;
include operation, outcome, UTC occurrence time, duration, supported cause
and actual dispatched-request accounting. Reuse the writer's `git_sha` for
pipeline revision rather than adding another revision field.

The planner observations and fetch-attempt records are the fact sources.
A source-run aggregate is not enough where it loses per-operation
facts. The Parquet projection preserves individual operations,
including partial and unsuccessful work, before a later plan stage can fail.
It does not add another planner event contract. These records do not provide
article-attributed CPU or private-memory cost. Host CPU and process RSS in
other ledgers are not article costs. The existing feed
`parse_status` describes RSS entry parsing; `success` with `parsed_count > 0`
does not prove article material was extracted. Keep those cases distinct.

The Row 2 contract slice registers `document-observations` for raw and compact
Parquet reads, with a Pydantic row model and a matching TypeScript reader
contract. Fetch and parse outcomes remain separate from request-attempt rows;
attempt rows retain their phase, sequence, retry, duration and known request
count. Nullable `observed_run_id` and `observed_attempt` retain fact-source
identity separately from the Parquet writer's required run identity. Unknown
request coverage remains null rather than becoming a zero.
The fetch, parse and full-plan paths write these observations through
`@idhazh/ledger-file-writer`. Explorer exposure remains separate.

Record the approved `source`, `pipeline` or `unresolved` attribution and
supported failure cause on operation observations; exact field names and types
are implementation details. The planner-only event stream remains its
TypeScript-owned contract. Use existing request-attempt and observation
records as the facts for request accounting; do not add a duplicate counter
to the event.

### Table A - Observation field decisions

| Id | Field or measure | Type or status | Source and rule |
| --- | --- | --- | --- |
| A1 | `publisher_id` | Nonempty configured ID or null | Record configured ID after Row 3. Keep unknown null; never backfill history. |
| A2 | `attribution` | Nullable `source`, `pipeline` or `unresolved` value | Failed observations use the [supported producer rules](../sources/feed-failure-diagnostics.md#operation-failure-attribution); a bare status without a typed target refusal is insufficient. |
| A3 | `failure_code` | Nullable declared code | Preserve supported technical cause; unknown cause remains unresolved. |
| A4 | `cpu_ms` | Nullable integer, `>= 0` | Proposal only. Eligible only when CPU belongs exclusively to this operation. Overlapping process deltas are not attributable. |
| A5 | Task-profile process CPU | Existing pinned-process delta; diagnostic only | Not additive across overlapping operations and never eligible for source waste. |
| A6 | `private_memory` | Unavailable for source scoring until attribution is proved | RSS and sampled maximum are diagnostic; they include retained/shared memory and cannot identify its source. |
| A7 | `http_request_count` | Nullable integer, `>= 0` | Owner-approved actual article-target attempts, including retries and redirects once. Exclude validation/API calls; unknown if coverage is incomplete. |

**Owner ruling, kumarsnaveen_microsoft, 2026-10-24 UTC:** Extend existing
records with actual article-request totals, technical extraction outcomes and
supported failure causes. Save per-source operational state with evidence
dates, coverage and policy version. Do not invent CPU or memory costs.

For requests, reuse `FetchAttemptSchema` as a fact source. Its `phase`
distinguishes `validation`, `robots` and `target`; keep those scopes distinct.
Count actual dispatched article-target requests, including retries and
redirects once each. Do not count API validation, robots or feed polls as
article requests, or copy feed-poll and robots costs onto articles. The
permitted fetcher counts dispatch at the transport call, after address
validation. Each completed attempt retains its actual count and completion
time. Validation attempts have known zero dispatches; a failed transport call
after dispatch still counts. A successful response is not a request counter.

Use `(run_id, source_id, candidate_id)` as the article-opportunity key.
Retries and correction records do not add article support. An observation
retains the actual request's required `document_kind` (`feed` or `article`),
so a feed URL hash in `article_id` cannot make a feed poll an article
opportunity. A candidate is an article opportunity only with article kind,
run identity and source identity. `caused_by_event_id` records causal lineage;
it does not replace a missing opportunity identity. Use `event_id` as the
replay key. A correction is a new event with nullable `corrects_event_id` and
`correction_revision`. Both fields are null for an ordinary event and both
are present for a correction. The row contract checks the pair and requires a
positive revision. The current reader retains correction events without
applying them; it also preserves events from every writer attempt, so a partial
retry cannot erase earlier operation facts. Native reads retain every writer attempt. Aggregation settles identical
`event_id` rows across attempts once and refuses conflicting copies; writer
attempts never become additional article support or dispatched requests.
Contribution aggregation must replace the prior contribution and reject tied
revisions. Each event retains its UTC time and producer revision. Operation
costs that cannot be linked to one article stay at their actual feed, run or
pipeline scope.

Use the existing `ArticleAssessmentRecordSchema.extraction_outcome` as the
nonsemantic article extraction result. Its values are `success`, `failed`,
`not_attempted` and `unavailable`; suitability and semantic judgments are
separate fields. A source-attributed `failed` extraction, or a supported
source-side fetch refusal that prevented extraction, can mark linked work as
waste. `not_attempted`, `unavailable`, pipeline failure and unresolved cause
do not. Do not add a second word-count test or semantic judgment.
`FeedOutcomePayload.parse_status` only describes RSS entry parsing and is not
an article extraction result.

The smallest persistence path is a Pydantic contract for the per-operation
observation rows, a bound TypeScript projection from existing planner
observations, registration in `config/ledgers.json`, then the existing
registered Parquet writer and raw/compact reader. Do not duplicate the
planner-only event schema or add a JSON sidecar. Extend existing observation
and fetch-attempt producers for `/fetch`, `/parse` and `/plan`; persist actual
work and partial outcomes before later plan stages can fail. The feed-client
must emit each actual dispatched request. Then Row 5 attaches supported
source, pipeline or unresolved causes, and Row 6 derives per-source request
totals, waste and coverage from the registered rows. This covers all actual
work, not a sample of 25 ordinary articles. Only supported source-side failure
can count as waste. Zero opportunity denominator means unknown. CPU and
private-memory costs remain unavailable until attributable. Feed-poll and
robots costs stay at their actual operation scope, not copied onto articles.

The correction identity, publisher mapping, full component schema and detailed
per-operation bindings are implementation details to declare and test before
writer changes. They do not need another owner vote unless they change the
approved attribution or scoring meaning.

### Completed-unit persistence

`services/feed-ingest-plan/src/ingest-observations.ts` writes immutable native
files under `state/raw/feed-ingest-plan/document-observations/`, partitioned by
each fact's UTC occurrence date. The shared fetch and parse units call it from
`/fetch`, `/parse` and `/plan`. A completed fetch saves its ordered attempt
rows and outcome together; each parse saves its own outcome before later
planning. Fetch exceptions flush completed attempts and a failed outcome too.
A hard process kill can lose an unfinished unit's unexported facts; missing
facts do not establish zero requests or complete coverage.

Attempt capture does not wait for Parquet I/O inside the HTTP deadline.
The writer's task identity derives from the operation and its trusted event ID,
not a URL, article text or a source-supplied filename. Concurrent units therefore
have distinct immutable write identities without a run lock. Pool failure
waits for already-running siblings to finish and retain their completed files.
No fetch or selection restarts because an observation save failed.

Plan facts retain the real run, attempt and offered-entry identity. Standalone
fetch/parse receipts have a journal run identity for replay, but no originating
planner run, attempt or offered entry. Their observation rows keep those three
fields null. Configured source and publisher identities remain curated; optional
salience-feed work has no source or publisher assignment. Reused robots and
feed responses add no dispatched-request rows. Parsing those bytes again is
separate actual parse work.

Failed outcomes use the supported [attribution rules](../sources/feed-failure-diagnostics.md#operation-failure-attribution),
with their existing typed failure code. Unknown causes remain unresolved.
CPU and private-memory costs remain unavailable. Early refusals record
not-attempted work, not fabricated requests or extraction.

A failed native save is logged with the affected event IDs and fails the
invocation. Other completed files remain intact. Standalone APIs first retain
the completed factual receipt, then report the save error; replay returns that
receipt without new network, parse or observation work. Replay does not repair
a failed telemetry save or claim that it succeeded. Plan summaries name the
actual observation files. The isolated workflow verifies these native files
and includes them in its exact commit manifest. It also retains verified
body-free observation files from its private document checks before removing
private article bodies. A later failure leaves completed native files in the
workflow evidence; it does not authorize a live run or a partial commit.

### Bounded article and request evidence

`feedback.window_days` in `config/feed-ingest-plan.json` defaults to seven
closed UTC days; the current UTC day is excluded. The planner reads each named
day through the registered raw/compact reader, including incomplete runs with
no final source-run row. Optional `inputs.document_observation_days` in
`config/feed-ingest-plan-service.json` supplies explicit files or indexes for
those dates; missing entries use the registered paths. The isolated workflow
stages this same named window without directory discovery.

The planner returns a typed internal aggregate as `article_evidence` and a
requests-first estimate as `operational_feedback` in its report. The estimate
uses only measured target requests, source-supported wasted requests, distinct
measured opportunities and measured coverage. It requires the configured
support and coverage thresholds and a known positive request denominator.
Unqualified or unavailable evidence contributes no penalty. CPU and private
memory remain unavailable, and their weights are not reassigned. This report
does not write derived state or change ranking; Row 10 owns the state writer
and selector consumer.
Source totals and explicitly recorded publisher totals keep distinct
attempted/measured opportunities, evidence instants, request counts and
coverage. Missing publisher IDs are not inferred. Feed polls, robots,
validation and work without an originating article identity do not add article
support. Unallocated observation/request amounts remain separate.

Request rows point to their fetch event; parse rows retain that same cause.
Only article-target dispatches enter article request totals. A completed
fetch with contiguous, complete attempt accounting proves request coverage;
orphan attempts, absent fetch completion and partial counts do not. Recorded
counts remain visible as lower bounds when coverage is incomplete. A source
failure marks only requests linked to that failed fetch or failed technical
extraction as waste. Successful extraction is not reversed by a later model
failure. Unresolved outcomes retain their requests but do not establish zero
source waste. If an opportunity eventually extracts successfully, it is not a
failed opportunity. Supported earlier failed-fetch requests remain operation
waste; requests from a fetch that later produces usable extraction do not.

Corrections replace their original contribution rather than add work.
Conflicting replays, tied revisions, cyclic lineage and changed opportunity
identity refuse the aggregate. An applied correction retains the original
operation's time and causal ID. A known out-of-window target is reported and
excluded. A target absent from the bounded input is reported as unavailable,
not assumed to be old or fetched by scanning history.

Counts are summed before dividing. `total_target_requests` requires a complete
request census for every observed opportunity and complete day coverage;
`source_wasted_requests` also requires resolved technical outcomes throughout.
These whole-window totals are separate from the supported measured subset.
`observed_request_census_opportunities` counts opportunities with complete
request accounting. `observed_resolved_outcome_opportunities` independently
counts opportunities where every fetch has successful extraction or a failure
attributed to the source or pipeline. `observed_measured_opportunities` counts
their intersection. A successful fetch without a parse outcome is unresolved.

`measured_target_requests` and `measured_source_wasted_requests` sum only that
intersection; `waste_ratio` divides those two amounts. Unknown requests and
unresolved outcomes are excluded, not counted as zero and not used to veto
other measured opportunities. An empty measured subset gives null totals.
The request and measured coverage denominators are distinct attempted
opportunities, never retry count. `request_coverage` reports complete request
censuses divided by attempts; `measured_coverage` reports the intersection
divided by attempts. A zero denominator or incomplete history gives null
coverage, while measured-subset amounts remain visible.

At 20 measured opportunities out of 25 attempts, measured coverage is 80
percent and the request component qualifies when its measured request
denominator is positive; 19 of 25 (76 percent) does not qualify. Below 80
percent, totals remain visible but the request component is unqualified. Row 6
does not calculate qualification or scores. A known zero-request opportunity
retains zero requests but gives no waste ratio.
The Row 7 caller must use `measured_target_requests`,
`measured_source_wasted_requests`, `observed_measured_opportunities` and
`measured_coverage`, not the strict whole-window totals or
`availability === "available"`. Partial opportunity coverage can meet the
approved 80 percent requirement. A history gap leaves coverage unknown and
cannot qualify, even when some measured totals are available. Missing resource
components stay unavailable; their weights are not reassigned to requests.
CPU and private memory remain null. Missing, damaged or ambiguous evidence is
reported without replacing saved state or inventing a successful empty history.

## Proposed score

For each supported measure, sum the raw wasted amount and total attributable
amount before dividing. Do not average article ratios. The current report
calculates only the requests component; it does not yet apply this estimate to
selection.

```text
component_waste = wasted_amount / total_amount
component_waste is in [0, 1]

operational_penalty = min(1, sum(component_weight * component_waste))
priority = editorial_priority - (source_authority_contribution * penalty)
```

Each component is normalized separately; unavailable components remain `null`
and do not gain weight through renormalization. A component with no supported
evidence makes no score change. A measured zero requires a known nonzero
denominator and no observed waste. When Row 10 activates the score, it changes
only the source-authority contribution, preserves the curated weight and tier,
and replaces rather than stacks with the RSS reliability penalty.

## Provisional evidence settings

These owner-approved policy defaults are not measurements learned from the
historical records:

- A configurable rolling window of closed UTC days, defaulting to seven.
- At least 20 distinct measured article opportunities for a component.
- At least 80 percent coverage of attempted opportunities for that component.
- Equal one-third weights for CPU, memory and requests.
- Requests are the only eligible component until CPU and private memory have
  source-attributable evidence; do not renormalize the equal weights.
- Unqualified evidence has no impact and does not fall back to RSS reliability.

Below either evidence requirement, preserve readings as unqualified and do not
apply that component. Historical CPU, memory and retry fields cannot
calibrate these values: the first two lack source attribution, and retries
are not a complete request census.

Use the raw per-source waste ratio over the configured rolling window. Do not
add a reference cohort, prior or decay: the component already has a fixed unit
and a `[0,1]` endpoint, while no historical source-attributed data can
calibrate a prior or half-life. The cost is that new sources remain
unqualified until they meet the approved support and coverage rules; no seed
value pretends to be measured evidence.

## D4 approved state behavior and implementation details

Reuse the existing registered ledger writer for observations and derived
operational state. Concurrent invocations remain allowed.

**Owner ruling, kumarsnaveen_microsoft, 2026-10-24 UTC:** make the evidence window
configurable, defaulting to seven closed UTC days; read registered data under
both `state/raw/` and `state/compact/`; allow concurrent runs; and design for
graceful failure. Exclude the current UTC day. The window rolls forward each
UTC day; it is not a frozen set of seven dates.

Propose `feedback.window_days` in `config/feed-ingest-plan.json` as the
positive-integer setting, default `7`. This is distinct from
`metrics.rolling_window_days`, which serves publication metrics. Compute the
named date range once per run from the UTC clock and this setting.

Raw observations are written once as native, registered Parquet under
`state/raw/{ledger}/`. The gardener compacts them to
`state/compact/{ledger}/`; readers use the existing indexes and period
precedence so a date is counted once. The derived per-source operational state is a declared, registered raw/compact
Parquet ledger payload, not a growing JSON sidecar or input to the digest-feed
summarizer. Its Pydantic row model, TypeScript reader schema, ledger
registration and compaction task are in place. Row 10 still owns the state
writer and next-allocation reader.

Yes, read both roots through the registered ledger reader and compact indexes.
For each date, use the compact period when an index names it; otherwise use
that date's raw files. Follow the existing period precedence so a date comes
from exactly one source. Do not append raw re-run files to compact rows when
the index already names that date; this avoids counting the same observations
twice.

### Table B - Declared operational-state fields

| Id | Field | Declared type or status |
| --- | --- | --- |
| B1 | `state_revision` | Positive integer, advanced per committed operational-state payload |
| B2 | `parent_revision` | Nullable positive integer naming the state revision used as its base |
| B3 | `written_at_utc`, `evidence_cutoff_utc` | UTC instants |
| B4 | `window_days` | Positive integer copied from configured setting |
| B5 | `window_start`, `window_end` | UTC dates; the closed days selected by `window_days` |
| B6 | `code_revision`, `policy_version` | Writer revision and policy version used |
| B7 | `source_id` and request evidence | One ledger row per source, with nullable evidence dates and request counts, measured opportunity counts, coverage and qualification |
| B8 | D5 control fields | Separate policy state; approved rules are inactive until its contract and enforcement are implemented |

**Owner ruling, kumarsnaveen_microsoft, 2026-10-24 UTC:** Preserve immutable
per-run observations. If another run saves first, recalculate only the
derived per-source operational state from the newer records. A failed save
leaves the old state intact and reports failure. An already-running selection
keeps the state revision it read. Report corrections outside the configured
evidence window, but do not use them in that window's score.

The row contract preserves measured request totals, source-supported waste,
distinct and measured opportunities, evidence dates, coverage, qualification
status and policy version. It does not add CPU or memory amounts: those remain
unavailable until attributable.

Restriction state is not part of the approved D3/D4 operational telemetry
payload. The D5 restriction and recovery policy below is approved, but its
state fields and runtime behavior are not yet implemented; do not activate
restrictions until that policy contract and implementation exist. Existing
robots, trust and access-safety rules remain unchanged.

Keep operational state separate from the curated source catalog: it cannot
retire a source or publisher. The Pydantic model is declared under
`backend/idhazh/contracts/`; its registered Parquet ledger contract and
TypeScript binding are in place. Row 10 will persist it through the shared
ledger writer and read it through the registered raw/compact path. Do not
create a JSON state file or another unregistered persistence path.

**Owner ruling, kumarsnaveen_microsoft, 2026-10-25 UTC:** select A1,
recalculate changed days only. Inspect registered day indexes for the
configured windows. When a day's input files or contents change, reread that
day and replace its saved contribution; reuse unchanged days. Compaction may
refresh a changed day. Declare validated day-input fingerprints and retained
contributions, including how cross-day causal settlement is handled. Late or
out-of-order commits and corrections must not be missed or counted twice.
Report corrections outside the retained window without applying them.

Read named ledger periods through the registered index, not a repository walk.

Compute article-request score evidence from named periods in the configured
closed-UTC-day window. Maintain the separate represented-day lifecycle by
rereading changed days and replacing their saved contributions; do not move a
full 31-day recomputation behind the API. Report corrections outside the score
window without using them in its score. An older correction does not rewrite
expired score evidence or clear a restriction.

Do not serialize fetch, parse, planning or selection, and do not add
selection idempotency. Keep each run's raw observation files immutable and
uniquely named; regenerate only the replaceable per-source operational-state
Parquet payload from the latest committed state and registered ledger inputs.

Reuse the shared publisher's existing recovery pattern
([committing completed output](../publishing/committing.md)): prepare derived
output again from named inputs on a fresh `main`, while retaining completed
immutable observations. Reuse that pattern, not a global lock or a custom Git
retry loop. The conflict is narrow: two runs may
read revision R and both compute derived state. Once one lands, Git rejects
the other's stale candidate. Rebuilding on the new tip incorporates newer
records; replaying stale state could overwrite newer state. This race does
not justify holding fetch, parse or selection.

This TypeScript flow cannot call the shared Python publisher as a local step.
Its existing publisher retries the same immutable files, so extend that
publication adapter with a bounded prepare callback: on a stale base, reuse
the existing push-retry policy and rebuild only the derived per-source
operational-state payload from the fresh committed state and named raw/compact
inputs. Preserve immutable observations. This is a scoped adapter extension
and concurrency tests, not a new commit engine or retry loop. Stale state
must never be replayed over newer state.

Settlement does not queue or hold other runs. If publication is refused or
retries are exhausted, leave the previously committed operational state unchanged,
retain the run artifacts, report the save failure and do not stop the entire
planner run. Missing or unreadable state is not empty history and must not
clear known restrictions.

A run that already read the previous operational state may finish with that
view; any separately approved future policy governs later allocations.
Preventing already-running allocations from using an older view would require
a separate per-source reservation rule, which is not included in this
proposal.

The next allocation reads the latest usable operational state with its code,
revision and original UTC window. If the current state is unreadable, use the
last valid saved state when one exists and label it `stale_fallback`; preserve
its original window and do not invent an expiry time. Apply its saved
qualified score adjustment as the best available state, but do not call it
current. D5 restrictions remain inactive until their policy state contract and
runtime implementation exist. If no state is readable, continue selection
without an operational adjustment and emit `restrictions_unverified`; never
write empty history over saved state. Existing robots, trust and access-safety
checks do not change.

The proposed read result carries `state_status: current|stale_fallback|unavailable`,
nullable `state_revision` and nullable `window_start`/`window_end`. For
`unavailable`, the score adjustment is null and the result includes the
`restrictions_unverified` notice, whose meaning is that restrictions could
not be verified. Fallback state retains its original revision and date range.
No age threshold is proposed; the status records what the reader used without
claiming it is current.

## Approved feed-health state migration

**Owner ruling, kumarsnaveen_microsoft, 2026-10-25 UTC:** adopt these ledger
names within the existing `feed-ingest-plan` family:

- Keep `article-assessments` and `editorial-selections`.
- Rename `dispatches` to `article-dispatches`.
- Rename `diversity` to `article-selection-diversity`.
- Rename `document-observations` to `ingest-observations` for both feed and
  article operations.
- Rename `operational-state` to `feed-health-state`.
- Rename `rejections` to `ingest-rejections`.
- Rename `source-runs` to `feed-runs`.

The raw and compact paths are
`state/{raw,compact}/feed-ingest-plan/<ledger-name>/`. `feed-health-state`
is one ledger, not separate observation and state ledgers, and remains inside
the existing family. This is a migration, not a runtime change in this docs
phase. Preserve old reads before writing renamed records, and ensure an
observation available under both names is counted only once. Do not remove
legacy data as part of the rename.

The approved implementation phases are:

1. **Contract and configuration:** design the full
   `POST /api/<existingversion>/feed-health-state` request, response and error
   contract. Keep two configurable windows distinct: a lifecycle inventory
   default of 31 represented days, and the existing article-request score
   default of seven closed UTC days. Do not encode 31 as a magic constant or
   add another request-weight cap; the approved request weight remains one
   third. Before writers, settle bounded behavior for late/out-of-order
   commits, corrections, window rollover and retained identity across the
   31-day inventory by inspecting registered day indexes. When day inputs
   change, reread only those days and replace their saved contributions;
   reuse unchanged days. Declare validated day-input fingerprints and retained
   contributions, including cross-day causal settlement. Late/out-of-order
   commits and corrections must not be missed or double-counted; corrections
   outside the retained window are reported but not applied. The API must
   identify the saved selection batch being settled using that selected
   output's `batch_id`; it is distinct from tracing context. Exact payload
   fields and configuration placement remain to be designed.
2. **Ledger rename:** update names, registrations, TypeScript raw/compact
   readers and writers, compaction configuration, manifests, verifiers,
   explorer labels and docs. Keep compatible old reads before new writes and
   prevent old/new double counting. Leave Python producers and consumers on
   their existing legacy paths for the deferred migration.
3. **Incremental TypeScript state:** update feed-health state after selection
   while partitioning proceeds independently, then have the next planner read
   the saved state. Inspect registered day indexes; reread and replace saved
   contributions only for changed days, and reuse unchanged days. Handle new
   observations, late commits, corrections and window expiry without a full
   31-day recomputation behind the API. Keep the configured seven-closed-day
   request-score rules unchanged.
4. **Remove redundant TypeScript reads and writes** only after the replacement
   covers current behavior.

Python migration to shared contracts and state, console migration to the
TypeScript-derived ledgers at build time, and retirement of the legacy
`feed-health` ledger and `frontend/public/source-health.json` are separate
deferred work. Retirement waits until the named Python and console consumers
are migrated and coverage is verified. The current Python runtime and legacy
files remain unchanged.

## D5 approved access policy; conditional trial and open polling

The approved control thresholds below are policy estimates, not measurements,
and are not active runtime behavior. They do not cap ordinary configured
fetching. Restriction fields and enforcement still need their Row 12 contract
and implementation. Recovery restores trial access only; it does not change
curated catalog membership or permanently activate a source. Keep any
existing API development flag separate from feedback policy. No selection
idempotency, conditional HTTP or semantic assessment is added.

### Table C - D5 policy decisions and open trial/polling work

| Id | Setting | Policy value or status | Effect |
| --- | --- | --- | --- |
| C1 | `age_group_article_cap` | Up to 100 distinct eligible articles per age group for the bounded trial; fewer if fewer are available | A2 remains conditional on total config/code cost after telemetry Rows 2, 4, 5 and 6. At most 500 distinct articles can be selected across the five groups; retries and redirects can make actual HTTP request totals higher. This does not cap all-work telemetry, ordinary fetches, selection inputs or the existing 100-item selected-output limit. |
| C2 | `restriction_failures` | **Approved 2026-10-25 UTC:** 3 consecutive confirmed source-side failures for the same source and evidenced endpoint/feed scope, within the configured window | Pause only that endpoint/feed scope. An article refusal affects only that article and cannot by itself widen the pause. A known success at the scope resets the streak; unknown and pipeline outcomes neither count as failure nor reset it. |
| C3 | `restriction_pause_hours` | **Approved 2026-10-25 UTC:** 24 hours | When the pause ends, a check becomes due for the next permitted planner run. Elapsed time alone does not restore ordinary work. |
| C4 | `recovery_successes` | **Approved 2026-10-25 UTC:** 3 consecutive successful recovery checks across at least 2 UTC dates, with at least 80 percent known outcomes | A confirmed source-side failure resets recovery progress and starts a new 24-hour pause. Unknown and pipeline outcomes are neither successes nor resets. Successful recovery restores trial access only. |
| C5 | `special_probe_budget` | **Approved 2026-10-25 UTC:** at most 20 recovery-check opportunities per planner run and at most 1 per source | Select oldest due checks first; ties use stable source ID, then endpoint identity. This limits checks, not HTTP requests; retries and redirects can exceed 20 requests. It does not cap ordinary feed or article work. |
| C6 | `maximum_poll_gap_hours` | Integer, 24 | Unapproved ceiling only; it does not define adaptive polling cadence. |

The owner-approved C2-C5 values are estimates, not measured thresholds. No
restriction or recovery action is active until Row 12 declares the policy
state and implements it. The prior 25-article trial suggestion remains
withdrawn. Capture all actual fetch, parse and technical-check work regardless
of trial selection. The score's 20-opportunity support floor is not the
20-check run budget. Permanent retirement remains curated.

For A2, use exact non-overlapping age groups: `[0,2)`, `[2,6)`, `[6,12)`,
`[12,24)`, and `[24,36]` hours. Use the existing captured observation clock
and trusted publication-time evidence. Unknown and future ages remain
ungrouped. The trial selects up to 100 distinct articles per group, fewer when
fewer are eligible. This caps articles selected for the trial, not HTTP
requests: retries and redirects can produce more requests. It does not cap
the complete parsed-batch input, telemetry for other work or normal production
selection. Persist each considered trial entry's disposition: selected,
excluded by the group cap, unknown age or future publication time.

The current harvester parses feed entries before article requests. Its age
calculation is reusable, but the observation and registered Parquet path is
not yet complete enough to audit the trial. First deliver the already-approved
telemetry sequence: Row 2 declares and registers the native operation-row
contract; Row 4 persists actual work and partial outcomes from `/fetch`,
`/parse`, `/plan` and `feed-client.ts`; Row 5 classifies supported causes; Row
6 derives request totals and coverage. Keep the planner-only event stream
TypeScript-owned; the Parquet rows are its separate persisted projection.

Only then add the age-group selector at
`services/feed-ingest-plan/src/harvest-feeds/harvest-pool.ts`, before
`harvestArticle`, with config declared in the native Zod config schema and
focused tests. Persist each considered entry's disposition with the trial
observations; keep unknown and future ages outside the groups. Continue
recording all actual work through the same observation and Parquet path. Do
not add an HTTP or selection API field, another ranking system or a second
pipeline. A worker identified additional disposition-contract, native-binding,
writer and readback work, plus a trial-only 24-36-hour harvest path. Total-cost
acceptance awaits the owner's decision; the earlier config-only estimate
omitted the approved telemetry dependency. Configuration placement remains
unsettled.

Owner ruling, kumarsnaveen_microsoft, 2026-10-24 UTC: approve A2 only if it is
not too much of a configuration or coding change. The approved trial groups
are non-overlapping age ranges `[24,36]`, `[12,24)`, `[6,12)`, `[2,6)` and
`[0,2)` hours, with up to 100 distinct articles selected from each and fewer
when available entries are fewer. The maximum is 500 distinct trial articles;
actual HTTP request counts can be higher due to retries or redirects. This
applies only to bounded trial measurement, not ordinary selection or a cap on
captured work. Unknown and future ages remain ungrouped, never assigned an
invented age. The 25-article proposal is withdrawn. Implementation remains
conditional on confirming total cost after the approved telemetry path is
delivered; no further approval is needed for that telemetry. Saving each
considered entry's disposition remains part of the trial. Total-cost
acceptance remains open. Configuration placement remains unsettled.

**Owner rulings, kumarsnaveen_microsoft, 2026-10-25 UTC:** Approve C2-C5 as
the restriction and recovery policy above. Three consecutive confirmed
source-side failures for the same source and evidenced endpoint/feed scope
within the configured window pause that scope. A known success at the scope
resets the failure streak; unknown and pipeline outcomes neither count as
failure nor reset it. An article refusal affects only that article. A
24-hour pause makes a check due for the next permitted planner run, but time
alone does not restore ordinary work. Recovery requires three consecutive
successful checks across at least two UTC dates and at least 80 percent known
outcomes. A confirmed source-side failure resets recovery progress and starts
a new 24-hour pause; unknown and pipeline outcomes neither count as success
nor reset progress. Each run may schedule up to 20 recovery-check
opportunities, at most one per source, oldest due first; ties use stable
source ID and endpoint identity. This is not an HTTP-request budget or an
ordinary-work cap. Recovery permits trial access only; it does not change
catalog membership. These policy choices do not activate behavior before the
Row 12 state contract and implementation are delivered.

Adaptive polling cadence remains unresolved. I Feed names new eligible
discoveries per completed permitted poll as the evidence and requires due
times within freshness and coverage bounds, but this plan has no approved
formula mapping that rate to a next-poll time. A 24-hour maximum alone does
not implement that behavior, so Row 13 is not ready to implement. Owner
approval is needed for the rate-to-interval formula and any minimum interval;
do not add a statistical model to fill this gap.
Keep permanent retirement in the curated catalog. Never broaden a restriction
from an article or endpoint to a feed or publisher without evidence at that
larger scope.

For Row 19, compare two adjacent windows, each using the configured number of
closed UTC days: the latest window and the one immediately before it. The
review input is the named registered ledger days, grouped by source and
producer revision, with source, pipeline and unresolved outcomes kept
separate. Report distinct opportunity counts,
coverage, raw outcomes and measured cost totals. Below 20 opportunities or 80
percent coverage, report `insufficient_evidence`; do not infer a regression.
Run the review once after settlement and whenever the producer revision
changes. Classify a supported issue as source-local when its cause is
source-attributed and confined to one evidenced scope; classify it as
pipeline-wide when pipeline-attributed failures share a producer revision;
report `mixed` when both occur and `insufficient_evidence` when support or
coverage is low. It recommends an action but cannot change score settings,
restrictions or catalog membership.

The proposed next-allocation reader is
`services/feed-ingest-plan/src/run-feed-plan.ts`, before article selection.
The proposed review call is `review-ingest-operations.ts` from that same
planner run, with Markdown rendered by
`.github/scripts/feed-ingest-plan-report.ts`. There is no production workflow
caller for this flow today; the existing test workflow is not a production
caller. Row 19 cannot close until an owner-approved real caller writes and
consumes the report and a later allocation reads the resulting committed
state.

## D8 proposal: replace the RSS penalty

Keep the approved arithmetic:

```text
source_operational_penalty = source_authority_contribution * operational_penalty
priority_score = base_article_score - source_operational_penalty
```

Use the existing equal-thirds, capped component calculation for
`operational_penalty`. It replaces the RSS reliability term; it does not add a
second penalty or an inverse-yield term. If evidence is not qualified, record
`operational_penalty = null` and apply zero score change. Do not fall back to
RSS reliability. Preserve RSS observations as historical evidence only.

The saved score needs one typed `source_operational` evidence object. The
approved trace is limited to the operational-state status, revision and evidence window,
plus the request counts and coverage that support the score. Do not add
restriction scope or other policy fields to this score trace.

### Table D - Proposed saved-score evidence

| Id | Field | Proposed type and bound |
| --- | --- | --- |
| D1 | `status` | `qualified`, `insufficient_support` or `unavailable` |
| D2 | `state_status` | `current`, `stale_fallback` or `unavailable` |
| D3 | `state_revision` | Nullable positive integer from the operational state actually used |
| D4 | `window_days`, `window_start`, `window_end` | Configured positive day count and nullable UTC dates from the operational state actually used |
| D5 | `http_requests` | Request `total` and `wasted` amounts, distinct and measured opportunity counts, and coverage; `wasted <= total`; counts are nonnegative; coverage is nullable in `[0,1]` |
| D6 | `operational_penalty` | Nullable finite number in `[0,1]`; null evidence makes no score change |

The per-source operational state records `policy_version`; do not duplicate
it in the score trace. The trace carries no CPU/memory amounts, restriction
scope or additional policy digest. The existing Pydantic `ScoreEvidence` and
its TypeScript copy now declare this object. Enclosing selection, assessment,
dispatch and stage payloads carry the new version and migrate historical rows
without changing publisher identity or exposure evidence. The old
`source_reliability` shape remains readable for historical rows; future
operational scoring must not use it as a fallback. The planner-event exception
does not make the saved score row TypeScript-only.

## Acceptance examples

- Replaying the same request event adds no request cost or article support.
- Three actual retry requests add three requests but remain one article
  opportunity.
- A pipeline parser failure retains its cost without lowering publisher
  priority.
- A known denominator with no waste records zero; a missing denominator is
  unknown.
- If only requests have supported evidence, CPU and memory stay `null`; their
  missing values do not increase the request weight.
- If requests are the only supported component and all their measured work is
  waste, the penalty is one third; unavailable CPU and memory do not add to it.
- If all three components later have qualified, fully wasted evidence, the
  penalty is 1 and the operational part of priority is reduced to zero.
- An unknown historical publisher remains unknown rather than inheriting
  today's feed mapping.

## Remaining contract work

- D3: the operational-state schema, registered ledger and saved-score trace
  shapes are declared and bound. Row 10 must implement publication and
  compatible state reading at the named caller. These are implementation
  details; they do not need another owner vote unless they change the approved
  concurrency, immutable-observation, failure, stale-read or late-correction
  behavior.
- D5: the C2-C5 restriction/recovery rules are approved but inactive pending
  Row 12's policy-state contract and implementation. Adaptive polling formula
  and review cadence, caller and authority remain unapproved. A2's trial
  remains conditional on total implementation cost after the approved
  telemetry path is delivered.
- D8: the saved-score trace fields and requests-first arithmetic are declared
  and bound. Row 10 still owns the state-backed consumer and ranking change.

Only D5 behavior or a proposed change to an approved meaning needs another
owner decision. Native field names, bindings and D8 trace types are
implementation work; proceed without another approval unless they change the
settled behavior.

## Design rationale

The owner asked for a score that can reduce priority when measured operational
cost. Requests, CPU and memory need separate measures because their units and
attribution differ. This page stays whole because its observations, settlement
and score form one contract consumed by the next planner; splitting it would
separate persisted fields from the behavior they govern.

The request aggregate remains internal until the saved-state publisher and
next selector are implemented. This keeps the registered operation rows as
the only factual authority and avoids a second persistent rollup with no
consumer. Replaying all writer attempts by event identity preserves work from
failed attempts without counting a reserialized event as new work.

## See also

- [Publisher identity](publisher-identity.md) - curated publisher IDs and
  historical unknowns.
- [Source curation](../sources/feed-curation.md) - selection score and
  publisher exposure.
- [I Feed](../sources/i-feed.md) - proposed source feedback and allocation.
- [Operator requests](../sources/feed-operator-api.md) - fetch, parse and
  selection request behavior.
- [Schema ownership](schemas.md) - persisted payload owners and migrations.
