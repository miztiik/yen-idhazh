# Feed-ingest feedback

How do measured feed and article costs affect the next planner selection?

**Last Updated**: 2026-10-24

**Status**: Contract proposal; no feedback score or state writer is deployed.
The user approved separate hardware and request measures, automatic score use
after evidence qualifies, replacement of RSS reliability in the isolated
TypeScript planner, the configurable provisional score settings below,
requests-first eligibility, and counting only supported source-side failures
as waste. D3/D4 approvals recorded below define the initial observations and
summary settlement. The rolling closed-UTC-day window is configurable with a
seven-day default. D5 activation thresholds remain unapproved.

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

## D3 proposal: observations and source rollups

Reuse the event identity already declared in
`FeedIngestEventSchema`: `event_id`, `correlation_id`, `run_id`, `attempt`,
`sequence`, `occurred_at`, `stage`, `source_id` and `candidate_id`. Reuse the
writer envelope's `git_sha` for the pipeline revision and the existing
extractor revision where the producer records it. Do not add a second event ID,
run ID or revision field.

The current feed-ingest event, source-run and planner-operation contracts
persist outcomes, durations, source/candidate identity and request attempts.
They do not persist article-attributed CPU or private-memory cost. Host CPU and
process RSS in other ledgers are not article costs. The existing feed
`parse_status` describes RSS entry parsing; `success` with `parsed_count > 0`
does not prove article material was extracted. Keep those cases distinct.

Propose recording `attribution` and nullable `failure_code` on existing
operation records. Their source/pipeline/unresolved meaning and supported
failure causes are approved; the exact field shape is not. The planner-only
event stream remains its TypeScript-owned contract. Use the existing
request-attempt and observation records for request counts; do not persist a
duplicate counter on the event.

### Table A - Observation field decisions

| Id | Field or measure | Type or status | Source and rule |
| --- | --- | --- | --- |
| A1 | `publisher_id` | Nonempty configured ID or null | Record configured ID after Row 3. Keep unknown null; never backfill history. |
| A2 | `attribution` | Proposed `source`, `pipeline` or `unresolved` value | Preserve the owner-approved distinction; a status code alone does not prove source attribution. |
| A3 | `failure_code` | Proposed nullable declared code | Preserve supported technical cause; unknown cause remains unresolved. |
| A4 | `cpu_ms` | Nullable integer, `>= 0` | Proposal only. Eligible only when CPU belongs exclusively to this operation. Overlapping process deltas are not attributable. |
| A5 | Task-profile process CPU | Existing pinned-process delta; diagnostic only | Not additive across overlapping operations and never eligible for source waste. |
| A6 | `private_memory` | Unavailable for source scoring until attribution is proved | RSS and sampled maximum are diagnostic; they include retained/shared memory and cannot identify its source. |
| A7 | `http_request_count` | Nullable integer, `>= 0` | Owner-approved actual article-target attempts, including retries and redirects once. Exclude validation/API calls; unknown if coverage is incomplete. |

**Owner ruling, kumarsnaveen_microsoft, 2026-10-24 UTC:** Extend existing
records with actual article-request totals, technical extraction outcomes and
supported failure causes. Save per-source summaries with evidence dates,
coverage and policy version. Do not invent CPU or memory costs.

For requests, `FetchAttemptSchema` already records one row per producer
execution, including retries and manually followed redirects. Its `phase`
distinguishes `validation`, `robots` and `target`. Count only `target` rows in
the article request measure. Keep feed polls and robots requests at their
source-operation scope; do not copy their cost onto each article. The current
producer's manual redirects make the attempt list complete at its
`transport.request` boundary, not for work hidden inside another transport.
The writer must keep that boundary and test the count against recorded
attempts. The current feed-poll record does not carry a complete request
census; keep that count null until the producer records each dispatched
request. Do not infer it from a successful feed response.

Use `(run_id, source_id, candidate_id)` as the article-opportunity key.
Retries and correction records do not add article support. Use `event_id` as
the replay key. A correction is a new event with nullable
`corrects_event_id` and `correction_revision`. Both fields are null for an
ordinary event and both are present for a correction. The positive correction
revision replaces the prior contribution; tied revisions are invalid. Each
event retains its UTC time and producer revision. Operation costs that cannot
be linked to one article stay at their actual feed, run or pipeline scope.

