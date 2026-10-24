# Feed-ingest feedback

How do measured feed and article costs affect the next planner selection?

**Last Updated**: 2026-10-24

**Status**: Contract proposal; no feedback score or state writer is deployed.
The user approved separate hardware and request measures, automatic score use
after evidence qualifies, replacement of RSS reliability in the isolated
TypeScript planner, the configurable provisional score settings below,
requests-first eligibility, and counting only supported source-side failures
as waste. The rolling closed-UTC-day window is configurable with a seven-day
default. Other field additions and unsettled D3-D5/D8 choices remain
proposals.

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

Add `attribution` and nullable `failure_code` to each `FeedIngestEvent`
operation record. The planner-only event stream remains its TypeScript-owned
contract. Use the existing request-attempt and observation records for request
counts; do not persist a duplicate counter on the event.

| Field or measure | Proposed type and bound | Source and rule |
| --- | --- | --- |
| `publisher_id` | Nonempty configured ID or null | Record the configured ID at observation time after Row 3. Keep null when unknown; never backfill history from today's catalog. |
| `attribution` | `source`, `pipeline` or `unresolved` | Required on each operation outcome. A status code alone does not establish source attribution. |
| `failure_code` | Nullable string from the producer's declared code vocabulary | Preserve the exact recorded cause. An unrecognized code maps to `unresolved`, not source failure. |
| `cpu_ms` | Nullable integer, `>= 0` | Eligible only when measured CPU belongs exclusively to this operation. A process CPU delta during overlapping work is not source-attributable. |
| Task-profile process CPU | Existing pinned-process CPU delta, diagnostic only | It is not additive across overlapping operations and cannot enter source waste. Do not copy it into an article event. |
| `private_memory` | `unavailable` for source scoring until attribution is proved | Process RSS, including sampled maximum, is diagnostic only. It includes retained and shared memory and cannot identify which source caused it. |
| `http_request_count` | Nullable integer, `>= 0` | Count dispatched article-target HTTP requests, including each retry and redirect once. Exclude validation checks and API calls. Leave null when the producer cannot prove complete coverage. |

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

Extend the existing `SourceRunRecord` row in TypeScript and Pydantic, and its
`source-run-summary.ts` writer, rather than adding a parallel rollup. It is
already one source/run row. Add nullable confirmed `publisher_id`, attempted
and measured distinct article-opportunity counts as integers `>= 0`, and for
article-linked target requests, nullable integer `total` and `wasted` amounts
`>= 0`. When both amounts are known, require `wasted <= total`. The CPU and
private-memory components stay unavailable until attribution is proved; do
not convert process readings into source costs. Keep feed-poll and robots
costs in separate source-operation records; do not divide them among article
opportunities. Keep separate pipeline and unresolved costs in their existing
event or operation records at the actual scope; do not copy them to the source
row. Derive coverage as
`measured_opportunities / attempted_opportunities`; when its denominator is
zero, keep coverage unknown. Only source-attributed, failed operation costs
enter a source's `wasted` amount. A successful operation, a pipeline failure,
an unresolved cause or a feed poll with no new entries is not source waste.
The Pydantic `SourceRunRecord` remains the authority for that persisted row;
the TypeScript copy and its binding checks must change with it.
Stamp the changed row contract and migrate old rows to null for new evidence;
do not restamp old rows as if their missing measurements were zero.

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
Keep one `settle-ingest-feedback` writer. Its versioned state snapshot should
carry:

| Field | Proposed type and bound |
| --- | --- |
| `state_revision` | Positive integer, advanced once per committed snapshot |
| `parent_revision` | Nullable positive integer naming the snapshot read |
| `written_at_utc`, `evidence_cutoff_utc` | UTC instants |
| `window_days` | Positive integer copied from the configured rolling-window setting |
| `window_start`, `window_end` | UTC dates; exactly the named closed days selected by `window_days` |
| `code_revision`, `policy_digest` | The writer's Git revision and digest of the settings used |
| `sources` | Rows keyed by nonempty `source_id`, each with the component and restriction fields below |
| Per-source `next_poll_at_utc`, `next_probe_at_utc` | Nullable UTC instants |

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

