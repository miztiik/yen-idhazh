# Plan 67 - Feed ingestion feedback and publisher selection

**Last Updated**: 2026-10-25
**Level**: 5 - broader feedback contracts remain design-gated; the owner authorized the feed-to-Parquet API delivery below.

**Owner clarification, 2026-10-24 UTC:** The current delivery target is
`fetch configured feeds -> parse feeds and retain item-level failures ->
select articles (screen and rank within one API) -> partition articles ->
persist dispatch rows as registered Parquet`.
Worker parity and integration with `digest.yml` and `work.py` are deferred.
They are not prerequisites for delivering this flow. This ruling supersedes
earlier parity-first and worker-ready wording below; contract binding checks
still apply to the persisted Parquet payload.

**Execution authorization, 2026-10-24 UTC:** The owner said "go ahead deliver"
for this flow. Its stage contracts, shared operations and HTTP routes form one
working PR phase: parsed batch -> combined selection -> partition ->
registered dispatch Parquet. The broader feedback/publisher rows remain
separate phases, not prerequisites for this API increment. Each stage receives
its own server-generated `batch_id`, since repeated selection or partition
calls can produce several outputs within one run. `correlation_id` remains
tracing context. The existing default-off service flag gates the new routes.

## 0. Operating contract

### Table A - Intent and execution boundary

| Id | Field | Contract |
| --- | --- | --- |
| A1 | Why this plan exists | Complete the unfinished nonsemantic ingestion, publisher-selection and operational-feedback work carried forward from [Plan 66](20261020-66-feed-ingest-plan.md), without rebuilding its delivered components or treating generated publication evidence as real delivery. |
| A2 | Scope confirmed by the owner | Keep measured operational feedback, including next-run updates, technical admission, temporary restrictions, recovery and polling. Exclude qualitative and semantic assessment. This is the owner's boundary clarification of 2026-10-24 UTC, not permission to implement an unsettled contract. |
| A3 | In scope | The original sixteen areas in Table B plus its separately tracked configured-priority review; applicable nonsemantic requirements from [I Feed](../docs/architecture/sources/i-feed.md); actual downstream costs and publication evidence; preservation of the existing fetch, parse, planning, replay and storage behavior. |
| A4 | Current readiness | Feed-to-Parquet API execution is authorized. Row 8 delivers that working phase with the stage-contract subset of Row 2; unrelated publisher/feedback designs remain open in Row 1. Resolve each remaining Table D decision before its affected build. |
| A5 | Strategy | Extend the existing TypeScript planner and shared fetch/parse units. Keep observation capture, estimates, policy decisions, selection and partitioning separate. Use the existing native ledger writer, not a second ingestion service or scoring framework. Do not add request idempotency to `/select-articles`. Fowler reviewed this strategy and dependency order; the corrected plan still requires owner contract approval. |
| A6 | Execution | Execute per docs/how-to/execute-a-plan.md: one owner carries the plan and delegates a row where delegation pays; keep parallel N = 4 rows in flight, refilling a slot as soon as a worker returns and never waiting on a merge; consult a persona only where two answers would lead to different code; AUTO-merge on green gates; honor the ESCALATE triggers in section 0. |
| A7 | Historical authority | Plan 66's sixteen original component rows remain historical delivery records. Its [owner-expanded follow-up work](20261020-66-feed-ingest-plan.md#20-owner-expanded-follow-up-work), including the pending nonsemantic inventory, supplies the unfinished scope. References below use area titles, not another plan's row numbers. Do not dispatch duplicate work from both plans. |
| A8 | Proposed versus approved | The feed-to-Parquet API flow is authorized, including one complete server-owned parse batch, combined screening/selection, separate partition/persistence APIs, server-generated batch identities and no selection idempotency or input-count cap. The configured 100-article limit bounds output only. Worker parity and production integration are deferred. Approved publisher identity, lifecycle, exposure and operational-score decisions are recorded in their owning [publisher](../docs/architecture/contracts/publisher-identity.md), [curation](../docs/architecture/sources/feed-curation.md) and [feedback](../docs/architecture/contracts/feed-ingest-feedback.md) pages. Publisher mappings remain curated data; uncertain matches stay unknown. Conditional HTTP is excluded. D3/D4 observation and settlement rulings and D8 requests-first eligibility are recorded in the feedback contract. D5 admission, restriction and polling thresholds are separate, unapproved, and do not block the authorized API increment or permit restrictions on ordinary fetches. |
| A9 | Work surfaces | Implement from current `main` in dedicated worktrees. This coordinator's old `feed-ingest-plan-engine` branch already shipped through [#1612](https://github.com/miztiik/yen-idhazh/pull/1612); do not push it to deliver this continuation. Adopt the existing cache branch before creating another one for that work. |

### Table B - Original sixteen pending areas and the separate priority-review task