Use the existing `ArticleAssessmentRecordSchema.extraction_outcome` as the
nonsemantic article extraction result. Its values are `success`, `failed`,
`not_attempted` and `unavailable`; suitability and semantic judgments are
separate fields. A source-attributed `failed` extraction, or a supported
source-side fetch refusal that prevented extraction, can mark linked work as
waste. `not_attempted`, `unavailable`, pipeline failure and unresolved cause
do not. Do not add a second word-count test or semantic judgment.
`FeedOutcomePayload.parse_status` only describes RSS entry parsing and is not
an article extraction result.

Extend the existing source/run and operation records and their writers; do not
add a parallel rollup. Record actual article-target request totals and
technical extraction outcomes. Keep source, pipeline and unresolved causes
distinct; only supported source-side failure can count as waste. Per-source
summary coverage is measured opportunities divided by attempted opportunities;
zero denominator means unknown. CPU and private-memory costs remain
unavailable until attributable. Feed-poll and robots costs stay at their
actual operation scope, not copied onto articles.

The table's correction identity, publisher mapping, full component schema and
detailed per-operation bindings remain proposals unless specified by the
owner ruling. Persisted shape and migration details must be settled before
their writer changes.

## Proposed score

For each supported measure, sum the raw wasted amount and total attributable
amount before dividing. Do not average article ratios.

```text
component_waste = wasted_amount / total_amount
component_waste is in [0, 1]

penalty = min(1, sum(component_weight * component_waste))
priority = editorial_priority - (source_authority_contribution * penalty)
```

The approved provisional component weights are one third each for CPU, memory
and requests. They are not calibrated by the historical records. The value 1
means all measured work in that component was classified as waste; it is the
normalization endpoint, not a historical percentile. The combined penalty
cannot exceed 1.

Do not mix raw CPU, memory and request values. Normalize each component first.
An unavailable component remains `null` and is not given extra weight through
renormalization. If no component has supported evidence, the combined penalty
is `null` and makes no score change. A measured zero is different: it requires
a known nonzero denominator and no observed waste.

The score change applies only to the source-authority contribution. It keeps
the curated source weight and tier. It replaces the existing RSS reliability
penalty; it does not add a second operational penalty. Unknown or insufficient
evidence does not demote a source. Once configured evidence rules pass, the
supported penalty applies automatically.

## Provisional evidence settings

The owner approved these provisional configuration values. They are policy
defaults, not measurements learned from the historical records:

- A configurable rolling window of closed UTC days, defaulting to seven.
- At least 20 distinct measured article opportunities for a component.
- At least 80 percent coverage of attempted opportunities for that component.
- Equal one-third weights for CPU, memory and requests.

Below the support or coverage requirement, preserve the readings as
unqualified evidence and do not apply that component. The historical CPU,
memory and retry fields cannot calibrate these settings: CPU and memory are
not source-attributed waste, and retry fields are not a complete request
census.

The producer additions above are not measurements already present in the
historical files. The seven-day default, 20 opportunities, 80 percent and
equal weights are approved policy defaults; they do not prove that CPU or
memory collection is available or calibrated.

Use the raw per-source waste ratio over the configured rolling window. Do not
add a reference cohort, prior or decay: the component already has a fixed unit
and a `[0,1]` endpoint, while no historical source-attributed data can
calibrate a prior or half-life. The cost is that new sources remain
unqualified until they meet the approved support and coverage rules; no seed
value pretends to be measured evidence.

Approved score boundary: requests are the first eligible operational
component. Keep CPU and private memory unavailable until source-attributable
evidence exists. Preserve equal one-third weights without renormalization, so
requests alone can contribute at most one third. Unqualified evidence has no
impact and does not fall back to RSS reliability.

Current process CPU and memory readings cannot qualify their source
components. The request component is the only eligible component until
source-attributable CPU or memory evidence exists.

## D4 proposal: durable settlement

Reuse the existing registered ledger writer for observed events and state.
Define a `settle-ingest-feedback` stage that writes a versioned state snapshot;
concurrent invocations remain allowed.

