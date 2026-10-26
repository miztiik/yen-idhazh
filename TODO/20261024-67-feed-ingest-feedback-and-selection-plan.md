# Plan 67 - Feed ingestion feedback and publisher selection

**Last Updated**: 2026-10-25
**Level**: 5 - the clean-break replacement is authorized; declare its minimal contracts before logic in the same cohesive cutover.

**Status**: Documentation-first delivery is authorized. The complete
[planner ledger proposal](../docs/reference/feed-planner-ledgers.md) is the
durable review page for retained fields, old-to-new mappings, API inventory and
independent lookback windows. The coordinator must first verify this docs-only
change is merged into remote `main`; no implementation session starts before
that gate. Superseded compatibility and state work stays paused:
[#1737](https://github.com/miztiik/yen-idhazh/pull/1737) stays a draft at
`664e26fe5fe84ab00990a312ca1119a909d44ab0`, and superseded
[#1720](https://github.com/miztiik/yen-idhazh/pull/1720) stays paused.
This document delivers no runtime feature. The active execution sequence is
Table E and the replacement brief in Row 22; old compatibility, snapshot/head
and causal-score briefs are not executable.

## 0. Operating contract

### Table A - Intent and execution boundary

| Id | Field | Contract |
| --- | --- | --- |
| A1 | Why this plan exists | Replace the planner's storage and API/runtime paths with the [four-ledger design](../docs/reference/feed-planner-ledgers.md), then complete the remaining approved nonsemantic work from [Plan 66](20261020-66-feed-ingest-plan.md) without claiming worker publication from planner output. |
| A2 | Confirmed direction | User approval, 2026-10-25 UTC: make a clean break, delete the same eight named obsolete planner-family prefixes under both raw and compact roots, and replace the real API code with asynchronous typed-event execution and bounded concurrency. No old-to-new migrators, compatibility readers, aliases or dual writers. The seven-day component is a spend report, not a ranking penalty. |
| A3 | In scope | Row 22's atomic contracts/storage/API/runtime/cleanup cutover; remaining technical admission, restrictions/recovery, polling, publisher and configured-priority work in Table B, subject only to their unresolved policy decisions. Field lists, dates, windows and APIs are declared once in the [proposal](../docs/reference/feed-planner-ledgers.md). |
| A4 | Current readiness and first gate | First merge and verify this docs-only change on remote `main`. Then start Row 22 from that head; its contracts precede logic inside one cohesive PR. The earlier compatibility B2 design is not a prerequisite. Unresolved trial, polling and review decisions block only their affected work, not Row 22. |
| A5 | Strategy | User-directed replacement in the existing TypeScript code paths and shared ledger infrastructure. Order the cutover as minimal contracts/storage, including native format readers and compaction -> real event-driven API/runtime -> required old-writer/raw-and-compact-data/registry cleanup and integration, all in one PR where a split would leave an unused second implementation. Reuse bounded pools and share validated payloads; do not add a global all-runs queue or selection idempotency. |
| A6 | Execution | Execute per docs/how-to/execute-a-plan.md: one maintainer carries the plan and delegates a row where delegation pays; keep parallel N = 4 rows in flight, refilling a slot as soon as a worker returns and never waiting on a merge; consult a persona only where two answers would lead to different code; AUTO-merge on green gates; honor the ESCALATE triggers in section 0. |
| A7 | One execution queue | Table E is the only queue. Completed rows remain delivery records. Earlier per-row details are context unless the current queue explicitly dispatches them against the replacement contracts; never execute the superseded compatibility, snapshot or causal-score sequence. Row 29 removes obsolete duplicated prose later, not during this field review. |
| A8 | Remaining permission | Technical admission, earned recovery and polling are not completed by existing rest fields. D5 trial total-cost acceptance, polling formula and review policy remain unresolved; approved restriction/recovery thresholds remain pending implementation. Publisher identity stays curated and unknown matches stay unknown. Worker parity, production digest integration, Python producer/consumer migration and legacy health-page retirement remain deferred. |
| A9 | Scope and escalation | Data deletion is limited to the explicit Row 22 obsolete planner-family prefixes under both roots. New-family native shared-ledger persistence/readback/compaction support is permitted, not registration-only work. Other families' protocols/data, global Python `feed-health`, the Python news pipeline, historical corpus and Git history are unchanged. Stop only the affected work for a new persisted meaning outside the field proposal, a trust-boundary change, an unresolved policy decision, unrelated scope or the execution contract's cost-overrun trigger; the authorized clean break itself needs no new vote. |

### Table B - Original sixteen pending areas and the separate priority-review task

| Id | Area from the pending inventory | What remains | Delivery rows |
| --- | --- | --- | --- |
| B1 | Publisher identity | Naming documentation shipped in [#1691](https://github.com/miztiik/yen-idhazh/pull/1691). Runtime validation, catalog references, curated mappings and compatible recorded identities remain. | 1, 2, 3 |
| B2 | `/select-articles` | Read the complete server-owned parse batch by `batch_id`; screen and rank within one API, returning selected articles and exclusions. Continue through the partition and persistence APIs. Do not accept caller paths or require idempotency. | 1, 2, 8 |
| B3 | Publisher breadth | Apply a data-only soft exposure preference using confirmed publisher identities and existing numeric priority, not article-quality comparison. | 1, 9 |
| B4 | Common fetch/parse observations | Keep actual request counters and grouped outcomes from `/fetch`, `/parse` and `/plan`; replace per-operation persistence with the proposed batched health/run ledgers. | 22 |
| B5 | Article-level source rollups | Retain the proposed feed/day opportunity, selection, request and grouped rejection counts; do not confuse them with successful feed reads or publication. | 22 |
| B6 | Failure and cost attribution | Keep supported feed, pipeline and unknown attribution in grouped causes, with real request spend; remove causal request histories and the waste score. | 22 |
| B7 | Evidence definitions and support | Use the proposal's independent windows, actual units, denominators, completeness and null meanings; do not restore removed opportunity qualification or resource weights. | 22 |
| B8 | Durable next-run feedback | Preserve partial/failed-run counters, settle duplicate storage representations once, and let the next allocation read the bounded current-format health evidence without a snapshot/head cache. | 22 |
| B9 | Technical admission and trials | Use bounded article samples, report every attempted outcome and return review when support is insufficient. | 11 |
| B10 | Temporary access restrictions and recovery | Restrict only supported scope, permit due probes and require observed recovery. Permanent retirement remains curated. | 12 |
| B11 | Adaptive feed polling | Use exact-URL discoveries and actual poll costs before requesting a feed; preserve freshness and bounded exploration. | 13 |
| B12 | Conditional HTTP | Removed from this plan by maintainer ruling on 2026-10-24. Ordinary feed fetch behavior remains; no validators, cached-body state or `304` handling will be added here. | - |
| B13 | URL hygiene corrections | Correct structured host/path matching; separately review and approve identity-changing query cleanup and migrations. | 15, 16 |
| B14 | Operational review and integration | Distinguish source deterioration from pipeline release failures and prove the complete feedback-and-next-consumer flow. | 19 |
| B15 | Real Phase 2 outcomes | Join genuine worker/model costs, publication and leads through actual producer/consumer identities; do not substitute generated fixtures. | 17, 18 |
| B16 | Cache profiling and combined hosted proof | Adopt the implemented cache PR, review its final candidate, and complete the previously requested integrated proof. Actual hardware counters remain unmeasured when permission is denied. | 20 |
| B17 | Reusing curated editorial priorities | Review useful configured watchlist, theme and carrier-priority inputs from the Python path; implement only approved numeric terms from recorded evidence, without copying its selections or introducing qualitative analysis. | 21 |

### Table C - Explicit exclusions and their cost

| Id | Outside this plan's current permission | Cost of leaving it out | What would bring it in |
| --- | --- | --- | --- |
| C1 | Semantic quality scoring, factual verification, semantic novelty, story classification and new content deduplication | Selection cannot determine truth, importance, repeated meaning or new developments. Technical access and numeric priority do not answer those questions. | A separate maintainer-approved assessment design, controlled model destination and evaluation contract. |
| C2 | Automatic formula/weight promotion, taxonomy reassignment and qualitative drift controls | Operational estimates can update, but the system does not teach itself a new formula or editorial classification. | A separate policy-comparison and promotion plan with independent outcomes. |
| C3 | Removing the production worker's existing fetch and summarization behavior | The worker must still fetch and summarize assigned articles. The TypeScript plan must not silently replace those worker duties. | A separate maintainer-approved worker redesign. |
| C4 | Hard day-wide publisher quotas, equal-share obligations or selection blocking because history is missing | Breadth is a preference, not a guarantee. A prolific publisher can still supply multiple selected articles. | A separate maintainer decision changing the already confirmed soft-limit intent. |
| C5 | Automatic permanent retirement or a second retirement file/index | Runtime evidence can stop ordinary work temporarily, but cannot rewrite curated membership. | A separately approved catalog-transition authority; current retirement authority remains `config/sources.json`. |
| C6 | Local Python execution, Python packages in isolated TypeScript work, broad Python runtime changes, or new test functions without approval | Some native compatibility and downstream execution must be established by existing repository CI or a separately authorized integration. | An explicit scoped exception; shared declarations, migrations and binding compatibility remain subject to the existing approved boundary. |
| C7 | Raising host security privileges to obtain hardware counters | A stock runner may prove honest counter unavailability, not measured cache hits/misses. | An already-permitted operator-controlled Linux host; do not weaken kernel permissions. |
| C8 | Conditional feed requests, cached bodies, `304` handling and recovery | Feed polls may transfer the same body again, using more network bytes and time. | A separate maintainer-approved plan with a bounded cache and replay contract. |

### Table D - Required design decisions and stop conditions

| Id | Decision to settle | Required output before the affected build | Authority and affected rows |
| --- | --- | --- | --- |
| D1 | Publisher catalog and recorded identity | Settled: `publishers[]` has `id` and `display_name`; feeds have nullable `publisher_id`; no separate alias, reconciliation or provenance fields; IDs stay immutable. Reviewed config changes and Git history record mapping decisions. AI may help find publisher-owned evidence; uncertain mappings remain null. `added_on` is the UTC date first entered; new retirements have `retired_on` and an open lower-case `retirement_reason`; missing legacy values stay unknown. Old config without `publishers` reads as empty; missing values stay unknown; undefined nonnull references fail. Compatible-reader tests belong in Row 2; evidence-backed mapping data belongs in Row 3. | Contract settled by maintainer; Rows 2, 3, 9 deliver it. |
| D2 | Selection input and result | Keep the complete server-owned parsed batch and server-generated stage `batch_id`; repeated selection is not idempotency. Partition depends on that selection. Replace old persistence with the metadata-only selected ledger and text-bearing artifact in [Table B](../docs/reference/feed-planner-ledgers.md#b-selected-articles), without an alias for the old route. The configured article limit bounds output, not input. | Authorized direction; Row 22 declares current-format strict batches and implements the real routes. |
| D3 | Operational observations and estimates | Retain actual per-run/feed/day counters, grouped failure attribution and API/phase timings from proposal Tables C and D. Do not retain per-operation causal histories or invent CPU/memory costs. The request component is only a seven-closed-UTC-day spend report; unknown accounting is not zero. | User-directed simplification replaces the earlier qualification and component-weight design. Row 22. |
| D4 | Health ownership and settlement | Use the existing family and named raw/compact inputs for current-format rows. Batch one health file per run/UTC work day; preserve completed work on a later failure. Compute the bounded lookbacks once per run, share them in memory, and capture what selection used. Do not add snapshots, head files, revision chains, a fifth ledger or another summary API. Distinct actual work remains counted; duplicate storage representations do not. | Authorized cutover; exact field/window meanings remain in the proposal. Row 22, not paused Row 10. |
| D5 | Activation and work limits | A2 remains conditional: trial-only, up to 100 distinct articles from each non-overlapping age group `[24,36]`, `[12,24)`, `[6,12)`, `[2,6)`, `[0,2)` hours, fewer if unavailable; retries/redirects can exceed 500 HTTP requests. Persist each considered entry's selected, capped, unknown-age or future-age disposition. Maintainer ruling, 2026-10-25 UTC: pause an evidenced source/endpoint scope after 3 consecutive confirmed source-side failures within the configured window; known success resets the streak, unknown/pipeline outcomes neither count nor reset, and article refusal affects only that article. A 24-hour pause makes a check due for the next permitted planner run; time alone does not restore ordinary work. Recovery requires 3 consecutive successful checks across at least 2 UTC dates and >=80 percent known outcomes; confirmed source failure resets progress and starts a new 24-hour pause, while unknown/pipeline outcomes neither count as success nor reset. Schedule up to 20 recovery-check opportunities per planner run, at most 1 per source, oldest due first; ties by stable source ID then endpoint identity. This is not a request budget or ordinary-work cap. Recovery restores trial access, not catalog membership. These policies are not active until Row 12 contracts and implements them. A2 total-cost acceptance awaits the maintainer decision; configuration placement is undecided. Adaptive polling formula and review caller/cadence/authority remain unapproved. The feedback contract records the worker's additional implementation-cost finding. | C2-C5 policy approved, not active; A2 conditional on total-cost acceptance after telemetry. Polling/review remain unapproved. |
| D6 | Publisher exposure comparison | Settled 2026-10-24: use the approved 0.25 coefficient; count actual UTC-day publications plus current selections, divide by planned slots and cap at 1; known-empty history is zero, unavailable history uses current selections only and records the gap, and unknown publishers add no count; replace feed crowding rather than duplicate charging. | Approved; Row 9. |
| D7 | Conditional HTTP state | Removed by maintainer ruling on 2026-10-24. Conditional requests, validator state, cached bodies, `304` handling and cache-miss recovery are not required in this plan; see C8 for the cost and route to reconsideration. | Closed; no delivery row. |
| D8 | Request report versus ranking | Remove the qualified causal request-waste score and its selection penalty; do not replace it with a raw-cost penalty. Keep native feed-read reliability separate, with its existing configured window/floor and explicit missingness. | Confirmed report-only choice; proposal Tables C and L. Row 22 removes the superseded consumer rather than resuming Row 10. |
| D9 | Changed canonical URL identity | Bounded old/new comparison; encoding and repeated-query semantics; tracking policy; explicit equivalence and ambiguity rules; read-side migration and cross-language consumers. Approval of the matcher correction is not approval of this migration. | Separate Level-5 approval in Row 16. |
| D10 | Genuine downstream invocation | Deferred by maintainer clarification on 2026-10-24. Deliver the feed-to-dispatch-Parquet flow first. Worker parity, the production adapter, workflow cutover and real downstream evidence require a later decision. | Not a gate for the current flow; Rows 17 and 18 deferred. |
| D11 | New finding during execution | A new persisted meaning, trust-boundary crossing, unrelated repair, scope change or unsupported cost claim. | STOP-AND-SURFACE per [scope changes](../docs/how-to/handle-scope-change.md); do not relax a check or silently narrow delivery. |
| D12 | Reusing curated editorial priorities | Name each proposed watchlist, theme or carrier term, its recorded input, independent meaning, existing/new config maintainer and default, no-double-counting rule, score evidence and reader-before-writer sequence. Preserve unknown evidence; no front-page-vote bonus, semantic comparison or wholesale Python-ranking port is implicitly approved. | Maintainer approval after Row 21's bounded review; no new term before that approval. |
| D13 | Clean-break four-ledger replacement | Use the four formats in the [durable proposal](../docs/reference/feed-planner-ledgers.md), not the previous eight-ledger rename or snapshot/head design. Declare and validate contracts before logic within the same atomic PR; replace active TypeScript/native format readers, writers, compaction, routes and registration together; delete the same named obsolete planner-family prefixes under raw and compact roots. No migrators, compatibility readers, aliases or dual writers. | User approval, 2026-10-25 UTC. One cohesive Row 22 PR replaces old B1/B2/B3/B4 execution; the Python news pipeline and other families' protocols/data remain unchanged. |
| D14 | Lookback cost | Reuse the planned shared health operation and compute bounded lookbacks once per run. Captured reliability is not a freshness-safe future-run cache. Record actual `feed-health-summary` API/phase duration when implementation exists; no timing of the proposed format exists. Consider a persisted cache only if representative runner evidence justifies it, first in the existing health family. | Provisional implementation recommendation, not a measured speed claim or mandatory host/cache/profiler task. |

## 1. Status Reckoner

### Table E - Meaningful PR phases

| Id | # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| E1 | 1 | Settle remaining trial, polling and review policy | - | A | PENDING (does not block authorized Row 22) | - | - | - |
| E2 | 2 | Land compatible shared readers before writers | 1 | B | DONE | operational-score-contracts | [#1712](https://github.com/miztiik/yen-idhazh/pull/1712), [#1719](https://github.com/miztiik/yen-idhazh/pull/1719) | - |
| E3 | 3 | Implement curated publisher catalog references | 2 | C | DONE | publisher-catalog-support | [#1704](https://github.com/miztiik/yen-idhazh/pull/1704) | - |
| E4 | 4 | Wire common fetch and parse observations | 2 | D | DONE | persist-ingestion-observations | [#1717](https://github.com/miztiik/yen-idhazh/pull/1717) | - |
| E5 | 5 | Classify failure and work attribution | 4 | E | DONE | operational-request-evidence | [#1718](https://github.com/miztiik/yen-idhazh/pull/1718) | failure-attribution |
| E6 | 6 | Aggregate article delivery and request costs | 5 | F | DONE (typed planner report; saved state remains Row 10) | operational-request-evidence | [#1718](https://github.com/miztiik/yen-idhazh/pull/1718) | - |
| E7 | 7 | Compute supported operational estimates | 6 | G | DONE (report-only request estimate; no ranking change) | operational-score-contracts | [#1719](https://github.com/miztiik/yen-idhazh/pull/1719) | - |
| E8 | 8 | Deliver selection, partition and persistence APIs | - (authorized stage contracts included) | E | DONE | feed-ingest-feedback-selection | - | - |
| E9 | 9 | Apply the soft publisher-exposure preference | 8 | F | DONE (current-run + fallback; production linkage deferred) | publisher-exposure-preference | [#1714](https://github.com/miztiik/yen-idhazh/pull/1714) | - |
| E10 | 10 | Settle feedback and consume it in the next allocation | 7, 8 | H | PAUSED (superseded design; #1720 unmerged, latest gates fail) | operational-state-feedback | [#1720](https://github.com/miztiik/yen-idhazh/pull/1720) | dfff7386 |
| E11 | 11 | Report bounded technical admission trials | 22 | I | PENDING (D5 trial acceptance remains open) | - | - | - |
| E12 | 12 | Enforce temporary access restrictions and earned recovery | 11 | J | PENDING | - | - | - |
| E13 | 13 | Apply discovery evidence before feed polling | 12 | K | PENDING | - | - | - |
| E14 | 14 | Conditional HTTP (removed by maintainer ruling) | - | - | REMOVED | - | - | - |
| E15 | 15 | Correct structured host and path exclusions | - (matcher intent approved separately) | B | DONE | structured-url-exclusions | [#1703](https://github.com/miztiik/yen-idhazh/pull/1703) | 4985fe0e-ca49-4ad2-9aaa-cd31323d8c52; tests: fbf40c01-d984-48ef-b6a5-a75fb4afe74d |
| E16 | 16 | Review and migrate URL identity separately | 15 | L | PENDING | - | - | - |
| E17 | 17 | Prove dispatch-Parquet parity, then wire digest workers | 8 | A | DEFERRED | - | - | - |
| E18 | 18 | Connect actual downstream outcomes to the observer | 2, 10, 17 | M | DEFERRED | - | - | - |
| E19 | 19 | Review operational regressions and prove the live loop | 22, 9, 12, 13, 21 | N | PENDING (review policy remains open) | - | - | - |
| E20 | 20 | Adopt cache delivery and finish the combined hosted proof | - | Z | DONE | potential-fiesta | [#1671](https://github.com/miztiik/yen-idhazh/pull/1671), [#1707](https://github.com/miztiik/yen-idhazh/pull/1707) | 6a57ff1e-bdfc-4248-86f8-cd5b17c8bde2 |
| E21 | 21 | Review and reuse configured numeric priorities | 22, 9 | O | PENDING (bounded review complete; D12 approval pending) | - | - | - |
| E22 | 22 | Replace planner ledgers and APIs in one atomic cutover | - (docs must first be on remote main) | P | DONE (cutover delivered; coordinator merge pending) | four-ledger-planner-cutover | [#1740](https://github.com/miztiik/yen-idhazh/pull/1740) | 939acb2f |
| E23 | 23 | Migrate the feed-planning ledger family | 22 | P | COLLAPSED into Row 22; no compatibility phase | - | - | - |
| E24 | 24 | Incrementally update and read feed-health state | 22 | P | COLLAPSED into Row 22; no snapshot/cache phase | - | - | - |
| E25 | 25 | Remove redundant TypeScript state paths | 22 | P | COLLAPSED into Row 22; required cleanup is atomic | - | - | - |
| E26 | 26 | Migrate Python producers and consumers | 22 | Q | DEFERRED | - | - | - |
| E27 | 27 | Migrate the console to derived ledgers | 22 | Q | DEFERRED | - | - | - |
| E28 | 28 | Retire legacy feed-health publication | 26, 27 | R | DEFERRED | - | - | - |
| E29 | 29 | Remove obsolete duplicated planning and feedback prose | 22, affected 26-28 migrations | S | PENDING (after replacement contracts and consumer migration) | - | - | - |

Table E is the only execution queue. After the remote-main documentation gate,
the first implementation PR is Row 22: contracts/storage, real asynchronous
API/runtime cutover, and required old-writer/raw-and-compact-data/registry cleanup with
integration checks. These are ordered work packages within one cohesive PR,
not separately merged unused formats. Rows 23-25 are collapsed, not delivered.
Later PRs carry independent remaining approved capabilities in Rows 11-13 and
21, with only their named unresolved policies paused; Row 19 supplies the later
operational-loop proof. Rows 26-28 remain deferred. Row 29 is later prose
cleanup, not permission to remove this review's field mapping.

The following earlier delivery sequence is retained context, not executable
replacement work; current D3/D4/D8/D13 and Row 22 supersede it.
The earlier D3/D4 implementation sequence was Row 2 -> Row 4 -> Row 5 ->
Row 6 -> Row 7 -> Row 10. Row 2 lands compatible readers and contracts; Row 4
records all actual request and extraction work; Row 5 classifies supported
source, pipeline and unresolved causes; Row 6 aggregates article-linked
request totals and coverage; Row 7 computes the approved request-only score
when evidence qualifies; Row 10 publishes the derived per-source operational
state and makes the next selection consume the revision it read or its
approved stale fallback. Publisher IDs from Row 3 remain null until known and
do not block recording observations. A2 adds only a conditional, bounded
trial to Row 11 after the telemetry prerequisites in Rows 2, 4, 5 and 6. It
does not require Row 10's score consumer. Other D5 rules do not gate these
rows and must not restrict ordinary fetching.

Row 2 delivered publisher-identity support through PR #1704 and the registered
per-operation observation contract, its TypeScript reader binding, and
raw/compact fixture compatibility through merged PR #1712. Its operational
state, saved-score trace, compatible historical readers and registered legacy
state ledger are also complete; they did not add a state writer or
next-selector consumer. Row 10 remains paused under its superseded design.
Row 22 now replaces that design in the actual code paths under the approved
clean-break direction; its contracts precede logic within the atomic PR.

## 2. Shared implementation boundaries

These current boundaries and the Row 22 brief govern the replacement. The
earlier row details in sections 3-23 are retained context, not executable
compatibility/snapshot/causal-score briefs. Remaining pending capability rows
must use the replacement contracts and their current Table D policy gates;
their scope is not cancelled by retaining their old detail for Row 29 cleanup.

### Table F - Where the six I Feed input areas belong

| Id | Input area | Producer and consumer |
| --- | --- | --- |
| F1 | Publisher exposure | Curated catalog supplies identity; actual publication supplies past exposure; `/select-articles` records current selection and the soft adjustment. A feed ID or common corporate maintainer is not a publisher. |
| F2 | Article access and technical extraction | `/fetch` records transport/access facts; `/parse` records technical extraction and warnings; shared `/plan` units emit the same facts; rollups group article outcomes. This is not qualitative article assessment. |
| F3 | Requests, retries and attributable work | Fetch units record actual HTTP attempts, redirect/retry work, waits and measured costs. DNS validation is a separate operation, not an invented on-wire HTTP request. Parse and downstream workers record their own real work. Replays and API call counts are not new outbound requests. |
| F4 | Evidence identity, age, support and coverage | Every producer retains source/run/attempt/correlation, event identity, relevant UTC times and revisions; the estimator retains raw units, denominators, support, missingness and the exact decision cutoff. |
| F5 | Exact-URL discoveries and cadence | Feed parsing plus deterministic eligibility and bounded seen history produce distinct new eligible URL keys per completed permitted poll. The scheduler consumes them before the next feed fetch, not only after parsing. New URL does not mean new story. |
| F6 | Worker/model costs, publication and leads | Actual downstream execution and the publication observer supply these facts. Fetch/parse cannot manufacture token cost, model waste, successful publication or lead selection. |

### Table G - Contracts and preservation requirements

| Id | Boundary | Required implementation |
| --- | --- | --- |
| G1 | Existing components | Reuse the Plan 66 shared writer, safe fetcher, parser, screening, curation, partitioner, request replay and native history readers. Existing CPU/RAM/PID instruments and separate reliability penalty are not new builds. |
| G2 | Native authority | Shared persisted payloads remain Pydantic-owned under `backend/idhazh/contracts/`, with small bound TypeScript copies and dated versions/changelogs. The approved clean break requires no old planner-family migrators. Other families retain their existing behavior. The planner-only typed-event exception remains limited to that event stream. |
| G3 | Publisher identity | Follow [publisher identity](../docs/architecture/contracts/publisher-identity.md). `PublisherIdSchema` aliases `SlugSchema`; no runtime slug generation or inferred mappings. Old missing IDs remain unknown, not backfilled from today's catalog. |
| G4 | API placement | Follow the numbered API flow below. `/select-articles` owns both eligibility screening and ranking; there is no separate screening endpoint or caller-visible screening step. Selection, partitioning and persistence have schema-validated HTTP APIs backed by shared operations. `/plan` calls those same operations in order, without making HTTP requests to its own listener. |
| G5 | One selection input mode | Selection reads a complete server-owned parse batch through its approved run/batch identity. It does not accept article text, a caller path, a per-article ID list or require idempotency. `correlation_id` remains observation context, not a file locator. |
| G6 | Selection and partition result | One selected object produces the artifact and strict metadata-only Parquet projection in proposal Table B. Preserve selection order, work and worker assignment without mutating the shared object. The configured output limit does not cap input. Worker parity and production digest integration remain deferred. |
| G7 | Soft breadth | Count confirmed publishers, not feeds or stories. Use actual known publication exposure and current choices. Unknown day history falls back to current-run publisher exposure with an explicit unavailable status; unknown publishers are not distinct invented publishers. Do not add a hard day ceiling. |
| G8 | Observation independence | Distinct articles, allocated opportunities, HTTP attempts, polls and model time have different denominators. Retrying or replaying an article does not add an independent article vote. A nonallocated slot is not wasted; a model failure after usable extraction is not source-access failure. |
| G9 | Durable feedback | Save each run's actual health counters even when later work fails; aggregate daily views from those counters without summing captured reliability. Share the once-per-run bounded summary in memory. Unknown, missing, known empty and observed zero remain distinct; do not rebuild revision/snapshot machinery. |
| G10 | Bounded reads and state | Use named run inputs, configured periods and existing ledger indexes. Declare maximum catch-up and insufficient-state behavior. New registered state may represent temporary restrictions, but must not become another permanent-retirement authority. |
| G11 | Technical admission and recovery | Report all sampled attempts, successful extraction warnings and exclusions. Technical success does not establish news value. Restriction expiry permits a probe, not automatic recovery. HTTP 403 alone proves neither paywall nor publisher-wide failure. |
| G12 | Actual costs | Retain source, pipeline and unresolved attribution; keep shared startup/infrastructure costs separate. Optional unmeasured resource values stay null. Hardware-counter permission denial is not a measured zero. |
| G13 | Historical boundary | Preserve genuine first-sight meaning, actual UTC clocks and external exclusion inputs. Do not restamp historical artifacts, derive order from UUID suffixes, migrate old planner-family rows or alter other families. Only the explicit obsolete planner-family raw/compact reset is authorized. |
| G14 | New modules | Paths marked `(new)` below are proposed files, not claims that they exist. Row 22 declares the minimal contracts before logic within its atomic cutover; update its named footprint before dispatch if a required caller was missed. Add no empty scaffolding. |

### Numbered API flow and payload boundaries

The [proposal's API inventory](../docs/reference/feed-planner-ledgers.md#k-api-inventory)
distinguishes current routes from the replacement target. Row 22 updates the
owning operator API page with the implemented current-format requests/results;
its old dispatch and snapshot details do not constrain this clean break.

`/plan` consumes typed events through shared operations without HTTP loopback.
Fetch precedes parse, selection waits for its complete batch, and partitioning
preserves selected order while assigning workers. Independent work overlaps
within configured bounds. One server-owned `batch_id` names each current-format
stage output; it is neither correlation context nor a caller-supplied path.
Persistence emits the selected metadata and text-bearing artifact declared in
the proposal, with an explicit empty result or write error. Artifact production
is part of Row 22; worker parity and production digest consumption remain
deferred.

### Table H - Gate records and evidence already available

| Id | Gate or retained delivery | Required use |
| --- | --- | --- |
| H1 | Local selection | Use [run the gates](../docs/how-to/run-the-gates.md), inspect the shared selector, then run only relevant TypeScript checks and named existing cases. Extend recorded fixtures/cases; do not introduce local Python execution or a new test function through this plan. Record selected inputs and results. |
| H2 | CI | Full repository CI on the exact merge candidate remains authoritative. Shared declarations require native field/vocabulary bindings; other families retain their compatibility checks. Do not repeat an unchanged worker check or raise deadlines to buy a pass. |
| H3 | Contracts and readers before writers | Row 22 declares contracts and implements current-format readers before writers within its one atomic PR. No old planner-family compatibility reader or separate migration phase is required. |
| H4 | Existing live ingestion proof | [Run 40029996902](https://github.com/miztiik/yen-idhazh/actions/runs/40029996902) proves selected HTML/native planning; [run 40047886723](https://github.com/miztiik/yen-idhazh/actions/runs/40047886723) adds real task/resource evidence. Retain them; neither proves genuine reader publication. |
| H5 | Exposing CPU and memory metrics reports | [#1669](https://github.com/miztiik/yen-idhazh/pull/1669) merged visible resource reporting and independent machine RAM; [#1673](https://github.com/miztiik/yen-idhazh/pull/1673) merged real target-PID CPU and HTTP task lifecycle. Code is delivered, not another pending build. Row 20 closes the remaining combined checkbox-enabled hosted proof. |
| H6 | Cache adoption snapshot | Child reports final head `baa2431cb0d05936f3d107055d3b53e6b97315d7` and green [CI 40095745824](https://github.com/miztiik/yen-idhazh/actions/runs/40095745824). Coordinator review and the combined hosted proof are not yet complete. Refresh PR/head/checks and inspect artifacts before any merge. No child merge or dispatch is authorized. |
| H7 | Published surface | Only a row that changes the published site needs the integrated-browser smoke and relevant design review. Operator report changes still need actual Markdown rendering and sufficient unavailable/empty presentation, not a new dashboard. |
| H8 | Closure | Each row records its oracle, exact candidate and applicable results. Original component delivery, a generated audit, a documented decision, a green CI run and actual production integration are separate claims. Preserve open decisions instead of marking the overall plan complete. |

## 3. Row #1 - Settle remaining trial, polling and review policy

- **Scope:** Settle only the still-open D5 trial total-cost acceptance, adaptive-polling formula and operational-review caller/cadence/authority before their affected capabilities.
- **Level:** 5 for those unresolved policies; the clean-break Row 22 direction is already authorized and does not wait for this row.
- **Files touched:**
  - `docs/architecture/contracts/publisher-identity.md`
  - `docs/architecture/contracts/feed-ingest-feedback.md`
  - `docs/architecture/sources/feed-operator-api.md`
  - `docs/architecture/sources/feed-curation.md`
  - `docs/architecture/sources/i-feed.md`
- **Acceptance gates:** Local: bounded named-link/anchor checks and ASCII/whitespace; no application suite for a documentation-only decision. CI: documentation-selected checks. Record each unresolved policy's input, default, actual authority and cost on its living page. Preserve already approved restriction/recovery thresholds, the report-only request component and all three window meanings. Do not restart old arithmetic, state revisions or migration work.
- **Oracle:** For each newly settled policy, a recorded fixture and its configured values determine the permitted action without an invented threshold or authority; this does not prove long-term effectiveness or complete its implementation.

### Table I - Decisions

| Id | Decision | Authority |
| --- | --- | --- |
| I1 | Only an unresolved policy needs a new decision; the documentation-first clean break and replacement runtime are already authorized. | Current user direction and Table D. |

### Table J - Rejected alternatives

| Id | Option | Why rejected | Cost to take | Authority |
| --- | --- | --- | --- | --- |
| J1 | Guess thresholds or payloads while implementing | Gives different workers different policies and silently expands approval. | Price and review the proposed defaults, fixture consequences and migration first. | CLAUDE.md sections 0d and 6. |

## 4. Row #2 - Land compatible shared readers before writers

- **Scope:** Implement only approved native declarations, bound copies, migrations and compatible readers needed by later rows. The new stage-snapshot subset is declared with its first real reader/writer in the authorized Row 8 API phase; this row retains the broader publisher and feedback contracts.
  The publisher-identity subset (shared source snapshot field, native declaration, versioned historical readers and binding checks) landed in PR #1704. Saved-batch APIs were delivered separately; their readers migrate old saved batches without inventing identity.
  PR #1712 delivered the registered per-operation observation contract, its TypeScript reader binding and raw/compact fixture compatibility. This phase declares the operational-state row and read-result shapes, the saved-score trace, their TypeScript copies, compatible migrations, and the registered raw/compact state ledger. It adds no state writer or live state consumer; Row 10 owns those behaviors.
- **Level:** 5; the approved Row 1 field/type table is mandatory.
- **Files touched:**
  - `backend/idhazh/contracts/feed_ingest_candidate.py`
  - `backend/idhazh/contracts/feed_ingest_article_assessment.py`
  - `backend/idhazh/contracts/feed_ingest_dispatch.py`
  - `backend/idhazh/contracts/feed_ingest_editorial_selection.py`
  - `backend/idhazh/contracts/feed_ingest_rejection.py`
  - `backend/idhazh/contracts/feed_ingest_source_run.py`
  - `backend/idhazh/contracts/feed_health.py`
  - `backend/idhazh/contracts/planner_operation.py`
  - `backend/idhazh/contracts/feed_ingest_observations.py` (new; persisted per-operation Parquet rows, not a second planner event contract)
  - `backend/idhazh/contracts/feed_ingest_feedback.py` (new)
  - `backend/idhazh/contracts/feed_ingest_candidate.py`
  - `backend/idhazh/contracts/feed_ingest_editorial_selection.py`
  - `backend/idhazh/contracts/feed_ingest_article_assessment.py`
  - `backend/idhazh/contracts/feed_ingest_dispatch.py`
  - `backend/idhazh/contracts/planner_stage.py`
  - `backend/idhazh/contracts/planner_stage.py` (authorized stage subset)
  - `packages/common-contracts/src/schemas/source.schema.ts`
  - `packages/common-contracts/src/schemas/candidate.schema.ts`
  - `packages/common-contracts/src/schemas/article-assessment.schema.ts`
  - `packages/common-contracts/src/schemas/dispatch.schema.ts`
  - `packages/common-contracts/src/schemas/editorial-selection.schema.ts`
  - `packages/common-contracts/src/schemas/rejection.schema.ts`
  - `packages/common-contracts/src/schemas/source-run.schema.ts`
  - `packages/common-contracts/src/schemas/event.schema.ts`
  - `packages/common-contracts/src/schemas/feed-health.schema.ts`
  - `packages/common-contracts/src/schemas/planner-operation.schema.ts`
  - `packages/common-contracts/src/schemas/ingest-observations.schema.ts` (new)
  - `packages/common-contracts/src/schemas/feed-ingest-feedback.schema.ts` (new)
  - `packages/common-contracts/src/schemas/planner-stage.schema.ts` (new; authorized stage subset)
  - `packages/common-contracts/src/index.ts`
  - `packages/common-contracts/src/schemas/config.schema.ts`
  - `packages/common-contracts/test/schema-binding.ts`
  - `packages/common-contracts/test/rejection.test.ts`
  - `config/ledgers.json`
  - `config/idhazh_gardener.json`
  - `config/gardener/compact-feed-ingest-plan-operational-state.json` (new)
  - `backend/idhazh/contracts/ledger_name.py`
  - `backend/idhazh/ledger/keys.py`
  - `backend/idhazh/ledger/raw_files.py`
  - `backend/idhazh/ledger/staging.py`
  - `backend/tests/ledger/test_feed_ingest_ledgers.py`
  - `packages/common-contracts/src/version.ts`
  - `services/feed-ingest-plan/src/read-ledger-history/encode-historical-record.ts`
  - `services/feed-ingest-plan/src/metrics/audit-contracts.ts`
  - `services/feed-ingest-plan/src/read-ledger-history/encode-historical-record.ts`
  - `services/feed-ingest-plan/src/metrics/audit-contracts.ts`
  - `backend/tests/contracts/test_curated_registries.py`
  - `backend/tests/contracts/test_feed_ingest_contracts.py`
  - `services/feed-ingest-plan/test/harvest.test.ts`
  - `services/feed-ingest-plan/test/plan-engine.test.ts`
  - `services/feed-ingest-plan/test/ledger-history.test.ts`
  - `tests/fixtures/feed-ingest-operational-state/qualified.json` (new)
  - `docs/architecture/contracts/feed-ingest-feedback.md`
- **Acceptance gates:** Local: common-contract and service type checks; recorded harvest, planner and ledger-history cases using named schemas and real Parquet. Bind `SourceSnapshot`, feed-health, operational-state and score-trace fields to their native Pydantic shapes; prove historical publisher identity and exposure survive migrations and stale fallback retains its original evidence window. Register the operation-row and operational-state ledgers for raw writing, compaction and indexed reading. Keep the planner-only `event.schema.ts` TypeScript-owned; Pydantic and TypeScript contracts define persisted Parquet observations, not a duplicate event stream. CI: existing native binding and historical compatibility gates. Do not emit derived state or change selection ranking in this phase.
- **Oracle:** Existing historical rows and request receipts retain their original evidence and readable identity, while current approved shapes reject invalid combinations; this cannot prove that future writers capture real observations.

### Table K - Decisions

| Id | Decision | Authority |
| --- | --- | --- |
| K1 | Missing old publisher, cost and feedback fields migrate to explicit unknown; existing nested types and required fields remain strict. Version every affected enclosing persisted payload, not only its shared child. | Row 1 approval and native schema ownership. |

### Table L - Rejected alternatives

| Id | Option | Why rejected | Cost to take | Authority |
| --- | --- | --- | --- | --- |
| L1 | A new TypeScript-only persisted-state exception | The existing exception covers planner events only. | Separate maintainer approval and updated native ownership/binding design. | CLAUDE.md Guardrail 3. |

## 5. Row #3 - Implement curated publisher catalog references

- **Scope:** Load publisher definitions and explicit feed references, validate them and capture identity in new source snapshots, feed-health rows, events and audit rows without changing historical meaning. Test mappings use recorded inputs only; no unsupported mapping is added to the live catalog.
- **Level:** 3 after approved declarations; changed catalog authority returns to Row 1.
- **Files touched:**
  - `config/sources.json`
  - `backend/idhazh/contracts/sources.py`
  - `services/feed-ingest-plan/src/harvest-feeds/load-harvest-inputs.ts`
  - `services/feed-ingest-plan/src/resolve-planning-inputs.ts`
  - `backend/idhazh/stages/plan.py`
  - `services/feed-ingest-plan/src/metrics/audit-contracts.ts`
  - `services/feed-ingest-plan/src/publisher-catalog.ts` (new)
  - `services/feed-ingest-plan/test/harvest-recordings.ts`
  - `services/feed-ingest-plan/test/plan-recordings.ts`
  - `services/feed-ingest-plan/test/harvest.test.ts`
  - `services/feed-ingest-plan/test/plan-engine.test.ts`
  - `docs/architecture/contracts/publisher-identity.md`
  - `docs/architecture/sources/i-feed.md`
  - `tests/fixtures/curated-registries/sources.json`
- **Acceptance gates:** Strict type checks and the existing native source-config, recorded harvest and planner cases. Prove valid shared references, duplicate and undefined-ID rejection, empty-registry legacy reads, fingerprint change on assignment, and identity through planning, observations and audit. The live registry remains empty because no current feed mapping had sufficient publisher-owned evidence; fixture mappings are not production assignments.
- **Oracle:** Changing a publisher display name or domain does not change its ID, while duplicate definitions and undefined references fail; this cannot verify editorial identity without curated provenance.

### Table M - Decisions

| Id | Decision | Authority |
| --- | --- | --- |
| M1 | Reuse the approved slug contract and explicit catalog review. Preserve distinct editorial publications under common ownership. Curate only confirmed mappings; leave uncertainty unknown. | Publisher identity contract and maintainer-approved D1. |

### Table N - Rejected alternatives

| Id | Option | Why rejected | Cost to take | Authority |
| --- | --- | --- | --- | --- |
| N1 | Infer all mappings from feed prefixes, titles or domains | Valid spelling does not prove one newsroom, and wrong grouping corrupts exposure. | Human review of the disputed identities and explicit reconciliation of recorded meaning. | Maintainer's curated-identity decision. |

## 6. Row #4 - Wire common fetch and parse observations

The producer phase wires real standalone fetch/parse and plan harvest work
into the registered native writer. Completed fetches save ordered attempt
facts and outcomes; parse units save before later planning. Handled fetch
exceptions retain completed attempts, while hard process kills do not prove
export coverage. Standalone replay does not repeat actual work, including
after a surfaced telemetry-save failure. Exact hosted output manifests include
the new native files. Attribution remains unresolved until Row 5; this phase
adds no waste aggregation, score, derived-state consumer, restriction or live
dispatch. The complete parsed-batch snapshot already retains candidates and
rejections through the existing stage API path; this phase does not replace it.

- **Scope:** Capture approved actual-work facts in the shared units used by both standalone APIs and `/plan`. Write one complete server-owned parse-batch output per correlation ID for Row 8.
- **Level:** 3.
- **Files touched:**
  - `services/feed-ingest-plan/src/api/document-operations.ts`
  - `services/feed-ingest-plan/src/harvest-feeds/feed-client.ts`
  - `services/feed-ingest-plan/src/harvest-feeds/robots-policy.ts`
  - `services/feed-ingest-plan/src/harvest-feeds/harvest-pool.ts`
  - `services/feed-ingest-plan/src/ingest-observations.ts` (new)
  - `services/feed-ingest-plan/test/harvest.test.ts`
  - `services/feed-ingest-plan/test/plan-api.test.ts`
  - `services/feed-ingest-plan/test/parse-batch.test.ts` (new)
  - `docs/architecture/sources/feed-operator-api.md`
  - `docs/architecture/sources/feed-harvesting.md`
- **Acceptance gates:** Local: recorded transport/parse/API cases cover successful, failed, malformed, empty, refused, not-attempted and interrupted work; verify one complete parse-batch artifact preserves every result for its correlation ID. Persist per-operation Parquet observations as each unit completes, before a later plan stage can fail; count actual dispatched requests from the feed-client path, with API validation, robots and target requests kept distinct. CI: ingestion integration and native compatibility.
- **Oracle:** Equivalent real fixture work through `/plan` and separate fetch/parse units produces the same causal facts, while completed replay adds no work or observations; this cannot prove current external source access.

### Table O - Decisions

| Id | Decision | Authority |
| --- | --- | --- |
| O1 | Reuse existing retries, request durations, technical extraction and task-profile readings. Resource collection remains independently optional; missing readings stay unavailable. | Approved D3 and existing operator/profiling contracts. |

### Table P - Rejected alternatives

| Id | Option | Why rejected | Cost to take | Authority |
| --- | --- | --- | --- | --- |
| P1 | Count API calls, replay or DNS validation as outbound HTTP work | Produces false denominators and duplicate costs. | Change the metric's declared unit and every reader; it would no longer answer actual-request efficiency. | Approved observation definitions. |

## 7. Row #5 - Classify failure and work attribution

The shared document-work producer now records supported source, pipeline or
unresolved attribution while preserving each factual cause code. A typed
target refusal is not a paywall claim or a publisher-wide finding.
Existing extraction outcomes, not new quality tests, determine technical
failure. Only typed empty-content extraction supports source attribution;
missing root/title and HTTP 408/429 remain unresolved. Target HTTP refusal
does not establish a paywall or publisher-wide failure.
Arbitrary network, timeout, server and unknown failures stay
unresolved. No CPU or private-memory attribution is claimed.

- **Scope:** Attach supported source, pipeline or unresolved attribution to recorded outcomes and costs without discarding unknown causes.
- **Level:** 3.
- **Files touched:**
  - `services/feed-ingest-plan/src/attribute-ingest-outcomes.ts` (new)
  - `services/feed-ingest-plan/src/ingest-observations.ts`
  - `services/feed-ingest-plan/test/harvest-safety.test.ts`
  - `services/feed-ingest-plan/test/article-assessments.test.ts`
  - `tests/fixtures/feed-ingest-plan/ingest-outcomes.json` (new)
  - `docs/architecture/sources/feed-failure-diagnostics.md`
- **Acceptance gates:** Local: extend existing cases with source refusal, shared extractor failure, infrastructure failure, usable extraction followed by model failure, retries and unresolved evidence; strict types. CI: same cases and contract checks.
- **Oracle:** Moving a failure from supported source evidence to a pipeline cause changes attribution, not the measured work, and removes the unsupported source penalty contribution; this cannot diagnose every live failure automatically.

### Table Q - Decisions

| Id | Decision | Authority |
| --- | --- | --- |
| Q1 | Attribute only what the evidence supports. Keep shared startup and infrastructure costs visible without dividing them arbitrarily among feeds. | I Feed component evidence and approved D3. |

### Table R - Rejected alternatives

| Id | Option | Why rejected | Cost to take | Authority |
| --- | --- | --- | --- | --- |
| R1 | Treat every failed summary or HTTP 403 as source misconduct/paywall | Confuses our failures, access restrictions and confirmed paywalls. | Obtain the missing causal or scoped access evidence first. | Maintainer's technical-only boundary. |

## 8. Row #6 - Aggregate article delivery and request costs

The planner reads the configured closed-UTC-day window from registered
raw/compact observations and returns typed article evidence in its report.
It does not require a successful final source-run record. Aggregation settles
replays across writer attempts, replaces corrections and refuses tied
revisions. Distinct article support, measured request coverage and scoped
source waste remain separate from retries, feed polls and unlinked work.
Known totals and lower bounds stay distinct; missing coverage and zero
opportunity denominators remain unknown.
Complete request censuses and resolved technical outcomes are counted
separately. Their intersection supplies measured request/waste totals and
coverage without requiring every opportunity to be measured. Native readback
covers 20 of 25 measured opportunities (80 percent), lower coverage and
successful recovery without calling the opportunity failed.

This increment does not save a second rollup or calculate a score. Row 7
still owns score qualification/arithmetic; Row 10 owns the registered
derived-state payload, concurrent publication and next-selector consumer.
Restrictions, trials, polling, worker integration and live dispatch remain
outside this increment.

- **Scope:** Produce bounded per-source and, where explicitly known, publisher rollups from actual article opportunities and attributed work.
- **Level:** 3.
- **Files touched:**
  - `services/feed-ingest-plan/src/rollup-ingest-outcomes.ts` (new)
  - `services/feed-ingest-plan/src/metrics/source-run-summary.ts`
  - `services/feed-ingest-plan/test/source-run-summary.test.ts`
  - `services/feed-ingest-plan/test/metrics.test.ts`
  - `tests/fixtures/feed-ingest-plan/ingest-outcomes.json`
  - `docs/architecture/contracts/feed-ingest-feedback.md`
- **Acceptance gates:** Local: existing metric cases cover distinct articles, reserved versus unallocated opportunities, repeated reports, retry counts, mixed attribution, unknown publishers and zero exposure; verify registered raw/compact operation-row readback with real Parquet. CI: metrics and binding gates.
- **Oracle:** Repeating an identical article report does not add article support, while a genuine extra HTTP attempt adds request cost; this cannot establish semantic usefulness or factual truth.

### Table S - Decisions

| Id | Decision | Authority |
| --- | --- | --- |
| S1 | Keep raw numerators, denominators and availability. Zero model work does not produce perfect model efficiency; RSS success is not article-access success. | I Feed component evidence and approved D3. |

### Table T - Rejected alternatives

| Id | Option | Why rejected | Cost to take | Authority |
| --- | --- | --- | --- | --- |
| T1 | Average daily percentages or treat retries as independent articles | Changes the exposure unit and gives repeated work extra evidence. | Recompute from the approved weighted numerators/denominators and distinct keys. | Approved metric definitions. |

## 9. Row #7 - Compute supported operational estimates

- **Scope:** Calculate the approved requests-first operational estimate from Row 6's measured request totals, distinct measured opportunities and coverage, and expose it in the actual planner report. Use configured support/coverage defaults; unavailable CPU and private-memory components stay neutral without weight redistribution. Keep this report-only: do not persist derived state or change ranking. Broader age/priors/decay behavior and selector consumption are not part of this phase.
- **Level:** 3 after D3/D8 approval.
- **Files touched:**
  - `config/feed-ingest-plan.json`
  - `packages/common-contracts/src/schemas/config.schema.ts`
  - `services/feed-ingest-plan/src/estimate-operational-feedback.ts` (new)
  - `services/feed-ingest-plan/src/run-feed-plan.ts`
  - `services/feed-ingest-plan/test/metrics.test.ts`
  - `services/feed-ingest-plan/test/history-window.test.ts`
  - `docs/architecture/sources/i-feed.md`
  - `docs/architecture/contracts/feed-ingest-feedback.md`
- **Acceptance gates:** Local: existing planner and ledger-history cases cover exactly 20/25 measured support, below-threshold support/coverage, zero or unknown request totals, missing coverage, the one-third maximum and report visibility from real bounded ledger evidence. CI: common-contract bindings, strict TypeScript checks and planner/ledger-history cases.
- **Oracle:** A fully wasted qualified request component contributes no more than its configured one-third weight; missing or unqualified evidence remains neutral, and the report does not alter selection. This cannot prove calibrated thresholds or editorial improvement.

### Table U - Decisions

| Id | Decision | Authority |
| --- | --- | --- |
| U1 | Preserve the measured request numerator, denominator, opportunity support and coverage separately. Keep unavailable components neutral; do not infer quality from word count or resource cost. | Approved requests-first D8 scope. |

### Table V - Rejected alternatives

| Id | Option | Why rejected | Cost to take | Authority |
| --- | --- | --- | --- | --- |
| V1 | Renormalize the request weight when CPU or private-memory evidence is absent | Makes the single available component stronger because unrelated measures are unavailable. | Wait until those measures have source-attributed evidence, then use the already approved equal component weights. | Approved requests-first D8 scope. |

## 10. Row #8 - Expose the independent `POST /select-articles` API

- **Scope:** Deliver the selection, partition and persistence APIs in the numbered API flow. `/select-articles` combines eligibility screening and ranking behind one endpoint; `/plan` calls that shared operation, then the partition and persistence operations. Read the complete server-owned parse batch by its approved run/batch identity. Do not add a separate screening endpoint, idempotency, count-based input splitting or response fields that break existing format parity.
- **Level:** 3.
- **Files touched:**
  - `services/feed-ingest-plan/src/api/routes/stages.route.ts` (new)
  - `services/feed-ingest-plan/src/api/selection-operation.ts` (new)
  - `services/feed-ingest-plan/src/api/partition-operation.ts` (new)
  - `services/feed-ingest-plan/src/api/persistence-operation.ts` (new)
  - `services/feed-ingest-plan/src/api/stage-response.schema.ts` (new)
  - `services/feed-ingest-plan/src/api/stage-store.ts` (new)
  - `services/feed-ingest-plan/src/api/server.ts`
  - `services/feed-ingest-plan/src/select-articles.ts` (new)
  - `services/feed-ingest-plan/src/resolve-planning-inputs.ts` (new)
  - `services/feed-ingest-plan/src/run-feed-plan.ts`
  - `services/feed-ingest-plan/src/harvest-feeds/harvest-types.ts`
  - `services/feed-ingest-plan/src/metrics/metrics-recorder.ts`
  - `services/feed-ingest-plan/src/seal-article-ledger/plan-sealer.ts` (removed; replaced by shared operations)
  - `services/feed-ingest-plan/test/plan-api.test.ts`
  - `services/feed-ingest-plan/test/plan-engine.test.ts`
  - `services/feed-ingest-plan/test/stage-api-cases.ts` (new helper; extends existing API case)
  - `docs/architecture/sources/feed-operator-api.md`
- **Acceptance gates:** Local: the existing API integration case exercises combined screening/selection over a whole parse batch, per-item failures, missing batch, run/configuration mismatch and existing output parity. Its stage helper also covers 205 generated inputs with a one-article output limit, unchanged ranks, empty output, restart, invalid saved context, damaged assignments and a genuine dispatch-directory write failure. The full planner produces registered dispatch Parquet read by the native TypeScript reader. Service checks and selected API/engine/metric cases passed; the 22 isolated adapter cases and native verifier passed. The contract agent's 61 shared cases and check passed. CI remains authoritative for Python binding and full merge-candidate coverage. No local Python ran.
- **Oracle:** The same validated candidate set and context produce identical unsharded selections through the new API and `/plan`; this cannot prove publication or worker consumption.
- **Closure evidence:** Candidate `776fd5d72b37981ce09d605fd30abb0fcc70e1ac` passed all five jobs in [CI run 40126606533](https://github.com/miztiik/yen-idhazh/actions/runs/40126606533), including native field/type/vocabulary binding, named fixture round trips, full backend coverage and the real TypeScript stage/API suites. This closes only the authorized API phase. The broader Row 1/2 feedback contracts and deferred worker integration remain open.

### Table W - Decisions

| Id | Decision | Authority |
| --- | --- | --- |
| W1 | Read one complete server-owned parse batch by `batch_id`; process all results in one selection call. Do not pass article lists or paths. `correlation_id` groups observations and does not locate the file. | Maintainer-authorized delivery; exact stage contracts in the owning API documentation. |
| W2 | Use one correlation ID for the batch and distinct event IDs for recorded events. Apply the existing 100-article limit only to selection output. | Maintainer direction; preserve existing observation and selection contracts. |
| W3 | Keep item-level failures in the batch and existing exclusion shapes; continue with usable results. A missing batch returns 404; damaged stored content returns 500. | Maintainer direction and authorized API error contract. |
| W4 | Do not require idempotency or a replay key for selection. Preserve existing selection rows and return a new saved result identity for each call. | Maintainer direction; shared schemas and API integration coverage. |
| W5 | Screening and ranking are internal parts of `/select-articles`, not separate caller-visible steps. The numbered API diagram has moved to the owning API page and is linked above. | Maintainer direction, 2026-10-24 UTC. |

### Table X - Rejected alternatives

| Id | Option | Why rejected | Cost to take | Authority |
| --- | --- | --- | --- | --- |
| X1 | Arbitrary file paths or a second selector hidden inside the route | Crosses the trust/input boundary or causes API/planner behavior to drift. | A separate approved file capability or algorithm change; neither is needed for this API. | Existing operator API and maintainer scope. |

## 11. Row #9 - Apply the soft publisher-exposure preference

- **Delivery provenance:** PR [#1714](https://github.com/miztiik/yen-idhazh/pull/1714)
  delivers the current-run publisher replacement and approved history fallback,
  not full actual-publication integration. The isolated selector replaces feed crowding with
  confirmed publisher exposure using the approved coefficient and planned-slot
  normalizer. Current selections, unknown identities, known-empty history and
  unavailable-history fallback are implemented. Strict named-day native readers
  require actual published membership and unambiguous recorded run/source/URL
  identity; fixture readback is not production integration proof. Production
  publication does not currently retain the original isolated planner identity,
  so its nonempty publisher history remains unavailable. The actual downstream
  identity link remains deferred under Rows 17/18. No mappings, day ceiling,
  worker integration or separate lookup index are added.
- **Scope:** Replace the approved feed-crowding term with the agreed publisher-exposure adjustment while preserving the existing numeric base and distinct operational penalty.
- **Level:** 3 after D6 approval; a changed score meaning returns to its native-contract maintainer.
- **Files touched:**
  - `config/feed-ingest-plan.json`
  - `services/feed-ingest-plan/src/curate-article-portfolio/mmr-portfolio.ts`
  - `services/feed-ingest-plan/src/curate-article-portfolio/publisher-exposure.ts` (new)
  - `services/feed-ingest-plan/src/read-ledger-history/read-daily-publication.ts`
  - `services/feed-ingest-plan/src/metrics/article-assessments.ts`
  - `services/feed-ingest-plan/test/curate.test.ts`
  - `services/feed-ingest-plan/test/article-assessments.test.ts`
  - `docs/architecture/sources/feed-curation.md`
- **Acceptance gates:** Local: recorded portfolio cases cover two feeds of one publisher, unequal known exposure, current-run fallback, unknown ID/history, known empty publication and coefficient substitution; native decision replay. CI: curation/assessment and historical compatibility.
- **Oracle:** Varying only confirmed publisher exposure changes only the approved soft term and resulting numeric choices, without hard rejection or rewritten base evidence; this cannot decide which story is journalistically stronger.

### Table Y - Decisions

| Id | Decision | Authority |
| --- | --- | --- |
| Y1 | Use actual known published exposure, not unpublished shadow selections. Unknown history never blocks selection or becomes invented zero history. Record the replaced term so the same crowding is not charged twice. | Maintainer's soft, data-only publisher-breadth decision and D6. |

### Table Z - Rejected alternatives

| Id | Option | Why rejected | Cost to take | Authority |
| --- | --- | --- | --- | --- |
| Z1 | Hard day cap or keeping the supposedly stronger story | Both change the approved intent; the latter adds unavailable qualitative assessment. | New maintainer-approved quota or assessment design and its reader trade-offs. | Maintainer clarification of 2026-10-24 UTC. |

## 12. Row #10 - Settle feedback and consume it in the next allocation

- **Scope:** Close the durable operational loop with concurrent observation settlement, fresh-base derived-state publication and an actual next-run allocation consumer, not report-only estimates.
- **Current state:** Paused. PR #1720 is open and unmerged; its latest `gates` check failed. Its current design is superseded by Rows 22-25. Preserve existing work for compatibility review, but do not mark this row complete.
- **Level:** 3 after Row 22 settles the compatible API and settlement contract.
- **Files touched:**
  - `config/ledgers.json`
  - `config/feed-ingest-plan-service.json`
  - `services/feed-ingest-plan/src/config/service-settings.ts`
  - `services/feed-ingest-plan/src/settle-ingest-feedback.ts` (new)
  - `services/feed-ingest-plan/src/read-ingest-feedback.ts` (new)
  - `services/feed-ingest-plan/src/run-feed-plan.ts`
  - `services/feed-ingest-plan/src/curate-article-portfolio/quality-decoupler.ts`
  - `services/feed-ingest-plan/test/plan-engine.test.ts`
  - `services/feed-ingest-plan/test/logical-completion.test.ts`
  - `docs/architecture/contracts/feed-ingest-feedback.md`
- **Acceptance gates:** Local: existing generated-run/recorded cases cover duplicate settlement, correction, delayed arrival, failed/partial runs, failed commit, overlap, latest-data lookup, incompatible state and bounded insufficient catch-up. CI: actual two-decision integration and native state readback.
- **Oracle:** A later allocation names and uses a compatible committed state revision changed by one settled source outcome, while replay settles it zero additional times; this cannot claim use of an unfinished predecessor or facts lost before export.

### Table AA - Decisions

| Id | Decision | Authority |
| --- | --- | --- |
| AA1 | Preserve pinned code/policy while reading latest compatible data. Qualified operational priority replaces the approved existing source term; unavailable evidence follows the approved explicit fallback, not an extra penalty. | Approved D4/D8. |

### Table AB - Rejected alternatives

| Id | Option | Why rejected | Cost to take | Authority |
| --- | --- | --- | --- | --- |
| AB1 | Write reports only, replay lifetime history, or reset restrictions on missing state | Does not deliver next-run adaptation, grows read cost, or silently removes a safety decision. | Build the bounded checkpoint/recovery contract and actual consumer before calling the loop complete. | I Feed next-run contract. |

## 13. Row #11 - Report bounded technical admission trials

- **Scope:** After the approved telemetry path in Rows 2, 4, 5 and 6 is delivered, implement A2's conditional age-group trial if its total config/code cost is acceptable. Select up to 100 distinct articles per non-overlapping age group `[24,36]`, `[12,24)`, `[6,12)`, `[2,6)`, `[0,2)` hours; retries and redirects can raise HTTP requests above 500 across the five groups. Persist each considered entry's disposition, including selected, excluded by the group cap, unknown age and future publication time. Record all actual trial work. Do not cap ordinary work, all-work telemetry, selection input or the existing 100-item selected output.
- **Level:** 3, conditional on total cost after telemetry; other Row 11 admission rules wait for D5 approval.
- **Files touched:**
  - `config/feed-ingest-plan.json`
  - `packages/common-contracts/src/schemas/config.schema.ts`
  - `packages/common-contracts/test/config.test.ts`
  - `services/feed-ingest-plan/src/harvest-feeds/harvest-pool.ts`
  - `services/feed-ingest-plan/test/harvest.test.ts`
  - Existing per-operation observation contract and registered writer from Rows 2 and 4
- **Acceptance gates:** Local: existing cases cover non-overlapping age boundaries, unknown and future ages kept ungrouped, group-cap disposition, fewer-than-100 cohorts and complete actual request/extraction outcomes. CI: trial-to-Parquet integration after Row 6, without changing ordinary selection or catalog membership.
- **Oracle:** Each known-age trial article belongs to at most one group; every actual request is recorded; this cannot establish qualitative news value or grant catalog membership.

### Table AC - Decisions

| Id | Decision | Authority |
| --- | --- | --- |
| AC1 | Trial authorization and budgets are explicit. Reuse safe fetch/parse and production observations; a technical verdict does not silently change a draft or retired catalog entry to active. | Approved D5 and catalog authority. |

### Table AD - Rejected alternatives

| Id | Option | Why rejected | Cost to take | Authority |
| --- | --- | --- | --- | --- |
| AD1 | Any-one-success admission | Fails the named mostly-blocked-feed case and hides sampling support. | Maintainer approval to accept that reduced evidence standard and its wasted-request risk. | I Feed first-delivery intent. |

## 14. Row #12 - Enforce temporary access restrictions and earned recovery

- **Scope:** Apply approved temporary restrictions to ordinary work and use due permitted probes and fresh evidence for recovery.
- **Level:** 3; D4 behavior and C2-C5 are approved, but Row 12 still needs the policy-state contract and enforcement implementation.
- **Files touched:**
  - `services/feed-ingest-plan/src/source-access-policy.ts` (new)
  - `services/feed-ingest-plan/src/settle-ingest-feedback.ts`
  - `services/feed-ingest-plan/src/read-ingest-feedback.ts`
  - `services/feed-ingest-plan/src/harvest-feeds/harvest-pool.ts`
  - `services/feed-ingest-plan/test/harvest-safety.test.ts`
  - `services/feed-ingest-plan/test/plan-engine.test.ts`
  - `docs/architecture/sources/i-feed.md`
  - `docs/architecture/sources/health.md`
- **Acceptance gates:** Local: existing cases cover article/endpoint/feed scope, unsupported publisher escalation, denied robots, probe due time, insufficient recovery, renewed failure, score decay, missing state and curated retirement. CI: next-run restriction/probe/recovery integration.
- **Oracle:** Expiry alone never restores ordinary work, whereas the approved observed recovery sequence can; this cannot certify access outside the tested scope or authorize permanent retirement.

### Table AE - Decisions

| Id | Decision | Authority |
| --- | --- | --- |
| AE1 | Keep permission, catalog retirement and temporary access state separate. Unknown availability does not invent failure; unknown robots permission still fails closed. | Existing health/trust contracts and approved D5. |

### Table AF - Rejected alternatives

| Id | Option | Why rejected | Cost to take | Authority |
| --- | --- | --- | --- | --- |
| AF1 | Automatic recovery at timeout or whole-publisher bans from one page | Neither proves restoration nor the larger failure scope. | Collect the required scoped evidence and obtain authority for any escalation. | I Feed lifecycle and maintainer retirement ruling. |

## 15. Row #13 - Apply discovery evidence before feed polling

- **Scope:** Compute approved due times from bounded exact-URL discovery and poll-cost evidence, then consume them before feed requests.
- **Level:** 3 after D5 approval.
- **Files touched:**
  - `services/feed-ingest-plan/src/plan-feed-polls.ts` (new)
  - `services/feed-ingest-plan/src/settle-ingest-feedback.ts`
  - `services/feed-ingest-plan/src/harvest-feeds/harvest-pool.ts`
  - `services/feed-ingest-plan/src/read-ledger-history/read-seen-evidence.ts`
  - `services/feed-ingest-plan/test/harvest.test.ts`
  - `services/feed-ingest-plan/test/plan-engine.test.ts`
  - `docs/architecture/sources/i-feed.md`
  - `docs/architecture/sources/freshness.md`
- **Acceptance gates:** Local: existing cases cover completed zero-arrival polls, no poll, missing seen coverage, stale entries, unchanged feeds, rotation, recovery/exploration allowances and infeasible freshness gaps. CI: due decision prevents actual fixture HTTP work and records unmet coverage.
- **Oracle:** A not-due ordinary feed causes no fetch, while a completed zero-discovery poll changes cadence without creating an article failure; this cannot guarantee discovery under unbounded CI delays.

### Table AG - Decisions

| Id | Decision | Authority |
| --- | --- | --- |
| AG1 | Preserve the approved article-age policy and declare maximum-gap and budget precedence. Existing numeric priority is not a reason to starve new, quiet or recovering sources of all observation. | Approved D5 and I Feed quiet-feed requirements. |

### Table AH - Rejected alternatives

| Id | Option | Why rejected | Cost to take | Authority |
| --- | --- | --- | --- | --- |
| AH1 | Poll everything, then apply cadence after parsing; or silently cap normal fetches | The first saves no acquisition work; the second chooses an unapproved coverage trade-off. | Maintainer-approved poll budget, maximum wait and coverage consequence before activation. | Maintainer scope and I Feed acquisition boundary. |

## 16. Row #14 - Removed from Plan 67

Maintainer ruling, 2026-10-24 UTC: remove conditional feed
requests from this plan. Keep ordinary feed fetching; do not add validators,
cached-body state, `304` handling or recovery requests. The cost is repeated
network transfer and time when a feed body is unchanged. A separate
maintainer-approved plan is required to revisit this optimization.

### Table AI - Decisions

| Id | Decision | Authority |
| --- | --- | --- |
| AI1 | Conditional HTTP and cached-body handling are excluded from Plan 67; ordinary feed fetching remains. | Maintainer ruling, 2026-10-24. |

## 17. Row #15 - Correct structured host and path exclusions

- **Scope:** Replace the existing article-prefetch predicate and audit verification with one pure structured host/path matcher, preserving the exclusion intent rather than adding a parallel pool filter over the old substring check.
- **Level:** 2; no URL identity change.
- **Authorization:** The maintainer approved this matcher correction independently of
  Row 1's open feedback design on 2026-10-24 UTC. The earlier Row 1 dependency
  does not block this phase. Delivery is complete with green CI; PR merge awaits
  maintainer review. This phase does not
  authorize Row 16 or a Python runtime matcher rewrite.
- **Files touched:**
  - `config/feed-ingest-plan.json`
  - `backend/idhazh/contracts/knobs/feed_ingest.py` (config declaration only)
  - `backend/tests/contracts/test_feed_ingest_config.py` (existing binding parameters)
  - `packages/common-contracts/src/schemas/config.schema.ts`
  - `services/feed-ingest-plan/src/harvest-feeds/url-exclusions.ts` (new)
  - `services/feed-ingest-plan/src/harvest-feeds/harvest-article.ts`
  - `services/feed-ingest-plan/src/harvest-feeds/harvest-types.ts`
  - `services/feed-ingest-plan/src/load-plan-inputs.ts`
  - `services/feed-ingest-plan/src/run-feed-plan.ts`
  - `services/feed-ingest-plan/src/metrics/stage-membership.ts`
  - `services/feed-ingest-plan/test/early-age.test.ts`
  - `services/feed-ingest-plan/test/harvest-recordings.ts`
  - `services/feed-ingest-plan/test/harvest-safety.test.ts`
  - `services/feed-ingest-plan/test/plan-engine.test.ts`
  - `tests/fixtures/feed-ingest-plan/harvest-safety.json`
  - `docs/architecture/sources/feed-screening.md`
- **Acceptance gates:** Local: existing safety cases cover exact host/path, approved subdomains/case rules, path boundaries and innocent query mentions. Extend the existing real-composition case: excluded host/path causes no article request, innocent query mentions remain eligible, and native planning verification accepts the evidence. Canonical keys remain unchanged. CI: harvest/screening regressions.
- **Delivery evidence:** Commit `f0078bb383c5d75b02ea2062a0df3e7958b3cedb`
  passed Linux CI run `40130153823`: scope, gates, site, browser and robots.
  This includes Python config bindings, full planner tests and native output
  verification. Local shared-contract checks and 61 tests passed; planner types,
  10 safety cases, the existing early-age and real-composition cases and native
  verifier passed. Wider Windows runs hit fixed timeouts and an existing
  dispatch-persistence assertion; Linux CI passed those checks. No local Python
  ran and no top-level test function was added.
- **Oracle:** The configured excluded host/path remains excluded while the same text in an unrelated query does not trigger it; this cannot resolve canonical identity or authorize removing the editorial exclusion.

### Table AK - Decisions

| Id | Decision | Authority |
| --- | --- | --- |
| AK1 | Preserve exclusion intent, reason and scope. State explicitly that this phase corrects the isolated TypeScript path, not an unapproved Python runtime rewrite. | I Feed host/path proposal and maintainer runtime boundary. |

### Table AL - Rejected alternatives

| Id | Option | Why rejected | Cost to take | Authority |
| --- | --- | --- | --- | --- |
| AL1 | Delete the affiliate exclusion or combine query cleanup here | The first admits excluded material; the second crosses a separate identity boundary. | Maintainer review of the editorial change or Row 16's distinct migration. | Maintainer scope and correction levels. |

## 18. Row #16 - Review and migrate URL identity separately

- **Scope:** Propose the versioned identity correction, obtain its separate approval, then land compatible readers before changed canonical writers in distinct PRs.
- **Level:** 5; no identity-writing implementation before D9 sign-off.
- **Files touched:**
  - `docs/architecture/sources/i-feed.md`
  - `docs/architecture/contracts/identity.md`
  - `services/feed-ingest-plan/src/harvest-feeds/url-cleaner.ts`
  - `services/feed-ingest-plan/src/read-ledger-history/read-seen-evidence.ts`
  - `services/feed-ingest-plan/src/read-ledger-history/published-row.ts`
  - `services/feed-ingest-plan/test/harvest-safety.test.ts`
  - `services/feed-ingest-plan/test/ledger-history.test.ts`
  - `tests/fixtures/feed-ingest-plan/url-identity-cases.json` (new)
- **Acceptance gates:** Local: bounded old/new fixture comparison for unknown keys including `ref`, `s`, `src`, repeated keys, encoded delimiters, ordering and ambiguous old merges. CI: approved reader/writer compatibility; any required Python runtime path is named and separately authorized before extending this footprint.
- **Oracle:** The approved migration preserves supported equivalence without restoring a known false merge through old-key fallback; this cannot recover article distinctions that old evidence never retained.

### Table AM - Decisions

| Id | Decision | Authority |
| --- | --- | --- |
| AM1 | Current generic-key removal and decoded query reconstruction are verified review targets, not permission to change identities silently. Preserve original addresses, versions and ambiguous history. | Separate D9 maintainer approval and identity contract. |

### Table AN - Rejected alternatives

| Id | Option | Why rejected | Cost to take | Authority |
| --- | --- | --- | --- | --- |
| AN1 | Rewrite historical URL hashes or use blanket old-key fallback | Destroys original identity or recreates the collision being corrected. | Preserve old records, declare ambiguity and perform bounded requalification where equivalence is not supported. | Native historical-read contract. |

## 19. Row #17 - Prove dispatch-Parquet parity, then wire digest workers

**Status:** Deferred by maintainer clarification on 2026-10-24 UTC. The following
is future work, not an executable row or a gate for the feed-to-Parquet flow.

- **Scope:** First prove that the TypeScript planner writes dispatch Parquet that the native Python contract and a bounded `work.py` reader path can consume, without changing `digest.yml`. After that parity gate passes, update `digest.yml` to hand the run's dispatch output to `work.py`; preserve worker fetch and summarization and use the recorded worker assignments.
- **Level:** 3 after the Row 1/2 contracts are approved; the final workflow cutover waits for the parity gate.
- **Files touched:**
  - `services/feed-ingest-plan/test/plan-api.test.ts`
  - `services/feed-ingest-plan/test/plan-engine.test.ts`
  - `backend/idhazh/contracts/feed_ingest_dispatch.py`
  - `backend/idhazh/stages/work.py`
  - `backend/idhazh/stages/common.py`
  - `backend/idhazh/cli.py`
  - `.github/workflows/digest.yml`
  - `docs/architecture/sources/feed-ingest-audit.md`
  - `docs/architecture/sources/feed-plan-runner.md`
  - `docs/architecture/sources/feed-partitioning.md`
  - `docs/architecture/summarize/throughput.md`
- **Acceptance gates:** Local: before any workflow edit, generate dispatch Parquet from bounded real fixtures and prove the Python reader assigns exactly the recorded article set to each worker without changing selection or assignment. CI: native contract binding and feed-ingest-plan parity pipeline. Only after that gate passes, verify `digest.yml` passes the same run's dispatch artifact to `work.py`, which consumes the assignments and keeps its existing fetch/summarize behavior.
- **Oracle:** The worker receives exactly the selected items and worker assignments recorded by TypeScript, while selection and Parquet rows remain unchanged; this cannot prove production publication until the gated workflow cutover runs.

### Table AO - Decisions

| Id | Decision | Authority |
| --- | --- | --- |
| AO1 | Production workers currently read Python `RunPlan` rows and do not consume TypeScript dispatch assignments. Build and pass the parity gate before changing `digest.yml`; then the worker reads the registered dispatch Parquet and retains its existing fetch/summarize duties. | Maintainer direction and the existing producer/consumer boundary. |

### Table AP - Rejected alternatives

| Id | Option | Why rejected | Cost to take | Authority |
| --- | --- | --- | --- | --- |
| AP1 | Attribute a Python-produced digest to a shadow TypeScript plan through URL overlap | Matching URLs do not establish causal consumption, attempt or configuration identity. | Approve and execute the concrete compatible handoff or keep the TypeScript completion claim unavailable. | Genuine Phase 2 intent. |

## 20. Row #18 - Connect actual downstream outcomes to the observer

**Status:** Deferred with Row 17. Do not claim downstream consumption or
publication from dispatch-Parquet creation alone.

- **Scope:** Implement the approved caller, join actual worker/model costs and publication/leads, and invoke the existing recorder/verifier on genuine output.
- **Level:** 3 after D10 approval.
- **Files touched:**
  - `services/feed-ingest-plan/src/metrics/publication-outcomes.ts`
  - `services/feed-ingest-plan/src/metrics/publication-metrics.ts`
  - `services/feed-ingest-plan/src/metrics/metrics-recorder.ts`
  - `services/feed-ingest-plan/src/observe-publication.ts` (new)
  - `services/feed-ingest-plan/test/publication-outcomes.test.ts`
  - `services/feed-ingest-plan/test/full-audit.test.ts`
  - `tests/fixtures/feed-ingest-plan/publication-evidence.json`
  - `docs/architecture/sources/feed-ingest-audit.md`
- **Acceptance gates:** Local: existing outcome/audit cases cover actual identity joins, duplicates, failed workers, absent costs, shared startup, missing publication, wrong attempt/configuration and leads. CI: native readback and the worker handoff proven in Row 17. Add the exact caller/workflow paths from Row 17 before dispatch.
- **Oracle:** Real publication and lead memberships reconcile with the actual consumed plan and original run/attempt, while foreign or missing joins cannot complete that audit; this cannot make an unapproved handoff or manufactured publication genuine.

### Table AQ - Decisions

| Id | Decision | Authority |
| --- | --- | --- |
| AQ1 | Reuse `recordPublicationMetrics` and `verifyPublicationMetrics`; generated fixtures remain boundary tests. Record costs from actual work and do not label absent model work perfect efficiency. | Existing observer contract and approved D10. |

### Table AR - Rejected alternatives

| Id | Option | Why rejected | Cost to take | Authority |
| --- | --- | --- | --- | --- |
| AR1 | Close Phase 2 with another generated full audit | Repeats evidence already available and still proves no real publication integration. | Run the approved real caller against genuine downstream output and inspect the resulting joins. | Maintainer's outstanding Phase 2 requirement. |

## 21. Row #19 - Review operational regressions and prove the live loop

- **Scope:** Implement and wire the approved bounded nonsemantic operational review, then verify the feedback loop and activate only approved consumers; name its actual caller and bounded evidence inputs in Files touched before dispatch.
- **Level:** 3; changed activation or comparison policy returns to D5/D8.
- **Files touched:**
  - `services/feed-ingest-plan/src/review-ingest-operations.ts` (new)
  - `services/feed-ingest-plan/test/plan-engine.test.ts`
  - `services/feed-ingest-plan/test/plan-api.test.ts`
  - `services/feed-ingest-plan/test/full-audit.test.ts`
  - `tests/fixtures/feed-ingest-plan/ingest-outcomes.json`
  - `.github/scripts/feed-ingest-plan-report.ts`
  - `.github/scripts/tests/feed-ingest-plan-outputs.test.ts`
  - `docs/architecture/sources/i-feed.md`
  - `docs/architecture/contracts/feed-ingest-feedback.md`
- **Acceptance gates:** Local: extend existing bounded integration cases for partial runs, changed extractor release, source-specific refusal, quiet feeds, unknown history, settlement, next-run choices and recovery; render actual report Markdown. CI: exact candidate full checks. The authorized review actually consumes named recent evidence and records coverage, diagnosis and approved action or recommendation; fixtures/report rendering alone do not close it. Observe the next authorized actual run for latest-state and next-consumer evidence; do not repeatedly dispatch a committing workflow as a test. Independent operational-loop proof need not wait for Row 18, but B15 and overall closure still require genuine downstream delivery.
- **Oracle:** A recorded source-access change and a shared pipeline-release failure lead to different supported operational decisions, and a later actual allocation consumes the committed state; this cannot establish semantic quality, factual truth or an untested policy's long-term benefit.

### Table AS - Decisions

| Id | Decision | Authority |
| --- | --- | --- |
| AS1 | Operational review examines independent technical outcomes and source/pipeline revisions. Keep automatic formula tuning and qualitative drift assessment excluded. Missing live evidence keeps the relevant closure claim open, not the entire implementation falsely complete. | Maintainer-confirmed scope and I Feed drift discipline. |

### Table AT - Rejected alternatives

| Id | Option | Why rejected | Cost to take | Authority |
| --- | --- | --- | --- | --- |
| AT1 | Use a higher internal score or one fixed fixture as live effectiveness proof | The objective cannot grade itself, and fixtures do not settle real next-run wiring. | Inspect the named actual run/state/decision chain and bounded independent technical outcomes. | I Feed validation intent. |

## 22. Row #20 - Adopt cache delivery and finish the combined hosted proof

- **Scope:** Adopt the cache delivery, correct the named-module sparse checkout omission with an existing bounded workflow regression, and complete the combined hosted proof. No further implementation or dispatch is part of this closure.
- **Delivery status:** DONE. Cache PR [#1671](https://github.com/miztiik/yen-idhazh/pull/1671) merged at `b037f8`; URL matcher PR [#1703](https://github.com/miztiik/yen-idhazh/pull/1703) merged at `52a0e1`; sparse checkout correction [#1707](https://github.com/miztiik/yen-idhazh/pull/1707) merged at `962b4cc`. The first authorized [run 40131128910](https://github.com/miztiik/yen-idhazh/actions/runs/40131128910) on `b037f8` failed before live work. The maintainer explicitly authorized one corrected [run 40133676513](https://github.com/miztiik/yen-idhazh/actions/runs/40133676513), which succeeded on exact head `b1830d0f0a684e5c09715f597ca05542d38edcd2`, attempt 1.
- **Failure:** Sparse checkout omitted `.github/scripts/feed-ingest-plan-pid-report.ts` and `.github/scripts/feed-ingest-plan-resource-values.ts`, imported by the resource/cache/profile reporters. `Check isolated adapters` failed with `Cannot find module` imports, and the existing workflow strict-check test failed. Normal CI used a complete checkout and passed; it did not prove the hosted sparse selection.
- **Level:** 3; workflow preflight correction and regression delivered, with combined hosted verification complete. This status closure changes documentation only.
- **Files touched:**
  - `.github/workflows/feed-ingest-plan-test.yml` (explicit selection of the two omitted modules)
  - Existing bounded workflow test (regression for the hosted sparse selection)
  - `docs/how-to/run-feed-ingest-plan-test.md` (sparse preflight requirements)
  - `TODO/20261024-67-feed-ingest-feedback-and-selection-plan.md` (this row's status)
  - `TODO/20261020-66-feed-ingest-plan.md` (only the corresponding expanded-follow-up status, after verified delivery)
- **Completed proof:** Run `2026-10-24-40133676513`, correlation `792986e7-d810-403d-817c-a1d1de6f971d`, used `freshness_hours=24` and `profile_machine_memory=true`; other overrides were omitted. The coordinator inspected downloaded actual artifacts and compared SHA-256 hashes of all 11 native/host output files with their exact Git blobs in landed [output commit `3c3a95fb7f8afd2cd5c1781d654cb883669d411f`](https://github.com/miztiik/yen-idhazh/commit/3c3a95fb7f8afd2cd5c1781d654cb883669d411f). That run's catalog contained 156 active feed IDs: 11,030 parsed items, 915 harvested, 679 eligible, 121 normalized and 100 selected.
- **Acceptance evidence:** Configured feed `bbc-tech` and selected HTML from `cgtn-opnion` were proved separately; dispatch receipt `01a16fd0-0cf6-8f14-a30e-1660c0dbd191` bound candidate `bc4d37262ad56fdc1112a6ae27d488fef22645271ce2da433aac15d0d4daa02f` to worker 2 of 4 with 990 words. Actual replay, journal, private HTTP 409 conflict handling and no extra network work were verified, as were CPU/PID RAM, independent machine RAM, reports, native bytes and the scoped no-Python audit. Restricted affinity `[1,3]` selected CPU 1; owned cancellation preserved the target. Hardware performance counters (PMU) reported `permission_denied` with null counts; the measured working-set curve is not direct L3-hit latency. A permitted-host counter measurement remains open separately under AU2, not as a Row 20 blocker. Live evidence retained `audited_complete=false` and `publication=null`, distinct from the `generated_fixture` audit; this proof makes no actual worker-publication claim.
- **Oracle:** The actual hosted feed/selected-HTML/native-output proof and resource report agree on their real work and identities, with denied counters null and working-set latency correctly labelled; this cannot measure direct L3-hit latency or successful PMU events on a denied host.

### Table AU - Decisions

| Id | Decision | Authority |
| --- | --- | --- |
| AU1 | Adopt `optional-cache-probes` in `potential-fiesta`, session `6a57ff1e-bdfc-4248-86f8-cd5b17c8bde2`. Review the live PR diff before merging; any necessary source correction returns to that maintainer and updates its footprint. Preserve H/I/J/K and existing notices when cache evidence is absent. | Existing delegated delivery and final review requirement. |
| AU2 | The default-false independent cache controls, measured working-set curve, exact unavailable LLC aliases and scoped native build audit are distinct evidence. A genuinely permitted hardware-counter reading remains open if no permitted host is available. | Existing cache contract and maintainer no-Python boundary. |

### Table AV - Rejected alternatives

| Id | Option | Why rejected | Cost to take | Authority |
| --- | --- | --- | --- | --- |
| AV1 | Rebuild the instruments, merge an earlier green head, or claim denied counters measured | Duplicates delivered work, bypasses final review or overstates the instrument. | Review the current exact candidate and obtain an already-permitted host for actual counter measurement. | Existing adoption and measurement requirements. |

## 23. Row #21 - Review and reuse configured numeric priorities

- **Scope:** Review useful Python watchlist, theme and carrier-priority behavior against recorded TypeScript inputs, then implement only explicitly approved numeric terms while preserving the distinct reliability and publisher-exposure adjustments.
- **Status:** The [bounded priority review](../docs/architecture/sources/feed-curation.md#configured-priority-review) is complete. D12 approval of any new term, matcher or default remains pending; no new term is implemented or enabled. The row remains open.
- **Level:** 5 for the policy/evidence proposal; no new bonus or changed persisted meaning before D12 approval.
- **Files touched in this review:**
  - `docs/architecture/sources/feed-curation.md`
  - `TODO/20261024-67-feed-ingest-feedback-and-selection-plan.md` (Row 21 only)
- **Current code references (read only):**
  - `config/feed-ingest-plan.json`
  - `packages/common-contracts/src/schemas/config.schema.ts`
  - `packages/common-contracts/src/schemas/candidate.schema.ts`
  - `packages/common-contracts/src/schemas/planner-stage.schema.ts`
  - `packages/common-contracts/src/schemas/selected-article.schema.ts`
  - `backend/idhazh/contracts/feed_ingest_selected_article.py`
  - `services/feed-ingest-plan/src/curate-article-portfolio/editorial-selection.ts`
  - `services/feed-ingest-plan/src/curate-article-portfolio/publisher-exposure.ts`
  - `services/feed-ingest-plan/test/curate.test.ts`
- **Acceptance gates - review:** Compare `backend/idhazh/rank.py`, headline matching in `backend/idhazh/stages/plan.py` through `backend/idhazh/tag.py`, and their maintainer-authored config with current TypeScript scoring and declared batch inputs. Record adopted behavior and unapproved recommendations in the living curation doc; raw titles/categories are not recorded theme/entity matches, and URL identities are not carrier witnesses. Check the docs with the shared selector and bounded named-link, ASCII and whitespace checks; no application suite is needed for this docs-only phase.
- **Acceptance gates - approved implementation:** Implementation remains blocked on D12. For an approved term, name the exact current contract/binding footprint, declare any new persisted meaning and update readers before writers; extend existing curation/binding cases for config substitution, unknown evidence, score readback and duplicate carriers. CI then checks strict types and current native/TypeScript bindings and readback. Do not restore removed assessment/classification paths, change Python ranking runtime or assume its exact selections are the target.
- **Oracle:** Varying one approved configured priority with the same recorded input changes only its declared score contribution and actual selection trace, without repeated carrier charges or inferred qualitative verdicts; this cannot establish that a higher numeric priority means a better story.

### Table AW - Decisions

| Id | Decision | Authority |
| --- | --- | --- |
| AW1 | Reuse useful explicit inputs, not the entire Python algorithm. Current candidates carry title and feed facts, not recorded theme/entity matches or carrier witnesses. Preserve feed allowances, choices recomputed against the chosen set and exploration. The review's recommendations do not grant D12 approval. | Maintainer's requested priority-review task and D12. |

### Table AX - Rejected alternatives

| Id | Option | Why rejected | Cost to take | Authority |
| --- | --- | --- | --- | --- |
| AX1 | Copy every Python bonus, restore a removed front-page bonus, or treat word matches as story quality | Adds unapproved policy, duplicate influence or qualitative claims unsupported by the observations. | Review the individual term, its evidence and counterexample, then obtain approval with compatible score readers. | Maintainer's nonsemantic scope and independent-priority requirement. |

## 24. Row #22 - Replace planner ledgers and APIs in one atomic cutover

- **Scope:** Replace the active planner formats, APIs and runtime with the four-ledger design, including its required obsolete raw/compact-data reset, without leaving an unused parallel implementation.
- **Level and permission:** Level 5, execution authorized by user approval on 2026-10-25 UTC. The coordinator first verifies this documentation change on remote `main`; this docs PR does not implement the row.
- **Contract source:** [Proposal Tables A-H, K and L](../docs/reference/feed-planner-ledgers.md). Declare the minimal native payloads and strict TypeScript bindings before logic. Preserve all review IDs and field meanings; a new persisted meaning outside that proposal is an escalation, not an excuse to resume the old design.
- **PR boundary and cost:** One cohesive implementation PR. Separating contracts/storage, current readers/writers, API runtime and mandatory cleanup would temporarily retain unused or incompatible implementations. Price that as a larger review and shared-file footprint, not a compatibility phase. Obsolete planner-family history under both named storage roots is deliberately lost; other families, global Python `feed-health`, historical corpus and the Python news pipeline are not reset.
- **Ordered work package 1 - contracts and storage:** Declare and validate the four persisted payloads, selected artifact and strict allowlisted metadata projection, date stamps/changelogs, current-format stage batches and exact native file metadata before logic within this same atomic cutover. There is no separate approval or contracts-only PR gate. Implement new-family native envelope parsing, stored-row readback, settlement, raw/compact verification and gardener packing through the existing storage infrastructure, alongside the TypeScript reader/writer changes. Registration-only edits cannot satisfy the minimal-metadata format. Do not inject `unit_id` or removed generic audit columns, globally relax the other families' protocol, or fabricate identity to make the old infrastructure accept a new file. Use the declared per-ledger row identity and preserve distinct real run/attempt work. Implement current-format readers before their writers within this PR; reject incompatible old planner batches/rows by name rather than migrating them. Native shared-ledger storage support is permitted, not a Python news-pipeline rewrite.
- **Ordered work package 2 - actual API/runtime cutover:** Replace the real `/plan`, `/fetch`, `/parse`, `/select-articles`, `/partition-articles` and persistence code paths in proposal Table K, register its planned health operation, and replace the old persistence route without an alias. Keep server-owned stage IDs, the complete parsed input, explicit errors and the existing default-off service flag. Route typed validated events to separate execution modules; do not put execution in the router or use HTTP self-calls. Remove the listener-wide `ready` promise chain in `api/server.ts` and keep run clocks, counters and selected data isolated per execution.
- **Concurrency and ordering:** Reuse configured bounded work pools for independent history reads, permitted requests and article work; do not serialize all runs. Fetch precedes its parse; article work may start after its supplying feed is parsed; selection waits for the complete admitted batch and health summary; partitioning waits for selection. After selection, health recording/reporting can overlap partitioning. `parse-document.ts` currently reaches synchronous `extractArticle` in `dom-extractor.ts`; `Promise.all` around that call is not CPU parallelism. Use the runtime's native bounded workers for blocking parsing when needed, preserving the same real extractor and safety rules. No new profiler framework or benchmark approval gate.
- **Shared state and artifact boundary:** Calculate the bounded lookbacks once per run through the shared health operation. Keep the proposal's three window meanings and capture both actual clocks. One in-memory selection produces the text-bearing Actions artifact and metadata-only Parquet without `pop`, `delete` or independent recalculation. Batch health counters per run/UTC work day; preserve completed work on later failure, finalize an explicit empty/partial/failed run result, and do not sum captured reliability during reports or compaction. Record actual `feed-health-summary` phase duration, not an estimated speed claim.
- **Native packing path:** `ledger.read_footer`/`load_stored` feed `gardener.ledger_marks` and `CompactTree.load`/`read_raw_day`; daily packing and reopened months settle rows before `ledger.render_period`, monthly packing uses the same renderer, and yearly packing calls `ledger.render_grouped_period`. Update these actual callers and period-input/packing modules for the new family so raw, daily, monthly, reopened-month and yearly files read back without generic `RowIdentity`/`unit_id` requirements. Keep all other families on their existing protocol. No frontend source `unit_id` consumer was found; do not invent a frontend source rewrite.
- **Ordered work package 3 - required cleanup and integration:** Remove old planner writers/readers, old route exports, dead old-family native model/export/contract-registry references, full-audit/classification/causal-score consumers and active registry/compaction entries replaced by this row. Remove a model only after its actual callers are replaced; keep unrelated shared types with real consumers. Update the existing isolated workflow adapters to commit only current declared planner output and upload text only as an artifact. Host instruments remain independent and optional, not a planner completion gate. Keep genuine external publication/exclusion inputs and fetch safety unchanged. Do not migrate rows, create aliases/dual writers or change `digest.yml`, `work.py`, the Python news pipeline or the global `feed-health` family.
- **Data deletion boundary:** At execution, derive the exact tracked deletion list from the same eight obsolete prefixes under both roots, as listed below, at the fixed candidate base. Include their raw data, compact period files and compact indexes. Report absent prefixes rather than inventing files or copying an old file/byte count. Inspect/stage explicit resolved paths only; remove no broader raw/compact root, other family, global Python `feed-health`, corpus or Git history. No permanent old-family compact archive, migration, alias or dual writer remains beside the replacement.
- **Files touched - shared contracts and storage (existing unless marked new):**
  - `backend/idhazh/contracts/feed_ingest_discovered_article.py` (new)
  - `backend/idhazh/contracts/feed_ingest_selected_article.py` (new)
  - `backend/idhazh/contracts/feed_ingest_plan_run.py` (new)
  - `backend/idhazh/contracts/feed_health_state.py`
  - `backend/idhazh/contracts/file_envelope.py` (new-family metadata support; other-family protocol unchanged)
  - `backend/idhazh/contracts/__init__.py`
  - `backend/idhazh/contracts/feed_ingest_article_assessment.py` (remove dead old-family model/export references)
  - `backend/idhazh/contracts/feed_ingest_dispatch.py` (remove dead old-family model/export references)
  - `backend/idhazh/contracts/feed_ingest_diversity.py` (remove dead old-family model/export references)
  - `backend/idhazh/contracts/feed_ingest_editorial_selection.py` (remove dead old-family model/export references)
  - `backend/idhazh/contracts/feed_ingest_feedback.py` (remove dead old-family model/export references)
  - `backend/idhazh/contracts/feed_ingest_observations.py` (remove dead old-family model/export references)
  - `backend/idhazh/contracts/feed_ingest_rejection.py` (remove dead old-family model/export references)
  - `backend/idhazh/contracts/feed_ingest_source_run.py` (remove dead old-family model/export references)
  - `backend/idhazh/contracts/planner_stage.py`
  - `backend/idhazh/contracts/ledger_name.py`
  - `backend/idhazh/ledger/__init__.py`
  - `backend/idhazh/ledger/keys.py`
  - `backend/idhazh/ledger/staging.py`
  - `backend/idhazh/ledger/persist.py`
  - `backend/idhazh/ledger/raw_files.py`
  - `backend/idhazh/ledger/stored_output.py`
  - `backend/idhazh/gardener/period_inputs.py`
  - `backend/idhazh/gardener/ledger_marks.py`
  - `backend/idhazh/gardener/tasks/compaction.py`
  - `backend/idhazh/gardener/tasks/_compact_tree.py`
  - `backend/idhazh/gardener/tasks/_daily_period.py`
  - `backend/idhazh/gardener/tasks/_monthly_period.py`
  - `backend/idhazh/gardener/tasks/_reopened_month.py`
  - `backend/idhazh/gardener/tasks/_yearly_period.py`
  - `packages/common-contracts/src/index.ts`
  - `packages/common-contracts/src/schemas/discovered-article.schema.ts` (new)
  - `packages/common-contracts/src/schemas/selected-article.schema.ts` (new)
  - `packages/common-contracts/src/schemas/plan-run.schema.ts` (new)
  - `packages/common-contracts/src/schemas/feed-health-state.schema.ts`
  - `packages/common-contracts/src/schemas/planner-stage.schema.ts`
  - `packages/common-contracts/src/schemas/event.schema.ts`
  - `packages/common-contracts/src/schemas/config.schema.ts`
  - `packages/common-contracts/src/schemas/candidate.schema.ts`
  - `packages/common-contracts/src/schemas/dispatch.schema.ts`
  - `packages/common-contracts/src/schemas/editorial-selection.schema.ts`
  - `packages/common-contracts/src/schemas/article-assessment.schema.ts`
  - `packages/common-contracts/src/schemas/diversity.schema.ts`
  - `packages/common-contracts/src/schemas/ingest-observations.schema.ts`
  - `packages/common-contracts/src/schemas/feed-ingest-feedback.schema.ts`
  - `packages/common-contracts/src/schemas/policy.schema.ts`
  - `packages/common-contracts/src/schemas/envelope.schema.ts`
  - `packages/common-contracts/src/schemas/source-run.schema.ts`
  - `packages/ledger-file-writer/src/row-identity.ts`
  - `packages/ledger-file-writer/src/row-schema.ts`
  - `packages/ledger-file-writer/src/render-ledger-file.ts`
  - `packages/ledger-file-writer/src/persist-raw.ts`
  - `packages/ledger-file-writer/src/persist-compact.ts`
  - `packages/ledger-file-writer/src/parquet/envelope-footer.ts`
  - `config/ledgers.json`
  - `config/feed-ingest-plan.json`
  - `config/feed-ingest-plan-service.json`
  - `config/idhazh_gardener.json`
  - `config/gardener/compact-feed-ingest-plan-article-assessments.json`
  - `config/gardener/compact-feed-ingest-plan-dispatches.json`
  - `config/gardener/compact-feed-ingest-plan-diversity.json`
  - `config/gardener/compact-feed-ingest-plan-document-observations.json`
  - `config/gardener/compact-feed-ingest-plan-editorial-selections.json`
  - `config/gardener/compact-feed-ingest-plan-operational-state.json`
  - `config/gardener/compact-feed-ingest-plan-rejections.json`
  - `config/gardener/compact-feed-ingest-plan-source-runs.json`
  - `config/gardener/compact-feed-ingest-plan-discovered-articles.json` (new)
  - `config/gardener/compact-feed-ingest-plan-selected-articles.json` (new)
  - `config/gardener/compact-feed-ingest-plan-feed-health-state.json` (new)
  - `config/gardener/compact-feed-ingest-plan-plan-runs.json` (new)
- **Files touched - real runtime and old-format callers:** The search-derived footprint below is one row, not parallel ownership. Edit or remove each obsolete caller with its replacement; refresh this named footprint before dispatch if a newly found caller is required.
  - `services/feed-ingest-plan/src/index.ts`
  - `services/feed-ingest-plan/src/load-plan-inputs.ts`
  - `services/feed-ingest-plan/src/run-feed-plan.ts`
  - `services/feed-ingest-plan/src/record-feed-plan.ts`
  - `services/feed-ingest-plan/src/select-articles.ts`
  - `services/feed-ingest-plan/src/config/service-settings.ts`
  - `services/feed-ingest-plan/src/api/server.ts`
  - `services/feed-ingest-plan/src/api/routes/stages.route.ts`
  - `services/feed-ingest-plan/src/api/routes/plan.route.ts`
  - `services/feed-ingest-plan/src/api/routes/document.route.ts`
  - `services/feed-ingest-plan/src/api/routes/feed-health-state.route.ts` (new)
  - `services/feed-ingest-plan/src/api/feed-health-state.schema.ts`
  - `services/feed-ingest-plan/src/api/feed-health-state-operation.ts` (new)
  - `services/feed-ingest-plan/src/api/document-operations.ts`
  - `services/feed-ingest-plan/src/api/selection-operation.ts`
  - `services/feed-ingest-plan/src/api/partition-operation.ts`
  - `services/feed-ingest-plan/src/api/persistence-operation.ts`
  - `services/feed-ingest-plan/src/api/stage-store.ts`
  - `services/feed-ingest-plan/src/api/stage-response.schema.ts`
  - `services/feed-ingest-plan/src/harvest-feeds/harvest-pool.ts`
  - `services/feed-ingest-plan/src/harvest-feeds/harvest-article.ts`
  - `services/feed-ingest-plan/src/harvest-feeds/parse-document.ts`
  - `services/feed-ingest-plan/src/harvest-feeds/dom-extractor.ts`
  - `services/feed-ingest-plan/src/harvest-feeds/article-parser-worker.ts` (new)
  - `services/feed-ingest-plan/src/harvest-feeds/article-parser-pool.ts` (new)
  - `services/feed-ingest-plan/src/harvest-feeds/record-rejection.ts`
  - `services/feed-ingest-plan/src/curate-article-portfolio/editorial-selection.ts`
  - `services/feed-ingest-plan/src/curate-article-portfolio/portfolio-input.ts`
  - `services/feed-ingest-plan/src/partition-article-shards/read-editorial-selection.ts`
  - `services/feed-ingest-plan/src/partition-article-shards/shard-packer.ts`
  - `services/feed-ingest-plan/src/screen-article-candidates/rejection-sealer.ts`
  - `services/feed-ingest-plan/src/ingest-observations.ts`
  - `services/feed-ingest-plan/src/estimate-operational-feedback.ts`
  - `services/feed-ingest-plan/src/settle-ingest-observations.ts`
  - `services/feed-ingest-plan/src/attribute-ingest-outcomes.ts`
  - `services/feed-ingest-plan/src/rollup-ingest-outcomes.ts`
  - `services/feed-ingest-plan/src/read-ledger-history/read-feed-history.ts`
  - `services/feed-ingest-plan/src/read-ledger-history/read-seen-evidence.ts`
  - `services/feed-ingest-plan/src/read-ledger-history/record-feed-health.ts`
  - `services/feed-ingest-plan/src/read-ledger-history/read-ingest-evidence.ts`
  - `services/feed-ingest-plan/src/read-ledger-history/read-parquet.ts`
  - `services/feed-ingest-plan/src/read-ledger-history/read-period.ts`
  - `services/feed-ingest-plan/src/read-ledger-history/complete-attempt.ts`
  - `services/feed-ingest-plan/src/read-ledger-history/encode-historical-record.ts`
  - `services/feed-ingest-plan/src/read-ledger-history/logical-records.ts`
  - `services/feed-ingest-plan/src/metrics/metrics-recorder.ts`
  - `services/feed-ingest-plan/src/metrics/planning-populations.ts`
  - `.github/scripts/feed-ingest-plan-http-proof.ts`
  - `.github/scripts/feed-ingest-plan-outputs.ts`
  - `.github/scripts/feed-ingest-plan-verification.ts`
  - `.github/scripts/feed-ingest-plan-feed-history.ts`
  - `.github/scripts/feed-ingest-plan-commit.ts`
  - `.github/scripts/feed-ingest-plan-report.ts`
  - `.github/scripts/feed-ingest-plan-audit-fixture.ts`
  - `.github/workflows/feed-ingest-plan-test.yml`
- **Files touched - existing bounded checks and fixtures:**
  - `packages/common-contracts/test/schema-binding.ts`
  - `packages/common-contracts/test/config.test.ts`
  - `packages/common-contracts/test/ledger-index.test.ts`
  - `packages/common-contracts/test/rejection.test.ts`
  - `packages/ledger-file-writer/test/parquet-parity.test.ts`
  - `packages/ledger-file-writer/test/reader-integrity.test.ts`
  - `packages/ledger-file-writer/test/uuid.test.ts`
  - `services/feed-ingest-plan/test/plan-api.test.ts`
  - `services/feed-ingest-plan/test/plan-engine.test.ts`
  - `services/feed-ingest-plan/test/plan-cli.test.ts`
  - `services/feed-ingest-plan/test/stage-api-cases.ts`
  - `services/feed-ingest-plan/test/plan-recordings.ts`
  - `services/feed-ingest-plan/test/harvest-recordings.ts`
  - `services/feed-ingest-plan/test/harvest.test.ts`
  - `services/feed-ingest-plan/test/harvest-safety.test.ts`
  - `services/feed-ingest-plan/test/history-window.test.ts`
  - `services/feed-ingest-plan/test/ledger-history.test.ts`
  - `services/feed-ingest-plan/test/health-order-recording.ts`
  - `services/feed-ingest-plan/test/logical-completion.test.ts`
  - `services/feed-ingest-plan/test/compaction-recording.ts`
  - `services/feed-ingest-plan/test/observation-recordings.ts`
  - `services/feed-ingest-plan/test/partition.test.ts`
  - `services/feed-ingest-plan/test/partition-fixtures.ts`
  - `services/feed-ingest-plan/test/curate.test.ts`
  - `services/feed-ingest-plan/test/triage.test.ts`
  - `services/feed-ingest-plan/test/policy.test.ts`
  - `services/feed-ingest-plan/test/early-age.test.ts`
  - `services/feed-ingest-plan/test/article-assessments.test.ts`
  - `services/feed-ingest-plan/test/source-run-summary.test.ts`
  - `services/feed-ingest-plan/test/full-audit.test.ts`
  - `services/feed-ingest-plan/test/full-audit-recording.ts`
  - `services/feed-ingest-plan/test/metrics.test.ts`
  - `services/feed-ingest-plan/test/publication-outcomes.test.ts`
  - `.github/scripts/tests/feed-ingest-plan-outputs.test.ts`
  - `.github/scripts/tests/feed-ingest-plan-report.test.ts`
  - `.github/scripts/tests/feed-ingest-plan-workflow.test.ts`
  - `backend/tests/contracts/test_feed_ingest_contracts.py`
  - `backend/tests/contracts/test_feed_ingest_config.py`
  - `backend/tests/contracts/test_feed_ingest_audit.py`
  - `backend/tests/contracts/test_ledger_registry.py`
  - `backend/tests/contracts/test_gardener_config.py`
  - `backend/tests/contracts/test_frontend_registry_shape.py`
  - `backend/tests/contracts/test_frontend_vocabularies.py`
  - `backend/tests/contracts/_fixtures.py`
  - `backend/tests/ledger/test_feed_ingest_ledgers.py`
  - `backend/tests/ledger/test_persist.py`
  - `backend/tests/ledger/test_raw_files.py`
  - `backend/tests/ledger/test_stored_output.py`
  - `backend/tests/gardener/test_period_inputs.py`
  - `backend/tests/gardener/tasks/test_compaction.py`
  - `backend/tests/gardener/tasks/test_compaction_batch.py`
  - `backend/tests/gardener/tasks/test_compaction_lifecycle.py`
  - `backend/tests/gardener/tasks/test_compaction_periods.py`
  - `backend/tests/gardener/tasks/test_compaction_years.py`
  - `frontend/tests/ledger-catalog.spec.ts`
  - `frontend/tests/ledger-copy.spec.ts`
  - `frontend/tests/ledger-door.spec.ts`
  - `frontend/tests/payload-ceilings.spec.ts`
  - `frontend/tests/console-data-explorer-still.spec.ts`
  - `frontend/tests/support/feed-ledgers.ts`
  - `tests/fixtures/feed-ingest-plan/harvest-responses.json`
  - `tests/fixtures/feed-ingest-plan/harvest-article.html`
  - `tests/fixtures/feed-ingest-plan/harvest-rss.xml`
  - `tests/fixtures/feed-ingest-plan/harvest-atom.xml`
  - `tests/fixtures/feed-ingest-plan/health-order-cases.json`
  - `tests/fixtures/feed-ingest-plan/ingest-outcomes.json`
  - `tests/fixtures/feed-ingest-plan/report-events.json`
- **Files touched - living docs and plan:**
  - `docs/reference/feed-planner-ledgers.md`
  - `docs/architecture/contracts/feed-ingest-feedback.md`
  - `docs/architecture/contracts/schemas.md`
  - `docs/architecture/contracts/state-ledgers.md`
  - `docs/architecture/contracts/ledger-registry.md`
  - `docs/architecture/contracts/persistence.md`
  - `docs/architecture/publishing/ledger-compaction.md`
  - `docs/architecture/sources/feed-operator-api.md`
  - `docs/architecture/sources/planner-feed-history.md`
  - `docs/architecture/sources/feed-harvesting.md`
  - `docs/architecture/sources/feed-screening.md`
  - `docs/architecture/sources/feed-curation.md`
  - `docs/architecture/sources/feed-partitioning.md`
  - `docs/architecture/sources/feed-plan-runner.md`
  - `docs/architecture/sources/feed-ingest-audit.md`
  - `docs/architecture/sources/feed-ingest-policies.md`
  - `docs/how-to/run-feed-ingest-plan-test.md`
  - `TODO/20261024-67-feed-ingest-feedback-and-selection-plan.md`
- **Named deletion allowlist (the same eight obsolete prefixes under both roots; not a runtime scan):**
  - `state/raw/feed-ingest-plan/article-assessments/`
  - `state/raw/feed-ingest-plan/dispatches/`
  - `state/raw/feed-ingest-plan/diversity/`
  - `state/raw/feed-ingest-plan/document-observations/`
  - `state/raw/feed-ingest-plan/editorial-selections/`
  - `state/raw/feed-ingest-plan/operational-state/`
  - `state/raw/feed-ingest-plan/rejections/`
  - `state/raw/feed-ingest-plan/source-runs/`
  - `state/compact/feed-ingest-plan/article-assessments/`
  - `state/compact/feed-ingest-plan/dispatches/`
  - `state/compact/feed-ingest-plan/diversity/`
  - `state/compact/feed-ingest-plan/document-observations/`
  - `state/compact/feed-ingest-plan/editorial-selections/`
  - `state/compact/feed-ingest-plan/operational-state/`
  - `state/compact/feed-ingest-plan/rejections/`
  - `state/compact/feed-ingest-plan/source-runs/`
- **Acceptance gates - local:** First inspect the shared selector from `frontend/` with `npm run test:changed -- --list`; record the selection but do not run a Python-bearing local group. Run `bun run --cwd packages/common-contracts check`, `bun run --cwd packages/ledger-file-writer check` and `bun run --cwd services/feed-ingest-plan check`. Extend and run existing bounded planner/API/history/partition/safety cases and the existing adapter command from [isolated checks](../docs/how-to/run-feed-ingest-plan-test.md#local-offline-checks), plus its native TypeScript verifier updated to current planner formats. Reuse recorded HTTP/HTML fixtures and generated run directories; no network tests, local Python, Python packages, mocks or new top-level test functions. Preserve unrelated fixed native compatibility vectors for other families.
- **Acceptance gates - CI:** Exact candidate full suite, native field/vocabulary/schema bindings, registry/compaction tests, selected frontend registry fixtures and isolated adapter/workflow strict checks. Extend the named native persistence/raw-file/stored-output and gardener period tests to read, verify, settle, compact and reopen generated new-family files without `unit_id`; independently prove another family's unchanged protocol still requires its original identity. Verify no dead old-family native model/export requirement remains, only current planner names/routes are active, the old persistence route returns the ordinary not-found response, and fixture output has exactly the declared planner columns. Check the exact deletion diff against the two-root allowlist, including old compact indexes, without an accumulated-tree runtime scan or frozen file count. A manual workflow that commits data is not a repeatable test gate; inspect the next authorized real run separately for correct four-ledger output, artifact-only text and actual phase timings. Do not require a host fingerprint, cache or profiler proof to finish planning.
- **Oracle:** Run the real listener and CLI against the bounded recorded corpus; independently decode their current-format Parquet and selected artifact and reconcile selected identities, order, worker assignments, per-run/day counters and explicit run outcome. The committed projection has no article text, `unit_id` or undeclared audit columns; native and TypeScript readers accept its declared format, and real daily/monthly/reopened-month/yearly packing preserves its rows and captured scores without generic identity restoration. Generated raw/compact copies contribute once, distinct real work remains counted, an empty/partial/failed run stays explicit, concurrent runs do not mix clocks/data, and another family's protocol remains unchanged. Prove real overlap from typed start/finish events and independent request progress, including a responsive listener during native-worker HTML parsing, not a `Promise.all` wrapper around synchronous code. This proves the cutover, storage and concurrency mechanisms, not a production speed percentage, live-source availability, downstream publication or completion of the remaining policy work.

### Table AY - Cutover decisions

| Id | Decision | Authority |
| --- | --- | --- |
| AY1 | Land this docs update on remote `main` first, then replace the actual planner path in one atomic PR; contracts are declared before logic within it. | User-directed documentation-first clean break, 2026-10-25 UTC. |
| AY2 | The four formats and independent windows are defined only in the linked proposal. Its old-field mapping does not require migrating old rows. | User-approved breaking replacement and seven-day report-only choice. |
| AY3 | Run independent work concurrently with configured bounds and typed events, while preserving data dependencies and per-run isolation. | User-directed asynchronous event-driven runtime. |
| AY4 | The permitted reset removes the same eight obsolete planner-family prefixes under both raw and compact roots, including compact indexes. No broader root, other family, global Python `feed-health`, corpus, Python news pipeline or Git history is reset. Native new-family storage/reader/compaction support is permitted without changing other families' protocol. | Scoped user approval; other migrations remain deferred. |

### Table AZ - Rejected cutover alternatives

| Id | Option | Why rejected | Cost to take | Authority |
| --- | --- | --- | --- | --- |
| AZ1 | Land unused replacement contracts, then keep old/new formats alive through a compatibility phase | Leaves the second implementation and historical machinery the user explicitly removed. | A new coexistence decision plus extra readers, writers, aliases and tests; no such phase is authorized. | Clean-break direction. |
| AZ2 | Add another summary ledger/API or incremental fingerprint/head cache before implementation | No timing of the proposed format shows a need, and captured scores do not establish cache freshness. | First obtain representative `feed-health-summary` timing and show which recurring read cost changes the design; then price a cache in the existing family. | Proposal design rationale. |
| AZ3 | Call synchronous HTML parsing through promises and describe it as CPU parallelism | The parser still blocks one event loop; requests cannot make progress while it runs. | Use bounded native workers for the real extractor and prove independent progress; no new profiler framework is needed. | Runtime behavior and required concurrency outcome. |

## 25. Row #23 - Migrate the feed-planning ledger family

- **Status:** COLLAPSED into Row 22, not delivered.
- **Reason:** The approved clean break removes the old-to-new compatibility phase. Current registration, native/TypeScript storage readers/writers/compaction and the permitted two-root obsolete-data reset belong to the same atomic cutover, not a second implementation.

## 26. Row #24 - Incrementally update and read feed-health state

- **Status:** COLLAPSED into Row 22, not delivered.
- **Reason:** Use the shared bounded health operation and run/day counters in the proposal. The old snapshot/head, changed-day fingerprint and causal-score design is not an executable step or a prerequisite.

## 27. Row #25 - Remove redundant TypeScript state paths

- **Status:** COLLAPSED into Row 22, not delivered.
- **Reason:** Remove the old planner readers/writers with their replacement. Mandatory runtime/data/registry cleanup is not deferred to another PR; only broad obsolete prose cleanup remains Row 29.

## 28. Row #26 - Migrate Python producers and consumers

- **Scope:** **DEFERRED.** Track migration of Python news-pipeline producers and consumers to the shared feed-planning contracts and renamed state. Those stages remain unchanged until this separate phase is reopened; Row 22's new-family shared-ledger storage/readback/compaction support is not this deferred pipeline migration.
- **Dependency:** Row 22 and a separately authorized Python implementation phase.
- **Acceptance gates:** Bind Python news-pipeline reads and writes to the current shared ledger identities and prove real Parquet exchange without migrating deleted obsolete planner-family rows or changing other families.
- **Oracle:** Python and TypeScript read the same committed state consistently; this does not authorize digest worker parity or workflow cutover.

## 29. Row #27 - Migrate the console to derived ledgers

- **Scope:** **DEFERRED.** Replace console reads of legacy feed-health data with build-time reads of the TypeScript-derived registered ledgers. Keep the static publication boundary; do not add a runtime service.
- **Dependency:** Row 22 and a separately authorized console implementation phase.
- **Acceptance gates:** The console reads named committed data from the new registered ledgers and retains its existing behavior for missing and unreadable data; verify the relevant build-time output.
- **Oracle:** Published console content reflects the committed derived ledger; this does not authorize deletion of the global `feed-health` data or `source-health.json` until Python news-pipeline migration is complete.

## 30. Row #28 - Retire legacy feed-health publication

- **Scope:** **DEFERRED.** Remove the legacy `feed-health` ledger and `frontend/public/source-health.json` only after every named Python and console consumer is migrated and coverage is verified.
- **Dependencies:** Rows 26 and 27 complete, with evidence that no remaining consumer reads either legacy source.
- **Acceptance gates:** Search and verify the named producer/consumer paths, confirm migrated replacements cover their current behavior, then remove the legacy outputs and their obsolete readers together. Neither global output is deleted in Rows 22-27; Row 22's obsolete planner-family raw/compact cleanup is separate.
- **Oracle:** No active producer or consumer depends on the legacy ledger or JSON file; this does not claim broader worker parity or completion of the whole plan.

## 31. Row #29 - Remove obsolete duplicated planning and feedback prose

- **Scope:** Remove or split obsolete duplicated prose in Plans 66 and 67 and the feedback documentation. Keep each settled rule on its owning living page and repair links; do not create a separate note or decision record.
- **Dependencies:** Complete Row 22's replacement contracts and active-reader/writer cutover, then migrate any remaining dependant of the prose being removed. Any affected deferred work in Rows 26-28 remains a prerequisite for its own obsolete definition.
- **Files touched:** `TODO/20261020-66-feed-ingest-plan.md`, this plan, `docs/reference/feed-planner-ledgers.md`, and the affected living feedback/API/history pages.
- **Acceptance gates:** Confirm that no active dependant relies on each obsolete definition before removing it. Preserve the complete field mapping and API inventory during the current row-by-row review. Remove duplicate definitions rather than archiving them, and keep unfinished trial, recovery, polling, Python and console work explicitly unfinished.
- **Oracle:** Each settled rule has one current home and its dependants use the replacement; this cleanup does not deliver or approve any pending feature.
