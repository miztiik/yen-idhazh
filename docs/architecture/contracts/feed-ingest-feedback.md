# Feed-ingest feedback

How do measured feed and article costs affect the next planner selection?

**Last Updated**: 2026-10-24

**Status**: Contract proposal; no feedback score or state writer is deployed.
The user approved separate hardware and request measures, automatic score use
after evidence qualifies, replacement of RSS reliability in the isolated
TypeScript planner, the configurable evidence settings below,
requests-first eligibility, and counting only supported source-side failures
as waste. D3/D4 approvals recorded below define the initial observations and
per-source operational state. The rolling closed-UTC-day window is
configurable with a seven-day default. D5 admission, restriction and polling
rules remain unapproved.

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
supported failure causes. Save per-source operational state with evidence
dates, coverage and policy version. Do not invent CPU or memory costs.

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

Extend existing source/run and operation records and their writers; do not
add a parallel rollup. Record actual work for every fetch, parse and technical
check, including article-target requests and extraction outcomes. This is
collection of completed work, not a sample of 25 ordinary articles. Keep
source, pipeline and unresolved causes distinct; only supported source-side
failure can count as waste. Per-source operational-state coverage is measured
opportunities divided by attempted opportunities; zero denominator means
unknown. CPU and private-memory costs remain unavailable until attributable.
Feed-poll and robots costs stay at their actual operation scope, not copied
onto articles.

The correction identity, publisher mapping, full component schema and detailed
per-operation bindings are implementation details to declare and test before
writer changes. They do not need another owner vote unless they change the
approved attribution or scoring meaning.

## Proposed score

For each supported measure, sum the raw wasted amount and total attributable
amount before dividing. Do not average article ratios.

```text
component_waste = wasted_amount / total_amount
component_waste is in [0, 1]

penalty = min(1, sum(component_weight * component_waste))
priority = editorial_priority - (source_authority_contribution * penalty)
```

Each component is normalized separately; unavailable components remain `null`
and do not gain weight through renormalization. A component with no supported
evidence makes no score change. A measured zero requires a known nonzero
denominator and no observed waste. The score changes only the source-authority
contribution, preserves the curated weight and tier, and replaces rather than
stacks with the RSS reliability penalty.

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
precedence so a date is counted once. The derived per-source operational
state is also a declared, registered Parquet ledger payload, not a growing
JSON sidecar or input to the digest-feed summarizer. The ledger name and
persisted row shape remain to be settled before a writer is added.

Yes, read both roots through the registered ledger reader and compact indexes.
For each date, use the compact period when an index names it; otherwise use
that date's raw files. Follow the existing period precedence so a date comes
from exactly one source. Do not append raw re-run files to compact rows when
the index already names that date; this avoids counting the same observations
twice.

### Table B - Operational-state field decisions

| Id | Field | Proposed type or status |
| --- | --- | --- |
| B1 | `state_revision` | Positive integer, advanced per committed operational-state payload |
| B2 | `parent_revision` | Nullable positive integer naming the state revision used as its base |
| B3 | `written_at_utc`, `evidence_cutoff_utc` | UTC instants |
| B4 | `window_days` | Positive integer copied from configured setting |
| B5 | `window_start`, `window_end` | UTC dates; the closed days selected by `window_days` |
| B6 | `code_revision`, `policy_version` | Writer revision and policy version used |
| B7 | `sources` | Per-source rows keyed by nonempty `source_id`, with evidence dates, request counts and coverage |
| B8 | D5 control fields | Excluded until separately approved; not implied by operational telemetry |

**Owner ruling, kumarsnaveen_microsoft, 2026-10-24 UTC:** Preserve immutable
per-run observations. If another run saves first, recalculate only the
derived per-source operational state from the newer records. A failed save
leaves the old state intact and reports failure. An already-running selection
keeps the state revision it read. Report corrections outside the configured
evidence window, but do not use them in that window's score.

The request component's exact field shape remains to be declared. Preserve
request totals, wasted requests when supported, distinct and measured
opportunities, evidence dates, coverage, qualification status and policy
version. Do not add CPU or memory amounts: those are unavailable until
attributable.

Restriction state is not part of this approved D3/D4 operational telemetry
payload. Any later D5 restriction fields require separate approval. Existing
robots, trust and access-safety rules remain unchanged.

Keep operational state separate from the curated source catalog: it cannot
retire a source or publisher. Declare its Pydantic model under
`backend/idhazh/contracts/`; persist it through the registered Parquet ledger
writer and read it through the existing raw/compact ledger reader, with
TypeScript copies held by the existing binding tests. Do not create a JSON
state file or another unregistered persistence path.

The checkpoint is `state_revision`, `evidence_cutoff_utc`,
`window_start` and `window_end`; do not add settled event IDs. Recompute the
configured named UTC days and select the latest compatible operational state
through the registered ledger index, not a repository walk.

Recompute the active configured window from named ledger periods, then publish
the derived per-source operational state. Report corrections outside the
configured window; do not use them in that window's score. Event replay and correction identity details remain to be declared. An older correction does
not rewrite expired score evidence or clear a restriction.

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
last valid saved state when one exists and label it `stale_fallback`; preserve its
original window and do not invent an expiry time. Apply its saved qualified
adjustment and known restrictions as the best available state, but do not call
them current. If none is readable, continue selection without an operational
adjustment and emit `restrictions_unverified`; never write empty history over
saved state. Existing robots, trust and access-safety checks do not change.

The proposed read result carries `state_status: current|stale_fallback|unavailable`,
nullable `state_revision` and nullable `window_start`/`window_end`. For
`unavailable`, the score adjustment is null and the result includes the
`restrictions_unverified` notice, whose meaning is that restrictions could
not be verified. Fallback state retains its original revision and date range.
No age threshold is proposed; the status records what the reader used without
claiming it is current.