**Owner-directed requirements, 2026-10-24 UTC:** make the evidence window
configurable, defaulting to seven closed UTC days; read registered data under
both `state/raw/` and `state/compact/`; allow concurrent runs; and design for
graceful failure. Exclude the current UTC day. The window rolls forward each
UTC day; it is not a frozen set of seven dates.

Propose `feedback.window_days` in `config/feed-ingest-plan.json` as the
positive-integer setting, default `7`. This is distinct from
`metrics.rolling_window_days`, which serves publication metrics. Compute the
named date range once per run from the UTC clock and this setting.

Yes, read both roots through the registered ledger reader and compact indexes.
For each date, use the compact period when an index names it; otherwise use
that date's raw files. Follow the existing period precedence so a date comes
from exactly one source. Do not append raw re-run files to compact rows when
the index already names that date; this avoids counting the same observations
twice.

### Table B - Summary field decisions

| Id | Field | Type or status |
| --- | --- | --- |
| B1 | `state_revision` | Positive integer, advanced per committed snapshot |
| B2 | `parent_revision` | Nullable positive integer naming the snapshot read |
| B3 | `written_at_utc`, `evidence_cutoff_utc` | UTC instants |
| B4 | `window_days` | Positive integer copied from configured setting |
| B5 | `window_start`, `window_end` | UTC dates; the closed days selected by `window_days` |
| B6 | `code_revision`, `policy_version` | Writer revision and policy version used |
| B7 | `sources` | Per-source rows keyed by nonempty `source_id`, with evidence dates, component counts/coverage and any separately approved restriction fields |
| B8 | Per-source `next_poll_at_utc`, `next_probe_at_utc` | Nullable UTC instants |

**Owner ruling, kumarsnaveen_microsoft, 2026-10-24 UTC:** Preserve immutable
per-run observations. If another run saves first, recalculate only the summary
from the newer records. A failed save leaves the old summary intact and
reports failure. An already-running selection keeps the summary revision it
read. Report corrections outside the configured evidence window, but do not
use them in that window's score.

Each source row has `publisher_id: string|null` and `cpu`, `private_memory`
and `http_requests` component records. Each component has
`status: qualified|insufficient_support|unavailable`; nullable integer
`total` and `wasted` amounts `>= 0`; integer `distinct_opportunities` and
`measured_opportunities` `>= 0`; and nullable finite `coverage` and
`waste_fraction` in `[0,1]`. For a qualified component, its denominator is
nonzero, `wasted <= total`, support is at least 20 and coverage is at least
0.8.

The proposed D5 restriction record has `status: normal|restricted|probe_due|trial`,
`scope: article|endpoint|feed|null`, a nullable stable `scope_key`, nullable
closed `reason_code`, and nullable UTC `restricted_since_utc` and
`next_probe_at_utc`. These fields do not approve activation of any D5
restriction policy. Scope keys come from configured source or candidate
identity, not fetched text or arbitrary URLs.

Keep the feedback snapshot separate from the curated source catalog: it may
hold temporary access state, but cannot retire a source or publisher. Each
source row keeps the confirmed `publisher_id` used for its observations.
Because this snapshot is a persisted payload read by a later run and is not
the planner-only event stream, declare its native model under
`backend/idhazh/contracts/` and keep the TypeScript reader copy in step with
the existing binding tests.

The checkpoint is `state_revision`, `evidence_cutoff_utc`,
`window_start` and `window_end`; do not add settled event IDs. Recompute the
configured named UTC days and select the latest compatible snapshot through
the registered index, not a repository walk.

Recompute the active configured window from named ledger periods, then publish
the derived summary. Report corrections outside the configured window; do not
use them in that window's score. The event replay and correction identity
details remain proposals. An older correction does not rewrite expired score
evidence or clear a restriction.

Do not serialize fetch, parse, planning or selection, and do not add
selection idempotency. Keep each run's observation files immutable and
uniquely named; regenerate only the replaceable feedback summary from the
latest committed summary and registered ledger inputs.

Use the shared publisher's existing recovery pattern
([committing completed output](../publishing/committing.md)): prepare derived
output again from named inputs on a fresh `main`, while retaining completed
immutable observations. Reuse that pattern, not a global lock or a custom Git
retry loop. The conflict is narrow: two runs may
read revision R and both compute a summary. Once one lands, Git rejects the
other's stale candidate. Rebuilding on the new tip incorporates newer records;
replaying the stale summary could overwrite newer state. This race does not
justify holding fetch, parse or selection.