| Id | Area from the pending inventory | What remains | Delivery rows |
| --- | --- | --- | --- |
| B1 | Publisher identity | Naming documentation shipped in [#1691](https://github.com/miztiik/yen-idhazh/pull/1691). Runtime validation, catalog references, curated mappings and compatible recorded identities remain. | 1, 2, 3 |
| B2 | `/select-articles` | Read the complete server-owned parse batch by `batch_id`; screen and rank within one API, returning selected articles and exclusions. Continue through the partition and persistence APIs. Do not accept caller paths or require idempotency. | 1, 2, 8 |
| B3 | Publisher breadth | Apply a data-only soft exposure preference using confirmed publisher identities and existing numeric priority, not article-quality comparison. | 1, 9 |
| B4 | Common fetch/parse observations | Finish uniform actual-work observations in `/fetch`, `/parse` and `/plan`, reusing facts already captured. | 1, 2, 4 |
| B5 | Article-level source rollups | Aggregate access and technical extraction outcomes separately from RSS success and request counts. | 6 |
| B6 | Failure and cost attribution | Distinguish source, pipeline and unresolved causes; keep real costs even when their attribution is unresolved. | 5 |
| B7 | Evidence definitions and support | Settle units, denominators, distinct keys, age, coverage, windows, normalization, priors, decay, missingness and qualification. | 1, 2, 7 |
| B8 | Durable next-run feedback | Settle outcomes once, preserve partial/failed-run facts, recover delayed and overlapping updates, and make the next allocation use compatible state. | 10 |
| B9 | Technical admission and trials | Use bounded article samples, report every attempted outcome and return review when support is insufficient. | 11 |
| B10 | Temporary access restrictions and recovery | Restrict only supported scope, permit due probes and require observed recovery. Permanent retirement remains curated. | 12 |
| B11 | Adaptive feed polling | Use exact-URL discoveries and actual poll costs before requesting a feed; preserve freshness and bounded exploration. | 13 |
| B12 | Conditional HTTP | Removed from this plan by owner ruling on 2026-10-24. Ordinary feed fetch behavior remains; no validators, cached-body state or `304` handling will be added here. | - |
| B13 | URL hygiene corrections | Correct structured host/path matching; separately review and approve identity-changing query cleanup and migrations. | 15, 16 |
| B14 | Operational review and integration | Distinguish source deterioration from pipeline release failures and prove the complete feedback-and-next-consumer flow. | 19 |
| B15 | Real Phase 2 outcomes | Join genuine worker/model costs, publication and leads through actual producer/consumer identities; do not substitute generated fixtures. | 17, 18 |
| B16 | Cache profiling and combined hosted proof | Adopt the implemented cache PR, review its final candidate, and complete the previously requested integrated proof. Actual hardware counters remain unmeasured when permission is denied. | 20 |
| B17 | Reusing curated editorial priorities | Review useful configured watchlist, theme and carrier-priority inputs from the Python path; implement only approved numeric terms from recorded evidence, without copying its selections or introducing qualitative analysis. | 21 |

### Table C - Explicit exclusions and their cost

| Id | Outside this plan's current permission | Cost of leaving it out | What would bring it in |
| --- | --- | --- | --- |
| C1 | Semantic quality scoring, factual verification, semantic novelty, story classification and new content deduplication | Selection cannot determine truth, importance, repeated meaning or new developments. Technical access and numeric priority do not answer those questions. | A separate owner-approved assessment design, controlled model destination and evaluation contract. |
| C2 | Automatic formula/weight promotion, taxonomy reassignment and qualitative drift controls | Operational estimates can update, but the system does not teach itself a new formula or editorial classification. | A separate policy-comparison and promotion plan with independent outcomes. |
| C3 | Removing the production worker's existing fetch and summarization behavior | The worker must still fetch and summarize assigned articles. The TypeScript plan must not silently replace those worker duties. | A separate owner-approved worker redesign. |
| C4 | Hard day-wide publisher quotas, equal-share obligations or selection blocking because history is missing | Breadth is a preference, not a guarantee. A prolific publisher can still supply multiple selected articles. | A separate owner decision changing the already confirmed soft-limit intent. |
| C5 | Automatic permanent retirement or a second retirement file/index | Runtime evidence can stop ordinary work temporarily, but cannot rewrite curated membership. | A separately approved catalog-transition authority; current retirement authority remains `config/sources.json`. |
| C6 | Local Python execution, Python packages in isolated TypeScript work, broad Python runtime changes, or new test functions without approval | Some native compatibility and downstream execution must be established by existing repository CI or a separately authorized integration. | An explicit scoped exception; shared declarations, migrations and binding compatibility remain subject to the existing approved boundary. |
| C7 | Raising host security privileges to obtain hardware counters | A stock runner may prove honest counter unavailability, not measured cache hits/misses. | An already-permitted operator-controlled Linux host; do not weaken kernel permissions. |
| C8 | Conditional feed requests, cached bodies, `304` handling and recovery | Feed polls may transfer the same body again, using more network bytes and time. | A separate owner-approved plan with a bounded cache and replay contract. |

### Table D - Required design decisions and stop conditions

| Id | Decision to settle | Required output before the affected build | Authority and affected rows |
| --- | --- | --- | --- |
| D1 | Publisher catalog and recorded identity | Settled: `publishers[]` has `id` and `display_name`; feeds have nullable `publisher_id`; no separate alias, reconciliation or provenance fields; IDs stay immutable. Reviewed config changes and Git history record mapping decisions. AI may help find publisher-owned evidence; uncertain mappings remain null. `added_on` is the UTC date first entered; new retirements have `retired_on` and an open lower-case `retirement_reason`; missing legacy values stay unknown. Old config without `publishers` reads as empty; missing values stay unknown; undefined nonnull references fail. Compatible-reader tests belong in Row 2; evidence-backed mapping data belongs in Row 3. | Contract settled by owner; Rows 2, 3, 9 deliver it. |
| D2 | Selection input and result | Settled for authorized API delivery: selection reads the complete parsed batch by server-generated UUIDv4 `batch_id`. Repeated calls create new stage IDs, not replay keys. A correlation groups observations, not files. Selection returns existing selection/exclusion rows; partition takes its saved batch ID and optional strategy/shards; persistence takes the partitioned batch ID. The configured 100-article limit bounds output only. Native snapshots, exact lookup and error behavior are declared in [operator APIs](../docs/architecture/sources/feed-operator-api.md#selection-partition-and-persistence-apis). | Execution authorized by owner on 2026-10-24; Rows 2 and 8 implement this subset without waiting for publisher/feedback designs. |
| D3 | Operational observations and estimates | Owner ruling, 2026-10-24 UTC: extend existing records with actual article-request totals, technical extraction outcomes and supported failure causes; keep source, pipeline and unresolved attribution distinct; save per-source operational state with evidence dates, coverage and policy version. Collect actual work for every fetch, parse and technical check; do not cap telemetry at 25 articles. No CPU or memory costs are invented. The configurable rolling closed-UTC-day window (default seven), support floor 20, 80 percent coverage and equal thirds remain approved. Requests are the only eligible component until CPU/private memory are attributable; no renormalization, requests at most one third, no impact for unqualified evidence, no RSS fallback. [The feedback contract](../docs/architecture/contracts/feed-ingest-feedback.md#d3-approved-observation-scope-and-remaining-field-details) holds the implementation details. | Observation behavior is approved; native field names and bindings are implementation details unless they change its meaning. Rows 2, 4, 5, 6, 7. |
| D4 | State ownership and settlement | Owner rulings, 2026-10-24 UTC: use a configurable rolling closed-UTC-day window (default seven), read registered Parquet ledgers from `state/raw/` and `state/compact/` using existing precedence, allow concurrent runs and fail gracefully. Preserve immutable per-run observations. If another run saves first, recalculate only the derived per-source operational state from newer records; if save fails, retain old state and report failure. Already-running selection keeps its original state revision. Report corrections outside the configured window but exclude them from its score. If current state is unreadable, use valid saved state as stale evidence with its original UTC range; if none is readable, continue without adjustment and report unverified restrictions. Never replace saved state with empty history. Persist derived state as a registered Parquet ledger payload, never a JSON sidecar. These behaviors are approved; see [the feedback contract](../docs/architecture/contracts/feed-ingest-feedback.md#d4-approved-state-behavior-and-implementation-details) for implementation details. No global lock, run-wide serialization or selection idempotency. | Settlement behavior is approved; schema spelling and publication-adapter details need no further owner vote unless they change that behavior. Rows 2, 10. |
| D5 | Activation and work limits | A2 conditional approval: for trial measurement only, select up to 100 distinct articles from each non-overlapping age group `[24,36]`, `[12,24)`, `[6,12)`, `[2,6)`, `[0,2)` hours; fewer if unavailable. Retries and redirects can raise HTTP requests above 500 across the groups. Reuse existing freshness evidence and fetch/parse/Parquet path; do not change ordinary selection, input limits or APIs. Persist each considered entry's selected, capped, unknown-age or future-age disposition. First deliver approved telemetry Rows 2, 4, 5 and 6. The earlier config-only estimate is withdrawn; total implementation cost is not established. No other trial, restriction, recovery or polling threshold is approved; adaptive polling formula remains open. See [the feedback contract](../docs/architecture/contracts/feed-ingest-feedback.md#d5-proposal-bounded-controls-and-operational-review). | A2 only, conditional on total cost after telemetry; no new telemetry approval required. |
| D6 | Publisher exposure comparison | Settled 2026-10-24: use the approved 0.25 coefficient; count actual UTC-day publications plus current selections, divide by planned slots and cap at 1; known-empty history is zero, unavailable history uses current selections only and records the gap, and unknown publishers add no count; replace feed crowding rather than duplicate charging. | Approved; Row 9. |
| D7 | Conditional HTTP state | Removed by owner ruling on 2026-10-24. Conditional requests, validator state, cached bodies, `304` handling and cache-miss recovery are not required in this plan; see C8 for the cost and route to reconsideration. | Closed; no delivery row. |
| D8 | Isolated operational arithmetic and source-priority replacement | The approved isolated TypeScript score and RSS-penalty replacement are in [the feedback contract](../docs/architecture/contracts/feed-ingest-feedback.md#d8-proposal-replace-the-rss-penalty). The saved score trace is limited to operational-state status/revision, configured window/evidence dates and request counts/coverage. Keep policy version in derived operational state, not duplicated in the trace. Do not add restriction scopes or invented CPU/memory amounts. Requests-first eligibility, equal-thirds without renormalization, no impact for unqualified evidence and no RSS fallback remain approved. Do not stack RSS reliability, article-delivery loss and inverse yield as duplicate penalties or alter article-quality evidence. | Arithmetic and trace boundary approved and now declared/bound; Row 7 report calculation is underway, Row 10 still owns state-backed selection. Rows 2, 7, 10. |
| D9 | Changed canonical URL identity | Bounded old/new comparison; encoding and repeated-query semantics; tracking policy; explicit equivalence and ambiguity rules; read-side migration and cross-language consumers. Approval of the matcher correction is not approval of this migration. | Separate Level-5 approval in Row 16. |
| D10 | Genuine downstream invocation | Deferred by owner clarification on 2026-10-24. Deliver the feed-to-dispatch-Parquet flow first. Worker parity, the production adapter, workflow cutover and real downstream evidence require a later decision. | Not a gate for the current flow; Rows 17 and 18 deferred. |
| D11 | New finding during execution | A new persisted meaning, trust-boundary crossing, unrelated repair, scope change or unsupported cost claim. | STOP-AND-SURFACE per [scope changes](../docs/how-to/handle-scope-change.md); do not relax a check or silently narrow delivery. |
| D12 | Reusing curated editorial priorities | Name each proposed watchlist, theme or carrier term, its recorded input, independent meaning, existing/new config owner and default, no-double-counting rule, score evidence and reader-before-writer sequence. Preserve unknown evidence; no front-page-vote bonus, semantic comparison or wholesale Python-ranking port is implicitly approved. | Owner approval after Row 21's bounded review; no new term before that approval. |

## 1. Status Reckoner

### Table E - Meaningful PR phases

| Id | # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| E1 | 1 | Approve runtime contracts and activation policy | - | A | IN-FLIGHT | feed-ingest-feedback-selection | - | - |
| E2 | 2 | Land compatible shared readers before writers | 1 | B | IN-REVIEW | operational-score-contracts | [#1712](https://github.com/miztiik/yen-idhazh/pull/1712), [#1719](https://github.com/miztiik/yen-idhazh/pull/1719) | - |
| E3 | 3 | Implement curated publisher catalog references | 2 | C | DONE | publisher-catalog-support | [#1704](https://github.com/miztiik/yen-idhazh/pull/1704) | - |
| E4 | 4 | Wire common fetch and parse observations | 2 (observation contract slice landed; other Row 2 contracts remain open) | D | DONE | persist-ingestion-observations | [#1717](https://github.com/miztiik/yen-idhazh/pull/1717) | - |
| E5 | 5 | Classify failure and work attribution | 4 | E | IN-REVIEW | operational-request-evidence | [#1718](https://github.com/miztiik/yen-idhazh/pull/1718) | failure-attribution |
| E6 | 6 | Aggregate article delivery and request costs | 5 | F | IN-REVIEW (typed planner report; saved state remains Row 10) | operational-request-evidence | [#1718](https://github.com/miztiik/yen-idhazh/pull/1718) | - |
| E7 | 7 | Compute supported operational estimates | 6 | G | IN-REVIEW (report-only request estimate; no ranking change) | operational-score-contracts | [#1719](https://github.com/miztiik/yen-idhazh/pull/1719) | - |
| E8 | 8 | Deliver selection, partition and persistence APIs | - (authorized stage contracts included) | E | DONE | feed-ingest-feedback-selection | - | - |
| E9 | 9 | Apply the soft publisher-exposure preference | 8 | F | IN-REVIEW (current-run + fallback) | publisher-exposure-preference | [#1714](https://github.com/miztiik/yen-idhazh/pull/1714) | - |
| E10 | 10 | Settle feedback and consume it in the next allocation | 7, 8 | H | PENDING | - | - | - |
| E11 | 11 | Report bounded technical admission trials | 2, 4, 5, 6 | I | PENDING | - | - | - |
| E12 | 12 | Enforce temporary access restrictions and earned recovery | 11 | J | PENDING | - | - | - |
| E13 | 13 | Apply discovery evidence before feed polling | 12 | K | PENDING | - | - | - |
| E14 | 14 | Conditional HTTP (removed by owner ruling) | - | - | REMOVED | - | - | - |
| E15 | 15 | Correct structured host and path exclusions | - (matcher intent approved separately) | B | DONE | structured-url-exclusions | [#1703](https://github.com/miztiik/yen-idhazh/pull/1703) | 4985fe0e-ca49-4ad2-9aaa-cd31323d8c52; tests: fbf40c01-d984-48ef-b6a5-a75fb4afe74d |
| E16 | 16 | Review and migrate URL identity separately | 15 | L | PENDING | - | - | - |
| E17 | 17 | Prove dispatch-Parquet parity, then wire digest workers | 8 | A | DEFERRED | - | - | - |
| E18 | 18 | Connect actual downstream outcomes to the observer | 2, 10, 17 | M | DEFERRED | - | - | - |
| E19 | 19 | Review operational regressions and prove the live loop | 9, 12, 13, 14, 21 | N | PENDING | - | - | - |
| E20 | 20 | Adopt cache delivery and finish the combined hosted proof | - | Z | DONE | potential-fiesta | [#1671](https://github.com/miztiik/yen-idhazh/pull/1671), [#1707](https://github.com/miztiik/yen-idhazh/pull/1707) | 6a57ff1e-bdfc-4248-86f8-cd5b17c8bde2 |
| E21 | 21 | Review and reuse configured numeric priorities | 9 | O | PENDING | - | - | - |

The approved D3/D4 implementation sequence is Row 2 -> Row 4 -> Row 5 ->
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
raw/compact fixture compatibility through merged PR #1712. The current
operational-score-contracts phase adds the remaining operational-state and
saved-score trace contracts, compatible historical readers and registered
state ledger. It does not add a state writer or next-selector consumer; those
remain Row 10 work. This phase is in review; contract CI remains pending.

## 2. Shared implementation boundaries

### Table F - Where the six I Feed input areas belong

| Id | Input area | Producer and consumer |
| --- | --- | --- |
| F1 | Publisher exposure | Curated catalog supplies identity; actual publication supplies past exposure; `/select-articles` records current selection and the soft adjustment. A feed ID or common corporate owner is not a publisher. |
| F2 | Article access and technical extraction | `/fetch` records transport/access facts; `/parse` records technical extraction and warnings; shared `/plan` units emit the same facts; rollups group article outcomes. This is not qualitative article assessment. |
| F3 | Requests, retries and attributable work | Fetch units record actual HTTP attempts, redirect/retry work, waits and measured costs. DNS validation is a separate operation, not an invented on-wire HTTP request. Parse and downstream workers record their own real work. Replays and API call counts are not new outbound requests. |
| F4 | Evidence identity, age, support and coverage | Every producer retains source/run/attempt/correlation, event identity, relevant UTC times and revisions; the estimator retains raw units, denominators, support, missingness and the exact decision cutoff. |
| F5 | Exact-URL discoveries and cadence | Feed parsing plus deterministic eligibility and bounded seen history produce distinct new eligible URL keys per completed permitted poll. The scheduler consumes them before the next feed fetch, not only after parsing. New URL does not mean new story. |
| F6 | Worker/model costs, publication and leads | Actual downstream execution and the publication observer supply these facts. Fetch/parse cannot manufacture token cost, model waste, successful publication or lead selection. |

### Table G - Contracts and preservation requirements

| Id | Boundary | Required implementation |
| --- | --- | --- |
| G1 | Existing components | Reuse the Plan 66 shared writer, safe fetcher, parser, screening, curation, partitioner, request replay and native history readers. Existing CPU/RAM/PID instruments and separate reliability penalty are not new builds. |
| G2 | Native authority | Shared persisted payloads remain Pydantic-owned under `backend/idhazh/contracts/`, with small bound TypeScript copies, dated versions/changelogs and read-side migration. The existing planner-only event exception remains limited to that event stream. |
| G3 | Publisher identity | Follow [publisher identity](../docs/architecture/contracts/publisher-identity.md). `PublisherIdSchema` aliases `SlugSchema`; no runtime slug generation or inferred mappings. Old missing IDs remain unknown, not backfilled from today's catalog. |
| G4 | API placement | Follow the numbered API flow below. `/select-articles` owns both eligibility screening and ranking; there is no separate screening endpoint or caller-visible screening step. Selection, partitioning and persistence have schema-validated HTTP APIs backed by shared operations. `/plan` calls those same operations in order, without making HTTP requests to its own listener. |
| G5 | One selection input mode | Selection reads a complete server-owned parse batch through its approved run/batch identity. It does not accept article text, a caller path, a per-article ID list or require idempotency. `correlation_id` remains observation context, not a file locator. |
| G6 | Selection and dispatch result | Preserve the existing selection output format and unchanged selected candidate content, applying the existing limit of 100 selected articles to the whole batch. The partition stage produces the existing schema-validated dispatch rows; the planner persists them through the registered Parquet writer. This is the current delivery endpoint; worker parity and production integration are deferred. |
| G7 | Soft breadth | Count confirmed publishers, not feeds or stories. Use actual known publication exposure and current choices. Unknown day history falls back to current-run publisher exposure with an explicit unavailable status; unknown publishers are not distinct invented publishers. Do not add a hard day ceiling. |
| G8 | Observation independence | Distinct articles, allocated opportunities, HTTP attempts, polls and model time have different denominators. Retrying or replaying an article does not add an independent article vote. A nonallocated slot is not wasted; a model failure after usable extraction is not source-access failure. |
| G9 | Durable feedback | Preserve raw facts before final run success; each concurrent run may settle supported outcomes, and a stale publication recomputes derived state from newer committed records. The next decision names its compatible state revision and cutoff. Unknown, pending, missing, known empty and observed zero remain distinct. |
| G10 | Bounded reads and state | Use named run inputs, configured periods and existing ledger indexes. Declare maximum catch-up and insufficient-state behavior. New registered state may represent temporary restrictions, but must not become another permanent-retirement authority. |
| G11 | Technical admission and recovery | Report all sampled attempts, successful extraction warnings and exclusions. Technical success does not establish news value. Restriction expiry permits a probe, not automatic recovery. HTTP 403 alone proves neither paywall nor publisher-wide failure. |
| G12 | Actual costs | Retain source, pipeline and unresolved attribution; keep shared startup/infrastructure costs separate. Optional unmeasured resource values stay null. Hardware-counter permission denial is not a measured zero. |
| G13 | Historical behavior | Preserve original captured precision, UUID conventions, first-seen meaning, native logical commitments, old source snapshots and byte-exact completed request responses. Do not restamp old artifacts or derive ordering from UUID suffixes. |
| G14 | New modules | Paths marked `(new)` below are proposed files, not claims that they exist. Row 1 fixes contract names and exact payload shapes before implementation; update affected footprint lists before dispatch if approval changes them. Add no empty scaffolding. |

### Numbered API flow and payload boundaries

`/plan` coordinates the five operations without HTTP loopback. The numbered
Mermaid diagram and exact request/result fields now live in
[operator APIs](../docs/architecture/sources/feed-operator-api.md#numbered-api-flow).
One `batch_id` identifies each saved stage output; it is neither a correlation
nor a caller-supplied path.

1. Fetch input uses configured source identities and existing request/context
   controls; output supplies fetch references and typed outcomes, not raw
   bodies in the HTTP response.
2. Parse uses the existing per-document fetch reference and identity controls.
   The planner assembles one complete saved batch, retaining successful
   results and item-level failures; a combined batch is new work, not an
   existing `/parse` capability.
3. Selection reads the whole batch with configuration and bounded history.
   It performs screening internally, then ranks eligible articles. Output
   retains selected content, existing selection rows and typed exclusions.
   The configured article limit bounds selected output, not batch input.
4. Partition input is selected content and selection rows plus configured
   strategy and worker count. Output is schema-validated dispatch rows.
   Bin-packing changes assignments, not selection or ranking.
5. Persistence input is validated dispatch rows and writer context. Storage
   settings and destinations come from committed configuration, not request
   paths. Output names the registered Parquet files, row counts and digests;
   an empty result is explicit, and a failed write is an error.

The diagram moved to its owning page during API decomposition. Row 8 lists
the actual shared route, three operations, storage and focused integration
helper. Worker parity, artifact upload and production consumption remain
deferred.

### Table H - Gate records and evidence already available

| Id | Gate or retained delivery | Required use |
| --- | --- | --- |
| H1 | Local selection | Use [run the gates](../docs/how-to/run-the-gates.md), inspect the shared selector, then run only relevant TypeScript checks and named existing cases. Extend recorded fixtures/cases; do not introduce local Python execution or a new test function through this plan. Record selected inputs and results. |
| H2 | CI | Full repository CI on the exact merge candidate remains authoritative. Shared declarations require native compatibility/binding checks. Do not repeat an unchanged worker check or raise deadlines to buy a pass. |
| H3 | Reader-before-writer | Row 2 lands compatible declarations/readers before any new persisted fields are emitted. A later contract change returns to its owner; do not add a writer-only field. |
| H4 | Existing live ingestion proof | [Run 40029996902](https://github.com/miztiik/yen-idhazh/actions/runs/40029996902) proves selected HTML/native planning; [run 40047886723](https://github.com/miztiik/yen-idhazh/actions/runs/40047886723) adds real task/resource evidence. Retain them; neither proves genuine reader publication. |
| H5 | Exposing CPU and memory metrics reports | [#1669](https://github.com/miztiik/yen-idhazh/pull/1669) merged visible resource reporting and independent machine RAM; [#1673](https://github.com/miztiik/yen-idhazh/pull/1673) merged real target-PID CPU and HTTP task lifecycle. Code is delivered, not another pending build. Row 20 closes the remaining combined checkbox-enabled hosted proof. |
| H6 | Cache adoption snapshot | Child reports final head `baa2431cb0d05936f3d107055d3b53e6b97315d7` and green [CI 40095745824](https://github.com/miztiik/yen-idhazh/actions/runs/40095745824). Coordinator review and the combined hosted proof are not yet complete. Refresh PR/head/checks and inspect artifacts before any merge. No child merge or dispatch is authorized. |
| H7 | Published surface | Only a row that changes the published site needs the integrated-browser smoke and relevant design review. Operator report changes still need actual Markdown rendering and sufficient unavailable/empty presentation, not a new dashboard. |
| H8 | Closure | Each row records its oracle, exact candidate and applicable results. Original component delivery, a generated audit, a documented decision, a green CI run and actual production integration are separate claims. Preserve open decisions instead of marking the overall plan complete. |

## 3. Row #1 - Approve runtime contracts and activation policy

- **Scope:** Record settled decisions and close only the policy choices that still need owner approval before their dependent implementation.
- **Level:** 5; consultation and documentation only until sign-off.
- **Files touched:**
  - `docs/architecture/contracts/publisher-identity.md`
  - `docs/architecture/contracts/feed-ingest-feedback.md`
  - `docs/architecture/sources/feed-operator-api.md`
  - `docs/architecture/sources/feed-curation.md`
  - `docs/architecture/sources/i-feed.md`
- **Acceptance gates:** Local: documentation selector, named-link/anchor checks and ASCII/whitespace. CI: documentation-selected checks. D1, D2, D6 and D7 are settled. D3 observation scope and D4 settlement behavior are owner-approved; declare their native payload fields, producer bindings and registered Parquet ledger before writers, without another policy vote unless the meaning changes. D8 arithmetic and trace boundary are approved and now declared/bound; Row 10 must still implement state publication and selection consumption. D5 thresholds remain unapproved except for A2's conditional age-group trial. No other D5 approval is needed to implement Rows 2, 4, 5, 6, 7 and 10 without restricting ordinary fetches.
- **Oracle:** Walk one real recorded article and one late corrected outcome from capture to the proposed next decision without inventing a field, timestamp, denominator or authority; this cannot establish effectiveness of an unbuilt policy.

### Table I - Decisions

| Id | Decision | Authority |
| --- | --- | --- |
| I1 | Contract approval is a real dependency, not a build worker's discretion. Record the isolated TypeScript arithmetic boundary and the source-priority replacement rule. | Owner sign-off required; Fowler proposes contract construction. |

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
| L1 | A new TypeScript-only persisted-state exception | The existing exception covers planner events only. | Separate owner approval and updated native ownership/binding design. | CLAUDE.md Guardrail 3. |

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
| M1 | Reuse the approved slug contract and explicit catalog review. Preserve distinct editorial publications under common ownership. Curate only confirmed mappings; leave uncertainty unknown. | Publisher identity contract and owner-approved D1. |

### Table N - Rejected alternatives

| Id | Option | Why rejected | Cost to take | Authority |
| --- | --- | --- | --- | --- |
| N1 | Infer all mappings from feed prefixes, titles or domains | Valid spelling does not prove one newsroom, and wrong grouping corrupts exposure. | Human review of the disputed identities and explicit reconciliation of recorded meaning. | Owner's curated-identity decision. |

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
| R1 | Treat every failed summary or HTTP 403 as source misconduct/paywall | Confuses our failures, access restrictions and confirmed paywalls. | Obtain the missing causal or scoped access evidence first. | Owner's technical-only boundary. |

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
| W1 | Read one complete server-owned parse batch by `batch_id`; process all results in one selection call. Do not pass article lists or paths. `correlation_id` groups observations and does not locate the file. | Owner-authorized delivery; exact stage contracts in the owning API documentation. |
| W2 | Use one correlation ID for the batch and distinct event IDs for recorded events. Apply the existing 100-article limit only to selection output. | Owner direction; preserve existing observation and selection contracts. |
| W3 | Keep item-level failures in the batch and existing exclusion shapes; continue with usable results. A missing batch returns 404; damaged stored content returns 500. | Owner direction and authorized API error contract. |
| W4 | Do not require idempotency or a replay key for selection. Preserve existing selection rows and return a new saved result identity for each call. | Owner direction; shared schemas and API integration coverage. |
| W5 | Screening and ranking are internal parts of `/select-articles`, not separate caller-visible steps. The numbered API diagram has moved to the owning API page and is linked above. | Owner direction, 2026-10-24 UTC. |

### Table X - Rejected alternatives

| Id | Option | Why rejected | Cost to take | Authority |
| --- | --- | --- | --- | --- |
| X1 | Arbitrary file paths or a second selector hidden inside the route | Crosses the trust/input boundary or causes API/planner behavior to drift. | A separate approved file capability or algorithm change; neither is needed for this API. | Existing operator API and owner scope. |

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
- **Level:** 3 after D6 approval; a changed score meaning returns to its native-contract owner.
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
| Y1 | Use actual known published exposure, not unpublished shadow selections. Unknown history never blocks selection or becomes invented zero history. Record the replaced term so the same crowding is not charged twice. | Owner's soft, data-only publisher-breadth decision and D6. |

### Table Z - Rejected alternatives

| Id | Option | Why rejected | Cost to take | Authority |
| --- | --- | --- | --- | --- |
| Z1 | Hard day cap or keeping the supposedly stronger story | Both change the approved intent; the latter adds unavailable qualitative assessment. | New owner-approved quota or assessment design and its reader trade-offs. | Owner clarification of 2026-10-24 UTC. |

## 12. Row #10 - Settle feedback and consume it in the next allocation

- **Scope:** Close the durable operational loop with concurrent observation settlement, fresh-base derived-state publication and an actual next-run allocation consumer, not report-only estimates.
- **Level:** 3 after D4/D8 approval.
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
| AD1 | Any-one-success admission | Fails the named mostly-blocked-feed case and hides sampling support. | Owner approval to accept that reduced evidence standard and its wasted-request risk. | I Feed first-delivery intent. |

## 14. Row #12 - Enforce temporary access restrictions and earned recovery

- **Scope:** Apply approved temporary restrictions to ordinary work and use due permitted probes and fresh evidence for recovery.
- **Level:** 3 after D4/D5 approval.
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
| AF1 | Automatic recovery at timeout or whole-publisher bans from one page | Neither proves restoration nor the larger failure scope. | Collect the required scoped evidence and obtain authority for any escalation. | I Feed lifecycle and owner retirement ruling. |

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
| AH1 | Poll everything, then apply cadence after parsing; or silently cap normal fetches | The first saves no acquisition work; the second chooses an unapproved coverage trade-off. | Owner-approved poll budget, maximum wait and coverage consequence before activation. | Owner scope and I Feed acquisition boundary. |

## 16. Row #14 - Removed from Plan 67

Owner ruling, kumarsnaveen_microsoft, 2026-10-24 UTC: remove conditional feed
requests from this plan. Keep ordinary feed fetching; do not add validators,
cached-body state, `304` handling or recovery requests. The cost is repeated
network transfer and time when a feed body is unchanged. A separate
owner-approved plan is required to revisit this optimization.

### Table AI - Decisions

| Id | Decision | Authority |
| --- | --- | --- |
| AI1 | Conditional HTTP and cached-body handling are excluded from Plan 67; ordinary feed fetching remains. | Owner ruling, 2026-10-24. |

## 17. Row #15 - Correct structured host and path exclusions

- **Scope:** Replace the existing article-prefetch predicate and audit verification with one pure structured host/path matcher, preserving the exclusion intent rather than adding a parallel pool filter over the old substring check.
- **Level:** 2; no URL identity change.
- **Authorization:** The owner approved this matcher correction independently of
  Row 1's open feedback design on 2026-10-24 UTC. The earlier Row 1 dependency
  does not block this phase. Delivery is complete with green CI; PR merge awaits
  owner review. This phase does not
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
| AK1 | Preserve exclusion intent, reason and scope. State explicitly that this phase corrects the isolated TypeScript path, not an unapproved Python runtime rewrite. | I Feed host/path proposal and owner runtime boundary. |

### Table AL - Rejected alternatives

| Id | Option | Why rejected | Cost to take | Authority |
| --- | --- | --- | --- | --- |
| AL1 | Delete the affiliate exclusion or combine query cleanup here | The first admits excluded material; the second crosses a separate identity boundary. | Owner review of the editorial change or Row 16's distinct migration. | Owner scope and correction levels. |

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
| AM1 | Current generic-key removal and decoded query reconstruction are verified review targets, not permission to change identities silently. Preserve original addresses, versions and ambiguous history. | Separate D9 owner approval and identity contract. |

### Table AN - Rejected alternatives

| Id | Option | Why rejected | Cost to take | Authority |
| --- | --- | --- | --- | --- |
| AN1 | Rewrite historical URL hashes or use blanket old-key fallback | Destroys original identity or recreates the collision being corrected. | Preserve old records, declare ambiguity and perform bounded requalification where equivalence is not supported. | Native historical-read contract. |

## 19. Row #17 - Prove dispatch-Parquet parity, then wire digest workers

**Status:** Deferred by owner clarification on 2026-10-24 UTC. The following
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
| AO1 | Production workers currently read Python `RunPlan` rows and do not consume TypeScript dispatch assignments. Build and pass the parity gate before changing `digest.yml`; then the worker reads the registered dispatch Parquet and retains its existing fetch/summarize duties. | Owner direction and the existing producer/consumer boundary. |

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
| AR1 | Close Phase 2 with another generated full audit | Repeats evidence already available and still proves no real publication integration. | Run the approved real caller against genuine downstream output and inspect the resulting joins. | Owner's outstanding Phase 2 requirement. |

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
| AS1 | Operational review examines independent technical outcomes and source/pipeline revisions. Keep automatic formula tuning and qualitative drift assessment excluded. Missing live evidence keeps the relevant closure claim open, not the entire implementation falsely complete. | Owner-confirmed scope and I Feed drift discipline. |

### Table AT - Rejected alternatives

| Id | Option | Why rejected | Cost to take | Authority |
| --- | --- | --- | --- | --- |
| AT1 | Use a higher internal score or one fixed fixture as live effectiveness proof | The objective cannot grade itself, and fixtures do not settle real next-run wiring. | Inspect the named actual run/state/decision chain and bounded independent technical outcomes. | I Feed validation intent. |

## 22. Row #20 - Adopt cache delivery and finish the combined hosted proof

- **Scope:** Adopt the cache delivery, correct the named-module sparse checkout omission with an existing bounded workflow regression, and complete the combined hosted proof. No further implementation or dispatch is part of this closure.
- **Delivery status:** DONE. Cache PR [#1671](https://github.com/miztiik/yen-idhazh/pull/1671) merged at `b037f8`; URL matcher PR [#1703](https://github.com/miztiik/yen-idhazh/pull/1703) merged at `52a0e1`; sparse checkout correction [#1707](https://github.com/miztiik/yen-idhazh/pull/1707) merged at `962b4cc`. The first authorized [run 40131128910](https://github.com/miztiik/yen-idhazh/actions/runs/40131128910) on `b037f8` failed before live work. The owner explicitly authorized one corrected [run 40133676513](https://github.com/miztiik/yen-idhazh/actions/runs/40133676513), which succeeded on exact head `b1830d0f0a684e5c09715f597ca05542d38edcd2`, attempt 1.
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
| AU1 | Adopt `optional-cache-probes` in `potential-fiesta`, session `6a57ff1e-bdfc-4248-86f8-cd5b17c8bde2`. Review the live PR diff before merging; any necessary source correction returns to that owner and updates its footprint. Preserve H/I/J/K and existing notices when cache evidence is absent. | Existing delegated delivery and final review requirement. |
| AU2 | The default-false independent cache controls, measured working-set curve, exact unavailable LLC aliases and scoped native build audit are distinct evidence. A genuinely permitted hardware-counter reading remains open if no permitted host is available. | Existing cache contract and owner no-Python boundary. |

### Table AV - Rejected alternatives

| Id | Option | Why rejected | Cost to take | Authority |
| --- | --- | --- | --- | --- |
| AV1 | Rebuild the instruments, merge an earlier green head, or claim denied counters measured | Duplicates delivered work, bypasses final review or overstates the instrument. | Review the current exact candidate and obtain an already-permitted host for actual counter measurement. | Existing adoption and measurement requirements. |

## 23. Row #21 - Review and reuse configured numeric priorities

- **Scope:** Review useful Python watchlist, theme and carrier-priority behavior against recorded TypeScript inputs, then implement only explicitly approved numeric terms while preserving the distinct reliability and publisher-exposure adjustments.
- **Level:** 5 for the policy/evidence proposal; no new bonus or changed persisted meaning before D12 approval.
- **Files touched:**
  - `config/feed-ingest-plan.json`
  - `packages/common-contracts/src/schemas/config.schema.ts`
  - `packages/common-contracts/src/schemas/source.schema.ts`
  - `backend/idhazh/contracts/feed_ingest_candidate.py`
  - `services/feed-ingest-plan/src/curate-article-portfolio/quality-decoupler.ts`
  - `services/feed-ingest-plan/src/curate-article-portfolio/carrier-cluster.ts`
  - `services/feed-ingest-plan/src/curate-article-portfolio/quota-normalizer.ts`
  - `services/feed-ingest-plan/test/curate.test.ts`
  - `services/feed-ingest-plan/test/article-assessments.test.ts`
  - `docs/architecture/sources/feed-curation.md`
- **Acceptance gates:** Local: compare the named rules in `backend/idhazh/rank.py` with existing recorded headline matches, carrier witnesses and TypeScript scoring. Record adopted and rejected terms with reasons before seeking D12 approval. For approved terms, land compatible enclosing readers before writers, update the exact binding/migration footprint, and extend existing curation/assessment cases for config substitution, unknown evidence and duplicate carriers. CI: strict types, binding/native decision replay and historical compatibility. Do not change Python ranking runtime or assume its exact selections are the target.
- **Oracle:** Varying one approved configured priority with the same recorded input changes only its declared score contribution and actual selection trace, without repeated carrier charges or inferred qualitative verdicts; this cannot establish that a higher numeric priority means a better story.

### Table AW - Decisions

| Id | Decision | Authority |
| --- | --- | --- |
| AW1 | Reuse useful explicit inputs, not the entire Python algorithm. Current configured theme/entity matches remain observations until an independently approved scoring rule consumes them. Preserve TypeScript opportunity normalization, set-aware choices and exploration. | Owner's requested priority-review task and D12. |

### Table AX - Rejected alternatives

| Id | Option | Why rejected | Cost to take | Authority |
| --- | --- | --- | --- | --- |
| AX1 | Copy every Python bonus, restore a removed front-page bonus, or treat word matches as story quality | Adds unapproved policy, duplicate influence or qualitative claims unsupported by the observations. | Review the individual term, its evidence and counterexample, then obtain approval with compatible score readers. | Owner's nonsemantic scope and independent-priority requirement. |