Each source row has `publisher_id: string|null` and `cpu`, `private_memory`
and `http_requests` component records. Each component has
`status: qualified|insufficient_support|unavailable`; nullable integer
`total` and `wasted` amounts `>= 0`; integer `distinct_opportunities` and
`measured_opportunities` `>= 0`; and nullable finite `coverage` and
`waste_fraction` in `[0,1]`. For a qualified component, its denominator is
nonzero, `wasted <= total`, support is at least 20 and coverage is at least
0.8.

The restriction record has `status: normal|restricted|probe_due|trial`,
`scope: article|endpoint|feed|null`, a nullable stable `scope_key`, nullable
closed `reason_code`, and nullable UTC `restricted_since_utc` and
`next_probe_at_utc`. Scope keys come from configured source or candidate
identity, not fetched text or arbitrary URLs.

Keep the feedback snapshot separate from the curated source catalog: it may
hold temporary access state, but cannot retire a source or publisher. Each
source row keeps the confirmed `publisher_id` used for its observations.
Because this snapshot is a persisted payload read by a later run and is not
the planner-only event stream, declare its native model under
`backend/idhazh/contracts/` and keep the TypeScript reader copy in step with
the existing binding tests.

The checkpoint is `state_revision`, `evidence_cutoff_utc`,
`window_start` and `window_end`; do not add a growing list of settled event
IDs. Recompute the rolling window from its configured named UTC ledger days.
Select the latest compatible snapshot through the registered ledger index,
not a repository walk.

Settle by `event_id`; an identical replay adds no amount or support. A
correction names the event it replaces and does not create another article
opportunity. Recompute the active configured window from named ledger periods,
then publish the derived snapshot. The proposed late-event bound is that same
configured window; an older correction is reported as late and does not
rewrite expired score evidence. It never clears a restriction.

**Concurrency and failure handling remain a proposal, not an approved
mechanism.** Do not serialize fetch, parse, planning or selection, and do not
add selection idempotency. Keep each run's observation files immutable and
uniquely named; regenerate the replaceable feedback snapshot from the latest
committed state and registered ledger inputs.

The shared publisher's existing recovery pattern
([committing completed output](../publishing/committing.md)) handles a commit
race by preparing derived output again from named inputs on a fresh `main`,
while retaining completed immutable observations. Reuse that pattern, not a
global lock or a custom Git retry loop. The conflict is narrow: two runs may
read revision R and both compute the next snapshot. Once one lands, Git rejects
the other's stale candidate. Rebuilding on the new tip incorporates the first
snapshot and both runs' immutable observations; replaying the stale snapshot
would instead overwrite a newer restriction. This race does not justify
holding fetch, parse or selection.

This is not a direct call to the shared publisher here: the TypeScript planner
publisher currently retries the same immutable files but cannot rebuild
derived state, and the shared Python publisher cannot be invoked as a local
Python step in this isolated TypeScript flow. The proposed route is a narrow
prepare callback at the existing TypeScript publication boundary. On a stale
base, it would use the existing bounded push-retry policy to rebuild the
snapshot from the fresh committed snapshot and named raw/compact inputs, while
preserving the run's immutable observation files. This costs a scoped adapter
change and its concurrency tests; the actual production caller is not yet
identified, so its declaration and ownership must be settled before
implementation. A stale snapshot must never be replayed over a newer
restriction.

No other run waits for settlement. If publication is refused or retries are
exhausted, leave the previously committed snapshot and restrictions unchanged,
retain the run artifacts, report settlement as failed/unsettled, and do not
claim completion. Missing or unreadable state is not empty history and must
not clear known restrictions.

The next allocation must read the latest compatible committed snapshot while
keeping its code and policy pinned. A failed commit does not advance
`state_revision`; the next settlement recomputes the named evidence window.
Missing or incompatible state must not become empty history or erase
restrictions. Whether the affected allocation stops or proceeds without
applying feedback state remains an operator-policy choice to settle before
implementation; it must not claim that unknown state was applied.

## D5 proposal: bounded controls and operational review

These values are estimates for owner review, not measured limits. They do not
cap ordinary configured feed fetching. Add no separate score-enable flag:
automatic score use after qualification is already approved. Keep any
existing API development flag separate from feedback policy. This proposal
does not add selection idempotency, conditional HTTP or semantic assessment.