This is not a direct call to the shared publisher here: the TypeScript planner
publisher currently retries the same immutable files but cannot rebuild
derived state, and the shared Python publisher cannot be invoked as a local
Python step in this isolated TypeScript flow. The proposed implementation is
a narrow prepare callback at the existing TypeScript publication boundary.
On a stale base, it would use the existing bounded push-retry policy to
rebuild only the summary from the fresh committed summary and named raw/compact
inputs, while preserving immutable observations. This costs a scoped adapter
change and concurrency tests; the production caller and exact summary shape
remain to be named before implementation. A stale summary must never be
replayed over newer state.

Settlement does not queue or hold other runs. If publication is refused or
retries are exhausted, leave the previously committed summary unchanged,
retain the run artifacts, report the save failure and do not stop the entire
planner run. Missing or unreadable state is not empty history and must not
clear known restrictions.

A run that already read the previous snapshot may finish with that view; a new
restriction governs allocations that read after it is published. Preventing
already-running allocations from using an older view would require a separate
per-source reservation rule, which is not included in this proposal.

The next allocation reads the latest usable summary with its code, revision
and original UTC window. If the current summary is unreadable, use the last
valid saved summary when one exists and label it `stale_fallback`; preserve its
original window and do not invent an expiry time. Apply its saved qualified
adjustment and known restrictions as the best available state, but do not call
them current. If none is readable, continue selection without an operational
adjustment and emit `restrictions_unverified`; never write empty history over
saved state. Existing robots, trust and access-safety checks do not change.

The proposed read result carries `summary_status: current|stale_fallback|unavailable`,
nullable `state_revision` and nullable `window_start`/`window_end`. For
`unavailable`, the score adjustment is null and the result includes the
`restrictions_unverified` notice, whose meaning is that restrictions could
not be verified. Fallback data retains its original revision and date range.
No age threshold is proposed; the status records what the reader used without
claiming it is current.

## D5 proposal: bounded controls and operational review

These values are estimates for owner review, not measured limits. They do not
cap ordinary configured feed fetching. Add no separate score-enable flag:
automatic score use after qualification is already approved. Keep any
existing API development flag separate from feedback policy. This proposal
does not add selection idempotency, conditional HTTP or semantic assessment.

### Table C - Provisional controls requiring approval

| Id | Setting | Proposed type and value | Effect |
| --- | --- | --- | --- |
| C1 | `trial_opportunities` | Integer, 25 per source trial | Report each attempt. Does not activate catalog membership. |
| C2 | `restriction_failures` | 3 consecutive known source-attributed failures for one source and endpoint/feed scope, within the configured window | A known success at that scope resets the streak; unknown, pipeline and unresolved outcomes neither assert failure nor reset it. Article refusal restricts only that article. |
| C3 | `restriction_pause_hours` | Integer, 24 | Pause ends by making a recovery probe due; elapsed time alone does not restore ordinary work. |
| C4 | `recovery_successes` | 3 distinct successful opportunities across at least 2 UTC dates, with at least 80 percent known outcomes | Restore trial access only after observed recovery. |
| C5 | `special_probe_budget` | 20 opportunities per planner run, at most 1 per source | Recovery first, then stable source ID. Does not cap ordinary fetches. |
| C6 | `maximum_poll_gap_hours` | Integer, 24 | Proposed freshness ceiling only; it does not define adaptive polling cadence. |

These are estimates, not approved limits. In particular, the consecutive
failure rule avoids restricting a high-volume source for scattered failures;
the threshold and window still need approval. A 20-item probe allowance is
not the score's 20-item support floor. Permanent retirement remains curated.

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
approved trace is limited to the summary status, revision and evidence window,
plus the request counts and coverage that support the score. Do not add
restriction scope or other policy fields to this score trace.

### Table D - Proposed saved-score evidence