## D5 proposal: bounded controls and operational review

These values are estimates for owner review, not measured limits. They do not
cap ordinary configured feed fetching. Add no separate score-enable flag:
automatic score use after qualification is already approved. Keep any
existing API development flag separate from feedback policy. This proposal
does not add selection idempotency, conditional HTTP or semantic assessment.

### Table C - Unapproved controls and conditional trial

| Id | Setting | Proposed type and value | Effect |
| --- | --- | --- | --- |
| C1 | `age_group_article_cap` | Up to 100 distinct eligible articles per age group for the bounded trial; fewer if fewer are available | A2 remains conditional on a small config/code change. At most 500 distinct articles can be selected across the five groups; retries and redirects can make actual HTTP request totals higher. It does not cap all-work telemetry, ordinary fetches, selection inputs or the existing 100-item selected-output limit. Report unknown-age entries separately. |
| C2 | `restriction_failures` | 3 consecutive known source-attributed failures for one source and endpoint/feed scope, within the configured window | A known success at that scope resets the streak; unknown, pipeline and unresolved outcomes neither assert failure nor reset it. Article refusal restricts only that article. |
| C3 | `restriction_pause_hours` | Integer, 24 | Pause ends by making a recovery probe due; elapsed time alone does not restore ordinary work. |
| C4 | `recovery_successes` | 3 distinct successful opportunities across at least 2 UTC dates, with at least 80 percent known outcomes | Restore trial access only after observed recovery. |
| C5 | `special_probe_budget` | 20 opportunities per planner run, at most 1 per source | Recovery first, then stable source ID. Does not cap ordinary fetches. |
| C6 | `maximum_poll_gap_hours` | Integer, 24 | Proposed freshness ceiling only; it does not define adaptive polling cadence. |

Apart from A2's conditional trial decision, these are unapproved proposals,
not approved limits. The earlier 25-article value is withdrawn; it was an
unapproved trial-budget suggestion, not an observation or ordinary-work cap.
Record all actual fetch, parse and technical-check work, regardless of the
trial's age-group cap. In particular, the consecutive failure rule avoids
restricting a high-volume source for scattered failures; the threshold and
window still need approval. A 20-item probe allowance is separate from the
score's 20-opportunity support floor. Permanent retirement remains curated.

For A2, use exact non-overlapping age groups: `[0,2)`, `[2,6)`, `[6,12)`,
`[12,24)`, and `[24,36]` hours. Use the existing captured observation clock
and trusted publication-time evidence. An item without a known age is counted
in a separate unknown-age result; do not assign an age. The trial selects up to 100 distinct articles per group, fewer when fewer are
eligible. This caps articles selected for the trial, not HTTP requests:
retries and redirects can produce more requests. It does not cap the complete
parsed-batch input, telemetry for other work or normal production selection.

The current harvester parses feed entries before article requests. It already
computes publication age from the captured clock and records actual article
work. The smallest implementation is one config-driven trial selector in
`services/feed-ingest-plan/src/harvest-feeds/harvest-pool.ts`, before
`harvestArticle`, then the existing fetch, parse, observation and registered
Parquet writers. The bounded footprint is the config, its native Zod config declaration and
validation case, this internal harvest seam, and focused tests.
Reuse the current age calculation; do not add an HTTP or selection API field,
another ranking system, a second pipeline or new age semantics. This is a
small internal config/harvest change, not an API or selection-contract rewrite.
If implementation needs broader changes, pause because A2 is conditional.

Owner ruling, kumarsnaveen_microsoft, 2026-10-24 UTC: approve A2 only if it is
not too much of a configuration or coding change. The approved trial groups
are non-overlapping age ranges `[24,36]`, `[12,24)`, `[6,12)`, `[2,6)` and
`[0,2)` hours, with up to 100 distinct articles selected from each and fewer
when available entries are fewer. The maximum is 500 distinct trial articles;
actual HTTP request counts can be higher due to retries or redirects. This
applies only to bounded trial measurement, not ordinary selection or a cap on
captured work. Unknown age is reported separately, never assigned an invented
age. The 25-article proposal is withdrawn. Implementation remains conditional
until its actual config and coding cost is confirmed.

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
scope or additional policy digest. The current score contract has no
operational-state status, state revision or evidence-window fields.
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

## Remaining contract work

- D3: declare the exact technical extraction binding, correction identity and
  persisted field shape before writers. These are native contract details;
  they do not need another owner vote unless they change the approved meaning.
- D4: declare the operational-state schema and implement the approved
  publication/reader behavior at the named caller. These are implementation
  details; they do not need another owner vote unless they change the approved
  concurrency, immutable-observation, failure, stale-read or late-correction
  behavior.
- D5: trial/restriction/recovery thresholds, polling formula, review cadence,
  caller and authority.
- D8: final trace field types against the existing score contract. Its
  requests-first arithmetic and trace boundary are approved above.

These remaining choices need approval before implementation.

## Design rationale

The owner asked for a score that can reduce priority when measured operational
cost. Requests, CPU and memory need separate measures because their units and
attribution differ. This page stays whole because its observations, settlement
and score form one contract consumed by the next planner; splitting it would
separate persisted fields from the behavior they govern.

## See also

- [Publisher identity](publisher-identity.md) - curated publisher IDs and
  historical unknowns.
- [Source curation](../sources/feed-curation.md) - selection score and
  publisher exposure.
- [I Feed](../sources/i-feed.md) - proposed source feedback and allocation.
- [Operator requests](../sources/feed-operator-api.md) - fetch, parse and
  selection request behavior.
- [Schema ownership](schemas.md) - persisted payload owners and migrations.