| Setting | Proposed type and default | Effect |
| --- | --- | --- |
| `trial_opportunities` | Integer, 25 maximum per source trial | Report each attempted article. Qualification still needs at least 20 measured opportunities and 80 percent coverage; 25 allows 20 measured opportunities at exactly 80 percent. It does not activate catalog membership. |
| `restriction_failures` | Integer, 3 distinct source-attributed failed opportunities in the configured closed-UTC-day window, at the same endpoint or feed scope | Pause ordinary work only at that scope. An explicit article-level refusal affects only that article. A bare HTTP 403, pipeline failure or unresolved cause does not trigger it. |
| `restriction_pause_hours` | Integer, 24 | After the pause, make one recovery probe due; expiry does not restore ordinary work. |
| `recovery_successes` | Integer, 3 distinct successful article opportunities across at least 2 UTC dates, with at least 80 percent known outcomes | Restore trial access only after the observed sequence; successful time alone is not recovery. |
| `special_probe_budget` | Integer, 20 opportunities per planner run, at most 1 per source | Shared cap for admission and recovery probes, with due recovery probes first and stable source ID as the tie-break. This is not a cap on ordinary configured feed polls or article fetches. |
| `maximum_poll_gap_hours` | Integer, 24 | Schedule each permitted feed no later than the current 24-hour freshness target. If workflow delay makes that impossible, record missed freshness; do not claim a guarantee or silently drop ordinary work. |

The trial, restriction, recovery and probe numbers are proposals, not owner
decisions. A 20-item probe allowance and the score's 20-item support floor
serve different purposes; the first limits extra work and the second
qualifies a score. They must not be silently treated as the same approval.
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

The saved score needs one typed `source_operational` evidence object:

| Field | Proposed type and bound |
| --- | --- |
| `status` | `qualified`, `insufficient_support`, `missing_state` or `incompatible_state` |
| `state_revision` | Nullable positive integer |
| `policy_digest` | Nullable SHA-256 digest |
| `window_start`, `window_end` | Nullable UTC dates |
| `cpu`, `private_memory`, `http_requests` | Fixed component records: `status` is `qualified`, `insufficient_support` or `unavailable`; nullable integer `total` and `wasted` amounts are `>= 0`; `attempted_opportunities` and `measured_opportunities` are integers `>= 0`; nullable `coverage` and `waste_fraction` are finite numbers in `[0,1]`; `weight` is a finite number in `[0,1]`, set to one third |
| `operational_penalty` | Nullable finite number in `[0,1]` |
| `source_authority_contribution` | Finite number `>= 0` used for this choice |

The current score contract has no operational status or state revision field.
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

- D3: the request-first score eligibility and one-third maximum are approved.
  The seven-closed-day window is a configurable default. The typed producer
  additions, nonsemantic extraction failure binding, poll/robots cost
  separation and no-prior/no-decay proposal still need approval.
  Source-attributable CPU is not established by the current task-profile
  process delta. The approved support floor, coverage and weights do not
  approve these producer fields.
- D4: configurable rolling window, seven-day default, raw/compact registered
  reads, concurrent runs and graceful failure are owner-directed requirements.
  Snapshot fields, late-event policy, publication preparation and behavior
  when state is missing or incompatible remain unapproved proposals.
- D5: approve or change the trial, restriction, recovery, special-probe and
  maximum-poll-gap values; approve the bounded review windows, cadence, caller
  and report-only authority. Window lengths use the proposed configurable
  `feedback.window_days`, default seven.
- D8: the request-first component eligibility, equal-thirds/no-renormalization
  behavior, no-impact treatment for unqualified evidence and no-RSS-fallback
  rule are approved as recorded below. The typed `source_operational` trace
  remains a proposal. The RSS penalty replacement, automatic use after
  qualification and no-duplicate-penalty rule are already approved.
Only the explicitly recorded portions are approved. The remaining D3-D5 and
D8 proposals still need approval before implementation.

## Design rationale

The owner asked for a score that can reduce priority when measured operational
waste is high, with the combined penalty capped at 1. Separate units are
required because machine work and network requests are different facts. A
normalized score can combine them only after the evidence identifies both the
cost and the work that caused it. Historical host readings alone cannot support
that attribution.

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

## See also

- [Publisher identity](publisher-identity.md) - curated publisher IDs and
  historical unknowns.
- [Source curation](../sources/feed-curation.md) - selection score and
  publisher exposure.
- [I Feed](../sources/i-feed.md) - proposed source feedback and allocation.
- [Operator requests](../sources/feed-operator-api.md) - fetch, parse and
  selection request behavior.
- [Schema ownership](schemas.md) - persisted payload owners and migrations.