| Id | Field | Proposed type and bound |
| --- | --- | --- |
| D1 | `status` | `qualified`, `insufficient_support` or `unavailable` |
| D2 | `summary_status` | `current`, `stale_fallback` or `unavailable` |
| D3 | `state_revision` | Nullable positive integer from the summary actually used |
| D4 | `window_days`, `window_start`, `window_end` | Configured positive day count and nullable UTC dates from the summary actually used |
| D5 | `policy_version` | Version used to produce the summary |
| D6 | `http_requests` | Request `total` and `wasted` amounts, distinct and measured opportunity counts, and coverage; `wasted <= total`; counts are nonnegative; coverage is nullable in `[0,1]` |
| D7 | `operational_penalty` | Nullable finite number in `[0,1]`; null evidence makes no score change |

This trace carries no CPU/memory amounts, restriction scope or additional
policy digest. The current score contract has no operational or summary-read
status, state revision or evidence-window fields.
Add the object to the saved score evidence, not to a new selection request or
response. The old `source_reliability` shape remains readable for historical
rows only; it is not a fallback for new scores. Reader-first schema migration
remains required: extend the existing Pydantic `ScoreEvidence` and its
TypeScript copy, then update the named binding tests. The planner-event
exception does not make the saved score row TypeScript-only.

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

## Open contract decisions

- D3: exact technical extraction binding, correction identity and detailed
  persisted field shape. The observations, source/pipeline/unresolved
  attribution, article request totals, source-side waste rule and configurable
  evidence window are approved.
- D4: exact summary schema, production caller and implementation details for
  fresh-base preparation. The concurrency, immutable-observation, failure,
  stale-read and late-correction behavior is approved.
- D5: trial/restriction/recovery thresholds, polling formula, review cadence,
  caller and authority.
- D8: final trace field types against the existing score contract. Its
  requests-first arithmetic and trace boundary are approved above.

These remaining choices need approval before implementation.

## Design rationale

The owner asked for a score that can reduce priority when measured operational
waste is high, with the combined penalty capped at 1. Separate units are
required because machine work and network requests are different facts. A
normalized score can combine them only after the evidence identifies both the
cost and the work that caused it. Historical host readings alone cannot support
that attribution. This page stays whole because the observations, settlement
and score are one contract consumed by the next planner; splitting them would
separate persisted fields from the behavior they govern.
Owner ruling, kumarsnaveen_microsoft, 2026-10-24 UTC: count cost as waste only
when an operation fails to produce usable material for a supported source-side
reason. Keep CPU, memory and request costs separate, normalize each before
combining, and apply the penalty automatically only after evidence qualifies.
Use configurable provisional defaults of a seven-day UTC window, 20 distinct
article opportunities, 80 percent measured coverage and equal one-third
component weights. These values are not calibrated by the historical data.

Owner ruling, kumarsnaveen_microsoft, 2026-10-24 UTC: requests are the first
eligible operational component. Keep CPU and private memory unavailable until
attributable. Do not renormalize the equal one-third weights; requests alone
can contribute at most one third. Unqualified evidence has no impact and does
not fall back to RSS reliability.

Owner direction, 2026-10-24 UTC: make the closed-UTC-day evidence window
configurable, default seven days; read registered data from both
`state/raw/` and `state/compact/`; allow concurrent runs; and design for
graceful failures. Compact indexes determine which tier supplies each day.
The window rolls forward; it is not a frozen seven-date set. A whole-run queue
was considered and withdrawn: observations are append-only, so it would hold
fetch, parse and selection without preventing a stale derived snapshot from
overwriting newer state. Protect only publication of the derived snapshot.

Owner ruling, kumarsnaveen_microsoft, 2026-10-24 UTC: when the current summary
is unreadable, use the last valid saved summary if available. If none is
readable, continue selection without operational adjustment and report that
restrictions could not be verified. Mark fallback state as stale, retain its
original UTC range, and do not invent an age limit. Do not overwrite saved
state with empty history. Existing robots and access-safety rules remain.

## See also

- [Publisher identity](publisher-identity.md) - curated publisher IDs and
  historical unknowns.
- [Source curation](../sources/feed-curation.md) - selection score and
  publisher exposure.
- [I Feed](../sources/i-feed.md) - proposed source feedback and allocation.
- [Operator requests](../sources/feed-operator-api.md) - fetch, parse and
  selection request behavior.
- [Schema ownership](schemas.md) - persisted payload owners and migrations.
